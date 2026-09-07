import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from requests.cookies import RequestsCookieJar, create_cookie
from test_p01_acquisition import safe_bytes

from insar_pilot.download import DownloadService, DownloadStorage, SearchService, create_dem_task
from insar_pilot.download.credentials import load_earthdata_credentials, save_earthdata_netrc
from insar_pilot.download.dem_service import DemCoveragePlanner, OpenTopographyDemService
from insar_pilot.download.geometry import (
    aoi_geojson_from_inputs,
    bbox_to_polygon,
    bounds_from_geojson,
    geojson_from_kml,
    polygon_from_kml,
    polygon_to_wkt,
    polygons_from_geojson,
    wkt_from_kml,
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

REPO_ROOT = Path(__file__).resolve().parents[1]
SAFE_PAYLOAD = safe_bytes()


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

    def download(self, task, *, progress_callback=None, cancel_check=None, network=None):
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
    def __init__(
        self,
        command,
        *,
        payload=SAFE_PAYLOAD,
        returncode=0,
        stderr="",
        running_polls=0,
        output_stream=None,
    ):
        self.command = command
        self._payload = payload
        self._final_returncode = returncode
        self._stderr = stderr
        self._running_polls = running_polls
        self._output_stream = output_stream
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
        if self._stderr and self._output_stream is not None:
            self._output_stream.write(self._stderr)
            self._output_stream.flush()
        self.returncode = self._final_returncode

    def _part_path(self) -> Path:
        if "--dir" in self.command and "--out" in self.command:
            directory = Path(self.command[self.command.index("--dir") + 1])
            output = self.command[self.command.index("--out") + 1]
            return directory / output
        request_file = Path(self.command[self.command.index("--input-file") + 1])
        task_options = {}
        for line in request_file.read_text(encoding="utf-8").splitlines()[1:]:
            key, value = line.strip().split("=", 1)
            task_options[key] = value
        directory = Path(task_options["dir"])
        output = task_options["out"]
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


def _patch_aria2(monkeypatch, *, payload=SAFE_PAYLOAD, returncode=0, stderr="", running_polls=0):
    calls = []
    stderr_text = stderr
    monkeypatch.setattr("insar_pilot.download.download_service.shutil.which", lambda name: "/usr/bin/aria2c")

    def _popen(command, stdout=None, stderr=None, text=False, shell=False):
        assert shell is False
        process = _FakeAria2Process(
            command,
            payload=payload,
            returncode=returncode,
            stderr=stderr_text,
            running_polls=running_polls,
            output_stream=stdout,
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


def _patch_dem_aria2(monkeypatch, *, payload=b"II*\x00dem", returncode=0, stderr="", cancelable=False):
    calls = []
    stderr_text = stderr
    monkeypatch.setattr(
        "insar_pilot.download.dem_service.shutil.which",
        lambda name: "/usr/bin/aria2c" if name == "aria2c" else f"/usr/bin/{name}",
    )

    def _popen(command, stdout=None, stderr=None, text=False, shell=False):
        assert shell is False
        request_file = Path(command[command.index("--input-file") + 1])
        process_class = _FakeCancelableAria2Process if cancelable else _FakeAria2Process
        if cancelable:
            process = process_class(command, payload=payload)
        else:
            process = process_class(
                command,
                payload=payload,
                returncode=returncode,
                stderr=stderr_text,
                output_stream=stdout,
            )
        request_text = request_file.read_text(encoding="utf-8")
        calls.append(
            {
                "command": command,
                "request_file": request_file,
                "request_url": request_text.splitlines()[0],
                "request_text": request_text,
                "request_mode": request_file.stat().st_mode & 0o777,
                "stdout": stdout,
                "stderr": stderr,
            }
        )
        return process

    monkeypatch.setattr("insar_pilot.download.dem_service.subprocess.Popen", _popen)
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

    def close(self):
        pass


class _FakeOtSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, stream=False, timeout=None):
        self.calls.append({"url": url, "params": params or {}, "stream": stream, "timeout": timeout})
        return self.response

    def close(self):
        pass


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


def test_kml_linestring_is_not_closed_into_a_self_intersecting_polygon(tmp_path: Path):
    kml = tmp_path / "road.kml"
    kml.write_text(
        "<kml><Document><Placemark><LineString>"
        "<coordinates>121.48,31.23 121.42,31.21 121.35,31.18</coordinates>"
        "</LineString></Placemark></Document></kml>",
        encoding="utf-8",
    )

    expected = "LINESTRING(121.48 31.23,121.42 31.21,121.35 31.18)"
    assert wkt_from_kml(kml) == expected
    assert ASFProvider._wkt_from_kml(kml) == expected
    geometry = geojson_from_kml(kml)
    assert geometry["type"] == "LineString"
    assert polygons_from_geojson(geometry)[0] == [
        (121.48, 31.23),
        (121.42, 31.21),
        (121.35, 31.18),
    ]


def test_multi_linestring_kml_uses_longest_path_for_asf_and_all_paths_for_preview(tmp_path: Path):
    kml = tmp_path / "roads.kml"
    kml.write_text(
        "<kml><Document><Placemark><MultiGeometry>"
        "<LineString><coordinates>121.40,31.20 121.41,31.21 121.42,31.22</coordinates></LineString>"
        "<LineString><coordinates>121.30,31.10 121.60,31.40</coordinates></LineString>"
        "</MultiGeometry></Placemark></Document></kml>",
        encoding="utf-8",
    )

    assert wkt_from_kml(kml) == "LINESTRING(121.3 31.1,121.6 31.4)"
    preview = geojson_from_kml(kml)
    assert preview["type"] == "GeometryCollection"
    assert len(polygons_from_geojson(preview)) == 2
    assert bounds_from_geojson([preview]) == (121.3, 31.1, 121.6, 31.4)


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
        NetworkConfig, "session", lambda self: _FakeSession(_FakeResponse([SAFE_PAYLOAD]))
    )
    aria2_calls = _patch_aria2(monkeypatch, payload=SAFE_PAYLOAD)
    updates = []

    tasks = service.create_tasks([scene], tmp_path, include_orbits=False)
    results = service.download(tasks, progress_callback=updates.append)

    assert results[0].status == "completed", results[0].message
    assert Path(results[0].local_path).read_bytes() == SAFE_PAYLOAD
    assert not Path(results[0].local_path + ".part").exists()
    assert updates[0].message.startswith("Preparing ASF authentication for aria2c download:")
    assert updates[0].local_path.endswith(".zip.part")
    assert updates[-1].bytes_done == len(SAFE_PAYLOAD)
    assert results[0].scene.status == "downloaded"
    assert results[0].backend == "aria2"
    assert aria2_calls[0]["shell"] is False
    assert aria2_calls[0]["stdout"] is not subprocess.PIPE
    assert aria2_calls[0]["stderr"] is subprocess.STDOUT
    command = aria2_calls[0]["command"]
    assert "--continue=true" in command
    assert "--max-connection-per-server=1" in command
    assert "--split=1" in command
    assert "--min-split-size=16M" in command
    assert "--all-proxy=" in command
    assert "--http-proxy=" in command
    assert "--https-proxy=" in command
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
    session = _FakeSession(_FakeResponse([SAFE_PAYLOAD]))
    session.cookies = RequestsCookieJar()
    session.cookies.set_cookie(create_cookie(name="asf-urs", value="super-secret-cookie", domain=".asf.alaska.edu"))
    service = DownloadService()
    monkeypatch.setattr(NetworkConfig, "session", lambda self: session)
    aria2_calls = _patch_aria2(monkeypatch, payload=SAFE_PAYLOAD)

    result = service.download(service.create_tasks([scene], tmp_path, include_orbits=False))[0]

    command = aria2_calls[0]["command"]
    cookie_path = Path(command[command.index("--load-cookies") + 1])
    assert result.status == "completed", result.message
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
    success = _FakeResponse([SAFE_PAYLOAD])
    session = _SequenceSession([redirect, success])
    auth_urls = []
    service = DownloadService()
    monkeypatch.setattr(service, "_create_session", lambda *args: session)
    monkeypatch.setattr(NetworkConfig, "session", lambda self: session)
    aria2_calls = _patch_aria2(monkeypatch, payload=SAFE_PAYLOAD)
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
        NetworkConfig,
        "session",
        lambda self: _FakeSession(_FakeResponse([SAFE_PAYLOAD])),
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
    slc_path.write_bytes(SAFE_PAYLOAD)
    monkeypatch.setattr(NetworkConfig, "session", lambda self: _FakeSession(_FakeResponse([b"unused"])))

    result = service.download(service.create_tasks([scene], tmp_path, include_orbits=False))[0]

    assert result.status == "skipped"
    assert result.bytes_done == len(SAFE_PAYLOAD)


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
        NetworkConfig,
        "session",
        lambda self: _FakeSession(_FakeResponse([], error=RuntimeError("boom"))),
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
    monkeypatch.setattr(NetworkConfig, "session", lambda self: session)
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
            _FakeResponse([SAFE_PAYLOAD]),
        ]
    )
    orbit_service = _FakeOrbitService()
    service = DownloadService(orbit_service=orbit_service)
    updates = []
    monkeypatch.setattr(NetworkConfig, "session", lambda self: session)
    _patch_aria2(monkeypatch, payload=SAFE_PAYLOAD)

    results = service.download(
        service.create_tasks([scene], tmp_path, include_orbits=True), progress_callback=updates.append
    )

    assert [result.product_type for result in results] == ["SLC", "ORBIT"]
    assert results[0].status == "completed"
    assert results[1].status == "completed"
    assert Path(results[0].local_path).read_bytes() == SAFE_PAYLOAD
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
    monkeypatch.setattr(NetworkConfig, "session", lambda self: session)
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
    monkeypatch.setattr(NetworkConfig, "session", lambda self: session)
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
        NetworkConfig,
        "session",
        lambda self: _FakeSession(_FakeResponse([], error=RuntimeError("boom"))),
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
    slc_path.write_bytes(SAFE_PAYLOAD)
    monkeypatch.setattr(NetworkConfig, "session", lambda self: _FakeSession(_FakeResponse([b"unused"])))

    tasks = service.create_tasks([scene], tmp_path, include_orbits=False)
    tasks.append(create_dem_task(tmp_path, "COP30"))
    results = service.download(tasks)

    assert [result.product_type for result in results] == ["SLC"]
    assert results[0].status == "skipped"






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


