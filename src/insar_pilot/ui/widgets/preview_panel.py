"""Reusable preview image panel with metadata text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget

from insar_pilot.i18n import tr


@dataclass(frozen=True)
class PreviewImageInfo:
    """Dimensions recorded while loading a scaled preview image."""

    path: Path
    original_width: int
    original_height: int
    display_width: int
    display_height: int


class PreviewPanel(QWidget):
    """Image preview area with scroll support and metadata panel."""

    MAX_PREVIEW_SIZE = QSize(1600, 1200)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.image_label = QLabel(tr("results.preview.none"))
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.image_label.setMinimumSize(480, 320)
        self.image_label.setScaledContents(False)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area, 1)

        self.meta_text = QPlainTextEdit()
        self.meta_text.setReadOnly(True)
        self.meta_text.setPlaceholderText(tr("widget.preview.meta_placeholder"))
        layout.addWidget(self.meta_text)

    def load_image(self, path: str | Path) -> PreviewImageInfo:
        """Decode and display an image at preview resolution."""

        image_path = Path(path).expanduser()
        if not image_path.is_file():
            raise FileNotFoundError(f"Preview image was not found: {image_path}")

        reader = QImageReader(str(image_path))
        reader.setAutoTransform(True)
        if not reader.canRead():
            raise ValueError(reader.errorString() or f"Unsupported preview image: {image_path}")

        original_size = reader.size()
        if original_size.isValid() and (
            original_size.width() > self.MAX_PREVIEW_SIZE.width()
            or original_size.height() > self.MAX_PREVIEW_SIZE.height()
        ):
            reader.setScaledSize(
                original_size.scaled(
                    self.MAX_PREVIEW_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
            )

        image = reader.read()
        if image.isNull():
            raise ValueError(reader.errorString() or f"Failed to decode preview image: {image_path}")
        if not original_size.isValid():
            original_size = image.size()

        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            raise ValueError(f"Failed to create preview image: {image_path}")

        self.image_label.setText("")
        self.image_label.setPixmap(pixmap)
        self.image_label.setMinimumSize(1, 1)
        self.image_label.resize(pixmap.size())
        return PreviewImageInfo(
            path=image_path,
            original_width=original_size.width(),
            original_height=original_size.height(),
            display_width=pixmap.width(),
            display_height=pixmap.height(),
        )

    def clear_image(self, message: str | None = None) -> None:
        """Clear the current preview and show an optional empty-state message."""

        self.image_label.clear()
        self.image_label.setText(message if message is not None else tr("results.preview.none"))
        self.image_label.setMinimumSize(480, 320)
        self.image_label.resize(480, 320)

    def set_metadata(self, text: str) -> None:
        """Replace the technical metadata shown below the preview."""

        self.meta_text.setPlainText(text)
