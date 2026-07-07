import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from requests.cookies import RequestsCookieJar, create_cookie

from insar_pilot.download import DownloadService, DownloadStorage, OrbitDownloadService, SearchService, create_dem_task
from insar_pilot.download.credentials import load_earthdata_credentials, save_earthdata_netrc
from insar_pilot.download.dem_service import DemCoveragePlanner, OpenTopographyDemService
from insar_pilot.download.geometry import (
    aoi_geojson_from_inputs,
    bbox_to_polygon,
    polygon_from_kml,
    polygon_to_wkt,
    polygons_from_geojson,
)
from insar_pilot.download.map_credentials import (
    load_tianditu_key,
    save_tianditu_key,
)
from insar_pilot.download.map_credentials import (
    test_tianditu_key as check_tianditu_key,
)
from insar_pilot.download.models import DemCoveragePlan, DownloadResult, DownloadTask, SceneRecord, SearchCriteria
from insar_pilot.download.network import NetworkConfig
from insar_pilot.download.opentopography_credentials import (
    load_opentopography_key,
    save_opentopography_key,
)
from insar_pilot.download.opentopography_credentials import (
    test_opentopography_key as check_opentopography_key,
)
from insar_pilot.download.project_importer import import_downloads_to_project
from insar_pilot.download.providers.asf_provider import ASFProvider
from insar_pilot.download.tile_proxy import TiandituTileProxy
from insar_pilot.services.iw_recommendation import BurstFootprint, IwFootprint, IwRecommendationResult


def _qt_app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    return app if app is not None else QApplication([])


REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeProduct:
    def __init__(self, properties):
        self.properties = properties
        self.geojson = properties.get("geojson", {})

    def get_urls(self):
        return [self.properties["url"]]


class _FakeResponse:
    def __init__(self, chunks, *, error=None, status_code=200, url="https://example.test/file.zip"):
        self._chunks = chunks
        self._error = error
        self.headers = {"content-length": str(sum(len(chunk) for chunk in chunks))}
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self._error:
            raise self._error

    def iter_content(self, chunk_size):
        yield from self._chunks

    def close(self):
        pass


class _FakeSession:
    def __init__(self, response):
        self.response = response
        self.urls = []

    def get(self, url, stream=True, timeout=60, **kwargs):
        self.urls.append(url)
        return self.response


class _SequenceSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []
        self._earthdata_username = "alice"
        self._earthdata_password = "secret"
        self._asf_cookie_jar = {}
        self.cookies = {}

    def get(self, url, stream=True, timeout=60, **kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


class _FakeOrbitService:
    def __init__(self):
        self.tasks = []

    def download(self, task, *, progress_callback=None, cancel_check=None):
        self.tasks.append(task)
        completed = task.with_updates(
            status="completed",
            local_path=str(Path(task.output_dir) / "Orbit" / f"{task.scene.scene_id}.EOF"),
            message="Orbit download completed.",
        )
        if progress_callback:
            progress_callback(completed)
        return DownloadService._result_from_task(completed)


class _FakeAria2Process:
    def __init__(self, command, *, payload=b"abc123", returncode=0, stderr="", running_polls=0):
        self.command = command
        self._payload = payload
        self._final_returncode = returncode
        self._stderr = stderr
        self._running_polls = running_polls
        self._poll_count = 0
        self.returncode = None

    def poll(self):
        if self._poll_count < self._running_polls:
            self._poll_count += 1
            return None
        self._finish()
        return self.returncode

    def communicate(self):
        self._finish()
        return "", self._stderr

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        if self.returncode is None:
            self._finish()
        return self.returncode

    def _finish(self):
        if self.returncode is not None:
            return
        if self._payload:
            part_path = self._part_path()
            part_path.parent.mkdir(parents=True, exist_ok=True)
            part_path.write_bytes(self._payload)
        self.returncode = self._final_returncode

    def _part_path(self) -> Path:
        directory = Path(self.command[self.command.index("--dir") + 1])
        output = self.command[self.command.index("--out") + 1]
        return directory / output


class _FakeCancelableAria2Process(_FakeAria2Process):
    def __init__(self, command, *, payload=b"abc"):
        super().__init__(command, payload=payload)
        self._terminated = False

    def poll(self):
        return self.returncode if self._terminated else None

    def terminate(self):
        part_path = self._part_path()
        part_path.parent.mkdir(parents=True, exist_ok=True)
        part_path.write_bytes(self._payload)
        self._terminated = True
        self.returncode = -15


def _patch_aria2(monkeypatch, *, payload=b"abc123", returncode=0, stderr="", running_polls=0):
    calls = []
    monkeypatch.setattr("insar_pilot.download.download_service.shutil.which", lambda name: "/usr/bin/aria2c")

    def _popen(command, stdout=None, stderr=None, text=False, shell=False):
        assert shell is False
        process = _FakeAria2Process(
            command,
            payload=payload,
            returncode=returncode,
            stderr=stderr,
            running_polls=running_polls,
        )
        calls.append({"command": command, "stdout": stdout, "stderr": stderr, "text": text, "shell": shell})
        return process

    monkeypatch.setattr("insar_pilot.download.download_service.subprocess.Popen", _popen)
    return calls


def _patch_cancelable_aria2(monkeypatch, *, payload=b"abc"):
    calls = []
    monkeypatch.setattr("insar_pilot.download.download_service.shutil.which", lambda name: "/usr/bin/aria2c")

    def _popen(command, stdout=None, stderr=None, text=False, shell=False):
        assert shell is False
        process = _FakeCancelableAria2Process(command, payload=payload)
        calls.append({"command": command, "stdout": stdout, "stderr": stderr, "text": text, "shell": shell})
        return process

    monkeypatch.setattr("insar_pilot.download.download_service.subprocess.Popen", _popen)
    return calls


class _FakeMapResponse:
    def __init__(self, *, content=b"\x89PNG\r\n", content_type="image/png", status_code=200):
        self.content = content
        self.headers = {"content-type": content_type}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeMapNetwork:
    timeout_seconds = 1

    def __init__(self, response):
        self.response = response
        self.urls = []

    def session(self):
        return self

    def get(self, url, timeout=None):
        self.urls.append(url)
        return self.response


class _FakeOtResponse:
    def __init__(self, chunks, *, content_type="image/tiff", status_code=200):
        self._chunks = chunks
        self.content = b"".join(chunks)
        self.text = self.content.decode("utf-8", errors="ignore")
        self.headers = {
            "content-length": str(sum(len(chunk) for chunk in chunks)),
            "content-type": content_type,
        }
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        yield from self._chunks


class _FakeOtSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, stream=False, timeout=None):
        self.calls.append({"url": url, "params": params or {}, "stream": stream, "timeout": timeout})
        return self.response


