"""Reusable full-resolution preview image panel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QImageReader, QLinearGradient, QPainter, QPaintEvent, QWheelEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.i18n import tr


@dataclass(frozen=True)
class PreviewImageInfo:
    """Original and current viewport dimensions for a loaded image."""

    path: Path
    original_width: int
    original_height: int
    display_width: int
    display_height: int


class FullResolutionImageView(QAbstractScrollArea):
    """Viewport renderer that keeps source pixels and paints only the visible region."""

    zoom_changed = Signal(float)
    viewport_resized = Signal()
    _ZOOM_STEP = 1.2
    _MIN_ZOOM = 0.001
    _MAX_ZOOM = 8.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("fullResolutionImageView")
        self.setMinimumHeight(400)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._image = QImage()
        self._empty_message = tr("results.preview.none")
        self._zoom_factor = 1.0
        self._fit_mode = True

    @property
    def zoom_factor(self) -> float:
        return self._zoom_factor

    @property
    def image_size(self) -> QSize:
        return self._image.size()

    @property
    def has_image(self) -> bool:
        return not self._image.isNull()

    def set_image(self, image: QImage) -> None:
        """Retain the decoded source image without creating a reduced copy."""

        self._image = image
        self._empty_message = ""
        self._fit_mode = True
        self.fit_to_view()

    def clear_image(self, message: str) -> None:
        self._image = QImage()
        self._empty_message = message
        self._zoom_factor = 1.0
        self._fit_mode = True
        self._update_scrollbars()
        self.viewport().update()
        self.zoom_changed.emit(self._zoom_factor)

    def display_size(self) -> QSize:
        if self._image.isNull():
            return QSize()
        return QSize(
            max(1, round(self._image.width() * self._zoom_factor)),
            max(1, round(self._image.height() * self._zoom_factor)),
        )

    def zoom_by(self, multiplier: float, anchor: QPointF | None = None) -> None:
        if self._image.isNull():
            return
        self._fit_mode = False
        self._set_zoom(self._zoom_factor * multiplier, anchor)

    def fit_to_view(self) -> None:
        if self._image.isNull():
            return
        viewport = self.viewport().size()
        if viewport.width() <= 1 or viewport.height() <= 1:
            return
        width_ratio = (viewport.width() - 4) / self._image.width()
        height_ratio = (viewport.height() - 4) / self._image.height()
        self._fit_mode = True
        self._set_zoom(min(1.0, width_ratio, height_ratio))

    def _set_zoom(self, factor: float, anchor: QPointF | None = None) -> None:
        if self._image.isNull():
            return
        viewport = self.viewport()
        if anchor is None:
            anchor = QPointF(viewport.width() / 2.0, viewport.height() / 2.0)
        image_anchor = self._image_point_at(anchor)
        self._zoom_factor = max(self._MIN_ZOOM, min(self._MAX_ZOOM, factor))
        self._update_scrollbars()

        scaled_size = self.display_size()
        if scaled_size.width() > viewport.width():
            self.horizontalScrollBar().setValue(
                round(image_anchor.x() * self._zoom_factor - anchor.x())
            )
        if scaled_size.height() > viewport.height():
            self.verticalScrollBar().setValue(
                round(image_anchor.y() * self._zoom_factor - anchor.y())
            )
        viewport.update()
        self.zoom_changed.emit(self._zoom_factor)

    def _image_point_at(self, viewport_point: QPointF) -> QPointF:
        if self._image.isNull():
            return QPointF()
        origin = self._image_origin()
        return QPointF(
            (viewport_point.x() - origin.x()) / self._zoom_factor,
            (viewport_point.y() - origin.y()) / self._zoom_factor,
        )

    def _image_origin(self) -> QPointF:
        viewport = self.viewport().size()
        scaled = self.display_size()
        x = (
            (viewport.width() - scaled.width()) / 2.0
            if scaled.width() <= viewport.width()
            else -float(self.horizontalScrollBar().value())
        )
        y = (
            (viewport.height() - scaled.height()) / 2.0
            if scaled.height() <= viewport.height()
            else -float(self.verticalScrollBar().value())
        )
        return QPointF(x, y)

    def _update_scrollbars(self) -> None:
        scaled = self.display_size()
        viewport = self.viewport().size()
        horizontal = self.horizontalScrollBar()
        vertical = self.verticalScrollBar()
        horizontal.setPageStep(viewport.width())
        vertical.setPageStep(viewport.height())
        horizontal.setRange(0, max(0, scaled.width() - viewport.width()))
        vertical.setRange(0, max(0, scaled.height() - viewport.height()))

    def paintEvent(self, event) -> None:
        del event
        viewport = self.viewport()
        painter = QPainter(viewport)
        painter.fillRect(viewport.rect(), self.palette().base())
        if self._image.isNull():
            painter.setPen(self.palette().text().color())
            painter.drawText(viewport.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_message)
            return

        scaled = self.display_size()
        origin = self._image_origin()
        target = QRectF(origin, QSize(scaled.width(), scaled.height()))
        visible = target.intersected(QRectF(viewport.rect()))
        if visible.isEmpty():
            return
        source = QRectF(
            (visible.left() - target.left()) / self._zoom_factor,
            (visible.top() - target.top()) / self._zoom_factor,
            visible.width() / self._zoom_factor,
            visible.height() / self._zoom_factor,
        )
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self._zoom_factor < 1.0)
        painter.drawImage(visible, self._image, source)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.zoom_by(self._ZOOM_STEP ** (delta / 120.0), event.position())
                event.accept()
                return

        pixel_delta = event.pixelDelta().y()
        step = pixel_delta or round(
            event.angleDelta().y() / 120.0 * QApplication.wheelScrollLines() * 20
        )
        vertical = self.verticalScrollBar()
        horizontal = self.horizontalScrollBar()
        if vertical.maximum() > 0:
            vertical.setValue(vertical.value() - step)
        elif horizontal.maximum() > 0:
            horizontal.setValue(horizontal.value() - step)
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.viewport_resized.emit()
        if self._fit_mode and not self._image.isNull():
            QTimer.singleShot(0, self.fit_to_view)
        else:
            self._update_scrollbars()


class ColorLegend(QWidget):
    """Small Viridis legend drawn over scalar-result previews."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._minimum = 0.0
        self._maximum = 1.0
        self.setFixedSize(200, 52)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_range(self, minimum: float, maximum: float) -> None:
        self._minimum = minimum
        self._maximum = maximum
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(255, 255, 255, 225))
        gradient = QLinearGradient(10, 10, 190, 10)
        for position, color in (
            (0.0, QColor.fromRgbF(0.267004, 0.004874, 0.329415)),
            (0.25, QColor.fromRgbF(0.229739, 0.322361, 0.545706)),
            (0.5, QColor.fromRgbF(0.127568, 0.566949, 0.550556)),
            (0.75, QColor.fromRgbF(0.369214, 0.788888, 0.382914)),
            (1.0, QColor.fromRgbF(0.993248, 0.906157, 0.143936)),
        ):
            gradient.setColorAt(position, color)
        painter.fillRect(10, 9, 180, 17, gradient)
        painter.setPen(QColor(40, 44, 52))
        painter.drawRect(10, 9, 180, 17)
        painter.drawText(10, 31, 88, 17, Qt.AlignmentFlag.AlignLeft, f"{self._minimum:.3g}")
        painter.drawText(102, 31, 88, 17, Qt.AlignmentFlag.AlignRight, f"{self._maximum:.3g}")


