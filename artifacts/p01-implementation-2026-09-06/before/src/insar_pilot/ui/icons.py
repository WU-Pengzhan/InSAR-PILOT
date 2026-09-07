"""Icon provider with optional QtAwesome support."""

from __future__ import annotations

from importlib import resources

from PySide6.QtCore import QObject, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
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
    # Map icon tones onto active-theme tokens so glyphs stay legible in dark mode.
    _TONE_TOKENS = {
        "default": "icon_default",
        "muted": "icon_muted",
        "success": "icon_success",
        "warning": "icon_warning",
        "error": "icon_error",
    }
    _ICON_NAME_PROPERTY = "insarPilotIconName"
    _ICON_TONE_PROPERTY = "insarPilotIconTone"
    _PIXMAP_NAME_PROPERTY = "insarPilotPixmapName"
    _PIXMAP_TONE_PROPERTY = "insarPilotPixmapTone"
    _PIXMAP_WIDTH_PROPERTY = "insarPilotPixmapWidth"
    _PIXMAP_HEIGHT_PROPERTY = "insarPilotPixmapHeight"

    @classmethod
    def _tone_color(cls, tone: str) -> str:
        from insar_pilot.ui.styles.tokens import active_tokens

        tokens = active_tokens()
        token_key = cls._TONE_TOKENS.get(tone, cls._TONE_TOKENS["default"])
        return tokens[token_key]

    @classmethod
    def icon(cls, name: str, tone: str = "default") -> QIcon:
        """Return a named icon, falling back to the active Qt style."""

        qta_name = cls._QTA_NAMES.get(name, cls._QTA_NAMES["info"])
        try:
            import qtawesome as qta  # type: ignore

            return qta.icon(qta_name, color=cls._tone_color(tone))
        except Exception:
            app = QApplication.instance()
            if app is None:
                return QIcon()
            pixmap = cls._STYLE_NAMES.get(name, cls._STYLE_NAMES["info"])
            return app.style().standardIcon(pixmap)

    @classmethod
    def apply(cls, target: QObject, name: str, tone: str = "default") -> None:
        """Set and register an icon so a live theme change can recolor it."""

        setter = getattr(target, "setIcon", None)
        if not callable(setter):
            raise TypeError(f"{type(target).__name__} does not support setIcon")
        target.setProperty(cls._ICON_NAME_PROPERTY, name)
        target.setProperty(cls._ICON_TONE_PROPERTY, tone)
        setter(cls.icon(name, tone))

    @classmethod
    def apply_pixmap(
        cls,
        target: QObject,
        name: str,
        size: QSize,
        tone: str = "default",
    ) -> None:
        """Set and register an icon pixmap so it follows live theme changes."""

        setter = getattr(target, "setPixmap", None)
        if not callable(setter):
            raise TypeError(f"{type(target).__name__} does not support setPixmap")
        target.setProperty(cls._PIXMAP_NAME_PROPERTY, name)
        target.setProperty(cls._PIXMAP_TONE_PROPERTY, tone)
        target.setProperty(cls._PIXMAP_WIDTH_PROPERTY, size.width())
        target.setProperty(cls._PIXMAP_HEIGHT_PROPERTY, size.height())
        setter(cls.icon(name, tone).pixmap(size))

    @classmethod
    def refresh_tree(cls, root: QObject) -> None:
        """Regenerate all registered icons and pixmaps below ``root``."""

        for target in (root, *root.findChildren(QObject)):
            name = target.property(cls._ICON_NAME_PROPERTY)
            if isinstance(name, str) and name:
                cls.apply(target, name, str(target.property(cls._ICON_TONE_PROPERTY) or "default"))

            pixmap_name = target.property(cls._PIXMAP_NAME_PROPERTY)
            if isinstance(pixmap_name, str) and pixmap_name:
                size = QSize(
                    int(target.property(cls._PIXMAP_WIDTH_PROPERTY) or 0),
                    int(target.property(cls._PIXMAP_HEIGHT_PROPERTY) or 0),
                )
                cls.apply_pixmap(
                    target,
                    pixmap_name,
                    size,
                    str(target.property(cls._PIXMAP_TONE_PROPERTY) or "default"),
                )

    @staticmethod
    def qtawesome_available() -> bool:
        try:
            import qtawesome  # noqa: F401
        except Exception:
            return False
        return True


class BrandAssets:
    """Load packaged InSAR-PILOT logo assets for Qt widgets."""

    PACKAGE = "insar_pilot.ui.assets"
    LOGO = "logo.png"
    MARK = "logo-mark.png"

    @classmethod
    def logo_path(cls, name: str = LOGO) -> str:
        """Return a filesystem-like resource path for packaged logo assets."""

        return str(resources.files(cls.PACKAGE).joinpath(name))

    @classmethod
    def pixmap(cls, name: str = MARK, size: QSize | None = None) -> QPixmap:
        """Return a logo pixmap loaded from package data."""

        data = resources.files(cls.PACKAGE).joinpath(name).read_bytes()
        pixmap = QPixmap()
        pixmap.loadFromData(data, "PNG")
        if size is not None and not pixmap.isNull():
            pixmap = pixmap.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return pixmap

    @classmethod
    def icon(cls) -> QIcon:
        """Return the application icon built from the square logo mark."""

        icon = QIcon()
        for pixels in (16, 24, 32, 48, 64, 96, 128, 256, 512):
            pixmap = cls.pixmap(cls.MARK, QSize(pixels, pixels))
            if not pixmap.isNull():
                icon.addPixmap(pixmap)
        return icon
