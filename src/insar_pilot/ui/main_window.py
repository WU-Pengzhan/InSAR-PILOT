"""Main application window with practitioner-oriented workflow shell."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread
from PySide6.QtGui import QAction, QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from insar_pilot import __version__
from insar_pilot.app.settings import AppSettings
from insar_pilot.bootstrap import create_default_project
from insar_pilot.domain.project import (
    EnvironmentConfig,
    ProjectDocument,
    ProjectStatus,
    StepStatus,
    WorkflowConfig,
)
from insar_pilot.download import (
    DownloadService,
    SearchService,
)
from insar_pilot.download.tile_proxy import TiandituTileProxy
from insar_pilot.i18n import Translator
from insar_pilot.services.aoi_import import AoiImportResult, AoiImportService
from insar_pilot.services.dem_coverage import DemCoverageService
from insar_pilot.services.dem_preparer import DemPreparationService
from insar_pilot.services.env_probe import EnvironmentProbe
from insar_pilot.services.input_catalog import InputCatalogReport, InputCatalogService
from insar_pilot.services.iw_recommendation import IwRecommendationResult, IwRecommendationService
from insar_pilot.services.output_discovery import OutputDiscoveryService
from insar_pilot.services.preflight import PreflightService
from insar_pilot.services.project_store import ProjectStore
from insar_pilot.services.run_executor import ProcessRunner
from insar_pilot.services.stack_generator import StackWorkflowService
from insar_pilot.services.visualization_service import (
    VisualizationBuildResult,
    VisualizationService,
)
from insar_pilot.ui.controllers.download_controller import DownloadController
from insar_pilot.ui.controllers.results_controller import ResultsController
from insar_pilot.ui.controllers.run_controller import RunController
from insar_pilot.ui.controllers.setup_controller import SetupController
from insar_pilot.ui.icons import BrandAssets, IconProvider
from insar_pilot.ui.pages.aoi_iw_page import AoiIwPage
from insar_pilot.ui.pages.data_download_page import DataDownloadPage
from insar_pilot.ui.pages.data_sources_page import DataSourcesPage
from insar_pilot.ui.pages.processing_plan_page import ProcessingPlanPage
from insar_pilot.ui.pages.processing_setup_page import ProcessingSetupPage
from insar_pilot.ui.pages.project_start_page import ProjectStartPage
from insar_pilot.ui.pages.results_page import ResultsPage
from insar_pilot.ui.pages.run_monitor_page import RunMonitorPage
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
        self.download_controller = DownloadController(
            self,
            self.data_download_page,
            download_service=self.download_service,
            search_service=self.download_search_service,
            preflight_service=self.preflight_service,
            tianditu_tile_proxy=self.tianditu_tile_proxy,
        )
        self.data_download_page.set_tianditu_proxy_url(self.tianditu_tile_proxy.base_url)
        self.download_controller._refresh_download_capability()
        self.results_controller = ResultsController(
            self,
            output_discovery_service=self.output_discovery_service,
            visualization_service=self.visualization_service,
        )
        self.setup_controller = SetupController(
            self,
            environment_probe=self.environment_probe,
            input_catalog_service=self.input_catalog_service,
            dem_preparation_service=self.dem_preparation_service,
            aoi_import_service=self.aoi_import_service,
            iw_recommendation_service=self.iw_recommendation_service,
            dem_coverage_service=self.dem_coverage_service,
            workflow_service=self.workflow_service,
            preflight_service=self.preflight_service,
        )
        self.run_controller = RunController(
            self,
            workflow_service=self.workflow_service,
        )
        self._connect_page_actions()
        self.combo_wheel_guard = install_no_wheel_on_combos(self)
        install_no_scroll_button_focus(self)
        self._connect_runner()
        self._populate_form_from_project()
        self.download_controller._populate_download_credentials()
        self.download_controller._populate_tianditu_key()
        self.download_controller._populate_opentopography_key()
        self.run_controller.refresh_steps_view()
        self.results_controller.refresh_outputs_view()
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

        self.page_stack.setCurrentIndex(
            0 if not self._has_project_workspace() else self._page_index_by_key["data_download"]
        )
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
        self.summary_sources_card = SummaryCard(
            self.translator.tr("summary.setup.title"), "Not prepared", "Dataset, orbit, and DEM readiness."
        )
        self.summary_aoi_card = SummaryCard(
            "AOI / BBox", "Not set", "AOI file is optional input; bbox is the processing parameter."
        )
        self.summary_selection_card = SummaryCard(
            "IW", "IW1 IW2 IW3", "Swath-level control for the processing workflow."
        )
        self.summary_reference_card = SummaryCard("Reference", "Auto", "Manual override optional.")
        self.summary_processing_card = SummaryCard(
            "Processing", "Not generated", "Workflow, coreg, looks, and concurrency."
        )
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
        self.action_search.triggered.connect(self.download_controller.search_sentinel_download_scenes)
        self.action_download.triggered.connect(self.download_controller.download_selected_sentinel_scenes)
        self.action_use_sources.triggered.connect(self.download_controller.use_download_workspace_as_data_sources)
        self.action_validate.triggered.connect(self.setup_controller.validate_environment)
        self.action_prepare.triggered.connect(self.setup_controller.prepare_data_sources)
        self.action_preview_command.triggered.connect(self.setup_controller._preview_generate_command)
        self.action_generate.triggered.connect(self.setup_controller.generate_workflow)
        self.action_run_next.triggered.connect(self.run_controller.run_next_step)
        self.action_run_selected.triggered.connect(self.run_controller.run_selected_step)
        self.action_run_remaining.triggered.connect(self.run_controller.run_remaining_steps)
        self.action_stop.triggered.connect(self.run_controller.stop_execution)
        self.action_refresh_outputs.triggered.connect(self.results_controller.refresh_outputs_view)
        self.action_about.triggered.connect(self._show_about_dialog)

        self.workflow_stepper.currentChanged.connect(self._handle_stepper_changed)
        self.project_start_page.newProjectRequested.connect(self.new_project)
        self.project_start_page.openProjectRequested.connect(self.open_project)
        self.project_start_page.recentProjectRequested.connect(self._open_recent_project)

        controller = self.download_controller
        self.data_download_page.output_dir_row.browse_button.clicked.connect(controller._browse_download_output_dir)
        self.data_download_page.aoi_file_row.browse_button.clicked.connect(controller._browse_download_aoi_file)
        self.data_download_page.test_credentials_button.clicked.connect(controller.test_asf_download_credentials)
        self.data_download_page.test_tianditu_button.clicked.connect(controller.test_tianditu_basemap_key)
        self.data_download_page.test_opentopography_button.clicked.connect(controller.test_opentopography_key)
        self.data_download_page.search_button.clicked.connect(controller.search_sentinel_download_scenes)
        self.data_download_page.clear_button.clicked.connect(controller.clear_sentinel_download_results)
        self.data_download_page.download_selected_button.clicked.connect(controller.download_selected_sentinel_scenes)
        self.data_download_page.cancel_download_button.clicked.connect(controller.cancel_sentinel_download)
        self.data_download_page.save_selected_button.clicked.connect(controller.save_selected_sentinel_scenes)
        self.data_download_page.use_as_sources_button.clicked.connect(controller.use_download_workspace_as_data_sources)
        self.data_download_page.open_workspace_button.clicked.connect(controller.open_download_workspace)

        setup = self.setup_controller
        self.validate_button.clicked.connect(setup.validate_environment)
        self.prepare_data_button.clicked.connect(setup.prepare_data_sources)
        self.inspect_inputs_button.clicked.connect(setup.inspect_inputs)

        self.extract_checkbox.toggled.connect(setup._toggle_extract_widgets)
        self.data_sources_page.shell_init_row.browse_button.clicked.connect(setup._browse_shell_init)
        self.data_sources_page.isce_root_row.browse_button.clicked.connect(setup._browse_isce_root)
        self.data_sources_page.input_path_row.browse_button.clicked.connect(setup._browse_input_dir)
        self.data_sources_page.orbit_path_row.browse_button.clicked.connect(setup._browse_orbit_dir)
        self.data_sources_page.dem_path_row.browse_button.clicked.connect(setup._browse_dem_file)
        self.data_sources_page.aux_path_row.browse_button.clicked.connect(setup._browse_aux_dir)
        self.data_sources_page.work_dir_row.browse_button.clicked.connect(setup._browse_work_dir)
        self.data_sources_page.extract_dir_row.browse_button.clicked.connect(setup._browse_extract_dir)

        self.aoi_source_browse_button.clicked.connect(setup._browse_aoi_file)
        if self.aoi_import_button is not None:
            self.aoi_import_button.clicked.connect(setup.import_aoi_file)
        self.use_common_overlap_check.toggled.connect(setup._toggle_common_overlap_mode)
        self.iw1_check.toggled.connect(setup._sync_iw_selection_card)
        self.iw2_check.toggled.connect(setup._sync_iw_selection_card)
        self.iw3_check.toggled.connect(setup._sync_iw_selection_card)
        self.recommend_iw_button.clicked.connect(setup.recommend_iw)
        self.verify_geometry_button.clicked.connect(setup.verify_aoi_iw_geometry)
        self.export_verify_button.clicked.connect(setup.export_verify_geometry_png)
        self.confirm_aoi_iw_button.clicked.connect(setup.confirm_aoi_iw)

        self.processing_page.preview_command_button.clicked.connect(setup._preview_generate_command)
        self.processing_page.rescan_button.clicked.connect(setup._rescan_existing_runfiles)
        self.generate_button.clicked.connect(setup.generate_workflow)
        self.num_proc_spin.valueChanged.connect(lambda _: setup._refresh_runfile_estimates())

        run = self.run_controller
        self.run_next_button.clicked.connect(run.run_next_step)
        self.run_selected_button.clicked.connect(run.run_selected_step)
        self.run_all_button.clicked.connect(run.run_remaining_steps)
        self.stop_button.clicked.connect(run.stop_execution)
        self.refresh_outputs_button.clicked.connect(self.results_controller.refresh_outputs_view)
        self.steps_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.steps_tree.customContextMenuRequested.connect(run._open_steps_context_menu)
        self.steps_tree.itemSelectionChanged.connect(run._handle_step_selection_changed)

        results = self.results_controller
        self.results_page.refresh_outputs_button.clicked.connect(results.refresh_outputs_view)
        self.visual_primary_browse_button.clicked.connect(results._browse_visual_primary)
        self.visual_secondary_browse_button.clicked.connect(results._browse_visual_secondary)
        self.visual_export_dir_browse_button.clicked.connect(results._browse_visual_export_dir)
        if self.visual_primary_from_outputs_button is not None:
            self.visual_primary_from_outputs_button.clicked.connect(results._fill_visual_primary_from_outputs)
        if self.visual_secondary_from_outputs_button is not None:
            self.visual_secondary_from_outputs_button.clicked.connect(results._fill_visual_secondary_from_outputs)
        self.visual_preview_button.clicked.connect(results.run_visualization_preview)
        self.visual_export_button.clicked.connect(results.run_visualization_export)
        self.visual_mode_combo.currentIndexChanged.connect(results._update_visualization_mode_ui)

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
        self.runner.command_started.connect(self.run_controller._handle_command_started)
        self.runner.command_finished.connect(self.run_controller._handle_command_finished)
        self.runner.queue_finished.connect(self.run_controller._handle_queue_finished)
        self.runner.runner_state_changed.connect(self.run_controller._handle_runner_state_changed)

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

    def _populate_form_from_project(self) -> None:
        self.download_controller.set_page_state(
            self.project.download.last_status.replace("_", " ").title()
            if self.project.download.last_status
            else "Ready",
            self.project.download.last_message or "Define AOI, dates, and Sentinel-1 SLC filters.",
        )
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
        self.setup_controller._sync_iw_selection_card()

        self.reference_date_edit.setText(self.project.workflow.reference_date)
        self.setup_controller._populate_reference_candidates()

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
        if configured_export and not self.results_controller._is_legacy_visual_export_dir(configured_export):
            self.visual_export_dir_edit.setText(configured_export)
        else:
            default_export = self.results_controller._preferred_visual_export_dir()
            self.visual_export_dir_edit.setText(str(default_export) if default_export is not None else "")
        self.visual_status_text.setPlainText(self.project.visualization.last_render_summary)
        self.results_controller._update_visualization_mode_ui()

        if self.project.visualization.last_preview_path:
            self.results_controller._display_preview_image(
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
        self.setup_controller._refresh_preflight_report()
        self.setup_controller._render_preparation_summary()
        self.setup_controller._refresh_runfile_estimates()
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
            last_status=self.download_controller.page_status.lower(),
            last_message=self.download_controller.page_message,
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

        if previous_signature and previous_signature != self.setup_controller._preparation_signature(
            self.project.workflow
        ):
            self.setup_controller._clear_prepared_state()
            self.statusBar().showMessage(
                "Data source changed. Please run Validate & Prepare Data again.",
                5000,
            )

        self.runner.set_environment(self.project.environment)
        self.refresh_status_labels()
        self._update_action_states()
        self._sync_summary_sidebar()

    def _try_save_project(self) -> None:
        try:
            self.project_store.save(self.project)
        except ValueError:
            # Data Download can run before processing data sources/work_dir are configured.
            return

    def _update_action_states(self) -> None:
        busy = self.runner.is_running()
        project_ready = self._has_project_workspace()
        has_selected_step = bool(self.run_controller._selected_steps())
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

        self.generate_button.setEnabled(
            project_ready and (not busy) and self.setup_controller._is_prepared_for_current_sources()
        )
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
        self.run_controller.refresh_steps_view()
        self.results_controller.refresh_outputs_view()
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

    def _restore_layout_settings(self) -> None:
        self.app_settings.restore_splitter("download_main", self.data_download_page.main_splitter)
        self.data_download_page.normalize_main_splitter_sizes()
        self.app_settings.restore_splitter("download_map_results", self.data_download_page.map_results_splitter)
        self.app_settings.restore_dock_visibility(
            "project_inspector", self.project_inspector_dock, default_visible=False
        )
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
            state.prepared_signature = self.setup_controller._preparation_signature(self.project.workflow)
            changed = True

        if state.prepared_signature and not self.setup_controller._is_prepared_for_current_sources():
            state.prepared_signature = ""
            changed = True

        if state.status == ProjectStatus.RUNNING:
            if state.steps:
                all_success = all(step.status == StepStatus.SUCCESS for step in state.steps)
                new_status = ProjectStatus.COMPLETED if all_success else ProjectStatus.GENERATED
            elif self.setup_controller._is_prepared_for_current_sources():
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

    def _sync_summary_sidebar(self) -> None:
        self.summary_download_card.set_value(self.download_controller.page_status)
        self.summary_download_card.set_body(self.download_controller.page_message)
        self.data_download_page.status_card.set_value(self.download_controller.page_status)
        self.data_download_page.status_card.set_body(self.download_controller.page_message)

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
            Path(self.project.workflow.orbit_path).name
            if self.project.workflow.orbit_path
            else "Point to local EOF orbit files."
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
            "Manual override applied."
            if self.project.workflow.reference_date
            else "Master date left to workflow defaults."
        )
        self.summary_processing_card.set_value(
            f"{self.project.workflow.workflow} / {self.project.workflow.coregistration}"
        )
        self.summary_processing_card.set_body(
            f"Looks {self.project.workflow.azimuth_looks}x{self.project.workflow.range_looks}, "
            f"num_proc={self.project.workflow.num_proc}"
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
            self.download_controller.page_status,
            "neutral",
        )
        self._set_nav_status(
            "setup",
            "Ready" if self.setup_controller._is_prepared_for_current_sources() else "Pending",
            "ready" if self.setup_controller._is_prepared_for_current_sources() else "warning",
        )
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
        active_threads = self.download_controller.active_background_threads()
        if not active_threads:
            self.tianditu_tile_proxy.stop()
            event.accept()
            return

        self.download_controller.cancel_active_download()
        self._shutdown_background_threads_now(active_threads)
        self.tianditu_tile_proxy.stop()
        event.accept()

    @staticmethod
    def _shutdown_background_threads_now(active_threads: list[tuple[str, QThread]]) -> None:
        """Request thread shutdown briefly, then leave Qt through a process-level exit."""

        for _name, thread in active_threads:
            thread.requestInterruption()
            thread.quit()
        for _name, thread in active_threads:
            if not thread.wait(300):
                os._exit(0)
