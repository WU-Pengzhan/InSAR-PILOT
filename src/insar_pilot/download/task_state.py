"""Pure helpers for download task bookkeeping and result construction.

These functions are Qt-free and side-effect-free; they translate ``DownloadTask``
state into ``DownloadResult`` records and compute progress telemetry (speed/ETA).
"""

from __future__ import annotations

import time
from pathlib import Path

from insar_pilot.download.models import DownloadResult, DownloadTask, SceneRecord


def slc_path(output_dir: Path, scene: SceneRecord) -> Path:
    """Return the canonical on-disk SLC zip path for a scene."""

    file_name = scene.file_name or f"{scene.scene_id}.zip"
    if not file_name.lower().endswith(".zip"):
        file_name = f"{file_name}.zip"
    return output_dir / "SLC" / file_name


def result_from_task(task: DownloadTask, *, scene: SceneRecord | None = None) -> DownloadResult:
    """Snapshot a task's current state into an immutable ``DownloadResult``."""

    return DownloadResult(
        task_id=task.task_id,
        scene=scene or task.scene,
        product_type=task.product_type,
        status=task.status,
        local_path=task.local_path,
        message=task.message,
        bytes_total=task.bytes_total,
        bytes_done=task.bytes_done,
        speed_bps=task.speed_bps,
        eta_seconds=task.eta_seconds,
        backend=task.backend,
    )


def is_retryable_slc_failure(result: DownloadResult) -> bool:
    """Return True when an SLC failure is worth retrying (transient, not fatal)."""

    if result.product_type.upper() != "SLC" or result.status != "failed":
        return False
    message = result.message.lower()
    return "aria2c is required" not in message and "no asf download url" not in message


def speed_bps(bytes_done: int, started: float) -> float:
    """Compute average download speed in bytes/second since ``started``."""

    elapsed = max(time.monotonic() - started, 0.001)
    return float(bytes_done) / elapsed


def eta_seconds(bytes_done: int, bytes_total: int, speed_bps: float) -> float | None:
    """Estimate remaining seconds; ``None`` when the total is unknown."""

    if bytes_total <= 0 or speed_bps <= 0 or bytes_done >= bytes_total:
        return 0.0 if bytes_total > 0 and bytes_done >= bytes_total else None
    return max((bytes_total - bytes_done) / speed_bps, 0.0)
