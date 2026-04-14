"""Qt application entry point."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from isce2_gui.bootstrap import create_default_project
from isce2_gui.ui.main_window import MainWindow
from isce2_gui.ui.theme import build_light_stylesheet


def _running_on_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    try:
        text = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False
    return "microsoft" in text


def main(argv: list[str] | None = None) -> int:
    """Launch the desktop application."""

    # WSLg fallback: force xcb unless user explicitly provides a backend.
    if _running_on_wsl():
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    args = list(sys.argv if argv is None else argv)
    app = QApplication(args)
    default_font = QFont(app.font())
    if default_font.pointSize() > 0:
        default_font.setPointSize(max(default_font.pointSize() + 2, 11))
    else:
        default_font.setPointSize(11)
    app.setFont(default_font)
    app.setStyleSheet(build_light_stylesheet())
    app.setApplicationName("ISCE2 Sentinel-1 GUI")
    app.setOrganizationName("Open Source")
    window = MainWindow(create_default_project())
    window.show()
    return app.exec()
