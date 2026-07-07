"""Results / visualization workflow controller extracted from MainWindow.

Owns output discovery, quicklook preview rendering, and the visualization
preview/export actions that shell out through the ProcessRunner. Behavior is
identical to the code that previously lived on ``MainWindow``; the controller
keeps a reference to the window for shell-level callbacks (error dialogs, action
state, navigation, and the shared visualization run state read by the run
monitor's command handlers).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTreeWidgetItem

from insar_pilot.domain.project import APP_METADATA_DIR
from insar_pilot.i18n import tr
from insar_pilot.services.output_discovery import OutputDiscoveryService, OutputNode
from insar_pilot.services.visualization_service import (
    VisualizationRequest,
    VisualizationService,
)

if TYPE_CHECKING:
    from insar_pilot.ui.main_window import MainWindow


class ResultsController(QObject):
    """Coordinates the results page: output discovery and visualization."""

    def __init__(
        self,
        window: MainWindow,
        *,
        output_discovery_service: OutputDiscoveryService,
        visualization_service: VisualizationService,
    ) -> None:
        super().__init__(window)
        self._window = window
        self.output_discovery_service = output_discovery_service
        self.visualization_service = visualization_service

    # ------------------------------------------------------------------
    # Browse / fill helpers
    # ------------------------------------------------------------------
    def _browse_visual_primary(self) -> None:
        self._window._browse_file_into(
            self._window.visual_primary_path_edit, tr("results.dialog.select_primary")
        )

    def _browse_visual_secondary(self) -> None:
        self._window._browse_file_into(
            self._window.visual_secondary_path_edit, tr("results.dialog.select_secondary")
        )

    def _browse_visual_export_dir(self) -> None:
        self._window._browse_dir_into(
            self._window.visual_export_dir_edit, tr("results.dialog.select_export_dir")
        )

    def _fill_visual_primary_from_outputs(self) -> None:
        selected = self._selected_output_file_path()
        if selected is None:
            QMessageBox.warning(
                self._window, tr("results.dialog.no_output.title"), tr("results.dialog.no_output.body")
            )
            return
        self._window.visual_primary_path_edit.setText(selected)

    def _fill_visual_secondary_from_outputs(self) -> None:
        selected = self._selected_output_file_path()
        if selected is None:
            QMessageBox.warning(
                self._window, tr("results.dialog.no_output.title"), tr("results.dialog.no_output.body")
            )
            return
        self._window.visual_secondary_path_edit.setText(selected)

    def _selected_output_file_path(self) -> str | None:
        item = self._window.outputs_tree.currentItem()
        if item is None:
            return None
        path_text = item.text(2).strip()
        if not path_text:
            return None
        path = Path(path_text).expanduser()
        if not path.exists() or not path.is_file():
            return None
        return str(path)

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------
    def _update_visualization_mode_ui(self) -> None:
        mode = str(self._window.visual_mode_combo.currentData() or "slc")
        is_overlay = mode == "overlay"
        self._window.results_page.set_overlay_fields_visible(is_overlay)
        if mode == "slc":
            self._window.visual_primary_path_edit.setPlaceholderText(tr("results.placeholder.slc"))
        elif mode == "interferogram":
            self._window.visual_primary_path_edit.setPlaceholderText(tr("results.placeholder.interferogram"))
        else:
            self._window.visual_primary_path_edit.setPlaceholderText(tr("results.placeholder.overlay_primary"))
            self._window.visual_secondary_path_edit.setPlaceholderText(
                tr("results.placeholder.overlay_secondary")
            )

    def run_visualization_preview(self) -> None:
        output_path = self._resolve_visualization_preview_output_path()
        if output_path is None:
            return
        request = self._build_visualization_request(output_path)
        if request is None:
            return
        signature = self.visualization_service.build_signature(request)
        self._run_visualization(request, action="preview", render_signature=signature)

    def run_visualization_export(self) -> None:
        output_path = self._resolve_visualization_export_output_path()
        if output_path is None:
            return
        request = self._build_visualization_request(output_path)
        if request is None:
            return
        signature = self.visualization_service.build_signature(request)
        if self._try_reuse_preview_for_export(signature, output_path):
            return
        self._run_visualization(request, action="export", render_signature=signature)

    def _build_visualization_request(self, output_path: str) -> VisualizationRequest | None:
        self._window._update_project_from_form()
        try:
            work_dir = str(self._window.project.resolved_work_dir())
        except ValueError as exc:
            self._window._show_error(tr("results.dialog.visualization_setup_failed.title"), str(exc))
            return None

        return VisualizationRequest(
            mode=str(self._window.visual_mode_combo.currentData() or "slc"),
            primary_input_path=self._window.visual_primary_path_edit.text().strip(),
            secondary_input_path=self._window.visual_secondary_path_edit.text().strip(),
            range_looks=self._window.visual_range_looks_spin.value(),
            azimuth_looks=self._window.visual_azimuth_looks_spin.value(),
            overlay_brightness=self._window.visual_overlay_brightness_spin.value(),
            work_dir=work_dir,
            output_bmp_path=output_path,
        )

    def _try_reuse_preview_for_export(self, signature: str, export_path: str) -> bool:
        preview_path = Path(self._window.project.visualization.last_preview_path).expanduser()
        if not preview_path.exists() or not preview_path.is_file():
            return False
        if self._window.project.visualization.last_render_signature != signature:
            return False

        destination = Path(export_path).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if preview_path.resolve() != destination.resolve():
                shutil.copy2(preview_path, destination)
        except OSError as exc:
            self._window._show_error(tr("dialog.export_failed.title"), f"Failed to copy preview image:\n{exc}")
            return False

        summary = self._window.project.visualization.last_render_summary.strip()
        details = summary if summary else "Reused latest preview."
        self._window.visual_status_text.setPlainText(
            f"{details}\n\nStatus: export reused cached preview\nSource: {preview_path}\nOutput: {destination}"
        )
        self._window.statusBar().showMessage(tr("results.status.export_reused", path=destination), 5000)
        self._window.project.state.last_error = ""
        self._window.project_store.save(self._window.project)
        return True

    def _resolve_visualization_preview_output_path(self) -> str | None:
        self._window._update_project_from_form()
        try:
            work_dir = self._window.project.resolved_work_dir()
        except ValueError as exc:
            self._window._show_error(tr("results.dialog.cannot_preview.title"), str(exc))
            return None
        mode = str(self._window.visual_mode_combo.currentData() or "slc")
        preview_dir = work_dir / APP_METADATA_DIR / "visualize" / "cache" / "latest"
        filename = f"{mode}_preview.bmp"
        return str(preview_dir / filename)

    def _resolve_visualization_export_output_path(self) -> str | None:
        self._window._update_project_from_form()
        export_dir_text = self._window.project.visualization.export_dir.strip()
        if export_dir_text:
            default_dir = Path(export_dir_text).expanduser()
        else:
            default_dir = self._preferred_visual_export_dir()
            if default_dir is None:
                self._window._show_error(
                    tr("results.dialog.export_setup_failed.title"),
                    tr("results.dialog.export_setup_failed.body"),
                )
                return None

        mode = str(self._window.visual_mode_combo.currentData() or "slc")
        initial = str(default_dir / f"{mode}_quicklook.bmp")
        output_path, _ = QFileDialog.getSaveFileName(
            self._window,
            tr("results.dialog.export_bmp.caption"),
            initial,
            tr("results.dialog.export_bmp.filter"),
        )
        if not output_path:
            return None
        self._window.visual_export_dir_edit.setText(str(Path(output_path).expanduser().parent))
        return output_path

    @staticmethod
    def _is_legacy_visual_export_dir(path_text: str) -> bool:
        path = Path(path_text).expanduser()
        return path.name == "iscegui_visualize_exports"

    def _preferred_visual_export_dir(self) -> Path | None:
        try:
            return self._window.project.metadata_dir() / "visualize" / "exports"
        except ValueError:
            return None

    def _run_visualization(self, request: VisualizationRequest, *, action: str, render_signature: str) -> None:
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

        self._window.visual_status_text.setPlainText(
            f"{result.summary}\n\nLog: {result.log_path}\n\nStatus: running ..."
        )
        self._window.preview_meta_text.setPlainText(
            f"{result.summary}\n\nOutput: {result.output_bmp_path}\nLog: {result.log_path}"
        )
        self._window.preview_image_label.setText(tr("status.rendering_preview"))
        self._window.preview_image_label.setPixmap(QPixmap())
        self._window.runner.run_queue([result.plan])
        self._window._update_action_states()
        self._window._set_current_page("results")

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------
    def refresh_outputs_view(self) -> None:
        self._window.outputs_tree.clear()
        try:
            work_dir = self._window.project.resolved_work_dir()
        except ValueError:
            self._window.results_page.empty_outputs_label.setVisible(True)
            self._window.summary_results_card.set_value(tr("summary.results_card.value"))
            self._window.summary_results_card.set_body(tr("results.card.resolve_work_dir"))
            return
        if not work_dir.exists():
            self._window.results_page.empty_outputs_label.setVisible(True)
            self._window.summary_results_card.set_value(tr("summary.results_card.value"))
            self._window.summary_results_card.set_body(tr("results.card.work_dir_missing"))
            return

        nodes = self.output_discovery_service.discover(work_dir)
        for node in nodes:
            self._window.outputs_tree.addTopLevelItem(self._output_item(node))
        self._window.outputs_tree.expandToDepth(1)
        self._window.results_page.empty_outputs_label.setVisible(
            self._window.outputs_tree.topLevelItemCount() == 0
        )
        self._window.summary_results_card.set_value(tr("results.card.output_roots", count=len(nodes)))
        self._window.summary_results_card.set_body(tr("results.card.outputs_discovered"))
        self._window.results_page.output_card.set_value(tr("results.card.output_roots", count=len(nodes)))
        self._window.results_page.output_card.set_body(str(work_dir))
        self._window._refresh_navigation_status()

    def _output_item(self, node: OutputNode) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.name, node.kind, node.path])
        for child in node.children:
            item.addChild(self._output_item(child))
        return item

    def _display_preview_image(self, image_path: str, summary: str) -> None:
        path = Path(image_path).expanduser()
        if not path.exists():
            self._window.preview_image_label.setPixmap(QPixmap())
            self._window.preview_image_label.setText(tr("results.preview.not_found", path=path))
            self._window.preview_image_label.resize(480, 320)
            self._window.preview_meta_text.setPlainText(summary)
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._window.preview_image_label.setPixmap(QPixmap())
            self._window.preview_image_label.setText(tr("results.preview.load_failed", path=path))
            self._window.preview_image_label.resize(480, 320)
        else:
            self._window.preview_image_label.setText("")
            self._window.preview_image_label.setPixmap(pixmap)
            self._window.preview_image_label.resize(pixmap.size())

        details = summary.strip()
        if details:
            details += "\n\n"
        if not pixmap.isNull():
            details += f"Preview image: {path}\nImage size: {pixmap.width()} x {pixmap.height()}"
        else:
            details += f"Preview image: {path}"
        self._window.preview_meta_text.setPlainText(details)
        self._window.results_page.preview_card.set_value(tr("card.value.ready"))
        self._window.results_page.preview_card.set_body(Path(image_path).name)
