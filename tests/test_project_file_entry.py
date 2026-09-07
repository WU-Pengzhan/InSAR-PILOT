"""Project marker identity, compatibility and named-entry recovery contracts."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from insar_pilot.domain.engine import canonical
from insar_pilot.infrastructure.application_state import ApplicationState
from insar_pilot.infrastructure.engine_store import ConflictError, EngineStore, atomic_json
from insar_pilot.infrastructure.project_codec import read_project_document
from insar_pilot.infrastructure.project_file import inspect_project, project_filename
from insar_pilot.web.api import create_app


def test_named_entry_survives_revision_crash_and_manual_import(tmp_path):
    store = EngineStore.create(tmp_path / "中文 空格", "研究", filename="研究.pilot")
    entry = store.project_file
    store.revise(1, name="Display name changed")
    assert entry.exists() and not (store.root / "project.pilot").exists()
    proposed = {**store.project(), "revision": 3, "name": "Recovered"}
    with store.connection() as db:
        db.execute("INSERT INTO pending_revision VALUES(1,?)", (canonical(proposed),))
    atomic_json(entry, proposed)
    assert inspect_project(entry)["status"] == "ready"
    # Inspection does not commit pending state.
    assert store.project()["revision"] == 2
    recovered = EngineStore(entry)
    assert recovered.project()["revision"] == 3
    atomic_json(entry, {**proposed, "name": "External"})
    assert inspect_project(entry)["status"] == "modified"
    reopened = EngineStore(entry)
    reopened.import_definition_edits(3)
    assert read_project_document(entry)["revision"] == 4


def test_old_web_file_without_format_stays_compatible(tmp_path):
    store = EngineStore.create(tmp_path / "old", "Old")
    body = store.project()
    body.pop("format")
    atomic_json(store.project_file, body)
    with store.connection() as db:
        db.execute("UPDATE project SET body=?", (canonical(body),))
    reopened = EngineStore(store.root)
    assert reopened.project_file.name == "project.pilot"
    reopened.revise(1, name="Updated")
    assert "format" not in read_project_document(reopened.project_file)


def test_mismatch_missing_and_multiple_entries_are_read_only(tmp_path):
    store = EngineStore.create(tmp_path / "root", "Test")
    entry = store.project_file
    original = entry.read_bytes()
    body = store.project()
    body["project_id"] = "another"
    atomic_json(entry, body)
    assert inspect_project(entry)["status"] == "conflict"
    with pytest.raises(ValueError):
        EngineStore(entry)
    entry.write_bytes(original)
    copy = store.root / "duplicate.pilot"
    copy.write_bytes(original)
    assert inspect_project(store.root)["status"] == "invalid"
    assert inspect_project(entry)["status"] == "invalid"
    copy.unlink()
    orphan = tmp_path / "orphan.pilot"
    orphan.write_bytes(original)
    assert inspect_project(orphan)["status"] == "incomplete"
    assert not (tmp_path / ".insar_pilot").exists()


@pytest.mark.parametrize("name", ["../escape", "a/b", r"a\b", "NUL", "CON.txt", "a?", "a.", "长" * 100])
def test_portable_project_names(name):
    with pytest.raises(ValueError):
        project_filename(name)


def test_registry_rejects_copied_identity_and_missing_recent(tmp_path):
    app = ApplicationState(tmp_path / "app")
    store = EngineStore.create(tmp_path / "original", "Original", filename="Original.pilot")
    app.register(store)
    assert app.recent()[0]["pipelines"] == {}
    copy = tmp_path / "copy"
    shutil.copytree(store.root, copy)
    with pytest.raises(ConflictError):
        app.open_project(copy / "Original.pilot")
    assert app.project(store.project()["project_id"]).root == store.root
    store.project_file.unlink()
    recent = app.recent()[0]
    assert not recent["available"]
    assert len(app.recent()) == 1


def test_api_creation_inspection_and_file_filter(tmp_path):
    with TestClient(create_app(tmp_path / "app", "test", testing=True)) as client:
        client.headers["Authorization"] = "Bearer test"
        parent = tmp_path / "parents"
        parent.mkdir()
        body = {"path": str(parent), "name": "工程 A", "parent_directory": True}
        preview = client.post("/api/v1/projects/creation-preview", json=body)
        assert preview.status_code == 200
        entry = Path(preview.json()["project_file"])
        assert entry == parent / "工程 A" / "工程 A.pilot"
        assert not entry.parent.exists()
        created = client.post("/api/v1/projects", json=body)
        assert created.status_code == 201
        assert created.json()["project_file"] == str(entry)
        assert client.post("/api/v1/projects", json=body).status_code != 201
        info = client.post("/api/v1/projects/inspect", json={"path": str(entry)}).json()
        assert info["status"] == "ready"
        opened = client.post("/api/v1/projects/open", json={"path": str(entry)})
        assert opened.json()["project_id"] == created.json()["project_id"]
        root = entry.parent
        (root / "image.h5").touch()
        (root / "data").mkdir(exist_ok=True)
        resolved = client.post("/api/v1/filesystem/resolve", json={"path": str(root)}).json()
        listing = client.get(
            "/api/v1/filesystem/directories/" + resolved["directory_id"], params={"extension": ".pilot", "limit": 2}
        ).json()
        assert all(e["kind"] == "directory" or e["name"].endswith(".pilot") for e in listing["entries"])
        assert client.get("/api/v1/projects").json()[0]["project_file"] == str(entry)


def test_legacy_recognition_and_import_keeps_source(tmp_path):
    from insar_pilot.services.project_store import ProjectStore

    source = tmp_path / "legacy"
    ProjectStore().create_workspace(source)
    entry = ProjectStore.resolve_project_file(source)
    original = entry.read_bytes()
    assert inspect_project(entry)["status"] == "legacy"
    with TestClient(create_app(tmp_path / "app", "test", testing=True)) as client:
        client.headers["Authorization"] = "Bearer test"
        assert client.post("/api/v1/projects/open", json={"path": str(entry)}).status_code == 422
        response = client.post(
            "/api/v1/projects/import",
            json={"source": str(entry), "destination": str(tmp_path / "new"), "name": "Imported"},
        )
        assert response.status_code == 200, response.text
        assert (tmp_path / "new" / "Imported.pilot").exists()
        assert entry.read_bytes() == original
        assert client.get("/api/v1/projects/" + response.json()["project_id"] + "/runs").json() == []


def test_invalid_pending_does_not_unlock_profile(tmp_path):
    store = EngineStore.create(tmp_path / "pending", "Pending")
    body = store.project()
    body.update(profile="sentinel1_tops", profile_locked=True)
    atomic_json(store.project_file, body)
    with store.connection() as db:
        db.execute("UPDATE project SET body=?", (canonical(body),))
        proposed = {**body, "revision": 2, "profile_locked": False}
        db.execute("INSERT INTO pending_revision VALUES(1,?)", (canonical(proposed),))
    atomic_json(store.project_file, proposed)
    assert inspect_project(store.project_file)["status"] == "invalid"
    with pytest.raises(ValueError):
        EngineStore(store.root)
    assert store.project()["profile_locked"] is True


def test_unsupported_corrupt_and_replaced_registered_identity(tmp_path):
    app = ApplicationState(tmp_path / "app")
    store = EngineStore.create(tmp_path / "original", "Original")
    app.register(store)
    body = store.project()
    atomic_json(store.project_file, {**body, "schema_version": 99})
    assert inspect_project(store.project_file)["status"] == "unsupported"
    atomic_json(store.project_file, {**body, "datasets": "invalid"})
    assert inspect_project(store.project_file)["status"] == "invalid"
    body["project_id"] = "replacement"
    atomic_json(store.project_file, body)
    with store.connection() as db:
        db.execute("UPDATE project SET body=?", (canonical(body),))
    with pytest.raises(ConflictError):
        app.open_project(store.root)
    assert not app.recent()[0]["available"]
