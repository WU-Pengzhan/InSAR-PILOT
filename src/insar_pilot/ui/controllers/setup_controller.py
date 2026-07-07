"""Processing-setup workflow controller extracted from MainWindow.

Owns the three logical sub-domains of the merged processing-setup page:
data sources / environment validation and preparation, AOI / IW selection and
verification, and the processing plan / workflow generation. Behavior is
identical to the code that previously lived on ``MainWindow``; the controller
keeps a reference to the window for shell-level callbacks (error dialogs, form
sync, status/summary refresh, navigation) and the shared preparation state read
by the run monitor's queue handlers.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog, QMessageBox

from insar_pilot.domain.project import (
    APP_METADATA_DIR,
    PreparedInputs,
    ProjectStatus,
    WorkflowConfig,
)
from insar_pilot.i18n import tr
from insar_pilot.services.aoi_import import AoiImportService
from insar_pilot.services.command_plan import CommandPlan
from insar_pilot.services.dem_coverage import DemCoverageService
from insar_pilot.services.dem_preparer import DemPreparationService
from insar_pilot.services.env_probe import EnvironmentProbe
from insar_pilot.services.input_catalog import InputCatalogService
from insar_pilot.services.iw_recommendation import IwRecommendationResult, IwRecommendationService
from insar_pilot.services.preflight import PreflightReport, PreflightService
from insar_pilot.services.runfile_plan import count_commands, parse_run_file
from insar_pilot.services.stack_generator import StackWorkflowService
from insar_pilot.ui.widgets.geometry_verify_panel import VerifyPlotData

if TYPE_CHECKING:
    from insar_pilot.ui.main_window import MainWindow


class SetupController(QObject):
    """Coordinates the processing-setup page: sources, AOI/IW, and generation."""

    def __init__(
        self,
        window: MainWindow,
        *,
        environment_probe: EnvironmentProbe,
        input_catalog_service: InputCatalogService,
        dem_preparation_service: DemPreparationService,
        aoi_import_service: AoiImportService,
        iw_recommendation_service: IwRecommendationService,
        dem_coverage_service: DemCoverageService,
        workflow_service: StackWorkflowService,
        preflight_service: PreflightService,
    ) -> None:
        super().__init__(window)
        self._window = window
        self.environment_probe = environment_probe
        self.input_catalog_service = input_catalog_service
        self.dem_preparation_service = dem_preparation_service
        self.aoi_import_service = aoi_import_service
        self.iw_recommendation_service = iw_recommendation_service
        self.dem_coverage_service = dem_coverage_service
        self.workflow_service = workflow_service
        self.preflight_service = preflight_service

    # ------------------------------------------------------------------
    # Browse helpers
    # ------------------------------------------------------------------
    def _toggle_extract_widgets(self, checked: bool) -> None:
        self._window.data_sources_page.extract_dir_row.setEnabled(checked)

    def _browse_shell_init(self) -> None:
        self._window._browse_file_into(self._window.shell_init_edit, tr("setup.dialog.select_shell_init"))

    def _browse_isce_root(self) -> None:
        self._window._browse_dir_into(self._window.isce_root_edit, tr("setup.dialog.select_runtime_root"))

    def _browse_input_dir(self) -> None:
        self._window._browse_dir_into(self._window.input_path_edit, tr("setup.dialog.select_slc"))

    def _browse_orbit_dir(self) -> None:
        self._window._browse_dir_into(self._window.orbit_path_edit, tr("setup.dialog.select_orbit"))

    def _browse_dem_file(self) -> None:
        self._window._browse_file_into(self._window.dem_path_edit, tr("setup.dialog.select_dem"))

    def _browse_aux_dir(self) -> None:
        self._window._browse_dir_into(self._window.aux_path_edit, tr("setup.dialog.select_aux"))

    def _browse_work_dir(self) -> None:
        self._window._browse_dir_into(self._window.work_dir_edit, tr("setup.dialog.select_work"))

    def _browse_extract_dir(self) -> None:
        self._window._browse_dir_into(self._window.extract_dir_edit, tr("setup.dialog.select_safe"))

    def _browse_aoi_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self._window,
            tr("setup.dialog.select_aoi"),
            self._window.aoi_source_edit.text() or str(Path.home()),
            tr("setup.dialog.aoi_filter"),
        )
        if path:
            self._window.aoi_source_edit.setText(path)

    # ------------------------------------------------------------------
    # Data sources / environment
    # ------------------------------------------------------------------
    def validate_environment(self) -> None:
        self._window._update_project_from_form()
        report = self.environment_probe.probe(self._window.project.environment)
        self._window.project.state.last_validation = report.as_text()
        if report.ok and self._window.project.state.status == ProjectStatus.DRAFT:
            self._window.project.state.status = ProjectStatus.READY
        self._window.validation_text.setPlainText(report.as_text())
        self._window.refresh_status_labels()
        self._window._sync_summary_sidebar()
        self._window.statusBar().showMessage(tr("setup.status.env_validated"), 5000)

    def inspect_inputs(self) -> None:
        self._window._update_project_from_form()
        try:
            report = self.input_catalog_service.scan(Path(self._window.project.workflow.input_path))
        except Exception as exc:
            self._window._show_error(tr("setup.dialog.inspect_failed.title"), str(exc))
            return

        self._window._last_catalog_report = report
        self._window.inputs_text.setPlainText(report.as_text())
        self._window.data_sources_page.dataset_card.set_value(
            tr("setup.card.detected_inputs", count=len(report.entries))
        )
        self._window.data_sources_page.dataset_card.set_body(tr("setup.card.scan_complete"))
        self._window.statusBar().showMessage(tr("setup.status.inputs_inspected"), 5000)
        self._window._sync_summary_sidebar()

    def prepare_data_sources(self) -> None:
        self._window._update_project_from_form()
        if self._window.runner.is_running():
            QMessageBox.warning(self._window, tr("dialog.busy.title"), tr("dialog.busy.body"))
            return

        errors = self._validate_data_source_inputs()
        if errors:
            self._window._show_error(tr("setup.dialog.cannot_prepare.title"), "\n".join(errors))
            return

        self._window.log_view.clear()
        self._window._pending_preparation = None
        try:
            report = self.input_catalog_service.scan(Path(self._window.project.workflow.input_path))
            prepared = self.input_catalog_service.prepare_inputs(
                self._window.project.workflow,
                self._window.project.resolved_work_dir(),
                report,
                logger=self._window.append_log,
            )
            dem_preparation = self.dem_preparation_service.prepare(
                self._window.project.environment,
                self._window.project.workflow.dem_path,
                self._window.project.workflow.dem_height_reference,
                self._window.project.resolved_work_dir(),
                self._window.project.logs_dir(),
            )
        except Exception as exc:
            self._window.project.state.last_error = str(exc)
            self._window.project.state.status = ProjectStatus.FAILED
            self._window.refresh_status_labels()
            self._window._update_action_states()
            self._window._show_error(tr("setup.dialog.prepare_failed.title"), str(exc))
            return

        self._window._last_catalog_report = report
        if dem_preparation.notes:
            self._window.append_log("\n".join(dem_preparation.notes) + "\n")

        signature = self._preparation_signature(self._window.project.workflow)
        if not dem_preparation.plans:
            self._commit_preparation_result(prepared, dem_preparation.final_dem_path, signature)
            self._window.statusBar().showMessage(tr("setup.status.prepared"), 5000)
            return

        self._window.project.state.last_error = ""
        self._window.project.state.status = ProjectStatus.RUNNING
        self._window.project.state.current_step = "data preparation"
        self._window.project_store.save(self._window.project)
        self._window.refresh_status_labels()
        self._window._update_action_states()
        self._window._pending_preparation = {
            "prepared": prepared,
            "dem_path": dem_preparation.final_dem_path,
            "signature": signature,
        }
        self._window.runner.run_queue(dem_preparation.plans)

    def _preparation_signature(self, workflow: WorkflowConfig) -> str:
        payload = {
            "input_path": workflow.input_path,
            "orbit_path": workflow.orbit_path,
            "dem_path": workflow.dem_path,
            "dem_height_reference": workflow.dem_height_reference,
            "extract_zips": workflow.extract_zips,
            "extract_dir": workflow.extract_dir,
            "work_dir": workflow.work_dir,
        }
        return json.dumps(payload, sort_keys=True)

    def _is_prepared_for_current_sources(self) -> bool:
        state = self._window.project.state
        prepared = state.prepared_inputs
        if not state.prepared_signature:
            return False
        if state.prepared_signature != self._preparation_signature(self._window.project.workflow):
            return False
        if not prepared.entries or not prepared.manifest_path or not state.prepared_dem_path:
            return False
        if not Path(prepared.manifest_path).expanduser().exists():
            return False
        return Path(state.prepared_dem_path).expanduser().exists()

    def _clear_prepared_state(self) -> None:
        self._window.project.state.prepared_inputs = PreparedInputs()
        self._window.project.state.prepared_dem_path = ""
        self._window.project.state.prepared_signature = ""
        self._window._last_catalog_report = None
        self._render_preparation_summary()
        self._window._update_action_states()
        self._window._sync_summary_sidebar()

    def _render_preparation_summary(self) -> None:
        prepared = self._window.project.state.prepared_inputs
        workflow = self._window.project.workflow
        self._window.data_sources_page.orbit_card.set_value(
            Path(workflow.orbit_path).name if workflow.orbit_path else tr("card.value.not_set")
        )
        self._window.data_sources_page.dem_card.set_value(
            Path(workflow.dem_path).name if workflow.dem_path else tr("card.value.not_set")
        )
        if not prepared.entries:
            self._window.inputs_text.setPlainText(tr("setup.panel.not_prepared_hint"))
            self._window.data_sources_page.dataset_card.set_value(tr("card.value.not_prepared"))
            self._window.data_sources_page.dataset_card.set_body(tr("setup.card.prepare_hint"))
            return

        lines: list[str] = []
        lines.extend(prepared.notes)
        if self._window.project.state.prepared_dem_path:
            lines.extend(["", f"Prepared DEM: {self._window.project.state.prepared_dem_path}"])
        lines.extend(["", "Prepared inputs:"])
        lines.extend(f"- {entry.path}" for entry in prepared.entries)
        self._window.inputs_text.setPlainText("\n".join(lines))
        self._window.data_sources_page.dataset_card.set_value(
            tr("setup.card.prepared_scenes", count=len(prepared.entries))
        )
        self._window.data_sources_page.dataset_card.set_body(
            Path(prepared.manifest_path).name if prepared.manifest_path else tr("setup.card.manifest_ready")
        )

    def _commit_preparation_result(self, prepared: PreparedInputs, dem_path: str, signature: str) -> None:
        self._window.project.state.prepared_inputs = prepared
        self._window.project.state.prepared_dem_path = dem_path
        self._window.project.state.prepared_signature = signature
        self._window.project.state.last_error = ""
        self._window.project.state.status = ProjectStatus.READY
        self._window.project.state.current_step = "data preparation"
        self._window.project_store.save(self._window.project)
        self._populate_reference_candidates()
        self._render_preparation_summary()
        self._window.refresh_status_labels()
        self._window._update_action_states()
        self._window._sync_summary_sidebar()

    # ------------------------------------------------------------------
    # AOI / IW
    # ------------------------------------------------------------------
    def _toggle_common_overlap_mode(self, checked: bool) -> None:
        self._window.aoi_iw_page.set_bbox_enabled(not checked)
        if checked:
            self._window.aoi_iw_page.set_bbox_components("", "", "", "")
        self._window._update_project_from_form()

    def _sync_iw_selection_card(self) -> None:
        swaths = self._window.aoi_iw_page.selected_swaths() or "1 2 3"
        text = " ".join(f"IW{token}" for token in swaths.split()) if swaths.strip() else tr("setup.iw.none")
        self._window.aoi_iw_page.iw_card.set_value(text)
        self._window.summary_selection_card.set_value(text)
        self._window.summary_selection_card.set_body(tr("setup.card.swath_control"))

    def confirm_aoi_iw(self) -> None:
        self._window._update_project_from_form()
        errors = self._validate_processing_inputs()
        if errors:
            self._window._show_error(tr("setup.dialog.invalid_geometry.title"), "\n".join(errors))
            return
        self._window._sync_summary_sidebar()
        self._window.statusBar().showMessage(tr("setup.status.geometry_confirmed"), 4000)

    def import_aoi_file(self) -> None:
        source_path = self._window.aoi_source_edit.text().strip()
        if not source_path:
            self._window._show_error(
                tr("setup.dialog.aoi_import_failed.title"), tr("setup.dialog.aoi_import_failed.body")
            )
            return

        try:
            result = self.aoi_import_service.import_aoi(source_path)
        except Exception as exc:
            self._window._show_error(tr("setup.dialog.aoi_import_failed.title"), str(exc))
            return

        self._window._last_aoi_import = result
        self._window.use_common_overlap_check.setChecked(False)
        self._window.aoi_iw_page.set_bbox_enabled(True)
        south, north, west, east = result.bbox_snwe.split()
        self._window.aoi_iw_page.set_bbox_components(south, north, west, east)
        self._window.aoi_iw_page.source_card.set_value(Path(result.source_path).name)
        self._window.aoi_iw_page.source_card.set_body(tr("setup.card.source_used"))
        notes = list(result.notes)
        if result.warnings:
            notes.extend(["", "Warnings:"])
            notes.extend(f"- {line}" for line in result.warnings)
        self._window.verify_notes.setPlainText("\n".join(notes))
        self._window.aoi_iw_page.verify_alert_label.clear()
        self._window.aoi_iw_page.verify_alert_label.hide()
        self._window._update_project_from_form()
        self.recommend_iw()
        self._window.statusBar().showMessage(tr("setup.status.aoi_imported"), 5000)

    def _first_entry_for_iw_recommendation(self) -> str:
        prepared = self._window.project.state.prepared_inputs.entries
        if prepared:
            return prepared[0].path

        input_dir = Path(self._window.project.workflow.input_path).expanduser()
        if not input_dir.is_dir():
            raise ValueError("Prepare data first or set a valid SLC folder.")
        report = self.input_catalog_service.scan(input_dir)
        if not report.entries:
            raise ValueError("No Sentinel-1 ZIP/SAFE inputs were found for IW recommendation.")
        return report.entries[0].path

    def _current_aoi_geometries(self) -> list[list[tuple[float, float]]]:
        source_path = self._window.aoi_source_edit.text().strip()
        if not source_path:
            return self._window._last_aoi_import.geometries if self._window._last_aoi_import else []
        if self._window._last_aoi_import and Path(self._window._last_aoi_import.source_path) == Path(
            source_path
        ).expanduser():
            return self._window._last_aoi_import.geometries
        try:
            self._window._last_aoi_import = self.aoi_import_service.import_aoi(source_path)
        except Exception:
            return self._window._last_aoi_import.geometries if self._window._last_aoi_import else []
        return self._window._last_aoi_import.geometries

    def recommend_iw(self) -> None:
        self._window._update_project_from_form()
        self._window.aoi_iw_page.verify_alert_label.clear()
        self._window.aoi_iw_page.verify_alert_label.hide()
        if self._window.project.workflow.use_common_overlap:
            self._window._show_error(
                tr("setup.dialog.iw_unavailable.title"),
                tr("setup.dialog.iw_unavailable.disable_overlap"),
            )
            return
        if not self._window.project.workflow.bbox_snwe.strip():
            self._window._show_error(
                tr("setup.dialog.iw_unavailable.title"), tr("setup.dialog.iw_unavailable.bbox_required")
            )
            return

        try:
            basis_entry = self._first_entry_for_iw_recommendation()
            result = self.iw_recommendation_service.recommend(
                basis_entry,
                self._window.project.workflow.normalized_bbox(),
            )
        except Exception as exc:
            self._window._show_error(tr("setup.dialog.iw_failed.title"), str(exc))
            return

        self._window._last_iw_recommendation = result
        self._window.aoi_iw_page.set_selected_swaths(result.recommended_swaths)
        self._sync_iw_selection_card()
        notes = list(result.notes)
        if result.warnings:
            notes.extend(["", "Warnings:"])
            notes.extend(f"- {line}" for line in result.warnings)
        self._window.verify_notes.setPlainText("\n".join(notes))
        self._window._update_project_from_form()
        self._window.statusBar().showMessage(
            tr("setup.status.recommended_iw", swaths=result.recommended_swaths), 5000
        )

    def _selected_swath_set(self) -> set[str]:
        return {item for item in (self._window.aoi_iw_page.selected_swaths() or "").split() if item}

    def _selected_auto_burst_pairs(self, recommendation: IwRecommendationResult) -> set[tuple[str, int]]:
        selected_swaths = self._selected_swath_set()
        pairs: set[tuple[str, int]] = set()
        for swath, burst_ids in recommendation.auto_selected_bursts.items():
            if selected_swaths and swath not in selected_swaths:
                continue
            for burst_id in burst_ids:
                pairs.add((swath, burst_id))
        return pairs

    @staticmethod
    def _union_bbox_from_bursts(
        recommendation: IwRecommendationResult,
        pairs: set[tuple[str, int]],
    ) -> tuple[float, float, float, float] | None:
        if not pairs:
            return None
        bboxes: list[tuple[float, float, float, float]] = []
        for swath, burst_id in pairs:
            for burst in recommendation.bursts.get(swath, []):
                if burst.burst_id == burst_id:
                    bboxes.append(burst.bbox_snwe)
                    break
        if not bboxes:
            return None
        south = min(item[0] for item in bboxes)
        north = max(item[1] for item in bboxes)
        west = min(item[2] for item in bboxes)
        east = max(item[3] for item in bboxes)
        return south, north, west, east

    def verify_aoi_iw_geometry(self) -> None:
        self._window._update_project_from_form()
        self._window.aoi_iw_page.verify_alert_label.clear()
        self._window.aoi_iw_page.verify_alert_label.hide()
        if self._window.project.workflow.use_common_overlap or not self._window.project.workflow.bbox_snwe.strip():
            self._window._show_error(
                tr("setup.dialog.verify_unavailable.title"),
                tr("setup.dialog.verify_unavailable.body"),
            )
            return

        try:
            bbox_text = self._window.project.workflow.normalized_bbox()
            south, north, west, east = [float(token) for token in bbox_text.split()]
            basis_entry = self._first_entry_for_iw_recommendation()
            self._window._last_iw_recommendation = self.iw_recommendation_service.recommend(basis_entry, bbox_text)
        except Exception as exc:
            self._window._show_error(tr("setup.dialog.verify_failed.title"), str(exc))
            return

        footprints = {
            swath: item.polygon
            for swath, item in self._window._last_iw_recommendation.footprints.items()
        }
        burst_polygons = {
            swath: {item.burst_id: item.polygon for item in bursts}
            for swath, bursts in self._window._last_iw_recommendation.bursts.items()
        }
        selected_burst_pairs = self._selected_auto_burst_pairs(self._window._last_iw_recommendation)
        burst_union_bbox = self._union_bbox_from_bursts(self._window._last_iw_recommendation, selected_burst_pairs)

        dem_bbox = None
        coverage_notes: list[str] = []
        coverage_warnings: list[str] = []
        if self._window.project.state.prepared_dem_path and burst_union_bbox is not None:
            try:
                coverage = self.dem_coverage_service.assess(
                    self._window.project.state.prepared_dem_path,
                    burst_union_bbox,
                )
                dem_bbox = coverage.dem_bbox_snwe
                coverage_notes.extend(coverage.notes)
                coverage_warnings.extend(coverage.warnings)
            except Exception as exc:
                coverage_warnings.append(f"DEM coverage assessment failed: {exc}")
        elif not self._window.project.state.prepared_dem_path:
            coverage_warnings.append("Prepared DEM path is empty; DEM coverage was not assessed.")
        else:
            coverage_warnings.append("No auto-selected burst intersects the selected IW + bbox.")

        plot = VerifyPlotData(
            aoi_geometries=list(self._current_aoi_geometries()),
            bbox_snwe=(south, north, west, east),
            iw_polygons=footprints,
            selected_swaths=set((self._window.aoi_iw_page.selected_swaths() or "").split()),
            burst_polygons=burst_polygons,
            selected_bursts=selected_burst_pairs,
            dem_bbox_snwe=dem_bbox,
        )
        self._window.aoi_iw_page.verify_panel.set_plot(plot)

        notes = []
        if self._window._last_aoi_import:
            notes.append(f"AOI source: {self._window._last_aoi_import.source_path}")
        notes.append(f"Processing bbox (SNWE): {bbox_text}")
        notes.append(f"Selected IW: {self._window.aoi_iw_page.selected_swaths() or '-'}")
        if selected_burst_pairs:
            by_swath: dict[str, list[int]] = {}
            for swath, burst_id in sorted(selected_burst_pairs):
                by_swath.setdefault(swath, []).append(burst_id)
            for swath, ids in sorted(by_swath.items()):
                notes.append(f"IW{swath} auto-selected bursts: {', '.join(str(item) for item in ids)}")
        else:
            notes.append("Auto-selected bursts: none")
        if burst_union_bbox is not None:
            notes.append(
                "Auto-selected burst union bbox (SNWE): "
                + " ".join(f"{value:g}" for value in burst_union_bbox)
            )
        if self._window._last_iw_recommendation:
            notes.extend(self._window._last_iw_recommendation.notes)
            if self._window._last_iw_recommendation.warnings:
                notes.extend(["", "Warnings:"])
                notes.extend(f"- {line}" for line in self._window._last_iw_recommendation.warnings)
        if coverage_notes:
            notes.extend(["", "DEM coverage:"])
            notes.extend(coverage_notes)
        if coverage_warnings:
            notes.extend(["", "Coverage warnings:"])
            notes.extend(f"- {line}" for line in coverage_warnings)
            self._window.aoi_iw_page.verify_alert_label.setText(f"DEM coverage warning: {coverage_warnings[0]}")
            self._window.aoi_iw_page.verify_alert_label.show()
        else:
            self._window.aoi_iw_page.verify_alert_label.clear()
            self._window.aoi_iw_page.verify_alert_label.hide()
        self._window.verify_notes.setPlainText("\n".join(notes))
        self._window.statusBar().showMessage(tr("setup.status.verify_updated"), 5000)

    def export_verify_geometry_png(self) -> None:
        try:
            work_dir = self._window.project.resolved_work_dir()
        except ValueError:
            self._window._show_error(
                tr("dialog.export_failed.title"), tr("setup.dialog.export_failed.work_dir")
            )
            return
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        default_path = work_dir / APP_METADATA_DIR / "verify" / f"aoi_iw_verify_{stamp}.png"
        output_path, _ = QFileDialog.getSaveFileName(
            self._window,
            tr("setup.dialog.export_verify.caption"),
            str(default_path),
            tr("setup.dialog.export_verify.filter"),
        )
        if not output_path:
            return
        if not output_path.lower().endswith(".png"):
            output_path = f"{output_path}.png"
        try:
            saved = self._window.aoi_iw_page.verify_panel.export_png(output_path)
        except Exception as exc:
            self._window._show_error(tr("dialog.export_failed.title"), str(exc))
            return
        self._window.statusBar().showMessage(tr("setup.status.verify_exported", path=saved), 5000)

    # ------------------------------------------------------------------
    # Processing plan / generation
    # ------------------------------------------------------------------
    def generate_workflow(self) -> None:
        self._window._update_project_from_form()
        errors = self._validate_generation_inputs()
        report = self._refresh_preflight_report()
        errors.extend(
            f"Preflight: {check.label}: {check.detail}"
            for check in report.blockers
            if f"Preflight: {check.label}: {check.detail}" not in errors
        )
        if errors:
            self._window._show_error(tr("setup.dialog.cannot_generate.title"), "\n".join(errors))
            return

        self._window.log_view.clear()
        try:
            command = self.workflow_service.build_generate_command(
                self._window.project,
                self._window.project.state.prepared_inputs,
                dem_path=self._window.project.state.prepared_dem_path,
            )
            self._window.project.state.last_generated_command = command
            if hasattr(self._window.command_preview_text, "set_metadata"):
                self._window.command_preview_text.set_metadata(
                    f"Work directory: {self._window.project.resolved_work_dir()} | "
                    f"Log: {self._window.project.logs_dir() / 'stack_generate.log'}"
                )
            self._window.command_preview_text.setPlainText(command)
            self._window.project.state.last_error = ""
            self._window.project.state.current_step = "workflow generation"
            self._window.project.state.status = ProjectStatus.RUNNING
            self._window.project_store.save(self._window.project)
        except Exception as exc:
            self._window.project.state.last_error = str(exc)
            self._window.project.state.status = ProjectStatus.FAILED
            self._window.refresh_status_labels()
            self._window._show_error(tr("setup.dialog.generate_setup_failed.title"), str(exc))
            return

        plan = CommandPlan(
            label="Generate processing workflow",
            command=command,
            cwd=str(self._window.project.resolved_work_dir()),
            log_path=str(self._window.project.logs_dir() / "stack_generate.log"),
            step_name="workflow generation",
            is_generation=True,
            kind="generation",
        )
        self._window.runner.run_queue([plan])
        self._window.refresh_status_labels()
        self._window._set_current_page("monitor")

    def _preview_generate_command(self) -> None:
        self._window._update_project_from_form()
        self._refresh_preflight_report()
        if not self._is_prepared_for_current_sources():
            self._window.command_preview_text.setPlainText(tr("setup.panel.prepare_command_hint"))
            return
        try:
            command = self.workflow_service.build_generate_command(
                self._window.project,
                self._window.project.state.prepared_inputs,
                dem_path=self._window.project.state.prepared_dem_path,
            )
        except Exception as exc:
            self._window.command_preview_text.setPlainText(f"Preview unavailable:\n{exc}")
            return
        if hasattr(self._window.command_preview_text, "set_metadata"):
            self._window.command_preview_text.set_metadata(
                f"Work directory: {self._window.project.resolved_work_dir()} | "
                f"Log: {self._window.project.logs_dir() / 'stack_generate.log'}"
            )
        self._window.command_preview_text.setPlainText(command)
        self._window.statusBar().showMessage(tr("setup.status.preview_updated"), 3000)

    def _rescan_existing_runfiles(self) -> None:
        try:
            self.workflow_service.synchronize_project_steps(self._window.project)
        except Exception as exc:
            self._window._show_error(tr("setup.dialog.rescan_failed.title"), str(exc))
            return
        self._window.run_controller.refresh_steps_view()
        self._window.refresh_status_labels()
        self._window._sync_summary_sidebar()
        self._window.statusBar().showMessage(tr("setup.status.rescanned"), 4000)

    def _populate_reference_candidates(self) -> None:
        dates = self._prepared_dates()
        recommended = dates[0] if dates else "Unavailable"
        self._window.processing_page.reference_hint_label.setText(
            tr("setup.hint.reference_recommended", date=recommended)
            if dates
            else tr("setup.hint.reference_run_prepare")
        )

    def _prepared_dates(self) -> list[str]:
        dates: set[str] = set()
        for entry in self._window.project.state.prepared_inputs.entries:
            match = re.search(r"(20\d{6})", Path(entry.path).name)
            if match:
                dates.add(match.group(1))
        return sorted(dates)

    def _refresh_runfile_estimates(self) -> None:
        current_parallel = max(1, self._window.project.workflow.num_proc)
        if not self._window.project.state.steps:
            text = tr("setup.panel.estimate_hint")
            self._window.runfile_estimate_text.setPlainText(text)
            self._window.monitor_runfile_estimate_text.setPlainText(text)
            self._window.processing_page.parallel_card.set_value(
                tr("setup.card.parallel_value", value=current_parallel)
            )
            return

        lines = [f"Current num_proc = {current_parallel}", ""]
        for step in self._window.project.state.steps:
            try:
                batches = parse_run_file(Path(step.path))
                command_count = count_commands(batches)
            except Exception as exc:
                lines.append(f"{step.name}: cannot parse run_file ({exc})")
                continue
            suggested = min(current_parallel, max(command_count, 1))
            lines.append(
                f"{step.name}: {command_count} commands, suggested parallel={suggested} "
                f"(num_proc={current_parallel})"
            )
        text = "\n".join(lines)
        self._window.runfile_estimate_text.setPlainText(text)
        self._window.monitor_runfile_estimate_text.setPlainText(text)
        self._window.processing_page.parallel_card.set_value(
            tr("setup.card.parallel_value", value=current_parallel)
        )
        self._window.processing_page.parallel_card.set_body(tr("setup.card.parallel_body"))

    def _refresh_preflight_report(self) -> PreflightReport:
        try:
            report = self.preflight_service.run(self._window.project, self._window.project.state.prepared_inputs)
        except Exception as exc:
            report = PreflightReport()
            self._window.preflight_text.setPlainText(f"Preflight unavailable:\n{exc}")
            return report

        if hasattr(self._window.processing_page, "preflight_check_list"):
            self._window.processing_page.preflight_check_list.set_report(report)
        if hasattr(self._window.processing_page, "preflight_alert"):
            if report.blockers:
                self._window.processing_page.preflight_alert.set_message(
                    tr("preflight.blocked", count=len(report.blockers)),
                    "blocker",
                )
            elif report.warnings:
                self._window.processing_page.preflight_alert.set_message(
                    tr("preflight.warning", count=len(report.warnings)),
                    "warning",
                )
            else:
                self._window.processing_page.preflight_alert.set_message(
                    tr("preflight.ready"), "info"
                )

        header = (
            f"Preflight found {len(report.blockers)} blocker(s). Resolve them before generation."
            if report.blockers
            else "Preflight complete. No blockers found."
        )
        if report.warnings:
            header += f"\nWarnings: {len(report.warnings)}"
        if not hasattr(self._window.processing_page, "preflight_check_list"):
            self._window.preflight_text.setPlainText(f"{header}\n\n{report.as_text()}")
        return report

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def _validate_data_source_inputs(self) -> list[str]:
        errors: list[str] = []
        workflow = self._window.project.workflow

        if not workflow.input_path:
            errors.append("SLC folder is required.")
        elif not Path(workflow.input_path).expanduser().is_dir():
            errors.append(f"SLC folder was not found: {workflow.input_path}")

        if not workflow.orbit_path:
            errors.append("Orbit folder is required.")
        elif not Path(workflow.orbit_path).expanduser().is_dir():
            errors.append(f"Orbit folder was not found: {workflow.orbit_path}")

        if not workflow.dem_path:
            errors.append("DEM path is required.")
        elif not Path(workflow.dem_path).expanduser().exists():
            errors.append(f"DEM path was not found: {workflow.dem_path}")
        elif Path(workflow.dem_path).suffix.lower() in {".tif", ".tiff"} and workflow.dem_height_reference not in {
            "egm96",
            "egm2008",
            "wgs84",
        }:
            errors.append(
                "Choose the GeoTIFF DEM height reference: EGM96 geoid, EGM2008 geoid, or WGS84 ellipsoid."
            )

        if workflow.aux_path and not Path(workflow.aux_path).expanduser().is_dir():
            errors.append(f"AUX folder was not found: {workflow.aux_path}")

        if workflow.extract_zips and workflow.extract_dir:
            extract_dir = Path(workflow.extract_dir).expanduser()
            if extract_dir.exists() and not extract_dir.is_dir():
                errors.append(f"Extracted SAFE directory is not a directory: {workflow.extract_dir}")

        return errors

    def _validate_processing_inputs(self) -> list[str]:
        errors: list[str] = []
        workflow = self._window.project.workflow

        if workflow.use_common_overlap:
            if workflow.bbox_snwe.strip():
                try:
                    workflow.normalized_bbox()
                except ValueError as exc:
                    errors.append(str(exc))
        else:
            if not workflow.bbox_snwe.strip():
                errors.append("Processing bbox (SNWE) is required unless 'Use common overlap' is enabled.")
            else:
                try:
                    workflow.normalized_bbox()
                except ValueError as exc:
                    errors.append(str(exc))

        if not workflow.swath_numbers.strip():
            errors.append("At least one IW swath must be selected.")
        if workflow.azimuth_looks < 1:
            errors.append("Azimuth looks must be >= 1.")
        if workflow.range_looks < 1:
            errors.append("Range looks must be >= 1.")
        if workflow.reference_date and (len(workflow.reference_date) != 8 or not workflow.reference_date.isdigit()):
            errors.append("Reference date must use YYYYMMDD format when provided.")

        return errors

    def _validate_generation_inputs(self) -> list[str]:
        errors = self._validate_processing_inputs()
        if not self._is_prepared_for_current_sources():
            errors.insert(0, "Run 'Validate & Prepare Data' successfully before workflow generation.")

        prepared = self._window.project.state.prepared_inputs
        if prepared.manifest_path and not Path(prepared.manifest_path).expanduser().exists():
            errors.append(f"Prepared manifest was not found: {prepared.manifest_path}")
        if self._window.project.state.prepared_dem_path and not Path(
            self._window.project.state.prepared_dem_path
        ).expanduser().exists():
            errors.append(f"Prepared DEM was not found: {self._window.project.state.prepared_dem_path}")
        return errors
