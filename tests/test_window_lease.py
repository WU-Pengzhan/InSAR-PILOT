"""Exclusive browser ownership is independent of shared cookies and background jobs."""

import pytest
from fastapi.testclient import TestClient

from insar_pilot.web.api import create_app
from insar_pilot.web.window_lease import WindowLease


def test_expiry_does_not_allow_old_owner_to_renew_or_release_new_owner():
    now = [0.0]
    lease = WindowLease(ttl=15, clock=lambda: now[0])
    first = lease.acquire()
    assert first and lease.acquire() is None
    now[0] = 16
    second = lease.acquire()
    assert second and second != first
    assert not lease.renew(first)
    lease.release(first)
    assert lease.valid(second)
    assert lease.renew(second)
    lease.release(second)
    assert lease.acquire()


def test_shared_cookie_cannot_take_over_and_old_window_cannot_submit(tmp_path):
    app = create_app(tmp_path / "app", "native-secret", testing=True)
    with TestClient(app) as client:
        job = {"job_id": "background", "status": "RUNNING", "products": [], "cancel_requested": False}
        app.state.registry.save_download(job)
        headers = {"Origin": "http://testserver", "X-Pilot-Workbench": "1"}
        assert client.post("/api/v1/session", headers=headers).status_code == 200
        client.headers.update({"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"})
        assert client.get("/api/v1/projects").status_code == 423
        with client.websocket_connect("/api/v1/window") as first:
            grant = first.receive_json()
            owner = grant["owner"]
            assert grant["state"] == "active"
            first.receive_json()
            first.send_text("pong")
            with client.websocket_connect("/api/v1/window") as second:
                assert second.receive_json() == {"state": "occupied"}
            assert client.get("/api/v1/projects", headers={"X-Pilot-Window": owner}).status_code == 200
            assert client.get("/api/v1/projects").status_code == 423
            assert (
                client.post("/api/v1/projects", json={"name": "Blocked", "path": str(tmp_path / "blocked")}).status_code
                == 423
            )
            assert not (tmp_path / "blocked").exists()
        # Closing the socket releases its claim even when both windows share a cookie.
        with client.websocket_connect("/api/v1/window") as replacement:
            new = replacement.receive_json()
            assert new["state"] == "active" and new["owner"] != owner
            assert app.state.registry.download("background")["status"] == "RUNNING"
            assert not app.state.registry.download("background")["cancel_requested"]
            assert client.get("/api/v1/projects", headers={"X-Pilot-Window": owner}).status_code == 423
            assert client.get("/api/v1/projects", headers={"X-Pilot-Window": new["owner"]}).status_code == 200


def test_window_socket_rejects_foreign_origin(tmp_path):
    from starlette.websockets import WebSocketDisconnect

    with TestClient(create_app(tmp_path, "secret", testing=True)) as client:
        client.cookies.set("pilot_session", "secret")
        with pytest.raises(WebSocketDisconnect), client.websocket_connect(
            "/api/v1/window", headers={"Origin": "http://evil.invalid"}
        ):
            pass


def test_unresponsive_window_times_out_without_being_able_to_steal_replacement(tmp_path):
    import time

    with TestClient(create_app(tmp_path, "secret", testing=True)) as client:
        client.cookies.set("pilot_session", "secret")
        client.headers["Origin"] = "http://testserver"
        with client.websocket_connect("/api/v1/window") as dead:
            old = dead.receive_json()["owner"]
            assert dead.receive_json()["state"] == "ping"
            time.sleep(15.2)  # Simulate a hung page: no heartbeat response or close frame.
            with client.websocket_connect("/api/v1/window") as replacement:
                current = replacement.receive_json()
                assert current["state"] == "active" and current["owner"] != old
                assert client.get("/api/v1/projects", headers={"X-Pilot-Window": old}).status_code == 423


def test_transport_disconnect_during_close_releases_window_without_server_error(tmp_path, monkeypatch):
    from starlette.websockets import WebSocket, WebSocketDisconnect

    async def disconnected_close(self, code=1000, reason=None):
        raise WebSocketDisconnect(code=1006)

    monkeypatch.setattr(WebSocket, "close", disconnected_close)
    with TestClient(create_app(tmp_path, "secret", testing=True)) as client:
        client.cookies.set("pilot_session", "secret")
        client.headers["Origin"] = "http://testserver"
        with client.websocket_connect("/api/v1/window") as first:
            owner = first.receive_json()["owner"]
        with client.websocket_connect("/api/v1/window") as second:
            grant = second.receive_json()
            assert grant["state"] == "active"
            assert grant["owner"] != owner
