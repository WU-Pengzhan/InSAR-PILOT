"""Inspector view for provider-neutral remote SAR products."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from insar_pilot.domain.search import RemoteSARProduct
from insar_pilot.i18n import tr


class ProductInspector(QWidget):
    """Render domain product fields without owning selection or search logic."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        self.empty_label = QLabel(tr("workbench.inspector.empty"))
        self.empty_label.setWordWrap(True)
        self.stack.addWidget(self.empty_label)

        detail = QWidget()
        form = QFormLayout(detail)
        self.product_id_label = QLabel()
        self.mission_label = QLabel()
        self.platform_label = QLabel()
        self.product_type_label = QLabel()
        self.acquisition_label = QLabel()
        self.provider_label = QLabel()
        form.addRow(tr("workbench.results.product_id"), self.product_id_label)
        form.addRow(tr("workbench.results.mission"), self.mission_label)
        form.addRow(tr("workbench.results.platform"), self.platform_label)
        form.addRow(tr("workbench.results.product_type"), self.product_type_label)
        form.addRow(tr("workbench.results.acquisition_time"), self.acquisition_label)
        form.addRow(tr("workbench.results.provider"), self.provider_label)
        self.stack.addWidget(detail)
        layout.addWidget(self.stack)
        layout.addStretch(1)
        self._product_id: str | None = None

    @property
    def product_id(self) -> str | None:
        return self._product_id

    def set_product(self, product: RemoteSARProduct | None) -> None:
        self._product_id = product.remote_product_id if product is not None else None
        if product is None:
            self.stack.setCurrentIndex(0)
            return
        self.product_id_label.setText(product.remote_product_id)
        self.mission_label.setText(product.mission)
        self.platform_label.setText(product.platform)
        self.product_type_label.setText(product.product_type)
        self.acquisition_label.setText(
            product.acquisition_time.isoformat() if product.acquisition_time is not None else ""
        )
        self.provider_label.setText(product.provider_id)
        self.stack.setCurrentIndex(1)
