"""Typed data models for GUI-native Sentinel-1 search and download state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SearchCriteria:
    """User-entered Sentinel-1 search parameters from the GUI."""

    start_date: str
    end_date: str
    aoi_mode: str = "bbox"
    bbox: str = ""
    wkt: str = ""
    aoi_file: str = ""
    platform: str = "SENTINEL-1"
    beam_mode: str = "IW"
    product_type: str = "SLC"
    orbit_direction: str = "ANY"
    relative_orbit: int | None = None
    polarization: str = "ANY"
    max_results: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SearchCriteria:
        """Build criteria from persisted JSON data."""

        data = dict(payload)
        if data.get("relative_orbit") in {"", None}:
            data["relative_orbit"] = None
        elif "relative_orbit" in data:
            data["relative_orbit"] = int(data["relative_orbit"])
        if data.get("max_results") in {"", None}:
            data["max_results"] = None
        elif "max_results" in data:
            data["max_results"] = int(data["max_results"])
        return cls(**data)


@dataclass(frozen=True)
class SceneRecord:
    """One Sentinel-1 scene returned by a provider search."""

    scene_id: str
    acquisition_time: str
    platform: str
    orbit_direction: str
    relative_orbit: int
    polarization: str
    size_mb: float
    coverage_percent: float = 0.0
    status: str = "available"
    local_path: str = ""
    download_url: str = ""
    file_name: str = ""
    footprint_geojson: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SceneRecord:
        """Build a scene record from persisted JSON data."""

        data = dict(payload)
        data["relative_orbit"] = int(data.get("relative_orbit", 0))
        data["size_mb"] = float(data.get("size_mb", 0.0))
        data["coverage_percent"] = float(data.get("coverage_percent", 0.0))
        data.setdefault("download_url", "")
        data.setdefault("file_name", "")
        footprint = data.get("footprint_geojson")
        data["footprint_geojson"] = footprint if isinstance(footprint, dict) else {}
        return cls(**data)

    def with_status(self, status: str, local_path: str | Path | None = None) -> SceneRecord:
        """Return a copy with updated download status and optional local path."""

        data = self.to_dict()
        data["status"] = status
        if local_path is not None:
            data["local_path"] = str(local_path)
        return SceneRecord.from_dict(data)


@dataclass(frozen=True)
class DownloadTask:
    """A planned or running download for one scene."""

    task_id: str
    scene: SceneRecord
    output_dir: str
    product_type: str = "SLC"
    status: str = "pending"
    local_path: str = ""
    message: str = ""
    url: str = ""
    bytes_total: int = 0
    bytes_done: int = 0
    speed_bps: float = 0.0
    eta_seconds: float | None = None
    backend: str = "python"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        data = asdict(self)
        data["scene"] = self.scene.to_dict()
        return data

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DownloadTask:
        """Build a task from persisted JSON data."""

        data = dict(payload)
        data["scene"] = SceneRecord.from_dict(data["scene"])
        data.setdefault("url", "")
        data["bytes_total"] = int(data.get("bytes_total", 0) or 0)
        data["bytes_done"] = int(data.get("bytes_done", 0) or 0)
        data["speed_bps"] = float(data.get("speed_bps", 0.0) or 0.0)
        eta = data.get("eta_seconds")
        data["eta_seconds"] = None if eta is None or eta == "" else float(eta)
        data.setdefault("backend", "python")
        return cls(**data)

    def with_updates(self, **updates: Any) -> DownloadTask:
        """Return a copy of the task with selected fields changed."""

        data = self.to_dict()
        data.update(updates)
        return DownloadTask.from_dict(data)


@dataclass(frozen=True)
class DownloadResult:
    """Final download outcome for one task."""

    task_id: str
    scene: SceneRecord
    product_type: str
    status: str
    local_path: str
    message: str = ""
    bytes_total: int = 0
    bytes_done: int = 0
    speed_bps: float = 0.0
    eta_seconds: float | None = None
    backend: str = "python"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        data = asdict(self)
        data["scene"] = self.scene.to_dict()
        return data

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DownloadResult:
        """Build a result from persisted JSON data."""

        data = dict(payload)
        data["scene"] = SceneRecord.from_dict(data["scene"])
        data["bytes_total"] = int(data.get("bytes_total", 0) or 0)
        data["bytes_done"] = int(data.get("bytes_done", 0) or 0)
        data["speed_bps"] = float(data.get("speed_bps", 0.0) or 0.0)
        eta = data.get("eta_seconds")
        data["eta_seconds"] = None if eta is None or eta == "" else float(eta)
        data.setdefault("backend", "python")
        return cls(**data)


@dataclass(frozen=True)
class DemCoveragePlan:
    """Burst-aware DEM planning result for the standalone workspace."""

    source_id: str
    selected_scene_ids: list[str]
    planned_bbox_snwe: tuple[float, float, float, float] | None
    planning_mode: str
    dem_path: str = ""
    dem_height_reference: str = ""
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DemCoveragePlan:
        """Build a plan from persisted JSON data."""

        data = dict(payload)
        bbox = data.get("planned_bbox_snwe")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            data["planned_bbox_snwe"] = tuple(float(value) for value in bbox)
        else:
            data["planned_bbox_snwe"] = None
        data["selected_scene_ids"] = [str(value) for value in data.get("selected_scene_ids", [])]
        data["warnings"] = [str(value) for value in data.get("warnings", [])]
        data["notes"] = [str(value) for value in data.get("notes", [])]
        return cls(**data)
