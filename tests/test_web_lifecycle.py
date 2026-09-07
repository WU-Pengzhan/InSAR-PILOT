import json
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from insar_pilot.infrastructure.job_executor import process_identity
from insar_pilot.web import launch, lifecycle
from insar_pilot.web.api import create_app


def test_shutdown_requires_session_and_idle_state_and_freezes_new_mutations(tmp_path):
    calls = []
    with TestClient(
        create_app(tmp_path, "local-test", testing=True, request_exit=lambda: calls.append(True))
    ) as client:
        assert client.post("/api/v1/application/shutdown").status_code == 401
        client.headers["Authorization"] = "Bearer local-test"
        registry = client.app.state.registry
        job = {"job_id": "fixture", "status": "RUNNING", "cancel_requested": False}
        registry.save_download(job)
        assert client.get("/api/v1/application/status").json()["download_jobs"] == 1
        assert client.post("/api/v1/application/shutdown").status_code == 409
        assert calls == []
        assert not registry.download("fixture")["cancel_requested"]
        job["status"] = "CANCELLED"
        registry.save_download(job)
        response = client.post("/api/v1/application/shutdown")
        assert response.status_code == 202 and calls == [True]
        assert response.json()["state"] == "STOPPING"
        assert client.post("/api/v1/projects", json={"path": str(tmp_path / "new"), "name": "New"}).status_code == 503
        assert not (tmp_path / "new").exists()
        assert client.get("/api/v1/application/status").json()["state"] == "STOPPING"


def test_shutdown_refuses_live_worker_even_without_active_task_records(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(lifecycle, "owned_workers", lambda _root: {123})
    with TestClient(create_app(tmp_path, "fixture", testing=True, request_exit=lambda: calls.append(True))) as client:
        client.headers["Authorization"] = "Bearer fixture"
        assert client.get("/api/v1/application/status").json()["worker_processes"] == 1
        assert client.post("/api/v1/application/shutdown").status_code == 409
        assert calls == []


def test_shutdown_checks_origin_and_test_server_does_not_exit(tmp_path):
    with TestClient(create_app(tmp_path, "fixture", testing=True)) as client:
        client.headers["Authorization"] = "Bearer fixture"
        assert (
            client.post("/api/v1/application/shutdown", headers={"Origin": "https://untrusted.invalid"}).status_code
            == 403
        )
        assert client.post("/api/v1/application/shutdown").status_code == 409


def test_status_and_stop_do_not_start_missing_service(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(launch.subprocess, "Popen", lambda *a, **kw: pytest.fail("Unexpected service start"))
    assert launch.service_command(tmp_path / "absent", stop=False) == 0
    assert launch.service_command(tmp_path / "absent", stop=True) == 0
    assert "STOPPED" in capsys.readouterr().out
    assert not (tmp_path / "absent").exists()


def test_real_local_service_status_stop_and_restart(tmp_path):
    state = tmp_path / "local-service"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    command = [sys.executable, "-m", "insar_pilot.web.launch", "--state", str(state)]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    def run(*args):
        return subprocess.run([*command, *args], env=env, capture_output=True, text=True, timeout=30)

    try:
        assert run("--no-browser", "--port", str(port)).returncode == 0
        config = json.loads((state / "service.json").read_text())
        assert process_identity(config["pid"])
        status = run("--status")
        assert status.returncode == 0 and "RUNNING" in status.stdout
        stopped = run("--stop")
        assert stopped.returncode == 0 and "STOPPED" in stopped.stdout
        assert not process_identity(config["pid"])
        assert json.loads((state / "service.json").read_text())["status"] == "stopped"
        assert "STOPPED" in run("--status").stdout
        assert run("--no-browser", "--port", str(port)).returncode == 0
        newer = json.loads((state / "service.json").read_text())
        assert newer["pid"] != config["pid"]
        assert newer["token"] == config["token"]
        assert newer["port"] == config["port"]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/v1/health", headers={"Cookie": "pilot_session=" + config["token"]}
        )
        with opener.open(request, timeout=3) as response:
            assert response.status == 200
        assert config["token"] not in status.stdout + stopped.stdout
        assert run("--stop").returncode == 0
    finally:
        if (state / "service.json").exists():
            run("--stop")


def test_browser_cookie_survives_close_and_keeps_origin_boundary(tmp_path):
    with TestClient(create_app(tmp_path, "test-credential", testing=True)) as client:
        response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-credential"})
        cookie = response.headers["set-cookie"]
        assert "Max-Age=2592000" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
        assert client.get("/api/v1/health").status_code == 200
        assert (
            client.post("/api/v1/application/shutdown", headers={"Origin": "https://foreign.invalid"}).status_code
            == 403
        )
