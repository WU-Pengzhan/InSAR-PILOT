"""Build official topsStack commands and track generated run files."""

from __future__ import annotations

import shlex
from pathlib import Path

from insar_pilot.domain.project import PreparedInputs, ProjectDocument, ProjectStatus, RunStep, StepStatus


class StackWorkflowService:
    """Manage stackSentinel.py generation and run-file discovery."""

    def ensure_generation_allowed(self, project: ProjectDocument) -> None:
        work_dir = project.resolved_work_dir()
        blocked = [work_dir / "run_files", work_dir / "configs"]
        existing = [path for path in blocked if path.exists()]
        if existing:
            joined = ", ".join(str(path) for path in existing)
            raise FileExistsError(
                f"Workflow generation was blocked because these paths already exist: {joined}"
            )

    def resolve_aux_dir(self, project: ProjectDocument, prepared: PreparedInputs) -> Path:
        aux_path = project.workflow.aux_path.strip()
        if aux_path:
            return Path(aux_path).expanduser()
        if prepared.aux_required:
            raise ValueError(
                "AUX_CAL is required because at least one input uses IPF version 002.36."
            )

        aux_dir = project.metadata_dir() / "aux_empty"
        aux_dir.mkdir(parents=True, exist_ok=True)
        return aux_dir

    def build_generate_command(
        self,
        project: ProjectDocument,
        prepared: PreparedInputs,
        dem_path: str | None = None,
    ) -> str:
        self.ensure_generation_allowed(project)
        aux_dir = self.resolve_aux_dir(project, prepared)
        workflow = project.workflow
        bbox = workflow.normalized_bbox()
        resolved_dem_path = dem_path or workflow.dem_path

        args: list[str] = [
            "stackSentinel.py",
            "-s",
            prepared.manifest_path,
            "-o",
            workflow.orbit_path,
            "-a",
            str(aux_dir),
            "-d",
            resolved_dem_path,
            "-w",
            str(project.resolved_work_dir()),
            "-W",
            workflow.workflow,
            "-C",
            workflow.coregistration,
            "-c",
            str(workflow.num_connections),
            "-z",
            str(workflow.azimuth_looks),
            "-r",
            str(workflow.range_looks),
            "-n",
            workflow.swath_numbers,
            "-p",
            workflow.polarization,
            "--num_proc",
            str(workflow.num_proc),
        ]
        if bbox:
            args.extend(["-b", bbox])
        if workflow.reference_date.strip():
            args.extend(["-m", workflow.reference_date.strip()])

        return " ".join(shlex.quote(value) for value in args)

    @staticmethod
    def discover_run_files(work_dir: Path) -> list[Path]:
        run_dir = work_dir / "run_files"
        if not run_dir.is_dir():
            return []
        return sorted(path for path in run_dir.iterdir() if path.is_file() and path.name.startswith("run_"))

    def synchronize_project_steps(self, project: ProjectDocument) -> list[RunStep]:
        run_files = self.discover_run_files(project.resolved_work_dir())
        project.synchronize_steps(run_files)
        if run_files:
            project.state.status = ProjectStatus.GENERATED
        return project.state.steps

    @staticmethod
    def step_command(step: RunStep) -> str:
        return f"bash {shlex.quote(step.path)}"

    @staticmethod
    def next_runnable_step(project: ProjectDocument) -> RunStep | None:
        for step in project.state.steps:
            if step.status in {StepStatus.PENDING, StepStatus.FAILED, StepStatus.CANCELLED}:
                return step
        return None

    @staticmethod
    def remaining_steps(project: ProjectDocument) -> list[RunStep]:
        return [
            step
            for step in project.state.steps
            if step.status in {StepStatus.PENDING, StepStatus.FAILED, StepStatus.CANCELLED}
        ]
