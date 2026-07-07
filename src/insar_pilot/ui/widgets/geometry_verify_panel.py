"""Geometry verify panel for AOI, bbox, and IW footprint overlays."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

Coord = tuple[float, float]  # (lon, lat)


@dataclass
class VerifyPlotData:
    aoi_geometries: list[list[Coord]]
    bbox_snwe: tuple[float, float, float, float] | None
    iw_polygons: dict[str, list[Coord]]
    selected_swaths: set[str]
    burst_polygons: dict[str, dict[int, list[Coord]]] = field(default_factory=dict)
    selected_bursts: set[tuple[str, int]] = field(default_factory=set)
    dem_bbox_snwe: tuple[float, float, float, float] | None = None
    highlighted_polygons: dict[str, list[Coord]] = field(default_factory=dict)


class GeometryVerifyPanel(QWidget):
    """Interactive verify plot with zoom and fit controls."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)
        self.status_label = QLabel("")
        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_out_button = QPushButton("Zoom Out")
        self.fit_button = QPushButton("Fit")
        self.zoom_in_button.setProperty("role", "secondary")
        self.zoom_out_button.setProperty("role", "secondary")
        self.fit_button.setProperty("role", "secondary")
        toolbar.addWidget(self.status_label, 1)
        toolbar.addWidget(self.zoom_in_button)
        toolbar.addWidget(self.zoom_out_button)
        toolbar.addWidget(self.fit_button)
        layout.addLayout(toolbar)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setBackgroundBrush(QBrush(QColor("#ffffff")))
        layout.addWidget(self.view, 1)

        self.zoom_in_button.clicked.connect(lambda: self._apply_zoom(1.2))
        self.zoom_out_button.clicked.connect(lambda: self._apply_zoom(1 / 1.2))
        self.fit_button.clicked.connect(self.fit_to_content)

    def set_plot(self, data: VerifyPlotData) -> None:
        self.scene.clear()
        all_points: list[QPointF] = []

        def to_point(lon: float, lat: float) -> QPointF:
            return QPointF(float(lon), float(-lat))

        # Draw IW polygons first.
        base_colors = {"1": "#8aa1bd", "2": "#7cbf87", "3": "#d6a061"}
        for swath, polygon in data.iw_polygons.items():
            if len(polygon) < 3:
                continue
            qpoly = QPolygonF([to_point(lon, lat) for lon, lat in polygon])
            all_points.extend(qpoly)
            selected = swath in data.selected_swaths
            color = QColor(base_colors.get(swath, "#8aa1bd"))
            fill = QColor(color)
            fill.setAlpha(90 if selected else 35)
            pen = QPen(QColor(color.darker(130 if selected else 110)))
            pen.setWidthF(2.0 if selected else 1.2)
            pen.setCosmetic(True)
            item = QGraphicsPolygonItem(qpoly)
            item.setPen(pen)
            item.setBrush(QBrush(fill))
            self.scene.addItem(item)

        # Draw burst footprints on top of IW footprints.
        for swath, bursts in data.burst_polygons.items():
            color = QColor(base_colors.get(swath, "#8aa1bd"))
            for burst_id, polygon in bursts.items():
                if len(polygon) < 3:
                    continue
                qpoly = QPolygonF([to_point(lon, lat) for lon, lat in polygon])
                all_points.extend(qpoly)
                selected = (swath, burst_id) in data.selected_bursts
                fill = QColor(color)
                fill.setAlpha(120 if selected else 26)
                pen = QPen(QColor(color.darker(155 if selected else 120)))
                pen.setWidthF(1.8 if selected else 0.9)
                pen.setCosmetic(True)
                item = QGraphicsPolygonItem(qpoly)
                item.setPen(pen)
                item.setBrush(QBrush(fill))
                self.scene.addItem(item)

        # Draw AOI geometries.
        aoi_pen = QPen(QColor("#2f5f94"))
        aoi_pen.setWidthF(2.0)
        aoi_pen.setCosmetic(True)
        for line in data.aoi_geometries:
            if len(line) < 2:
                continue
            points = [to_point(lon, lat) for lon, lat in line]
            all_points.extend(points)
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            item = QGraphicsPathItem(path)
            item.setPen(aoi_pen)
            self.scene.addItem(item)

        # Draw bbox.
        if data.bbox_snwe is not None:
            south, north, west, east = data.bbox_snwe
            rect = QRectF(QPointF(west, -north), QPointF(east, -south)).normalized()
            bbox_pen = QPen(QColor("#b64646"))
            bbox_pen.setWidthF(2.2)
            bbox_pen.setCosmetic(True)
            bbox_item = QGraphicsRectItem(rect)
            bbox_item.setPen(bbox_pen)
            bbox_item.setBrush(Qt.BrushStyle.NoBrush)
            self.scene.addItem(bbox_item)
            all_points.extend([rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()])

        # Draw highlighted footprints last so the current table row is obvious.
        highlight_pen = QPen(QColor("#f2c94c"))
        highlight_pen.setWidthF(3.0)
        highlight_pen.setCosmetic(True)
        highlight_fill = QColor("#f2c94c")
        highlight_fill.setAlpha(45)
        for polygon in data.highlighted_polygons.values():
            if len(polygon) < 3:
                continue
            qpoly = QPolygonF([to_point(lon, lat) for lon, lat in polygon])
            all_points.extend(qpoly)
            item = QGraphicsPolygonItem(qpoly)
            item.setPen(highlight_pen)
            item.setBrush(QBrush(highlight_fill))
            self.scene.addItem(item)

        # Draw DEM bounds for coverage check.
        if data.dem_bbox_snwe is not None:
            south, north, west, east = data.dem_bbox_snwe
            rect = QRectF(QPointF(west, -north), QPointF(east, -south)).normalized()
            dem_pen = QPen(QColor("#4f627c"))
            dem_pen.setStyle(Qt.PenStyle.DashLine)
            dem_pen.setWidthF(2.0)
            dem_pen.setCosmetic(True)
            dem_item = QGraphicsRectItem(rect)
            dem_item.setPen(dem_pen)
            dem_item.setBrush(Qt.BrushStyle.NoBrush)
            self.scene.addItem(dem_item)
            all_points.extend([rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()])

        if not all_points:
            self.status_label.setText("")
            self.scene.setSceneRect(QRectF(-1.0, -1.0, 2.0, 2.0))
            return

        xs = [point.x() for point in all_points]
        ys = [point.y() for point in all_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max(1e-6, max_x - min_x)
        height = max(1e-6, max_y - min_y)
        pad_x = width * 0.08
        pad_y = height * 0.08
        self.scene.setSceneRect(min_x - pad_x, min_y - pad_y, width + 2 * pad_x, height + 2 * pad_y)
        self.status_label.setText("")
        self.fit_to_content()

    def fit_to_content(self) -> None:
        rect = self.scene.sceneRect()
        if rect.width() <= 0.0 or rect.height() <= 0.0:
            return
        self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def export_png(self, output_path: str, width: int = 1600, height: int = 1100) -> str:
        path = Path(output_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(QColor("#ffffff"))
        painter = QPainter(image)
        self.scene.render(painter)
        painter.end()
        image.save(str(path), "PNG")
        return str(path)

    def _apply_zoom(self, factor: float) -> None:
        self.view.scale(factor, factor)
