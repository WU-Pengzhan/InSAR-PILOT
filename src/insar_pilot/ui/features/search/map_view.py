"""Native, network-free footprint map used by Workbench search results."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from PySide6.QtCore import QPointF, QRectF, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView

from insar_pilot.domain.search import RemoteSARProduct
from insar_pilot.download.geometry import polygons_from_geojson
from insar_pilot.ui.styles import active_tokens

_PRODUCT_ID_ROLE = 0


class SearchFootprintMap(QGraphicsView):
    """Display result footprints and expose selection only by product ID."""

    productSelected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        scene = QGraphicsScene(self)
        self.setScene(scene)
        self.setObjectName("workbenchSearchMap")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setFrameShape(QGraphicsView.Shape.StyledPanel)
        self._scene = scene
        self._items_by_product_id: dict[str, list[QGraphicsItem]] = {}
        self._selected_product_id: str | None = None
        self._batch_revision = 0
        self._scene.selectionChanged.connect(self._selection_changed)

    @property
    def batch_revision(self) -> int:
        return self._batch_revision

    @property
    def product_ids(self) -> tuple[str, ...]:
        return tuple(self._items_by_product_id)

    @property
    def selected_product_id(self) -> str | None:
        return self._selected_product_id

    def set_products(self, products: Iterable[RemoteSARProduct]) -> None:
        """Replace all markers in one scene update and fit the final extent once."""

        product_paths = [
            (product.remote_product_id, self._paths_for_footprint(product.footprint))
            for product in products
        ]
        self.setUpdatesEnabled(False)
        blocker = QSignalBlocker(self._scene)
        try:
            self._scene.clear()
            self._items_by_product_id.clear()
            self._selected_product_id = None
            all_points = [point for _product_id, paths in product_paths for path in paths for point in path]
            marker_radius = self._marker_radius(all_points)
            tokens = active_tokens()
            outline = QColor(tokens["accent"])
            fill = QColor(outline)
            fill.setAlpha(48)
            marker_fill = QColor(outline)
            marker_fill.setAlpha(180)
            for product_id, paths in product_paths:
                for path in paths:
                    if not path:
                        continue
                    polygon = QPolygonF(path)
                    item = self._scene.addPolygon(polygon, QPen(outline, 0), QBrush(fill))
                    self._configure_item(item, product_id)
                    self._items_by_product_id.setdefault(product_id, []).append(item)
                    center = polygon.boundingRect().center()
                    marker = self._scene.addEllipse(
                        center.x() - marker_radius,
                        center.y() - marker_radius,
                        marker_radius * 2,
                        marker_radius * 2,
                        QPen(outline, 0),
                        QBrush(marker_fill),
                    )
                    self._configure_item(marker, product_id)
                    self._items_by_product_id[product_id].append(marker)
            self._batch_revision += 1
        finally:
            del blocker
            self.setUpdatesEnabled(True)

        bounds = self._scene.itemsBoundingRect()
        if bounds.isValid() and not bounds.isEmpty():
            self.fitInView(bounds.adjusted(-1, -1, 1, 1), Qt.AspectRatioMode.KeepAspectRatio)
        self.viewport().update()

    def set_selected_product_id(self, product_id: str | None) -> None:
        blocker = QSignalBlocker(self._scene)
        try:
            self._scene.clearSelection()
            for item in self._items_by_product_id.get(product_id or "", ()):
                item.setSelected(True)
            self._selected_product_id = product_id if product_id in self._items_by_product_id else None
        finally:
            del blocker
        self.viewport().update()

    def _selection_changed(self) -> None:
        selected_ids = {
            str(item.data(_PRODUCT_ID_ROLE))
            for item in self._scene.selectedItems()
            if item.data(_PRODUCT_ID_ROLE)
        }
        product_id = next(iter(selected_ids), None)
        if product_id is None:
            return
        self.set_selected_product_id(product_id)
        self.productSelected.emit(product_id)

    @staticmethod
    def _paths_for_footprint(footprint: Mapping[str, object]) -> list[QPolygonF]:
        geometry = dict(footprint)
        return [
            QPolygonF([QPointF(longitude, -latitude) for longitude, latitude in path])
            for path in polygons_from_geojson(geometry)
            if path
        ]

    @staticmethod
    def _marker_radius(points: list[QPointF]) -> float:
        if not points:
            return 0.1
        bounds = QRectF(points[0], points[0])
        for point in points[1:]:
            bounds = bounds.united(QRectF(point, point))
        extent = float(max(bounds.width(), bounds.height()))
        return max(0.02, extent * 0.012)

    @staticmethod
    def _configure_item(item: QGraphicsItem, product_id: str) -> None:
        item.setData(_PRODUCT_ID_ROLE, product_id)
        item.setToolTip(product_id)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