def test_opentopography_dem_service_downloads_geotiff_and_updates_result(tmp_path: Path, monkeypatch):
    plan = DemCoveragePlan(
        source_id="COP30",
        selected_scene_ids=["S1_TEST"],
        planned_bbox_snwe=(20.0, 21.0, 110.0, 111.0),
        planning_mode="burst_union",
        dem_height_reference="egm2008",
    )
    task = create_dem_task(tmp_path, "COP30")
    service = OpenTopographyDemService()
    monkeypatch.setattr(service, "_geotiff_validation_error", lambda path: "")
    aria2_calls = _patch_dem_aria2(monkeypatch, payload=b"II*\x00abc123")
    updates = []

    result = service.download(task, plan, api_key="demo-key", progress_callback=updates.append)

    assert result.status == "completed"
    assert Path(result.local_path).read_bytes() == b"II*\x00abc123"
    assert result.backend == "aria2"
    command = aria2_calls[0]["command"]
    query = parse_qs(urlparse(aria2_calls[0]["request_url"]).query)
    assert query["demtype"] == ["COP30"]
    assert query["API_Key"] == ["demo-key"]
    assert "demo-key" not in " ".join(command)
    assert "--split=4" in command
    assert "--max-connection-per-server=4" in command
    assert "--file-allocation=none" in command
    assert "--all-proxy=" in command
    assert "--dir" not in command
    assert "--out" not in command
    assert f"  dir={tmp_path / 'DEM'}\n" in aria2_calls[0]["request_text"]
    assert "  out=cop30_20p0000_21p0000_110p0000_111p0000.tif.part\n" in aria2_calls[0]["request_text"]
    assert aria2_calls[0]["request_mode"] == 0o600
    assert not aria2_calls[0]["request_file"].exists()


