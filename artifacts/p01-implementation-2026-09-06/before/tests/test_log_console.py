"""Regression tests for bounded, user-friendly log consoles."""

from PySide6.QtWidgets import QApplication

from insar_pilot.ui.widgets.log_console import LogConsole


def _qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_log_console_is_read_only_and_bounded():
    _qt_app()
    console = LogConsole(max_blocks=5)

    assert console.isReadOnly() is True
    assert console.document().maximumBlockCount() == 5

    for index in range(20):
        console.appendPlainText(f"line {index}")

    text = console.toPlainText()
    assert "line 0\n" not in text
    assert "line 15" in text
    assert "line 19" in text


def test_log_console_preserves_manual_scroll_position():
    app = _qt_app()
    console = LogConsole(max_blocks=200)
    console.resize(360, 140)
    console.show()
    for index in range(100):
        console.append_text_preserving_scroll(f"line {index}\n")
    app.processEvents()

    scrollbar = console.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum() // 3)
    app.processEvents()
    previous = scrollbar.value()

    console.append_text_preserving_scroll("new line while reading history\n")
    app.processEvents()

    assert scrollbar.value() == previous
