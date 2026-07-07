"""Sentinel-1 EOF precise-orbit download service (sentineleof-backed)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from insar_pilot.download.models import DownloadResult, DownloadTask, SceneRecord
from insar_pilot.download.task_state import result_from_task

ProgressCallback = Callable[[DownloadTask], None]
CancelCheck = Callable[[], bool]


class OrbitDownloadService:
    """Download Sentinel-1 EOF orbit files using sentineleof."""

    def download(
        self,
        task: DownloadTask,
        *,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> DownloadResult:
        orbit_dir = Path(task.output_dir).expanduser() / "Orbit"
        orbit_dir.mkdir(parents=True, exist_ok=True)
        existing = self._existing_orbit_file(orbit_dir, task.scene)
        if existing is not None:
            skipped = task.with_updates(
                status="skipped",
                local_path=str(existing),
                message="Orbit file already exists; skipped.",
            )
            if progress_callback:
                progress_callback(skipped)
            return result_from_task(skipped)

        if cancel_check and cancel_check():
            cancelled = task.with_updates(status="cancelled", message="Download cancelled.")
            if progress_callback:
                progress_callback(cancelled)
            return result_from_task(cancelled)

        running = task.with_updates(status="running", local_path=str(orbit_dir), message="Downloading orbit file...")
        if progress_callback:
            progress_callback(running)

        before = set(orbit_dir.glob("*.EOF"))
        try:
            download_eofs = self._download_eofs_function()
            sentinel_file = self._sentinel_file_for_task(task)
            if sentinel_file and Path(sentinel_file).exists():
                download_eofs(
                    sentinel_file=sentinel_file,
                    save_dir=str(orbit_dir),
                    orbit_type="precise",
                    force_asf=True,
                )
            else:
                download_eofs(
                    [self._scene_datetime(task.scene)],
                    [self._mission(task.scene)],
                    save_dir=str(orbit_dir),
                    orbit_type="precise",
                    force_asf=True,
                )
        except Exception as exc:
            failed = task.with_updates(
                status="failed", local_path=str(orbit_dir), message=f"Orbit download failed: {exc}"
            )
            if progress_callback:
                progress_callback(failed)
            return result_from_task(failed)

        orbit_path = self._new_or_existing_orbit(orbit_dir, task.scene, before)
        if orbit_path is None:
            failed = task.with_updates(
                status="failed", local_path=str(orbit_dir), message="Orbit downloader returned no EOF file."
            )
            if progress_callback:
                progress_callback(failed)
            return result_from_task(failed)

        completed = task.with_updates(
            status="completed",
            local_path=str(orbit_path),
            bytes_total=orbit_path.stat().st_size,
            bytes_done=orbit_path.stat().st_size,
            message="Orbit download completed.",
        )
        if progress_callback:
            progress_callback(completed)
        return result_from_task(completed)

    @staticmethod
    def _download_eofs_function() -> Callable[..., Any]:
        try:
            from eof.download import download_eofs
        except Exception as exc:
            raise RuntimeError("sentineleof is required for orbit downloads. Install sentineleof>=0.11.1.") from exc
        return cast(Callable[..., Any], download_eofs)

    @staticmethod
    def _mission(scene: SceneRecord) -> str:
        scene_text = (scene.scene_id or scene.file_name or scene.platform).upper()
        if "S1C" in scene_text or "SENTINEL-1C" in scene.platform.upper():
            return "S1C"
        if "S1B" in scene_text or "SENTINEL-1B" in scene.platform.upper():
            return "S1B"
        return "S1A"

    @staticmethod
    def _scene_datetime(scene: SceneRecord) -> datetime:
        text = scene.acquisition_time.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            for token in (scene.scene_id or scene.file_name).split("_"):
                if len(token) == 15 and token[8] == "T":
                    return datetime.strptime(token, "%Y%m%dT%H%M%S")
        raise ValueError(f"Could not determine acquisition time for {scene.scene_id}")

    @staticmethod
    def _sentinel_file_for_task(task: DownloadTask) -> str:
        slc_name = task.scene.file_name or f"{task.scene.scene_id}.zip"
        if not slc_name.lower().endswith(".zip"):
            slc_name = f"{slc_name}.zip"
        slc_path = Path(task.output_dir).expanduser() / "SLC" / slc_name
        return str(slc_path)

    @classmethod
    def _existing_orbit_file(cls, orbit_dir: Path, scene: SceneRecord) -> Path | None:
        mission = cls._mission(scene)
        try:
            acquisition = cls._scene_datetime(scene)
        except ValueError:
            acquisition = None
        for path in sorted(orbit_dir.glob(f"{mission}_OPER_AUX_*ORB_*.EOF")):
            if acquisition is None or cls._orbit_name_matches(path.name, acquisition):
                return path
        return None

    @classmethod
    def _new_or_existing_orbit(cls, orbit_dir: Path, scene: SceneRecord, before: set[Path]) -> Path | None:
        created = sorted(set(orbit_dir.glob("*.EOF")) - before)
        if created:
            return created[-1]
        return cls._existing_orbit_file(orbit_dir, scene)

    @staticmethod
    def _orbit_name_matches(name: str, acquisition: datetime) -> bool:
        parts = name.split("_")
        start_text = ""
        stop_text = ""
        for index, part in enumerate(parts):
            if part.startswith("V") and len(part) >= 16 and index + 1 < len(parts):
                start_text = part[1:16]
                stop_text = parts[index + 1][:15]
                break
        if not start_text or not stop_text:
            return False
        try:
            start = datetime.strptime(start_text, "%Y%m%dT%H%M%S")
            stop = datetime.strptime(stop_text, "%Y%m%dT%H%M%S")
        except ValueError:
            return False
        naive_acquisition = acquisition.replace(tzinfo=None)
        return start <= naive_acquisition <= stop
