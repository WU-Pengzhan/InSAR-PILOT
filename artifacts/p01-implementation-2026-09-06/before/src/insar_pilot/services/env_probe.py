"""Environment validation for the local Sentinel-1 processing runtime."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from insar_pilot.domain.project import EnvironmentConfig
from insar_pilot.services.shell import (
    ShellCommandBuilder,
    is_conda_isce_layout,
    is_source_isce_layout,
    resolve_isce_runtime_root,
)


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

        conda_prefix_text = os.environ.get("CONDA_PREFIX", "").strip()
        conda_prefix = Path(conda_prefix_text).expanduser().resolve() if conda_prefix_text else None
        python_prefix = Path(sys.prefix).expanduser().resolve()
        report.checks.append(
            ValidationCheck(
                name="Launch environment",
                ok=conda_prefix == python_prefix,
                detail=(
                    f"Inherited active conda environment at {conda_prefix}."
                    if conda_prefix == python_prefix
                    else f"Active conda prefix {conda_prefix or '<missing>'} does not match Python {python_prefix}."
                ),
            )
        )

        isce_root = resolve_isce_runtime_root("")
        if isce_root is not None and is_source_isce_layout(isce_root):
            stack_script = isce_root / "contrib" / "stack" / "topsStack" / "stackSentinel.py"
            layout_detail = f"source layout: {stack_script}"
        elif isce_root is not None and is_conda_isce_layout(isce_root):
            stack_script = isce_root / "share" / "isce2" / "topsStack" / "stackSentinel.py"
            layout_detail = f"conda-style layout: {stack_script}"
        else:
            stack_script = None
            layout_detail = ""

        if isce_root is not None:
            isce_root_ok = True
            isce_root_detail = f"Found {layout_detail}."
        else:
            isce_root_ok = True
            isce_root_detail = "No runtime root configured; relying on PATH/PYTHONPATH from the launch environment."

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
                "python -c 'import importlib.util, isce, sys; "
                'missing=[name for name in ("isce", "isceobj") if importlib.util.find_spec(name) is None]; '
                'print("available" if not missing else "missing: "+", ".join(missing)); '
                "sys.exit(1 if missing else 0)'",
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