def test_opentopography_dem_service_rejects_truncated_geotiff(tmp_path: Path, monkeypatch):
    plan = DemCoveragePlan(
        source_id="AW3D30_E",
        selected_scene_ids=["S1_TEST"],
        planned_bbox_snwe=(20.0, 21.0, 110.0, 111.0),
        planning_mode="burst_union",
        dem_height_reference="wgs84",
    )
    task = create_dem_task(tmp_path, "AW3D30_E")
    service = OpenTopographyDemService()
    monkeypatch.setattr(
        service,
        "_geotiff_validation_error",
        lambda path: "TIFF tile extends beyond the downloaded file",
    )
    _patch_dem_aria2(monkeypatch, payload=b"II*\x00truncated")

    result = service.download(task, plan, api_key="demo-key")

    assert result.status == "failed"
    assert result.local_path.endswith(".tif.part")
    assert "incomplete or corrupt" in result.message
    assert not Path(result.local_path.removesuffix(".part")).exists()


def test_opentopography_aria2_failure_redacts_api_key(tmp_path: Path, monkeypatch):
    plan = DemCoveragePlan(
        source_id="AW3D30_E",
        selected_scene_ids=["S1_TEST"],
        planned_bbox_snwe=(20.0, 21.0, 110.0, 111.0),
        planning_mode="burst_union",
        dem_height_reference="wgs84",
    )
    task = create_dem_task(tmp_path, "AW3D30_E")
    service = OpenTopographyDemService()
    aria2_calls = _patch_dem_aria2(
        monkeypatch,
        returncode=1,
        stderr="request failed: API_Key=super-secret-key&demtype=AW3D30_E",
    )

    result = service.download(task, plan, api_key="super-secret-key")

    assert result.status == "failed"
    assert result.backend == "aria2"
    assert "super-secret-key" not in result.message
    assert "<redacted>" in result.message
    assert "super-secret-key" not in " ".join(aria2_calls[0]["command"])
    assert not aria2_calls[0]["request_file"].exists()


