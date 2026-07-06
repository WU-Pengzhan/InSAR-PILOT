"""Save and load persistent GUI project state."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from insar_pilot.domain.project import (
    APP_METADATA_DIR,
    LEGACY_APP_METADATA_DIR,
    PROJECT_FILE_NAME,
    PROJECT_ROOT_FILE_NAME,
    DataDownloadConfig,
    ProjectWorkspace,
    ProjectDocument,
    WorkflowConfig,
)


class ProjectStore:
    """Persist the project inside the selected working directory."""

    def create_workspace(self, root: str | Path) -> ProjectDocument:
        """Create the product project folder layout and return a configured project."""

        project = ProjectDocument(workspace=ProjectWorkspace(project_root=str(Path(root).expanduser())))
        workspace = project.workspace
        for path in (
            workspace.slc_dir(),
            workspace.orbit_dir(),
            workspace.dem_dir(),
            workspace.processing_work_dir(),
            workspace.quicklook_dir(),
            workspace.logs_dir(),
            workspace.cache_dir(),
        ):
            path.mkdir(parents=True, exist_ok=True)

        project.workflow = WorkflowConfig(
            input_path=str(workspace.slc_dir()),
            orbit_path=str(workspace.orbit_dir()),
            dem_path="",
            work_dir=str(workspace.processing_work_dir()),
        )
        project.download = DataDownloadConfig(
            output_dir=str(workspace.root_path() / "data"),
            include_orbits=True,
            last_status="ready",
            last_message="Project workspace is ready for Sentinel-1 data acquisition.",
        )
        self.save(project)
        return project

    def save(self, project: ProjectDocument) -> Path:
        metadata_dir = project.metadata_dir()
        metadata_dir.mkdir(parents=True, exist_ok=True)
        project.logs_dir().mkdir(parents=True, exist_ok=True)
        if project.workspace.configured:
            for path in (
                project.workspace.slc_dir(),
                project.workspace.orbit_dir(),
                project.workspace.dem_dir(),
                project.workspace.processing_work_dir(),
                project.workspace.quicklook_dir(),
                project.workspace.cache_dir(),
            ):
                path.mkdir(parents=True, exist_ok=True)
        target = project.project_file()
        target.write_text(json.dumps(self._serialize(project), indent=2), encoding="utf-8")
        return target

    def load(self, path: str | Path) -> ProjectDocument:
        project_file = self.resolve_project_file(path)
        payload = json.loads(project_file.read_text(encoding="utf-8"))
        return ProjectDocument.from_dict(payload)

    @staticmethod
    def resolve_project_file(path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        if candidate.is_dir():
            if candidate.name in {APP_METADATA_DIR, LEGACY_APP_METADATA_DIR}:
                candidate = candidate / PROJECT_FILE_NAME
            else:
                root_project = candidate / PROJECT_ROOT_FILE_NAME
                current = candidate / APP_METADATA_DIR / PROJECT_FILE_NAME
                legacy = candidate / LEGACY_APP_METADATA_DIR / PROJECT_FILE_NAME
                if root_project.exists():
                    candidate = root_project
                else:
                    candidate = current if current.exists() or not legacy.exists() else legacy
        return candidate

    def _serialize(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Path):
            return str(value)
        if is_dataclass(value):
            return {
                field.name: self._serialize(getattr(value, field.name))
                for field in fields(value)
            }
        if isinstance(value, list):
            return [self._serialize(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize(item) for key, item in value.items()}
        return value
