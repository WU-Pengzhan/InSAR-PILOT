"""Runtime launch helpers for WSL2 and Ubuntu desktop sessions."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


APP_NAME = "InSAR-PILOT"


def running_on_wsl() -> bool:
    """Return True when launched inside WSL/WSLg."""

    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    try:
        text = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False
    return "microsoft" in text


def _prepend_env_path(name: str, paths: list[Path]) -> None:
    existing = os.environ.get(name, "")
    clean_paths = [str(path) for path in paths if path.exists()]
    if clean_paths:
        os.environ[name] = os.pathsep.join(clean_paths + ([existing] if existing else []))


def _pyside_root() -> Path | None:
    spec = importlib.util.find_spec("PySide6")
    if spec is None or spec.submodule_search_locations is None:
        return None
    for location in spec.submodule_search_locations:
        path = Path(location)
        if path.exists():
            return path
    return None


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def prepare_qt_runtime() -> None:
    """Prepare Qt/PySide paths for both PySide wheels and conda Qt layouts."""

    prefix = Path(sys.prefix)
    pyside_root = _pyside_root()
    pyside_qt_root = pyside_root / "Qt" if pyside_root is not None else None
    qt6_root = prefix / "lib" / "qt6"

    qt_libs = [prefix / "lib"]
    if pyside_qt_root is not None:
        qt_libs.insert(0, pyside_qt_root / "lib")
    shiboken_root = importlib.util.find_spec("shiboken6")
    if shiboken_root is not None and shiboken_root.submodule_search_locations is not None:
        qt_libs.extend(Path(item) for item in shiboken_root.submodule_search_locations)
    _prepend_env_path("LD_LIBRARY_PATH", qt_libs)

    plugin_roots = [qt6_root / "plugins", prefix / "plugins"]
    if pyside_qt_root is not None:
        plugin_roots.insert(0, pyside_qt_root / "plugins")
    _prepend_env_path("QT_PLUGIN_PATH", plugin_roots)

    platform_dir = _first_existing([path / "platforms" for path in plugin_roots])
    if platform_dir is not None:
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_dir)

    webengine_process_paths = [
        qt6_root / "libexec" / "QtWebEngineProcess",
        prefix / "libexec" / "QtWebEngineProcess",
    ]
    webengine_resource_paths = [qt6_root / "resources", prefix / "resources"]
    webengine_locale_paths = [prefix / "share" / "qt6" / "translations" / "qtwebengine_locales"]
    if pyside_qt_root is not None:
        webengine_process_paths.insert(0, pyside_qt_root / "libexec" / "QtWebEngineProcess")
        webengine_resource_paths.insert(0, pyside_qt_root / "resources")
        webengine_locale_paths.insert(0, pyside_qt_root / "translations" / "qtwebengine_locales")

    webengine_process = _first_existing(webengine_process_paths)
    webengine_resources = _first_existing(webengine_resource_paths)
    webengine_locales = _first_existing(webengine_locale_paths)
    if webengine_process is not None:
        os.environ["QTWEBENGINEPROCESS_PATH"] = str(webengine_process)
    if webengine_resources is not None:
        os.environ["QTWEBENGINE_RESOURCES_PATH"] = str(webengine_resources)
    if webengine_locales is not None:
        os.environ["QTWEBENGINE_LOCALES_PATH"] = str(webengine_locales)


def prepare_desktop_environment() -> None:
    """Set conservative defaults that work on WSLg and native Ubuntu desktops."""

    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.plugin=false")
    if running_on_wsl() and not os.environ.get("XDG_RUNTIME_DIR"):
        wslg_runtime = Path("/mnt/wslg/runtime-dir")
        if wslg_runtime.exists():
            os.environ["XDG_RUNTIME_DIR"] = str(wslg_runtime)


def qt_platform_candidates() -> list[str]:
    """Return platform plugin candidates ordered for the current desktop session."""

    display = bool(os.environ.get("DISPLAY"))
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if running_on_wsl():
        if display and wayland:
            return ["xcb", "wayland"]
        if display:
            return ["xcb"]
        if wayland:
            return ["wayland"]
        return ["xcb", "wayland"]
    if session_type == "wayland" and wayland:
        return ["wayland", "xcb"] if display else ["wayland"]
    if display:
        return ["xcb", "wayland"] if wayland else ["xcb"]
    if wayland:
        return ["wayland", "xcb"]
    return ["xcb", "wayland"]


def qt_platform_works(platform: str) -> tuple[bool, str]:
    """Probe a Qt platform plugin in a child process."""

    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = platform
    env.setdefault("QT_LOGGING_RULES", "qt.qpa.plugin=false")
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "from PySide6.QtWidgets import QApplication; app = QApplication([])",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "Qt platform probe timed out."
    detail = (completed.stderr or completed.stdout or "").strip()
    return completed.returncode == 0, detail


def select_qt_platform() -> bool:
    """Select a working Qt platform unless the user already requested one."""

    if os.environ.get("QT_QPA_PLATFORM"):
        return True

    failures: list[str] = []
    for candidate in qt_platform_candidates():
        ok, detail = qt_platform_works(candidate)
        if ok:
            os.environ["QT_QPA_PLATFORM"] = candidate
            if os.environ.get("INSAR_PILOT_DEBUG_LAUNCH"):
                print(f"{APP_NAME}: selected Qt platform '{candidate}'.", file=sys.stderr)
            return True
        failures.append(f"{candidate}: {detail.splitlines()[-1] if detail else 'failed'}")

    hint = (
        "No graphical display backend could be initialized.\n"
        "For WSL2, start from WSLg or an X server and install xcb runtime packages:\n"
        "  sudo apt install -y libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0\n"
        "For Ubuntu Desktop, verify that DISPLAY or WAYLAND_DISPLAY is available in this shell.\n\n"
    )
    print(f"{APP_NAME} could not initialize a Qt display backend.\n{hint}" + "\n".join(failures), file=sys.stderr)
    return False


def apply_runtime_environment() -> bool:
    """Apply launch-time environment defaults before importing Qt widgets."""

    prepare_desktop_environment()
    prepare_qt_runtime()
    return select_qt_platform()


def prepare_qt_application_attributes() -> None:
    """Set Qt application attributes that must be applied before QApplication."""

    from PySide6.QtCore import QCoreApplication, Qt

    for name in ("AA_ShareOpenGLContexts", "AA_DontCreateNativeWidgetSiblings"):
        attribute = getattr(Qt.ApplicationAttribute, name, None)
        if attribute is not None:
            QCoreApplication.setAttribute(attribute, True)


def main(argv: list[str] | None = None) -> int:
    """Launch the desktop application."""

    if not apply_runtime_environment():
        return 2

    args = list(sys.argv if argv is None else argv)
    prepare_qt_application_attributes()
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from insar_pilot.bootstrap import create_default_project
    from insar_pilot.ui.main_window import MainWindow
    from insar_pilot.ui.theme import build_light_stylesheet

    app = QApplication(args)
    default_font = QFont(app.font())
    default_font.setPointSize(12)
    app.setFont(default_font)
    app.setStyleSheet(build_light_stylesheet())
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Open Source")
    window = MainWindow(create_default_project())
    window.show()
    return app.exec()
