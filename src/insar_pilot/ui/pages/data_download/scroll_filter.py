"""Wheel-focus event filter for nested text edits on the data download page."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QPlainTextEdit


class NestedScrollFilter(QObject):
    """Keep wheel focus on the text edit under the cursor."""

    def __init__(self, text_edit: QPlainTextEdit) -> None:
        super().__init__(text_edit)
        self.text_edit = text_edit

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.Wheel:
            self.text_edit.setFocus(Qt.FocusReason.MouseFocusReason)
            scrollbar = self.text_edit.verticalScrollBar()
            delta = event.angleDelta().y()
            at_top = scrollbar.value() <= scrollbar.minimum()
            at_bottom = scrollbar.value() >= scrollbar.maximum()
            if (delta > 0 and not at_top) or (delta < 0 and not at_bottom):
                event.accept()
                return False
            event.ignore()
        return False