class PreviewPanel(QWidget):
    """Full-resolution image viewport with smooth viewport-only scaling."""

    _DECODE_BYTES_PER_PIXEL = 4
    _ALLOCATION_HEADROOM_MB = 64

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)
        self.zoom_out_button = QPushButton("−")
        self.zoom_in_button = QPushButton("+")
        self.fit_button = QPushButton(tr("results.preview.fit"))
        self.actual_size_button = QPushButton(tr("results.preview.actual_size"))
        for button in (
            self.zoom_out_button,
            self.zoom_in_button,
            self.fit_button,
            self.actual_size_button,
        ):
            button.setProperty("role", "secondary")
            button.setMinimumWidth(36)
        self.zoom_label = QLabel("100%")
        self.zoom_hint_label = QLabel(tr("results.preview.zoom_hint"))
        self.zoom_hint_label.setObjectName("summaryCardBody")
        toolbar.addWidget(self.zoom_out_button)
        toolbar.addWidget(self.zoom_in_button)
        toolbar.addWidget(self.fit_button)
        toolbar.addWidget(self.actual_size_button)
        toolbar.addWidget(self.zoom_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.zoom_hint_label)
        layout.addLayout(toolbar)

        self.image_view = FullResolutionImageView()
        self.scroll_area = self.image_view
        layout.addWidget(self.image_view, 1)
        self._metadata = ""
        self.color_legend = ColorLegend(self.image_view.viewport())
        self.color_legend.hide()

        self.zoom_out_button.clicked.connect(
            lambda: self.image_view.zoom_by(1.0 / self.image_view._ZOOM_STEP)
        )
        self.zoom_in_button.clicked.connect(
            lambda: self.image_view.zoom_by(self.image_view._ZOOM_STEP)
        )
        self.fit_button.clicked.connect(self.image_view.fit_to_view)
        self.actual_size_button.clicked.connect(lambda: self.image_view._set_zoom(1.0))
        self.image_view.zoom_changed.connect(
            lambda factor: self.zoom_label.setText(f"{factor * 100:.1f}%")
        )
        self.image_view.viewport_resized.connect(self._position_color_legend)

    def load_image(self, path: str | Path) -> PreviewImageInfo:
        """Decode every source pixel and display it through a viewport renderer."""

        image_path = Path(path).expanduser()
        if not image_path.is_file():
            raise FileNotFoundError(f"Preview image was not found: {image_path}")

        reader = QImageReader(str(image_path))
        reader.setAutoTransform(True)
        if not reader.canRead():
            raise ValueError(reader.errorString() or f"Unsupported preview image: {image_path}")

        original_size = reader.size()
        previous_limit = QImageReader.allocationLimit()
        required_limit = self._required_allocation_limit_mb(original_size)
        allocation_was_raised = required_limit > previous_limit
        if allocation_was_raised:
            QImageReader.setAllocationLimit(required_limit)
        try:
            image = reader.read()
        finally:
            if allocation_was_raised:
                QImageReader.setAllocationLimit(previous_limit)
        if image.isNull():
            raise ValueError(reader.errorString() or f"Failed to decode preview image: {image_path}")
        if not original_size.isValid():
            original_size = image.size()

        self.image_view.set_image(image)
        display_size = self.image_view.display_size()
        return PreviewImageInfo(
            path=image_path,
            original_width=original_size.width(),
            original_height=original_size.height(),
            display_width=display_size.width(),
            display_height=display_size.height(),
        )

    @classmethod
    def _required_allocation_limit_mb(cls, size: QSize) -> int:
        if not size.isValid():
            return QImageReader.allocationLimit()
        byte_count = size.width() * size.height() * cls._DECODE_BYTES_PER_PIXEL
        mebibyte = 1024 * 1024
        decoded_mb = (byte_count + mebibyte - 1) // mebibyte
        return decoded_mb + cls._ALLOCATION_HEADROOM_MB

    @property
    def zoom_factor(self) -> float:
        return self.image_view.zoom_factor

    def zoom_by(self, multiplier: float, anchor: QPointF | None = None) -> None:
        self.image_view.zoom_by(multiplier, anchor)

    def fit_to_view(self) -> None:
        self.image_view.fit_to_view()

    def clear_image(self, message: str | None = None) -> None:
        self.image_view.clear_image(
            message if message is not None else tr("results.preview.none")
        )

    def set_metadata(self, text: str) -> None:
        """Retain metadata for compatibility; the page displays it in its details drawer."""

        self._metadata = text

    def set_color_legend_visible(self, visible: bool) -> None:
        self.color_legend.setVisible(visible)
        if visible:
            self._position_color_legend()

    def set_color_range(self, minimum: float, maximum: float) -> None:
        self.color_legend.set_range(minimum, maximum)

    def _position_color_legend(self) -> None:
        viewport = self.image_view.viewport()
        margin = 14
        self.color_legend.move(
            max(margin, viewport.width() - self.color_legend.width() - margin),
            max(margin, viewport.height() - self.color_legend.height() - margin),
        )
        self.color_legend.raise_()