class _FakeOtNetwork:
    timeout_seconds = 1

    def __init__(self, response):
        self.session_obj = _FakeOtSession(response)

    def session(self):
        return self.session_obj


def test_search_criteria_and_scene_round_trip():
    criteria = SearchCriteria(
        start_date="2024-01-01",
        end_date="2024-01-31",
        bbox="120,30,121,31",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
    )
    loaded = SearchCriteria.from_dict(criteria.to_dict())

    assert loaded.relative_orbit == 42
    assert loaded.aoi_mode == "bbox"

    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        coverage_percent=95.0,
        footprint_geojson={"type": "Polygon", "coordinates": [[[120, 30], [121, 30], [121, 31], [120, 30]]]},
    )

    assert SceneRecord.from_dict(scene.to_dict()) == scene
    assert scene.with_status("downloaded", "/tmp/S1_TEST.zip").local_path.endswith(".zip")


def test_network_config_direct_ignores_environment_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://bad-proxy.local:7890")

    session = NetworkConfig(mode="direct").session()

    assert session.trust_env is False
    assert session.proxies == {}


def test_network_config_manual_sets_proxy():
    config = NetworkConfig(
        mode="manual",
        http_proxy="http://127.0.0.1:7890",
        https_proxy="http://127.0.0.1:7890",
    )

    session = config.session()

    assert session.trust_env is False
    assert session.proxies["https"] == "http://127.0.0.1:7890"


def test_load_earthdata_credentials_from_netrc(tmp_path: Path):
    netrc_path = tmp_path / ".netrc"
    netrc_path.write_text(
        "machine urs.earthdata.nasa.gov\n  login demo_user\n  password demo_pass\n",
        encoding="utf-8",
    )

    credentials = load_earthdata_credentials(netrc_path)

    assert credentials is not None
    assert credentials.username == "demo_user"
    assert credentials.password == "demo_pass"


def test_search_service_returns_provider_records():
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="DESCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
    )

    class _Provider:
        def search(self, criteria):
            return [scene]

    criteria = SearchCriteria(
        start_date="2024-01-01",
        end_date="2024-01-31",
        bbox="120,30,121,31",
        orbit_direction="DESCENDING",
    )

    scenes = SearchService(provider=_Provider()).search(criteria)

    assert len(scenes) == 1
    assert all(scene.orbit_direction == "DESCENDING" for scene in scenes)


def test_asf_provider_maps_asf_products(monkeypatch):
    def _geo_search(**kwargs):
        assert kwargs["processingLevel"] == "SLC"
        assert kwargs["beamMode"] == "IW"
        assert kwargs["maxResults"] == 25
        return [
            _FakeProduct(
                {
                    "sceneName": "S1A_IW_SLC__TEST",
                    "startTime": "2024-01-01T00:00:00Z",
                    "platform": "Sentinel-1A",
                    "flightDirection": "ASCENDING",
                    "pathNumber": 42,
                    "polarization": "VV+VH",
                    "bytes": 104857600,
                    "url": "https://example.test/S1A_IW_SLC__TEST.zip",
                    "fileName": "S1A_IW_SLC__TEST.zip",
                    "geojson": {
                        "type": "Polygon",
                        "coordinates": [[[120, 30], [121, 30], [121, 31], [120, 30]]],
                    },
                }
            )
        ]

    monkeypatch.setattr("insar_pilot.download.providers.asf_provider.asf.geo_search", _geo_search)
    criteria = SearchCriteria(
        start_date="2024-01-01",
        end_date="2024-01-31",
        bbox="120,30,121,31",
        max_results=25,
    )

    scenes = ASFProvider().search(criteria)

    assert scenes == [
        SceneRecord(
            scene_id="S1A_IW_SLC__TEST",
            acquisition_time="2024-01-01T00:00:00Z",
            platform="Sentinel-1A",
            orbit_direction="ASCENDING",
            relative_orbit=42,
            polarization="VV+VH",
            size_mb=100.0,
            coverage_percent=0.0,
            status="available",
            local_path="",
            download_url="https://example.test/S1A_IW_SLC__TEST.zip",
            file_name="S1A_IW_SLC__TEST.zip",
            footprint_geojson={
                "type": "Polygon",
                "coordinates": [[[120, 30], [121, 30], [121, 31], [120, 30]]],
            },
        )
    ]


def test_aoi_geometry_helpers_support_bbox_wkt_and_kml(tmp_path: Path):
    assert bbox_to_polygon("120,30,121,31")[0] == (120.0, 30.0)
    wkt = "POLYGON((120 30,121 30,121 31,120 30))"
    assert polygons_from_geojson(aoi_geojson_from_inputs("wkt", wkt=wkt))[0][1] == (121.0, 30.0)
    kml = tmp_path / "aoi.kml"
    kml.write_text(
        "<kml><Document><Placemark><Polygon><outerBoundaryIs><LinearRing>"
        "<coordinates>120,30,0 121,30,0 121,31,0 120,30,0</coordinates>"
        "</LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>",
        encoding="utf-8",
    )
    assert polygons_from_geojson(aoi_geojson_from_inputs("kml", aoi_file=str(kml)))[0][2] == (121.0, 31.0)
    assert polygon_from_kml(kml)[1] == (121.0, 30.0)
    assert polygon_to_wkt(polygon_from_kml(kml)) == "POLYGON((120 30,121 30,121 31,120 30))"


def test_asf_provider_uses_original_kml_polygon_for_intersects(tmp_path: Path):
    kml = tmp_path / "aoi.kml"
    kml.write_text(
        "<kml><Document><Placemark><Polygon><outerBoundaryIs><LinearRing>"
        "<coordinates>120,30,0 121,30,0 121,31,0 120,30,0</coordinates>"
        "</LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>",
        encoding="utf-8",
    )

    assert ASFProvider._wkt_from_kml(kml) == "POLYGON((120 30,121 30,121 31,120 30))"


def test_asf_provider_does_not_limit_results_by_default(monkeypatch):
    def _geo_search(**kwargs):
        assert "maxResults" not in kwargs
        return []

    monkeypatch.setattr("insar_pilot.download.providers.asf_provider.asf.geo_search", _geo_search)
    criteria = SearchCriteria(
        start_date="2024-01-01",
        end_date="2024-01-31",
        bbox="120,30,121,31",
    )

    assert ASFProvider().search(criteria) == []


def test_asf_provider_accepts_compact_yyyymmdd_dates(monkeypatch):
    def _geo_search(**kwargs):
        assert kwargs["start"] == "2024-01-01T00:00:00Z"
        assert kwargs["end"] == "2024-01-31T23:59:59Z"
        return []

    monkeypatch.setattr("insar_pilot.download.providers.asf_provider.asf.geo_search", _geo_search)
    criteria = SearchCriteria(
        start_date="20240101",
        end_date="20240131",
        bbox="120,30,121,31",
    )

    assert ASFProvider().search(criteria) == []


