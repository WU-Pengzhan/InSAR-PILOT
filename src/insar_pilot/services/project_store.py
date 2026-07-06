"""Save and load persistent GUI project state."""

from __future__ import annotations

import json
from json import JSONDecodeError
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from insar_pilot.domain.project import (
    APP_METADATA_DIR,
    LEGACY_APP_METADATA_DIR,
    LEGACY_APP_METADATA_DIRS,
    LEGACY_PROJECT_ROOT_FILE_NAMES,
    PROJECT_FILE_NAME,
    PROJECT_ROOT_FILE_NAME,
    DataDownloadConfig,
    ProjectWorkspace,
    ProjectDocument,
    WorkflowConfig,
)


class ProjectLoadError(ValueError):
    """Raised when a project file cannot be trusted or parsed."""


class ProjectStore:
    """Persist the project inside the selected working directory."""

    CURRENT_SCHEMA_VERSION = 1
    MAX_PROJECT_FILE_BYTES = 8 * 1024 * 1024
    _KNOWN_SECTIONS = {
        "workspace",
        "environment",
        "workflow",
        "download",
        "visualization",
        "state",
    }

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
        payload = self._read_project_payload(project_file)
        try:
            project = ProjectDocument.from_dict(payload)
        except (TypeError, ValueError) as exc:
            raise ProjectLoadError(f"Project file is malformed or incompatible: {project_file}") from exc
        if project_file.name == PROJECT_ROOT_FILE_NAME and not project.workspace.configured:
            project.workspace = ProjectWorkspace(project_root=str(project_file.parent))
        return project

    @staticmethod
    def resolve_project_file(path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        if candidate.is_dir():
            if candidate.name in {APP_METADATA_DIR, LEGACY_APP_METADATA_DIR, *LEGACY_APP_METADATA_DIRS}:
                candidate = candidate / PROJECT_FILE_NAME
            else:
                root_project = candidate / PROJECT_ROOT_FILE_NAME
                legacy_root_projects = [candidate / name for name in LEGACY_PROJECT_ROOT_FILE_NAMES]
                current = candidate / APP_METADATA_DIR / PROJECT_FILE_NAME
                legacy_metadata_projects = [candidate / name / PROJECT_FILE_NAME for name in LEGACY_APP_METADATA_DIRS]
                if root_project.exists():
                    candidate = root_project
                elif any(path.exists() for path in legacy_root_projects):
                    candidate = next(path for path in legacy_root_projects if path.exists())
                elif current.exists():
                    candidate = current
                elif any(path.exists() for path in legacy_metadata_projects):
                    candidate = next(path for path in legacy_metadata_projects if path.exists())
                else:
                    candidate = root_project
        return candidate

    def _read_project_payload(self, project_file: Path) -> dict[str, Any]:
        if not project_file.exists():
            raise ProjectLoadError(f"Project file was not found: {project_file}")
        if not project_file.is_file():
            raise ProjectLoadError(f"Project path is not a file: {project_file}")
        if project_file.stat().st_size > self.MAX_PROJECT_FILE_BYTES:
            raise ProjectLoadError(
                f"Project file is too large to open safely: {project_file} "
                f"({project_file.stat().st_size} bytes)"
            )

        try:
            text = project_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProjectLoadError(f"Project file could not be read: {project_file}") from exc

        try:
            payload = json.loads(text)
        except JSONDecodeError as exc:
            raise ProjectLoadError(f"Project file is not valid JSON: {project_file}") from exc

        if not isinstance(payload, dict):
            raise ProjectLoadError("Project file must contain a JSON object.")
        self._validate_payload(payload)
        return payload

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        schema_version = payload.get("schema_version", 1)
        try:
            schema_version = int(schema_version)
        except (TypeError, ValueError) as exc:
            raise ProjectLoadError("Project schema_version must be an integer.") from exc
        if schema_version < 1 or schema_version > self.CURRENT_SCHEMA_VERSION:
            raise ProjectLoadError(
                f"Unsupported project schema_version {schema_version}; "
                f"this application supports up to {self.CURRENT_SCHEMA_VERSION}."
            )

        if not any(section in payload for section in self._KNOWN_SECTIONS):
            raise ProjectLoadError("This file does not look like an InSAR-PILOT project.")

        for section in self._KNOWN_SECTIONS:
            value = payload.get(section)
            if value is not None and not isinstance(value, dict):
                raise ProjectLoadError(f"Project section '{section}' must be a JSON object.")

        workspace = payload.get("workspace")
        if isinstance(workspace, dict):
            project_root = workspace.get("project_root")
            if project_root is not None and not isinstance(project_root, str):
                raise ProjectLoadError("Project workspace.project_root must be a string.")

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
