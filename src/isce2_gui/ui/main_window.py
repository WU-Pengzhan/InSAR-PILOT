"""Main application window with practitioner-oriented workflow shell."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QTreeWidgetItem,
    QSizePolicy,
)

from isce2_gui.bootstrap import create_default_project
from isce2_gui.domain.project import (
    EnvironmentConfig,
    PreparedInputs,
    ProjectDocument,
    ProjectStatus,
    RunSubcommand,
    RunStep,
    StepStatus,
    WorkflowConfig,
)
from isce2_gui.services.command_plan import CommandPlan
from isce2_gui.services.aoi_import import AoiImportResult, AoiImportService
from isce2_gui.services.dem_coverage import DemCoverageService
from isce2_gui.services.dem_preparer import DemPreparationService
from isce2_gui.services.env_probe import EnvironmentProbe
from isce2_gui.services.input_catalog import InputCatalogReport, InputCatalogService
from isce2_gui.services.iw_recommendation import IwRecommendationResult, IwRecommendationService
from isce2_gui.services.output_discovery import OutputDiscoveryService, OutputNode
from isce2_gui.services.project_store import ProjectStore
from isce2_gui.services.run_executor import ProcessRunner
from isce2_gui.services.runfile_plan import (
    build_parallel_batch_command,
    count_commands,
    parse_result_markers,
    parse_run_file,
    split_batches_for_parallelism,
)
from isce2_gui.services.stack_generator import StackWorkflowService
from isce2_gui.services.visualization_service import (
    VisualizationBuildResult,
    VisualizationRequest,
    VisualizationService,
)
from isce2_gui.ui.pages.aoi_iw_page import AoiIwPage
from isce2_gui.ui.pages.data_sources_page import DataSourcesPage
from isce2_gui.ui.pages.processing_plan_page import ProcessingPlanPage
from isce2_gui.ui.pages.results_page import ResultsPage
from isce2_gui.ui.pages.run_monitor_page import RunMonitorPage
from isce2_gui.ui.widgets.geometry_verify_panel import VerifyPlotData
from isce2_gui.ui.widgets.status_badge import StatusBadge
from isce2_gui.ui.widgets.summary_card import SummaryCard
from isce2_gui.ui.widgets.workflow_nav_item import WorkflowNavItemWidget


class MainWindow(QMainWindow):
    """Stage 2 shell that preserves backend behavior and reorganizes the UX."""

    def __init__(self, project: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.project_store = ProjectStore()
        self.environment_probe = EnvironmentProbe()
        self.dem_preparation_service = DemPreparationService()
        self.input_catalog_service = InputCatalogService()
        self.aoi_import_service = AoiImportService()
        self.iw_recommendation_service = IwRecommendationService()
        self.dem_coverage_service = DemCoverageService()
        self.workflow_service = StackWorkflowService()
        self.output_discovery_service = OutputDiscoveryService()
        self.visualization_service = VisualizationService()
        self.runner = ProcessRunner(project.environment, self)
        self._last_catalog_report: InputCatalogReport | None = None
        self._pending_preparation: dict[str, object] | None = None
        self._pending_visualization: VisualizationBuildResult | None = None
        self._last_aoi_import: AoiImportResult | None = None
        self._last_iw_recommendation: IwRecommendationResult | None = None
        self._last_visualization_saved_status: ProjectStatus | None = None
        self._stop_requested = False
        self._nav_items: dict[str, WorkflowNavItemWidget] = {}
        self._page_index_by_key: dict[str, int] = {}

        self.setWindowTitle("ISCE2 Sentinel-1 GUI")
        self.resize(1600, 980)

        self._build_ui()
        self._alias_page_widgets()
        self._connect_page_actions()
        self._connect_runner()
        self._populate_form_from_project()
        self.refresh_steps_view()
        self.refresh_outputs_view()
        self.refresh_status_labels()
        self._sync_summary_sidebar()
        self._refresh_navigation_status()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)
        root.addWidget(self._build_project_header())

        body_splitter = QSplitter(Qt.Orientation.Horizontal, central)
        body_splitter.addWidget(self._build_workflow_navigation())
        body_splitter.addWidget(self._build_page_stack())
        body_splitter.addWidget(self._build_summary_sidebar())
        body_splitter.setStretchFactor(0, 0)
        body_splitter.setStretchFactor(1, 1)
        body_splitter.setStretchFactor(2, 0)
        body_splitter.setSizes([275, 1040, 260])
        root.addWidget(body_splitter, 1)
        self.setCentralWidget(central)

        self._build_log_console()

    def _build_project_header(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)
        title = QLabel("ISCE2 Sentinel-1 TOPS GUI")
        title.setObjectName("headerTitle")
        subtitle = QLabel("Practitioner workflow for local ISCE2 topsStack processing")
        subtitle.setObjectName("headerSubTitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        layout.addLayout(title_col, 1)

        project_col = QVBoxLayout()
        project_col.setContentsMargins(0, 0, 0, 0)
        project_col.setSpacing(2)
        self.header_project_label = QLabel("Project: new session")
        self.header_current_step_label = QLabel("Current step: -")
        project_col.addWidget(self.header_project_label)
        project_col.addWidget(self.header_current_step_label)
        layout.addLayout(project_col)

        self.header_status_badge = StatusBadge("draft", "neutral")
        self.header_env_badge = StatusBadge("Env unchecked", "warning")
        layout.addWidget(self.header_status_badge)
        layout.addWidget(self.header_env_badge)

        self.console_toggle_button = self._header_button("Show Console")
        self.new_button = self._header_button("New Project")
        self.open_button = self._header_button("Open Project")
        self.save_button = self._header_button("Save Project")
        self.console_toggle_button.setProperty("role", "secondary")
        self.new_button.setProperty("role", "secondary")
        self.open_button.setProperty("role", "secondary")
        self.save_button.setProperty("role", "primary")
        layout.addWidget(self.console_toggle_button)
        layout.addWidget(self.new_button)
        layout.addWidget(self.open_button)
        layout.addWidget(self.save_button)
        return widget

    def _build_workflow_navigation(self) -> QWidget:
        widget = QWidget()
        widget.setMinimumWidth(250)
        widget.setMaximumWidth(300)
        widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel("Workflow")
        label.setObjectName("summaryCardTitle")
        layout.addWidget(label)

        self.workflow_nav = QListWidget()
        self.workflow_nav.setObjectName("workflowNav")
        self.workflow_nav.setMinimumWidth(250)
        self.workflow_nav.setMaximumWidth(300)
        self.workflow_nav.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.workflow_nav.setSpacing(8)
        self.workflow_nav.setUniformItemSizes(True)
        self.workflow_nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.workflow_nav, 1)
        return widget

    def _build_page_stack(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.page_stack = QStackedWidget()
        layout.addWidget(self.page_stack)

        self.data_sources_page = DataSourcesPage()
        self.aoi_iw_page = AoiIwPage()
        self.processing_page = ProcessingPlanPage()
        self.run_monitor_page = RunMonitorPage()
        self.results_page = ResultsPage()

        pages = [
            ("data_sources", "Data Sources", self.data_sources_page),
            ("aoi_iw", "AOI + BBox + IW", self.aoi_iw_page),
            ("processing", "Processing Plan", self.processing_page),
            ("monitor", "Run Monitor", self.run_monitor_page),
            ("results", "Results & Visualization", self.results_page),
        ]
        for index, (key, title, widget) in enumerate(pages):
            self.page_stack.addWidget(widget)
            self._page_index_by_key[key] = index
            self._add_nav_item(key, title)

        self.workflow_nav.setCurrentRow(0)
        self._sync_nav_selection_state()
        self._apply_page_spacing()
        return container

    def _build_summary_sidebar(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        # Add left breathing room so the summary column does not sit on the splitter line.
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(10)

        title = QLabel("Project Summary")
        title.setObjectName("summaryCardTitle")
        layout.addWidget(title)

        self.summary_sources_card = SummaryCard("Data Sources", "Not prepared", "Dataset, orbit, and DEM readiness.")
        self.summary_aoi_card = SummaryCard("AOI / BBox", "Not set", "AOI file is optional input; bbox is the ISCE parameter.")
        self.summary_selection_card = SummaryCard("IW", "IW1 IW2 IW3", "Swath-level control for stackSentinel.")
        self.summary_reference_card = SummaryCard("Reference", "Auto", "Manual override optional.")
        self.summary_processing_card = SummaryCard("Processing", "Not generated", "Workflow, coreg, looks, and concurrency.")
        self.summary_results_card = SummaryCard("Results", "No outputs scanned", "Quicklooks and native ISCE outputs.")
        for card in (
            self.summary_sources_card,
            self.summary_aoi_card,
            self.summary_selection_card,
            self.summary_reference_card,
            self.summary_processing_card,
            self.summary_results_card,
        ):
            layout.addWidget(card)
        layout.addStretch(1)
        return widget

    def _build_log_console(self) -> None:
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Live stdout/stderr will appear here.")
        self.log_dock = QDockWidget("Log Console", self)
        self.log_dock.setWidget(self.log_view)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.log_dock.visibilityChanged.connect(self._handle_log_dock_visibility)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()

    def _alias_page_widgets(self) -> None:
        data = self.data_sources_page
        self.shell_init_edit = data.shell_init_row.line_edit
        self.conda_env_edit = data.conda_env_edit
        self.isce_root_edit = data.isce_root_row.line_edit
        self.input_path_edit = data.input_path_row.line_edit
        self.orbit_path_edit = data.orbit_path_row.line_edit
        self.dem_path_edit = data.dem_path_row.line_edit
        self.dem_reference_combo = data.dem_reference_combo
        self.aux_path_edit = data.aux_path_row.line_edit
        self.work_dir_edit = data.work_dir_row.line_edit
        self.extract_checkbox = data.extract_checkbox
        self.extract_dir_edit = data.extract_dir_row.line_edit
        self.validate_button = data.validate_env_button
        self.prepare_data_button = data.prepare_button
        self.inspect_inputs_button = data.inspect_button
        self.validation_text = data.validation_text
        self.inputs_text = data.inputs_text

        self.aoi_source_edit = self.aoi_iw_page.aoi_file_row.line_edit
        self.aoi_source_browse_button = self.aoi_iw_page.aoi_file_row.browse_button
        self.aoi_import_button = self.aoi_iw_page.aoi_file_row.secondary_button
        self.use_common_overlap_check = self.aoi_iw_page.use_common_overlap_check
        self.bbox_south_edit = self.aoi_iw_page.bbox_south_edit
        self.bbox_north_edit = self.aoi_iw_page.bbox_north_edit
        self.bbox_west_edit = self.aoi_iw_page.bbox_west_edit
        self.bbox_east_edit = self.aoi_iw_page.bbox_east_edit
        self.iw1_check = self.aoi_iw_page.iw1_check
        self.iw2_check = self.aoi_iw_page.iw2_check
        self.iw3_check = self.aoi_iw_page.iw3_check
        self.recommend_iw_button = self.aoi_iw_page.recommend_iw_button
        self.verify_geometry_button = self.aoi_iw_page.verify_button
        self.export_verify_button = self.aoi_iw_page.export_verify_button
        self.confirm_aoi_iw_button = self.aoi_iw_page.confirm_button
        self.verify_notes = self.aoi_iw_page.verify_notes

        self.workflow_combo = self.processing_page.workflow_combo
        self.coreg_combo = self.processing_page.coreg_combo
        self.num_connections_spin = self.processing_page.num_connections_spin
        self.azimuth_looks_spin = self.processing_page.azimuth_looks_spin
        self.range_looks_spin = self.processing_page.range_looks_spin
        self.num_proc_spin = self.processing_page.num_proc_spin
        self.num_proc_hint = self.processing_page.num_proc_hint
        self.polarization_combo = self.processing_page.polarization_combo
        self.generate_button = self.processing_page.generate_button
        self.runfile_estimate_text = self.processing_page.runfile_estimate_text
        self.command_preview_text = self.processing_page.command_preview_text
        self.reference_date_edit = self.processing_page.reference_date_edit

        self.steps_tree = self.run_monitor_page.steps_tree
        self.run_next_button = self.run_monitor_page.run_next_button
        self.run_selected_button = self.run_monitor_page.run_selected_button
        self.run_all_button = self.run_monitor_page.run_all_button
        self.stop_button = self.run_monitor_page.stop_button
        self.refresh_outputs_button = self.run_monitor_page.refresh_outputs_button
        self.monitor_runfile_estimate_text = self.run_monitor_page.runfile_estimate_text
        self.command_detail_text = self.run_monitor_page.command_detail_text

        self.outputs_tree = self.results_page.outputs_tree
        self.preview_image_label = self.results_page.preview_panel.image_label
        self.preview_scroll = self.results_page.preview_panel.scroll_area
        self.preview_meta_text = self.results_page.preview_panel.meta_text
        self.visual_mode_combo = self.results_page.visual_mode_combo
        self.visual_primary_path_edit = self.results_page.visual_primary_row.line_edit
        self.visual_secondary_path_edit = self.results_page.visual_secondary_row.line_edit
        self.visual_export_dir_edit = self.results_page.visual_export_dir_row.line_edit
        self.visual_primary_browse_button = self.results_page.visual_primary_row.browse_button
        self.visual_secondary_browse_button = self.results_page.visual_secondary_row.browse_button
        self.visual_export_dir_browse_button = self.results_page.visual_export_dir_row.browse_button
        self.visual_primary_from_outputs_button = self.results_page.visual_primary_row.secondary_button
        self.visual_secondary_from_outputs_button = self.results_page.visual_secondary_row.secondary_button
        self.visual_range_looks_spin = self.results_page.visual_range_looks_spin
        self.visual_azimuth_looks_spin = self.results_page.visual_azimuth_looks_spin
        self.visual_overlay_brightness_spin = self.results_page.visual_overlay_brightness_spin
        self.visual_preview_button = self.results_page.visual_preview_button
        self.visual_export_button = self.results_page.visual_export_button
        self.visual_status_text = self.results_page.visual_status_text

    def _connect_page_actions(self) -> None:
        self.new_button.clicked.connect(self.new_project)
        self.open_button.clicked.connect(self.open_project)
        self.save_button.clicked.connect(self.save_project)
        self.console_toggle_button.clicked.connect(self._toggle_log_console)

        self.workflow_nav.currentRowChanged.connect(self._handle_nav_changed)

        self.validate_button.clicked.connect(self.validate_environment)
        self.prepare_data_button.clicked.connect(self.prepare_data_sources)
        self.inspect_inputs_button.clicked.connect(self.inspect_inputs)

        self.extract_checkbox.toggled.connect(self._toggle_extract_widgets)
        self.data_sources_page.shell_init_row.browse_button.clicked.connect(self._browse_shell_init)
        self.data_sources_page.isce_root_row.browse_button.clicked.connect(self._browse_isce_root)
        self.data_sources_page.input_path_row.browse_button.clicked.connect(self._browse_input_dir)
        self.data_sources_page.orbit_path_row.browse_button.clicked.connect(self._browse_orbit_dir)
        self.data_sources_page.dem_path_row.browse_button.clicked.connect(self._browse_dem_file)
        self.data_sources_page.aux_path_row.browse_button.clicked.connect(self._browse_aux_dir)
        self.data_sources_page.work_dir_row.browse_button.clicked.connect(self._browse_work_dir)
        self.data_sources_page.extract_dir_row.browse_button.clicked.connect(self._browse_extract_dir)

        self.aoi_source_browse_button.clicked.connect(self._browse_aoi_file)
        if self.aoi_import_button is not None:
            self.aoi_import_button.clicked.connect(self.import_aoi_file)
        self.use_common_overlap_check.toggled.connect(self._toggle_common_overlap_mode)
        self.iw1_check.toggled.connect(self._sync_iw_selection_card)
        self.iw2_check.toggled.connect(self._sync_iw_selection_card)
        self.iw3_check.toggled.connect(self._sync_iw_selection_card)
        self.recommend_iw_button.clicked.connect(self.recommend_iw)
        self.verify_geometry_button.clicked.connect(self.verify_aoi_iw_geometry)
        self.export_verify_button.clicked.connect(self.export_verify_geometry_png)
        self.confirm_aoi_iw_button.clicked.connect(self.confirm_aoi_iw)

        self.processing_page.preview_command_button.clicked.connect(self._preview_generate_command)
        self.processing_page.rescan_button.clicked.connect(self._rescan_existing_runfiles)
        self.generate_button.clicked.connect(self.generate_workflow)
        self.num_proc_spin.valueChanged.connect(lambda _: self._refresh_runfile_estimates())

        self.run_next_button.clicked.connect(self.run_next_step)
        self.run_selected_button.clicked.connect(self.run_selected_step)
        self.run_all_button.clicked.connect(self.run_remaining_steps)
        self.stop_button.clicked.connect(self.stop_execution)
        self.refresh_outputs_button.clicked.connect(self.refresh_outputs_view)
        self.steps_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.steps_tree.customContextMenuRequested.connect(self._open_steps_context_menu)
        self.steps_tree.itemSelectionChanged.connect(self._handle_step_selection_changed)

        self.results_page.refresh_outputs_button.clicked.connect(self.refresh_outputs_view)
        self.visual_primary_browse_button.clicked.connect(self._browse_visual_primary)
        self.visual_secondary_browse_button.clicked.connect(self._browse_visual_secondary)
        self.visual_export_dir_browse_button.clicked.connect(self._browse_visual_export_dir)
        if self.visual_primary_from_outputs_button is not None:
            self.visual_primary_from_outputs_button.clicked.connect(self._fill_visual_primary_from_outputs)
        if self.visual_secondary_from_outputs_button is not None:
            self.visual_secondary_from_outputs_button.clicked.connect(self._fill_visual_secondary_from_outputs)
        self.visual_preview_button.clicked.connect(self.run_visualization_preview)
        self.visual_export_button.clicked.connect(self.run_visualization_export)
        self.visual_mode_combo.currentIndexChanged.connect(self._update_visualization_mode_ui)

    def _connect_runner(self) -> None:
        self.runner.log_emitted.connect(self.append_log)
        self.runner.command_started.connect(self._handle_command_started)
        self.runner.command_finished.connect(self._handle_command_finished)
        self.runner.queue_finished.connect(self._handle_queue_finished)
        self.runner.runner_state_changed.connect(self._handle_runner_state_changed)

    def _add_nav_item(self, key: str, title: str) -> None:
        item = QListWidgetItem(self.workflow_nav)
        item.setData(Qt.ItemDataRole.UserRole, key)
        row_widget = WorkflowNavItemWidget(title)
        size_hint = row_widget.sizeHint()
        row_height = max(size_hint.height(), row_widget.minimumHeight())
        item.setSizeHint(QSize(0, row_height))
        self.workflow_nav.addItem(item)
        self.workflow_nav.setItemWidget(item, row_widget)
        self._nav_items[key] = row_widget

    def _apply_page_spacing(self) -> None:
        """Apply consistent page-level breathing room around central content."""
        for page in (
            self.data_sources_page,
            self.aoi_iw_page,
            self.processing_page,
            self.run_monitor_page,
            self.results_page,
        ):
            layout = page.layout()
            if layout is not None:
                layout.setContentsMargins(14, 10, 14, 10)
                layout.setSpacing(max(layout.spacing(), 14))

    @staticmethod
    def _header_button(text: str):
        from PySide6.QtWidgets import QPushButton

        return QPushButton(text)

    def _handle_nav_changed(self, row: int) -> None:
        if row < 0:
            return
        self.page_stack.setCurrentIndex(row)
        self._sync_nav_selection_state()
        key = self.workflow_nav.item(row).data(Qt.ItemDataRole.UserRole)
        if key in {"monitor", "results"}:
            self.console_toggle_button.setText("Hide Console")
        else:
            self.console_toggle_button.setText("Show Console" if not self.log_dock.isVisible() else "Hide Console")

    def _toggle_log_console(self) -> None:
        self.log_dock.setVisible(not self.log_dock.isVisible())

    def _handle_log_dock_visibility(self, visible: bool) -> None:
        self.console_toggle_button.setText("Hide Console" if visible else "Show Console")

    def _toggle_extract_widgets(self, checked: bool) -> None:
        self.data_sources_page.extract_dir_row.setEnabled(checked)

    def _browse_shell_init(self) -> None:
        self._browse_file_into(self.shell_init_edit, "Select shell init file")

    def _browse_isce_root(self) -> None:
        self._browse_dir_into(self.isce_root_edit, "Select ISCE2 root")

    def _browse_input_dir(self) -> None:
        self._browse_dir_into(self.input_path_edit, "Select Sentinel-1 input folder")

    def _browse_orbit_dir(self) -> None:
        self._browse_dir_into(self.orbit_path_edit, "Select orbit folder")

    def _browse_dem_file(self) -> None:
        self._browse_file_into(self.dem_path_edit, "Select DEM file")

    def _browse_aux_dir(self) -> None:
        self._browse_dir_into(self.aux_path_edit, "Select AUX directory")

    def _browse_work_dir(self) -> None:
        self._browse_dir_into(self.work_dir_edit, "Select working directory")

    def _browse_extract_dir(self) -> None:
        self._browse_dir_into(self.extract_dir_edit, "Select extracted SAFE directory")

    def _browse_aoi_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select AOI file",
            self.aoi_source_edit.text() or str(Path.home()),
            "AOI files (*.kml *.shp);;All files (*)",
        )
        if path:
            self.aoi_source_edit.setText(path)

    def _browse_visual_primary(self) -> None:
        self._browse_file_into(self.visual_primary_path_edit, "Select primary visualization input")

    def _browse_visual_secondary(self) -> None:
        self._browse_file_into(self.visual_secondary_path_edit, "Select secondary visualization input")

    def _browse_visual_export_dir(self) -> None:
        self._browse_dir_into(self.visual_export_dir_edit, "Select visualization export directory")

    def _fill_visual_primary_from_outputs(self) -> None:
        selected = self._selected_output_file_path()
        if selected is None:
            QMessageBox.warning(self, "No output file selected", "Select a file in Results first.")
            return
        self.visual_primary_path_edit.setText(selected)

    def _fill_visual_secondary_from_outputs(self) -> None:
        selected = self._selected_output_file_path()
        if selected is None:
            QMessageBox.warning(self, "No output file selected", "Select a file in Results first.")
            return
        self.visual_secondary_path_edit.setText(selected)

    def _selected_output_file_path(self) -> str | None:
        item = self.outputs_tree.currentItem()
        if item is None:
            return None
        path_text = item.text(2).strip()
        if not path_text:
            return None
        path = Path(path_text).expanduser()
        if not path.exists() or not path.is_file():
            return None
        return str(path)

    def _browse_dir_into(self, edit, title: str) -> None:
        path = QFileDialog.getExistingDirectory(self, title, edit.text() or str(Path.home()))
        if path:
            edit.setText(path)

    def _browse_file_into(self, edit, title: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, title, edit.text() or str(Path.home()))
        if path:
            edit.setText(path)

    def _populate_form_from_project(self) -> None:
        self.shell_init_edit.setText(self.project.environment.shell_init_path)
        self.conda_env_edit.setText(self.project.environment.conda_env_name)
        self.isce_root_edit.setText(self.project.environment.isce_root)

        self.input_path_edit.setText(self.project.workflow.input_path)
        self.orbit_path_edit.setText(self.project.workflow.orbit_path)
        self.dem_path_edit.setText(self.project.workflow.dem_path)
        index = self.dem_reference_combo.findData(self.project.workflow.dem_height_reference)
        self.dem_reference_combo.setCurrentIndex(index if index >= 0 else 0)
        self.aux_path_edit.setText(self.project.workflow.aux_path)
        self.work_dir_edit.setText(self.project.workflow.work_dir)
        self.extract_checkbox.setChecked(self.project.workflow.extract_zips)
        self.extract_dir_edit.setText(self.project.workflow.extract_dir)
        self.extract_dir_edit.setEnabled(self.project.workflow.extract_zips)

        self.aoi_source_edit.setText(self.project.workflow.aoi_source_path)
        previous = self.use_common_overlap_check.blockSignals(True)
        self.use_common_overlap_check.setChecked(self.project.workflow.use_common_overlap)
        self.use_common_overlap_check.blockSignals(previous)
        try:
            south, north, west, east = self.project.workflow.bbox_components()
        except ValueError:
            south, north, west, east = "", "", "", ""
        self.aoi_iw_page.set_bbox_components(south, north, west, east)
        self.aoi_iw_page.set_bbox_enabled(not self.use_common_overlap_check.isChecked())
        self.aoi_iw_page.set_selected_swaths(self.project.workflow.swath_numbers or "1 2 3")
        self._sync_iw_selection_card()

        self.reference_date_edit.setText(self.project.workflow.reference_date)
        self._populate_reference_candidates()

        self.workflow_combo.setCurrentText(self.project.workflow.workflow)
        self.coreg_combo.setCurrentText(self.project.workflow.coregistration)
        self.num_connections_spin.setValue(self.project.workflow.num_connections)
        self.azimuth_looks_spin.setValue(self.project.workflow.azimuth_looks)
        self.range_looks_spin.setValue(self.project.workflow.range_looks)
        self.num_proc_spin.setValue(self.project.workflow.num_proc)
        self.polarization_combo.setCurrentText(self.project.workflow.polarization)

        mode_index = self.visual_mode_combo.findData(self.project.visualization.mode)
        self.visual_mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        self.visual_primary_path_edit.setText(self.project.visualization.primary_input_path)
        self.visual_secondary_path_edit.setText(self.project.visualization.secondary_input_path)
        self.visual_range_looks_spin.setValue(max(1, self.project.visualization.range_looks))
        self.visual_azimuth_looks_spin.setValue(max(1, self.project.visualization.azimuth_looks))
        self.visual_overlay_brightness_spin.setValue(max(0.05, self.project.visualization.overlay_brightness))
        if self.project.visualization.export_dir:
            self.visual_export_dir_edit.setText(self.project.visualization.export_dir)
        else:
            try:
                default_export = self.project.metadata_dir() / "visualize" / "exports"
            except ValueError:
                default_export = Path.home() / "iscegui_visualize_exports"
            self.visual_export_dir_edit.setText(str(default_export))
        self.visual_status_text.setPlainText(self.project.visualization.last_render_summary)
        self._update_visualization_mode_ui()

        if self.project.visualization.last_preview_path:
            self._display_preview_image(
                self.project.visualization.last_preview_path,
                self.project.visualization.last_render_summary,
            )
        else:
            self.preview_image_label.setPixmap(QPixmap())
            self.preview_image_label.setText("No preview generated yet.")
            self.preview_image_label.resize(480, 320)
            self.preview_meta_text.setPlainText("")

        self.validation_text.setPlainText(self.project.state.last_validation)
        self.command_preview_text.setPlainText(self.project.state.last_generated_command)
        self._render_preparation_summary()
        self._refresh_runfile_estimates()
        self._update_action_states()
        self._sync_summary_sidebar()

    def _update_project_from_form(self) -> None:
        previous_signature = self.project.state.prepared_signature
        self.project.environment = EnvironmentConfig(
            shell_init_path=self.shell_init_edit.text().strip(),
            conda_env_name=self.conda_env_edit.text().strip(),
            isce_root=self.isce_root_edit.text().strip(),
        )
        bbox_parts = list(self.aoi_iw_page.bbox_components())
        bbox_snwe = " ".join(part for part in bbox_parts if part) if any(bbox_parts) else ""
        use_common_overlap = self.use_common_overlap_check.isChecked()
        if use_common_overlap:
            bbox_snwe = ""

        self.project.workflow = WorkflowConfig(
            input_path=self.input_path_edit.text().strip(),
            orbit_path=self.orbit_path_edit.text().strip(),
            dem_path=self.dem_path_edit.text().strip(),
            dem_height_reference=str(self.dem_reference_combo.currentData() or ""),
            aux_path=self.aux_path_edit.text().strip(),
            work_dir=self.work_dir_edit.text().strip(),
            bbox_snwe=bbox_snwe,
            aoi_source_path=self.aoi_source_edit.text().strip(),
            use_common_overlap=use_common_overlap,
            extract_zips=self.extract_checkbox.isChecked(),
            extract_dir=self.extract_dir_edit.text().strip(),
            workflow=self.workflow_combo.currentText(),
            coregistration=self.coreg_combo.currentText(),
            num_connections=self.num_connections_spin.value(),
            azimuth_looks=self.azimuth_looks_spin.value(),
            range_looks=self.range_looks_spin.value(),
            swath_numbers=self.aoi_iw_page.selected_swaths() or "1 2 3",
            polarization=self.polarization_combo.currentText(),
            reference_date=self.reference_date_edit.text().strip(),
            num_proc=self.num_proc_spin.value(),
        )

        self.project.visualization.mode = str(self.visual_mode_combo.currentData() or "slc")
        self.project.visualization.primary_input_path = self.visual_primary_path_edit.text().strip()
        self.project.visualization.secondary_input_path = self.visual_secondary_path_edit.text().strip()
        self.project.visualization.range_looks = self.visual_range_looks_spin.value()
        self.project.visualization.azimuth_looks = self.visual_azimuth_looks_spin.value()
        self.project.visualization.overlay_brightness = self.visual_overlay_brightness_spin.value()
        self.project.visualization.export_dir = self.visual_export_dir_edit.text().strip()

        if previous_signature and previous_signature != self._preparation_signature(self.project.workflow):
            self._clear_prepared_state()
            self.statusBar().showMessage(
                "Data source changed. Please run Validate & Prepare Data again.",
                5000,
            )

        self.runner.set_environment(self.project.environment)
        self.refresh_status_labels()
        self._update_action_states()
        self._sync_summary_sidebar()

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
        state = self.project.state
        prepared = state.prepared_inputs
        if not state.prepared_signature:
            return False
        if state.prepared_signature != self._preparation_signature(self.project.workflow):
            return False
        if not prepared.entries or not prepared.manifest_path or not state.prepared_dem_path:
            return False
        if not Path(prepared.manifest_path).expanduser().exists():
            return False
        if not Path(state.prepared_dem_path).expanduser().exists():
            return False
        return True

    def _clear_prepared_state(self) -> None:
        self.project.state.prepared_inputs = PreparedInputs()
        self.project.state.prepared_dem_path = ""
        self.project.state.prepared_signature = ""
        self._last_catalog_report = None
        self._render_preparation_summary()
        self._update_action_states()
        self._sync_summary_sidebar()

    def _render_preparation_summary(self) -> None:
        prepared = self.project.state.prepared_inputs
        self.data_sources_page.orbit_card.set_value(
            Path(self.project.workflow.orbit_path).name if self.project.workflow.orbit_path else "Not set"
        )
        self.data_sources_page.dem_card.set_value(
            Path(self.project.workflow.dem_path).name if self.project.workflow.dem_path else "Not set"
        )
        if not prepared.entries:
            self.inputs_text.setPlainText("Data has not been prepared yet.")
            self.data_sources_page.dataset_card.set_value("Not prepared")
            self.data_sources_page.dataset_card.set_body("Run Validate & Prepare Data to create the SAFE manifest.")
            return

        lines: list[str] = []
        lines.extend(prepared.notes)
        if self.project.state.prepared_dem_path:
            lines.extend(["", f"Prepared DEM: {self.project.state.prepared_dem_path}"])
        lines.extend(["", "Prepared inputs:"])
        lines.extend(f"- {entry.path}" for entry in prepared.entries)
        self.inputs_text.setPlainText("\n".join(lines))
        self.data_sources_page.dataset_card.set_value(f"{len(prepared.entries)} prepared scenes")
        self.data_sources_page.dataset_card.set_body(Path(prepared.manifest_path).name if prepared.manifest_path else "Manifest ready")

    def _commit_preparation_result(self, prepared: PreparedInputs, dem_path: str, signature: str) -> None:
        self.project.state.prepared_inputs = prepared
        self.project.state.prepared_dem_path = dem_path
        self.project.state.prepared_signature = signature
        self.project.state.last_error = ""
        self.project.state.status = ProjectStatus.READY
        self.project.state.current_step = "data preparation"
        self.project_store.save(self.project)
        self._populate_reference_candidates()
        self._render_preparation_summary()
        self.refresh_status_labels()
        self._update_action_states()
        self._sync_summary_sidebar()

    def _update_action_states(self) -> None:
        busy = self.runner.is_running()
        has_selected_step = bool(self._selected_steps())
        self.generate_button.setEnabled((not busy) and self._is_prepared_for_current_sources())
        self.run_next_button.setEnabled(not busy)
        self.run_selected_button.setEnabled((not busy) and has_selected_step)
        self.run_all_button.setEnabled(not busy)
        self.validate_button.setEnabled(not busy)
        self.inspect_inputs_button.setEnabled(not busy)
        self.prepare_data_button.setEnabled(not busy)
        self.aoi_source_edit.setEnabled(not busy)
        self.aoi_source_browse_button.setEnabled(not busy)
        if self.aoi_import_button is not None:
            self.aoi_import_button.setEnabled(not busy)
        self.use_common_overlap_check.setEnabled(not busy)
        self.iw1_check.setEnabled(not busy)
        self.iw2_check.setEnabled(not busy)
        self.iw3_check.setEnabled(not busy)
        self.recommend_iw_button.setEnabled(not busy)
        self.verify_geometry_button.setEnabled(not busy)
        self.export_verify_button.setEnabled(not busy)
        self.confirm_aoi_iw_button.setEnabled(not busy)
        bbox_edit_enabled = (not busy) and (not self.use_common_overlap_check.isChecked())
        self.bbox_south_edit.setEnabled(bbox_edit_enabled)
        self.bbox_north_edit.setEnabled(bbox_edit_enabled)
        self.bbox_west_edit.setEnabled(bbox_edit_enabled)
        self.bbox_east_edit.setEnabled(bbox_edit_enabled)
        self.stop_button.setEnabled(busy)
        self.visual_preview_button.setEnabled(not busy)
        self.visual_export_button.setEnabled(not busy)
        self.visual_primary_browse_button.setEnabled(not busy)
        self.visual_secondary_browse_button.setEnabled(not busy)
        if self.visual_primary_from_outputs_button is not None:
            self.visual_primary_from_outputs_button.setEnabled(not busy)
        if self.visual_secondary_from_outputs_button is not None:
            self.visual_secondary_from_outputs_button.setEnabled(not busy)
        self.visual_export_dir_browse_button.setEnabled(not busy)

    def refresh_status_labels(self) -> None:
        status_text = self.project.state.status.value
        current_step = self.project.state.current_step or "-"
        try:
            work_dir = str(self.project.resolved_work_dir())
        except ValueError:
            work_dir = "-"

        project_name = Path(work_dir).name if work_dir != "-" else "new session"
        self.header_project_label.setText(f"Project: {project_name}")
        self.header_current_step_label.setText(f"Current step: {current_step}")
        self.header_status_badge.set_status(status_text, self._tone_for_status(status_text))
        self.run_monitor_page.status_card.set_value(status_text)
        self.run_monitor_page.status_card.set_badge(status_text, self._tone_for_status(status_text))
        self.run_monitor_page.current_step_card.set_value(current_step)
        self.run_monitor_page.work_dir_card.set_value(work_dir)

        env_text, env_tone = self._environment_health_badge()
        self.header_env_badge.set_status(env_text, env_tone)

    def append_log(self, text: str) -> None:
        cursor = self.log_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    def validate_environment(self) -> None:
        self._update_project_from_form()
        report = self.environment_probe.probe(self.project.environment)
        self.project.state.last_validation = report.as_text()
        if report.ok and self.project.state.status == ProjectStatus.DRAFT:
            self.project.state.status = ProjectStatus.READY
        self.validation_text.setPlainText(report.as_text())
        self.refresh_status_labels()
        self._sync_summary_sidebar()
        self.statusBar().showMessage("Environment validation finished.", 5000)

    def inspect_inputs(self) -> None:
        self._update_project_from_form()
        try:
            report = self.input_catalog_service.scan(Path(self.project.workflow.input_path))
        except Exception as exc:
            self._show_error("Input inspection failed", str(exc))
            return

        self._last_catalog_report = report
        self.inputs_text.setPlainText(report.as_text())
        self.data_sources_page.dataset_card.set_value(f"{len(report.entries)} detected inputs")
        self.data_sources_page.dataset_card.set_body("ZIP/SAFE scan complete.")
        self.statusBar().showMessage("Input inspection finished.", 5000)
        self._sync_summary_sidebar()

    def prepare_data_sources(self) -> None:
        self._update_project_from_form()
        if self.runner.is_running():
            QMessageBox.warning(self, "Busy", "Another command is already running.")
            return

        errors = self._validate_data_source_inputs()
        if errors:
            self._show_error("Cannot prepare data", "\n".join(errors))
            return

        self.log_view.clear()
        self._pending_preparation = None
        try:
            report = self.input_catalog_service.scan(Path(self.project.workflow.input_path))
            prepared = self.input_catalog_service.prepare_inputs(
                self.project.workflow,
                self.project.resolved_work_dir(),
                report,
                logger=self.append_log,
            )
            dem_preparation = self.dem_preparation_service.prepare(
                self.project.environment,
                self.project.workflow.dem_path,
                self.project.workflow.dem_height_reference,
                self.project.resolved_work_dir(),
                self.project.logs_dir(),
            )
        except Exception as exc:
            self.project.state.last_error = str(exc)
            self.project.state.status = ProjectStatus.FAILED
            self.refresh_status_labels()
            self._update_action_states()
            self._show_error("Data preparation failed", str(exc))
            return

        self._last_catalog_report = report
        if dem_preparation.notes:
            self.append_log("\n".join(dem_preparation.notes) + "\n")

        signature = self._preparation_signature(self.project.workflow)
        if not dem_preparation.plans:
            self._commit_preparation_result(prepared, dem_preparation.final_dem_path, signature)
            self.statusBar().showMessage("Data validation and preparation finished.", 5000)
            return

        self.project.state.last_error = ""
        self.project.state.status = ProjectStatus.RUNNING
        self.project.state.current_step = "data preparation"
        self.project_store.save(self.project)
        self.refresh_status_labels()
        self._update_action_states()
        self._pending_preparation = {
            "prepared": prepared,
            "dem_path": dem_preparation.final_dem_path,
            "signature": signature,
        }
        self.runner.run_queue(dem_preparation.plans)

    def save_project(self) -> None:
        self._update_project_from_form()
        try:
            path = self.project_store.save(self.project)
        except Exception as exc:
            self._show_error("Save failed", str(exc))
            return
        self.statusBar().showMessage(f"Project saved: {path}", 5000)

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open project",
            str(Path.home()),
            "Project JSON (project.json);;All files (*)",
        )
        if not path:
            return
        try:
            self.project = self.project_store.load(path)
            self.runner.set_environment(self.project.environment)
            self.workflow_service.synchronize_project_steps(self.project)
            recovered = self._recover_loaded_state()
            if recovered:
                self.project_store.save(self.project)
        except Exception as exc:
            self._show_error("Open failed", str(exc))
            return

        self._last_catalog_report = None
        self._pending_preparation = None
        self._pending_visualization = None
        self._last_visualization_saved_status = None
        self.log_view.clear()
        self.outputs_tree.clear()
        self.steps_tree.clear()
        self.validation_text.clear()
        self.inputs_text.clear()
        self.command_detail_text.clear()
        self._populate_form_from_project()
        self.refresh_steps_view()
        self.refresh_outputs_view()
        self.refresh_status_labels()
        self._sync_summary_sidebar()
        self._refresh_navigation_status()
        self.statusBar().showMessage(f"Loaded project: {path}", 5000)

    def new_project(self) -> None:
        self.project = create_default_project()
        self.runner.set_environment(self.project.environment)
        self._last_catalog_report = None
        self._pending_preparation = None
        self._pending_visualization = None
        self._last_visualization_saved_status = None
        self.log_view.clear()
        self.outputs_tree.clear()
        self.steps_tree.clear()
        self.validation_text.clear()
        self.inputs_text.clear()
        self.command_detail_text.clear()
        self._populate_form_from_project()
        self.refresh_steps_view()
        self.refresh_outputs_view()
        self.refresh_status_labels()
        self._sync_summary_sidebar()
        self._refresh_navigation_status()

    def generate_workflow(self) -> None:
        self._update_project_from_form()
        errors = self._validate_generation_inputs()
        if errors:
            self._show_error("Cannot generate workflow", "\n".join(errors))
            return

        self.log_view.clear()
        try:
            command = self.workflow_service.build_generate_command(
                self.project,
                self.project.state.prepared_inputs,
                dem_path=self.project.state.prepared_dem_path,
            )
            self.project.state.last_generated_command = command
            self.command_preview_text.setPlainText(command)
            self.project.state.last_error = ""
            self.project.state.current_step = "workflow generation"
            self.project.state.status = ProjectStatus.RUNNING
            self.project_store.save(self.project)
        except Exception as exc:
            self.project.state.last_error = str(exc)
            self.project.state.status = ProjectStatus.FAILED
            self.refresh_status_labels()
            self._show_error("Workflow generation setup failed", str(exc))
            return

        plan = CommandPlan(
            label="Generate topsStack workflow",
            command=command,
            cwd=str(self.project.resolved_work_dir()),
            log_path=str(self.project.logs_dir() / "stack_generate.log"),
            step_name="workflow generation",
            is_generation=True,
            kind="generation",
        )
        self.runner.run_queue([plan])
        self.refresh_status_labels()
        self._set_current_page("monitor")

    def run_next_step(self) -> None:
        self._update_project_from_form()
        step = self.workflow_service.next_runnable_step(self.project)
        if step is None:
            QMessageBox.information(self, "No runnable steps", "There are no remaining run files to execute.")
            return
        self._run_steps([step])

    def run_selected_step(self) -> None:
        self._update_project_from_form()
        steps = self._selected_steps()
        if not steps:
            QMessageBox.information(
                self,
                "No step selected",
                "Select one or more run steps in Run Monitor, then click 'Run Selected Step'.",
            )
            return
        for step in steps:
            if not step.path:
                self._show_error("Invalid step", f"{step.name} does not have a valid run file path.")
                return
            if not Path(step.path).expanduser().exists():
                self._show_error("Run file missing", f"Run file was not found for {step.name}:\n{step.path}")
                return

        if len(steps) == 1:
            self.statusBar().showMessage(
                "Running selected step only. Downstream step statuses are left unchanged.",
                7000,
            )
        else:
            self.statusBar().showMessage(
                f"Running {len(steps)} selected steps in run-file order. Downstream statuses are left unchanged.",
                7000,
            )
        self._run_steps(steps)

    def run_remaining_steps(self) -> None:
        self._update_project_from_form()
        steps = self.workflow_service.remaining_steps(self.project)
        if not steps:
            QMessageBox.information(self, "No runnable steps", "There are no remaining run files to execute.")
            return
        self._run_steps(steps)

    def stop_execution(self) -> None:
        self._stop_requested = True
        self.runner.stop()

    def _update_visualization_mode_ui(self) -> None:
        mode = str(self.visual_mode_combo.currentData() or "slc")
        is_overlay = mode == "overlay"
        self.results_page.set_overlay_fields_visible(is_overlay)
        if mode == "slc":
            self.visual_primary_path_edit.setPlaceholderText(
                "Select .slc/.slc.vrt/.slc.full.vrt or a file with sibling .xml"
            )
        elif mode == "interferogram":
            self.visual_primary_path_edit.setPlaceholderText(
                "Select .int/.int.vrt/.int.full.vrt or a file with sibling .xml"
            )
        else:
            self.visual_primary_path_edit.setPlaceholderText("Select SLC input (.slc/.vrt/.xml)")
            self.visual_secondary_path_edit.setPlaceholderText("Select interferogram input (.int/.vrt/.xml)")

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
        self._update_project_from_form()
        try:
            work_dir = str(self.project.resolved_work_dir())
        except ValueError as exc:
            self._show_error("Visualization setup failed", str(exc))
            return None

        return VisualizationRequest(
            mode=str(self.visual_mode_combo.currentData() or "slc"),
            primary_input_path=self.visual_primary_path_edit.text().strip(),
            secondary_input_path=self.visual_secondary_path_edit.text().strip(),
            range_looks=self.visual_range_looks_spin.value(),
            azimuth_looks=self.visual_azimuth_looks_spin.value(),
            overlay_brightness=self.visual_overlay_brightness_spin.value(),
            work_dir=work_dir,
            output_bmp_path=output_path,
        )

    def _try_reuse_preview_for_export(self, signature: str, export_path: str) -> bool:
        preview_path = Path(self.project.visualization.last_preview_path).expanduser()
        if not preview_path.exists() or not preview_path.is_file():
            return False
        if self.project.visualization.last_render_signature != signature:
            return False

        destination = Path(export_path).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if preview_path.resolve() != destination.resolve():
                shutil.copy2(preview_path, destination)
        except OSError as exc:
            self._show_error("Export failed", f"Failed to copy preview image:\n{exc}")
            return False

        summary = self.project.visualization.last_render_summary.strip()
        details = summary if summary else "Reused latest preview."
        self.visual_status_text.setPlainText(
            f"{details}\n\nStatus: export reused cached preview\nSource: {preview_path}\nOutput: {destination}"
        )
        self.statusBar().showMessage(f"Export reused preview: {destination}", 5000)
        self.project.state.last_error = ""
        self.project_store.save(self.project)
        return True

    def _resolve_visualization_preview_output_path(self) -> str | None:
        self._update_project_from_form()
        try:
            work_dir = self.project.resolved_work_dir()
        except ValueError as exc:
            self._show_error("Cannot preview", str(exc))
            return None
        mode = str(self.visual_mode_combo.currentData() or "slc")
        preview_dir = work_dir / ".iscegui" / "visualize" / "cache" / "latest"
        filename = f"{mode}_preview.bmp"
        return str(preview_dir / filename)

    def _resolve_visualization_export_output_path(self) -> str | None:
        self._update_project_from_form()
        try:
            export_dir_text = self.project.visualization.export_dir.strip()
            if export_dir_text:
                default_dir = Path(export_dir_text).expanduser()
            else:
                default_dir = self.project.metadata_dir() / "visualize" / "exports"
        except ValueError:
            default_dir = Path.home()

        mode = str(self.visual_mode_combo.currentData() or "slc")
        initial = str(default_dir / f"{mode}_quicklook.bmp")
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export visualization BMP",
            initial,
            "BMP files (*.bmp);;All files (*)",
        )
        if not output_path:
            return None
        self.visual_export_dir_edit.setText(str(Path(output_path).expanduser().parent))
        return output_path

    def _run_visualization(self, request: VisualizationRequest, *, action: str, render_signature: str) -> None:
        if self.runner.is_running():
            QMessageBox.warning(self, "Busy", "Another command is already running.")
            return

        try:
            result = self.visualization_service.build(request, self.project.logs_dir())
        except Exception as exc:
            self._show_error("Visualization setup failed", str(exc))
            return

        result.render_signature = render_signature
        result.action = action
        self._stop_requested = False
        self._pending_visualization = result
        self._last_visualization_saved_status = self.project.state.status
        self.project.state.current_step = "visualization"
        self.project.state.last_error = ""
        self.project_store.save(self.project)

        self.visual_status_text.setPlainText(
            f"{result.summary}\n\nLog: {result.log_path}\n\nStatus: running ..."
        )
        self.preview_meta_text.setPlainText(
            f"{result.summary}\n\nOutput: {result.output_bmp_path}\nLog: {result.log_path}"
        )
        self.preview_image_label.setText("Rendering preview ...")
        self.preview_image_label.setPixmap(QPixmap())
        self.runner.run_queue([result.plan])
        self._update_action_states()
        self._set_current_page("results")

    def _run_steps(self, steps: list[RunStep]) -> None:
        if self.runner.is_running():
            QMessageBox.warning(self, "Busy", "Another command is already running.")
            return

        self._stop_requested = False
        plans: list[CommandPlan] = []
        runfile_parallel = max(1, self.project.workflow.num_proc)
        for step in steps:
            run_file = Path(step.path)
            try:
                parsed_batches = parse_run_file(run_file)
            except Exception as exc:
                self._show_error("Run file parsing failed", f"{step.name}: {exc}")
                return

            if not parsed_batches:
                self._show_error("Run file parsing failed", f"{step.name}: no executable commands found.")
                return

            batches = split_batches_for_parallelism(parsed_batches, runfile_parallel)
            command_logs = {
                cmd.index: str(self.project.logs_dir() / f"{step.name}.cmd_{cmd.index:03d}.log")
                for batch in batches
                for cmd in batch
            }
            step.subcommands = [
                RunSubcommand(
                    index=index,
                    command=command,
                    status=StepStatus.PENDING,
                    log_path=log_path,
                    exit_code=None,
                )
                for index, command, log_path in (
                    (cmd.index, cmd.command, command_logs[cmd.index])
                    for batch in batches
                    for cmd in batch
                )
            ]
            step.subcommands.sort(key=lambda item: item.index)
            step.status = StepStatus.PENDING
            step.exit_code = None
            step.last_message = ""
            step.log_path = str(self.project.logs_dir() / f"{step.name}.batch_001.log")

            total_batches = len(batches)
            for batch_index, batch in enumerate(batches, start=1):
                batch_log_path = str(self.project.logs_dir() / f"{step.name}.batch_{batch_index:03d}.log")
                plans.append(
                    CommandPlan(
                        label=f"{step.name} [batch {batch_index}/{total_batches}]",
                        command=build_parallel_batch_command(batch, command_logs),
                        cwd=str(self.project.resolved_work_dir()),
                        log_path=batch_log_path,
                        step_name=step.name,
                        is_generation=False,
                        kind="step_batch",
                        metadata={
                            "subcommand_indices": [cmd.index for cmd in batch],
                            "batch_index": batch_index,
                            "batch_total": total_batches,
                        },
                    )
                )

        self.project.state.status = ProjectStatus.RUNNING
        self.project.state.current_step = steps[0].name
        self.project.state.last_error = ""
        self.project_store.save(self.project)
        self.runner.run_queue(plans)
        self.refresh_status_labels()
        self._set_current_page("monitor")

    def _handle_command_started(self, plan: CommandPlan) -> None:
        self.append_log(f"\n=== {plan.label} ===\n")
        self.project.state.current_step = plan.step_name or plan.label
        if plan.kind == "step_batch":
            step = self._find_step(plan.step_name)
            if step is not None:
                step.status = StepStatus.RUNNING
                step.exit_code = None
                for sub_index in plan.metadata.get("subcommand_indices", []):
                    subcommand = self._find_subcommand(step, int(sub_index))
                    if subcommand is not None:
                        subcommand.status = StepStatus.RUNNING
                        subcommand.exit_code = None
        elif plan.kind == "visualization":
            self.preview_image_label.setPixmap(QPixmap())
            self.preview_image_label.setText("Rendering preview ...")
            self.preview_image_label.resize(480, 320)
        self.refresh_steps_view()
        self.refresh_status_labels()
        self._sync_summary_sidebar()

    def _handle_command_finished(self, plan: CommandPlan, exit_code: int) -> None:
        stopped = self._stop_requested and exit_code != 0
        if plan.kind == "generation":
            if stopped:
                self.project.state.status = ProjectStatus.CANCELLED
            elif exit_code == 0:
                self.workflow_service.synchronize_project_steps(self.project)
                self.project.state.status = ProjectStatus.GENERATED
            else:
                self.project.state.status = ProjectStatus.FAILED
                self.project.state.last_error = f"Workflow generation failed with exit code {exit_code}"
        elif plan.kind == "step_batch":
            step = self._find_step(plan.step_name)
            if step is not None:
                sub_indices = [int(item) for item in plan.metadata.get("subcommand_indices", [])]
                marker_text = ""
                try:
                    marker_text = Path(plan.log_path).read_text(encoding="utf-8")
                except OSError:
                    marker_text = ""
                marker_codes = parse_result_markers(marker_text)
                for sub_index in sub_indices:
                    subcommand = self._find_subcommand(step, sub_index)
                    if subcommand is None:
                        continue
                    rc = marker_codes.get(sub_index)
                    if rc is None:
                        if stopped:
                            subcommand.status = StepStatus.CANCELLED
                            subcommand.exit_code = None
                        elif exit_code != 0:
                            subcommand.status = StepStatus.FAILED
                            subcommand.exit_code = -1
                        continue
                    subcommand.exit_code = rc
                    subcommand.status = StepStatus.SUCCESS if rc == 0 else StepStatus.FAILED

                failed_sub = next(
                    (item for item in sorted(step.subcommands, key=lambda cmd: cmd.index) if item.status == StepStatus.FAILED),
                    None,
                )
                if stopped:
                    step.status = StepStatus.CANCELLED
                    step.exit_code = None
                    step.last_message = "Stopped by user."
                elif failed_sub is not None or exit_code != 0:
                    step.status = StepStatus.FAILED
                    step.exit_code = exit_code
                    failed_index = failed_sub.index if failed_sub is not None else "?"
                    failed_cmd = failed_sub.command if failed_sub is not None else "(unknown command)"
                    step.last_message = f"Failed subcommand #{failed_index}: {failed_cmd}"
                elif all(item.status == StepStatus.SUCCESS for item in step.subcommands):
                    step.status = StepStatus.SUCCESS
                    step.exit_code = 0
                    step.last_message = "All subcommands completed successfully."
                else:
                    step.status = StepStatus.RUNNING
                    step.exit_code = None
                    step.last_message = "Waiting for remaining batch commands."

            if stopped:
                self.project.state.status = ProjectStatus.CANCELLED
            elif step is None:
                if exit_code != 0:
                    self.project.state.status = ProjectStatus.FAILED
                    self.project.state.last_error = f"{plan.step_name} failed with exit code {exit_code}"
                else:
                    self.project.state.status = ProjectStatus.RUNNING
            elif step is not None and step.status == StepStatus.FAILED:
                self.project.state.status = ProjectStatus.FAILED
                self.project.state.last_error = step.last_message or f"{plan.step_name} failed with exit code {exit_code}"
            elif all(item.status == StepStatus.SUCCESS for item in self.project.state.steps):
                self.project.state.status = ProjectStatus.COMPLETED
            else:
                self.project.state.status = ProjectStatus.RUNNING
        elif plan.kind == "visualization":
            pending = self._pending_visualization
            if exit_code != 0:
                self.project.state.last_error = f"Visualization failed with exit code {exit_code}"
                self.visual_status_text.setPlainText(
                    f"{pending.summary if pending else ''}\n\nStatus: failed (exit={exit_code})"
                )
                self.preview_image_label.setPixmap(QPixmap())
                self.preview_image_label.setText("Visualization failed. Check the log for details.")
                self.preview_image_label.resize(480, 320)
            else:
                if pending is not None:
                    if pending.action == "preview":
                        self.project.visualization.last_preview_path = pending.output_bmp_path
                        self.project.visualization.last_render_signature = pending.render_signature
                    self.project.visualization.last_log_path = pending.log_path
                    self.project.visualization.last_render_summary = pending.summary
                    if pending.action == "preview":
                        self._display_preview_image(pending.output_bmp_path, pending.summary)
                    self.visual_status_text.setPlainText(
                        f"{pending.summary}\n\nStatus: success\nOutput: {pending.output_bmp_path}\nLog: {pending.log_path}"
                    )
        else:
            if stopped:
                self.project.state.status = ProjectStatus.CANCELLED
            elif exit_code != 0:
                self.project.state.status = ProjectStatus.FAILED
                self.project.state.last_error = f"{plan.label} failed with exit code {exit_code}"

        self.project_store.save(self.project)
        self.refresh_steps_view()
        self.refresh_outputs_view()
        self.refresh_status_labels()
        self._sync_summary_sidebar()

    def _handle_queue_finished(self, success: bool, message: str) -> None:
        if self._pending_visualization is not None:
            pending = self._pending_visualization
            self._pending_visualization = None
            if self._last_visualization_saved_status is not None:
                self.project.state.status = self._last_visualization_saved_status
            self._last_visualization_saved_status = None
            self.project.state.current_step = ""
            try:
                job_path = Path(pending.job_dir).expanduser().resolve()
                output_path = Path(pending.output_bmp_path).expanduser().resolve()
                if not output_path.is_relative_to(job_path):
                    shutil.rmtree(job_path, ignore_errors=True)
            except Exception:
                pass
            if success:
                self.project.state.last_error = ""
                self.statusBar().showMessage(f"Visualization completed: {pending.output_bmp_path}", 5000)
            else:
                self.statusBar().showMessage("Visualization failed. Check logs.", 5000)
            self.project_store.save(self.project)
            self.refresh_status_labels()
            self._update_action_states()
            self._sync_summary_sidebar()
            return

        if self._pending_preparation is not None:
            pending = self._pending_preparation
            self._pending_preparation = None
            if success:
                self._commit_preparation_result(
                    pending["prepared"],
                    str(pending["dem_path"]),
                    str(pending["signature"]),
                )
                message = "Data validation and preparation finished."
            else:
                self.project.state.status = ProjectStatus.FAILED
                self.project.state.last_error = self.project.state.last_error or "Data preparation failed."
                self.project_store.save(self.project)

        if self._pending_preparation is None:
            if self._stop_requested and not success:
                self.project.state.status = ProjectStatus.CANCELLED
            elif success:
                if self.project.state.steps and all(
                    item.status == StepStatus.SUCCESS for item in self.project.state.steps
                ):
                    self.project.state.status = ProjectStatus.COMPLETED
                elif self.project.state.steps:
                    self.project.state.status = ProjectStatus.GENERATED
                elif self._is_prepared_for_current_sources():
                    self.project.state.status = ProjectStatus.READY
            elif self.project.state.status == ProjectStatus.RUNNING:
                self.project.state.status = ProjectStatus.FAILED

        if self._stop_requested and not success:
            self.project.state.status = ProjectStatus.CANCELLED
        self._stop_requested = False
        self.project_store.save(self.project)
        self.refresh_status_labels()
        self._update_action_states()
        self._sync_summary_sidebar()
        self.statusBar().showMessage(message, 5000)

    def _handle_runner_state_changed(self, state: str) -> None:
        _ = state
        self._update_action_states()

    def refresh_steps_view(self) -> None:
        self.steps_tree.clear()
        for step in self.project.state.steps:
            item = QTreeWidgetItem(
                [
                    step.name,
                    step.status.value,
                    "" if step.exit_code is None else str(step.exit_code),
                    step.log_path,
                    step.last_message,
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, step.name)
            for subcommand in sorted(step.subcommands, key=lambda cmd: cmd.index):
                child = QTreeWidgetItem(
                    [
                        f"#{subcommand.index}: {subcommand.command}",
                        subcommand.status.value,
                        "" if subcommand.exit_code is None else str(subcommand.exit_code),
                        subcommand.log_path,
                        "",
                    ]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, step.name)
                item.addChild(child)
            self.steps_tree.addTopLevelItem(item)
        self.steps_tree.expandAll()
        self.run_monitor_page.empty_state_label.setVisible(self.steps_tree.topLevelItemCount() == 0)
        self._refresh_runfile_estimates()
        self._update_action_states()
        self._refresh_navigation_status()

    def refresh_outputs_view(self) -> None:
        self.outputs_tree.clear()
        try:
            work_dir = self.project.resolved_work_dir()
        except ValueError:
            self.results_page.empty_outputs_label.setVisible(True)
            self.summary_results_card.set_value("No outputs scanned")
            self.summary_results_card.set_body("Resolve a work directory first.")
            return
        if not work_dir.exists():
            self.results_page.empty_outputs_label.setVisible(True)
            self.summary_results_card.set_value("No outputs scanned")
            self.summary_results_card.set_body("Work directory does not exist yet.")
            return

        nodes = self.output_discovery_service.discover(work_dir)
        for node in nodes:
            self.outputs_tree.addTopLevelItem(self._output_item(node))
        self.outputs_tree.expandToDepth(1)
        self.results_page.empty_outputs_label.setVisible(self.outputs_tree.topLevelItemCount() == 0)
        self.summary_results_card.set_value(f"{len(nodes)} output roots")
        self.summary_results_card.set_body("Results and visualization outputs discovered.")
        self.results_page.output_card.set_value(f"{len(nodes)} output roots")
        self.results_page.output_card.set_body(str(work_dir))
        self._refresh_navigation_status()

    def _output_item(self, node: OutputNode) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.name, node.kind, node.path])
        for child in node.children:
            item.addChild(self._output_item(child))
        return item

    def _display_preview_image(self, image_path: str, summary: str) -> None:
        path = Path(image_path).expanduser()
        if not path.exists():
            self.preview_image_label.setPixmap(QPixmap())
            self.preview_image_label.setText(f"Preview image not found:\n{path}")
            self.preview_image_label.resize(480, 320)
            self.preview_meta_text.setPlainText(summary)
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.preview_image_label.setPixmap(QPixmap())
            self.preview_image_label.setText(f"Failed to load preview image:\n{path}")
            self.preview_image_label.resize(480, 320)
        else:
            self.preview_image_label.setText("")
            self.preview_image_label.setPixmap(pixmap)
            self.preview_image_label.resize(pixmap.size())

        details = summary.strip()
        if details:
            details += "\n\n"
        if not pixmap.isNull():
            details += f"Preview image: {path}\nImage size: {pixmap.width()} x {pixmap.height()}"
        else:
            details += f"Preview image: {path}"
        self.preview_meta_text.setPlainText(details)
        self.results_page.preview_card.set_value("Ready")
        self.results_page.preview_card.set_body(Path(image_path).name)

    def _validate_data_source_inputs(self) -> list[str]:
        errors: list[str] = []
        workflow = self.project.workflow
        environment = self.project.environment

        if not environment.isce_root.strip():
            errors.append("ISCE2 root is required.")
        else:
            isce_root = Path(environment.isce_root).expanduser()
            source_stack = isce_root / "contrib" / "stack" / "topsStack" / "stackSentinel.py"
            conda_stack = isce_root / "share" / "isce2" / "topsStack" / "stackSentinel.py"
            if not source_stack.exists() and not conda_stack.exists():
                errors.append(
                    "ISCE2 root does not contain topsStack stackSentinel.py in expected source or conda layout:\n"
                    f"- {source_stack}\n- {conda_stack}"
                )

        if not workflow.input_path:
            errors.append("Sentinel-1 input folder is required.")
        elif not Path(workflow.input_path).expanduser().is_dir():
            errors.append(f"Sentinel-1 input folder was not found: {workflow.input_path}")

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
            "wgs84",
        }:
            errors.append("Choose the GeoTIFF DEM height reference: EGM96 geoid or WGS84 ellipsoid.")

        if workflow.aux_path and not Path(workflow.aux_path).expanduser().is_dir():
            errors.append(f"AUX folder was not found: {workflow.aux_path}")

        if workflow.extract_zips and workflow.extract_dir:
            extract_dir = Path(workflow.extract_dir).expanduser()
            if extract_dir.exists() and not extract_dir.is_dir():
                errors.append(f"Extracted SAFE directory is not a directory: {workflow.extract_dir}")

        return errors

    def _validate_processing_inputs(self) -> list[str]:
        errors: list[str] = []
        workflow = self.project.workflow

        if workflow.use_common_overlap:
            if workflow.bbox_snwe.strip():
                try:
                    workflow.normalized_bbox()
                except ValueError as exc:
                    errors.append(str(exc))
        else:
            if not workflow.bbox_snwe.strip():
                errors.append("ISCE bbox (SNWE) is required unless 'Use common overlap' is enabled.")
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

        prepared = self.project.state.prepared_inputs
        if prepared.manifest_path and not Path(prepared.manifest_path).expanduser().exists():
            errors.append(f"Prepared manifest was not found: {prepared.manifest_path}")
        if self.project.state.prepared_dem_path and not Path(self.project.state.prepared_dem_path).expanduser().exists():
            errors.append(f"Prepared DEM was not found: {self.project.state.prepared_dem_path}")
        return errors

    def _find_step(self, name: str) -> RunStep | None:
        for step in self.project.state.steps:
            if step.name == name:
                return step
        return None

    def _step_item_from_item(self, item: QTreeWidgetItem | None) -> QTreeWidgetItem | None:
        if item is None:
            return None
        current = item
        while current.parent() is not None:
            current = current.parent()
        return current

    def _selected_steps(self) -> list[RunStep]:
        selected_items = self.steps_tree.selectedItems()
        if not selected_items:
            current = self.steps_tree.currentItem()
            selected_items = [current] if current is not None else []

        names: set[str] = set()
        for item in selected_items:
            step_item = self._step_item_from_item(item)
            if step_item is None:
                continue
            step_name = str(step_item.data(0, Qt.ItemDataRole.UserRole) or step_item.text(0)).strip()
            if step_name:
                names.add(step_name)

        if not names:
            return []
        # Keep deterministic execution order by run-file order.
        return [step for step in self.project.state.steps if step.name in names]

    def _open_steps_context_menu(self, pos) -> None:
        item = self.steps_tree.itemAt(pos)
        step_item = self._step_item_from_item(item)
        if step_item is None:
            return

        step_name = str(step_item.data(0, Qt.ItemDataRole.UserRole) or step_item.text(0)).strip()
        if step_name:
            matching = self.steps_tree.findItems(step_name, Qt.MatchFlag.MatchExactly, 0)
            if matching and not matching[0].isSelected():
                self.steps_tree.clearSelection()
                matching[0].setSelected(True)
                self.steps_tree.setCurrentItem(matching[0])

        menu = QMenu(self)
        run_action = menu.addAction("Run Selected Step")
        run_action.setEnabled((not self.runner.is_running()) and bool(self._selected_steps()))
        chosen = menu.exec(self.steps_tree.viewport().mapToGlobal(pos))
        if chosen == run_action:
            self.run_selected_step()

    @staticmethod
    def _find_subcommand(step: RunStep, index: int) -> RunSubcommand | None:
        for item in step.subcommands:
            if item.index == index:
                return item
        return None

    def _refresh_runfile_estimates(self) -> None:
        current_parallel = max(1, self.project.workflow.num_proc)
        if not self.project.state.steps:
            text = "Generate workflow first. Run-file command estimates will appear here."
            self.runfile_estimate_text.setPlainText(text)
            self.monitor_runfile_estimate_text.setPlainText(text)
            self.processing_page.parallel_card.set_value(f"num_proc = {current_parallel}")
            return

        lines = [f"Current num_proc = {current_parallel}", ""]
        for step in self.project.state.steps:
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
        self.runfile_estimate_text.setPlainText(text)
        self.monitor_runfile_estimate_text.setPlainText(text)
        self.processing_page.parallel_card.set_value(f"num_proc = {current_parallel}")
        self.processing_page.parallel_card.set_body("Review estimates before running large stacks.")

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def _recover_loaded_state(self) -> bool:
        changed = False
        state = self.project.state
        prepared = state.prepared_inputs

        if prepared.entries and state.prepared_dem_path and not state.prepared_signature:
            state.prepared_signature = self._preparation_signature(self.project.workflow)
            changed = True

        if state.prepared_signature and not self._is_prepared_for_current_sources():
            state.prepared_signature = ""
            changed = True

        if state.status == ProjectStatus.RUNNING:
            if state.steps:
                all_success = all(step.status == StepStatus.SUCCESS for step in state.steps)
                new_status = ProjectStatus.COMPLETED if all_success else ProjectStatus.GENERATED
            elif self._is_prepared_for_current_sources():
                new_status = ProjectStatus.READY
            else:
                new_status = ProjectStatus.DRAFT
            if state.status != new_status:
                state.status = new_status
                changed = True
            if state.current_step:
                state.current_step = ""
                changed = True

        return changed

    def _toggle_common_overlap_mode(self, checked: bool) -> None:
        self.aoi_iw_page.set_bbox_enabled(not checked)
        if checked:
            self.aoi_iw_page.set_bbox_components("", "", "", "")
        self._update_project_from_form()

    def _sync_iw_selection_card(self) -> None:
        swaths = self.aoi_iw_page.selected_swaths() or "1 2 3"
        text = " ".join(f"IW{token}" for token in swaths.split()) if swaths.strip() else "None"
        self.aoi_iw_page.iw_card.set_value(text)
        self.summary_selection_card.set_value(text)
        self.summary_selection_card.set_body("Swath-level control is active.")

    def confirm_aoi_iw(self) -> None:
        self._update_project_from_form()
        errors = self._validate_processing_inputs()
        if errors:
            self._show_error("Invalid AOI/BBox/IW", "\n".join(errors))
            return
        self._sync_summary_sidebar()
        self.statusBar().showMessage("AOI/BBox/IW parameters confirmed.", 4000)

    def import_aoi_file(self) -> None:
        source_path = self.aoi_source_edit.text().strip()
        if not source_path:
            self._show_error("AOI import failed", "Select a KML or SHP AOI file first.")
            return

        try:
            result = self.aoi_import_service.import_aoi(source_path)
        except Exception as exc:
            self._show_error("AOI import failed", str(exc))
            return

        self._last_aoi_import = result
        self.use_common_overlap_check.setChecked(False)
        self.aoi_iw_page.set_bbox_enabled(True)
        south, north, west, east = result.bbox_snwe.split()
        self.aoi_iw_page.set_bbox_components(south, north, west, east)
        self.aoi_iw_page.source_card.set_value(Path(result.source_path).name)
        self.aoi_iw_page.source_card.set_body("Imported AOI data was used to fill ISCE bbox.")
        notes = list(result.notes)
        if result.warnings:
            notes.extend(["", "Warnings:"])
            notes.extend(f"- {line}" for line in result.warnings)
        self.verify_notes.setPlainText("\n".join(notes))
        self.aoi_iw_page.verify_alert_label.clear()
        self.aoi_iw_page.verify_alert_label.hide()
        self._update_project_from_form()
        self.recommend_iw()
        self.statusBar().showMessage("AOI imported and ISCE bbox updated.", 5000)

    def _first_entry_for_iw_recommendation(self) -> str:
        prepared = self.project.state.prepared_inputs.entries
        if prepared:
            return prepared[0].path

        input_dir = Path(self.project.workflow.input_path).expanduser()
        if not input_dir.is_dir():
            raise ValueError("Prepare data first or set a valid Sentinel-1 input folder.")
        report = self.input_catalog_service.scan(input_dir)
        if not report.entries:
            raise ValueError("No Sentinel-1 ZIP/SAFE inputs were found for IW recommendation.")
        return report.entries[0].path

    def _current_aoi_geometries(self) -> list[list[tuple[float, float]]]:
        source_path = self.aoi_source_edit.text().strip()
        if not source_path:
            return self._last_aoi_import.geometries if self._last_aoi_import else []
        if self._last_aoi_import and Path(self._last_aoi_import.source_path) == Path(source_path).expanduser():
            return self._last_aoi_import.geometries
        try:
            self._last_aoi_import = self.aoi_import_service.import_aoi(source_path)
        except Exception:
            return self._last_aoi_import.geometries if self._last_aoi_import else []
        return self._last_aoi_import.geometries

    def recommend_iw(self) -> None:
        self._update_project_from_form()
        self.aoi_iw_page.verify_alert_label.clear()
        self.aoi_iw_page.verify_alert_label.hide()
        if self.project.workflow.use_common_overlap:
            self._show_error("IW recommendation unavailable", "Disable 'Use common overlap' and provide ISCE bbox first.")
            return
        if not self.project.workflow.bbox_snwe.strip():
            self._show_error("IW recommendation unavailable", "ISCE bbox is required for IW recommendation.")
            return

        try:
            basis_entry = self._first_entry_for_iw_recommendation()
            result = self.iw_recommendation_service.recommend(
                basis_entry,
                self.project.workflow.normalized_bbox(),
            )
        except Exception as exc:
            self._show_error("IW recommendation failed", str(exc))
            return

        self._last_iw_recommendation = result
        self.aoi_iw_page.set_selected_swaths(result.recommended_swaths)
        self._sync_iw_selection_card()
        notes = list(result.notes)
        if result.warnings:
            notes.extend(["", "Warnings:"])
            notes.extend(f"- {line}" for line in result.warnings)
        self.verify_notes.setPlainText("\n".join(notes))
        self._update_project_from_form()
        self.statusBar().showMessage(f"Recommended IW: {result.recommended_swaths}", 5000)

    def _selected_swath_set(self) -> set[str]:
        return {item for item in (self.aoi_iw_page.selected_swaths() or "").split() if item}

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
        self._update_project_from_form()
        self.aoi_iw_page.verify_alert_label.clear()
        self.aoi_iw_page.verify_alert_label.hide()
        if self.project.workflow.use_common_overlap or not self.project.workflow.bbox_snwe.strip():
            self._show_error(
                "Verify unavailable",
                "Provide ISCE bbox first (disable 'Use common overlap').",
            )
            return

        try:
            bbox_text = self.project.workflow.normalized_bbox()
            south, north, west, east = [float(token) for token in bbox_text.split()]
            basis_entry = self._first_entry_for_iw_recommendation()
            self._last_iw_recommendation = self.iw_recommendation_service.recommend(basis_entry, bbox_text)
        except Exception as exc:
            self._show_error("Verify failed", str(exc))
            return

        footprints = {
            swath: item.polygon
            for swath, item in self._last_iw_recommendation.footprints.items()
        }
        burst_polygons = {
            swath: {item.burst_id: item.polygon for item in bursts}
            for swath, bursts in self._last_iw_recommendation.bursts.items()
        }
        selected_burst_pairs = self._selected_auto_burst_pairs(self._last_iw_recommendation)
        burst_union_bbox = self._union_bbox_from_bursts(self._last_iw_recommendation, selected_burst_pairs)

        dem_bbox = None
        coverage_notes: list[str] = []
        coverage_warnings: list[str] = []
        if self.project.state.prepared_dem_path and burst_union_bbox is not None:
            try:
                coverage = self.dem_coverage_service.assess(
                    self.project.state.prepared_dem_path,
                    burst_union_bbox,
                )
                dem_bbox = coverage.dem_bbox_snwe
                coverage_notes.extend(coverage.notes)
                coverage_warnings.extend(coverage.warnings)
            except Exception as exc:
                coverage_warnings.append(f"DEM coverage assessment failed: {exc}")
        elif not self.project.state.prepared_dem_path:
            coverage_warnings.append("Prepared DEM path is empty; DEM coverage was not assessed.")
        else:
            coverage_warnings.append("No auto-selected burst intersects the selected IW + bbox.")

        plot = VerifyPlotData(
            aoi_geometries=list(self._current_aoi_geometries()),
            bbox_snwe=(south, north, west, east),
            iw_polygons=footprints,
            selected_swaths=set((self.aoi_iw_page.selected_swaths() or "").split()),
            burst_polygons=burst_polygons,
            selected_bursts=selected_burst_pairs,
            dem_bbox_snwe=dem_bbox,
        )
        self.aoi_iw_page.verify_panel.set_plot(plot)

        notes = []
        if self._last_aoi_import:
            notes.append(f"AOI source: {self._last_aoi_import.source_path}")
        notes.append(f"ISCE bbox (SNWE): {bbox_text}")
        notes.append(f"Selected IW: {self.aoi_iw_page.selected_swaths() or '-'}")
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
        if self._last_iw_recommendation:
            notes.extend(self._last_iw_recommendation.notes)
            if self._last_iw_recommendation.warnings:
                notes.extend(["", "Warnings:"])
                notes.extend(f"- {line}" for line in self._last_iw_recommendation.warnings)
        if coverage_notes:
            notes.extend(["", "DEM coverage:"])
            notes.extend(coverage_notes)
        if coverage_warnings:
            notes.extend(["", "Coverage warnings:"])
            notes.extend(f"- {line}" for line in coverage_warnings)
            self.aoi_iw_page.verify_alert_label.setText(f"DEM coverage warning: {coverage_warnings[0]}")
            self.aoi_iw_page.verify_alert_label.show()
        else:
            self.aoi_iw_page.verify_alert_label.clear()
            self.aoi_iw_page.verify_alert_label.hide()
        self.verify_notes.setPlainText("\n".join(notes))
        self.statusBar().showMessage("AOI/BBox/IW + burst/DEM verify plot updated.", 5000)

    def export_verify_geometry_png(self) -> None:
        try:
            work_dir = self.project.resolved_work_dir()
        except ValueError:
            self._show_error("Export failed", "Set working directory first.")
            return
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        default_path = work_dir / ".iscegui" / "verify" / f"aoi_iw_verify_{stamp}.png"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export verify image",
            str(default_path),
            "PNG image (*.png)",
        )
        if not output_path:
            return
        if not output_path.lower().endswith(".png"):
            output_path = f"{output_path}.png"
        try:
            saved = self.aoi_iw_page.verify_panel.export_png(output_path)
        except Exception as exc:
            self._show_error("Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Verify image exported: {saved}", 5000)

    def _populate_reference_candidates(self) -> None:
        dates = self._prepared_dates()
        recommended = dates[0] if dates else "Unavailable"
        self.processing_page.reference_hint_label.setText(
            (
                f"Recommended reference date from prepared inputs: {recommended}. "
                "Leave empty to let workflow choose automatically."
            )
            if dates
            else "Run Validate & Prepare Data to populate available dates. Leave empty to auto-select reference."
        )

    def _prepared_dates(self) -> list[str]:
        dates: set[str] = set()
        for entry in self.project.state.prepared_inputs.entries:
            match = re.search(r"(20\d{6})", Path(entry.path).name)
            if match:
                dates.add(match.group(1))
        return sorted(dates)

    def _preview_generate_command(self) -> None:
        self._update_project_from_form()
        if not self._is_prepared_for_current_sources():
            self.command_preview_text.setPlainText(
                "Prepare data first. The generated stackSentinel.py command will appear here."
            )
            return
        try:
            command = self.workflow_service.build_generate_command(
                self.project,
                self.project.state.prepared_inputs,
                dem_path=self.project.state.prepared_dem_path,
            )
        except Exception as exc:
            self.command_preview_text.setPlainText(f"Preview unavailable:\n{exc}")
            return
        self.command_preview_text.setPlainText(command)
        self.statusBar().showMessage("Generated command preview updated.", 3000)

    def _rescan_existing_runfiles(self) -> None:
        try:
            self.workflow_service.synchronize_project_steps(self.project)
        except Exception as exc:
            self._show_error("Re-scan failed", str(exc))
            return
        self.refresh_steps_view()
        self.refresh_status_labels()
        self._sync_summary_sidebar()
        self.statusBar().showMessage("Existing run_files re-scanned.", 4000)

    def _handle_step_selection_changed(self) -> None:
        self._update_action_states()
        self._update_step_detail_panel()

    def _update_step_detail_panel(self) -> None:
        selected_steps = self._selected_steps()
        if len(selected_steps) > 1:
            lines = [f"Selected steps: {len(selected_steps)}", ""]
            lines.extend(f"- {step.name} ({step.status.value})" for step in selected_steps)
            self.command_detail_text.setPlainText("\n".join(lines))
            return

        item = self.steps_tree.currentItem()
        if item is None:
            self.command_detail_text.setPlainText("")
            return
        root = self._step_item_from_item(item)
        if root is None:
            return
        step = self._find_step(str(root.data(0, Qt.ItemDataRole.UserRole) or root.text(0)))
        if step is None:
            self.command_detail_text.setPlainText("")
            return
        lines = [
            f"Step: {step.name}",
            f"Status: {step.status.value}",
            f"Run file: {step.path}",
            f"Batch log: {step.log_path}",
            f"Message: {step.last_message or '-'}",
        ]
        if item.parent() is not None:
            text = item.text(0)
            try:
                sub_index = int(text.split(":", 1)[0].lstrip("#"))
            except ValueError:
                sub_index = -1
            sub = self._find_subcommand(step, sub_index)
            if sub is not None:
                lines.extend(
                    [
                        "",
                        f"Subcommand #{sub.index}",
                        f"Command: {sub.command}",
                        f"Status: {sub.status.value}",
                        f"Exit: {sub.exit_code if sub.exit_code is not None else '-'}",
                        f"Log: {sub.log_path}",
                    ]
                )
        else:
            if step.subcommands:
                lines.extend(["", "Subcommands:"])
                lines.extend(f"- #{sub.index}: {sub.command}" for sub in step.subcommands)
        self.command_detail_text.setPlainText("\n".join(lines))

    def _sync_summary_sidebar(self) -> None:
        prepared = self.project.state.prepared_inputs
        self.summary_sources_card.set_value(
            f"{len(prepared.entries)} prepared inputs" if prepared.entries else "Not prepared"
        )
        if self.project.state.prepared_dem_path:
            self.summary_sources_card.set_body(Path(self.project.state.prepared_dem_path).name)
        else:
            self.summary_sources_card.set_body("Dataset, orbit, and DEM still need validation.")
        self.data_sources_page.orbit_card.set_value(
            Path(self.project.workflow.orbit_path).name if self.project.workflow.orbit_path else "Not set"
        )
        self.data_sources_page.dem_card.set_value(
            Path(self.project.workflow.dem_path).name if self.project.workflow.dem_path else "Not set"
        )
        self.data_sources_page.orbit_card.set_body(
            self.project.workflow.orbit_path or "Point to local EOF orbit files."
        )
        self.data_sources_page.dem_card.set_body(
            self.project.state.prepared_dem_path or self.project.workflow.dem_path or "GeoTIFF or native ISCE DEM path."
        )

        try:
            bbox = self.project.workflow.normalized_bbox() if self.project.workflow.bbox_snwe else ""
        except ValueError:
            bbox = ""
        if self.project.workflow.use_common_overlap:
            self.summary_aoi_card.set_value("Common overlap")
            self.summary_aoi_card.set_body("Empty bbox is allowed by compatibility switch.")
            self.aoi_iw_page.bbox_card.set_value("Common overlap")
            self.aoi_iw_page.bbox_card.set_body("ISCE bbox will be omitted.")
        else:
            self.summary_aoi_card.set_value(bbox or "Not set")
            self.summary_aoi_card.set_body("ISCE bbox in SNWE decimal degrees.")
            self.aoi_iw_page.bbox_card.set_value(bbox or "Not set")
            self.aoi_iw_page.bbox_card.set_body("Final stackSentinel -b parameter.")
        self.aoi_iw_page.source_card.set_value(
            Path(self.project.workflow.aoi_source_path).name if self.project.workflow.aoi_source_path else "Manual"
        )
        self.aoi_iw_page.source_card.set_body(
            self.project.workflow.aoi_source_path or "AOI file optional; you can fill bbox manually."
        )

        swaths = self.project.workflow.swath_numbers.strip() or "1 2 3"
        self.summary_selection_card.set_value(" ".join(f"IW{item}" for item in swaths.split()))
        self.aoi_iw_page.iw_card.set_value(" ".join(f"IW{item}" for item in swaths.split()))
        self.summary_reference_card.set_value(self.project.workflow.reference_date or "Auto")
        self.summary_reference_card.set_body(
            "Manual override applied." if self.project.workflow.reference_date else "Master date left to workflow defaults."
        )
        self.summary_processing_card.set_value(
            f"{self.project.workflow.workflow} / {self.project.workflow.coregistration}"
        )
        self.summary_processing_card.set_body(
            f"Looks {self.project.workflow.azimuth_looks}x{self.project.workflow.range_looks}, num_proc={self.project.workflow.num_proc}"
        )
        self.processing_page.plan_card.set_value(
            f"{self.project.workflow.workflow} / {self.project.workflow.coregistration}"
        )
        self.processing_page.plan_card.set_body(
            f"Range looks {self.project.workflow.range_looks}, azimuth looks {self.project.workflow.azimuth_looks}"
        )
        if self.project.visualization.last_preview_path:
            self.summary_results_card.set_body(Path(self.project.visualization.last_preview_path).name)

        self._refresh_navigation_status()

    def _refresh_navigation_status(self) -> None:
        self._set_nav_status(
            "data_sources",
            "Ready" if self._is_prepared_for_current_sources() else "Pending",
            "ready" if self._is_prepared_for_current_sources() else "warning",
        )
        swath_ok = bool(self.project.workflow.swath_numbers.strip() or self.aoi_iw_page.selected_swaths())
        if self.project.workflow.use_common_overlap:
            bbox_ok = True
        else:
            try:
                self.project.workflow.normalized_bbox()
                bbox_ok = True
            except ValueError:
                bbox_ok = False
        aoi_iw_ok = bbox_ok and swath_ok
        self._set_nav_status("aoi_iw", "Ready" if aoi_iw_ok else "Check", "ready" if aoi_iw_ok else "warning")
        self._set_nav_status(
            "processing",
            self.project.state.status.value,
            self._tone_for_status(self.project.state.status.value),
        )
        has_steps = bool(self.project.state.steps)
        self._set_nav_status("monitor", "Ready" if has_steps else "Pending", "ready" if has_steps else "neutral")
        has_results = self.outputs_tree.topLevelItemCount() > 0
        self._set_nav_status("results", "Ready" if has_results else "Pending", "ready" if has_results else "neutral")
        self._sync_nav_selection_state()

    def _set_nav_status(self, key: str, text: str, tone: str) -> None:
        self._nav_items[key].set_status(text, tone)

    def _sync_nav_selection_state(self) -> None:
        current_row = self.workflow_nav.currentRow()
        for row in range(self.workflow_nav.count()):
            item = self.workflow_nav.item(row)
            key = str(item.data(Qt.ItemDataRole.UserRole))
            nav_item = self._nav_items.get(key)
            if nav_item is not None:
                nav_item.set_selected(row == current_row)

    def _environment_health_badge(self) -> tuple[str, str]:
        text = self.project.state.last_validation.strip()
        if not text:
            return "Env unchecked", "warning"
        if "[FAIL]" in text:
            return "Env issue", "failed"
        return "Env ready", "ready"

    @staticmethod
    def _tone_for_status(status_text: str) -> str:
        mapping = {
            "draft": "neutral",
            "ready": "ready",
            "generated": "running",
            "running": "running",
            "completed": "success",
            "success": "success",
            "pending": "neutral",
            "failed": "failed",
            "cancelled": "warning",
        }
        return mapping.get(status_text, "neutral")

    def _set_current_page(self, key: str) -> None:
        if key not in self._page_index_by_key:
            return
        self.workflow_nav.setCurrentRow(self._page_index_by_key[key])
