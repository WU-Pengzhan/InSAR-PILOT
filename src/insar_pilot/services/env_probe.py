"""Environment validation for the local Sentinel-1 processing runtime."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from insar_pilot.domain.project import EnvironmentConfig
from insar_pilot.services.shell import ShellCommandBuilder


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
    """Probe the local shell environment and required processing entry points."""

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
                    "No shell init configured; the app will rely on explicit conda and runtime exports."
                    if shell_init is None
                    else f"{shell_init} exists"
                    if shell_init.exists()
                    else f"{shell_init} was not found"
                ),
            )
        )

        isce_root_text = environment.isce_root.strip()
        isce_root = Path(isce_root_text).expanduser() if isce_root_text else None
        source_stack_script = (
            isce_root / "contrib" / "stack" / "topsStack" / "stackSentinel.py"
            if isce_root is not None
            else None
        )
        conda_stack_script = (
            isce_root / "share" / "isce2" / "topsStack" / "stackSentinel.py"
            if isce_root is not None
            else None
        )
        if not isce_root_text:
            isce_root_ok = True
            isce_root_detail = "No runtime root override configured; using the environment that launched the application."
        elif source_stack_script is not None and source_stack_script.exists():
            isce_root_ok = True
            isce_root_detail = f"Found source layout: {source_stack_script}"
        elif conda_stack_script is not None and conda_stack_script.exists():
            isce_root_ok = True
            isce_root_detail = f"Found conda-style layout: {conda_stack_script}"
        else:
            isce_root_ok = False
            isce_root_detail = (
                f"Missing stackSentinel.py under source ({source_stack_script}) "
                f"or conda layout ({conda_stack_script})."
            )

        report.checks.append(
            ValidationCheck(
                name="Runtime root",
                ok=isce_root_ok,
                detail=isce_root_detail,
            )
        )

        shell_checks = [
            (
                "Python processing modules",
                "python -c 'import importlib.util, sys; "
                'ok=importlib.util.find_spec("isce") and importlib.util.find_spec("isceobj"); '
                'print("available" if ok else "missing"); sys.exit(0 if ok else 1)\'',
            ),
            ("stackSentinel.py", "which stackSentinel.py"),
            ("SentinelWrapper.py", "which SentinelWrapper.py"),
            (
                "DEM metadata tool",
                "python -c 'import shutil, sys; p=shutil.which(\"gdal2isce_xml.py\"); "
                'print("available" if p else "missing"); sys.exit(0 if p else 1)\'',
            ),
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
