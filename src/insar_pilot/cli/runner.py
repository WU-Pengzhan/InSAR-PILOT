"""Subprocess-backed command runner for the headless CLI.

Mirrors the observable log/exit contract of the Qt ``ProcessRunner`` (see
``services/run_executor.py``) so a project's ``logs/`` output looks identical
whether a step was executed from the GUI or the CLI: each invocation gets a
clean per-command log file that starts with a ``$ <command>`` header, captures
merged stdout/stderr, and ends with an ``[exit=..., status=...]`` footer.

This module is intentionally Qt-free; it drives ``subprocess.Popen`` directly
and builds the final ``bash -lc`` invocation through ``ShellCommandBuilder`` so
conda activation and ISCE2 environment exports are applied exactly as the GUI
applies them.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from insar_pilot.domain.project import EnvironmentConfig
from insar_pilot.services.command_plan import CommandPlan
from insar_pilot.services.shell import ShellCommandBuilder


def _default_echo(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


class HeadlessRunner:
    """Run :class:`CommandPlan` invocations sequentially without Qt."""

    def __init__(
        self,
        environment: EnvironmentConfig,
        *,
        echo: Callable[[str], None] | None = None,
    ) -> None:
        self._builder = ShellCommandBuilder(environment)
        self._echo = echo if echo is not None else _default_echo

    def _argv(self, plan: CommandPlan) -> list[str]:
        cwd = Path(plan.cwd) if plan.cwd else None
        if plan.metadata.get("skip_environment"):
            return ShellCommandBuilder.wrap_without_activation(plan.command, cwd)
        return self._builder.wrap(plan.command, cwd)

    def run(self, plan: CommandPlan) -> int:
        """Execute one plan, stream output to its log + stdout, return exit code.

        Returns the process exit code, normalizing signal-terminated processes
        to ``-1`` to match the Qt runner's ``CrashExit`` handling.
        """

        log_path = Path(plan.log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        argv = self._argv(plan)

        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write(f"$ {plan.command}\n")
            handle.flush()
            process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            stream = process.stdout
            assert stream is not None
            for line in stream:
                handle.write(line)
                handle.flush()
                self._echo(line)
            return_code = process.wait()
            status_code = 0 if return_code >= 0 else 1
            handle.write(f"\n[exit={return_code}, status={status_code}]\n")

        return return_code if return_code >= 0 else -1
