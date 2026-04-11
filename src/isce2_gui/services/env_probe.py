"""Environment validation for the local ISCE2 installation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from isce2_gui.domain.project import EnvironmentConfig
from isce2_gui.services.shell import ShellCommandBuilder


@dataclass
class ValidationCheck:
    name: str
    ok: bool
    detail: str


@dataclass
class EnvironmentReport:
    checks: list[ValidationCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def as_text(self) -> str:
        if not self.checks:
            return "No validation checks were run."
        return "\n".join(
            f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.detail}"
            for check in self.checks
        )


class EnvironmentProbe:
    """Probe the local shell environment and required ISCE entry points."""

    def __init__(
        self,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._runner = runner

    def _run_shell(self, builder: ShellCommandBuilder, command: str) -> subprocess.CompletedProcess[str]:
        return self._runner(builder.wrap(command), capture_output=True, text=True)

    def probe(self, environment: EnvironmentConfig) -> EnvironmentReport:
        builder = ShellCommandBuilder(environment)
        report = EnvironmentReport()

        shell_init_text = environment.shell_init_path.strip()
        shell_init = Path(shell_init_text).expanduser() if shell_init_text else None
        report.checks.append(
            ValidationCheck(
                name="Shell init",
                ok=shell_init is None or shell_init.exists(),
                detail=(
                    "No shell init configured; the app will rely on explicit conda and ISCE exports."
                    if shell_init is None
                    else f"{shell_init} exists"
                    if shell_init.exists()
                    else f"{shell_init} was not found"
                ),
            )
        )

        isce_root = Path(environment.isce_root).expanduser()
        stack_script = isce_root / "contrib" / "stack" / "topsStack" / "stackSentinel.py"
        report.checks.append(
            ValidationCheck(
                name="ISCE root",
                ok=isce_root.exists() and stack_script.exists(),
                detail=f"Found {stack_script}" if stack_script.exists() else f"Missing {stack_script}",
            )
        )

        shell_checks = [
            ("Python import", "python -c 'import isce, isceobj; print(isce.__file__)'"),
            ("stackSentinel.py", "which stackSentinel.py"),
            ("SentinelWrapper.py", "which SentinelWrapper.py"),
            ("gdal2isce_xml.py", "which gdal2isce_xml.py"),
            ("looks.py", "which looks.py"),
            ("imageMath.py", "which imageMath.py"),
            ("gdal_translate", "which gdal_translate"),
            ("snaphu", "which snaphu"),
        ]
        for name, command in shell_checks:
            completed = self._run_shell(builder, command)
            output = (completed.stdout or completed.stderr).strip()
            detail = output.splitlines()[-1] if output else f"exit={completed.returncode}"
            report.checks.append(
                ValidationCheck(
                    name=name,
                    ok=completed.returncode == 0,
                    detail=detail,
                )
            )

        return report
