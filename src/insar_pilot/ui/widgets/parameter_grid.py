"""Two-column parameter grid for SARscape/GIS style setup pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QWidget


class ParameterGrid(QFrame):
    """Compact two-column parameter editor surface."""

    LABEL_COLUMN_WIDTH = 185
    ROW_MIN_HEIGHT = 40
    EDITOR_MIN_HEIGHT = 36

    def __init__(self, title: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("parameterGrid")
        self._row = 0
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setHorizontalSpacing(0)
        self.layout.setVerticalSpacing(0)
        self.layout.setColumnMinimumWidth(0, self.LABEL_COLUMN_WIDTH)
        self.layout.setColumnStretch(0, 0)
        self.layout.setColumnStretch(1, 1)
        if title:
            self.title_label = QLabel(title)
            self.title_label.setObjectName("parameterGridTitle")
            self.layout.addWidget(self.title_label, self._row, 0, 1, 2)
            self.layout.setRowMinimumHeight(self._row, self.ROW_MIN_HEIGHT)
            self._row += 1
        else:
            self.title_label = None

    def add_row(self, label: str, editor: QWidget, hint: str = "") -> QLabel:
        """Add a labeled editor row."""

        label_widget = QLabel(label)
        label_widget.setObjectName("parameterGridLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label_widget.setWordWrap(False)
        label_widget.setMinimumWidth(self.LABEL_COLUMN_WIDTH)
        label_widget.setMaximumWidth(self.LABEL_COLUMN_WIDTH)
        label_widget.setToolTip(hint or label)
        label_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        editor.setToolTip(hint or editor.toolTip())
        editor.setMinimumHeight(self.EDITOR_MIN_HEIGHT)
        editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.layout.setRowMinimumHeight(self._row, self.ROW_MIN_HEIGHT)
        self.layout.addWidget(label_widget, self._row, 0)
        self.layout.addWidget(editor, self._row, 1)
        self._row += 1
        return label_widget

    def add_full_row(self, widget: QWidget) -> None:
        """Add a full-width row for grouped controls or explanatory text."""

        self.layout.addWidget(widget, self._row, 0, 1, 2)
        self.layout.setRowMinimumHeight(self._row, self.ROW_MIN_HEIGHT)
        self._row += 1
