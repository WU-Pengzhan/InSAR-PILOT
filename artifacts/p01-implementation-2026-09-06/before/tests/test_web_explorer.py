from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from insar_pilot.application import engine_download
from insar_pilot.download.models import DownloadResult
from insar_pilot.infrastructure.application_state import ApplicationState
from insar_pilot.infrastructure.engine_store import EngineStore
from insar_pilot.web.api import create_app
from insar_pilot.web.imagery import ImageryTiles


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "state", "explorer-fixture", testing=True)) as client:
        client.headers["Authorization"] = "Bearer explorer-fixture"
        yield client


def test_legacy_aoi_formats_preserve_search_geometry(client, tmp_path):
    bbox = client.post("/api/v1/data/aoi", json={"mode": "bbox", "value": "108,34,109,35"})
    assert bbox.status_code == 200
    assert bbox.json()["bounds"] == [108, 34, 109, 35]
    assert bbox.json()["geometry"]["type"] == "Polygon"
    for value in ("200,34,201,35", "0,nan,1,2", "1,2,0,3"):
        assert client.post("/api/v1/data/aoi", json={"mode": "bbox", "value": value}).status_code == 422
    kml = tmp_path / "轨道.kml"
    kml.write_text(
        "<kml><Placemark><LineString><coordinates>108,34 109,35</coordinates></LineString></Placemark></kml>"
    )
    parsed = client.post("/api/v1/data/aoi", json={"mode": "file", "value": str(kml)}).json()
    assert parsed["wkt"].startswith("LINESTRING")
    assert parsed["geometry"]["type"] == "LineString"
    assert client.post("/api/v1/data/aoi", json={"mode": "wkt", "value": "garbage"}).status_code == 422


def test_imagery_uses_only_legacy_image_layer_and_caches_success(monkeypatch):
    tiles = ImageryTiles()
    calls = []
    monkeypatch.setattr(tiles.proxy, "fetch_tile", lambda *args: calls.append(args) or (200, "image/jpeg", b"image"))
    assert tiles.fetch(3, 2, 1) == (200, "image/jpeg", b"image")
    assert tiles.fetch(3, 2, 1)[0] == 200
    assert calls == [("esri_img", 3, 2, 1)]
    with pytest.raises(ValueError):
        tiles.fetch(3, 8, 1)
    monkeypatch.setattr(tiles.proxy, "fetch_tile", lambda *args: (200, "text/html", b"failure"))
    assert tiles.fetch(3, 3, 1)[0] == 502
    assert (3, 3, 1) not in tiles.cache
    tiles.close()


def test_readiness_does_not_expose_or_validate_credentials(client, monkeypatch):
    monkeypatch.setattr(
        "insar_pilot.download.credentials.load_earthdata_credentials",
        lambda: SimpleNamespace(username="private-user", password="private-password"),
    )
    monkeypatch.setattr(engine_download, "aria2_executable", lambda _app: "/bin/aria2c")
    response = client.get("/api/v1/data/download-readiness")
    assert response.json()["ready"] is True
    assert response.json()["credentials_validated"] is False
    assert "private-user" not in response.text and "private-password" not in response.text


def product(mission):
    return {
        "remote_product_id": "fixture",
        "provider_id": "asf",
        "mission": mission,
        "acquisition_time": "2024-01-01T00:00:00Z",
        "platform": mission,
        "polarizations": ["HH" if mission == "NISAR" else "VV"],
        "download_url": "https://example.invalid/file",
    }


def saved_job(app, mission, project_id=None, cancelled=False):
    job = {
        "job_id": "download-fixture",
        "status": "QUEUED",
        "products": [product(mission)],
        "progress": [],
        "cancel_requested": cancelled,
        "project_id": project_id,
    }
    app.save_download(job)
    return job["job_id"]


@pytest.mark.parametrize("mission,expected", [("SENTINEL-1", ["SLC", "ORBIT"]), ("NISAR", ["RSLC"])])
def test_web_download_reuses_legacy_tasks_and_attaches_orbits(tmp_path, monkeypatch, mission, expected):
    app = ApplicationState(tmp_path / "state")
    project = app.register(EngineStore.create(tmp_path / "project", "Downloads"))
    job_id = saved_job(app, mission, project["project_id"])
    monkeypatch.setattr(
        engine_download, "load_earthdata_credentials", lambda: SimpleNamespace(username="u", password="fixture-secret")
    )
    attached = []
    monkeypatch.setattr(
        "insar_pilot.application.engine_data.import_sources",
        lambda app, store, paths, role: attached.append(role) or [{"artifact_id": "fixture"}],
    )
    monkeypatch.setattr(EngineStore, "resolve_remote", lambda *args: None)

    def download(self, tasks, **kwargs):
        assert [task.product_type for task in tasks] == expected
        results = []
        for task in tasks:
            path = Path(task.local_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture")
            kwargs["progress_callback"](task.with_updates(status="completed", bytes_done=7, bytes_total=7))
            results.append(DownloadResult(task.task_id, task.scene, task.product_type, "completed", task.local_path))
        return results

    monkeypatch.setattr(engine_download.DownloadService, "download", download)
    engine_download.execute(app, job_id)
    job = app.downloads()[0]
    assert job["status"] == "SUCCESS", job
    assert [r["product_type"] for r in job["results"]] == expected
    assert attached == (["sar", "orbit"] if mission == "SENTINEL-1" else ["sar"])
    assert "fixture-secret" not in str(job)


def test_cancelled_download_does_not_require_credentials_or_start_transport(tmp_path, monkeypatch):
    app = ApplicationState(tmp_path / "state")
    job = saved_job(app, "NISAR", cancelled=True)
    monkeypatch.setattr(engine_download, "load_earthdata_credentials", lambda: pytest.fail("Credentials accessed"))
    engine_download.execute(app, job)
    assert app.downloads()[0]["status"] == "CANCELLED"


def test_cancel_is_observed_while_waiting_for_identity_lock(tmp_path, monkeypatch):
    app = ApplicationState(tmp_path / "state")
    job = saved_job(app, "NISAR")
    monkeypatch.setattr(
        engine_download, "load_earthdata_credentials", lambda: SimpleNamespace(username="u", password="p")
    )

    def locked(*args):
        raise BlockingIOError

    def cancel_while_waiting(_seconds):
        current = app.downloads()[0]
        current["cancel_requested"] = True
        app.save_download(current)

    monkeypatch.setattr(engine_download.fcntl, "flock", locked)
    monkeypatch.setattr(engine_download.time, "sleep", cancel_while_waiting)
    engine_download.execute(app, job)
    assert app.downloads()[0]["status"] == "CANCELLED"


def test_configured_aria2_is_available_outside_application_path(client, tmp_path):
    binary = tmp_path / "processor-env" / "aria2c"
    binary.parent.mkdir()
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o700)
    response = client.post("/api/v1/data/download-runtime", json={"aria2_executable": str(binary)})
    assert response.status_code == 200
    assert response.json()["aria2_available"] is True
    assert response.json()["aria2_executable"] == str(binary)
    assert engine_download.aria2_executable(client.app.state.registry) == str(binary)
    binary.chmod(0o600)
    assert client.get("/api/v1/data/download-readiness").json()["aria2_available"] is False