def test_search_service_network_failure_is_catchable():
    class _FailingProvider:
        def search(self, criteria):
            raise RuntimeError("network down")

    criteria = SearchCriteria(start_date="2024-01-01", end_date="2024-01-31", bbox="120,30,121,31")

    try:
        SearchService(provider=_FailingProvider()).search(criteria)
    except RuntimeError as exc:
        assert "network down" in str(exc)
    else:
        raise AssertionError("provider failure should remain catchable by the GUI")


def test_search_criteria_accepts_kml_aoi():
    criteria = SearchCriteria(
        start_date="2024-01-01",
        end_date="2024-01-31",
        aoi_mode="kml",
        aoi_file="/tmp/aoi.kml",
    )

    loaded = SearchCriteria.from_dict(criteria.to_dict())

    assert loaded.aoi_mode == "kml"
    assert loaded.aoi_file.endswith(".kml")


def test_download_service_creates_tasks_with_slc_and_orbit_paths(tmp_path: Path):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    service = DownloadService()

    tasks = service.create_tasks([scene], tmp_path)

    assert len(tasks) == 2
    assert tasks[0].local_path == str(tmp_path / "SLC" / "S1_TEST.zip")
    assert tasks[1].local_path == str(tmp_path / "Orbit" / "S1_TEST.EOF")
    assert tasks[0].url == "https://example.test/S1_TEST.zip"


