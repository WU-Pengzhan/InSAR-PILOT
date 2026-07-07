"""Tests for the light/dark token system, theme assembly, and theme setting."""

import re

from insar_pilot.app.settings import AppSettings
from insar_pilot.ui.styles.tokens import (
    DARK_TOKENS,
    LIGHT_TOKENS,
    active_tokens,
    resolve_tokens,
    set_active_tokens,
)
from insar_pilot.ui.theme import (
    build_dark_stylesheet,
    build_light_stylesheet,
    build_stylesheet,
)

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}")


def test_light_and_dark_token_sets_share_identical_keys():
    assert set(LIGHT_TOKENS) == set(DARK_TOKENS)
    # Every value is a hex color literal in both palettes.
    for palette in (LIGHT_TOKENS, DARK_TOKENS):
        for key, value in palette.items():
            assert _HEX.fullmatch(value), f"{key} is not a hex literal: {value!r}"


def test_resolve_tokens_defaults_to_light_and_maps_dark():
    assert resolve_tokens() is LIGHT_TOKENS
    assert resolve_tokens("light") is LIGHT_TOKENS
    assert resolve_tokens("dark") is DARK_TOKENS
    assert resolve_tokens("DARK") is DARK_TOKENS
    assert resolve_tokens("nonsense") is LIGHT_TOKENS


def test_both_stylesheets_build_non_empty_and_differ():
    light = build_light_stylesheet()
    dark = build_dark_stylesheet()

    assert light and dark
    assert light == build_stylesheet("light")
    assert dark == build_stylesheet("dark")
    assert light != dark
    # Same structural rules in both themes -> same set of selectors/lengths.
    assert len(light.splitlines()) == len(dark.splitlines())


def test_stylesheets_only_use_colors_from_their_palette():
    for mode, palette in (("light", LIGHT_TOKENS), ("dark", DARK_TOKENS)):
        sheet = build_stylesheet(mode)
        allowed = {value.lower() for value in palette.values()}
        used = {match.group(0).lower() for match in _HEX.finditer(sheet)}
        leftover = used - allowed
        assert not leftover, f"{mode} stylesheet has non-palette literals: {leftover}"


def test_set_active_tokens_switches_the_active_palette():
    try:
        assert set_active_tokens("dark") is DARK_TOKENS
        assert active_tokens() is DARK_TOKENS
        assert set_active_tokens("light") is LIGHT_TOKENS
        assert active_tokens() is LIGHT_TOKENS
    finally:
        set_active_tokens("light")


def test_app_settings_theme_defaults_to_light(tmp_path):
    from PySide6.QtCore import QSettings

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)

    assert AppSettings(settings).theme() == "light"


def test_app_settings_theme_round_trip(tmp_path):
    from PySide6.QtCore import QSettings

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    app_settings = AppSettings(settings)

    app_settings.set_theme("dark")
    app_settings.sync()

    reopened = AppSettings(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    assert reopened.theme() == "dark"

    # Unknown values fall back to the light default.
    app_settings.set_theme("psychedelic")
    assert app_settings.theme() == "light"
