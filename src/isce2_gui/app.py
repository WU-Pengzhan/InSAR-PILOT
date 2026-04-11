"""Qt application entry point."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from isce2_gui.bootstrap import create_default_project
from isce2_gui.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    """Launch the desktop application."""

    args = list(sys.argv if argv is None else argv)
    app = QApplication(args)
    default_font = QFont(app.font())
    if default_font.pointSize() > 0:
        default_font.setPointSize(max(default_font.pointSize() + 2, 11))
    else:
        default_font.setPointSize(11)
    app.setFont(default_font)
    app.setApplicationName("ISCE2 Sentinel-1 GUI")
    app.setOrganizationName("Open Source")
    window = MainWindow(create_default_project())
    window.show()
    return app.exec()
