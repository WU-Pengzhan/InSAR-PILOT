"""Collapsible diagnostics panel for paths, commands, and raw logs."""

from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit

from insar_pilot.ui.widgets.collapsible_section import CollapsibleSection


class TechnicalDetailsPanel(CollapsibleSection):
    """Collapsed-by-default technical details for advanced operators."""

    def __init__(self, title: str = "Technical Details", parent=None) -> None:
        super().__init__(title, expanded=False, parent=parent)
        self.setObjectName("technicalDetailsPanel")
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlaceholderText("Commands, paths, run_files, and diagnostics appear here.")
        self.text.setMaximumHeight(180)
        self.content_layout.addWidget(self.text)

    def setPlainText(self, text: str) -> None:  # noqa: N802 - Qt compatibility style
        self.text.setPlainText(text)

    def toPlainText(self) -> str:  # noqa: N802 - Qt compatibility style
        return self.text.toPlainText()

    def appendPlainText(self, text: str) -> None:  # noqa: N802 - Qt compatibility style
        self.text.appendPlainText(text)
