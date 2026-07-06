"""Shared log text helpers."""

from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit


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
