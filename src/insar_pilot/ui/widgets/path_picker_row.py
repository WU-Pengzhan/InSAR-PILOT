"""Reusable path picker row with optional extra action."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class PathPickerRow(QWidget):
    """Inline picker row used across data and visualization pages."""

    def __init__(
        self,
        browse_label: str = "Browse",
        secondary_label: str | None = None,
        *,
        compact: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        control_height = 34 if compact else 40
        row_height = 36 if compact else 42
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.line_edit = QLineEdit()
        self.line_edit.setMinimumHeight(control_height)
        layout.addWidget(self.line_edit, 1)

        self.browse_button = QPushButton(browse_label)
        self.browse_button.setMinimumHeight(control_height)
        self.browse_button.setFixedWidth(96)
        layout.addWidget(self.browse_button)

        self.secondary_button: QPushButton | None = None
        if secondary_label is not None:
            self.secondary_button = QPushButton(secondary_label)
            self.secondary_button.setMinimumHeight(control_height)
            self.secondary_button.setMinimumWidth(156)
            layout.addWidget(self.secondary_button)
        self.setMinimumHeight(row_height)
