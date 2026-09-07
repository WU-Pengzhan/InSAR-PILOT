"""Application font selection for Linux, WSLg, and Windows-hosted displays."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication

UI_FONT_CANDIDATES = (
    "Noto Sans CJK SC",
    "Microsoft YaHei UI",
    "Source Han Sans SC",
    "PingFang SC",
    "Segoe UI",
    "Ubuntu",
    "DejaVu Sans",
)


def resolve_ui_font_family(families: Iterable[str] | None = None) -> str:
    """Return the first installed family suitable for mixed Chinese/Latin UI text."""

    if families is None:
        if QGuiApplication.instance() is None:
            return ""
        families = QFontDatabase.families()
    available = set(families)
    return next((family for family in UI_FONT_CANDIDATES if family in available), "")


def build_ui_font(base_font: QFont | None = None, point_size: float = 12.0) -> QFont:
    """Build a readable desktop UI font without depending on implicit fallback."""

    font = QFont(base_font) if base_font is not None else QFont()
    family = resolve_ui_font_family()
    if family:
        font.setFamily(family)
    font.setPointSizeF(point_size)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font
