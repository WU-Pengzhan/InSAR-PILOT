"""Preflight checks before topsStack workflow generation."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from insar_pilot.domain.project import PreparedInputs, ProjectDocument


@dataclass(frozen=True)
class DownloadCapability:
    """Runtime capability for the current download backend."""

    aria2c_path: str = ""

    @property
    def aria2c_available(self) -> bool:
        return bool(self.aria2c_path)

    @property
    def status(self) -> str:
        return "available" if self.aria2c_available else "missing"


@dataclass(frozen=True)
class PreflightCheck:
    """One preflight item for display and tests."""

    key: str
    label: str
    status: str
    detail: str

    @property
    def blocking(self) -> bool:
        return self.status == "blocker"

    @property
    def warning(self) -> bool:
        return self.status == "warning"


@dataclass(frozen=True)
class PreflightReport:
    """Collection of checks produced before workflow generation."""

    checks: list[PreflightCheck] = field(default_factory=list)

    @property
    def blockers(self) -> list[PreflightCheck]:
        return [check for check in self.checks if check.blocking]

    @property
    def warnings(self) -> list[PreflightCheck]:
        return [check for check in self.checks if check.warning]

    @property
    def ok(self) -> bool:
        return not self.blockers

    def as_text(self) -> str:
        if not self.checks:
            return "No preflight checks were run."
        prefix = {"ok": "OK", "warning": "WARN", "blocker": "BLOCK"}
        return "\n".join(
            f"[{prefix.get(check.status, check.status.upper())}] {check.label}: {check.detail}"
            for check in self.checks
        )


class PreflightService:
    """Run non-destructive checks for generation readiness."""

    def check_aria2_capability(self) -> DownloadCapability:
        return DownloadCapability(aria2c_path=shutil.which("aria2c") or "")

    def run(self, project: ProjectDocument, prepared: PreparedInputs | None = None) -> PreflightReport:
        prepared_inputs = prepared or project.state.prepared_inputs
        checks: list[PreflightCheck] = []
        workflow = project.workflow
        environment = project.environment

        checks.append(
            self._check(
                "conda_env",
                "Conda environment",
                bool(environment.conda_env_name.strip()),
                f"Generation will run through: conda activate {environment.conda_env_name.strip() or '<missing>'}.",
                "Set the conda environment name. The packaged WSL2 environment default is 'insar'.",
            )
        )
        checks.append(
            self._check_path("input_path", "Sentinel-1 input folder", workflow.input_path, must_be_dir=True)
        )
        checks.append(self._check_path("orbit_path", "EOF orbit folder", workflow.orbit_path, must_be_dir=True))
        checks.append(self._check_path("dem_path", "DEM path", project.state.prepared_dem_path or workflow.dem_path))

        manifest_ok = bool(prepared_inputs.manifest_path and Path(prepared_inputs.manifest_path).expanduser().is_file())
        checks.append(
            self._check(
                "prepared_manifest",
                "Prepared SAFE manifest",
                manifest_ok,
                prepared_inputs.manifest_path or "No prepared manifest recorded.",
                "Run Validate & Prepare Data before generating stackSentinel.py.",
            )
        )
        entries_ok = bool(prepared_inputs.entries)
        checks.append(
            self._check(
                "prepared_inputs",
                "Prepared Sentinel-1 inputs",
                entries_ok,
                f"{len(prepared_inputs.entries)} prepared input(s).",
                "No prepared ZIP/SAFE entries were recorded.",
            )
        )

        try:
            work_dir = project.resolved_work_dir()
            checks.append(self._check_work_dir(work_dir))
            checks.extend(self._check_generation_conflicts(work_dir))
        except Exception as exc:
            checks.append(
                PreflightCheck(
                    key="work_dir",
                    label="Working directory",
                    status="blocker",
                    detail=str(exc),
                )
            )

        capability = self.check_aria2_capability()
        checks.append(
            PreflightCheck(
                key="aria2c",
                label="aria2c download backend",
                status="ok" if capability.aria2c_available else "warning",
                detail=(
                    f"Found aria2c at {capability.aria2c_path}."
                    if capability.aria2c_available
                    else "aria2c was not found on PATH; SLC downloads require it for multipart resumable transfers."
                ),
            )
        )
        return PreflightReport(checks)

    @staticmethod
    def _check(key: str, label: str, ok: bool, ok_detail: str, fail_detail: str) -> PreflightCheck:
        return PreflightCheck(key=key, label=label, status="ok" if ok else "blocker", detail=ok_detail if ok else fail_detail)

    @staticmethod
    def _check_path(key: str, label: str, path_text: str, *, must_be_dir: bool = False) -> PreflightCheck:
        if not path_text.strip():
            return PreflightCheck(key=key, label=label, status="blocker", detail="Path is not set.")
        path = Path(path_text).expanduser()
        if must_be_dir and not path.is_dir():
            return PreflightCheck(key=key, label=label, status="blocker", detail=f"Directory not found: {path}")
        if not must_be_dir and not path.exists():
            return PreflightCheck(key=key, label=label, status="blocker", detail=f"Path not found: {path}")
        return PreflightCheck(key=key, label=label, status="ok", detail=str(path))

    @staticmethod
    def _check_work_dir(work_dir: Path) -> PreflightCheck:
        path = work_dir.expanduser()
        if path.exists() and not path.is_dir():
            return PreflightCheck("work_dir", "Working directory", "blocker", f"Not a directory: {path}")
        target = path if path.exists() else path.parent
        if not target.exists():
            return PreflightCheck("work_dir", "Working directory", "blocker", f"Parent directory not found: {target}")
        if not os.access(target, os.W_OK):
            return PreflightCheck("work_dir", "Working directory", "blocker", f"Directory is not writable: {target}")
        return PreflightCheck("work_dir", "Working directory", "ok", str(path))

    @staticmethod
    def _check_generation_conflicts(work_dir: Path) -> list[PreflightCheck]:
        checks: list[PreflightCheck] = []
        for name in ("run_files", "configs"):
            path = work_dir / name
            if path.exists():
                checks.append(
                    PreflightCheck(
                        key=f"conflict_{name}",
                        label=f"Existing {name}",
                        status="blocker",
                        detail=f"Workflow generation would overwrite or conflict with existing path: {path}",
                    )
                )
            else:
                checks.append(
                    PreflightCheck(
                        key=f"conflict_{name}",
                        label=f"Existing {name}",
                        status="ok",
                        detail=f"No existing {name} path detected.",
                    )
                )
        return checks
