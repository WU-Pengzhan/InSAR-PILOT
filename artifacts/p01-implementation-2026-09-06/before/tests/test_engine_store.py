"""Behavioral tests for history isolation, intent revisions and recovery."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from insar_pilot.domain.engine import (
    ArtifactOutput,
    OutputAsset,
    PipelineDefinition,
    Profile,
    QCCheck,
    QCMetric,
    QCReport,
    RunStatus,
    StepDefinition,
)
from insar_pilot.infrastructure.engine_store import ConflictError, EngineStore, atomic_json


@pytest.fixture
def project(tmp_path: Path) -> tuple[EngineStore, str]:
    source = tmp_path / "input.dat"
    source.write_bytes(b"science input")
    store = EngineStore.create(tmp_path / "project", "Example")
    artifact = store.register_source(source, "Sentinel1SLC", Profile.SENTINEL1_TOPS)
    store.attach_dataset([artifact["artifact_id"]], Profile.SENTINEL1_TOPS, 1)
    definition = PipelineDefinition(
        "test.pipeline",
        Profile.SENTINEL1_TOPS,
        (
            StepDefinition("geometry", "Geometry", output_roles=("geometry",)),
            StepDefinition("interferogram", "Interferogram", depends_on=("geometry",), output_roles=("ifg",)),
        ),
    )
    pid = store.add_pipeline(definition, {"source": [artifact["artifact_id"]]}, {"reference": "A"}, {}, 2)
    return store, pid


def success_report() -> QCReport:
    check = QCCheck("output_exists", "exists", expected=True, blocking=True)
    return QCReport(checks=(check.evaluate(QCMetric("exists", True)),))


def execute_first(store: EngineStore, pid: str) -> tuple[str, dict]:
    execution = store.submit(store.create_plan(pid, "geometry")["plan_id"])
    rid = execution["run_ids"][0]
    store.begin(rid, [["official", "processor"]], {"version": "test"})
    output = Path(execution["working_directory"]) / "geometry.bin"
    output.write_bytes(b"immutable geometry")
    artifact = store.publish(rid, ArtifactOutput("ReferenceGeometry", (OutputAsset(str(output), "geometry"),)))
    store.finish(rid, RunStatus.SUCCESS, 0, [artifact], success_report())
    return rid, artifact


def test_profile_locks_and_mixed_mission_attach_is_rejected(project, tmp_path):
    store, _ = project
    with pytest.raises(ConflictError):
        store.revise(3, profile="nisar", profile_locked=False)
    source = tmp_path / "nisar.h5"
    source.write_bytes(b"hdf5")
    artifact = store.register_source(source, "NisarRSLC", Profile.NISAR)
    with pytest.raises(ConflictError):
        store.attach_dataset([artifact["artifact_id"]], Profile.NISAR, 3)
    store.revise(3, datasets=[])
    assert store.project()["profile_locked"] is True


def test_revision_conflicts_do_not_overwrite_current_intent(project):
    store, _ = project
    store.revise(3, name="Updated")
    with pytest.raises(ConflictError):
        store.revise(3, name="Lost update")
    assert store.project()["name"] == "Updated"


def test_recovery_finishes_only_manifest_matching_pending_revision(project):
    store, _ = project
    body = {**store.project(), "revision": 4, "name": "After crash"}
    with store.connection() as db:
        db.execute("INSERT INTO pending_revision VALUES(1,?)", (json.dumps(body),))
    atomic_json(store.root / "project.pilot", body)
    reopened = EngineStore(store.root)
    assert reopened.project()["name"] == "After crash"
    assert reopened.events()[-1]["event_type"] == "project.revised"


def test_recovery_aborts_pending_before_file_replace(project):
    store, _ = project
    body = {**store.project(), "revision": 4, "name": "Never published"}
    with store.connection() as db:
        db.execute("INSERT INTO pending_revision VALUES(1,?)", (json.dumps(body),))
    assert EngineStore(store.root).project()["revision"] == 3


def test_rerun_preserves_history_and_physical_outputs(project):
    store, pid = project
    rid, artifact = execute_first(store, pid)
    historical = store.run(rid)
    Path(historical["working_directory"], "geometry.bin").write_bytes(b"later mutable change")
    assert Path(artifact["assets"][0]["uri"]).read_bytes() == b"immutable geometry"
    rid2, _ = execute_first(store, pid)
    assert rid2 != rid
    assert store.run(rid) == historical
    assert store.states(pid)[0]["active_run_id"] == rid2
    assert store.run(rid2)["working_directory"] != historical["working_directory"]


def test_terminal_run_cannot_be_overwritten_even_with_sql(project):
    store, pid = project
    rid, _ = execute_first(store, pid)
    with pytest.raises(ConflictError):
        store.finish(rid, RunStatus.FAILED, 2)
    with pytest.raises(sqlite3.IntegrityError), store.connection() as db:
        db.execute("UPDATE runs SET status='FAILED' WHERE run_id=?", (rid,))


def test_stale_propagates_without_rewriting_success(project):
    store, pid = project
    rid, _ = execute_first(store, pid)
    pipelines = store.project()["pipelines"]
    pipelines[pid]["parameters"]["reference"] = "B"
    store.revise(3, pipelines=pipelines)
    states = store.states(pid)
    assert states[0]["status"] == "STALE"
    assert states[1]["active_usable"] is False
    assert store.run(rid)["status"] == "SUCCESS"


def test_changed_input_blocks_plan(project):
    store, pid = project
    source = Path(store.list_objects("artifacts")[0]["assets"][0]["uri"])
    source.write_bytes(b"changed input bytes")
    with pytest.raises(ConflictError, match="input_changed"):
        store.create_plan(pid)


def test_old_plan_rejected_and_double_submit_rejected(project):
    store, pid = project
    plan = store.create_plan(pid, "geometry")
    store.revise(3, name="Revision changed")
    with pytest.raises(ConflictError, match="stale"):
        store.submit(plan["plan_id"])
    plan = store.create_plan(pid, "geometry")
    store.submit(plan["plan_id"])
    with pytest.raises(ConflictError, match="already submitted"):
        store.submit(plan["plan_id"])


def test_exit_zero_with_failed_structural_qc_is_failed(project):
    store, pid = project
    execution = store.submit(store.create_plan(pid, "geometry")["plan_id"])
    rid = execution["run_ids"][0]
    store.begin(rid, [["processor"]], {})
    check = QCCheck("exists", "exists", expected=True, blocking=True)
    report = QCReport(checks=(check.evaluate(QCMetric("exists", False)),))
    result = store.finish(rid, RunStatus.SUCCESS, 0, report=report)
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 0
    assert result["failure_kind"] == "artifact_contract"


def test_completion_after_edit_does_not_promote_stale_run(project):
    store, pid = project
    execution = store.submit(store.create_plan(pid, "geometry")["plan_id"])
    rid = execution["run_ids"][0]
    store.begin(rid, [["processor"]], {})
    pipelines = store.project()["pipelines"]
    pipelines[pid]["parameters"]["reference"] = "B"
    store.revise(3, pipelines=pipelines)
    output = Path(execution["working_directory"]) / "geometry.bin"
    output.write_bytes(b"old configuration")
    artifact = store.publish(rid, ArtifactOutput("ReferenceGeometry", (OutputAsset(str(output), "geometry"),)))
    store.finish(rid, RunStatus.SUCCESS, 0, [artifact], success_report())
    assert store.run(rid)["status"] == "SUCCESS"
    assert store.states(pid)[0]["active_run_id"] is None


def test_qc_reevaluation_preserves_history_and_signature(project):
    store, pid = project
    rid, _ = execute_first(store, pid)
    historical = store.run(rid)
    signature = store.desired(pid, "geometry")[0]
    report = QCReport(
        policy_version="2",
        checks=(QCCheck("valid", "valid", expected=True, blocking=True).evaluate(QCMetric("valid", False)),),
    )
    store.evaluate_qc(rid, report)
    assert store.run(rid) == historical
    assert store.desired(pid, "geometry")[0] == signature
    assert store.states(pid)[0]["active_usable"] is False
    with pytest.raises(ConflictError, match="QC-accepted"):
        store.set_active(rid)
    store.evaluate_qc(rid, success_report())
    assert store.states(pid)[0]["status"] == "SUCCESS"


def test_empty_outputs_cannot_satisfy_product_contract(project):
    store, pid = project
    execution = store.submit(store.create_plan(pid, "geometry")["plan_id"])
    rid = execution["run_ids"][0]
    store.begin(rid, [["processor"]], {})
    result = store.finish(rid, RunStatus.SUCCESS, 0, report=success_report())
    assert result["status"] == "FAILED"
    assert result["failure_kind"] == "artifact_contract"
    assert result["exit_code"] == 0


def test_presentation_edit_allows_matching_completion(project, monkeypatch):
    store, pid = project
    finish = store.finish

    def finish_after_edit(*args, **kwargs):
        store.revise(3, name="Renamed while running")
        return finish(*args, **kwargs)

    monkeypatch.setattr(store, "finish", finish_after_edit)
    rid, _ = execute_first(store, pid)
    assert store.states(pid)[0]["active_run_id"] == rid


def test_events_are_durable_ordered_and_replayable(project):
    store, pid = project
    execute_first(store, pid)
    first = store.events(limit=2)
    remaining = EngineStore(store.root).events(after=first[-1]["sequence"])
    assert all(e["sequence"] > first[-1]["sequence"] for e in remaining)
    assert len({e["event_id"] for e in first + remaining}) == len(first + remaining)


def test_artifact_publication_rejects_output_outside_workspace(project, tmp_path):
    store, pid = project
    execution = store.submit(store.create_plan(pid, "geometry")["plan_id"])
    rid = execution["run_ids"][0]
    store.begin(rid, [["processor"]], {})
    source = tmp_path / "outside"
    source.write_bytes(b"do not publish")
    with pytest.raises(ValueError, match="isolated workspace"):
        store.publish(rid, ArtifactOutput("bad", (OutputAsset(str(source), "data"),)))


def test_unconfigured_scientific_metric_is_unknown_and_advisory():
    result = QCCheck("coherence", "coherence").evaluate(QCMetric("coherence", 0.2))
    assert result["status"] == "UNKNOWN"
    assert QCReport(checks=(result,)).gate_passed
    assert not QCReport(checks=(QCCheck("needed", "missing", blocking=True).evaluate(None),)).gate_passed


def test_shared_hdf5_datasets_have_distinct_artifacts_and_one_container(project):
    store, pid = project
    execution = store.submit(store.create_plan(pid, "geometry")["plan_id"])
    rid = execution["run_ids"][0]
    store.begin(rid, [["processor"]], {})
    output = Path(execution["working_directory"]) / "product.h5"
    output.write_bytes(b"container bytes")
    artifacts = store.publish_outputs(
        rid, [ArtifactOutput(role, (OutputAsset(str(output), role, f"/{role}"),)) for role in ("phase", "coherence")]
    )
    assert artifacts[0]["artifact_id"] != artifacts[1]["artifact_id"]
    assert artifacts[0]["assets"][0]["uri"] == artifacts[1]["assets"][0]["uri"]
    assert artifacts[1]["assets"][0]["subdataset"] == "/coherence"
    store.finish(rid, RunStatus.SUCCESS, 0, artifacts, success_report())
    assert len(store.run(rid)["output_artifact_ids"]) == 2


def test_template_change_invalidates_preview_and_success(project, tmp_path):
    store, pid = project
    template = tmp_path / "official.yaml"
    template.write_text("science: 1")
    pipelines = store.project()["pipelines"]
    pipelines[pid]["parameters"]["template_path"] = str(template)
    store.revise(3, pipelines=pipelines)
    rid, _ = execute_first(store, pid)
    plan = store.create_plan(pid, "geometry")
    template.write_text("science: 2")
    with pytest.raises(ConflictError, match="template changed"):
        store.submit(plan["plan_id"])
    assert store.states(pid)[0]["status"] == "STALE"
    assert store.run(rid)["status"] == "SUCCESS"


def test_remote_selection_becomes_a_new_dataset_revision(tmp_path):
    store = EngineStore.create(tmp_path / "project", "Selection")
    remote = store.register_remote({"remote_product_id": "S1", "provider_id": "asf"}, Profile.SENTINEL1_TOPS)
    store.attach_dataset([remote["artifact_id"]], Profile.SENTINEL1_TOPS, 1)
    assert store.availability(remote) == (False, "source_not_acquired")
    source = tmp_path / "source.zip"
    source.write_bytes(b"downloaded")
    local = store.register_source(source, "Sentinel1SLC", Profile.SENTINEL1_TOPS)
    store.resolve_remote("S1", local["artifact_id"])
    dataset = store.project()["datasets"][0]
    assert dataset["revision"] == 2
    assert dataset["artifact_ids"] == [local["artifact_id"]]
    assert store.artifact(remote["artifact_id"]) == remote