def test_opentopography_aria2_cancel_keeps_partial_file(tmp_path: Path, monkeypatch):
    plan = DemCoveragePlan(
        source_id="COP30",
        selected_scene_ids=["S1_TEST"],
        planned_bbox_snwe=(20.0, 21.0, 110.0, 111.0),
        planning_mode="burst_union",
        dem_height_reference="egm2008",
    )
    task = create_dem_task(tmp_path, "COP30")
    service = OpenTopographyDemService()
    _patch_dem_aria2(monkeypatch, payload=b"II*\x00partial", cancelable=True)

    result = service.download(task, plan, api_key="demo-key", cancel_check=lambda: True)

    assert result.status == "cancelled"
    assert result.backend == "aria2"
    assert result.local_path.endswith(".tif.part")
    assert Path(result.local_path).read_bytes() == b"II*\x00partial"


def test_opentopography_dem_validation_detects_gdal_checksum_failure(tmp_path: Path, monkeypatch):
    tif_path = tmp_path / "truncated.tif"
    tif_path.write_bytes(b"II*\x00")
    monkeypatch.setattr("insar_pilot.download.dem_service.shutil.which", lambda name: "/usr/bin/gdalinfo")
    monkeypatch.setattr(
        "insar_pilot.download.dem_service.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout='{"bands": [{"band": 1, "checksum": -1}]}',
            stderr="ERROR 3: Checksum value could not be computed due to I/O read error.\n",
        ),
    )

    error = OpenTopographyDemService._geotiff_validation_error(tif_path)

    assert "Checksum value could not be computed" in error


def test_opentopography_quarantines_corrupt_file_without_overwrite(tmp_path: Path):
    tif_path = tmp_path / "dem.tif"
    tif_path.write_bytes(b"broken")
    first_quarantine = Path(f"{tif_path}.corrupt")
    first_quarantine.write_bytes(b"older evidence")

    quarantined = OpenTopographyDemService._quarantine_corrupt_file(tif_path)

    assert quarantined == Path(f"{tif_path}.corrupt.1")
    assert quarantined.read_bytes() == b"broken"
    assert first_quarantine.read_bytes() == b"older evidence"
    assert not tif_path.exists()








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
