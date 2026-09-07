"""Authenticated API contract and registered-resource boundaries."""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from insar_pilot.web.api import create_app


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path / "state", "test-session", testing=True)) as client:
        client.headers["Authorization"] = "Bearer test-session"
        yield client


def test_session_is_required_and_untrusted_origin_is_rejected(client):
    assert client.get("/api/v1/health", headers={"Authorization": "wrong"}).status_code == 401
    assert client.get("/api/v1/health", headers={"Origin": "https://untrusted.invalid"}).status_code == 403
    assert client.get("/api/v1/health").status_code == 200


def test_create_open_revision_and_file_boundaries(client, tmp_path):
    root = tmp_path / "project"
    response = client.post("/api/v1/projects", json={"name": "Science", "path": str(root)})
    assert response.status_code == 201
    project = response.json()
    pid = project["project_id"]
    assert client.post("/api/v1/projects/open", json={"path": str(root)}).json()["project_id"] == pid
    assert client.patch(f"/api/v1/projects/{pid}", json={"expected_revision": 1, "name": "Revised"}).status_code == 200
    assert client.patch(f"/api/v1/projects/{pid}", json={"expected_revision": 1, "name": "Old"}).status_code == 409
    assert client.get(f"/api/v1/projects/{pid}/files", params={"relative": ".."}).status_code == 403
    assert client.get(f"/api/v1/projects/{pid}/artifacts/unknown/assets/0").status_code == 404


def test_events_replay_and_websocket_require_session(client, tmp_path):
    project = client.post("/api/v1/projects", json={"name": "Events", "path": str(tmp_path / "events")}).json()
    pid = project["project_id"]
    client.patch(f"/api/v1/projects/{pid}", json={"expected_revision": 1, "name": "Second"})
    events = client.get(f"/api/v1/projects/{pid}/events").json()
    assert events[-1]["event_type"] == "project.revised"
    with client.websocket_connect(f"/api/v1/projects/{pid}/events/ws", subprotocols=["pilot", "test-session"]) as ws:
        replay = ws.receive_json()
        assert replay == events
    assert client.get(f"/api/v1/projects/{pid}/events?after={events[-1]['sequence']}").json() == []


def test_definitions_do_not_claim_cuda_processing(client):
    response = client.get("/api/v1/compute")
    assert response.status_code == 200
    assert response.json()["cuda_processing_validated"] is False
    providers = client.get("/api/v1/data/capabilities").json()
    assert len(providers) == 2


def test_cookie_websocket_negotiates_subprotocol_without_raw_header(tmp_path):
    app = create_app(tmp_path / "session-state", "cookie-fixture", testing=True)

    async def consumed_header(scope, receive, send):
        if scope["type"] == "websocket":
            scope = {**scope, "headers": [(k, v) for k, v in scope["headers"] if k != b"sec-websocket-protocol"]}
        await app(scope, receive, send)

    with TestClient(consumed_header) as session:
        project = session.post(
            "/api/v1/projects", json={"name": "Cookie", "path": str(tmp_path / "cookie-project")},
            headers={"Authorization": "Bearer cookie-fixture"},
        ).json()
        with session.websocket_connect(
            f"/api/v1/projects/{project['project_id']}/events/ws", subprotocols=["pilot"]
        ) as socket:
            assert socket.accepted_subprotocol == "pilot"
            assert isinstance(socket.receive_json(), list)
