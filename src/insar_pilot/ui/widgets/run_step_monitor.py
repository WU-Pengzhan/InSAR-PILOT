"""Run-file step monitor widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QPlainTextEdit,
    QSplitter,
    QTreeWidget,
    QVBoxLayout,
)


class RunStepMonitor(QFrame):
    """Execution dashboard for run_files and subcommands."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("runStepMonitor")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.steps_tree = QTreeWidget()
        self.steps_tree.setObjectName("runFilesTree")
        self.steps_tree.setHeaderLabels(["Step", "Status", "Exit", "Log", "Message"])
        self.steps_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.steps_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.steps_tree.setAlternatingRowColors(True)
        self.steps_tree.setUniformRowHeights(True)
        self.splitter.addWidget(self.steps_tree)

        detail = QFrame()
        detail.setObjectName("runDetailPanel")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(6)
        self.command_detail_text = QPlainTextEdit()
        self.command_detail_text.setReadOnly(True)
        self.command_detail_text.setPlaceholderText("Selected step and subcommand details will appear here.")
        self.runfile_estimate_text = QPlainTextEdit()
        self.runfile_estimate_text.setReadOnly(True)
        self.runfile_estimate_text.setPlaceholderText("Run-file command estimates appear here after generation.")
        detail_layout.addWidget(self.command_detail_text, 2)
        detail_layout.addWidget(self.runfile_estimate_text, 1)
        self.splitter.addWidget(detail)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter, 1)
