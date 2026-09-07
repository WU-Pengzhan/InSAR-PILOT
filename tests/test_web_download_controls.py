import os
import signal
import subprocess
import sys

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from insar_pilot.application import engine_download, engine_download_control
from insar_pilot.infrastructure.application_state import ApplicationState
from insar_pilot.web.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_download.subprocess, "Popen", lambda *a, **kw: None)
    monkeypatch.setattr(engine_download, "aria2_executable", lambda app: "/bin/aria2c")
    with TestClient(create_app(tmp_path / "app", "download-controls", testing=True)) as client:
        client.headers["Authorization"] = "Bearer download-controls"
        yield client


def seed(app, status="RUNNING"):
    job = {
        "job_id": "parent",
        "status": status,
        "products": [{"remote_product_id": "original-selection", "mission": "NISAR"}],
        "cancel_requested": False,
        "progress": [],
        "results": [],
        "created_at": "2026-09-05T00:00:00Z",
    }
    app.save_download(job)
    return job


def test_pause_survives_old_worker_writes_and_resume_freezes_original_selection(client):
    app = client.app.state.registry
    old_worker = seed(app)
    assert client.post("/api/v1/data/downloads/parent/pause").json()["display_status"] == "PAUSING"
    # A pre-update worker knows nothing about the new control table.
    old_worker.update(status="RUNNING", progress=[{"task_id": "old-progress"}])
    app.save_download(old_worker)
    assert app.download("parent")["display_status"] == "PAUSING"
    assert client.post("/api/v1/data/downloads/parent/resume").status_code == 409
    old_worker.update(status="CANCELLED")
    app.save_download(old_worker)
    assert app.download("parent")["display_status"] == "PAUSED"
    with app.connection() as db:
        before = db.execute("SELECT body FROM downloads WHERE job_id='parent'").fetchone()[0]
    resumed = client.post("/api/v1/data/downloads/parent/resume")
    assert resumed.status_code == 202
    child = resumed.json()
    assert child["job_id"] != "parent" and child["parent_job_id"] == "parent"
    assert child["products"] == old_worker["products"] and not child["cancel_requested"]
    assert app.download("parent")["continued_by"] == child["job_id"]
    assert client.post("/api/v1/data/downloads/parent/resume").status_code == 409
    assert len(app.downloads()) == 2
    with app.connection() as db:
        assert db.execute("SELECT body FROM downloads WHERE job_id='parent'").fetchone()[0] == before


def test_cancel_paused_queue_and_retry_keeps_history(client):
    app = client.app.state.registry
    job = seed(app)
    client.post("/api/v1/data/downloads/parent/pause")
    job.update(status="CANCELLED")
    app.save_download(job)
    assert client.post("/api/v1/data/downloads/parent/cancel").json()["display_status"] == "CANCELLED"
    assert client.post("/api/v1/data/downloads/parent/resume").status_code == 409
    assert client.post("/api/v1/data/downloads/parent/retry").status_code == 202
    assert app.download("parent")["status"] == "CANCELLED"


def test_success_wins_race_with_pause_and_cannot_be_resumed(client):
    app = client.app.state.registry
    job = seed(app)
    client.post("/api/v1/data/downloads/parent/pause")
    job.update(status="SUCCESS")
    app.save_download(job)
    assert app.download("parent")["display_status"] == "SUCCESS"
    for action in ("resume", "retry", "cancel"):
        assert client.post(f"/api/v1/data/downloads/parent/{action}").status_code == 409


def test_control_requires_session_and_known_job(client):
    assert client.post("/api/v1/data/downloads/missing/pause").status_code == 404
    client.cookies.clear()
    client.headers.pop("Authorization")
    for action in ("pause", "resume", "cancel", "retry"):
        assert client.post(f"/api/v1/data/downloads/parent/{action}").status_code == 401


def test_stop_observer_finishes_unresponsive_process_group_and_preserves_partials(tmp_path, monkeypatch):
    app = ApplicationState(tmp_path / "app")
    seed(app)
    part = app.root / "library" / "partial" / "fixture.part"
    part.write_bytes(b"resume-data")
    # A local inert worker with a child simulates a blocked network call; no HTTP or SAR download.
    script = (
        "import subprocess,sys,time; "
        "subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        "print('ready',flush=True); time.sleep(60)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script], start_new_session=True, stdout=subprocess.PIPE, text=True
    )
    assert process.stdout.readline().strip() == "ready"
    identity = engine_download_control.process_state(process.pid)[2]
    monkeypatch.setattr(engine_download_control, "workers", lambda *args: {process.pid: identity})
    try:
        app.stop_download("parent", pause=True)
        engine_download_control.stop_worker(app, "parent")
        process.wait(timeout=2)
        assert not engine_download_control.group_alive(process.pid, identity)
        assert app.download("parent")["display_status"] == "PAUSED"
        assert part.read_bytes() == b"resume-data"
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def test_process_id_reuse_is_not_signalled(monkeypatch):
    monkeypatch.setattr(engine_download_control, "process_state", lambda pid: ("S", pid, "different-start"))
    monkeypatch.setattr(engine_download_control.os, "killpg", lambda *args: pytest.fail("Unrelated process signalled"))
    with pytest.raises(RuntimeError, match="identity changed"):
        engine_download_control.signal_group(123, "original-start", signal.SIGTERM)


def test_cancel_queued_attempt_never_starts_transport(tmp_path, monkeypatch):
    app = ApplicationState(tmp_path / "app")
    seed(app, "QUEUED")
    app.stop_download("parent", pause=True)
    monkeypatch.setattr(engine_download_control, "workers", lambda *args: {})
    engine_download_control.stop_worker(app, "parent")
    monkeypatch.setattr(engine_download, "load_earthdata_credentials", lambda: pytest.fail("Transport started"))
    engine_download.execute(app, "parent")
    assert app.download("parent")["display_status"] == "PAUSED"
