"""Icon provider with optional QtAwesome support."""

from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle


class IconProvider:
    """Return product icons while keeping deployment resilient without QtAwesome."""

    _QTA_NAMES = {
        "account": "fa6s.user-shield",
        "search": "fa6s.magnifying-glass",
        "download": "fa6s.download",
        "cancel": "fa6s.ban",
        "save": "fa6s.floppy-disk",
        "folder": "fa6s.folder-open",
        "import": "fa6s.file-import",
        "refresh": "fa6s.rotate",
        "run": "fa6s.play",
        "stop": "fa6s.stop",
        "settings": "fa6s.gear",
        "language": "fa6s.language",
        "check": "fa6s.circle-check",
        "warning": "fa6s.triangle-exclamation",
        "error": "fa6s.circle-xmark",
        "info": "fa6s.circle-info",
        "preview": "fa6s.eye",
        "generate": "fa6s.wand-magic-sparkles",
    }
    _STYLE_NAMES = {
        "account": QStyle.StandardPixmap.SP_DialogApplyButton,
        "search": QStyle.StandardPixmap.SP_FileDialogContentsView,
        "download": QStyle.StandardPixmap.SP_ArrowDown,
        "cancel": QStyle.StandardPixmap.SP_DialogCancelButton,
        "save": QStyle.StandardPixmap.SP_DialogSaveButton,
        "folder": QStyle.StandardPixmap.SP_DirOpenIcon,
        "import": QStyle.StandardPixmap.SP_FileIcon,
        "refresh": QStyle.StandardPixmap.SP_BrowserReload,
        "run": QStyle.StandardPixmap.SP_MediaPlay,
        "stop": QStyle.StandardPixmap.SP_MediaStop,
        "settings": QStyle.StandardPixmap.SP_FileDialogDetailedView,
        "language": QStyle.StandardPixmap.SP_MessageBoxInformation,
        "check": QStyle.StandardPixmap.SP_DialogApplyButton,
        "warning": QStyle.StandardPixmap.SP_MessageBoxWarning,
        "error": QStyle.StandardPixmap.SP_MessageBoxCritical,
        "info": QStyle.StandardPixmap.SP_MessageBoxInformation,
        "preview": QStyle.StandardPixmap.SP_FileDialogInfoView,
        "generate": QStyle.StandardPixmap.SP_CommandLink,
    }
    _TONE_COLORS = {
        "default": "#2f5f94",
        "muted": "#5e6a7d",
        "success": "#2f6b45",
        "warning": "#8a6532",
        "error": "#8a2d2d",
    }

    @classmethod
    def icon(cls, name: str, tone: str = "default") -> QIcon:
        """Return a named icon, falling back to the active Qt style."""

        qta_name = cls._QTA_NAMES.get(name, cls._QTA_NAMES["info"])
        try:
            import qtawesome as qta  # type: ignore

            return qta.icon(qta_name, color=cls._TONE_COLORS.get(tone, cls._TONE_COLORS["default"]))
        except Exception:
            app = QApplication.instance()
            if app is None:
                return QIcon()
            pixmap = cls._STYLE_NAMES.get(name, cls._STYLE_NAMES["info"])
            return app.style().standardIcon(pixmap)

    @staticmethod
    def qtawesome_available() -> bool:
        try:
            import qtawesome  # noqa: F401
        except Exception:
            return False
        return True
