"""Main application window with practitioner-oriented workflow shell."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QThread, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QTreeWidgetItem,
)

from insar_pilot import __version__
from insar_pilot.app.settings import AppSettings
from insar_pilot.bootstrap import create_default_project
from insar_pilot.download import (
    DownloadService,
    DownloadStorage,
    DownloadTask,
    SearchService,
    create_dem_task,
)
from insar_pilot.download.credentials import load_earthdata_credentials
from insar_pilot.download.map_credentials import load_tianditu_key
from insar_pilot.download.opentopography_credentials import load_opentopography_key
from insar_pilot.download.tile_proxy import TiandituTileProxy
from insar_pilot.i18n import Translator
from insar_pilot.domain.project import (
    APP_METADATA_DIR,
    EnvironmentConfig,
    PreparedInputs,
    ProjectDocument,
    ProjectStatus,
    RunSubcommand,
    RunStep,
    StepStatus,
    WorkflowConfig,
)
from insar_pilot.services.command_plan import CommandPlan
from insar_pilot.services.aoi_import import AoiImportResult, AoiImportService
from insar_pilot.services.dem_coverage import DemCoverageService
from insar_pilot.services.dem_preparer import DemPreparationService
from insar_pilot.services.env_probe import EnvironmentProbe
from insar_pilot.services.input_catalog import InputCatalogReport, InputCatalogService
from insar_pilot.services.iw_recommendation import IwRecommendationResult, IwRecommendationService
from insar_pilot.services.output_discovery import OutputDiscoveryService, OutputNode
from insar_pilot.services.preflight import PreflightReport, PreflightService
from insar_pilot.services.project_store import ProjectStore
from insar_pilot.services.run_executor import ProcessRunner
from insar_pilot.services.runfile_plan import (
    build_parallel_batch_command,
    count_commands,
    parse_result_markers,
    parse_run_file,
    split_batches_for_parallelism,
)
from insar_pilot.services.stack_generator import StackWorkflowService
from insar_pilot.services.visualization_service import (
    VisualizationBuildResult,
    VisualizationRequest,
    VisualizationService,
)
from insar_pilot.ui.pages.aoi_iw_page import AoiIwPage
from insar_pilot.ui.pages.data_download_page import DataDownloadPage
from insar_pilot.ui.pages.data_sources_page import DataSourcesPage
from insar_pilot.ui.download_worker import (
    CredentialWorker,
    DownloadWorker,
    OpenTopographyKeyWorker,
    SearchWorker,
    TiandituKeyWorker,
)
from insar_pilot.ui.pages.processing_plan_page import ProcessingPlanPage
from insar_pilot.ui.pages.project_start_page import ProjectStartPage
from insar_pilot.ui.pages.processing_setup_page import ProcessingSetupPage
from insar_pilot.ui.pages.results_page import ResultsPage
from insar_pilot.ui.pages.run_monitor_page import RunMonitorPage
from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.widgets.geometry_verify_panel import VerifyPlotData
from insar_pilot.ui.icons import BrandAssets
from insar_pilot.ui.widgets.combo_wheel_guard import install_no_scroll_button_focus, install_no_wheel_on_combos
from insar_pilot.ui.widgets.log_console import append_text_preserving_scroll
from insar_pilot.ui.widgets.status_badge import StatusBadge
from insar_pilot.ui.widgets.summary_card import SummaryCard
from insar_pilot.ui.widgets.top_workflow_stepper import TopWorkflowStepper


class MainWindow(QMainWindow):
    """Stage 2 shell that preserves backend behavior and reorganizes the UX."""

    def __init__(self, project: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.app_settings = AppSettings()
        self.translator = Translator("en")
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
        self.preflight_service = PreflightService()
        self.download_search_service = SearchService()
        self.download_service = DownloadService()
        self.tianditu_tile_proxy = TiandituTileProxy()
        self.tianditu_tile_proxy.start()
        self.runner = ProcessRunner(project.environment, self)
        self._last_catalog_report: InputCatalogReport | None = None
        self._download_page_status = "Ready"
        self._download_page_message = "Define AOI, dates, and Sentinel-1 SLC filters."
        self._download_thread: QThread | None = None
        self._download_worker: DownloadWorker | None = None
        self._download_search_thread: QThread | None = None
        self._download_search_worker: SearchWorker | None = None
        self._credential_thread: QThread | None = None
        self._credential_worker: CredentialWorker | None = None
        self._tianditu_thread: QThread | None = None
        self._tianditu_worker: TiandituKeyWorker | None = None
        self._tianditu_check_origin = "idle"
        self._opentopography_thread: QThread | None = None
        self._opentopography_worker: OpenTopographyKeyWorker | None = None
        self._opentopography_check_origin = "idle"
        self._active_search_output_dir = ""
        self._download_tasks: list[DownloadTask] = []
        self._download_task_status: dict[str, str] = {}
        self._download_task_message: dict[str, str] = {}
        self._download_credentials_ok = False
        self._pending_preparation: dict[str, object] | None = None
        self._pending_visualization: VisualizationBuildResult | None = None
        self._last_aoi_import: AoiImportResult | None = None
        self._last_iw_recommendation: IwRecommendationResult | None = None
        self._last_visualization_saved_status: ProjectStatus | None = None
        self._stop_requested = False
        self._step_keys = ["data_download", "setup", "monitor", "results"]
        self._step_status: dict[str, tuple[str, str]] = {}
        self._page_index_by_key: dict[str, int] = {}

        self.setWindowTitle(self.translator.tr("app.title"))
        self.setWindowIcon(BrandAssets.icon())
        self.resize(1720, 980)
        self.setMinimumSize(1366, 768)

        self._build_ui()
        self._alias_page_widgets()
        self.data_download_page.set_tianditu_proxy_url(self.tianditu_tile_proxy.base_url)
        self._refresh_download_capability()
        self._connect_page_actions()
        self.combo_wheel_guard = install_no_wheel_on_combos(self)
        install_no_scroll_button_focus(self)
        self._connect_runner()
        self._populate_form_from_project()
        self._populate_download_credentials()
        self._populate_tianditu_key()
        self._populate_opentopography_key()
        self.refresh_steps_view()
        self.refresh_outputs_view()
        self.refresh_status_labels()
        self._sync_summary_sidebar()
        self._refresh_navigation_status()
        self._refresh_start_page()
        self._restore_layout_settings()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.tianditu_tile_proxy.stop)

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        root.addWidget(self._build_project_header())
        root.addWidget(self._build_page_stack(), 1)
        self.setCentralWidget(central)

        self._build_project_inspector_dock()
        self._build_log_console()
        self._build_menu_bar()
        self._build_main_toolbar()

    def _build_project_header(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("projectHeader")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(0)
        title = QLabel(self.translator.tr("app.title"))
        title.setObjectName("headerTitle")
        subtitle = QLabel(self.translator.tr("app.subtitle"))
        subtitle.setObjectName("headerSubTitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        layout.addLayout(title_col, 1)
        layout.addWidget(self._build_workflow_stepper(), 0, Qt.AlignmentFlag.AlignVCenter)

        project_meta = QFrame()
        project_meta.setObjectName("projectHeaderMeta")
        project_col = QVBoxLayout()
        project_col.setContentsMargins(10, 4, 10, 4)
        project_col.setSpacing(2)
        self.header_project_label = QLabel(f"{self.translator.tr('header.project')}: new session")
        self.header_current_step_label = QLabel(f"{self.translator.tr('header.current_step')}: -")
        project_col.addWidget(self.header_project_label)
        project_col.addWidget(self.header_current_step_label)
        project_meta.setLayout(project_col)
        layout.addWidget(project_meta, 0, Qt.AlignmentFlag.AlignVCenter)

        self.header_status_badge = StatusBadge("draft", "neutral")
        self.header_env_badge = StatusBadge("Env unchecked", "warning")
        layout.addWidget(self.header_status_badge)
        layout.addWidget(self.header_env_badge)
        return widget

    def _build_workflow_stepper(self) -> TopWorkflowStepper:
        self.workflow_stepper = TopWorkflowStepper()
        self.workflow_stepper.setMaximumWidth(500)
        self.workflow_stepper.set_steps(
            [
                ("Data", "Sentinel-1 Data Download"),
                ("Setup", "Processing Setup"),
                ("Run", "Run Executor"),
                ("Results", "Results Quicklook"),
            ]
        )
        return self.workflow_stepper

    def _build_page_stack(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.page_stack = QStackedWidget()
        layout.addWidget(self.page_stack)

        self.project_start_page = ProjectStartPage()
        self.project_start_page.set_version(__version__)
        self.project_start_page.set_notices(
            [
                "Project folders keep downloads, processing state, logs, and quicklook outputs together.",
                "Launch from the target runtime environment before validating or running processing.",
                "Use Results after processing to browse quicklooks and exported products.",
            ]
        )
        self.data_download_page = DataDownloadPage()
        self.processing_setup_page = ProcessingSetupPage()
        self.legacy_data_sources_page = DataSourcesPage()
        self.legacy_aoi_iw_page = AoiIwPage()
        self.legacy_processing_page = ProcessingPlanPage()
        self.data_sources_page = self.processing_setup_page
        self.aoi_iw_page = self.processing_setup_page
        self.processing_page = self.processing_setup_page
        self.run_monitor_page = RunMonitorPage()
        self.results_page = ResultsPage()

        self.page_stack.addWidget(self.project_start_page)
        self._page_index_by_key["start"] = 0
        pages = [
            ("data_download", "Data", self.translator.tr("nav.data_download"), self.data_download_page),
            ("setup", "Setup", self.translator.tr("nav.processing_setup"), self.processing_setup_page),
            ("monitor", "Run", self.translator.tr("nav.monitor"), self.run_monitor_page),
            ("results", "Results", self.translator.tr("nav.results"), self.results_page),
        ]
        for index, (key, _title, _tooltip, widget) in enumerate(pages, start=1):
            self.page_stack.addWidget(widget)
            self._page_index_by_key[key] = index

        self.page_stack.setCurrentIndex(0 if not self._has_project_workspace() else self._page_index_by_key["data_download"])
        self._sync_nav_selection_state()
        self._apply_page_spacing()
        return container

    def _build_project_inspector_dock(self) -> None:
        self.project_inspector_dock = QDockWidget("Project Inspector", self)
        self.project_inspector_dock.setObjectName("projectInspectorDock")
        self.project_inspector_dock.setWidget(self._build_summary_sidebar())
        self.project_inspector_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.project_inspector_dock)
        self.project_inspector_dock.hide()

    def _build_summary_sidebar(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        # Add left breathing room so the summary column does not sit on the splitter line.
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(10)

        title = QLabel(self.translator.tr("summary.title"))
        title.setObjectName("summaryCardTitle")
        layout.addWidget(title)

        self.summary_download_card = SummaryCard(
            self.translator.tr("summary.download.title"),
            "Ready",
            "Define AOI, dates, and Sentinel-1 SLC filters.",
        )
        self.summary_sources_card = SummaryCard(self.translator.tr("summary.setup.title"), "Not prepared", "Dataset, orbit, and DEM readiness.")
        self.summary_aoi_card = SummaryCard("AOI / BBox", "Not set", "AOI file is optional input; bbox is the processing parameter.")
        self.summary_selection_card = SummaryCard("IW", "IW1 IW2 IW3", "Swath-level control for the processing workflow.")
        self.summary_reference_card = SummaryCard("Reference", "Auto", "Manual override optional.")
        self.summary_processing_card = SummaryCard("Processing", "Not generated", "Workflow, coreg, looks, and concurrency.")
        self.summary_results_card = SummaryCard("Results", "No outputs scanned", "Quicklooks and processing outputs.")
        for card in (
            self.summary_sources_card,
            self.summary_download_card,
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

    def _build_menu_bar(self) -> None:
        self.action_new_project = QAction(IconProvider.icon("info"), "New Project", self)
        self.action_open_project = QAction(IconProvider.icon("folder"), "Open Project", self)
        self.action_save_project = QAction(IconProvider.icon("save"), "Save Project", self)
        self.action_toggle_console = QAction(IconProvider.icon("settings"), "Log Console", self)
        self.action_toggle_console.setCheckable(True)
        self.action_exit = QAction("Exit", self)
        self.action_search = QAction(IconProvider.icon("search"), "Search Scenes", self)
        self.action_download = QAction(IconProvider.icon("download"), "Download Selected", self)
        self.action_use_sources = QAction(IconProvider.icon("import"), "Use as Data Sources", self)
        self.action_validate = QAction(IconProvider.icon("check"), "Validate", self)
        self.action_prepare = QAction(IconProvider.icon("run"), "Prepare Data", self)
        self.action_preview_command = QAction(IconProvider.icon("preview"), "Preview Command", self)
        self.action_generate = QAction(IconProvider.icon("generate"), "Generate Workflow", self)
        self.action_run_next = QAction(IconProvider.icon("run"), "Run Next Step", self)
        self.action_run_selected = QAction("Run Selected Step", self)
        self.action_run_remaining = QAction("Run Remaining Steps", self)
        self.action_stop = QAction(IconProvider.icon("stop"), "Stop", self)
        self.action_refresh_outputs = QAction(IconProvider.icon("refresh"), "Refresh Outputs", self)
        self.action_about = QAction("About", self)

        project_menu = self.menuBar().addMenu("Project")
        project_menu.addActions([self.action_new_project, self.action_open_project, self.action_save_project])
        project_menu.addSeparator()
        project_menu.addAction(self.action_exit)

        self.action_project_inspector = self.project_inspector_dock.toggleViewAction()
        self.action_project_inspector.setText("Project Inspector")
        self.action_project_inspector.setIcon(IconProvider.icon("settings"))

        self.view_menu = self.menuBar().addMenu("View")
        self.view_menu.addAction(self.action_project_inspector)
        self.view_menu.addAction(self.action_toggle_console)

        data_menu = self.menuBar().addMenu("Data")
        data_menu.addActions([self.action_search, self.action_download, self.action_use_sources])

        processing_menu = self.menuBar().addMenu("Processing")
        processing_menu.addActions([
            self.action_validate,
            self.action_prepare,
            self.action_preview_command,
            self.action_generate,
        ])

        run_menu = self.menuBar().addMenu("Run")
        run_menu.addActions([
            self.action_run_next,
            self.action_run_selected,
            self.action_run_remaining,
            self.action_stop,
        ])

        results_menu = self.menuBar().addMenu("Results")
        results_menu.addAction(self.action_refresh_outputs)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.action_about)

    def _build_main_toolbar(self) -> None:
        toolbar = QToolBar("Workflow", self)
        toolbar.setObjectName("mainWorkflowToolbar")
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setMovable(False)
        toolbar.addAction(self.action_open_project)
        toolbar.addAction(self.action_save_project)
        toolbar.addSeparator()
        toolbar.addAction(self.action_search)
        toolbar.addAction(self.action_download)
        toolbar.addSeparator()
        toolbar.addAction(self.action_validate)
        toolbar.addAction(self.action_generate)
        toolbar.addSeparator()
        toolbar.addAction(self.action_run_next)
        toolbar.addAction(self.action_stop)
        toolbar.addSeparator()
        toolbar.addAction(self.action_refresh_outputs)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        self.main_toolbar = toolbar

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
        self.preflight_text = self.processing_page.preflight_text
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
        self.action_new_project.triggered.connect(self.new_project)
        self.action_open_project.triggered.connect(self.open_project)
        self.action_save_project.triggered.connect(self.save_project)
        self.action_toggle_console.triggered.connect(self._toggle_log_console)
        self.action_exit.triggered.connect(self.close)
        self.action_search.triggered.connect(self.search_sentinel_download_scenes)
        self.action_download.triggered.connect(self.download_selected_sentinel_scenes)
        self.action_use_sources.triggered.connect(self.use_download_workspace_as_data_sources)
        self.action_validate.triggered.connect(self.validate_environment)
        self.action_prepare.triggered.connect(self.prepare_data_sources)
        self.action_preview_command.triggered.connect(self._preview_generate_command)
        self.action_generate.triggered.connect(self.generate_workflow)
        self.action_run_next.triggered.connect(self.run_next_step)
        self.action_run_selected.triggered.connect(self.run_selected_step)
        self.action_run_remaining.triggered.connect(self.run_remaining_steps)
        self.action_stop.triggered.connect(self.stop_execution)
        self.action_refresh_outputs.triggered.connect(self.refresh_outputs_view)
        self.action_about.triggered.connect(self._show_about_dialog)

        self.workflow_stepper.currentChanged.connect(self._handle_stepper_changed)
        self.project_start_page.newProjectRequested.connect(self.new_project)
        self.project_start_page.openProjectRequested.connect(self.open_project)
        self.project_start_page.recentProjectRequested.connect(self._open_recent_project)

        self.data_download_page.output_dir_row.browse_button.clicked.connect(self._browse_download_output_dir)
        self.data_download_page.aoi_file_row.browse_button.clicked.connect(self._browse_download_aoi_file)
        self.data_download_page.test_credentials_button.clicked.connect(self.test_asf_download_credentials)
        self.data_download_page.test_tianditu_button.clicked.connect(self.test_tianditu_basemap_key)
        self.data_download_page.test_opentopography_button.clicked.connect(self.test_opentopography_key)
        self.data_download_page.search_button.clicked.connect(self.search_sentinel_download_scenes)
        self.data_download_page.clear_button.clicked.connect(self.clear_sentinel_download_results)
        self.data_download_page.download_selected_button.clicked.connect(self.download_selected_sentinel_scenes)
        self.data_download_page.cancel_download_button.clicked.connect(self.cancel_sentinel_download)
        self.data_download_page.save_selected_button.clicked.connect(self.save_selected_sentinel_scenes)
        self.data_download_page.use_as_sources_button.clicked.connect(self.use_download_workspace_as_data_sources)
        self.data_download_page.open_workspace_button.clicked.connect(self.open_download_workspace)

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

    def _show_about_dialog(self) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("About InSAR-PILOT")
        dialog.setWindowIcon(BrandAssets.icon())
        dialog.setIconPixmap(BrandAssets.pixmap(size=QSize(72, 72)))
        dialog.setText("InSAR-PILOT")
        dialog.setInformativeText(
            "InSAR Processing Interface and Lightweight Orchestration Toolkit\n"
            f"Version {__version__}\n\n"
            "Open Desktop Workbench for Guided SAR/InSAR Processing"
        )
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

    def _connect_runner(self) -> None:
        self.runner.log_emitted.connect(self.append_log)
        self.runner.command_started.connect(self._handle_command_started)
        self.runner.command_finished.connect(self._handle_command_finished)
        self.runner.queue_finished.connect(self._handle_queue_finished)
        self.runner.runner_state_changed.connect(self._handle_runner_state_changed)

    def _apply_page_spacing(self) -> None:
        """Apply consistent page-level breathing room around central content."""
        for page in (
            self.data_download_page,
            self.processing_setup_page,
            self.run_monitor_page,
            self.results_page,
        ):
            layout = page.layout()
            if layout is not None:
                layout.setContentsMargins(10, 8, 10, 8)
                layout.setSpacing(max(layout.spacing(), 8))

    def _handle_stepper_changed(self, row: int) -> None:
        if row < 0:
            return
        if not self._has_project_workspace():
            self.page_stack.setCurrentIndex(self._page_index_by_key["start"])
            self.workflow_stepper.set_current_index(0)
            self.statusBar().showMessage("Create or open a project workspace first.", 4000)
            return
        key = self._step_keys[row] if row < len(self._step_keys) else "data_download"
        self.page_stack.setCurrentIndex(self._page_index_by_key[key])
        self._sync_nav_selection_state()
        self.action_toggle_console.setChecked(self.log_dock.isVisible())

    def _toggle_log_console(self, checked: bool | None = None) -> None:
        self.log_dock.setVisible(not self.log_dock.isVisible())

    def _handle_log_dock_visibility(self, visible: bool) -> None:
        if hasattr(self, "action_toggle_console"):
            self.action_toggle_console.setChecked(visible)

    def _toggle_extract_widgets(self, checked: bool) -> None:
        self.data_sources_page.extract_dir_row.setEnabled(checked)

    def _browse_shell_init(self) -> None:
        self._browse_file_into(self.shell_init_edit, "Select shell init file")

    def _browse_isce_root(self) -> None:
        self._browse_dir_into(self.isce_root_edit, "Select processing runtime root")

    def _browse_input_dir(self) -> None:
        self._browse_dir_into(self.input_path_edit, "Select SLC folder")

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

    def _browse_download_output_dir(self) -> None:
        self._browse_dir_into(self.data_download_page.output_dir_row.line_edit, "Select Sentinel-1 download workspace")

    def _browse_download_aoi_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select AOI KML file",
            self.data_download_page.aoi_file_row.line_edit.text() or str(Path.home()),
            "KML files (*.kml);;All files (*)",
        )
        if path:
            self.data_download_page.aoi_file_row.line_edit.setText(path)

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

    @staticmethod
    def _set_combo_by_data(combo, value: str) -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _has_project_workspace(self) -> bool:
        return self.project.workspace.configured or bool(self.project.workflow.work_dir.strip())

    def _download_storage(self) -> DownloadStorage:
        output_dir = self.data_download_page.output_dir()
        if not output_dir:
            raise ValueError("Choose an output directory for the standalone download workspace first.")
        return DownloadStorage(output_dir)

    def _populate_download_credentials(self) -> None:
        credentials = load_earthdata_credentials()
        if credentials is not None:
            self.data_download_page.set_credential_inputs(
                credentials.username,
                credentials.password,
                source=credentials.source,
            )

    def _populate_tianditu_key(self) -> None:
        self.data_download_page.set_tianditu_basemap_state(
            available=False,
            preferred_basemap="External Imagery",
        )
        key = load_tianditu_key()
        if key is not None:
            self.tianditu_tile_proxy.update_key(key.key)
            self.data_download_page.set_tianditu_key(key.key, source=key.source)
            self.data_download_page.set_tianditu_status(
                f"Loaded Tianditu key from {key.source}. Checking availability in the background."
            )
            self._start_tianditu_key_check(key.key, origin="startup", save_on_success=False)
        else:
            self.tianditu_tile_proxy.update_key("")
            self.data_download_page.set_tianditu_key("")
            self.data_download_page.set_tianditu_status(
                "Tianditu key is optional. External Imagery is active until Tianditu is configured."
            )

    def _populate_opentopography_key(self) -> None:
        self.data_download_page.set_opentopography_available(False)
        key = load_opentopography_key()
        if key is not None:
            self.data_download_page.set_opentopography_key(key.key, source=key.source)
            self.data_download_page.set_opentopography_status(
                f"Loaded OpenTopography key from {key.source}. Checking availability in the background."
            )
            self._start_opentopography_key_check(key.key, origin="startup", save_on_success=False)
        else:
            self.data_download_page.set_opentopography_key("")
            self.data_download_page.set_opentopography_status(
                "OpenTopography key is required for DEM download. Validate your key to enable DEM controls."
            )

    def _start_tianditu_key_check(self, key: str, *, origin: str, save_on_success: bool) -> None:
        if self._tianditu_thread is not None:
            return
        self._tianditu_check_origin = origin
        network = self.data_download_page.network_config()
        if origin == "manual":
            self.data_download_page.set_tianditu_busy(True)
            self.data_download_page.set_tianditu_status("Testing Tianditu basemap key...")
            self.data_download_page.append_log("Testing Tianditu basemap key in the background...")
        self._tianditu_thread = QThread(self)
        self._tianditu_worker = TiandituKeyWorker(key, network=network, save_on_success=save_on_success)
        self._tianditu_worker.moveToThread(self._tianditu_thread)
        self._tianditu_thread.started.connect(self._tianditu_worker.run)
        self._tianditu_worker.finished.connect(self._handle_tianditu_key_test_finished)
        self._tianditu_worker.finished.connect(self._tianditu_thread.quit)
        self._tianditu_thread.finished.connect(self._tianditu_worker.deleteLater)
        self._tianditu_thread.finished.connect(self._tianditu_thread.deleteLater)
        self._tianditu_thread.finished.connect(self._clear_tianditu_worker_refs)
        self._tianditu_thread.start()

    def _start_opentopography_key_check(self, key: str, *, origin: str, save_on_success: bool) -> None:
        if self._opentopography_thread is not None:
            return
        self._opentopography_check_origin = origin
        network = self.data_download_page.network_config()
        if origin == "manual":
            self.data_download_page.set_opentopography_busy(True)
            self.data_download_page.set_opentopography_status("Testing OpenTopography API key...")
            self.data_download_page.append_log("Testing OpenTopography DEM key in the background...")
        self._opentopography_thread = QThread(self)
        self._opentopography_worker = OpenTopographyKeyWorker(key, network=network, save_on_success=save_on_success)
        self._opentopography_worker.moveToThread(self._opentopography_thread)
        self._opentopography_thread.started.connect(self._opentopography_worker.run)
        self._opentopography_worker.finished.connect(self._handle_opentopography_key_test_finished)
        self._opentopography_worker.finished.connect(self._opentopography_thread.quit)
        self._opentopography_thread.finished.connect(self._opentopography_worker.deleteLater)
        self._opentopography_thread.finished.connect(self._opentopography_thread.deleteLater)
        self._opentopography_thread.finished.connect(self._clear_opentopography_worker_refs)
        self._opentopography_thread.start()

    def search_sentinel_download_scenes(self) -> None:
        if self._download_search_thread is not None:
            self._show_error("Search already running", "Wait for the current ASF search to finish first.")
            return
        try:
            criteria = self.data_download_page.criteria()
            self._validate_download_search_criteria(criteria)
        except Exception as exc:
            self._show_error("Search setup failed", str(exc))
            self.data_download_page.append_log(f"Search setup failed: {exc}")
            return

        output_dir = self.data_download_page.output_dir()
        network = self.data_download_page.network_config()
        self._active_search_output_dir = output_dir
        self.data_download_page.set_search_busy(True)
        self.data_download_page.append_log(
            f"Searching ASF for Sentinel-1 SLC scenes from {criteria.start_date} to {criteria.end_date}..."
        )
        if not output_dir:
            self.data_download_page.append_log("No workspace selected; search results will be shown but not saved.")
        self._download_page_status = "Searching"
        self._download_page_message = "ASF search is running in the background."
        self._sync_summary_sidebar()
        self._download_search_thread = QThread(self)
        self._download_search_worker = SearchWorker(
            self.download_search_service,
            criteria,
            output_dir=output_dir,
            network=network,
        )
        self._download_search_worker.moveToThread(self._download_search_thread)
        self._download_search_thread.started.connect(self._download_search_worker.run)
        self._download_search_worker.finished.connect(self._handle_download_search_finished)
        self._download_search_worker.failed.connect(self._handle_download_search_failed)
        self._download_search_worker.finished.connect(self._download_search_thread.quit)
        self._download_search_worker.failed.connect(self._download_search_thread.quit)
        self._download_search_thread.finished.connect(self._download_search_worker.deleteLater)
        self._download_search_thread.finished.connect(self._download_search_thread.deleteLater)
        self._download_search_thread.finished.connect(self._clear_download_search_worker_refs)
        self._download_search_thread.start()

    def _handle_download_search_finished(self, scenes, saved_path: str) -> None:
        scene_list = list(scenes)
        self.data_download_page.set_search_busy(False)
        self.data_download_page.set_scenes(scene_list)
        if saved_path:
            self.data_download_page.append_log(
                f"ASF search completed with {len(scene_list)} scenes. Results saved to {saved_path}."
            )
            message = f"{len(scene_list)} ASF scenes available in {self._active_search_output_dir}."
        else:
            self.data_download_page.append_log(
                f"ASF search completed with {len(scene_list)} scenes. Select a workspace before saving or downloading."
            )
            message = f"{len(scene_list)} ASF scenes available. Workspace not selected."
        self._download_page_status = "Ready"
        self._download_page_message = message
        self._sync_summary_sidebar()

    def _handle_download_search_failed(self, message: str) -> None:
        self.data_download_page.set_search_busy(False)
        detail = self._friendly_network_error(message)
        self.data_download_page.append_log(f"ASF search failed: {detail}")
        self._download_page_status = "Search failed"
        self._download_page_message = detail
        self._sync_summary_sidebar()

    def _clear_download_search_worker_refs(self) -> None:
        self._download_search_thread = None
        self._download_search_worker = None

    @staticmethod
    def _validate_download_search_criteria(criteria) -> None:
        if not criteria.start_date.strip() or not criteria.end_date.strip():
            raise ValueError("Start date and end date are required.")
        if not MainWindow._is_supported_download_date(criteria.start_date):
            raise ValueError("Start date must use YYYY-MM-DD or YYYYMMDD format.")
        if not MainWindow._is_supported_download_date(criteria.end_date):
            raise ValueError("End date must use YYYY-MM-DD or YYYYMMDD format.")
        if criteria.aoi_mode == "kml":
            if not criteria.aoi_file.strip():
                raise ValueError("Choose an AOI KML file before searching.")
            if not Path(criteria.aoi_file).expanduser().is_file():
                raise ValueError(f"AOI file was not found: {criteria.aoi_file}")
        elif criteria.aoi_mode == "wkt":
            if not criteria.wkt.strip():
                raise ValueError("WKT AOI is required when WKT input is selected.")
        elif not criteria.bbox.strip():
            raise ValueError("AOI bbox is required when BBOX input is selected.")

    @staticmethod
    def _is_supported_download_date(value: str) -> bool:
        text = value.strip()
        if re.fullmatch(r"\d{8}", text):
            try:
                datetime.strptime(text, "%Y%m%d")
            except ValueError:
                return False
            return True
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            try:
                datetime.strptime(text, "%Y-%m-%d")
            except ValueError:
                return False
            return True
        return False

    @staticmethod
    def _friendly_network_error(message: str) -> str:
        """Add context for common ASF/CMR connectivity failures."""

        lower = message.lower()
        if "proxyerror" in lower or "proxy" in lower:
            return (
                f"{message} Current proxy settings appear to be unreachable. "
                "Check HTTP_PROXY/HTTPS_PROXY/ALL_PROXY in the WSL environment, or unset them before launching."
            )
        if "cmr.earthdata.nasa.gov" in lower:
            return (
                f"{message} ASF search uses NASA CMR (cmr.earthdata.nasa.gov); "
                "being able to open search.asf.alaska.edu in a browser does not guarantee this API endpoint is reachable."
            )
        if "timeout" in lower or "timed out" in lower:
            return f"{message} The request timed out; the GUI remains usable while the background worker finishes."
        return message

    def test_asf_download_credentials(self) -> None:
        if self._credential_thread is not None:
            self._show_error("Connection test already running", "Wait for the current ASF connection test to finish first.")
            return
        username, password = self.data_download_page.credential_inputs()
        network = self.data_download_page.network_config()
        self.data_download_page.set_credential_status("Testing ASF Earthdata connection...")
        self._download_credentials_ok = False
        self.data_download_page.test_credentials_button.setEnabled(False)
        self.data_download_page.append_log("Testing ASF Earthdata connection in the background...")
        self._credential_thread = QThread(self)
        self._credential_worker = CredentialWorker(
            username,
            password,
            save_netrc=self.data_download_page.should_save_netrc(),
            network=network,
        )
        self._credential_worker.moveToThread(self._credential_thread)
        self._credential_thread.started.connect(self._credential_worker.run)
        self._credential_worker.finished.connect(self._handle_credential_test_finished)
        self._credential_worker.finished.connect(self._credential_thread.quit)
        self._credential_thread.finished.connect(self._credential_worker.deleteLater)
        self._credential_thread.finished.connect(self._credential_thread.deleteLater)
        self._credential_thread.finished.connect(self._clear_credential_worker_refs)
        self._credential_thread.start()

    def _handle_credential_test_finished(self, result, saved_path: str, endpoint_checks) -> None:
        self.data_download_page.test_credentials_button.setEnabled(True)
        self.data_download_page.set_credential_status(result.message)
        self._download_credentials_ok = bool(result.ok)
        for check in endpoint_checks:
            status = "OK" if check.ok else "FAILED"
            self.data_download_page.append_log(f"{check.name}: {status} ({check.message})")
        if saved_path:
            self.data_download_page.append_log(
                f"Saved Earthdata credentials to {saved_path}." if not saved_path.startswith("Saving ") else saved_path
            )
            if not saved_path.startswith("Saving "):
                self._populate_download_credentials()
        self.data_download_page.append_log(result.message)
        self._download_page_status = "Credentials OK" if result.ok else "Credential failed"
        self._download_page_message = result.message
        self._sync_summary_sidebar()

    def _clear_credential_worker_refs(self) -> None:
        self._credential_thread = None
        self._credential_worker = None

    def test_tianditu_basemap_key(self) -> None:
        if self._tianditu_thread is not None:
            self._show_error("Tianditu key test already running", "Wait for the current basemap key test to finish first.")
            return
        key = self.data_download_page.tianditu_key()
        self._start_tianditu_key_check(key, origin="manual", save_on_success=True)

    def test_opentopography_key(self) -> None:
        if self._opentopography_thread is not None:
            self._show_error(
                "OpenTopography key test already running",
                "Wait for the current DEM key test to finish first.",
            )
            return
        key = self.data_download_page.opentopography_key()
        self._start_opentopography_key_check(key, origin="manual", save_on_success=True)

    def _handle_tianditu_key_test_finished(self, result, saved_path: str) -> None:
        origin = self._tianditu_check_origin
        if origin == "manual":
            self.data_download_page.set_tianditu_busy(False)

        if result.ok:
            key = self.data_download_page.tianditu_key()
            self.tianditu_tile_proxy.update_key(key)
            self.data_download_page.set_tianditu_basemap_state(
                available=True,
                preferred_basemap="Tianditu Imagery",
            )
            self.data_download_page.set_tianditu_status(result.message)
        else:
            self.data_download_page.set_tianditu_basemap_state(
                available=False,
                preferred_basemap="External Imagery",
            )
            if origin == "startup":
                self.data_download_page.set_tianditu_status(
                    "Saved Tianditu key could not be validated. External Imagery is active."
                )
            else:
                self.data_download_page.set_tianditu_status(result.message)

        if origin == "manual":
            if saved_path:
                self.data_download_page.append_log(
                    f"Saved Tianditu key to {saved_path}." if not saved_path.startswith("Saving ") else saved_path
                )
            self.data_download_page.append_log(result.message)

    def _clear_tianditu_worker_refs(self) -> None:
        self._tianditu_thread = None
        self._tianditu_worker = None
        self._tianditu_check_origin = "idle"

    def _handle_opentopography_key_test_finished(self, result, saved_path: str) -> None:
        origin = self._opentopography_check_origin
        if origin == "manual":
            self.data_download_page.set_opentopography_busy(False)

        self.data_download_page.set_opentopography_available(result.ok)
        self.data_download_page.set_opentopography_status(result.message)
        if origin == "manual":
            if saved_path:
                self.data_download_page.append_log(
                    f"Saved OpenTopography key to {saved_path}."
                    if not saved_path.startswith("Saving ")
                    else saved_path
                )
            self.data_download_page.append_log(result.message)

    def _clear_opentopography_worker_refs(self) -> None:
        self._opentopography_thread = None
        self._opentopography_worker = None
        self._opentopography_check_origin = "idle"

    def clear_sentinel_download_results(self) -> None:
        self.data_download_page.clear_results()
        self.data_download_page.append_log("Search results cleared.")
        self._download_page_status = "Ready"
        self._download_page_message = "Define AOI, dates, and Sentinel-1 SLC filters."
        self._sync_summary_sidebar()

    def save_selected_sentinel_scenes(self) -> None:
        try:
            storage = self._download_storage()
        except Exception as exc:
            self._show_error("Save selected scenes failed", str(exc))
            return

        selected = self.data_download_page.selected_scenes()
        if not selected:
            self._show_error("No scenes selected", "Select at least one scene in the search results table.")
            return

        path = storage.save_selected_scenes(selected)
        self.data_download_page.append_log(f"Saved {len(selected)} selected scenes to {path}.")
        self._download_page_status = "Selected"
        self._download_page_message = f"{len(selected)} selected scenes saved."
        self._sync_summary_sidebar()

    def download_selected_sentinel_scenes(self) -> None:
        if self._download_thread is not None:
            self._show_error("Download already running", "Wait for the current download to finish or cancel it first.")
            return
        capability = self.preflight_service.check_aria2_capability()
        self.data_download_page.set_aria2_capability(capability.aria2c_available, capability.aria2c_path)
        if not capability.aria2c_available:
            self._show_error(
                "aria2c missing",
                "SLC downloads require aria2c for multipart resumable transfers. Activate the insar conda environment or install aria2c, then try again.",
            )
            return
        if not self._download_credentials_ok:
            self._show_error(
                "ASF credentials not verified",
                "Test ASF Earthdata credentials successfully before starting downloads.",
            )
            return
        try:
            storage = self._download_storage()
        except Exception as exc:
            self._show_error("Download setup failed", str(exc))
            return

        selected = self.data_download_page.selected_scenes()
        if not selected:
            self._show_error("No scenes selected", "Select at least one scene before downloading.")
            return
        criteria = self.data_download_page.criteria()
        include_dem = self.data_download_page.should_download_dem()
        dem_source = self.data_download_page.dem_source()
        dem_api_key = self.data_download_page.opentopography_key()
        if include_dem and not dem_api_key.strip():
            self._show_error("DEM key missing", "Validate an OpenTopography key before enabling DEM download.")
            return

        storage.save_selected_scenes(selected)
        tasks = self.download_service.create_tasks(
            selected,
            storage.output_dir,
            include_orbits=self.data_download_page.include_orbits(),
        )
        if include_dem:
            tasks.append(create_dem_task(storage.output_dir, dem_source))
        storage.save_download_tasks(tasks)
        username, password = self.data_download_page.credential_inputs()
        network = self.data_download_page.network_config()
        self._download_tasks = tasks
        self._download_task_status = {task.task_id: task.status for task in tasks}
        self._download_task_message = {task.task_id: task.message for task in tasks}
        self._download_thread = QThread(self)
        self._download_worker = DownloadWorker(
            self.download_service,
            storage,
            tasks,
            username=username,
            password=password,
            criteria=criteria,
            download_dem=include_dem,
            dem_source=dem_source,
            dem_api_key=dem_api_key,
            network=network,
        )
        self._download_worker.moveToThread(self._download_thread)
        self._download_thread.started.connect(self._download_worker.run)
        self._download_worker.task_updated.connect(self._handle_download_task_updated)
        self._download_worker.dem_plan_ready.connect(self._handle_dem_plan_ready)
        self._download_worker.log.connect(self.data_download_page.append_log)
        self._download_worker.finished.connect(self._handle_download_finished)
        self._download_worker.failed.connect(self._handle_download_failed)
        self._download_worker.finished.connect(self._download_thread.quit)
        self._download_worker.failed.connect(self._download_thread.quit)
        self._download_thread.finished.connect(self._download_worker.deleteLater)
        self._download_thread.finished.connect(self._download_thread.deleteLater)
        self._download_thread.finished.connect(self._clear_download_worker_refs)
        self.data_download_page.set_download_busy(True)
        self.data_download_page.set_download_tasks(tasks)
        self.data_download_page.append_log(f"Started {len(tasks)} download tasks in {storage.output_dir}.")
        self._download_page_status = "Downloading"
        self._download_page_message = f"{len(tasks)} download tasks running."
        self._sync_summary_sidebar()
        self._download_thread.start()

    def cancel_sentinel_download(self) -> None:
        if self._download_worker is not None:
            self._download_worker.cancel()

    def _handle_download_task_updated(self, task: DownloadTask) -> None:
        previous_status = self._download_task_status.get(task.task_id, "")
        previous_message = self._download_task_message.get(task.task_id, "")
        self._download_task_status[task.task_id] = task.status
        self._download_task_message[task.task_id] = task.message
        completed = self._download_completed_task_count()
        total = len(self._download_tasks)
        self.data_download_page.apply_task_update(task, completed, total)
        terminal = {"completed", "skipped", "failed", "cancelled"}
        should_log = task.status in terminal or (
            task.status == "running" and (previous_status != "running" or task.message != previous_message)
        )
        if should_log and task.message:
            suffix = f" -> {task.local_path}" if task.product_type.upper() == "ORBIT" and task.local_path else ""
            self.data_download_page.append_log(f"{task.task_id} [{task.product_type}]: {task.message}{suffix}")

    def _handle_download_finished(self, results) -> None:
        result_list = list(results)
        self.data_download_page.apply_download_results(result_list)
        completed = sum(result.status == "completed" for result in result_list)
        skipped = sum(result.status == "skipped" for result in result_list)
        failed = sum(result.status == "failed" for result in result_list)
        cancelled = sum(result.status == "cancelled" for result in result_list)
        self.data_download_page.append_log(
            f"Download finished: {completed} completed, {skipped} skipped, {failed} failed, {cancelled} cancelled."
        )
        self.data_download_page.set_download_busy(False)
        self._download_page_status = "Downloaded" if failed == 0 and cancelled == 0 else "Download issues"
        self._download_page_message = (
            f"{completed} completed, {skipped} skipped, {failed} failed, {cancelled} cancelled."
        )
        self._sync_summary_sidebar()

    def _handle_dem_plan_ready(self, plan) -> None:
        self.data_download_page.set_dem_plan(plan)
        if plan.planned_bbox_snwe is not None:
            bbox_text = " ".join(f"{value:g}" for value in plan.planned_bbox_snwe)
            self.data_download_page.append_log(f"Planned DEM bbox ({plan.planning_mode}): {bbox_text}")

    def _handle_download_failed(self, message: str) -> None:
        self.data_download_page.append_log(f"Download worker failed: {message}")
        self.data_download_page.set_download_busy(False)
        self._download_page_status = "Download failed"
        self._download_page_message = message
        self._sync_summary_sidebar()

    def _clear_download_worker_refs(self) -> None:
        self._download_thread = None
        self._download_worker = None

    def _download_completed_task_count(self) -> int:
        terminal = {"completed", "skipped", "failed", "cancelled"}
        return sum(status in terminal for status in self._download_task_status.values())

    def use_download_workspace_as_data_sources(self) -> None:
        try:
            storage = self._download_storage()
        except Exception as exc:
            self._show_error("Download workspace missing", str(exc))
            return
        slc_dir = storage.output_dir / "SLC"
        orbit_dir = storage.output_dir / "Orbit"
        dem_plan = storage.load_dem_plan()
        if not slc_dir.is_dir():
            self._show_error("SLC folder missing", f"No SLC folder exists yet: {slc_dir}")
            return
        self.input_path_edit.setText(str(slc_dir))
        if orbit_dir.is_dir():
            self.orbit_path_edit.setText(str(orbit_dir))
        if dem_plan is not None and dem_plan.dem_path:
            self.dem_path_edit.setText(dem_plan.dem_path)
            index = self.dem_reference_combo.findData(dem_plan.dem_height_reference)
            self.dem_reference_combo.setCurrentIndex(index if index >= 0 else 0)
        self._update_project_from_form()
        if dem_plan is not None and dem_plan.dem_path:
            self.data_download_page.append_log(
                "Filled Data Sources with the download workspace SLC/Orbit folders and DEM."
            )
        else:
            self.data_download_page.append_log("Filled Data Sources with the download workspace SLC/Orbit folders.")
        self._download_page_status = "Ready for Data Sources"
        self._download_page_message = (
            "SLC/Orbit/DEM paths were filled into Data Sources. Run Validate & Prepare Data next."
            if dem_plan is not None and dem_plan.dem_path
            else "SLC/Orbit paths were filled into Data Sources. Run Validate & Prepare Data next."
        )
        self._sync_summary_sidebar()

    def open_download_workspace(self) -> None:
        try:
            storage = self._download_storage()
        except Exception as exc:
            self._show_error("Download workspace missing", str(exc))
            return
        storage.output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(storage.output_dir)))

    def _populate_form_from_project(self) -> None:
        self._download_page_status = self.project.download.last_status.replace("_", " ").title() if self.project.download.last_status else "Ready"
        self._download_page_message = self.project.download.last_message or "Define AOI, dates, and Sentinel-1 SLC filters."
        self.shell_init_edit.setText(self.project.environment.shell_init_path)
        self.conda_env_edit.setText(self.project.environment.conda_env_name)
        self.isce_root_edit.setText(self.project.environment.isce_root)
        self._populate_runtime_diagnostics()

        self.data_download_page.output_dir_row.line_edit.setText(self.project.download.output_dir)
        self.data_download_page.start_date_edit.setText(self.project.download.start_date)
        self.data_download_page.end_date_edit.setText(self.project.download.end_date)
        self.data_download_page.bbox_edit.setText(self.project.download.bbox)
        self.data_download_page.wkt_edit.setText(self.project.download.wkt)
        self.data_download_page.aoi_file_row.line_edit.setText(self.project.download.aoi_file)
        self._set_combo_by_data(self.data_download_page.aoi_mode_combo, self.project.download.aoi_mode)
        self._set_combo_by_data(self.data_download_page.platform_combo, self.project.download.platform)
        self._set_combo_by_data(self.data_download_page.orbit_direction_combo, self.project.download.orbit_direction)
        self._set_combo_by_data(self.data_download_page.polarization_combo, self.project.download.polarization)
        self.data_download_page.relative_orbit_edit.setText(self.project.download.relative_orbit)
        self.data_download_page.include_orbits_checkbox.setChecked(self.project.download.include_orbits)
        self.data_download_page.download_dem_checkbox.setChecked(self.project.download.download_dem)
        self._set_combo_by_data(self.data_download_page.dem_source_combo, self.project.download.dem_source)
        self.data_download_page.set_preferred_selected_scene_ids(self.project.download.selected_scene_ids)
        self.data_download_page._handle_aoi_mode_changed()

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
        configured_export = self.project.visualization.export_dir.strip()
        if configured_export and not self._is_legacy_visual_export_dir(configured_export):
            self.visual_export_dir_edit.setText(configured_export)
        else:
            default_export = self._preferred_visual_export_dir()
            self.visual_export_dir_edit.setText(str(default_export) if default_export is not None else "")
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
        self._refresh_preflight_report()
        self._render_preparation_summary()
        self._refresh_runfile_estimates()
        self._update_action_states()
        self._sync_summary_sidebar()

    def _populate_runtime_diagnostics(self) -> None:
        conda_env = os.environ.get("CONDA_DEFAULT_ENV", "") or self.project.environment.conda_env_name or "-"
        conda_prefix = os.environ.get("CONDA_PREFIX", "") or self.project.environment.isce_root or "-"
        path_head = os.environ.get("PATH", "").split(os.pathsep)[:8]
        lines = [
            "Runtime is inherited from the process that launched this application.",
            f"Python: {sys.executable}",
            f"Conda env: {conda_env}",
            f"Conda prefix: {conda_prefix}",
            "",
            "PATH head:",
            *[f"- {item}" for item in path_head if item],
        ]
        if hasattr(self.processing_setup_page, "runtime_diagnostics_text"):
            self.processing_setup_page.runtime_diagnostics_text.setPlainText("\n".join(lines))

    def _update_project_from_form(self) -> None:
        previous_signature = self.project.state.prepared_signature
        self.project.environment = EnvironmentConfig(
            shell_init_path=self.shell_init_edit.text().strip(),
            conda_env_name=self.conda_env_edit.text().strip(),
            isce_root=self.isce_root_edit.text().strip(),
        )
        self.project.download = self.project.download.__class__(
            last_status=self._download_page_status.lower(),
            last_message=self._download_page_message,
            output_dir=self.data_download_page.output_dir(),
            aoi_mode=str(self.data_download_page.aoi_mode_combo.currentData() or "bbox"),
            bbox=self.data_download_page.bbox_edit.text().strip(),
            wkt=self.data_download_page.wkt_edit.text().strip(),
            aoi_file=self.data_download_page.aoi_file_row.line_edit.text().strip(),
            platform=str(self.data_download_page.platform_combo.currentData() or "SENTINEL-1"),
            start_date=self.data_download_page.start_date_edit.text().strip(),
            end_date=self.data_download_page.end_date_edit.text().strip(),
            orbit_direction=str(self.data_download_page.orbit_direction_combo.currentData() or "ANY"),
            relative_orbit=self.data_download_page.relative_orbit_edit.text().strip(),
            polarization=str(self.data_download_page.polarization_combo.currentData() or "ANY"),
            include_orbits=self.data_download_page.include_orbits(),
            download_dem=self.data_download_page.should_download_dem(),
            dem_source=self.data_download_page.dem_source(),
            selected_scene_ids=[scene.scene_id for scene in self.data_download_page.selected_scenes()],
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

    def _try_save_project(self) -> None:
        try:
            self.project_store.save(self.project)
        except ValueError:
            # Data Download can run before processing data sources/work_dir are configured.
            return

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
        project_ready = self._has_project_workspace()
        has_selected_step = bool(self._selected_steps())
        self.action_search.setEnabled(project_ready and not busy)
        self.action_download.setEnabled(project_ready and not busy)
        self.action_use_sources.setEnabled(project_ready and not busy)
        self.action_validate.setEnabled(project_ready and not busy)
        self.action_prepare.setEnabled(project_ready and not busy)
        self.action_preview_command.setEnabled(project_ready and not busy)
        self.action_generate.setEnabled(project_ready and not busy)
        self.action_run_next.setEnabled(project_ready and not busy)
        self.action_run_selected.setEnabled(project_ready and not busy and has_selected_step)
        self.action_run_remaining.setEnabled(project_ready and not busy)
        self.action_refresh_outputs.setEnabled(project_ready and not busy)

        self.data_download_page.setEnabled(project_ready)
        self.processing_setup_page.setEnabled(project_ready)
        self.run_monitor_page.setEnabled(project_ready)
        self.results_page.setEnabled(project_ready)

        self.generate_button.setEnabled(project_ready and (not busy) and self._is_prepared_for_current_sources())
        self.run_next_button.setEnabled(project_ready and not busy)
        self.run_selected_button.setEnabled(project_ready and (not busy) and has_selected_step)
        self.run_all_button.setEnabled(project_ready and not busy)
        self.validate_button.setEnabled(project_ready and not busy)
        self.inspect_inputs_button.setEnabled(project_ready and not busy)
        self.prepare_data_button.setEnabled(project_ready and not busy)
        self.aoi_source_edit.setEnabled(project_ready and not busy)
        self.aoi_source_browse_button.setEnabled(project_ready and not busy)
        if self.aoi_import_button is not None:
            self.aoi_import_button.setEnabled(project_ready and not busy)
        self.use_common_overlap_check.setEnabled(project_ready and not busy)
        self.iw1_check.setEnabled(project_ready and not busy)
        self.iw2_check.setEnabled(project_ready and not busy)
        self.iw3_check.setEnabled(project_ready and not busy)
        self.recommend_iw_button.setEnabled(project_ready and not busy)
        self.verify_geometry_button.setEnabled(project_ready and not busy)
        self.export_verify_button.setEnabled(project_ready and not busy)
        self.confirm_aoi_iw_button.setEnabled(project_ready and not busy)
        bbox_edit_enabled = project_ready and (not busy) and (not self.use_common_overlap_check.isChecked())
        self.bbox_south_edit.setEnabled(bbox_edit_enabled)
        self.bbox_north_edit.setEnabled(bbox_edit_enabled)
        self.bbox_west_edit.setEnabled(bbox_edit_enabled)
        self.bbox_east_edit.setEnabled(bbox_edit_enabled)
        self.stop_button.setEnabled(busy)
        self.visual_preview_button.setEnabled(project_ready and not busy)
        self.visual_export_button.setEnabled(project_ready and not busy)
        self.visual_primary_browse_button.setEnabled(project_ready and not busy)
        self.visual_secondary_browse_button.setEnabled(project_ready and not busy)
        if self.visual_primary_from_outputs_button is not None:
            self.visual_primary_from_outputs_button.setEnabled(project_ready and not busy)
        if self.visual_secondary_from_outputs_button is not None:
            self.visual_secondary_from_outputs_button.setEnabled(project_ready and not busy)
        self.visual_export_dir_browse_button.setEnabled(project_ready and not busy)

    def refresh_status_labels(self) -> None:
        status_text = self.project.state.status.value
        current_step = self.project.state.current_step or "-"
        try:
            work_dir = str(self.project.resolved_work_dir())
        except ValueError:
            work_dir = "-"

        if self.project.workspace.configured:
            project_name = self.project.workspace.root_path().name
        else:
            project_name = "select project"
        self.header_project_label.setText(f"Project: {project_name}")
        self.header_current_step_label.setText(f"Current step: {current_step}")
        self.header_status_badge.set_status(status_text, self._tone_for_status(status_text))
        self.run_monitor_page.status_card.set_value(status_text)
        self.run_monitor_page.status_card.set_badge(status_text, self._tone_for_status(status_text))
        self.run_monitor_page.current_step_card.set_value(current_step)
        self.run_monitor_page.work_dir_card.set_value(Path(work_dir).name if work_dir != "-" else "-")
        self.run_monitor_page.work_dir_card.set_body("Full path is available in diagnostics and logs.")
        if hasattr(self.run_monitor_page, "project_status_label"):
            self.run_monitor_page.project_status_label.setText(f"Status: {status_text}")
            self.run_monitor_page.current_step_label.setText(f"Step: {current_step}")
            self.run_monitor_page.work_dir_label.setText(
                f"Work dir: {Path(work_dir).name if work_dir != '-' else '-'}"
            )

        env_text, env_tone = self._environment_health_badge()
        self.header_env_badge.set_status(env_text, env_tone)

    def append_log(self, text: str) -> None:
        append_text_preserving_scroll(self.log_view, text)

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
        if not self._has_project_workspace():
            self.new_project()
            if not self._has_project_workspace():
                return
        self._update_project_from_form()
        try:
            path = self.project_store.save(self.project)
        except Exception as exc:
            self._show_error("Save failed", str(exc))
            return
        self._remember_current_project(path)
        self.statusBar().showMessage(f"Project saved: {path}", 5000)

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open project",
            str(Path.home()),
            "InSAR-PILOT Project (*.pilot);;Legacy Project (*.insarpilot *.json);;All files (*)",
        )
        if not path:
            return
        self._load_project_from_path(path)

    def _open_recent_project(self, path: str) -> None:
        self._load_project_from_path(path)

    def _load_project_from_path(self, path: str | Path) -> None:
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

        self._remember_current_project(path)
        self._finish_project_workspace_change()
        self.statusBar().showMessage(f"Loaded project: {path}", 5000)

    def _finish_project_workspace_change(self) -> None:
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
        self._set_current_page("data_download")
        self.refresh_steps_view()
        self.refresh_outputs_view()
        self.refresh_status_labels()
        self._sync_summary_sidebar()
        self._refresh_navigation_status()
        self._refresh_start_page()

    def new_project(self) -> None:
        root = QFileDialog.getExistingDirectory(self, "Select project folder", str(Path.home()))
        if not root:
            self._set_current_page("start")
            return
        self.project = self.project_store.create_workspace(root)
        detected = create_default_project().environment
        self.project.environment = detected
        self.project_store.save(self.project)
        self.runner.set_environment(self.project.environment)
        self._remember_current_project(root)
        self._finish_project_workspace_change()
        self.statusBar().showMessage(f"Project created: {self.project.project_file()}", 5000)

    def _refresh_start_page(self) -> None:
        if hasattr(self.app_settings, "recent_projects"):
            self.project_start_page.set_recent_projects(self.app_settings.recent_projects())

    def _remember_current_project(self, source_path: str | Path | None = None) -> None:
        if not hasattr(self.app_settings, "add_recent_project"):
            return
        try:
            if self.project.workspace.configured:
                root = self.project.workspace.root_path()
                self.app_settings.add_recent_project(root.name, root)
            elif source_path is not None:
                path = Path(source_path).expanduser()
                name = path.parent.name if path.is_file() else path.name
                self.app_settings.add_recent_project(name, path)
            if hasattr(self.app_settings, "sync"):
                self.app_settings.sync()
        except Exception:
            return
        self._refresh_start_page()

    def generate_workflow(self) -> None:
        self._update_project_from_form()
        errors = self._validate_generation_inputs()
        report = self._refresh_preflight_report()
        errors.extend(
            f"Preflight: {check.label}: {check.detail}"
            for check in report.blockers
            if f"Preflight: {check.label}: {check.detail}" not in errors
        )
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
            if hasattr(self.command_preview_text, "set_metadata"):
                self.command_preview_text.set_metadata(
                    f"Work directory: {self.project.resolved_work_dir()} | Log: {self.project.logs_dir() / 'stack_generate.log'}"
                )
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
            label="Generate processing workflow",
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
        preview_dir = work_dir / APP_METADATA_DIR / "visualize" / "cache" / "latest"
        filename = f"{mode}_preview.bmp"
        return str(preview_dir / filename)

    def _resolve_visualization_export_output_path(self) -> str | None:
        self._update_project_from_form()
        export_dir_text = self.project.visualization.export_dir.strip()
        if export_dir_text:
            default_dir = Path(export_dir_text).expanduser()
        else:
            default_dir = self._preferred_visual_export_dir()
            if default_dir is None:
                self._show_error(
                    "Export setup failed",
                    "Set data source/work directory first so export can default inside the project work folder.",
                )
                return None

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

    @staticmethod
    def _is_legacy_visual_export_dir(path_text: str) -> bool:
        path = Path(path_text).expanduser()
        return path.name == "iscegui_visualize_exports"

    def _preferred_visual_export_dir(self) -> Path | None:
        try:
            return self.project.metadata_dir() / "visualize" / "exports"
        except ValueError:
            return None

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
        if state == "running" and not self.log_dock.isVisible():
            self.log_dock.show()
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
        workflow = self.project.workflow

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

    def _refresh_preflight_report(self) -> PreflightReport:
        try:
            report = self.preflight_service.run(self.project, self.project.state.prepared_inputs)
        except Exception as exc:
            report = PreflightReport()
            self.preflight_text.setPlainText(f"Preflight unavailable:\n{exc}")
            return report

        if hasattr(self.processing_page, "preflight_check_list"):
            self.processing_page.preflight_check_list.set_report(report)
        if hasattr(self.processing_page, "preflight_alert"):
            if report.blockers:
                self.processing_page.preflight_alert.set_message(
                    f"Preflight found {len(report.blockers)} blocker(s). Resolve them before generation.",
                    "blocker",
                )
            elif report.warnings:
                self.processing_page.preflight_alert.set_message(
                    f"Preflight completed with {len(report.warnings)} warning(s).",
                    "warning",
                )
            else:
                self.processing_page.preflight_alert.set_message("Preflight complete. No blockers found.", "info")

        header = (
            f"Preflight found {len(report.blockers)} blocker(s). Resolve them before generation."
            if report.blockers
            else "Preflight complete. No blockers found."
        )
        if report.warnings:
            header += f"\nWarnings: {len(report.warnings)}"
        if not hasattr(self.processing_page, "preflight_check_list"):
            self.preflight_text.setPlainText(f"{header}\n\n{report.as_text()}")
        return report

    def _refresh_download_capability(self) -> None:
        capability = self.preflight_service.check_aria2_capability()
        self.data_download_page.set_aria2_capability(
            capability.aria2c_available,
            capability.aria2c_path,
        )

    def _restore_layout_settings(self) -> None:
        self.app_settings.restore_splitter("download_main", self.data_download_page.main_splitter)
        self.data_download_page.normalize_main_splitter_sizes()
        self.app_settings.restore_splitter("download_map_results", self.data_download_page.map_results_splitter)
        self.app_settings.restore_dock_visibility("project_inspector", self.project_inspector_dock, default_visible=False)
        self.app_settings.restore_dock_visibility("log_console", self.log_dock, default_visible=False)

    def _save_layout_settings(self) -> None:
        self.app_settings.save_splitter("download_main", self.data_download_page.main_splitter)
        self.app_settings.save_splitter("download_map_results", self.data_download_page.map_results_splitter)
        self.app_settings.save_dock_visibility("project_inspector", self.project_inspector_dock)
        self.app_settings.save_dock_visibility("log_console", self.log_dock)
        self.app_settings.sync()

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
        self.aoi_iw_page.source_card.set_body("Imported AOI data was used to fill the processing bbox.")
        notes = list(result.notes)
        if result.warnings:
            notes.extend(["", "Warnings:"])
            notes.extend(f"- {line}" for line in result.warnings)
        self.verify_notes.setPlainText("\n".join(notes))
        self.aoi_iw_page.verify_alert_label.clear()
        self.aoi_iw_page.verify_alert_label.hide()
        self._update_project_from_form()
        self.recommend_iw()
        self.statusBar().showMessage("AOI imported and processing bbox updated.", 5000)

    def _first_entry_for_iw_recommendation(self) -> str:
        prepared = self.project.state.prepared_inputs.entries
        if prepared:
            return prepared[0].path

        input_dir = Path(self.project.workflow.input_path).expanduser()
        if not input_dir.is_dir():
            raise ValueError("Prepare data first or set a valid SLC folder.")
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
            self._show_error("IW recommendation unavailable", "Disable 'Use common overlap' and provide the processing bbox first.")
            return
        if not self.project.workflow.bbox_snwe.strip():
            self._show_error("IW recommendation unavailable", "Processing bbox is required for IW recommendation.")
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
                "Provide the processing bbox first (disable 'Use common overlap').",
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
        notes.append(f"Processing bbox (SNWE): {bbox_text}")
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
        default_path = work_dir / APP_METADATA_DIR / "verify" / f"aoi_iw_verify_{stamp}.png"
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
        self._refresh_preflight_report()
        if not self._is_prepared_for_current_sources():
            self.command_preview_text.setPlainText(
                "Prepare data first. The generated processing command will appear here."
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
        if hasattr(self.command_preview_text, "set_metadata"):
            self.command_preview_text.set_metadata(
                f"Work directory: {self.project.resolved_work_dir()} | Log: {self.project.logs_dir() / 'stack_generate.log'}"
            )
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
        self.summary_download_card.set_value(self._download_page_status)
        self.summary_download_card.set_body(self._download_page_message)
        self.data_download_page.status_card.set_value(self._download_page_status)
        self.data_download_page.status_card.set_body(self._download_page_message)

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
            Path(self.project.workflow.orbit_path).name if self.project.workflow.orbit_path else "Point to local EOF orbit files."
        )
        self.data_sources_page.dem_card.set_body(
            Path(self.project.state.prepared_dem_path or self.project.workflow.dem_path).name
            if (self.project.state.prepared_dem_path or self.project.workflow.dem_path)
            else "GeoTIFF or prepared DEM path."
        )

        try:
            bbox = self.project.workflow.normalized_bbox() if self.project.workflow.bbox_snwe else ""
        except ValueError:
            bbox = ""
        if self.project.workflow.use_common_overlap:
            self.summary_aoi_card.set_value("Common overlap")
            self.summary_aoi_card.set_body("Empty bbox is allowed by compatibility switch.")
            self.aoi_iw_page.bbox_card.set_value("Common overlap")
            self.aoi_iw_page.bbox_card.set_body("Processing bbox will be omitted.")
        else:
            self.summary_aoi_card.set_value(bbox or "Not set")
            self.summary_aoi_card.set_body("Processing bbox in SNWE decimal degrees.")
            self.aoi_iw_page.bbox_card.set_value(bbox or "Not set")
            self.aoi_iw_page.bbox_card.set_body("Final geographic processing boundary.")
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
        project_ready = self._has_project_workspace()
        self._set_nav_status(
            "data_download",
            self._download_page_status,
            "neutral",
        )
        self._set_nav_status(
            "setup",
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
        has_steps = bool(self.project.state.steps)
        self._set_nav_status("monitor", "Ready" if has_steps else "Pending", "ready" if has_steps else "neutral")
        has_results = self.outputs_tree.topLevelItemCount() > 0
        self._set_nav_status("results", "Ready" if has_results else "Pending", "ready" if has_results else "neutral")
        for index, _key in enumerate(self._step_keys):
            self.workflow_stepper.set_step_enabled(index, project_ready)
        self._sync_nav_selection_state()

    def _set_nav_status(self, key: str, text: str, tone: str) -> None:
        self._step_status[key] = (text, tone)
        if key in self._step_keys:
            self.workflow_stepper.set_step_state(self._step_keys.index(key), tone)

    def _sync_nav_selection_state(self) -> None:
        current_index = self.page_stack.currentIndex()
        for row, key in enumerate(self._step_keys):
            if self._page_index_by_key.get(key) == current_index:
                self.workflow_stepper.set_current_index(row)
                return

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
        if not self._has_project_workspace() and key != "start":
            self.page_stack.setCurrentIndex(self._page_index_by_key["start"])
            return
        self.page_stack.setCurrentIndex(self._page_index_by_key[key])
        self._sync_nav_selection_state()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Stop background work quickly before allowing Qt-owned threads to be destroyed."""

        self._save_layout_settings()
        active_threads = self._active_background_threads()
        if not active_threads:
            self.tianditu_tile_proxy.stop()
            event.accept()
            return

        if self._download_thread is not None and self._download_thread.isRunning() and self._download_worker is not None:
            self._download_worker.cancel()
        self._shutdown_background_threads_now(active_threads)
        self.tianditu_tile_proxy.stop()
        event.accept()

    def _active_background_threads(self) -> list[tuple[str, QThread]]:
        candidates = [
            ("download", self._download_thread),
            ("search", self._download_search_thread),
            ("Earthdata test", self._credential_thread),
            ("Tianditu key test", self._tianditu_thread),
            ("OpenTopography key test", self._opentopography_thread),
        ]
        return [(name, thread) for name, thread in candidates if thread is not None and thread.isRunning()]

    @staticmethod
    def _shutdown_background_threads_now(active_threads: list[tuple[str, QThread]]) -> None:
        """Request thread shutdown briefly, then leave Qt through a process-level exit."""

        for _name, thread in active_threads:
            thread.requestInterruption()
            thread.quit()
        for _name, thread in active_threads:
            if not thread.wait(300):
                os._exit(0)
