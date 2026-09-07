"""Download state helpers shared by the page and future coordinator."""

from __future__ import annotations

from dataclasses import dataclass

from insar_pilot.download.models import DownloadResult, DownloadTask

TERMINAL_DOWNLOAD_STATUSES = {"completed", "skipped", "failed", "cancelled"}


@dataclass(frozen=True)
class DownloadRuntimeState:
    """Aggregated state for the Data Acquisition task panel."""

    total_tasks: int = 0
    completed_tasks: int = 0
    running_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    bytes_done: int = 0
    bytes_total: int = 0
    speed_bps: float = 0.0
    eta_seconds: float | None = None
    active_task_id: str = ""
    active_product_type: str = ""
    active_status: str = ""
    active_file: str = ""
    active_backend: str = ""
    active_message: str = ""

    @property
    def percent(self) -> int:
        if self.bytes_total > 0:
            return max(0, min(100, int((self.bytes_done / self.bytes_total) * 100)))
        if self.total_tasks > 0:
            return max(0, min(100, int((self.completed_tasks / self.total_tasks) * 100)))
        return 0


class DownloadStateReducer:
    """Build display-ready download state without owning Qt worker lifetimes."""

    @classmethod
    def from_tasks(cls, tasks: list[DownloadTask], *, active_task: DownloadTask | None = None) -> DownloadRuntimeState:
        selected_active = active_task or cls._active_task(tasks)
        total_tasks = len(tasks)
        completed_tasks = sum(task.status in TERMINAL_DOWNLOAD_STATUSES for task in tasks)
        running_tasks = sum(task.status == "running" for task in tasks)
        failed_tasks = sum(task.status == "failed" for task in tasks)
        cancelled_tasks = sum(task.status == "cancelled" for task in tasks)
        bytes_total = sum(task.bytes_total for task in tasks if task.bytes_total)
        bytes_done = sum(task.bytes_done for task in tasks if task.bytes_done)
        speed_bps = sum(task.speed_bps for task in tasks if task.status == "running")
        eta_seconds = cls._eta(bytes_done, bytes_total, speed_bps)
        return DownloadRuntimeState(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            running_tasks=running_tasks,
            failed_tasks=failed_tasks,
            cancelled_tasks=cancelled_tasks,
            bytes_done=bytes_done,
            bytes_total=bytes_total,
            speed_bps=speed_bps,
            eta_seconds=eta_seconds,
            active_task_id=selected_active.task_id if selected_active else "",
            active_product_type=selected_active.product_type if selected_active else "",
            active_status=selected_active.status if selected_active else "",
            active_file=selected_active.local_path if selected_active else "",
            active_backend=selected_active.backend if selected_active else "",
            active_message=selected_active.message if selected_active else "",
        )

    @classmethod
    def from_results(cls, results: list[DownloadResult]) -> DownloadRuntimeState:
        tasks = [
            DownloadTask(
                task_id=result.task_id,
                scene=result.scene,
                output_dir="",
                product_type=result.product_type,
                status=result.status,
                local_path=result.local_path,
                message=result.message,
                bytes_total=result.bytes_total,
                bytes_done=result.bytes_done,
                speed_bps=result.speed_bps,
                eta_seconds=result.eta_seconds,
                backend=result.backend,
            )
            for result in results
        ]
        return cls.from_tasks(tasks)

    @staticmethod
    def _active_task(tasks: list[DownloadTask]) -> DownloadTask | None:
        for task in reversed(tasks):
            if task.status == "running":
                return task
        return tasks[-1] if tasks else None

    @staticmethod
    def _eta(bytes_done: int, bytes_total: int, speed_bps: float) -> float | None:
        if bytes_total <= 0 or speed_bps <= 0 or bytes_done >= bytes_total:
            return 0.0 if bytes_total > 0 and bytes_done >= bytes_total else None
        return max((bytes_total - bytes_done) / speed_bps, 0.0)
