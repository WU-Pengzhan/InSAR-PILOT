from pathlib import Path

import pytest

from insar_pilot.domain.project import (
    APP_METADATA_DIR,
    PreparedInputs,
    ProjectDocument,
    ProjectStatus,
    StepStatus,
    WorkflowConfig,
)
from insar_pilot.services.stack_generator import StackWorkflowService


def test_build_generate_command_uses_managed_empty_aux_dir(tmp_path: Path):
    project = ProjectDocument(
        workflow=WorkflowConfig(
            input_path=str(tmp_path / "inputs"),
            orbit_path=str(tmp_path / "orbits"),
            dem_path=str(tmp_path / "dem.dem"),
            work_dir=str(tmp_path / "work"),
            bbox_snwe="10 11 20 21",
        )
    )
    prepared = PreparedInputs(
        manifest_path=str(tmp_path / "work" / APP_METADATA_DIR / "inputs" / "safe_inputs.txt")
    )

    command = StackWorkflowService().build_generate_command(project, prepared)

    assert "stackSentinel.py" in command
    assert "-s" in command
    assert "-a" in command
    assert f"{APP_METADATA_DIR}/aux_empty" in command
    assert "-b" in command
    assert "-z" in command
    assert "-r" in command


def test_build_generate_command_supports_custom_looks(tmp_path: Path):
    project = ProjectDocument(
        workflow=WorkflowConfig(
            input_path=str(tmp_path / "inputs"),
            orbit_path=str(tmp_path / "orbits"),
            dem_path=str(tmp_path / "dem.dem"),
            work_dir=str(tmp_path / "work"),
            azimuth_looks=5,
            range_looks=7,
        )
    )
    prepared = PreparedInputs(
        manifest_path=str(tmp_path / "work" / APP_METADATA_DIR / "inputs" / "safe_inputs.txt")
    )

    command = StackWorkflowService().build_generate_command(project, prepared)

    assert "-z 5" in command
    assert "-r 7" in command
    assert "--num_proc 1" in command


def _workflow_project(tmp_path: Path, **overrides) -> ProjectDocument:
    defaults = dict(
        input_path=str(tmp_path / "inputs"),
        orbit_path=str(tmp_path / "orbits"),
        dem_path=str(tmp_path / "dem.dem"),
        work_dir=str(tmp_path / "work"),
    )
    defaults.update(overrides)
    return ProjectDocument(workflow=WorkflowConfig(**defaults))


def test_ensure_generation_allowed_blocks_existing_run_files(tmp_path: Path):
    project = _workflow_project(tmp_path)
    run_files = project.resolved_work_dir() / "run_files"
    run_files.mkdir(parents=True)

    with pytest.raises(FileExistsError) as excinfo:
        StackWorkflowService().ensure_generation_allowed(project)
    assert "run_files" in str(excinfo.value)


def test_resolve_aux_dir_prefers_explicit_path(tmp_path: Path):
    aux = tmp_path / "AUX_CAL"
    project = _workflow_project(tmp_path, aux_path=str(aux))

    resolved = StackWorkflowService().resolve_aux_dir(project, PreparedInputs())

    assert resolved == aux


def test_resolve_aux_dir_raises_when_aux_required(tmp_path: Path):
    project = _workflow_project(tmp_path)

    with pytest.raises(ValueError, match="AUX_CAL is required"):
        StackWorkflowService().resolve_aux_dir(project, PreparedInputs(aux_required=True))


def test_resolve_aux_dir_creates_managed_empty_dir(tmp_path: Path):
    project = _workflow_project(tmp_path)

    resolved = StackWorkflowService().resolve_aux_dir(project, PreparedInputs())

    assert resolved.is_dir()
    assert resolved.name == "aux_empty"


def test_build_generate_command_includes_reference_date_when_set(tmp_path: Path):
    project = _workflow_project(tmp_path, reference_date="20240101")
    prepared = PreparedInputs(manifest_path=str(tmp_path / "safe_inputs.txt"))

    command = StackWorkflowService().build_generate_command(project, prepared)

    assert "-m 20240101" in command


def test_discover_and_synchronize_run_files_sets_generated_status(tmp_path: Path):
    project = _workflow_project(tmp_path)
    run_dir = project.resolved_work_dir() / "run_files"
    run_dir.mkdir(parents=True)
    (run_dir / "run_02_second").write_text("echo two", encoding="utf-8")
    (run_dir / "run_01_first").write_text("echo one", encoding="utf-8")
    (run_dir / "ignore.txt").write_text("noise", encoding="utf-8")

    service = StackWorkflowService()
    discovered = service.discover_run_files(project.resolved_work_dir())
    steps = service.synchronize_project_steps(project)

    # Only run_* files, sorted; unrelated file excluded.
    assert [path.name for path in discovered] == ["run_01_first", "run_02_second"]
    assert [step.name for step in steps] == ["run_01_first", "run_02_second"]
    assert project.state.status == ProjectStatus.GENERATED


def test_synchronize_project_steps_without_run_files_keeps_status(tmp_path: Path):
    project = _workflow_project(tmp_path)
    project.resolved_work_dir().mkdir(parents=True)

    steps = StackWorkflowService().synchronize_project_steps(project)

    assert steps == []
    assert project.state.status != ProjectStatus.GENERATED


def test_step_command_quotes_path():
    from insar_pilot.domain.project import RunStep

    step = RunStep(name="run_01", path="/work/run files/run_01")
    assert StackWorkflowService.step_command(step) == "bash '/work/run files/run_01'"


def test_next_runnable_and_remaining_steps_skip_completed():
    from insar_pilot.domain.project import RunStep

    project = ProjectDocument()
    project.state.steps = [
        RunStep(name="run_01", path="/w/run_01", status=StepStatus.SUCCESS),
        RunStep(name="run_02", path="/w/run_02", status=StepStatus.FAILED),
        RunStep(name="run_03", path="/w/run_03", status=StepStatus.PENDING),
    ]

    service = StackWorkflowService()
    assert service.next_runnable_step(project).name == "run_02"
    assert [step.name for step in service.remaining_steps(project)] == ["run_02", "run_03"]


def test_next_runnable_step_returns_none_when_all_done():
    from insar_pilot.domain.project import RunStep

    project = ProjectDocument()
    project.state.steps = [RunStep(name="run_01", path="/w/run_01", status=StepStatus.SUCCESS)]

    assert StackWorkflowService.next_runnable_step(project) is None
