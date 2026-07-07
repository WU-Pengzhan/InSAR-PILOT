"""Behavioral tests for the headless ``insar-pilot-cli`` entry point.

These drive real bash (with a blank :class:`EnvironmentConfig` so no conda/ISCE2
activation is emitted) against fake ``run_files`` and assert the observable
contract: project layout creation, generation command building, sequential
execution with stop-on-failure, per-invocation logs, persisted step statuses,
and step-range selection. State is written through the same ``ProjectStore``
used by the GUI, so a project stays interchangeable between front-ends.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from insar_pilot.cli.main import main
from insar_pilot.cli.runner import HeadlessRunner
from insar_pilot.domain.project import (
    EnvironmentConfig,
    PreparedInputs,
    ProjectStatus,
    StepStatus,
    WorkflowConfig,
)
from insar_pilot.services.command_plan import CommandPlan
from insar_pilot.services.project_store import ProjectStore
from insar_pilot.services.stack_generator import StackWorkflowService


def _blank_env_project(store: ProjectStore, root: Path):
    """Load the project and blank the environment so bash runs with no conda."""

    project = store.load(root)
    project.environment = EnvironmentConfig(shell_init_path="", conda_env_name="", isce_root="")
    store.save(project)
    return project


def _write_run_files(work_dir: Path, files: dict[str, str]) -> None:
    run_dir = work_dir / "run_files"
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (run_dir / name).write_text(body, encoding="utf-8")


def _generated_project(store: ProjectStore, root: Path, files: dict[str, str]):
    """Create a project, drop fake run files, and sync steps like generation would."""

    project = _blank_env_project(store, root)
    _write_run_files(project.resolved_work_dir(), files)
    StackWorkflowService().synchronize_project_steps(project)
    store.save(project)
    return project


# ----------------------------------------------------------------------
# init
# ----------------------------------------------------------------------
def test_init_creates_layout_and_project_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "proj"
    assert main(["init", str(root), "--name", "demo"]) == 0

    out = capsys.readouterr().out
    assert "demo" in out
    assert (root / "project.pilot").is_file()
    for rel in (
        "data/SLC",
        "data/Orbit",
        "data/DEM",
        "processing/work",
        "outputs/quicklooks",
        "logs",
        ".insar_pilot/cache",
    ):
        assert (root / rel).is_dir(), rel

    project = ProjectStore().load(root)
    assert project.workspace.configured


def test_init_defaults_name_to_directory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "auto_name"
    assert main(["init", str(root)]) == 0
    assert "auto_name" in capsys.readouterr().out


def test_init_refuses_existing_project(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    assert main(["init", str(root)]) == 0
    assert main(["init", str(root)]) == 2


# ----------------------------------------------------------------------
# generate
# ----------------------------------------------------------------------
def test_generate_dry_run_prints_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    project = _blank_env_project(store, root)
    project.workflow = WorkflowConfig(
        input_path=str(root / "data" / "SLC"),
        orbit_path=str(root / "data" / "Orbit"),
        dem_path=str(tmp_path / "dem.dem"),
        work_dir=str(project.resolved_work_dir()),
        bbox_snwe="10 11 20 21",
        azimuth_looks=3,
        range_looks=5,
    )
    project.state.prepared_inputs = PreparedInputs(manifest_path=str(tmp_path / "manifest.txt"))
    store.save(project)

    assert main(["generate", str(root), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "stackSentinel.py" in out
    assert "-s" in out and "manifest.txt" in out
    assert "-b" in out
    assert "-z" in out and "-r" in out
    # Dry-run must not create run_files.
    assert not (project.resolved_work_dir() / "run_files").exists()


def test_generate_refuses_when_runfiles_exist(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    project = _blank_env_project(store, root)
    (project.resolved_work_dir() / "run_files").mkdir(parents=True, exist_ok=True)

    assert main(["generate", str(root)]) == 2


def test_generate_execution_failure_marks_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # With a blank env, `stackSentinel.py` is not on PATH, so generation runs but
    # exits non-zero: exercises the execute-then-fail branch and status update.
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    _blank_env_project(store, root)

    assert main(["generate", str(root)]) == 1
    err = capsys.readouterr().err
    assert "failed" in err.lower()

    project = store.load(root)
    assert project.state.status == ProjectStatus.FAILED
    assert (root / "logs" / "stack_generate.log").is_file()


def test_generate_missing_project_is_usage_error(tmp_path: Path) -> None:
    assert main(["generate", str(tmp_path / "nope")]) == 2


# ----------------------------------------------------------------------
# run
# ----------------------------------------------------------------------
def test_run_executes_steps_and_persists_state(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    project = _generated_project(
        store,
        root,
        {"run_01_first": "echo hello-first\n", "run_02_second": "echo hello-second\n"},
    )
    work_dir = project.resolved_work_dir()

    assert main(["run", str(root)]) == 0

    reloaded = store.load(root)
    assert [step.status for step in reloaded.state.steps] == [StepStatus.SUCCESS, StepStatus.SUCCESS]
    assert reloaded.state.status == ProjectStatus.COMPLETED

    logs = root / "logs"
    assert (logs / "run_01_first.batch_001.log").is_file()
    # Subcommand stdout is captured in its own cmd log.
    cmd_log = (logs / "run_01_first.cmd_001.log").read_text(encoding="utf-8")
    assert "hello-first" in cmd_log
    assert work_dir.name == "work"


def test_run_stops_on_failure_and_propagates_exit(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    _generated_project(
        store,
        root,
        {
            "run_01_ok": "echo ok\n",
            "run_02_boom": "exit 7\n",
            "run_03_never": "echo never\n",
        },
    )

    assert main(["run", str(root)]) == 1

    reloaded = store.load(root)
    statuses = {step.name: step.status for step in reloaded.state.steps}
    assert statuses["run_01_ok"] == StepStatus.SUCCESS
    assert statuses["run_02_boom"] == StepStatus.FAILED
    # The third step never ran.
    assert statuses["run_03_never"] == StepStatus.PENDING
    assert reloaded.state.status == ProjectStatus.FAILED
    # The failing subcommand's non-zero return code is recorded from the marker.
    boom = next(step for step in reloaded.state.steps if step.name == "run_02_boom")
    assert boom.subcommands[0].exit_code == 7


def test_run_step_range_selection(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    _generated_project(
        store,
        root,
        {"run_01_a": "echo a\n", "run_02_b": "echo b\n", "run_03_c": "echo c\n"},
    )

    assert main(["run", str(root), "--steps", "2-3"]) == 0

    reloaded = store.load(root)
    statuses = {step.name: step.status for step in reloaded.state.steps}
    assert statuses["run_01_a"] == StepStatus.PENDING
    assert statuses["run_02_b"] == StepStatus.SUCCESS
    assert statuses["run_03_c"] == StepStatus.SUCCESS
    # Not all steps succeeded, so the project is left GENERATED, not COMPLETED.
    assert reloaded.state.status == ProjectStatus.GENERATED


def test_run_single_step_selection(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    _generated_project(store, root, {"run_01_a": "echo a\n", "run_02_b": "echo b\n"})

    assert main(["run", str(root), "--steps", "1"]) == 0
    reloaded = store.load(root)
    statuses = {step.name: step.status for step in reloaded.state.steps}
    assert statuses["run_01_a"] == StepStatus.SUCCESS
    assert statuses["run_02_b"] == StepStatus.PENDING


def test_run_dry_run_prints_plans_without_executing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    _generated_project(store, root, {"run_01_a": "echo a\n"})

    assert main(["run", str(root), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "run_01_a" in out
    assert "echo a" in out

    reloaded = store.load(root)
    assert reloaded.state.steps[0].status == StepStatus.PENDING
    # No batch log written for a dry run.
    assert not (root / "logs" / "run_01_a.batch_001.log").exists()


def test_run_without_steps_is_usage_error(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    assert main(["run", str(root)]) == 2


def test_run_invalid_step_range_is_usage_error(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    _generated_project(store, root, {"run_01_a": "echo a\n"})

    assert main(["run", str(root), "--steps", "5-9"]) == 2
    assert main(["run", str(root), "--steps", "abc"]) == 2


def test_run_no_pending_steps_returns_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    project = _generated_project(store, root, {"run_01_a": "echo a\n"})
    project.state.steps[0].status = StepStatus.SUCCESS
    store.save(project)

    assert main(["run", str(root)]) == 0
    assert "No pending steps" in capsys.readouterr().out


def test_run_missing_run_file_is_usage_error(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    project = _generated_project(store, root, {"run_01_a": "echo a\n"})
    # Remove the run file after steps were synced.
    Path(project.state.steps[0].path).unlink()

    assert main(["run", str(root)]) == 2


# ----------------------------------------------------------------------
# status
# ----------------------------------------------------------------------
def test_status_prints_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    store = ProjectStore()
    _generated_project(store, root, {"run_01_a": "echo a\n", "run_02_b": "echo b\n"})

    assert main(["status", str(root)]) == 0
    out = capsys.readouterr().out
    assert "STEP" in out and "STATUS" in out
    assert "run_01_a" in out
    assert "run_02_b" in out
    assert "pending" in out


def test_status_without_steps(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "proj"
    main(["init", str(root)])
    assert main(["status", str(root)]) == 0
    assert "No run steps" in capsys.readouterr().out


# ----------------------------------------------------------------------
# argument parsing
# ----------------------------------------------------------------------
def test_no_subcommand_exits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0


# ----------------------------------------------------------------------
# HeadlessRunner
# ----------------------------------------------------------------------
def test_headless_runner_streams_logs_and_returns_exit(tmp_path: Path) -> None:
    echoed: list[str] = []
    runner = HeadlessRunner(
        EnvironmentConfig(shell_init_path="", conda_env_name="", isce_root=""),
        echo=echoed.append,
    )
    log_path = tmp_path / "out.log"
    plan = CommandPlan(
        label="greet",
        command="echo hi-there",
        cwd=str(tmp_path),
        log_path=str(log_path),
        metadata={"skip_environment": True},
    )
    assert runner.run(plan) == 0

    text = log_path.read_text(encoding="utf-8")
    assert text.startswith("$ echo hi-there\n")
    assert "hi-there" in text
    assert "[exit=0, status=0]" in text
    assert any("hi-there" in chunk for chunk in echoed)


def test_headless_runner_reports_nonzero_exit(tmp_path: Path) -> None:
    runner = HeadlessRunner(
        EnvironmentConfig(shell_init_path="", conda_env_name="", isce_root=""),
        echo=lambda _text: None,
    )
    plan = CommandPlan(
        label="boom",
        command="exit 4",
        cwd=str(tmp_path),
        log_path=str(tmp_path / "boom.log"),
        metadata={"skip_environment": True},
    )
    assert runner.run(plan) == 4
