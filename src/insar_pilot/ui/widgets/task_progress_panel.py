"""Download task progress panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QProgressBar, QVBoxLayout

from insar_pilot.controllers.download_coordinator import DownloadRuntimeState


class TaskProgressPanel(QFrame):
    """Compact, scan-friendly display for current and total download progress."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("taskProgressPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("No active download.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        self.current_file_label = QLabel("-")
        self.total_label = QLabel("0/0 tasks")
        self.speed_label = QLabel("-")
        self.eta_label = QLabel("-")
        self.backend_label = QLabel("-")
        for row, (title, value) in enumerate(
            (
                ("Current file", self.current_file_label),
                ("Total", self.total_label),
                ("Speed", self.speed_label),
                ("ETA", self.eta_label),
                ("Backend", self.backend_label),
            )
        ):
            title_label = QLabel(title)
            title_label.setObjectName("summaryCardTitle")
            grid.addWidget(title_label, row, 0)
            value.setWordWrap(True)
            grid.addWidget(value, row, 1)
        layout.addLayout(grid)

    def reset(self) -> None:
        self.progress_bar.setValue(0)
        self.status_label.setText("No active download.")
        self.current_file_label.setText("-")
        self.total_label.setText("0/0 tasks")
        self.speed_label.setText("-")
        self.eta_label.setText("-")
        self.backend_label.setText("-")

    def apply_state(self, state: DownloadRuntimeState) -> None:
        self.progress_bar.setValue(state.percent)
        if state.active_task_id:
            headline = (
                f"{state.active_product_type}: {state.active_status} "
                f"({state.completed_tasks}/{state.total_tasks})"
            )
            if state.active_message:
                headline += f"\n{state.active_message}"
            self.status_label.setText(headline)
        else:
            self.status_label.setText("No active download.")
        self.current_file_label.setText(self._short_path(state.active_file))
        self.total_label.setText(
            f"{state.completed_tasks}/{state.total_tasks} tasks"
            + (f", {state.failed_tasks} failed" if state.failed_tasks else "")
            + (f", {state.cancelled_tasks} cancelled" if state.cancelled_tasks else "")
        )
        self.speed_label.setText(f"{self._format_bytes(state.speed_bps)}/s" if state.speed_bps > 0 else "-")
        self.eta_label.setText(self._format_duration(state.eta_seconds) if state.eta_seconds is not None else "-")
        self.backend_label.setText(state.active_backend or "-")

    @staticmethod
    def _short_path(path_text: str) -> str:
        if not path_text:
            return "-"
        path = Path(path_text)
        parent = path.parent.name
        return f"{parent}/{path.name}" if parent else path.name

    @staticmethod
    def _format_bytes(value: float | int) -> str:
        size = float(value or 0)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size) < 1024.0 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{size:.1f} TB"

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
        if seconds is None:
            return "-"
        seconds = max(int(seconds), 0)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes:02d}m"
        if minutes:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"
