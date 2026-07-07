import json
import re
from importlib import resources

from insar_pilot.app.settings import AppSettings
from insar_pilot.i18n import Translator

_PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def _load_locale(language: str) -> dict[str, str]:
    payload = (
        resources.files("insar_pilot.i18n.locales")
        .joinpath(f"{language}.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(payload)


def test_app_settings_default_language_is_english(tmp_path):
    from PySide6.QtCore import QSettings

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)

    assert AppSettings(settings).language() == "en"


def test_app_settings_tracks_recent_projects(tmp_path):
    from PySide6.QtCore import QSettings

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    app_settings = AppSettings(settings)

    app_settings.add_recent_project("city", tmp_path / "city")
    app_settings.add_recent_project("dam", tmp_path / "dam")
    app_settings.add_recent_project("city", tmp_path / "city")

    recent = app_settings.recent_projects()
    assert recent[0]["name"] == "city"
    assert recent[0]["path"] == str(tmp_path / "city")
    assert [item["name"] for item in recent] == ["city", "dam"]


def test_translator_uses_english_only_fallback():
    assert Translator("en").tr("nav.data_download") == "Sentinel-1 Data Download"
    assert Translator("fr").tr("nav.data_download") == "Sentinel-1 Data Download"
    assert Translator("fr").tr("nav.processing_setup") == "Processing Setup"


def test_translator_falls_back_to_default_or_key():
    translator = Translator("en")

    assert translator.tr("missing.key", default="Fallback") == "Fallback"
    assert translator.tr("missing.key") == "missing.key"


def test_locale_key_sets_are_identical():
    en = _load_locale("en")
    zh = _load_locale("zh")

    assert set(en) == set(zh)


def test_locale_values_are_non_empty():
    for language in ("en", "zh"):
        for key, value in _load_locale(language).items():
            assert value.strip(), f"empty value for {key} in {language}.json"


def test_locale_placeholders_match_between_languages():
    en = _load_locale("en")
    zh = _load_locale("zh")

    for key in en:
        en_tokens = sorted(_PLACEHOLDER.findall(en[key]))
        zh_tokens = sorted(_PLACEHOLDER.findall(zh[key]))
        assert en_tokens == zh_tokens, f"placeholder mismatch for {key}"


def test_translator_loads_simplified_chinese():
    translator = Translator("zh")

    assert translator.language == "zh"
    assert translator.tr("nav.processing_setup") == "处理设置"
    assert translator.tr("header.save") == "保存项目"
    # Placeholder substitution survives translation.
    assert translator.tr("preflight.warning", count=2) == "预检完成，存在 2 个警告。"


def test_translator_zh_falls_back_to_english_for_missing_key():
    translator = Translator("zh")

    assert translator.tr("missing.key") == "missing.key"
    assert translator.tr("missing.key", default="Fallback") == "Fallback"
