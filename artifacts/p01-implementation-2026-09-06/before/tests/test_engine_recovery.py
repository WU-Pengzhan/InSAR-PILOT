"""Recovery must preserve uncertainty and exclude duplicate science execution."""

import sys
from pathlib import Path

from insar_pilot.application.engine_worker import execute
from insar_pilot.domain.engine import PipelineDefinition, Profile, StepDefinition
from insar_pilot.infrastructure.engine_store import EngineStore


def make_execution(tmp_path: Path):
    source = tmp_path / "input"
    source.write_text("data")
    store = EngineStore.create(tmp_path / "project", "Recovery")
    artifact = store.register_source(source, "NisarRSLC", Profile.NISAR)
    store.attach_dataset([artifact["artifact_id"]], Profile.NISAR, 1)
    definition = PipelineDefinition(
        "recovery", Profile.NISAR, (StepDefinition("one", "One"), StepDefinition("two", "Two", depends_on=("one",)))
    )
    pid = store.add_pipeline(
        definition, {"input": [artifact["artifact_id"]]}, {}, {"python_executable": str(tmp_path / "missing-python")}, 2
    )
    return store, store.submit(store.create_plan(pid)["plan_id"])


def test_invalid_runtime_finishes_queue_with_explicit_failure(tmp_path):
    store, execution = make_execution(tmp_path)
    execute(store, execution["execution_id"], tmp_path / "state")
    runs = [store.run(rid) for rid in execution["run_ids"]]
    assert [r["status"] for r in runs] == ["FAILED", "CANCELLED"]
    assert runs[0]["failure_kind"] == "adapter_error"


def test_lost_worker_does_not_restart_started_science(tmp_path):
    store, execution = make_execution(tmp_path)
    rid = execution["run_ids"][0]
    store.begin(rid, [[sys.executable]], {})
    execute(store, execution["execution_id"], tmp_path / "state")
    assert store.run(rid)["failure_kind"] == "interrupted"
    assert store.run(execution["run_ids"][1])["status"] == "CANCELLED"


def test_duplicate_dispatch_cannot_acquire_execution_lease(tmp_path):
    import fcntl

    store, execution = make_execution(tmp_path)
    with (store.metadata / f"execution-{execution['execution_id']}.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        execute(store, execution["execution_id"], tmp_path / "state")
    assert all(store.run(rid)["status"] == "QUEUED" for rid in execution["run_ids"])
