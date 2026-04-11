"""Save and load persistent GUI project state."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from isce2_gui.domain.project import APP_METADATA_DIR, PROJECT_FILE_NAME, ProjectDocument


class ProjectStore:
    """Persist the project inside the selected working directory."""

    def save(self, project: ProjectDocument) -> Path:
        metadata_dir = project.metadata_dir()
        metadata_dir.mkdir(parents=True, exist_ok=True)
        project.logs_dir().mkdir(parents=True, exist_ok=True)
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
            if candidate.name == APP_METADATA_DIR:
                candidate = candidate / PROJECT_FILE_NAME
            else:
                candidate = candidate / APP_METADATA_DIR / PROJECT_FILE_NAME
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
