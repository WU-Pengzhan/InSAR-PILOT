"""Reusable path picker row with optional extra action."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class PathPickerRow(QWidget):
    """Inline picker row used across data and visualization pages."""

    def __init__(
        self,
        browse_label: str = "Browse",
        secondary_label: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.line_edit = QLineEdit()
        layout.addWidget(self.line_edit, 1)

        self.browse_button = QPushButton(browse_label)
        layout.addWidget(self.browse_button)

        self.secondary_button: QPushButton | None = None
        if secondary_label is not None:
            self.secondary_button = QPushButton(secondary_label)
            layout.addWidget(self.secondary_button)
