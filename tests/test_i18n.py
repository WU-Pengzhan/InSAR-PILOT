from insar_pilot.app.settings import AppSettings
from insar_pilot.i18n import Translator


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
