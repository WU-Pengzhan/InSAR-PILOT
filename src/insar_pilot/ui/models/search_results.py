"""Model/View skeleton for mission-neutral remote search results."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from insar_pilot.domain.search import RemoteSARProduct
from insar_pilot.i18n import tr

_ROOT_INDEX = QModelIndex()


class SearchResultsTableModel(QAbstractTableModel):
    """Flat view model that accepts domain products, never provider SDK objects."""

    _HEADER_KEYS = (
        "workbench.results.product_id",
        "workbench.results.mission",
        "workbench.results.platform",
        "workbench.results.product_type",
        "workbench.results.acquisition_time",
        "workbench.results.orbit_direction",
        "workbench.results.relative_orbit",
        "workbench.results.polarizations",
        "workbench.results.provider",
    )

    def __init__(self, rows: Iterable[RemoteSARProduct] = (), parent=None) -> None:
        super().__init__(parent)
        self._result_rows: list[RemoteSARProduct] = list(rows)

    def rowCount(self, parent: QModelIndex = _ROOT_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._result_rows)

    def columnCount(self, parent: QModelIndex = _ROOT_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._HEADER_KEYS)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> object | None:
        row_index = int(index.row())
        column_index = int(index.column())
        if not index.isValid() or not 0 <= row_index < len(self._result_rows):
            return None
        if not 0 <= column_index < len(self._HEADER_KEYS):
            return None
        row = self._result_rows[row_index]
        if role == int(Qt.ItemDataRole.DisplayRole):
            return self._display_values(row)[column_index]
        if role == int(Qt.ItemDataRole.UserRole):
            return row
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> object | None:
        if role != int(Qt.ItemDataRole.DisplayRole):
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._HEADER_KEYS):
            return tr(self._HEADER_KEYS[section])
        if orientation == Qt.Orientation.Vertical and 0 <= section < len(self._result_rows):
            return section + 1
        return None

    def set_rows(self, rows: Iterable[RemoteSARProduct]) -> None:
        """Replace all displayed rows with one model reset."""

        self.beginResetModel()
        self._result_rows = list(rows)
        self.endResetModel()

    def clear(self) -> None:
        self.set_rows(())

    def result_at(self, index: QModelIndex) -> RemoteSARProduct | None:
        row_index = int(index.row())
        if not index.isValid() or not 0 <= row_index < len(self._result_rows):
            return None
        return self._result_rows[row_index]

    def product_for_id(self, product_id: str) -> RemoteSARProduct | None:
        return next(
            (product for product in self._result_rows if product.remote_product_id == product_id),
            None,
        )

    def index_for_product_id(self, product_id: str) -> QModelIndex:
        for row, product in enumerate(self._result_rows):
            if product.remote_product_id == product_id:
                return self.index(row, 0)
        return QModelIndex()

    @staticmethod
    def _display_values(product: RemoteSARProduct) -> tuple[str, ...]:
        acquisition_time = product.acquisition_time.isoformat() if product.acquisition_time is not None else ""
        return (
            product.remote_product_id,
            product.mission,
            product.platform,
            product.product_type,
            acquisition_time,
            product.orbit_direction or "",
            str(product.relative_orbit) if product.relative_orbit is not None else "",
            "+".join(product.polarizations),
            product.provider_id,
        )
