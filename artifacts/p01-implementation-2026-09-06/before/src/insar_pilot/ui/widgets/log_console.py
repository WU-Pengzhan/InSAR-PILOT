"""Bounded log console and shared scroll-preserving append helpers."""

from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit


class LogConsole(QPlainTextEdit):
    """Read-only log view that keeps only the most recent text blocks."""

    DEFAULT_MAX_BLOCKS = 10_000

    def __init__(self, *, max_blocks: int = DEFAULT_MAX_BLOCKS, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("logConsole")
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(max(1, int(max_blocks)))

    def append_text_preserving_scroll(self, text: str) -> None:
        """Append text without pulling a user away from older log lines."""

        append_text_preserving_scroll(self, text)


def append_text_preserving_scroll(text_edit: QPlainTextEdit, text: str) -> None:
    """Append text and only auto-scroll when the user was already at the bottom."""

    scrollbar = text_edit.verticalScrollBar()
    was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 2
    previous_value = scrollbar.value()
    cursor = text_edit.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    cursor.insertText(text)
    text_edit.setTextCursor(cursor)
    if was_at_bottom:
        scrollbar.setValue(scrollbar.maximum())
    else:
        scrollbar.setValue(previous_value)
