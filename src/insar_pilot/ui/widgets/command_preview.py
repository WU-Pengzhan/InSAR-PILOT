"""Command preview surface."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPlainTextEdit, QVBoxLayout


class CommandPreview(QFrame):
    """Show generated command text with contextual metadata."""

    def __init__(self, title: str = "stackSentinel.py Command Preview", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("commandPreview")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("sectionPanelTitle")
        self.meta_label = QLabel("Work directory, log path, and command text will appear before generation.")
        self.meta_label.setObjectName("summaryCardBody")
        self.meta_label.setWordWrap(True)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText("Generated stackSentinel.py command will appear here.")
        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.text_edit, 1)

    def set_metadata(self, text: str) -> None:
        self.meta_label.setText(text)

    def setPlainText(self, text: str) -> None:  # noqa: N802 - compatibility with QPlainTextEdit call sites
        self.text_edit.setPlainText(text)

    def toPlainText(self) -> str:  # noqa: N802 - compatibility
        return self.text_edit.toPlainText()

    def clear(self) -> None:
        self.text_edit.clear()
