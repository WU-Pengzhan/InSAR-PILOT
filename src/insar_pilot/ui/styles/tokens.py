"""Design tokens for the GIS-style desktop theme (light + dark).

This module is the single source of truth for the visual language. Every QSS
module consumes these values; no color literal should live anywhere else in the
styling layer (canvas/QGraphics drawing colors are the only documented
exception, and even those resolve their tones from here).

Two palettes ship with identical key sets: ``LIGHT_TOKENS`` (default) and
``DARK_TOKENS`` (its disciplined dark-mode counterpart). ``resolve_tokens`` maps
a mode name onto a palette; ``set_active_tokens``/``active_tokens`` expose the
theme chosen at launch so non-QSS surfaces (icon tones) can follow it.
"""

from __future__ import annotations

# --- Light palette (default) -----------------------------------------------
LIGHT_TOKENS: dict[str, str] = {
    # --- Surfaces ---
    "background": "#eceff3",
    "surface": "#ffffff",
    "surface_alt": "#f4f6f8",  # action bars, panel header strips, grid label cells
    "surface_muted": "#e9edf2",  # header sections, grid titles, progress groove, neutral chips
    # Alternating table/tree rows (QPalette.AlternateBase). Matches the Qt
    # Fusion light default exactly so light appearance stays unchanged.
    "alternate_row": "#f7f7f7",
    # --- Borders ---
    "border": "#bfc7d1",
    "border_strong": "#9ca9b8",
    # --- Text (three-tier hierarchy) ---
    "text": "#1f2329",  # titles, values, control labels
    "text_subtle": "#4a5665",  # field/section labels (secondary structural text)
    "text_muted": "#586270",  # descriptive / hint / subtitle body text
    "placeholder": "#7e8896",  # QLineEdit placeholder (>=3.5:1 on surface)
    # --- Accent / focus ---
    "accent": "#1f5b99",
    "accent_hover": "#1a4f87",
    "accent_pressed": "#143f6d",
    "on_accent": "#ffffff",  # text/icon on accent fills (>=4.5:1)
    "focus": "#1f5b99",  # keyboard focus ring (accent-based)
    "selection": "#cfe3f8",
    # --- Interactive blue tint ramp (hover / pressed / checked) ---
    "hover_bg": "#edf5fd",
    "hover_border": "#8fb5dd",
    "pressed_bg": "#bfdaf2",
    "pressed_border": "#3f6f9f",
    "checked_bg": "#d7e9fb",
    "checked_border": "#5d91c4",
    # --- Disabled ---
    "disabled_text": "#7c8798",  # >=3.0:1 on disabled_bg
    "disabled_bg": "#eef1f5",
    "disabled_border": "#d6dde9",
    # --- Status: success ---
    "success_bg": "#e5f2e8",
    "success_text": "#23623a",
    "success_border": "#bcd9c4",
    # --- Status: running / info (one blue family) ---
    "running_bg": "#e4f0fb",
    "running_text": "#245f96",
    "info_bg": "#e4f0fb",
    "info_text": "#245f96",
    "info_border": "#b8d2ed",
    # --- Status: warning ---
    "warning_bg": "#fff1d8",
    "warning_text": "#79581f",
    "warning_border": "#e4c792",
    # --- Status: error / danger ---
    "error_bg": "#f9e2e2",
    "error_text": "#843232",
    "error_border": "#e0b0b0",
    "danger_bg": "#fbecec",
    "danger_pressed_bg": "#f2caca",
    "danger_pressed_border": "#be7e7e",
    # --- Icon tones (QPainter/qtawesome glyph fills, resolved per theme) ---
    "icon_default": "#2f5f94",
    "icon_muted": "#5e6a7d",
    "icon_success": "#2f6b45",
    "icon_warning": "#8a6532",
    "icon_error": "#8a2d2d",
}

