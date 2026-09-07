"""Full-width radar-result catalog and visualization workbench."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.domain.project import VisualizationConfig
from insar_pilot.i18n import tr
from insar_pilot.services.result_catalog import ResultProduct
from insar_pilot.ui.styles import SPACE
from insar_pilot.ui.widgets.collapsible_section import CollapsibleSection
from insar_pilot.ui.widgets.preview_panel import PreviewPanel


class ResultsPage(QWidget):
    """Responsive results workspace without a permanently narrow side panel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._products: list[ResultProduct] = []
        self._custom_products: list[ResultProduct] = []
        self._image_dimensions = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["md"], SPACE["md"], SPACE["md"])
        layout.setSpacing(SPACE["sm"])

        layout.addWidget(self._build_product_bar())
        layout.addWidget(self._build_parameter_bar())
        layout.addWidget(self._build_advanced_section())

        self.preview_panel = PreviewPanel()
        self.preview_panel.setMinimumHeight(360)
        self.preview_panel.image_view.zoom_changed.connect(self._update_image_status)
        layout.addWidget(self.preview_panel, 1)

        layout.addWidget(self._build_status_strip())
        layout.addWidget(self._build_details_section())

        self.set_product_kind("")
        self.set_stale(False)

    def _build_product_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionPanel")
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        title = QLabel(tr("results.catalog.title"))
        title.setProperty("formLabel", True)
        self.product_type_combo = QComboBox()
        self.product_type_combo.addItem(tr("results.catalog.all"), "all")
        self.product_type_combo.addItem("SLC", "slc")
        self.product_type_combo.addItem("INT", "wrapped_interferogram")
        self.product_type_combo.addItem(tr("results.product.coherence"), "coherence")
        self.product_type_combo.addItem(tr("results.product.unwrapped"), "unwrapped_phase")
        self.product_type_combo.setMinimumWidth(150)

        self.product_combo = QComboBox()
        self.product_combo.setEditable(True)
        self.product_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.product_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.product_combo.setMinimumWidth(320)
        completer = self.product_combo.completer()
        if completer is not None:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

        self.refresh_products_button = QPushButton(tr("action.refresh_outputs"))
        self.refresh_products_button.setProperty("role", "secondary")
        self.open_other_button = QPushButton(tr("results.catalog.open_other"))
        self.open_other_button.setProperty("role", "secondary")

        row.addWidget(title)
        row.addWidget(self.product_type_combo)
        row.addWidget(self.product_combo, 1)
        row.addWidget(self.refresh_products_button)
        row.addWidget(self.open_other_button)
        return frame

    def _build_parameter_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionPanel")
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        self.render_style_label = self._form_label(tr("results.render_style.label"))
        self.render_style_combo = QComboBox()
        self.render_style_combo.addItem(tr("results.render_style.overlay"), "overlay")
        self.render_style_combo.addItem(tr("results.render_style.phase"), "phase")
        self.render_style_combo.setMinimumWidth(185)

        self.range_looks_label = self._form_label(tr("results.row.range_looks"))
        self.range_looks_spin = QSpinBox()
        self.range_looks_spin.setRange(1, 100)
        self.range_looks_spin.setValue(VisualizationConfig.SENTINEL1_RECOMMENDED_RANGE_LOOKS)
        self.range_looks_spin.setFixedWidth(72)
        self.azimuth_looks_label = self._form_label(tr("results.row.azimuth_looks"))
        self.azimuth_looks_spin = QSpinBox()
        self.azimuth_looks_spin.setRange(1, 100)
        self.azimuth_looks_spin.setValue(VisualizationConfig.SENTINEL1_RECOMMENDED_AZIMUTH_LOOKS)
        self.azimuth_looks_spin.setFixedWidth(72)

        self.brightness_label = self._form_label(tr("results.row.overlay_brightness"))
        self.brightness_spin = QDoubleSpinBox()
        self.brightness_spin.setRange(0.05, 5.0)
        self.brightness_spin.setDecimals(2)
        self.brightness_spin.setSingleStep(0.05)
        self.brightness_spin.setValue(0.5)
        self.brightness_spin.setFixedWidth(82)

        self.range_mode_label = self._form_label(tr("results.range_mode.label"))
        self.range_mode_combo = QComboBox()
        self.range_mode_combo.addItem(tr("results.range_mode.auto"), "auto")
        self.range_mode_combo.addItem(tr("results.range_mode.manual"), "manual")
        self.range_mode_combo.setMinimumWidth(110)

        self.range_min_spin = QDoubleSpinBox()
        self.range_min_spin.setRange(-1.0e9, 1.0e9)
        self.range_min_spin.setDecimals(3)
        self.range_min_spin.setPrefix("min ")
        self.range_min_spin.setFixedWidth(120)
        self.range_max_spin = QDoubleSpinBox()
        self.range_max_spin.setRange(-1.0e9, 1.0e9)
        self.range_max_spin.setDecimals(3)
        self.range_max_spin.setPrefix("max ")
        self.range_max_spin.setValue(1.0)
        self.range_max_spin.setFixedWidth(120)

        self.preview_button = QPushButton(tr("results.button.preview"))
        self.preview_button.setProperty("role", "primary")
        self.export_button = QToolButton()
        self.export_button.setText(tr("results.button.export"))
        self.export_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.export_menu = QMenu(self.export_button)
        self.export_png_action = self.export_menu.addAction(tr("results.button.export_png"))
        self.export_bmp_action = self.export_menu.addAction(tr("results.button.export_bmp"))
        self.export_button.setMenu(self.export_menu)
        self.export_button.setProperty("role", "secondary")
        self.export_button.setMinimumWidth(82)

        for widget in (
            self.render_style_label,
            self.render_style_combo,
            self.range_looks_label,
            self.range_looks_spin,
            self.azimuth_looks_label,
            self.azimuth_looks_spin,
            self.brightness_label,
            self.brightness_spin,
            self.range_mode_label,
            self.range_mode_combo,
            self.range_min_spin,
            self.range_max_spin,
        ):
            row.addWidget(widget)
        row.addStretch(1)
        row.addWidget(self.preview_button)
        row.addWidget(self.export_button)
        return frame

    def _build_advanced_section(self) -> CollapsibleSection:
        self.advanced_section = CollapsibleSection(tr("results.advanced.title"), expanded=False)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.crop_valid_check = QCheckBox(tr("results.crop_valid_extent.option"))
        self.crop_valid_check.setChecked(True)
        self.colormap_label = self._form_label(tr("results.colormap.label"))
        self.colormap_combo = QComboBox()
        self.colormap_combo.addItem("Viridis", "viridis")
        self.slc_background_label = self._form_label(tr("results.slc_background.label"))
        self.slc_background_edit = QLineEdit()
        self.slc_background_edit.setPlaceholderText(tr("results.slc_background.placeholder"))
        self.slc_background_edit.setToolTip(tr("results.slc_background.placeholder"))
        self.slc_background_browse_button = QPushButton(tr("action.browse"))
        self.slc_background_browse_button.setProperty("role", "secondary")

        row.addWidget(self.crop_valid_check)
        row.addWidget(self.colormap_label)
        row.addWidget(self.colormap_combo)
        row.addWidget(self.slc_background_label)
        row.addWidget(self.slc_background_edit, 1)
        row.addWidget(self.slc_background_browse_button)
        self.advanced_section.content_layout.addLayout(row)
        return self.advanced_section

    def _build_status_strip(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("statusStrip")
        row = QHBoxLayout(frame)
        row.setContentsMargins(4, 3, 4, 3)
        row.setSpacing(12)
        self.product_status_label = QLabel(tr("results.status.no_product"))
        self.image_status_label = QLabel("")
        self.render_status_label = QLabel(tr("results.status.ready"))
        self.render_status_label.setProperty("status", "neutral")
        row.addWidget(self.product_status_label, 1)
        row.addWidget(self.image_status_label)
        row.addWidget(self.render_status_label)
        return frame

    def _build_details_section(self) -> CollapsibleSection:
        self.details_section = CollapsibleSection(tr("results.details.title"), expanded=False)
        self.details_text = QPlainTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setPlaceholderText(tr("results.details.placeholder"))
        self.details_section.content_layout.addWidget(self.details_text)
        return self.details_section

    @staticmethod
    def _form_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("formLabel", True)
        return label

    def set_products(self, products: list[ResultProduct], selected_id: str = "") -> None:
        self._products = list(products)
        self._rebuild_product_combo(selected_id)

    def add_custom_product(self, product: ResultProduct) -> None:
        self._custom_products = [item for item in self._custom_products if item.product_id != product.product_id]
        self._custom_products.append(product)
        previous = self.product_type_combo.blockSignals(True)
        self.product_type_combo.setCurrentIndex(0)
        self.product_type_combo.blockSignals(previous)
        self._rebuild_product_combo(product.product_id)

    def filter_products(self) -> None:
        selected = self.current_product()
        self._rebuild_product_combo(selected.product_id if selected else "")

    def _rebuild_product_combo(self, selected_id: str) -> None:
        kind_filter = str(self.product_type_combo.currentData() or "all")
        previous = self.product_combo.blockSignals(True)
        self.product_combo.clear()
        visible = [*self._products, *self._custom_products]
        if kind_filter != "all":
            visible = [item for item in visible if item.kind == kind_filter]
        for product in visible:
            self.product_combo.addItem(self.product_label(product), product)
            index = self.product_combo.count() - 1
            self.product_combo.setItemData(index, product.path, Qt.ItemDataRole.ToolTipRole)
        selected_index = next(
            (
                index
                for index in range(self.product_combo.count())
                if self.product_combo.itemData(index).product_id == selected_id
            ),
            0 if self.product_combo.count() else -1,
        )
        self.product_combo.setCurrentIndex(selected_index)
        self.product_combo.blockSignals(previous)

    def current_product(self) -> ResultProduct | None:
        product = self.product_combo.currentData()
        return product if isinstance(product, ResultProduct) else None

    @property
    def product_count(self) -> int:
        return len(self._products) + len(self._custom_products)

    @staticmethod
    def product_label(product: ResultProduct) -> str:
        pair = product.pair_label
        if product.kind == "slc":
            role = tr(
                "results.product.reference"
                if product.variant == "reference"
                else "results.product.coregistered"
            )
            return f"SLC · {pair} · {role}" if pair else product.display_name
        if product.kind == "wrapped_interferogram":
            variant = tr(
                "results.product.filtered"
                if product.variant == "filtered"
                else "results.product.unfiltered"
            )
            return f"INT · {pair} · {variant}" if pair else product.display_name
        if product.kind == "coherence":
            return f"{tr('results.product.coherence')} · {pair}" if pair else product.display_name
        if product.kind == "unwrapped_phase":
            return f"{tr('results.product.unwrapped')} · {pair}" if pair else product.display_name
        return product.display_name

    def set_product_kind(self, kind: str) -> None:
        is_int = kind == "wrapped_interferogram"
        is_unwrapped = kind in {"unwrapped_phase", "custom_raster"}
        is_scalar = kind in {"coherence", "unwrapped_phase", "custom_raster"}
        is_overlay = is_int and str(self.render_style_combo.currentData() or "overlay") == "overlay"
        self._set_visible(self.render_style_label, is_int)
        self._set_visible(self.render_style_combo, is_int)
        self._set_visible(self.brightness_label, is_overlay)
        self._set_visible(self.brightness_spin, is_overlay)
        self._set_visible(self.range_mode_label, is_unwrapped)
        self._set_visible(self.range_mode_combo, is_unwrapped)
        manual = is_unwrapped and str(self.range_mode_combo.currentData() or "auto") == "manual"
        self._set_visible(self.range_min_spin, manual)
        self._set_visible(self.range_max_spin, manual)
        self._set_visible(self.colormap_label, is_scalar)
        self._set_visible(self.colormap_combo, is_scalar)
        self._set_visible(self.slc_background_label, is_overlay)
        self._set_visible(self.slc_background_edit, is_overlay)
        self._set_visible(self.slc_background_browse_button, is_overlay)
        self.crop_valid_check.setVisible(kind != "slc")
        self.preview_panel.set_color_legend_visible(is_scalar)

    @staticmethod
    def _set_visible(widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)

    def set_stale(self, stale: bool) -> None:
        self.render_status_label.setText(
            tr("results.status.stale") if stale else tr("results.status.ready")
        )
        self.render_status_label.setProperty("status", "warning" if stale else "success")
        self.render_status_label.style().unpolish(self.render_status_label)
        self.render_status_label.style().polish(self.render_status_label)

    def set_running(self, running: bool) -> None:
        self.preview_button.setText(
            tr("results.button.stop_preview") if running else tr("results.button.preview")
        )
        self.render_status_label.setText(
            tr("results.status.rendering") if running else tr("results.status.ready")
        )
        self.render_status_label.setProperty("status", "info" if running else "success")

    def browse_slc_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("results.dialog.select_secondary"),
            self.slc_background_edit.text(),
            tr("results.dialog.radar_files"),
        )
        if path:
            self.slc_background_edit.setText(path)

    def set_details(self, text: str) -> None:
        self.details_text.setPlainText(text)

    def set_image_dimensions(self, text: str) -> None:
        self._image_dimensions = text
        self._update_image_status()

    def _update_image_status(self, *_args) -> None:
        if not self._image_dimensions:
            self.image_status_label.setText("")
            return
        self.image_status_label.setText(
            f"{self._image_dimensions} · {self.preview_panel.zoom_factor * 100:.1f}%"
        )

    # Compatibility names used by the shell while the controller is being migrated.
    @property
    def visual_range_looks_spin(self) -> QSpinBox:
        return self.range_looks_spin

    @property
    def visual_azimuth_looks_spin(self) -> QSpinBox:
        return self.azimuth_looks_spin
