"""JSON persistence for GUI-native Sentinel-1 download state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from insar_pilot.download.models import DemCoveragePlan, DownloadTask, SceneRecord


class DownloadStorage:
    """Store search, selection, and task state below a user-selected directory."""

    SEARCH_RESULTS = "search_results.json"
    SELECTED_SCENES = "selected_scenes.json"
    DOWNLOAD_TASKS = "download_tasks.json"
    DEM_PLAN = "dem_plan.json"

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir).expanduser()

    def save_search_results(self, scenes: list[SceneRecord]) -> Path:
        """Persist provider search results."""

        return self._write(self.SEARCH_RESULTS, [scene.to_dict() for scene in scenes])

    def load_search_results(self) -> list[SceneRecord]:
        """Load persisted search results."""

        return [SceneRecord.from_dict(item) for item in self._read_list(self.SEARCH_RESULTS)]

    def save_selected_scenes(self, scenes: list[SceneRecord]) -> Path:
        """Persist the user's selected scenes."""

        return self._write(self.SELECTED_SCENES, [scene.to_dict() for scene in scenes])

    def load_selected_scenes(self) -> list[SceneRecord]:
        """Load persisted selected scenes."""

        return [SceneRecord.from_dict(item) for item in self._read_list(self.SELECTED_SCENES)]

    def save_download_tasks(self, tasks: list[DownloadTask]) -> Path:
        """Persist download task records."""

        return self._write(self.DOWNLOAD_TASKS, [task.to_dict() for task in tasks])

    def load_download_tasks(self) -> list[DownloadTask]:
        """Load persisted download task records."""

        return [DownloadTask.from_dict(item) for item in self._read_list(self.DOWNLOAD_TASKS)]

    def save_dem_plan(self, plan: DemCoveragePlan) -> Path:
        """Persist the current DEM planning result."""

        return self._write(self.DEM_PLAN, plan.to_dict())

    def load_dem_plan(self) -> DemCoveragePlan | None:
        """Load the persisted DEM planning result, if any."""

        payload = self._read_object(self.DEM_PLAN)
        if payload is None:
            return None
        return DemCoveragePlan.from_dict(payload)

    def _write(self, filename: str, payload: Any) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _read_list(self, filename: str) -> list[dict[str, Any]]:
        path = self.output_dir / filename
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected a JSON list in {path}")
        return payload

    def _read_object(self, filename: str) -> dict[str, Any] | None:
        path = self.output_dir / filename
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object in {path}")
        return payload
