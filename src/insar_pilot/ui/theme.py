"""Professional desktop stylesheet assembly for the industrial shell.

The visual language ships in two palettes (light default + dark). Both are
assembled from the same token-driven QSS modules; only the token dictionary
differs, so the two themes stay structurally identical.
"""

from __future__ import annotations

from typing import Literal

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
