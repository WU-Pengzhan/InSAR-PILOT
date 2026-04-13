"""Compact status badge widget for project and step state."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel


class StatusBadge(QLabel):
    """Small pill-shaped label with semantic tone styling."""

    def __init__(self, text: str = "", tone: str = "neutral", parent=None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(62)
        self.setProperty("badge", True)
        self.set_status(text, tone)

    def set_tone(self, tone: str) -> None:
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_status(self, text: str, tone: str) -> None:
        display_text = text or ""
        self.setText(display_text)
        # Keep badges compact but avoid text clipping.
        metrics = QFontMetrics(self.font())
        target_width = max(self.minimumWidth(), min(220, metrics.horizontalAdvance(display_text) + 18))
        self.setFixedWidth(target_width)
        self.set_tone(tone)
