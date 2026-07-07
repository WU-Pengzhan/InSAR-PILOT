"""Reusable preview image panel with metadata text."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget

from insar_pilot.i18n import tr


class PreviewPanel(QWidget):
    """Image preview area with scroll support and metadata panel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.image_label = QLabel(tr("results.preview.none"))
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.image_label.setMinimumSize(480, 320)
        self.image_label.setScaledContents(False)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area, 1)

        self.meta_text = QPlainTextEdit()
        self.meta_text.setReadOnly(True)
        self.meta_text.setPlaceholderText(tr("widget.preview.meta_placeholder"))
        layout.addWidget(self.meta_text)
