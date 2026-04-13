"""Run monitor page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from isce2_gui.ui.widgets.summary_card import SummaryCard


class RunMonitorPage(QWidget):
    """Execution monitoring and failure recovery page."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.status_card = SummaryCard("Project Status", "-", "Execution state across run_files.")
        self.current_step_card = SummaryCard("Current Step", "-", "Currently active workflow step.")
        self.work_dir_card = SummaryCard("Work Directory", "-", "Resolved project work directory.")
        cards.addWidget(self.status_card, 1)
        cards.addWidget(self.current_step_card, 1)
        cards.addWidget(self.work_dir_card, 1)
        layout.addLayout(cards)

        button_grid = QGridLayout()
        self.run_next_button = QPushButton("Run Next Step")
        self.run_selected_button = QPushButton("Run Selected Step")
        self.run_all_button = QPushButton("Run Remaining Steps")
        self.stop_button = QPushButton("Stop")
        self.refresh_outputs_button = QPushButton("Refresh Outputs")
        self.run_next_button.setProperty("role", "primary")
        self.run_selected_button.setProperty("role", "secondary")
        self.run_all_button.setProperty("role", "secondary")
        self.stop_button.setProperty("role", "danger")
        self.refresh_outputs_button.setProperty("role", "secondary")
        button_grid.addWidget(self.run_next_button, 0, 0)
        button_grid.addWidget(self.run_selected_button, 0, 1)
        button_grid.addWidget(self.run_all_button, 1, 0)
        button_grid.addWidget(self.stop_button, 1, 1)
        button_grid.addWidget(self.refresh_outputs_button, 2, 0, 1, 2)
        layout.addLayout(button_grid)

        body = QHBoxLayout()
        body.setSpacing(12)

        self.empty_state_label = QLabel(
            "No run files yet. Generate workflow in 'Processing Plan' to populate executable steps."
        )
        self.empty_state_label.setProperty("emptyState", True)
        self.empty_state_label.setWordWrap(True)
        layout.addWidget(self.empty_state_label)

        self.steps_tree = QTreeWidget()
        self.steps_tree.setHeaderLabels(["Step", "Status", "Exit", "Log", "Message"])
        self.steps_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.steps_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        body.addWidget(self.steps_tree, 2)

        detail_col = QVBoxLayout()
        detail_col.setSpacing(10)
        self.command_detail_text = QPlainTextEdit()
        self.command_detail_text.setReadOnly(True)
        self.command_detail_text.setPlaceholderText("Selected step and subcommand details will appear here.")
        detail_col.addWidget(self.command_detail_text, 1)
        self.runfile_estimate_text = QPlainTextEdit()
        self.runfile_estimate_text.setReadOnly(True)
        self.runfile_estimate_text.setPlaceholderText("Run-file command estimates appear here after generation.")
        detail_col.addWidget(self.runfile_estimate_text, 1)
        body.addLayout(detail_col, 1)
        layout.addLayout(body, 1)
