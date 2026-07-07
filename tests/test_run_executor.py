"""Behavioral tests for the QProcess-backed sequential command runner.

These drive a real ``QProcess`` running tiny bash commands (with environment
activation skipped so no conda/ISCE2 is required), and assert the observable
contract: queue ordering, stop-on-nonzero-exit, per-invocation log files, and
signal emissions.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication

from insar_pilot.domain.project import EnvironmentConfig
from insar_pilot.services.command_plan import CommandPlan
from insar_pilot.services.run_executor import ProcessRunner


def _qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _plan(command: str, cwd: Path, log_path: Path, label: str = "step") -> CommandPlan:
    return CommandPlan(
        label=label,
        command=command,
        cwd=str(cwd),
        log_path=str(log_path),
        metadata={"skip_environment": True},
    )


def _pump_until(app: QApplication, predicate, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    if not predicate():
        raise AssertionError("Timed out waiting for the runner to reach the expected state.")


def test_run_queue_runs_plans_in_order_and_emits_signals(tmp_path: Path) -> None:
    app = _qt_app()
    runner = ProcessRunner(EnvironmentConfig())

    started: list[str] = []
    finished: list[tuple[str, int]] = []
    queue_done: list[tuple[bool, str]] = []
    states: list[str] = []
    runner.command_started.connect(lambda plan: started.append(plan.label))
    runner.command_finished.connect(lambda plan, code: finished.append((plan.label, code)))
    runner.queue_finished.connect(lambda ok, msg: queue_done.append((ok, msg)))
    runner.runner_state_changed.connect(states.append)

    marker = tmp_path / "order.txt"
    plans = [
        _plan(f"echo first >> {marker}", tmp_path, tmp_path / "a.log", label="first"),
        _plan(f"echo second >> {marker}", tmp_path, tmp_path / "b.log", label="second"),
    ]
    runner.run_queue(plans)
    _pump_until(app, lambda: bool(queue_done))

    # Both commands ran, in queue order.
    assert [label for label, _ in finished] == ["first", "second"]
    assert started == ["first", "second"]
    assert marker.read_text(encoding="utf-8").split() == ["first", "second"]
    # Success terminal signal + state transitions running -> idle.
    assert queue_done == [(True, "All queued commands finished.")]
    assert states[0] == "running"
    assert states[-1] == "idle"


def test_per_invocation_log_file_captures_command_output_and_exit(tmp_path: Path) -> None:
    app = _qt_app()
    runner = ProcessRunner(EnvironmentConfig())
    done: list[bool] = []
    runner.queue_finished.connect(lambda ok, msg: done.append(ok))

    log_path = tmp_path / "run.log"
    runner.run_queue([_plan("echo hello-log", tmp_path, log_path, label="greet")])
    _pump_until(app, lambda: bool(done))

    text = log_path.read_text(encoding="utf-8")
    assert text.startswith("$ echo hello-log\n")  # command header
    assert "hello-log" in text  # streamed stdout
    assert "[exit=0, status=" in text  # exit footer


def test_stop_on_first_nonzero_exit_halts_queue(tmp_path: Path) -> None:
    app = _qt_app()
    runner = ProcessRunner(EnvironmentConfig())
    finished: list[tuple[str, int]] = []
    queue_done: list[tuple[bool, str]] = []
    runner.command_finished.connect(lambda plan, code: finished.append((plan.label, code)))
    runner.queue_finished.connect(lambda ok, msg: queue_done.append((ok, msg)))

    never = tmp_path / "never.txt"
    plans = [
        _plan("exit 3", tmp_path, tmp_path / "fail.log", label="boom"),
        _plan(f"echo ran >> {never}", tmp_path, tmp_path / "after.log", label="after"),
    ]
    runner.run_queue(plans)
    _pump_until(app, lambda: bool(queue_done))

    # The failing command reports its non-zero code; the second never runs.
    assert finished == [("boom", 3)]
    assert not never.exists()
    assert queue_done == [(False, "Command failed: boom")]


def test_run_queue_rejects_concurrent_run(tmp_path: Path) -> None:
    app = _qt_app()
    runner = ProcessRunner(EnvironmentConfig())
    done: list[bool] = []
    runner.queue_finished.connect(lambda ok, msg: done.append(ok))

    runner.run_queue([_plan("sleep 0.3", tmp_path, tmp_path / "sleep.log")])
    assert runner.is_running() is True
    try:
        runner.run_queue([_plan("echo x", tmp_path, tmp_path / "x.log")])
    except RuntimeError as exc:
        assert "already running" in str(exc)
    else:
        raise AssertionError("A second run_queue while running must raise RuntimeError.")
    _pump_until(app, lambda: bool(done))
    assert runner.is_running() is False


def test_stop_kills_running_process_and_reports_stopped(tmp_path: Path) -> None:
    app = _qt_app()
    runner = ProcessRunner(EnvironmentConfig())
    queue_done: list[tuple[bool, str]] = []
    runner.queue_finished.connect(lambda ok, msg: queue_done.append((ok, msg)))

    runner.run_queue([_plan("sleep 5", tmp_path, tmp_path / "long.log")])
    _pump_until(app, lambda: runner.is_running())
    runner.stop()
    assert runner.stopping is True
    _pump_until(app, lambda: bool(queue_done))

    assert queue_done == [(False, "Execution stopped.")]
    assert runner.is_running() is False


def test_set_environment_rebuilds_builder() -> None:
    runner = ProcessRunner(EnvironmentConfig(conda_env_name="insar"))
    original = runner._builder
    runner.set_environment(EnvironmentConfig(conda_env_name="other"))
    assert runner._builder is not original


def test_exit_status_code_handles_enum_and_fallback() -> None:
    assert ProcessRunner._exit_status_code(QProcess.ExitStatus.NormalExit) == 0
    assert ProcessRunner._exit_status_code(QProcess.ExitStatus.CrashExit) == 1

    class _Bad:
        def __int__(self) -> int:
            raise ValueError("not an int")

    assert ProcessRunner._exit_status_code(_Bad()) == -1  # type: ignore[arg-type]
