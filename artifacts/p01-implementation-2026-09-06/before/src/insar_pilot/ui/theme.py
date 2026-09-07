"""Professional desktop stylesheet assembly for the industrial shell.

The visual language ships in two palettes (light default + dark). Both are
assembled from the same token-driven QSS modules; only the token dictionary
differs, so the two themes stay structurally identical.
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from insar_pilot.ui.styles import (
    build_base_qss,
    build_component_qss,
    build_status_qss,
    build_widget_qss,
    resolve_tokens,
)

ThemeMode = Literal["light", "dark"]


def build_stylesheet(mode: ThemeMode = "light") -> str:
    """Return the composed stylesheet for ``mode`` (``"light"`` default)."""

    tokens = resolve_tokens(mode)
    return "\n".join(
        (
            build_base_qss(tokens),
            build_component_qss(tokens),
            build_status_qss(tokens),
            build_widget_qss(tokens),
        )
    )


def build_light_stylesheet() -> str:
    """Return the default light stylesheet for scientific desktop workflows."""

    return build_stylesheet("light")


def build_dark_stylesheet() -> str:
    """Return the dark stylesheet counterpart."""

    return build_stylesheet("dark")


def apply_theme(app: QApplication, mode: str) -> None:
    """Apply a theme to a running application, including non-QSS palette roles."""

    from insar_pilot.ui.styles import set_active_tokens

    normalized: ThemeMode = "dark" if str(mode or "light").lower() == "dark" else "light"
    tokens = set_active_tokens(normalized)
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(tokens["placeholder"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens["alternate_row"]))
    app.setPalette(palette)
    app.setStyleSheet(build_stylesheet(normalized))
    for widget in app.allWidgets():
        widget.update()
