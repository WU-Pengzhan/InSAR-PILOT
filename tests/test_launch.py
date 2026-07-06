from __future__ import annotations

import os
from pathlib import Path

import insar_pilot.launch as launch


def test_qt_platform_candidates_prefer_xcb_on_wsl(monkeypatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)

    assert launch.qt_platform_candidates() == ["xcb", "wayland"]


def test_qt_platform_candidates_follow_ubuntu_wayland_session(monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    monkeypatch.setattr(launch, "running_on_wsl", lambda: False)
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")

    assert launch.qt_platform_candidates() == ["wayland", "xcb"]


def test_select_qt_platform_respects_user_override(monkeypatch):
    called = False

    def _probe(_platform):
        nonlocal called
        called = True
        return True, ""

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(launch, "qt_platform_works", _probe)

    assert launch.select_qt_platform() is True
    assert called is False


def test_prepare_qt_application_attributes_is_callable():
    launch.prepare_qt_application_attributes()


def test_prepare_qt_runtime_supports_pyside_and_conda_qt_layouts(tmp_path, monkeypatch):
    prefix = tmp_path / "env"
    pyside = prefix / "lib" / "python3.10" / "site-packages" / "PySide6"
    pyside_plugins = pyside / "Qt" / "plugins"
    conda_platforms = prefix / "lib" / "qt6" / "plugins" / "platforms"
    webengine = pyside / "Qt" / "libexec" / "QtWebEngineProcess"
    for path in (pyside_plugins / "platforms", conda_platforms, webengine.parent):
        path.mkdir(parents=True)
    webengine.write_text("", encoding="utf-8")

    class _Spec:
        submodule_search_locations = [str(pyside)]

    monkeypatch.setattr(launch.sys, "prefix", str(prefix))
    monkeypatch.setattr(launch.importlib.util, "find_spec", lambda name: _Spec() if name == "PySide6" else None)
    for key in (
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QTWEBENGINEPROCESS_PATH",
        "LD_LIBRARY_PATH",
    ):
        monkeypatch.delenv(key, raising=False)

    launch.prepare_qt_runtime()

    plugin_paths = os.environ["QT_PLUGIN_PATH"].split(os.pathsep)
    assert str(pyside_plugins) in plugin_paths
    assert str(prefix / "lib" / "qt6" / "plugins") in plugin_paths
    assert Path(os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"]) == pyside_plugins / "platforms"
    assert Path(os.environ["QTWEBENGINEPROCESS_PATH"]) == webengine
