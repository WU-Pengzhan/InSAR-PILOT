"""Selection and download action controls plus the task progress panel."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton

from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.pages.data_download.base import DownloadSection
from insar_pilot.ui.widgets.task_progress_panel import TaskProgressPanel


class ActionsSection(DownloadSection):
    """Scene selection, download, workspace, and task-progress controls."""

    def __init__(self, parent=None) -> None:
        super().__init__("Selection and Download", parent, expanded=True)
        self.select_all_button = QPushButton("Select All")
        self.select_none_button = QPushButton("Select None")
        self.save_selected_button = QPushButton("Save Selection")
        self.download_selected_button = QPushButton("Download Selected")
        self.cancel_download_button = QPushButton("Cancel Download")
        self.use_as_sources_button = QPushButton("Use as Data Sources")
        self.open_workspace_button = QPushButton("Open Workspace")
        self.select_all_button.setIcon(IconProvider.icon("check"))
        self.select_none_button.setIcon(IconProvider.icon("cancel", "muted"))
        self.save_selected_button.setIcon(IconProvider.icon("save"))
        self.download_selected_button.setIcon(IconProvider.icon("download"))
        self.cancel_download_button.setIcon(IconProvider.icon("cancel", "error"))
        self.use_as_sources_button.setIcon(IconProvider.icon("import"))
        self.open_workspace_button.setIcon(IconProvider.icon("folder"))
        self.select_all_button.setProperty("role", "secondary")
        self.select_none_button.setProperty("role", "secondary")
        self.save_selected_button.setProperty("role", "secondary")
        self.cancel_download_button.setProperty("role", "danger")
        self.use_as_sources_button.setProperty("role", "secondary")
        self.open_workspace_button.setProperty("role", "secondary")
        self.download_selected_button.setProperty("role", "primary")
        self.cancel_download_button.setEnabled(False)
        self.selection_label = QLabel("0 selected")
        self.selection_label.setObjectName("summaryCardTitle")
        self.content_layout.addWidget(self.selection_label)
        selection_row = QHBoxLayout()
        selection_row.setSpacing(8)
        selection_row.addWidget(self.select_all_button, 1)
        selection_row.addWidget(self.select_none_button, 1)
        self.content_layout.addLayout(selection_row)
        save_row = QHBoxLayout()
        save_row.setSpacing(8)
        save_row.addWidget(self.save_selected_button, 1)
        save_row.addWidget(self.open_workspace_button, 1)
        self.content_layout.addLayout(save_row)
        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        source_row.addWidget(self.use_as_sources_button, 1)
        self.content_layout.addLayout(source_row)
        download_row = QHBoxLayout()
        download_row.setSpacing(8)
        download_row.addWidget(self.download_selected_button, 1)
        download_row.addWidget(self.cancel_download_button, 1)
        self.content_layout.addLayout(download_row)

        self.task_progress_panel = TaskProgressPanel()
        self.download_progress_bar = self.task_progress_panel.progress_bar
        self.download_status_label = self.task_progress_panel.status_label
        self.content_layout.addWidget(self.task_progress_panel)
