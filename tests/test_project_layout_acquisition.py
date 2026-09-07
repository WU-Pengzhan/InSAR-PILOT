"""New layout history, frozen download targets and verified source publication."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_engine_store import execute_first
from test_p01_acquisition import save_product

from insar_pilot.application import acquisition, engine_download
from insar_pilot.application.acquisition_storage import publish_source, reusable_asset
from insar_pilot.domain.engine import PipelineDefinition, Profile, StepDefinition
from insar_pilot.infrastructure.application_state import ApplicationState
from insar_pilot.infrastructure.engine_store import ConflictError, EngineStore, atomic_project
from insar_pilot.web.api import create_app


@pytest.mark.parametrize("version", [1, 2])
def test_layout_keeps_run_and_artifact_history_on_rerun(tmp_path, version):
    store = EngineStore.create(tmp_path / "P", "P", storage_layout_version=version)
    source = tmp_path / "source"
    source.write_bytes(b"input")
    artifact = store.register_source(source, "Sentinel1SLC", Profile.SENTINEL1_TOPS)
    store.attach_dataset([artifact["artifact_id"]], Profile.SENTINEL1_TOPS, 1)
    definition = PipelineDefinition("test", Profile.SENTINEL1_TOPS, (StepDefinition("geometry", "Geometry"),))
    pid = store.add_pipeline(definition, {"source": [artifact["artifact_id"]]}, {}, {}, 2)
    rid, product = execute_first(store, pid)
    old = store.run(rid)
    payload = Path(product["assets"][0]["uri"]).read_bytes()
    second = store.submit(store.create_plan(pid, "geometry")["plan_id"])
    assert second["run_ids"][0] != rid
    assert second["working_directory"] != old["working_directory"]
    assert Path(product["assets"][0]["uri"]).read_bytes() == payload
    assert (store.layout.runs / rid / "snapshot.json").exists()
    reopened = EngineStore(store.project_file)
    assert reopened.layout.version == version and reopened.run(rid) == old
    if version == 2:
        assert Path(old["working_directory"]).parent == store.root / "processing"
        assert Path(product["assets"][0]["uri"]).is_relative_to(store.root / "products")
        assert not (store.root / "runs").exists()
        assert {p.name for p in store.layout.data.iterdir()} == {"slc", "dem", "orbit", "aux", "aoi"}


def test_manual_edit_cannot_redirect_layout(tmp_path):
    store = EngineStore.create(tmp_path / "P", "P", storage_layout_version=2)
    atomic_project(store.project_file, {**store.project(), "storage_layout_version": 1})
    with pytest.raises(ValueError, match="layout"):
        store.import_definition_edits(1)
    assert store.project()["storage_layout_version"] == 2


def test_plan_freezes_new_destination_and_retry_preserves_it(tmp_path, monkeypatch):
    app = ApplicationState(tmp_path / "app")
    product = save_product(app)
    target = {"name": "Project", "path": str(tmp_path), "parent_directory": True}
    plan = acquisition.preview(app, {"product_ids": [product["product_key"]], "new_project": target})
    assert plan["destination"] == str(tmp_path / "Project/data")
    assert not (tmp_path / "Project").exists()
    request = {"plan_id": plan["plan_id"], "idempotency_key": "preview-target", "new_project": target}
    with pytest.raises(ConflictError, match="destination"):
        acquisition.commit(app, {**request, "new_project": {**target, "name": "Other"}}, testing=True)
    result = acquisition.commit(app, request, testing=True)
    job = result["job"]
    assert job["destination"] == plan["destination"]
    assert job["destination_kind"] == "project"
    assert job["transfer_root"] == str(tmp_path / "Project/.insar_pilot/transfers")
    job["status"] = "FAILED"
    app.save_download(job)
    monkeypatch.setattr(engine_download, "launch_worker", lambda *args: None)
    child = engine_download.continue_download(app, job["job_id"], resume=False)
    assert child["destination"] == job["destination"]
    assert child["transfer_root"] == job["transfer_root"]
    assert child["job_id"] != job["job_id"]
    assert child["worker_log"] != job["worker_log"]
    assert Path(child["worker_log"]).is_relative_to(tmp_path / "Project/.insar_pilot/records/downloads")


def test_publish_sources_versioned_cancellable_and_recoverable(tmp_path):
    source = tmp_path / "stage/source.zip"
    source.parent.mkdir()
    source.write_bytes(b"first")
    target = tmp_path / "data"
    staging = tmp_path / "hidden"
    published = publish_source(source, target, "SLC", staging, lambda: False)
    assert published.read_bytes() == b"first" and source.exists()
    assert publish_source(source, target, "SLC", staging, lambda: False) == published
    source.write_bytes(b"second")
    second = publish_source(source, target, "SLC", staging, lambda: False)
    assert second != published and published.read_bytes() == b"first"
    source.write_bytes(b"cancelled")
    with pytest.raises(InterruptedError):
        publish_source(source, target, "SLC", staging, lambda: True)
    assert len(list((target / "slc").iterdir())) == 2
    assert not list(staging.iterdir())
    source.write_bytes(b"first")
    published.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="overwrite"):
        publish_source(source, target, "SLC", staging, lambda: False)
    assert published.read_bytes() == b"tampered"


def test_reuse_checks_registered_version_and_source_availability(tmp_path):
    app = ApplicationState(tmp_path / "app")
    source = tmp_path / "source"
    source.write_bytes(b"registered")
    app.library_register(str(source), {"role": "SLC", "product_key": "scene", "integrity": {"checks": ["fixture"]}})
    assert reusable_asset(app, "scene", "SLC") == source
    source.write_bytes(b"changed size")
    assert reusable_asset(app, "scene", "SLC") is None
    source.unlink()
    assert reusable_asset(app, "scene", "SLC") is None


def test_download_paging_and_hidden_records_api(tmp_path):
    app = create_app(tmp_path / "app", "test", testing=True)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer test"
        p = client.post("/api/v1/projects", json={"name": "P", "path": str(tmp_path / "P")}).json()
        detail = client.get(f"/api/v1/projects/{p['project_id']}").json()
        assert detail["path"] == str(tmp_path / "P")
        assert detail["project_file"] == p["project_file"]
        route = f"/api/v1/projects/{p['project_id']}/files"
        assert ".insar_pilot" not in [r["name"] for r in client.get(route).json()]
        assert client.get(route, params={"relative": ".insar_pilot"}).status_code == 403
        assert client.get(route, params={"relative": ".insar_pilot", "show_hidden": True}).status_code == 200
        for i in range(23):
            app.state.registry.save_download(
                {
                    "job_id": f"job-{i}",
                    "status": "QUEUED" if i < 2 else "SUCCESS",
                    "products": [],
                    "destination": "/fixture",
                }
            )
        first = client.get("/api/v1/data/downloads-page").json()
        next_page = client.get("/api/v1/data/downloads-page?offset=10").json()
        assert first["total"] == first["count"] == 23 and first["active"] == 2
        assert len(first["items"]) == len(next_page["items"]) == 10
        assert not {j["job_id"] for j in first["items"]} & {j["job_id"] for j in next_page["items"]}
        assert client.get("/api/v1/data/downloads-page?state=active").json()["count"] == 2


def test_worker_publishes_to_frozen_project_then_reuses_across_projects(tmp_path, monkeypatch):
    from insar_pilot.download.integrity import receipt_path
    from insar_pilot.download.models import DownloadResult
    from insar_pilot.infrastructure.engine_store import atomic_json

    app = ApplicationState(tmp_path / "app")
    product = save_product(app)
    monkeypatch.setattr(engine_download, "load_earthdata_credentials", lambda: None)
    monkeypatch.setattr(engine_download, "launch_worker", lambda *args: None)
    # Keep this an acquisition orchestration test: numerical metadata readers are tested separately.
    monkeypatch.setattr(
        "insar_pilot.application.engine_data.import_sources",
        lambda app, store, paths, role, **kw: [store.register_source(paths[0], "Sentinel1SLC", Profile.SENTINEL1_TOPS)],
    )
    transfers = []

    def download(service, tasks, **kwargs):
        results = []
        for task in tasks:
            transfers.append(task.local_path)
            path = Path(task.local_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"verified fixture payload")
            atomic_json(receipt_path(path), {"checks": ["fixture_transport"]})
            results.append(DownloadResult(task.task_id, task.scene, task.product_type, "completed", str(path)))
        return results

    monkeypatch.setattr(engine_download.DownloadService, "download", download)
    completed = []
    for name in ("First", "Second"):
        target = {"name": name, "path": str(tmp_path), "parent_directory": True}
        plan = acquisition.preview(
            app, {"product_ids": [product["product_key"]], "new_project": target, "include_orbits": False}
        )
        result = acquisition.commit(
            app, {"plan_id": plan["plan_id"], "idempotency_key": "request-" + name, "new_project": target}, testing=True
        )
        engine_download.execute(app, result["job"]["job_id"])
        job = app.download(result["job"]["job_id"])
        assert job["status"] == "SUCCESS", job["results"]
        assert job["project_id"] == result["project"]["project_id"]
        completed.append(job)
    assert len(transfers) == 1
    assert Path(completed[0]["published"][0]["path"]).is_relative_to(tmp_path / "First/data/slc")
    assert completed[1]["results"][0]["status"] == "skipped"
    assert completed[1]["published"][0]["path"] == completed[0]["published"][0]["path"]
    assert completed[1]["destination"] == str(tmp_path / "Second/data")
