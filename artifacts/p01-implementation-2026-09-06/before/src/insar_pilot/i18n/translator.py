"""JSON/dict based translations for the PySide widgets UI."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from importlib import resources
from string import Formatter
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

    def messages(self) -> dict[str, str]:
        """Return the effective message catalog, including English fallbacks."""

        return {**self._fallback, **self._messages}

    def translation_map_to(self, target: Translator) -> dict[str, str]:
        """Map exact rendered source strings to another locale.

        If several keys share a rendered source string, the most common target
        spelling wins; catalog order resolves ties. Context-specific controls can
        still be refreshed precisely by their owning component.
        """

        source_messages = self.messages()
        target_messages = target.messages()
        candidates: dict[str, dict[str, int]] = {}
        for key, source_text in source_messages.items():
            target_text = target_messages.get(key, source_text)
            if source_text and source_text != target_text:
                counts = candidates.setdefault(source_text, {})
                counts[target_text] = counts.get(target_text, 0) + 1
        return {
            source_text: max(target_counts, key=lambda value: target_counts[value])
            for source_text, target_counts in candidates.items()
        }

    def text_translator_to(self, target: Translator) -> Callable[[str], str]:
        """Build a translator for text already rendered from catalog templates."""

        exact = self.translation_map_to(target)
        source_messages = self.messages()
        target_messages = target.messages()
        template_candidates: dict[str, set[str]] = {}
        for key, source_text in source_messages.items():
            target_text = target_messages.get(key, source_text)
            if "{" in source_text and source_text != target_text:
                template_candidates.setdefault(source_text, set()).add(target_text)

        templates: list[tuple[re.Pattern[str], dict[str, str], str]] = []
        for source_text, target_texts in sorted(
            template_candidates.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if len(target_texts) != 1:
                continue
            pattern, groups = _compile_rendered_template(source_text)
            templates.append((pattern, groups, next(iter(target_texts))))

        def translated(text: str) -> str:
            if text in exact:
                return exact[text]
            for pattern, groups, target_template in templates:
                match = pattern.fullmatch(text)
                if match is None:
                    continue
                values = {field: match.group(group) for field, group in groups.items()}
                try:
                    return target_template.format(**values)
                except (KeyError, ValueError):
                    return text
            return text

        return translated

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


def _compile_rendered_template(template: str) -> tuple[re.Pattern[str], dict[str, str]]:
    """Compile a catalog format string into a pattern that captures its values."""

    chunks: list[str] = []
    field_groups: dict[str, str] = {}
    for literal, field, _format_spec, _conversion in Formatter().parse(template):
        chunks.append(re.escape(literal))
        if field is None:
            continue
        group = field_groups.get(field)
        if group is None:
            group = f"value_{len(field_groups)}"
            field_groups[field] = group
            chunks.append(f"(?P<{group}>.+?)")
        else:
            chunks.append(f"(?P={group})")
    return re.compile("".join(chunks), re.DOTALL), field_groups


# Process-wide shared translator.
#
# UI pages and widgets are constructed without a translator reference (see
# ``MainWindow._build_page_stack``). A single shared instance lets every widget
# resolve strings through the same translator without threading a constructor
# parameter through the whole UI tree, and can be updated for live retranslation.
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