def test_download_service_uses_aria2_to_part_and_renames(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    service = DownloadService()
    monkeypatch.setattr(
        service, "_session", lambda username="", password="": _FakeSession(_FakeResponse([b"abc", b"123"]))
    )
    aria2_calls = _patch_aria2(monkeypatch, payload=b"abc123")
    updates = []

    tasks = service.create_tasks([scene], tmp_path, include_orbits=False)
    results = service.download(tasks, progress_callback=updates.append)

    assert results[0].status == "completed"
    assert Path(results[0].local_path).read_bytes() == b"abc123"
    assert not Path(results[0].local_path + ".part").exists()
    assert updates[0].message.startswith("Preparing ASF authentication for aria2c download:")
    assert updates[0].local_path.endswith(".zip.part")
    assert updates[-1].bytes_done == 6
    assert results[0].scene.status == "downloaded"
    assert results[0].backend == "aria2"
    assert aria2_calls[0]["shell"] is False
    command = aria2_calls[0]["command"]
    assert "--continue=true" in command
    assert "--max-connection-per-server=4" in command
    assert "--split=4" in command
    assert "--min-split-size=1M" in command
    assert "--load-cookies" not in command


def test_download_service_passes_asf_cookies_to_aria2_without_logging_secrets(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    session = _FakeSession(_FakeResponse([b"ok"]))
    session.cookies = RequestsCookieJar()
    session.cookies.set_cookie(create_cookie(name="asf-urs", value="super-secret-cookie", domain=".asf.alaska.edu"))
    service = DownloadService()
    monkeypatch.setattr(service, "_session", lambda username="", password="", network=None: session)
    aria2_calls = _patch_aria2(monkeypatch, payload=b"ok")

    result = service.download(service.create_tasks([scene], tmp_path, include_orbits=False))[0]

    command = aria2_calls[0]["command"]
    cookie_path = Path(command[command.index("--load-cookies") + 1])
    assert result.status == "completed"
    assert "--load-cookies" in command
    assert not cookie_path.exists()
    assert "super-secret-cookie" not in " ".join(command)
    assert "super-secret-cookie" not in DownloadService._safe_subprocess_excerpt(
        "Cookie: asf-urs=super-secret-cookie password=secret"
    )


def test_download_service_reattempts_slc_after_earthdata_redirect(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://datapool.asf.alaska.edu/SLC/SA/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    redirect = _FakeResponse(
        [],
        status_code=401,
        url=(
            "https://urs.earthdata.nasa.gov/oauth/authorize?"
            "client_id=BO_n7nTIlMljdvU6kRRB3g&response_type=code"
        ),
    )
    success = _FakeResponse([b"II"])
    session = _SequenceSession([redirect, success])
    auth_urls = []
    service = DownloadService()
    monkeypatch.setattr(service, "_session", lambda username="", password="", network=None: session)
    aria2_calls = _patch_aria2(monkeypatch, payload=b"II")
    monkeypatch.setattr(
        service,
        "_obtain_asf_cookie",
        lambda session, cookie_jar, username, password, network, auth_url="": auth_urls.append(auth_url),
    )

    result = service.download(
        service.create_tasks([scene], tmp_path, include_orbits=False), username="alice", password="secret"
    )[0]

    assert result.status == "completed"
    assert result.backend == "aria2"
    assert aria2_calls[0]["shell"] is False
    assert auth_urls and "urs.earthdata.nasa.gov/oauth/authorize" in auth_urls[0]
    assert len(session.urls) == 2


def test_download_service_cancel_keeps_partial_path_visible(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    service = DownloadService()
    monkeypatch.setattr(
        service,
        "_session",
        lambda username="", password="", network=None: _FakeSession(_FakeResponse([b"abc", b"123"])),
    )
    _patch_cancelable_aria2(monkeypatch, payload=b"abc")
    calls = {"count": 0}

    def _cancel_after_first_check():
        calls["count"] += 1
        return calls["count"] >= 3

    result = service.download(
        service.create_tasks([scene], tmp_path, include_orbits=False),
        cancel_check=_cancel_after_first_check,
    )[0]

    assert result.status == "cancelled"
    assert result.local_path.endswith(".zip.part")
    assert Path(result.local_path).read_bytes() == b"abc"


def test_download_service_skips_existing_slc(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    service = DownloadService()
    slc_path = tmp_path / "SLC" / "S1_TEST.zip"
    slc_path.parent.mkdir()
    slc_path.write_bytes(b"exists")
    monkeypatch.setattr(service, "_session", lambda username="", password="": _FakeSession(_FakeResponse([b"unused"])))

    result = service.download(service.create_tasks([scene], tmp_path, include_orbits=False))[0]

    assert result.status == "skipped"
    assert result.bytes_done == len(b"exists")


def test_download_service_reports_slc_failure(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    service = DownloadService()
    monkeypatch.setattr(
        service,
        "_session",
        lambda username="", password="": _FakeSession(_FakeResponse([], error=RuntimeError("boom"))),
    )
    _patch_aria2(monkeypatch)

    result = service.download(service.create_tasks([scene], tmp_path, include_orbits=False))[0]

    assert result.status == "failed"
    assert "boom" in result.message


def test_download_service_reports_missing_aria2_without_retrying(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    session = _FakeSession(_FakeResponse([b"unused"]))
    service = DownloadService()
    monkeypatch.setattr(service, "_session", lambda username="", password="", network=None: session)
    monkeypatch.setattr("insar_pilot.download.download_service.shutil.which", lambda name: None)

    result = service.download(service.create_tasks([scene], tmp_path, include_orbits=False))[0]

    assert result.status == "failed"
    assert result.backend == "aria2"
    assert "aria2c is required" in result.message
    assert session.urls == []


def test_download_service_retries_failed_slc_then_runs_deferred_orbit(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    session = _SequenceSession(
        [
            _FakeResponse([], error=RuntimeError("temporary network drop")),
            _FakeResponse([b"ok"]),
        ]
    )
    orbit_service = _FakeOrbitService()
    service = DownloadService(orbit_service=orbit_service)
    updates = []
    monkeypatch.setattr(service, "_session", lambda username="", password="", network=None: session)
    _patch_aria2(monkeypatch, payload=b"ok")

    results = service.download(
        service.create_tasks([scene], tmp_path, include_orbits=True), progress_callback=updates.append
    )

    assert [result.product_type for result in results] == ["SLC", "ORBIT"]
    assert results[0].status == "completed"
    assert results[1].status == "completed"
    assert Path(results[0].local_path).read_bytes() == b"ok"
    assert len(session.urls) == 2
    assert orbit_service.tasks and orbit_service.tasks[0].scene.scene_id == "S1_TEST"
    assert any("Retrying SLC download (attempt 2/3)" in update.message for update in updates)


def test_download_service_retries_failed_slc_twice_then_skips_orbit(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    session = _SequenceSession(
        [
            _FakeResponse([], error=RuntimeError("boom 1")),
            _FakeResponse([], error=RuntimeError("boom 2")),
            _FakeResponse([], error=RuntimeError("boom 3")),
        ]
    )
    orbit_service = _FakeOrbitService()
    service = DownloadService(orbit_service=orbit_service)
    monkeypatch.setattr(service, "_session", lambda username="", password="", network=None: session)
    _patch_aria2(monkeypatch)

    results = service.download(service.create_tasks([scene], tmp_path, include_orbits=True))

    assert [result.product_type for result in results] == ["SLC", "ORBIT"]
    assert results[0].status == "failed"
    assert results[1].status == "skipped"
    assert "after retries" in results[1].message
    assert len(session.urls) == 3
    assert orbit_service.tasks == []


def test_download_service_cancel_after_failure_does_not_retry(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    session = _SequenceSession(
        [
            _FakeResponse([], error=RuntimeError("boom")),
            _FakeResponse([b"unused"]),
        ]
    )
    service = DownloadService()
    calls = {"count": 0}
    monkeypatch.setattr(service, "_session", lambda username="", password="", network=None: session)
    _patch_aria2(monkeypatch)

    def _cancel_after_first_pass():
        calls["count"] += 1
        return calls["count"] >= 2

    result = service.download(
        service.create_tasks([scene], tmp_path, include_orbits=False),
        cancel_check=_cancel_after_first_pass,
    )[0]

    assert result.status == "failed"
    assert len(session.urls) == 1


def test_download_service_skips_orbit_when_paired_slc_fails(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    service = DownloadService()
    monkeypatch.setattr(
        service,
        "_session",
        lambda username="", password="", network=None: _FakeSession(_FakeResponse([], error=RuntimeError("boom"))),
    )
    _patch_aria2(monkeypatch)

    results = service.download(service.create_tasks([scene], tmp_path, include_orbits=True))

    assert [result.product_type for result in results] == ["SLC", "ORBIT"]
    assert results[0].status == "failed"
    assert results[1].status == "skipped"
    assert "after retries" in results[1].message


def test_download_service_leaves_dem_tasks_for_download_worker(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        download_url="https://example.test/S1_TEST.zip",
        file_name="S1_TEST.zip",
    )
    service = DownloadService()
    slc_path = tmp_path / "SLC" / "S1_TEST.zip"
    slc_path.parent.mkdir()
    slc_path.write_bytes(b"exists")
    monkeypatch.setattr(service, "_session", lambda username="", password="": _FakeSession(_FakeResponse([b"unused"])))

    tasks = service.create_tasks([scene], tmp_path, include_orbits=False)
    tasks.append(create_dem_task(tmp_path, "COP30"))
    results = service.download(tasks)

    assert [result.product_type for result in results] == ["SLC"]
    assert results[0].status == "skipped"


def test_orbit_download_service_uses_sentineleof_and_records_eof(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1A_IW_SLC__1SDV_20240101T000000_20240101T000030_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        file_name="S1A_IW_SLC__1SDV_20240101T000000_20240101T000030_TEST.zip",
    )
    slc_path = tmp_path / "SLC" / scene.file_name
    slc_path.parent.mkdir()
    slc_path.write_bytes(b"slc")
    task = DownloadTask(task_id="orbit-001", scene=scene, output_dir=str(tmp_path), product_type="ORBIT")
    service = OrbitDownloadService()

    def _fake_download_eofs(**kwargs):
        assert kwargs["sentinel_file"] == str(slc_path)
        eof = tmp_path / "Orbit" / "S1A_OPER_AUX_POEORB_OPOD_20240102T000000_V20231231T000000_20240102T000000.EOF"
        eof.write_bytes(b"orbit")

    monkeypatch.setattr(service, "_download_eofs_function", lambda: _fake_download_eofs)

    result = service.download(task)

    assert result.status == "completed"
    assert result.local_path.endswith(".EOF")


def test_orbit_failure_does_not_require_slc_failure(tmp_path: Path, monkeypatch):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
    )
    task = DownloadTask(task_id="orbit-001", scene=scene, output_dir=str(tmp_path), product_type="ORBIT")
    service = OrbitDownloadService()

    def _fake_download_eofs(*args, **kwargs):
        raise RuntimeError("orbit down")

    monkeypatch.setattr(service, "_download_eofs_function", lambda: _fake_download_eofs)

    result = service.download(task)

    assert result.status == "failed"
    assert "orbit down" in result.message


def test_download_storage_persists_json_state(tmp_path: Path):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
    )
    task = DownloadTask(
        task_id="download-001",
        scene=scene,
        output_dir=str(tmp_path),
        product_type="SLC",
        local_path=str(tmp_path / "SLC" / "S1_TEST.zip"),
        url="https://example.test/S1_TEST.zip",
        bytes_total=10,
        bytes_done=3,
    )
    storage = DownloadStorage(tmp_path)

    search_path = storage.save_search_results([scene])
    selected_path = storage.save_selected_scenes([scene])
    task_path = storage.save_download_tasks([task])

    assert search_path.name == "search_results.json"
    assert selected_path.name == "selected_scenes.json"
    assert task_path.name == "download_tasks.json"
    assert storage.load_search_results() == [scene]
    assert storage.load_selected_scenes() == [scene]
    assert storage.load_download_tasks() == [task]


def test_download_task_and_result_load_legacy_progress_payload():
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
    )
    task_payload = {
        "task_id": "download-001",
        "scene": scene.to_dict(),
        "output_dir": "/tmp/out",
        "product_type": "SLC",
        "bytes_total": 10,
        "bytes_done": 3,
    }
    result_payload = {
        "task_id": "download-001",
        "scene": scene.to_dict(),
        "product_type": "SLC",
        "status": "running",
        "local_path": "/tmp/out/SLC/S1_TEST.zip.part",
        "bytes_total": 10,
        "bytes_done": 3,
    }

    task = DownloadTask.from_dict(task_payload)
    result = DownloadResult.from_dict(result_payload)

    assert task.speed_bps == 0.0
    assert task.eta_seconds is None
    assert task.backend == "python"
    assert result.speed_bps == 0.0
    assert result.eta_seconds is None
    assert result.backend == "python"


def test_save_earthdata_netrc_writes_machine_and_permissions(tmp_path: Path):
    path = tmp_path / ".netrc"

    saved = save_earthdata_netrc("alice", "secret", path)

    assert saved == path
    assert "machine urs.earthdata.nasa.gov" in path.read_text(encoding="utf-8")
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_tianditu_key_loads_from_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("INSAR_PILOT_TIANDITU_KEY", "env-key")
    path = tmp_path / "tianditu.json"
    path.write_text('{"key": "file-key"}', encoding="utf-8")

    key = load_tianditu_key(path)

    assert key is not None
    assert key.key == "env-key"
    assert "INSAR_PILOT_TIANDITU_KEY" in key.source


def test_save_and_load_tianditu_key_permissions(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("INSAR_PILOT_TIANDITU_KEY", raising=False)
    path = tmp_path / "tianditu.json"

    saved = save_tianditu_key("file-key", path)
    key = load_tianditu_key(path)

    assert saved == path
    assert key is not None
    assert key.key == "file-key"
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_tianditu_key_test_uses_wmts_tile_request():
    network = _FakeMapNetwork(_FakeMapResponse())

    result = check_tianditu_key("demo-key", network=network)

    assert result.ok is True
    assert "img_w/wmts" in network.urls[0]
    assert "tk=demo-key" in network.urls[0]


def test_tianditu_key_test_rejects_non_image_response():
    result = check_tianditu_key(
        "demo-key",
        network=_FakeMapNetwork(_FakeMapResponse(content=b"<xml />", content_type="text/xml")),
    )

    assert result.ok is False
    assert "map tile image" in result.message


def test_save_and_load_opentopography_key_permissions(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("INSAR_PILOT_OPENTOPOGRAPHY_KEY", raising=False)
    path = tmp_path / "opentopography.json"

    saved = save_opentopography_key("ot-key", path)
    key = load_opentopography_key(path)

    assert saved == path
    assert key is not None
    assert key.key == "ot-key"
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_opentopography_key_loads_from_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("INSAR_PILOT_OPENTOPOGRAPHY_KEY", "env-ot-key")
    path = tmp_path / "opentopography.json"
    path.write_text('{"key": "file-ot-key"}', encoding="utf-8")

    key = load_opentopography_key(path)

    assert key is not None
    assert key.key == "env-ot-key"
    assert "INSAR_PILOT_OPENTOPOGRAPHY_KEY" in key.source


def test_opentopography_key_test_uses_globaldem_request():
    network = _FakeOtNetwork(_FakeOtResponse([b"II*\x00demo"]))

    result = check_opentopography_key("demo-key", network=network)

    assert result.ok is True
    params = network.session_obj.calls[0]["params"]
    assert params["demtype"] == "COP30"
    assert params["API_Key"] == "demo-key"
    assert params["outputFormat"] == "GTiff"


def test_download_storage_persists_dem_plan(tmp_path: Path):
    storage = DownloadStorage(tmp_path)
    plan = DemCoveragePlan(
        source_id="COP30",
        selected_scene_ids=["S1_TEST"],
        planned_bbox_snwe=(20.0, 21.0, 110.0, 111.0),
        planning_mode="burst_union",
        dem_path=str(tmp_path / "DEM" / "cop30.tif"),
        dem_height_reference="egm2008",
        warnings=["none"],
        notes=["ready"],
    )

    path = storage.save_dem_plan(plan)

    assert path.name == "dem_plan.json"
    assert storage.load_dem_plan() == plan


def test_tianditu_tile_proxy_builds_expected_upstream_url():
    proxy = TiandituTileProxy()
    proxy.update_key("demo-key")

    url = proxy.upstream_url("img", 3, 4, 5)

    assert "https://t0.tianditu.gov.cn/img_w/wmts" in url
    assert "TILEMATRIX=3" in url
    assert "TILECOL=4" in url
    assert "TILEROW=5" in url
    assert "tk=demo-key" in url


def test_tile_proxy_builds_esri_upstream_url_without_key():
    proxy = TiandituTileProxy()

    imagery = proxy.upstream_url("esri_img", 3, 4, 5)
    topo = proxy.upstream_url("esri_topo", 3, 4, 5)

    assert imagery == "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/3/5/4"
    assert topo == "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/3/5/4"
    assert "tk=" not in imagery
    assert "tk=" not in topo


def test_tianditu_tile_proxy_ignores_broken_pipe_from_cancelled_client():
    class _BrokenPipeStream:
        def write(self, payload):
            raise BrokenPipeError("client closed socket")

    assert TiandituTileProxy._write_payload(_BrokenPipeStream(), b"tile") is False


def test_gui_download_worker_imports():
    from insar_pilot.ui.download_worker import DownloadWorker

    assert DownloadWorker.__name__ == "DownloadWorker"


def test_download_page_source_no_longer_exposes_advanced_network_ui():
    package_dir = REPO_ROOT / "src/insar_pilot/ui/pages/data_download"
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(package_dir.glob("*.py")))
    source += (REPO_ROOT / "src/insar_pilot/ui/pages/data_download_page.py").read_text(encoding="utf-8")

    assert "Advanced Network" not in source
    assert "network_mode_combo" not in source
    assert "http_proxy_edit" not in source
    assert "https_proxy_edit" not in source


def test_footprint_map_widget_imports_and_builds_fallback_payload():
    from insar_pilot.ui.widgets.footprint_map import FootprintMapWidget, _read_text_asset

    assert FootprintMapWidget.__name__ == "FootprintMapWidget"
    assert "Leaflet 1.9.4" in _read_text_asset("leaflet.js")
    assert "window.L" in _read_text_asset("leaflet.js")
    assert "leaflet-container" in _read_text_asset("leaflet.css")


def test_footprint_map_html_defaults_to_tianditu_when_key_is_available():
    from insar_pilot.ui.widgets.footprint_map import FootprintMapWidget

    widget = FootprintMapWidget.__new__(FootprintMapWidget)
    widget._highlight_scene_id = ""
    widget._selected_scene_ids = set()
    widget._tianditu_enabled = True
    widget._tianditu_proxy_url = "http://127.0.0.1:39123/tianditu"
    widget._preferred_basemap_name = "Tianditu Imagery"
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        footprint_geojson={"type": "Polygon", "coordinates": [[[120, 30], [121, 30], [121, 31], [120, 30]]]},
    )

    html = widget._leaflet_html({}, [scene])

    assert "const tiandituEnabled = true;" in html
    assert "http://127.0.0.1:39123/tianditu" in html
    assert "const tiandituProxyUrl =" in html
    assert "tiandituLayer('img'" in html
    assert "tiandituLayer('cia'" in html
    assert "tiandituLayer('ter'" in html
    assert "tiandituLayer('cta'" in html
    assert 'const preferredBasemapName = "Tianditu Imagery";' in html
    assert "L.map('map', { preferCanvas: true }).setView([0, 0], 2)" in html
    assert "External Imagery" in html
    assert "External Terrain" in html
    assert "esri_img/{z}/{x}/{y}" in html
    assert "esri_topo/{z}/{x}/{y}" in html
    assert "fillOpacity: 0.0" in html
    assert "fillOpacity: 0.18" in html
    assert "fillOpacity: 0.12" not in html
    assert "activateBasemap('External Imagery');" in html


def test_footprint_map_updates_tianditu_state_in_one_render():
    from insar_pilot.ui.widgets.footprint_map import FootprintMapWidget

    widget = FootprintMapWidget.__new__(FootprintMapWidget)
    renders = []
    widget._tianditu_enabled = False
    widget._preferred_basemap_name = "External Imagery"
    widget._web_ready = True
    widget._render = lambda *, fit_bounds: renders.append(fit_bounds)

    FootprintMapWidget.set_tianditu_basemap_state(
        widget,
        enabled=True,
        preferred_basemap="Tianditu Imagery",
    )

    assert widget._tianditu_enabled is True
    assert widget._preferred_basemap_name == "Tianditu Imagery"
    assert widget._web_ready is False
    assert renders == [False]


def test_footprint_map_html_without_key_keeps_external_layers_and_notice():
    from insar_pilot.ui.widgets.footprint_map import FootprintMapWidget

    widget = FootprintMapWidget.__new__(FootprintMapWidget)
    widget._highlight_scene_id = ""
    widget._selected_scene_ids = set()
    widget._tianditu_enabled = False
    widget._tianditu_proxy_url = "http://127.0.0.1:39123/tianditu"
    widget._preferred_basemap_name = "External Imagery"

    html = widget._leaflet_html({}, [])

    assert "const tiandituEnabled = false;" in html
    assert 'const preferredBasemapName = "External Imagery";' in html
    assert "External Imagery" in html
    assert "External Terrain" in html


def test_footprint_map_can_force_native_fallback(monkeypatch):
    from insar_pilot.ui.widgets.footprint_map import FootprintMapWidget

    _qt_app()
    monkeypatch.setenv("INSAR_PILOT_MAP_BACKEND", "native")
    widget = FootprintMapWidget()
    widget.resize(420, 240)
    widget.show()
    widget.set_data(None, [])

    assert widget.web_view is None
    assert widget.stack.currentWidget() is widget.geometry_panel
    assert "Embedded map disabled" in widget.fallback_reason
    widget.close()


def test_footprint_map_highlighted_scene_is_emitted_last():
    from insar_pilot.ui.widgets.footprint_map import FootprintMapWidget

    widget = FootprintMapWidget.__new__(FootprintMapWidget)
    widget._highlight_scene_id = "S1_HIGHLIGHT"
    widget._selected_scene_ids = {"S1_HIGHLIGHT", "S1_OTHER"}
    widget._tianditu_enabled = False
    widget._tianditu_proxy_url = ""
    widget._preferred_basemap_name = "External Imagery"
    scenes = [
        SceneRecord(
            scene_id="S1_HIGHLIGHT",
            acquisition_time="2024-01-01T00:00:00Z",
            platform="Sentinel-1A",
            orbit_direction="ASCENDING",
            relative_orbit=42,
            polarization="VV",
            size_mb=1000.0,
            footprint_geojson={"type": "Polygon", "coordinates": [[[120, 30], [121, 30], [121, 31], [120, 30]]]},
        ),
        SceneRecord(
            scene_id="S1_OTHER",
            acquisition_time="2024-01-02T00:00:00Z",
            platform="Sentinel-1A",
            orbit_direction="ASCENDING",
            relative_orbit=42,
            polarization="VV",
            size_mb=1000.0,
            footprint_geojson={"type": "Polygon", "coordinates": [[[121, 30], [122, 30], [122, 31], [121, 30]]]},
        ),
    ]

    html = widget._leaflet_html({}, scenes)

    assert html.rfind('"scene_id": "S1_HIGHLIGHT"') > html.rfind('"scene_id": "S1_OTHER"')


def test_footprint_map_includes_dem_overlay_when_plan_exists():
    from insar_pilot.ui.widgets.footprint_map import FootprintMapWidget

    widget = FootprintMapWidget.__new__(FootprintMapWidget)
    widget._highlight_scene_id = ""
    widget._selected_scene_ids = set()
    widget._dem_bbox_snwe = (20.0, 21.0, 110.0, 111.0)
    widget._tianditu_enabled = False
    widget._tianditu_proxy_url = ""
    widget._preferred_basemap_name = "External Imagery"

    html = widget._leaflet_html({}, [])

    assert '"name": "DEM coverage"' in html
    assert "#27ae60" in html


def test_download_page_layout_defaults_expand_controls_and_use_external_basemap_until_validated():
    from insar_pilot.ui.pages.data_download_page import DataDownloadPage

    app = _qt_app()
    page = DataDownloadPage()
    page.resize(1720, 900)
    page.show()
    app.processEvents()
    page.normalize_main_splitter_sizes(force=True)

    assert page.control_scroll.minimumWidth() == 500
    assert page.control_scroll.maximumWidth() == 760
    assert page.main_splitter.objectName() == "dataMainSplitter"
    assert page.main_splitter.handleWidth() == 12
    assert 560 <= page.main_splitter.sizes()[0] <= 680
    assert page.main_splitter.count() == 2
    assert page.map_results_splitter.count() == 2
    assert page.map_results_splitter.objectName() == "dataMapResultsSplitter"
    assert page.map_results_splitter.handleWidth() == 8
    assert page.download_step_tree.topLevelItemCount() == 5
    assert page.download_step_tree.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.download_wizard_bar.run_button.text() == "Download"
    assert page.search_definition_section.property("density") == "compact"
    assert page.search_definition_form.verticalSpacing() == 6
    assert page.search_definition_form.horizontalSpacing() == 10
    assert page.platform_combo.maximumHeight() <= 38
    assert page.start_date_edit.maximumHeight() <= 38
    assert page.search_button.maximumHeight() <= 38

    page.set_tianditu_key("demo-key", source="saved")

    assert page.tianditu_status_label.text().startswith("Loaded Tianditu key from saved.")
    assert page.footprint_map._tianditu_enabled is False
    assert page.footprint_map._preferred_basemap_name == "External Imagery"
    assert page.download_dem_checkbox.isEnabled() is False
    assert page.dem_source_combo.isEnabled() is False
    page.close()


def test_download_page_normalizes_bad_restored_splitter_sizes():
    from insar_pilot.ui.pages.data_download_page import DataDownloadPage

    app = _qt_app()
    page = DataDownloadPage()
    page.resize(1720, 900)
    page.show()
    app.processEvents()
    page.main_splitter.setSizes([420, 1300])
    app.processEvents()

    page.normalize_main_splitter_sizes()

    assert 560 <= page.main_splitter.sizes()[0] <= 680
    page.close()


def test_download_page_scene_table_uses_readable_fixed_columns_with_horizontal_scroll():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHeaderView

    from insar_pilot.ui.pages.data_download_page import DataDownloadPage

    _qt_app()
    page = DataDownloadPage()

    header = page.results_table.horizontalHeader()

    assert page.results_table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert header.stretchLastSection() is False
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Interactive
    assert page.results_table.columnWidth(1) >= 260
    assert page.results_table.columnWidth(9) >= 360


def test_download_state_reducer_aggregates_running_task_progress():
    from insar_pilot.controllers.download_coordinator import DownloadStateReducer

    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
    )
    tasks = [
        DownloadTask(
            task_id="slc-001",
            scene=scene,
            output_dir="/tmp",
            product_type="SLC",
            status="completed",
            local_path="/tmp/S1_TEST.zip",
            bytes_done=100,
            bytes_total=100,
        ),
        DownloadTask(
            task_id="orbit-001",
            scene=scene,
            output_dir="/tmp",
            product_type="ORBIT",
            status="running",
            local_path="/tmp/S1_TEST.EOF.part",
            bytes_done=50,
            bytes_total=150,
            speed_bps=10,
            backend="aria2",
        ),
    ]

    state = DownloadStateReducer.from_tasks(tasks)

    assert state.total_tasks == 2
    assert state.completed_tasks == 1
    assert state.running_tasks == 1
    assert state.percent == 60
    assert state.eta_seconds == 10
    assert state.active_task_id == "orbit-001"
    assert state.active_backend == "aria2"


def test_download_page_task_progress_panel_shows_planned_and_running_task():
    from insar_pilot.ui.pages.data_download_page import DataDownloadPage

    _qt_app()
    page = DataDownloadPage()
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
    )
    planned = DownloadTask(
        task_id="slc-001",
        scene=scene,
        output_dir="/tmp",
        product_type="SLC",
        status="pending",
        local_path="/tmp/S1_TEST.zip.part",
        backend="aria2",
    )

    page.set_download_tasks([planned])

    assert page.task_progress_panel.total_label.text() == "0/1 tasks"
    assert page.download_progress_bar is page.task_progress_panel.progress_bar
    assert page.download_status_label is page.task_progress_panel.status_label

    page.apply_task_update(
        planned.with_updates(
            status="running",
            bytes_done=5 * 1024 * 1024,
            bytes_total=10 * 1024 * 1024,
            speed_bps=1024 * 1024,
            eta_seconds=5,
            message="Downloading SLC",
        ),
        completed_count=0,
        total_count=1,
    )

    assert "SLC: running" in page.download_status_label.text()
    assert "ETA" in page.download_status_label.text()
    assert page.task_progress_panel.speed_label.text() == "1.0 MB/s"
    assert page.task_progress_panel.eta_label.text() == "5s"
    assert page.task_progress_panel.backend_label.text() == "aria2"


def test_download_page_enables_dem_controls_after_opentopography_validation():
    from insar_pilot.ui.pages.data_download_page import DataDownloadPage

    _qt_app()
    page = DataDownloadPage()

    page.set_opentopography_available(True)

    assert page.download_dem_checkbox.isEnabled() is True
    assert page.dem_source_combo.isEnabled() is True

    page.set_opentopography_available(False)

    assert page.download_dem_checkbox.isChecked() is False
    assert page.dem_source_combo.isEnabled() is False


def test_download_page_apply_results_does_not_refresh_map(monkeypatch):
    from insar_pilot.ui.pages.data_download_page import DataDownloadPage

    _qt_app()
    page = DataDownloadPage()
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        footprint_geojson={"type": "Polygon", "coordinates": [[[120, 30], [121, 30], [121, 31], [120, 30]]]},
    )
    page.set_scenes([scene])
    monkeypatch.setattr(page.footprint_map, "set_data", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        page.footprint_map, "set_highlight", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError())
    )

    page.apply_download_results(
        [
            DownloadResult(
                task_id="slc-001",
                scene=scene.with_status("downloaded", "/tmp/S1_TEST.zip"),
                product_type="SLC",
                status="completed",
                local_path="/tmp/S1_TEST.zip",
            )
        ]
    )

    assert page.results_table.item(0, 8).text() == "completed"
    assert page.results_table.item(0, 9).text() == "/tmp/S1_TEST.zip"


def test_download_page_log_append_preserves_manual_scroll_position():
    from insar_pilot.ui.pages.data_download_page import DataDownloadPage

    app = _qt_app()
    page = DataDownloadPage()
    page.show()
    for index in range(80):
        page.append_log(f"line {index}")
    app.processEvents()
    scrollbar = page.log_text.verticalScrollBar()
    scrollbar.setValue(max(scrollbar.minimum(), scrollbar.maximum() // 3))
    app.processEvents()
    previous = scrollbar.value()

    page.append_log("new line while reading old logs")
    app.processEvents()

    assert scrollbar.value() == previous


def test_download_page_task_update_does_not_refresh_map_or_scene_detail(monkeypatch):
    from insar_pilot.ui.pages.data_download_page import DataDownloadPage

    _qt_app()
    page = DataDownloadPage()
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
        footprint_geojson={"type": "Polygon", "coordinates": [[[120, 30], [121, 30], [121, 31], [120, 30]]]},
    )
    page.set_scenes([scene])
    page.scene_detail_text.setPlainText("user is reading this")
    monkeypatch.setattr(page.footprint_map, "set_data", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        page.footprint_map, "set_highlight", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError())
    )
    task = DownloadTask(
        task_id="slc-001",
        scene=scene,
        output_dir="/tmp",
        product_type="SLC",
        status="running",
        local_path="/tmp/S1_TEST.zip.part",
        bytes_total=10,
        bytes_done=5,
        speed_bps=2,
        eta_seconds=3,
    )

    page.apply_task_update(task, completed_count=0, total_count=1)

    assert page.scene_detail_text.toPlainText() == "user is reading this"
    assert page.results_table.item(0, 8).text() == "running"
    assert "ETA" in page.download_status_label.text()


def test_dem_coverage_planner_expands_single_burst_and_uses_scene_fallback(tmp_path: Path):
    scene_a = SceneRecord(
        scene_id="S1_A",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=11,
        polarization="VV+VH",
        size_mb=1000.0,
        local_path=str(tmp_path / "S1_A.zip"),
        footprint_geojson={
            "type": "Polygon",
            "coordinates": [[[113.0, 22.0], [114.0, 22.0], [114.0, 23.0], [113.0, 22.0]]],
        },
    )
    Path(scene_a.local_path).write_bytes(b"zip")
    scene_b = SceneRecord(
        scene_id="S1_B",
        acquisition_time="2024-01-02T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=11,
        polarization="VV+VH",
        size_mb=1000.0,
        local_path=str(tmp_path / "missing.zip"),
        footprint_geojson={
            "type": "Polygon",
            "coordinates": [[[114.0, 22.0], [115.0, 22.0], [115.0, 23.0], [114.0, 22.0]]],
        },
    )

    result = IwRecommendationResult(
        basis_entry_path=scene_a.local_path,
        footprints={"1": IwFootprint(swath="1", bbox_snwe=(22.0, 23.0, 113.0, 114.0), polygon=[])},
        bursts={
            "1": [
                BurstFootprint(swath="1", burst_id=1, bbox_snwe=(22.0, 22.4, 113.0, 113.4), polygon=[]),
                BurstFootprint(swath="1", burst_id=2, bbox_snwe=(22.4, 22.8, 113.0, 113.4), polygon=[]),
                BurstFootprint(swath="1", burst_id=3, bbox_snwe=(22.8, 23.2, 113.0, 113.4), polygon=[]),
            ]
        },
        auto_selected_bursts={"1": [2]},
    )

    class _FakeIwService:
        def recommend(self, entry_path: str, bbox_snwe: str):
            return result

    planner = DemCoveragePlanner(iw_service=_FakeIwService())
    criteria = SearchCriteria(start_date="2024-01-01", end_date="2024-01-31", bbox="113.1,22.1,114.2,22.9")

    plan = planner.plan(criteria, [scene_a, scene_b], "COP30")

    assert plan.planning_mode == "burst_union"
    assert plan.planned_bbox_snwe == (22.0, 23.2, 113.0, 115.0)
    assert any("scene footprint bbox" in warning for warning in plan.warnings)


def test_dem_coverage_planner_falls_back_to_scene_footprints_when_burst_parsing_fails(tmp_path: Path):
    scene = SceneRecord(
        scene_id="S1_FAIL",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=11,
        polarization="VV+VH",
        size_mb=1000.0,
        local_path=str(tmp_path / "S1_FAIL.zip"),
        footprint_geojson={
            "type": "Polygon",
            "coordinates": [[[113.0, 22.0], [114.0, 22.0], [114.0, 23.0], [113.0, 22.0]]],
        },
    )
    Path(scene.local_path).write_bytes(b"zip")

    class _FailingIwService:
        def recommend(self, entry_path: str, bbox_snwe: str):
            raise RuntimeError("bad annotation")

    planner = DemCoveragePlanner(iw_service=_FailingIwService())
    criteria = SearchCriteria(start_date="2024-01-01", end_date="2024-01-31", bbox="113.1,22.1,114.2,22.9")

    plan = planner.plan(criteria, [scene], "AW3D30_E")

    assert plan.planning_mode == "scene_fallback"
    assert plan.planned_bbox_snwe == (22.0, 23.0, 113.0, 114.0)


def test_opentopography_dem_service_downloads_geotiff_and_updates_result(tmp_path: Path):
    plan = DemCoveragePlan(
        source_id="COP30",
        selected_scene_ids=["S1_TEST"],
        planned_bbox_snwe=(20.0, 21.0, 110.0, 111.0),
        planning_mode="burst_union",
        dem_height_reference="egm2008",
    )
    task = create_dem_task(tmp_path, "COP30")
    service = OpenTopographyDemService()
    network = _FakeOtNetwork(_FakeOtResponse([b"II*\x00abc", b"123"], content_type="image/tiff"))
    updates = []

    result = service.download(task, plan, api_key="demo-key", network=network, progress_callback=updates.append)

    assert result.status == "completed"
    assert Path(result.local_path).read_bytes() == b"II*\x00abc123"
    params = network.session_obj.calls[0]["params"]
    assert params["demtype"] == "COP30"
    assert params["API_Key"] == "demo-key"


def test_download_page_uses_explicit_transparent_form_labels():
    base = (REPO_ROOT / "src/insar_pilot/ui/pages/data_download/base.py").read_text(encoding="utf-8")
    search = (REPO_ROOT / "src/insar_pilot/ui/pages/data_download/search_section.py").read_text(encoding="utf-8")
    theme = (REPO_ROOT / "src/insar_pilot/ui/styles/components.py").read_text(encoding="utf-8")

    assert 'label.setProperty("formLabel", True)' in base
    assert 'quick_form.addRow(self._form_label("Dataset"), self.platform_combo)' in search
    assert 'QLabel[formLabel="true"]' in theme


def test_main_window_source_uses_top_workflow_stepper():
    source = (REPO_ROOT / "src/insar_pilot/ui/main_window.py").read_text(encoding="utf-8")

    assert "layout.addWidget(self._build_workflow_stepper(), 0, Qt.AlignmentFlag.AlignVCenter)" in source
    assert "self.workflow_stepper = TopWorkflowStepper()" in source
    assert "self._step_keys = [\"data_download\", \"setup\", \"monitor\", \"results\"]" in source
    assert "workflow_nav" not in source
    assert "body_splitter" not in source


def test_workflow_nav_item_source_uses_compact_gis_rows():
    source = (REPO_ROOT / "src/insar_pilot/ui/widgets/workflow_nav_item.py").read_text(encoding="utf-8")

    assert "self.setMinimumHeight(48)" in source
    assert "Qt.AlignmentFlag.AlignVCenter" in source


def test_project_importer_writes_placeholder_config(tmp_path: Path):
    scene = SceneRecord(
        scene_id="S1_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
    )

    config_path = import_downloads_to_project(tmp_path / "project", [scene])

    assert config_path.name == "project_config.json"
    assert "S1_TEST" in config_path.read_text(encoding="utf-8")
