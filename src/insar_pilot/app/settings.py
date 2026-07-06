"""User-level Qt settings for the desktop shell."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings
from PySide6.QtWidgets import QDockWidget, QSplitter


class AppSettings:
    """Small wrapper around QSettings for preferences outside project state."""

    ORGANIZATION = "Open Source"
    APPLICATION = "InSAR-PILOT"

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings(self.ORGANIZATION, self.APPLICATION)

    def language(self, default: str = "en") -> str:
        value = self._settings.value("ui/language", default)
        return str(value or default)

    def set_language(self, language: str) -> None:
        self._settings.setValue("ui/language", language or "en")

    def recent_projects(self) -> list[dict[str, str]]:
        """Return recently opened project workspaces, newest first."""

        raw = self._settings.value("projects/recent", "[]")
        if not isinstance(raw, str):
            raw = "[]"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []

        projects: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            if not path or path in seen:
                continue
            name = str(item.get("name", "")).strip() or Path(path).expanduser().name
            projects.append({"name": name, "path": path})
            seen.add(path)
        return projects[:8]

    def add_recent_project(self, name: str, path: str | Path) -> None:
        """Add or promote a project workspace path in the recent list."""

        resolved_path = str(Path(path).expanduser())
        display_name = (name or "").strip() or Path(resolved_path).name
        updated = [{"name": display_name, "path": resolved_path}]
        for item in self.recent_projects():
            if item["path"] != resolved_path:
                updated.append(item)
        self._settings.setValue("projects/recent", json.dumps(updated[:8]))

    def clear_recent_projects(self) -> None:
        self._settings.setValue("projects/recent", "[]")

    def restore_splitter(self, name: str, splitter: QSplitter) -> bool:
        value = self._settings.value(f"layout/{name}")
        if isinstance(value, QByteArray):
            return splitter.restoreState(value)
        if isinstance(value, (bytes, bytearray)):
            return splitter.restoreState(QByteArray(value))
        return False

    def save_splitter(self, name: str, splitter: QSplitter) -> None:
        self._settings.setValue(f"layout/{name}", splitter.saveState())

    def restore_dock_visibility(self, name: str, dock: QDockWidget, *, default_visible: bool = False) -> None:
        value = self._settings.value(f"layout/{name}/visible", default_visible)
        visible = value if isinstance(value, bool) else str(value).lower() in {"1", "true", "yes"}
        dock.setVisible(bool(visible))

    def save_dock_visibility(self, name: str, dock: QDockWidget) -> None:
        self._settings.setValue(f"layout/{name}/visible", dock.isVisible())

    def sync(self) -> None:
        self._settings.sync()
