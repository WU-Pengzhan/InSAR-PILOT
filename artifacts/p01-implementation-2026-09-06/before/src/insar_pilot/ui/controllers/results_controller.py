"""Controller for the radar-product results workbench."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog, QMessageBox

from insar_pilot.domain.project import APP_METADATA_DIR
from insar_pilot.i18n import tr
from insar_pilot.services.result_catalog import ResultCatalogService, ResultProduct
from insar_pilot.services.visualization_service import VisualizationRequest, VisualizationService

if TYPE_CHECKING:
    from insar_pilot.ui.main_window import MainWindow


class ResultsController(QObject):
    """Coordinate logical-product discovery, rendering, preview, and export."""

    def __init__(
        self,
        window: MainWindow,
        *,
        result_catalog_service: ResultCatalogService,
        visualization_service: VisualizationService,
    ) -> None:
        super().__init__(window)
        self._window = window
        self.result_catalog_service = result_catalog_service
        self.visualization_service = visualization_service
        self._restoring = False

    @property
    def page(self):
        return self._window.results_page

    # ------------------------------------------------------------------
    # Catalog and form state
    # ------------------------------------------------------------------
    def refresh_outputs_view(self) -> None:
        """Compatibility entry point used by the toolbar and run monitor."""

        try:
            work_dir = self._window.project.resolved_work_dir()
        except ValueError:
            self.page.set_products([])
            self.page.product_status_label.setText(tr("results.status.no_product"))
            return

        products = self.result_catalog_service.discover(
            work_dir,
            reference_date=self._window.project.workflow.reference_date,
        )
        selected_id = self._window.project.visualization.selected_product_id
        if not selected_id:
            selected_id = self._legacy_product_id(products)
        if not selected_id and products:
            selected_id = self._preferred_initial_product(products).product_id
        self.page.set_products(products, selected_id)
        current = self.page.current_product()
        selection_changed = bool(
            self._window.project.visualization.selected_product_id
            and current is not None
            and current.product_id != self._window.project.visualization.selected_product_id
        )
        self._handle_product_selection(mark_stale=selection_changed)
        self._window.summary_results_card.set_value(
            tr("results.catalog.product_count", count=len(products))
        )
        self._window.summary_results_card.set_body(str(work_dir))
        self._window._refresh_navigation_status()

    def _legacy_product_id(self, products: list[ResultProduct]) -> str:
        legacy_path = self._window.project.visualization.primary_input_path.strip()
        if not legacy_path:
            return ""
        legacy = Path(legacy_path).expanduser()
        for product in products:
            candidate = Path(product.path).expanduser()
            if candidate == legacy or self._logical_path(candidate) == self._logical_path(legacy):
                return product.product_id
        return ""

    @staticmethod
    def _preferred_initial_product(products: list[ResultProduct]) -> ResultProduct:
        filtered_int = next(
            (
                product
                for product in reversed(products)
                if product.kind == "wrapped_interferogram" and product.variant == "filtered"
            ),
            None,
        )
        return filtered_int or products[0]

    @staticmethod
    def _logical_path(path: Path) -> str:
        text = str(path)
        for suffix in (".full.vrt", ".vrt", ".xml"):
            if text.lower().endswith(suffix):
                return text[: -len(suffix)]
        return text

    def filter_products(self) -> None:
        self.page.filter_products()
        self._handle_product_selection(mark_stale=True)

    def browse_custom_product(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(
            self._window,
            tr("results.catalog.open_other"),
            "",
            tr("results.dialog.radar_files"),
        )
        if not path_text:
            return
        try:
            product = self.result_catalog_service.product_from_path(Path(path_text))
        except ValueError as exc:
            self._window._show_error(tr("results.dialog.unsupported_product.title"), str(exc))
            return
        self.page.add_custom_product(product)
        self._handle_product_selection(mark_stale=True)

    def _handle_product_selection(self, *, mark_stale: bool = True) -> None:
        product = self.page.current_product()
        if product is None:
            self.page.set_product_kind("")
            self.page.product_status_label.setText(tr("results.status.no_product"))
            self.page.set_details("")
            self.page.preview_button.setEnabled(False)
            self.page.export_button.setEnabled(False)
            return

        self.page.preview_button.setEnabled(not self._window.runner.is_running())
        self.page.export_button.setEnabled(not self._window.runner.is_running())
        product_changed = product.product_id != self._window.project.visualization.selected_product_id
        if product.kind == "wrapped_interferogram":
            if product_changed and not self._restoring:
                self.page.render_style_combo.setCurrentIndex(
                    max(0, self.page.render_style_combo.findData("overlay"))
                )
            if (product_changed and not self._restoring) or not self.page.slc_background_edit.text().strip():
                self.page.slc_background_edit.setText(product.paired_slc_path)
        self.page.set_product_kind(product.kind)
        dimensions = (
            f"{product.width} × {product.height}"
            if product.width is not None and product.height is not None
            else tr("results.status.dimensions_unknown")
        )
        product_label = self.page.product_label(product)
        self.page.product_status_label.setText(product_label)
        if mark_stale or not self.page.preview_panel.image_view.has_image:
            self.page.set_image_dimensions(dimensions)
        if product.kind == "coherence":
            self.page.preview_panel.set_color_range(0.0, 1.0)
        elif product.kind == "unwrapped_phase" and self.page.range_mode_combo.currentData() == "manual":
            self.page.preview_panel.set_color_range(
                self.page.range_min_spin.value(), self.page.range_max_spin.value()
            )
        details = [
            f"Product: {product_label}",
            f"Product ID: {product.product_id}",
            f"Type: {product.kind}",
            f"Source: {product.path}",
        ]
        if product.paired_slc_path:
            details.append(f"Matched reference SLC: {product.paired_slc_path}")
        if product.warning:
            details.append(f"Warning: {product.warning}")
            self._window.statusBar().showMessage(product.warning, 8000)
        self.page.set_details("\n".join(details))
        self._window.project.visualization.selected_product_id = product.product_id
        self._window.project.visualization.primary_input_path = product.path
        if mark_stale:
            self.mark_preview_stale()

    def handle_product_selection(self) -> None:
        self._handle_product_selection(mark_stale=True)

    def update_mode_controls(self) -> None:
        product = self.page.current_product()
        self.page.set_product_kind(product.kind if product else "")
        self.mark_preview_stale()

    def update_range_controls(self) -> None:
        product = self.page.current_product()
        self.page.set_product_kind(product.kind if product else "")
        self.mark_preview_stale()

    def mark_preview_stale(self) -> None:
        if not self._restoring and self.page.current_product() is not None:
            self.page.set_stale(True)

    def restore_project_state(self) -> None:
        config = self._window.project.visualization
        self._restoring = True
        try:
            self.page.range_looks_spin.setValue(max(1, config.range_looks))
            self.page.azimuth_looks_spin.setValue(max(1, config.azimuth_looks))
            self.page.brightness_spin.setValue(max(0.05, config.overlay_brightness))
            self.page.crop_valid_check.setChecked(config.crop_valid_extent)
            style = config.render_style or ("phase" if config.mode == "interferogram" else "overlay")
            style_index = self.page.render_style_combo.findData(style)
            self.page.render_style_combo.setCurrentIndex(style_index if style_index >= 0 else 0)
            range_index = self.page.range_mode_combo.findData(config.range_mode)
            self.page.range_mode_combo.setCurrentIndex(range_index if range_index >= 0 else 0)
            self.page.range_min_spin.setValue(config.range_min if config.range_min is not None else 0.0)
            self.page.range_max_spin.setValue(config.range_max if config.range_max is not None else 1.0)
            self.page.slc_background_edit.setText(config.secondary_input_path)
            self.refresh_outputs_view()
        finally:
            self._restoring = False

        if config.last_preview_path:
            self._display_preview_image(config.last_preview_path, config.last_render_summary)
            self.page.set_stale(False)
        else:
            self.page.preview_panel.clear_image()
            self.page.set_stale(False)

    def update_project_from_form(self) -> None:
        product = self.page.current_product()
        config = self._window.project.visualization
        if product is not None:
            config.selected_product_id = product.product_id
            config.primary_input_path = product.path
            config.mode = self._legacy_mode(product)
        config.render_style = str(self.page.render_style_combo.currentData() or "overlay")
        config.secondary_input_path = self.page.slc_background_edit.text().strip()
        config.range_looks = self.page.range_looks_spin.value()
        config.azimuth_looks = self.page.azimuth_looks_spin.value()
        config.overlay_brightness = self.page.brightness_spin.value()
        config.crop_valid_extent = self.page.crop_valid_check.isChecked()
        config.colormap = str(self.page.colormap_combo.currentData() or "viridis")
        config.range_mode = str(self.page.range_mode_combo.currentData() or "auto")
        config.range_min = self.page.range_min_spin.value() if config.range_mode == "manual" else None
        config.range_max = self.page.range_max_spin.value() if config.range_mode == "manual" else None

    @staticmethod
    def _legacy_mode(product: ResultProduct) -> str:
        if product.kind == "slc":
            return "slc"
        if product.kind == "wrapped_interferogram":
            return "overlay"
        return product.kind

    # ------------------------------------------------------------------
    # Preview and export
    # ------------------------------------------------------------------
    def run_or_stop_preview(self) -> None:
        if self._window.runner.is_running() and self._window._pending_visualization is not None:
            self._window.run_controller.stop_execution()
            return
        self.run_visualization_preview()

    def run_visualization_preview(self) -> None:
        product = self.page.current_product()
        if product is None:
            return
        try:
            work_dir = self._window.project.resolved_work_dir()
        except ValueError as exc:
            self._window._show_error(tr("results.dialog.cannot_preview.title"), str(exc))
            return
        render_key = self._render_key(product)
        preview_dir = work_dir / APP_METADATA_DIR / "visualize" / "cache" / "latest"
        output = preview_dir / f"{render_key}_preview.png"
        metadata = output.with_suffix(".json")
        request = self._build_request(product, output, metadata)
        self._run_visualization(
            request,
            action="preview",
            render_signature=self.visualization_service.build_signature(request),
        )

    def run_visualization_export(self, suffix: str = ".png") -> None:
        product = self.page.current_product()
        if product is None:
            return
        suffix = suffix.lower()
        if suffix not in {".png", ".bmp"}:
            suffix = ".png"
        default_dir = self._preferred_visual_export_dir()
        if default_dir is None:
            return
        default_dir.mkdir(parents=True, exist_ok=True)
        initial = default_dir / f"{self._render_key(product)}{suffix}"
        caption = tr("results.dialog.export.caption")
        file_filter = (
            tr("results.dialog.export.png_filter")
            if suffix == ".png"
            else tr("results.dialog.export.bmp_filter")
        )
        output_text, _ = QFileDialog.getSaveFileName(self._window, caption, str(initial), file_filter)
        if not output_text:
            return
        output = Path(output_text).expanduser()
        if output.suffix.lower() != suffix:
            output = output.with_suffix(suffix)
        metadata = output.with_suffix(".json")
        request = self._build_request(product, output, metadata)
        signature = self.visualization_service.build_signature(request)
        if self._try_reuse_preview_for_export(signature, output, metadata):
            return
        self._run_visualization(request, action="export", render_signature=signature)

    def _build_request(
        self,
        product: ResultProduct,
        output_path: Path,
        metadata_path: Path,
    ) -> VisualizationRequest:
        self._window._update_project_from_form()
        config = self._window.project.visualization
        return VisualizationRequest(
            product_kind=product.kind,
            product_id=product.product_id,
            product_label=self.page.product_label(product),
            render_style=config.render_style,
            primary_input_path=product.path,
            secondary_input_path=config.secondary_input_path if config.render_style == "overlay" else "",
            range_looks=config.range_looks,
            azimuth_looks=config.azimuth_looks,
            overlay_brightness=config.overlay_brightness,
            crop_valid_extent=config.crop_valid_extent,
            colormap=config.colormap,
            range_mode=config.range_mode,
            range_min=config.range_min,
            range_max=config.range_max,
            work_dir=str(self._window.project.resolved_work_dir()),
            output_path=str(output_path),
            metadata_path=str(metadata_path),
        )

    @staticmethod
    def _render_key(product: ResultProduct) -> str:
        return product.product_id.replace(":", "_").replace("/", "_")

    def _try_reuse_preview_for_export(
        self,
        signature: str,
        destination: Path,
        metadata_destination: Path,
    ) -> bool:
        config = self._window.project.visualization
        preview = Path(config.last_preview_path).expanduser()
        preview_metadata = preview.with_suffix(".json")
        if destination.suffix.lower() != preview.suffix.lower():
            return False
        if config.last_render_signature != signature or not preview.is_file() or not preview_metadata.is_file():
            return False
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if preview.resolve() != destination.resolve():
                shutil.copy2(preview, destination)
            if preview_metadata.resolve() != metadata_destination.resolve():
                shutil.copy2(preview_metadata, metadata_destination)
        except OSError as exc:
            self._window._show_error(tr("dialog.export_failed.title"), str(exc))
            return False
        self.page.set_details(
            f"Status: export reused cached preview\nSource: {preview}\n"
            f"Output: {destination}\nMetadata: {metadata_destination}"
        )
        self._window.statusBar().showMessage(
            tr("results.status.export_reused", path=destination), 5000
        )
        return True

    def _run_visualization(
        self,
        request: VisualizationRequest,
        *,
        action: str,
        render_signature: str,
    ) -> None:
        if self._window.runner.is_running():
            QMessageBox.warning(self._window, tr("dialog.busy.title"), tr("dialog.busy.body"))
            return
        try:
            result = self.visualization_service.build(request, self._window.project.logs_dir())
        except Exception as exc:
            self._window._show_error(tr("results.dialog.visualization_setup_failed.title"), str(exc))
            return
        result.render_signature = render_signature
        result.action = action
        self._window._stop_requested = False
        self._window._pending_visualization = result
        self._window._last_visualization_saved_status = self._window.project.state.status
        self._window.project.state.current_step = "visualization"
        self._window.project.state.last_error = ""
        self._window.project_store.save(self._window.project)
        self.page.set_running(True)
        self.page.set_details(f"{result.summary}\n\nLog: {result.log_path}\n\nStatus: running")
        self.page.preview_panel.clear_image(tr("status.rendering_preview"))
        self._window.runner.run_queue([result.plan])
        self._window._update_action_states()
        self._window._set_current_page("results")

    def _display_preview_image(self, image_path: str, summary: str) -> None:
        path = Path(image_path).expanduser()
        try:
            info = self.page.preview_panel.load_image(path)
        except (FileNotFoundError, ValueError) as exc:
            self.page.preview_panel.clear_image(tr("results.preview.load_failed", path=path))
            self.page.set_details(f"{summary}\n\nPreview image: {path}\nError: {exc}")
            return
        metadata_text = ""
        metadata_path = path.with_suffix(".json")
        if metadata_path.is_file():
            try:
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                minimum = float(payload.get("display_range_min", 0.0))
                maximum = float(payload.get("display_range_max", 1.0))
                self.page.preview_panel.set_color_range(minimum, maximum)
                metadata_text = f"\nMetadata: {metadata_path}"
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                metadata_text = f"\nMetadata: unreadable ({metadata_path})"
        self.page.set_image_dimensions(f"{info.original_width} × {info.original_height}")
        self.page.set_details(
            f"{summary}\n\nPreview image: {info.path}\n"
            f"Image size: {info.original_width} × {info.original_height}{metadata_text}"
        )
        self.page.set_stale(False)

    @staticmethod
    def _is_legacy_visual_export_dir(path_text: str) -> bool:
        return Path(path_text).expanduser().name == "iscegui_visualize_exports"

    def _preferred_visual_export_dir(self) -> Path | None:
        try:
            configured = self._window.project.visualization.export_dir.strip()
            if configured and not self._is_legacy_visual_export_dir(configured):
                return Path(configured).expanduser()
            return self._window.project.metadata_dir() / "visualize" / "exports"
        except ValueError:
            return None
