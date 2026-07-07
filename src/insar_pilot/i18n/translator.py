"""JSON/dict based translations for the PySide widgets UI."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


class Translator:
    """Load simple JSON translations with English fallback."""

    DEFAULT_LANGUAGE = "en"
    SUPPORTED_LANGUAGES = ("en", "zh")

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self.language = self._normalize(language)
        self._fallback = self._load(self.DEFAULT_LANGUAGE)
        self._messages = self._fallback if self.language == self.DEFAULT_LANGUAGE else self._load(self.language)

    def set_language(self, language: str) -> None:
        self.language = self._normalize(language)
        self._messages = self._fallback if self.language == self.DEFAULT_LANGUAGE else self._load(self.language)

    def tr(self, key: str, default: str | None = None, **values: Any) -> str:
        text = str(self._messages.get(key) or self._fallback.get(key) or default or key)
        if values:
            try:
                return text.format(**values)
            except Exception:
                return text
        return text

    @classmethod
    def _normalize(cls, language: str) -> str:
        value = (language or cls.DEFAULT_LANGUAGE).replace("-", "_").lower()
        if value.startswith("zh"):
            return "zh"
        return cls.DEFAULT_LANGUAGE

    @staticmethod
    def _load(language: str) -> dict[str, str]:
        try:
            payload = (
                resources.files("insar_pilot.i18n.locales")
                .joinpath(f"{language}.json")
                .read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            if language == Translator.DEFAULT_LANGUAGE:
                return {}
            return Translator._load(Translator.DEFAULT_LANGUAGE)
        data = json.loads(payload)
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items()}


# Process-wide shared translator.
#
# UI pages and widgets are constructed without a translator reference (see
# ``MainWindow._build_page_stack``), and the selected language is fixed for the
# lifetime of a window (changing it requires an application restart). A single
# shared instance therefore lets every widget resolve strings through the same
# translator without threading a constructor parameter through the whole UI tree.
_SHARED_TRANSLATOR = Translator()


def get_translator() -> Translator:
    """Return the process-wide shared translator instance."""

    return _SHARED_TRANSLATOR


def set_shared_language(language: str) -> None:
    """Update the language of the shared translator instance in place."""

    _SHARED_TRANSLATOR.set_language(language)


def tr(key: str, default: str | None = None, **values: Any) -> str:
    """Resolve ``key`` through the shared translator (module-level convenience)."""

    return _SHARED_TRANSLATOR.tr(key, default, **values)
