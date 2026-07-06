"""Readable GIS-style property form used on setup pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QWidget


class PropertyForm(QFrame):
    """Two-column parameter form with breathing room between rows."""

    LABEL_WIDTH = 180
    ROW_HEIGHT = 44
    EDITOR_HEIGHT = 40

    def __init__(self, title: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("propertyForm")
        self._row = 0
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setHorizontalSpacing(10)
        self.layout.setVerticalSpacing(8)
        self.layout.setColumnMinimumWidth(0, self.LABEL_WIDTH)
        self.layout.setColumnStretch(0, 0)
        self.layout.setColumnStretch(1, 1)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("propertyFormTitle")
            self.layout.addWidget(title_label, self._row, 0, 1, 2)
            self._row += 1
        else:
            title_label = None
        self.title_label = title_label

    def add_row(self, label: str, editor: QWidget, hint: str = "") -> QLabel:
        label_widget = QLabel(label)
        label_widget.setObjectName("propertyFormLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label_widget.setMinimumWidth(self.LABEL_WIDTH)
        label_widget.setMaximumWidth(self.LABEL_WIDTH)
        label_widget.setWordWrap(False)
        label_widget.setToolTip(hint or label)
        label_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        editor.setMinimumHeight(self.EDITOR_HEIGHT)
        editor.setToolTip(hint or editor.toolTip())
        editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.layout.setRowMinimumHeight(self._row, self.ROW_HEIGHT)
        self.layout.addWidget(label_widget, self._row, 0)
        self.layout.addWidget(editor, self._row, 1)
        self._row += 1
        return label_widget

    def add_full_row(self, widget: QWidget) -> None:
        widget.setMinimumHeight(self.EDITOR_HEIGHT)
        self.layout.addWidget(widget, self._row, 0, 1, 2)
        self.layout.setRowMinimumHeight(self._row, self.ROW_HEIGHT)
        self._row += 1
