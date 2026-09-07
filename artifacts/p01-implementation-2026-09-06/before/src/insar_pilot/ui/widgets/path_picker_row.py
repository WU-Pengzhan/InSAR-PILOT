"""Reusable path picker row with optional extra action."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLineEdit, QPushButton, QWidget

from insar_pilot.i18n import tr


class PathPickerRow(QWidget):
    """Inline picker row used across data and visualization pages."""

    def __init__(
        self,
        browse_label: str | None = None,
        secondary_label: str | None = None,
        *,
        compact: bool = False,
        stacked: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if browse_label is None:
            browse_label = tr("widget.browse")
        control_height = 34 if compact else 40
        row_height = 36 if compact else 42
        layout = QGridLayout(self) if stacked else QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6 if compact else 8)

        self.line_edit = QLineEdit()
        self.line_edit.setMinimumHeight(control_height)
        if stacked:
            layout.addWidget(self.line_edit, 0, 0, 1, 3)
            layout.setColumnStretch(0, 1)
        else:
            layout.addWidget(self.line_edit, 1)

        self.browse_button = QPushButton(browse_label)
        self.browse_button.setMinimumHeight(control_height)
        self.browse_button.setFixedWidth(80 if compact else 96)
        if stacked:
            layout.addWidget(self.browse_button, 1, 1)
        else:
            layout.addWidget(self.browse_button)

        self.secondary_button: QPushButton | None = None
        if secondary_label is not None:
            self.secondary_button = QPushButton(secondary_label)
            self.secondary_button.setMinimumHeight(control_height)
            self.secondary_button.setMinimumWidth(132 if compact else 156)
            if stacked:
                layout.addWidget(self.secondary_button, 1, 2)
            else:
                layout.addWidget(self.secondary_button)
        self.setMinimumHeight(row_height * (2 if stacked else 1))
