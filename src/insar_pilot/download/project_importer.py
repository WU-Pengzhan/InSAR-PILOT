"""Optional bridge from downloaded scenes into an ISCE project directory."""

from __future__ import annotations

import json
from pathlib import Path

from insar_pilot.download.models import SceneRecord


def import_downloads_to_project(
    project_dir: str | Path,
    scenes: list[SceneRecord],
    orbit_dir: str | Path | None = None,
    dem_path: str | Path | None = None,
) -> Path:
    """Write a placeholder project import configuration.

    The GUI MVP does not call this function automatically. It is a future bridge
    for explicit handoff from the standalone download workspace to an ISCE
    project.
    """

    root = Path(project_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "project_config.json"
    payload = {
        "sentinel_1_downloads": [scene.to_dict() for scene in scenes],
        "orbit_dir": str(Path(orbit_dir).expanduser()) if orbit_dir else "",
        "dem_path": str(Path(dem_path).expanduser()) if dem_path else "",
        "status": "placeholder",
    }
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return config_path