# --- Dark palette -----------------------------------------------------------
# Designed as the light theme's disciplined counterpart. Every fg/bg pair used
# by the QSS clears its WCAG target (body/muted/subtle >=4.5, status >=4.5,
# primary-button text >=4.5, disabled >=3.0, placeholder >=3.5) -- see the
# task report's scripted contrast table.
DARK_TOKENS: dict[str, str] = {
    # --- Surfaces ---
    "background": "#14171c",
    "surface": "#1d2127",
    "surface_alt": "#242932",  # action bars, panel header strips, grid label cells
    "surface_muted": "#2b313b",  # header sections, grid titles, progress groove, neutral chips
    # Alternating table/tree rows (QPalette.AlternateBase): one step above
    # surface so striped rows read as dark stripes, not Qt's light-grey default.
    "alternate_row": "#242932",
    # --- Borders (visible but quiet) ---
    "border": "#363d48",
    "border_strong": "#49515f",
    # --- Text (three-tier hierarchy; brighter = more prominent) ---
    "text": "#e8eaed",
    "text_subtle": "#c2cad4",  # field/section labels
    "text_muted": "#a7b0bc",  # descriptive / hint / subtitle body text
    "placeholder": "#7e8894",  # >=3.5:1 on surface
    # --- Accent / focus (lighter for a dark ground; brightens on hover/press) ---
    "accent": "#4f8fd0",
    "accent_hover": "#64a0dc",
    "accent_pressed": "#7ab0e8",  # also used as accent-colored text on dark chips
    "on_accent": "#10151b",  # dark text on the light-blue accent (>=4.5:1)
    "focus": "#6aa8e6",  # bright keyboard focus ring
    "selection": "#2c4056",  # translucent-feel dark blue
    # --- Interactive blue tint ramp (hover / pressed / checked) ---
    "hover_bg": "#232b36",
    "hover_border": "#3f6f9f",
    "pressed_bg": "#2b3a4c",
    "pressed_border": "#4f8fd0",
    "checked_bg": "#26374b",
    "checked_border": "#3f6f9f",
    # --- Disabled (>=3.0:1) ---
    "disabled_text": "#6c7580",
    "disabled_bg": "#20242b",
    "disabled_border": "#2c323b",
    # --- Status: success (dim bg, bright text) ---
    "success_bg": "#1d3226",
    "success_text": "#7fc99a",
    "success_border": "#2f5540",
    # --- Status: running / info (one blue family) ---
    "running_bg": "#1b2f45",
    "running_text": "#78b4e6",
    "info_bg": "#1b2f45",
    "info_text": "#78b4e6",
    "info_border": "#2d4a6b",
    # --- Status: warning ---
    "warning_bg": "#3a2f19",
    "warning_text": "#e0b878",
    "warning_border": "#5c4a28",
    # --- Status: error / danger ---
    "error_bg": "#3a2020",
    "error_text": "#e79191",
    "error_border": "#5c3232",
    "danger_bg": "#33201f",
    "danger_pressed_bg": "#4a2a28",
    "danger_pressed_border": "#6e4442",
    # --- Icon tones (lightened for dark surfaces) ---
    "icon_default": "#6aa8e6",
    "icon_muted": "#97a1b0",
    "icon_success": "#7fc99a",
    "icon_warning": "#e0b878",
    "icon_error": "#e79191",
}

# Backward-compatible default alias: the light palette is the single ``TOKENS``
# dict that existing callers and module-level QSS constants read from.
TOKENS: dict[str, str] = LIGHT_TOKENS

_PALETTES: dict[str, dict[str, str]] = {"light": LIGHT_TOKENS, "dark": DARK_TOKENS}


def resolve_tokens(mode: str = "light") -> dict[str, str]:
    """Return the palette for ``mode`` (``"light"`` default; unknown -> light)."""

    return _PALETTES.get((mode or "light").lower(), LIGHT_TOKENS)


# --- Active-theme holder ----------------------------------------------------
# The theme is chosen once at launch and persisted; painted surfaces (icon
# tones) read the active palette so they follow the chosen theme after restart.
_ACTIVE_TOKENS: dict[str, str] = LIGHT_TOKENS


def set_active_tokens(mode: str) -> dict[str, str]:
    """Record the active theme palette and return it."""

    global _ACTIVE_TOKENS
    _ACTIVE_TOKENS = resolve_tokens(mode)
    return _ACTIVE_TOKENS


def active_tokens() -> dict[str, str]:
    """Return the palette recorded by :func:`set_active_tokens` (light default)."""

    return _ACTIVE_TOKENS


# --- Non-color scales (Python constants) -----------------------------------
# Spacing rhythm in px. Use at layout call sites instead of magic numbers.
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24}

# Corner radii in px.
RADIUS = {"sm": 2, "md": 4, "lg": 6}

# Font point-size scale. Map existing sizes onto these rungs; do not invent new
# visual sizes.
FONT_SIZES = {
    "caption": 10.5,
    "body": 12,
    "body_lg": 12.5,
    "h3": 13,
    "h2": 15,
    "h1": 18,
}
