from __future__ import annotations

from pathlib import Path

from insar_pilot.backends.isce2 import Isce2TopsStackTaskBackend
from insar_pilot.domain.local_data import AssetRef
from insar_pilot.domain.task_runtime import RuntimeProfile, TaskRunRequest, TaskStatus
from insar_pilot.providers.task_runtime import TaskBackendRegistry
from insar_pilot.services.task_runtime import TaskExecutionApplicationService, TaskRunStore
from insar_pilot.services.workflow_eligibility import build_default_workflow_recipe_registry


def _descriptor():
    recipe = next(
        item
        for item in build_default_workflow_recipe_registry().descriptors()
        if item.recipe_id == "sentinel1.tops.isce2"
    )
    return next(task for task in recipe.tasks if task.task_id == "sentinel1.run_official_stage")


def _execute(tmp_path: Path, text: str):
    work_dir = tmp_path / "work"
    run_dir = work_dir / "run_files"
    run_dir.mkdir(parents=True)
    run_file = run_dir / "run_13_generate_burst_igram"
    run_file.write_text(text, encoding="utf-8")
    registry = TaskBackendRegistry()
    registry.register(Isce2TopsStackTaskBackend())
    service = TaskExecutionApplicationService(registry, TaskRunStore(tmp_path / "project"))
    request = TaskRunRequest(
        run_id="official-stage-001",
        task_id="sentinel1.run_official_stage",
        backend_id="isce2.topsstack",
        inputs=(AssetRef(str(run_file), "run_file"),),
        output_dir=str(tmp_path / "task-output"),
        parameters={"max_parallel": 2},
    )
    return service.execute(
        _descriptor(),
        request,
        RuntimeProfile("local-isce2", "isce2.topsstack", {}),
    )


def test_official_isce2_stage_runs_generated_parallel_batches(tmp_path: Path) -> None:
    record = _execute(
        tmp_path,
        "printf first &\nprintf second &\nwait\nprintf third\n",
    )

    assert record.status is TaskStatus.SUCCEEDED
    assert record.outputs[0].role == "stage_artifact"
    assert (tmp_path / "task-output" / "command_001.log").read_text(encoding="utf-8") == "first"
    assert (tmp_path / "task-output" / "command_003.log").read_text(encoding="utf-8") == "third"


def test_official_isce2_stage_propagates_subcommand_failure(tmp_path: Path) -> None:
    record = _execute(tmp_path, "printf ok &\nfalse &\nwait\nprintf should-not-run\n")

    assert record.status is TaskStatus.FAILED
    assert record.exit_code == 1
    assert "batch 1/2" in record.message
    assert not (tmp_path / "task-output" / "command_003.log").exists()
