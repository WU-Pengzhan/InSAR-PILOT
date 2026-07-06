"""Qt-based sequential command runner with log capture."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from insar_pilot.domain.project import EnvironmentConfig
from insar_pilot.services.command_plan import CommandPlan
from insar_pilot.services.shell import ShellCommandBuilder


class ProcessRunner(QObject):
    """Run commands inside the configured WSL bash environment."""

    log_emitted = Signal(str)
    command_started = Signal(object)
    command_finished = Signal(object, int)
    queue_finished = Signal(bool, str)
    runner_state_changed = Signal(str)

    def __init__(self, environment: EnvironmentConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._builder = ShellCommandBuilder(environment)
        self._process: QProcess | None = None
        self._queue: list[CommandPlan] = []
        self._current: CommandPlan | None = None
        self._log_handle = None
        self._stopping = False

    def set_environment(self, environment: EnvironmentConfig) -> None:
        self._builder = ShellCommandBuilder(environment)

    @property
    def stopping(self) -> bool:
        return self._stopping

    def is_running(self) -> bool:
        return self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning

    def run_queue(self, plans: list[CommandPlan]) -> None:
        if self.is_running():
            raise RuntimeError("A command is already running.")
        self._queue = list(plans)
        self._stopping = False
        self._start_next()

    def stop(self) -> None:
        if not self.is_running() or self._process is None:
            return
        self._stopping = True
        self._queue.clear()
        self._process.kill()

    def _start_next(self) -> None:
        if not self._queue:
            message = "Execution stopped." if self._stopping else "All queued commands finished."
            success = not self._stopping
            self._stopping = False
            self.runner_state_changed.emit("idle")
            self.queue_finished.emit(success, message)
            return

        plan = self._queue.pop(0)
        self._current = plan
        Path(plan.log_path).parent.mkdir(parents=True, exist_ok=True)
        # Keep one clean log per invocation to avoid mixing stale failures with
        # the current run.
        self._log_handle = open(plan.log_path, "w", encoding="utf-8")
        self._log_handle.write(f"$ {plan.command}\n")
        self._log_handle.flush()

        argv = self._wrap_plan(plan)
        process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        if environment.contains("LD_LIBRARY_PATH"):
            # Avoid host-shell/libtinfo mismatches when launching /usr/bin/bash from
            # GUI sessions that inherit a conda library path from the parent shell.
            environment.remove("LD_LIBRARY_PATH")
        process.setProcessEnvironment(environment)
        process.setProgram(argv[0])
        process.setArguments(argv[1:])
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(self._handle_finished)
        self._process = process

        self.runner_state_changed.emit("running")
        self.command_started.emit(plan)
        process.start()

    def _wrap_plan(self, plan: CommandPlan) -> list[str]:
        if plan.metadata.get("skip_environment"):
            return ShellCommandBuilder.wrap_without_activation(plan.command, Path(plan.cwd) if plan.cwd else None)
        return self._builder.wrap(plan.command, Path(plan.cwd))

    def _read_output(self) -> None:
        if self._process is None:
            return
        payload = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not payload:
            return
        if self._log_handle is not None:
            self._log_handle.write(payload)
            self._log_handle.flush()
        self.log_emitted.emit(payload)

    def _handle_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        plan = self._current
        self._current = None
        if self._log_handle is not None:
            status_code = self._exit_status_code(exit_status)
            self._log_handle.write(f"\n[exit={exit_code}, status={status_code}]\n")
            self._log_handle.close()
            self._log_handle = None

        actual_exit_code = exit_code if exit_status == QProcess.ExitStatus.NormalExit else -1
        self.command_finished.emit(plan, actual_exit_code)

        if self._process is not None:
            self._process.deleteLater()
            self._process = None

        if self._stopping:
            self._queue.clear()
            self._start_next()
            return

        if actual_exit_code != 0:
            self.runner_state_changed.emit("idle")
            self.queue_finished.emit(False, f"Command failed: {plan.label}")
            self._queue.clear()
            return

        self._start_next()

    @staticmethod
    def _exit_status_code(exit_status: QProcess.ExitStatus) -> int:
        if hasattr(exit_status, "value"):
            return int(exit_status.value)
        try:
            return int(exit_status)
        except (TypeError, ValueError):
            return -1
