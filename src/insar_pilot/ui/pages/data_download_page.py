"""Standalone Sentinel-1 data download page."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.controllers.download_coordinator import DownloadStateReducer
from insar_pilot.download.dem_service import dem_label_for_source
from insar_pilot.download.models import DemCoveragePlan, DownloadResult, DownloadTask, SceneRecord, SearchCriteria
from insar_pilot.download.network import NetworkConfig
from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.widgets.collapsible_section import CollapsibleSection
from insar_pilot.ui.widgets.footprint_map import FootprintMapWidget
from insar_pilot.ui.widgets.log_console import append_text_preserving_scroll
from insar_pilot.ui.widgets.path_picker_row import PathPickerRow
from insar_pilot.ui.widgets.summary_card import SummaryCard
from insar_pilot.ui.widgets.task_progress_panel import TaskProgressPanel
from insar_pilot.ui.widgets.wizard_action_bar import WizardActionBar
from insar_pilot.ui.widgets.workflow_step_tree import WorkflowStep, WorkflowStepTree


class _NestedScrollFilter(QObject):
    """Keep wheel focus on the text edit under the cursor."""

    def __init__(self, text_edit: QPlainTextEdit) -> None:
        super().__init__(text_edit)
        self.text_edit = text_edit

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.Wheel:
            self.text_edit.setFocus(Qt.FocusReason.MouseFocusReason)
            scrollbar = self.text_edit.verticalScrollBar()
            delta = event.angleDelta().y()
            at_top = scrollbar.value() <= scrollbar.minimum()
            at_bottom = scrollbar.value() >= scrollbar.maximum()
            if (delta > 0 and not at_top) or (delta < 0 and not at_bottom):
                event.accept()
                return False
            event.ignore()
        return False


class DataDownloadPage(QWidget):
    """ASF-like Sentinel-1 search workspace for standalone data preparation."""

    CONTROL_MIN_WIDTH = 500
    CONTROL_MAX_WIDTH = 760
    CONTROL_SAFE_MIN_WIDTH = 540
    CONTROL_RECOMMENDED_MIN_WIDTH = 560
    CONTROL_RECOMMENDED_MAX_WIDTH = 680
    CONTROL_RECOMMENDED_RATIO = 0.32

    TABLE_COLUMNS = [
        "Select",
        "scene_id",
        "acquisition_time",
        "platform",
        "orbit_direction",
        "relative_orbit",
        "polarization",
        "size",
        "status",
        "local_path",
    ]
    TABLE_COLUMN_WIDTHS = [78, 300, 210, 150, 170, 150, 140, 110, 130, 420]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scenes: list[SceneRecord] = []
        self._dem_plan: DemCoveragePlan | None = None
        self._opentopography_available = False
        self._planned_download_tasks: list[DownloadTask] = []
        self._download_task_updates: dict[str, DownloadTask] = {}
        self._log_scroll_filters: list[_NestedScrollFilter] = []
        self._preferred_selected_scene_ids: set[str] = set()
        self._main_splitter_normalized = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setObjectName("dataMainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(12)
        layout.addWidget(self.main_splitter, 1)

        self.control_scroll = QScrollArea()
        self.control_scroll.setWidgetResizable(True)
        self.control_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.control_scroll.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.control_scroll.setMinimumWidth(self.CONTROL_MIN_WIDTH)
        self.control_scroll.setMaximumWidth(self.CONTROL_MAX_WIDTH)
        control_panel = QWidget()
        control_panel.setObjectName("dataControlPanel")
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(10, 8, 18, 8)
        control_layout.setSpacing(9)

        self.download_step_tree = WorkflowStepTree()
        self.download_step_tree.set_steps(
            [
                WorkflowStep("1. Account", "pending", "Validate Earthdata access"),
                WorkflowStep("2. Search Area", "pending", "Set AOI, dates, orbit, and polarization"),
                WorkflowStep("3. Scene Selection", "pending", "Select scenes from the results table"),
                WorkflowStep("4. Download", "pending", "Download SLC, orbit files, and optional DEM"),
                WorkflowStep("5. Import", "pending", "Send downloaded workspace to Processing Setup"),
            ]
        )
        self.download_step_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.download_step_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.download_step_tree.setMinimumHeight(210)
        self.download_step_tree.setMaximumHeight(230)
        control_layout.addWidget(self.download_step_tree)

        self.status_card = SummaryCard("Data Acquisition", "Ready", "Account, search, download, and setup handoff.")
        self.result_card = SummaryCard("Scene Selection", "0 scenes", "ASF search results and selected scenes appear here.")
        self.task_card = SummaryCard("Download Tasks", "0 tasks", "Download SLC ZIPs, EOF orbit files, and optional DEM.")
        for card in (self.status_card, self.result_card, self.task_card):
            card.setProperty("flatSummary", True)
        self.status_card.hide()

        self.aoi_mode_combo = QComboBox()
        self.aoi_mode_combo.addItem("BBOX", "bbox")
        self.aoi_mode_combo.addItem("WKT", "wkt")
        self.aoi_mode_combo.addItem("KML file", "kml")
        self.bbox_edit = QLineEdit()
        self.bbox_edit.setPlaceholderText("minLon,minLat,maxLon,maxLat")
        self.wkt_edit = QLineEdit()
        self.wkt_edit.setPlaceholderText("POLYGON((lon lat, ...))")
        self.aoi_file_row = PathPickerRow()
        self.aoi_file_row.line_edit.setPlaceholderText("Select AOI KML file")
        self.aoi_stack = QStackedWidget()
        self.aoi_stack.addWidget(self.bbox_edit)
        self.aoi_stack.addWidget(self.wkt_edit)
        self.aoi_stack.addWidget(self.aoi_file_row)

        self.platform_combo = QComboBox()
        for value in ("SENTINEL-1", "SENTINEL-1A", "SENTINEL-1B", "SENTINEL-1C"):
            self.platform_combo.addItem(value, value)
        self.start_date_edit = QLineEdit()
        self.start_date_edit.setPlaceholderText("YYYY-MM-DD or YYYYMMDD")
        self.end_date_edit = QLineEdit()
        self.end_date_edit.setPlaceholderText("YYYY-MM-DD or YYYYMMDD")
        self.orbit_direction_combo = QComboBox()
        for value in ("ANY", "ASCENDING", "DESCENDING"):
            self.orbit_direction_combo.addItem(value, value)
        self.relative_orbit_edit = QLineEdit()
        self.relative_orbit_edit.setPlaceholderText("optional")
        self.polarization_combo = QComboBox()
        for value in ("ANY", "VV", "VH", "VV+VH"):
            self.polarization_combo.addItem(value, value)

        query_section = CollapsibleSection("Search Definition", expanded=True)
        query_section.setProperty("density", "compact")
        self.search_definition_section = query_section
        query_section.content_layout.setContentsMargins(10, 4, 10, 10)
        query_section.content_layout.setSpacing(6)
        quick_form = QFormLayout()
        quick_form.setContentsMargins(0, 0, 0, 0)
        quick_form.setHorizontalSpacing(10)
        quick_form.setVerticalSpacing(6)
        quick_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.search_definition_form = quick_form
        quick_form.addRow(self._form_label("Dataset"), self.platform_combo)
        quick_form.addRow(self._form_label("Start date"), self.start_date_edit)
        quick_form.addRow(self._form_label("End date"), self.end_date_edit)
        quick_form.addRow(self._form_label("AOI type"), self.aoi_mode_combo)
        quick_form.addRow(self._form_label("AOI"), self.aoi_stack)
        quick_form.addRow(self._form_label("Orbit direction"), self.orbit_direction_combo)
        quick_form.addRow(self._form_label("Relative orbit"), self.relative_orbit_edit)
        quick_form.addRow(self._form_label("Polarization"), self.polarization_combo)
        query_section.content_layout.addLayout(quick_form)
        self._apply_search_definition_compact_geometry()

        query_actions = QHBoxLayout()
        query_actions.setSpacing(8)
        self.search_button = QPushButton("Search ASF")
        self.search_button.setIcon(IconProvider.icon("search"))
        self.search_button.setProperty("role", "primary")
        self.clear_button = QPushButton("Clear Results")
        self.clear_button.setIcon(IconProvider.icon("refresh"))
        self.clear_button.setProperty("role", "secondary")
        self.search_button.setFixedHeight(38)
        self.clear_button.setFixedHeight(38)
        query_actions.addWidget(self.search_button, 1)
        query_actions.addWidget(self.clear_button, 1)
        query_section.content_layout.addLayout(query_actions)
        control_layout.addWidget(query_section)

        basemap_section = CollapsibleSection("Basemap", expanded=False)
        basemap_form = QFormLayout()
        basemap_form.setContentsMargins(0, 0, 0, 0)
        basemap_form.setSpacing(10)
        self.tianditu_key_edit = QLineEdit()
        self.tianditu_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.tianditu_key_edit.setPlaceholderText("Tianditu API key")
        self.tianditu_status_label = QLabel(
            "Tianditu key is optional. External Imagery will be used automatically until Tianditu is available."
        )
        self.tianditu_status_label.setWordWrap(True)
        basemap_form.addRow(self._form_label("Tianditu key"), self.tianditu_key_edit)
        basemap_form.addRow(self._form_label("Status"), self.tianditu_status_label)
        basemap_section.content_layout.addLayout(basemap_form)
        self.test_tianditu_button = QPushButton("Test and Save Key")
        self.test_tianditu_button.setIcon(IconProvider.icon("check"))
        self.test_tianditu_button.setProperty("role", "secondary")
        basemap_section.content_layout.addWidget(self.test_tianditu_button)
        basemap_hint = QLabel(
            "Tianditu is used by default for mainland-friendly basemaps. External Esri imagery and terrain layers are available only when selected on the map."
        )
        basemap_hint.setProperty("emptyState", True)
        basemap_hint.setWordWrap(True)
        basemap_section.content_layout.addWidget(basemap_hint)
        control_layout.addWidget(basemap_section)

        credentials_section = CollapsibleSection("ASF Earthdata Account", expanded=True)
        self.credentials_section = credentials_section
        credentials_form = QFormLayout()
        credentials_form.setContentsMargins(0, 0, 0, 0)
        credentials_form.setSpacing(10)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Earthdata username")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Earthdata password")
        self.credential_status_label = QLabel("Connection has not been tested.")
        self.credential_status_label.setWordWrap(True)
        self.credential_hint_label = QLabel(
            "Recommended first step: test ASF Earthdata credentials before searching or downloading."
        )
        self.credential_hint_label.setProperty("emptyState", True)
        self.credential_hint_label.setWordWrap(True)
        self.save_netrc_checkbox = QCheckBox("Save credentials to ~/.netrc")
        credentials_form.addRow(self._form_label("Username"), self.username_edit)
        credentials_form.addRow(self._form_label("Password"), self.password_edit)
        credentials_form.addRow(self._form_label("Status"), self.credential_status_label)
        credentials_form.addRow("", self.save_netrc_checkbox)
        credentials_section.content_layout.addLayout(credentials_form)
        credentials_section.content_layout.addWidget(self.credential_hint_label)
        credentials_actions = QHBoxLayout()
        self.test_credentials_button = QPushButton("Test ASF Connection")
        self.test_credentials_button.setIcon(IconProvider.icon("account"))
        self.test_credentials_button.setProperty("role", "secondary")
        credentials_actions.addWidget(self.test_credentials_button, 1)
        credentials_section.content_layout.addLayout(credentials_actions)
        control_layout.addWidget(credentials_section)

        workspace_section = CollapsibleSection("Download Workspace", expanded=True)
        workspace_form = QFormLayout()
        workspace_form.setContentsMargins(0, 0, 0, 0)
        workspace_form.setSpacing(10)
        self.output_dir_row = PathPickerRow()
        self.output_dir_row.line_edit.setPlaceholderText("~/sentinel1_downloads")
        workspace_form.addRow(self._form_label("Output directory"), self.output_dir_row)
        self.include_orbits_checkbox = QCheckBox("Download matching EOF orbit files")
        self.include_orbits_checkbox.setChecked(True)
        workspace_form.addRow("", self.include_orbits_checkbox)
        workspace_section.content_layout.addLayout(workspace_form)
        workspace_hint = QLabel("SLC ZIPs are saved to SLC/. If enabled, matching EOF orbit files are saved to Orbit/.")
        workspace_hint.setProperty("emptyState", True)
        workspace_hint.setWordWrap(True)
        workspace_section.content_layout.addWidget(workspace_hint)
        self.aria2_status_label = QLabel("Checking aria2c availability...")
        self.aria2_status_label.setProperty("emptyState", True)
        self.aria2_status_label.setWordWrap(True)
        workspace_section.content_layout.addWidget(self.aria2_status_label)
        control_layout.addWidget(workspace_section)

        dem_section = CollapsibleSection("DEM Download", expanded=False)
        dem_form = QFormLayout()
        dem_form.setContentsMargins(0, 0, 0, 0)
        dem_form.setSpacing(10)
        self.opentopography_key_edit = QLineEdit()
        self.opentopography_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.opentopography_key_edit.setPlaceholderText("OpenTopography API key")
        self.opentopography_status_label = QLabel(
            "OpenTopography key is required for DEM download. Validate your key to enable DEM controls."
        )
        self.opentopography_status_label.setWordWrap(True)
        self.download_dem_checkbox = QCheckBox("Download matching DEM after SLC download")
        self.download_dem_checkbox.setEnabled(False)
        self.dem_source_combo = QComboBox()
        self.dem_source_combo.addItem("COP30 (Copernicus Global DSM 30m)", "COP30")
        self.dem_source_combo.addItem("AW3D30_E (ALOS World 3D Ellipsoidal, 30m)", "AW3D30_E")
        self.dem_source_combo.setEnabled(False)
        dem_form.addRow(self._form_label("OpenTopography key"), self.opentopography_key_edit)
        dem_form.addRow(self._form_label("Status"), self.opentopography_status_label)
        dem_form.addRow("", self.download_dem_checkbox)
        dem_form.addRow(self._form_label("DEM source"), self.dem_source_combo)
        dem_section.content_layout.addLayout(dem_form)
        self.test_opentopography_button = QPushButton("Test and Save Key")
        self.test_opentopography_button.setIcon(IconProvider.icon("check"))
        self.test_opentopography_button.setProperty("role", "secondary")
        dem_section.content_layout.addWidget(self.test_opentopography_button)
        dem_hint = QLabel(
            "DEM coverage is planned after SLC download using local burst footprints. COP30 uses EGM2008 heights; AW3D30_E is already ellipsoidal."
        )
        dem_hint.setProperty("emptyState", True)
        dem_hint.setWordWrap(True)
        dem_section.content_layout.addWidget(dem_hint)
        control_layout.addWidget(dem_section)

        actions_section = CollapsibleSection("Selection and Download", expanded=True)
        self.select_all_button = QPushButton("Select All")
        self.select_none_button = QPushButton("Select None")
        self.save_selected_button = QPushButton("Save Selection")
        self.download_selected_button = QPushButton("Download Selected")
        self.cancel_download_button = QPushButton("Cancel Download")
        self.use_as_sources_button = QPushButton("Use as Data Sources")
        self.open_workspace_button = QPushButton("Open Workspace")
        self.select_all_button.setIcon(IconProvider.icon("check"))
        self.select_none_button.setIcon(IconProvider.icon("cancel", "muted"))
        self.save_selected_button.setIcon(IconProvider.icon("save"))
        self.download_selected_button.setIcon(IconProvider.icon("download"))
        self.cancel_download_button.setIcon(IconProvider.icon("cancel", "error"))
        self.use_as_sources_button.setIcon(IconProvider.icon("import"))
        self.open_workspace_button.setIcon(IconProvider.icon("folder"))
        self.select_all_button.setProperty("role", "secondary")
        self.select_none_button.setProperty("role", "secondary")
        self.save_selected_button.setProperty("role", "secondary")
        self.cancel_download_button.setProperty("role", "danger")
        self.use_as_sources_button.setProperty("role", "secondary")
        self.open_workspace_button.setProperty("role", "secondary")
        self.download_selected_button.setProperty("role", "primary")
        self.cancel_download_button.setEnabled(False)
        self.selection_label = QLabel("0 selected")
        self.selection_label.setObjectName("summaryCardTitle")
        actions_section.content_layout.addWidget(self.selection_label)
        selection_row = QHBoxLayout()
        selection_row.setSpacing(8)
        selection_row.addWidget(self.select_all_button, 1)
        selection_row.addWidget(self.select_none_button, 1)
        actions_section.content_layout.addLayout(selection_row)
        save_row = QHBoxLayout()
        save_row.setSpacing(8)
        save_row.addWidget(self.save_selected_button, 1)
        save_row.addWidget(self.open_workspace_button, 1)
        actions_section.content_layout.addLayout(save_row)
        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        source_row.addWidget(self.use_as_sources_button, 1)
        actions_section.content_layout.addLayout(source_row)
        download_row = QHBoxLayout()
        download_row.setSpacing(8)
        download_row.addWidget(self.download_selected_button, 1)
        download_row.addWidget(self.cancel_download_button, 1)
        actions_section.content_layout.addLayout(download_row)

        self.task_progress_panel = TaskProgressPanel()
        self.download_progress_bar = self.task_progress_panel.progress_bar
        self.download_status_label = self.task_progress_panel.status_label
        actions_section.content_layout.addWidget(self.task_progress_panel)
        control_layout.addWidget(actions_section)

        detail_label = QLabel("Scene Detail")
        detail_label.setObjectName("summaryCardTitle")
        control_layout.addWidget(detail_label)
        self.scene_detail_text = QPlainTextEdit()
        self.scene_detail_text.setReadOnly(True)
        self.scene_detail_text.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.scene_detail_text.setPlaceholderText("Select a scene to inspect orbit, polarization, size, status, and local path.")
        self.scene_detail_text.setMinimumHeight(120)
        self.scene_detail_text.setMaximumHeight(150)
        control_layout.addWidget(self.scene_detail_text)
        log_label = QLabel("Activity Log")
        log_label.setObjectName("summaryCardTitle")
        control_layout.addWidget(log_label)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.log_text.setPlaceholderText("ASF search, selection, save, and download status will appear here.")
        self.log_text.setMinimumHeight(160)
        self.log_text.setMaximumHeight(260)
        control_layout.addWidget(self.log_text, 1)
        self._install_nested_scroll_filter(self.scene_detail_text)
        self._install_nested_scroll_filter(self.log_text)
        self._reorder_control_panel(
            control_layout,
            [
                self.download_step_tree,
                credentials_section,
                query_section,
                basemap_section,
                dem_section,
                self.result_card,
                detail_label,
                self.scene_detail_text,
                workspace_section,
                actions_section,
                self.task_card,
                log_label,
                self.log_text,
            ],
        )
        self.download_wizard_bar = WizardActionBar()
        self.download_wizard_bar.back_button.setEnabled(False)
        self.download_wizard_bar.next_button.setText("Search >")
        self.download_wizard_bar.run_button.setText("Download")
        self.download_wizard_bar.next_button.clicked.connect(self.search_button.click)
        self.download_wizard_bar.run_button.clicked.connect(self.download_selected_button.click)
        self.download_wizard_bar.cancel_button.clicked.connect(self.cancel_download_button.click)
        control_layout.addWidget(self.download_wizard_bar)
        self.control_scroll.setWidget(control_panel)
        self.main_splitter.addWidget(self.control_scroll)

        map_workspace = QFrame()
        map_workspace.setObjectName("dataMapWorkspace")
        map_workspace_layout = QVBoxLayout(map_workspace)
        map_workspace_layout.setContentsMargins(12, 8, 10, 8)
        map_workspace_layout.setSpacing(8)
        map_label = QLabel("Footprint Map")
        map_label.setObjectName("summaryCardTitle")
        map_workspace_layout.addWidget(map_label)
        self.map_results_splitter = QSplitter(Qt.Orientation.Vertical)
        self.map_results_splitter.setObjectName("dataMapResultsSplitter")
        self.map_results_splitter.setChildrenCollapsible(False)
        self.map_results_splitter.setHandleWidth(8)
        self.footprint_map = FootprintMapWidget()
        self.footprint_map.setMinimumHeight(440)
        self.map_results_splitter.addWidget(self.footprint_map)

        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(8)
        results_label = QLabel("Scenes")
        results_label.setObjectName("summaryCardTitle")
        results_layout.addWidget(results_label)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(len(self.TABLE_COLUMNS))
        self.results_table.setHorizontalHeaderLabels(self.TABLE_COLUMNS)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.setMinimumHeight(190)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setWordWrap(False)
        self.results_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.results_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._apply_results_table_geometry()
        results_layout.addWidget(self.results_table, 1)
        self.map_results_splitter.addWidget(results_panel)
        self.map_results_splitter.setStretchFactor(0, 5)
        self.map_results_splitter.setStretchFactor(1, 2)
        self.map_results_splitter.setSizes([780, 250])
        map_workspace_layout.addWidget(self.map_results_splitter, 1)
        self.main_splitter.addWidget(map_workspace)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([620, 1100])

        self.aoi_mode_combo.currentIndexChanged.connect(self._handle_aoi_mode_changed)
        self.results_table.itemSelectionChanged.connect(self._update_scene_detail_from_selection)
        self.results_table.itemChanged.connect(lambda _: self._update_selection_summary())
        self.select_all_button.clicked.connect(lambda: self._set_all_scene_checks(Qt.CheckState.Checked))
        self.select_none_button.clicked.connect(lambda: self._set_all_scene_checks(Qt.CheckState.Unchecked))
        self._handle_aoi_mode_changed()
        self._update_selection_summary()
        if self.footprint_map.fallback_reason:
            self.append_log(f"Footprint map fallback: {self.footprint_map.fallback_reason}")

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        if not self._main_splitter_normalized:
            self._main_splitter_normalized = True
            QTimer.singleShot(0, self.normalize_main_splitter_sizes)

    def normalize_main_splitter_sizes(self, force: bool = False) -> None:
        """Keep restored or first-run Data page splitter sizes in a usable range."""

        sizes = self.main_splitter.sizes()
        total_width = sum(sizes) or self.main_splitter.width() or self.width()
        if total_width <= 0:
            QTimer.singleShot(0, lambda: self.normalize_main_splitter_sizes(force=force))
            return

        current_left = sizes[0] if sizes else 0
        should_fix = (
            force
            or current_left <= 0
            or current_left < self.CONTROL_SAFE_MIN_WIDTH
            or current_left > self.CONTROL_MAX_WIDTH
        )
        if not should_fix:
            return

        left_width = self._recommended_control_width(total_width)
        if total_width > 1:
            left_width = min(left_width, total_width - 1)
        right_width = max(1, total_width - left_width)
        self.main_splitter.setSizes([left_width, right_width])

    @classmethod
    def _recommended_control_width(cls, total_width: int) -> int:
        target = int(total_width * cls.CONTROL_RECOMMENDED_RATIO)
        return max(
            cls.CONTROL_RECOMMENDED_MIN_WIDTH,
            min(cls.CONTROL_RECOMMENDED_MAX_WIDTH, target),
        )

    def _apply_search_definition_compact_geometry(self) -> None:
        compact_widgets = [
            self.platform_combo,
            self.start_date_edit,
            self.end_date_edit,
            self.aoi_mode_combo,
            self.bbox_edit,
            self.wkt_edit,
            self.aoi_stack,
            self.orbit_direction_combo,
            self.relative_orbit_edit,
            self.polarization_combo,
            self.aoi_file_row,
            self.aoi_file_row.line_edit,
            self.aoi_file_row.browse_button,
        ]
        for widget in compact_widgets:
            widget.setFixedHeight(36)

    @staticmethod
    def _form_label(text: str) -> QLabel:
        """Build a transparent form label that matches the rest of the shell."""

        label = QLabel(text)
        label.setProperty("formLabel", True)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setWordWrap(False)
        return label

    def _install_nested_scroll_filter(self, text_edit: QPlainTextEdit) -> None:
        scroll_filter = _NestedScrollFilter(text_edit)
        text_edit.viewport().installEventFilter(scroll_filter)
        self._log_scroll_filters.append(scroll_filter)

    @staticmethod
    def _reorder_control_panel(layout: QVBoxLayout, widgets: list[QWidget]) -> None:
        for widget in widgets:
            layout.removeWidget(widget)
        for widget in widgets:
            layout.addWidget(widget, 1 if isinstance(widget, QPlainTextEdit) and widget.placeholderText().startswith("ASF search") else 0)

    def criteria(self) -> SearchCriteria:
        """Return validated search criteria from page controls."""

        relative_text = self.relative_orbit_edit.text().strip()
        return SearchCriteria(
            start_date=self.start_date_edit.text().strip(),
            end_date=self.end_date_edit.text().strip(),
            aoi_mode=str(self.aoi_mode_combo.currentData() or "bbox"),
            bbox=self.bbox_edit.text().strip(),
            wkt=self.wkt_edit.text().strip(),
            aoi_file=self.aoi_file_row.line_edit.text().strip(),
            platform=str(self.platform_combo.currentData() or "SENTINEL-1"),
            orbit_direction=str(self.orbit_direction_combo.currentData() or "ANY"),
            relative_orbit=int(relative_text) if relative_text else None,
            polarization=str(self.polarization_combo.currentData() or "ANY"),
        )

    def output_dir(self) -> str:
        """Return the selected standalone download workspace."""

        return self.output_dir_row.line_edit.text().strip()

    def include_orbits(self) -> bool:
        """Return whether orbit-file tasks should be created."""

        return self.include_orbits_checkbox.isChecked()

    def should_download_dem(self) -> bool:
        """Return whether DEM download should run after SLC download."""

        return self.download_dem_checkbox.isChecked() and self.download_dem_checkbox.isEnabled()

    def dem_source(self) -> str:
        """Return the selected DEM source identifier."""

        return str(self.dem_source_combo.currentData() or "COP30")

    def credential_inputs(self) -> tuple[str, str]:
        """Return ASF Earthdata username/password fields."""

        return self.username_edit.text().strip(), self.password_edit.text()

    def set_credential_inputs(self, username: str, password: str, *, source: str = "") -> None:
        """Populate ASF Earthdata credentials from a local source."""

        self.username_edit.setText(username)
        self.password_edit.setText(password)
        if source:
            self.credential_status_label.setText(f"Loaded Earthdata credentials from {source}.")

    def network_config(self) -> NetworkConfig:
        """Return the internal default network behavior for remote calls."""

        return NetworkConfig()

    def tianditu_key(self) -> str:
        """Return the Tianditu API key entered for the basemap."""

        return self.tianditu_key_edit.text().strip()

    def opentopography_key(self) -> str:
        """Return the OpenTopography API key entered for DEM download."""

        return self.opentopography_key_edit.text().strip()

    def set_tianditu_key(self, key: str, *, source: str = "") -> None:
        """Populate the Tianditu key and refresh the footprint map."""

        self.tianditu_key_edit.setText(key)
        if source:
            self.tianditu_status_label.setText(f"Loaded Tianditu key from {source}.")
        else:
            self.tianditu_status_label.setText(
                "Tianditu key is optional. External Imagery will be used automatically until Tianditu is available."
            )

    def set_opentopography_key(self, key: str, *, source: str = "") -> None:
        """Populate the OpenTopography key and status from a local source."""

        self.opentopography_key_edit.setText(key)
        if source:
            self.opentopography_status_label.setText(f"Loaded OpenTopography key from {source}.")
        else:
            self.opentopography_status_label.setText(
                "OpenTopography key is required for DEM download. Validate your key to enable DEM controls."
            )

    def set_tianditu_proxy_url(self, base_url: str) -> None:
        """Provide the localhost tile proxy URL used by the embedded map."""

        self.footprint_map.set_tianditu_proxy_url(base_url)

    def set_tianditu_available(self, available: bool) -> None:
        """Enable or disable Tianditu layers in the embedded map."""

        self.footprint_map.set_tianditu_enabled(available)

    def set_preferred_basemap(self, name: str) -> None:
        """Select which basemap should be used on the next map refresh."""

        self.footprint_map.set_preferred_basemap(name)

    def set_tianditu_basemap_state(self, *, available: bool, preferred_basemap: str) -> None:
        """Update Tianditu availability and startup basemap together."""

        self.footprint_map.set_tianditu_basemap_state(
            enabled=available,
            preferred_basemap=preferred_basemap,
        )

    def set_tianditu_status(self, message: str) -> None:
        """Update the Tianditu key status message."""

        self.tianditu_status_label.setText(message)

    def set_tianditu_busy(self, busy: bool) -> None:
        """Toggle the Tianditu key check button while validation runs."""

        self.test_tianditu_button.setEnabled(not busy)
        self.test_tianditu_button.setText("Testing Key..." if busy else "Test and Save Key")

    def set_opentopography_status(self, message: str) -> None:
        """Update the OpenTopography key status message."""

        self.opentopography_status_label.setText(message)

    def set_opentopography_busy(self, busy: bool) -> None:
        """Toggle the OpenTopography key action while validation runs."""

        self.test_opentopography_button.setEnabled(not busy)
        self.test_opentopography_button.setText("Testing Key..." if busy else "Test and Save Key")

    def set_opentopography_available(self, available: bool) -> None:
        """Enable or disable DEM controls based on OpenTopography key health."""

        self._opentopography_available = bool(available)
        self.download_dem_checkbox.setEnabled(self._opentopography_available)
        self.dem_source_combo.setEnabled(self._opentopography_available)
        if not self._opentopography_available:
            self.download_dem_checkbox.setChecked(False)

    def should_save_netrc(self) -> bool:
        """Return whether credentials should be persisted to ~/.netrc."""

        return self.save_netrc_checkbox.isChecked()

    def set_credential_status(self, message: str) -> None:
        """Update the credential status label."""

        self.credential_status_label.setText(message)
        lowered = message.lower()
        if any(token in lowered for token in ("ok", "success", "validated", "loaded")):
            self.download_step_tree.set_step_status("1. Account", "ready", message)
            if any(token in lowered for token in ("ok", "success", "validated")):
                self.credentials_section.toggle_button.setChecked(False)
        elif any(token in lowered for token in ("fail", "error", "invalid")):
            self.download_step_tree.set_step_status("1. Account", "failed", message)

    def set_aria2_capability(self, available: bool, path: str = "") -> None:
        """Display current aria2c backend availability."""

        if available:
            self.aria2_status_label.setText(
                f"aria2c available: {path}. SLC downloads use the aria2c multipart resumable backend."
            )
        else:
            self.aria2_status_label.setText(
                "aria2c was not found on PATH. SLC downloads require aria2c for multipart resumable downloads."
            )

    def set_search_busy(self, busy: bool) -> None:
        """Toggle controls that should be locked while an ASF request is running."""

        self.search_button.setEnabled(not busy)
        self.search_button.setText("Searching ASF..." if busy else "Search ASF")
        self.clear_button.setEnabled(not busy)
        self.download_step_tree.set_step_status(
            "2. Search Area",
            "running" if busy else "pending",
            "ASF query is running." if busy else "Ready for search.",
        )

    def set_download_busy(self, busy: bool) -> None:
        """Toggle download controls while the background worker is active."""

        if busy:
            self._download_task_updates = {}
            self.download_step_tree.set_step_status("4. Download", "running", "Download worker is active.")
        else:
            self.download_step_tree.set_step_status("4. Download", "pending", "Ready to download selected scenes.")
        self.download_selected_button.setEnabled(not busy)
        self.cancel_download_button.setEnabled(busy)
        self.search_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        self.save_selected_button.setEnabled(not busy)
        self.include_orbits_checkbox.setEnabled(not busy)
        self.download_dem_checkbox.setEnabled((not busy) and self._opentopography_available)
        self.dem_source_combo.setEnabled((not busy) and self._opentopography_available)
        self.test_opentopography_button.setEnabled(not busy)

    def set_download_tasks(self, tasks: list[DownloadTask]) -> None:
        """Show the planned task set before the worker starts producing updates."""

        self._planned_download_tasks = list(tasks)
        self._download_task_updates = {task.task_id: task for task in self._planned_download_tasks}
        self.task_progress_panel.apply_state(DownloadStateReducer.from_tasks(self._planned_download_tasks))
        self.task_card.set_value(f"0/{len(self._planned_download_tasks)} tasks")
        self.task_card.set_body("Download plan ready. Waiting for worker updates.")
        if tasks:
            self.download_step_tree.set_step_status("4. Download", "ready", f"{len(tasks)} task(s) planned.")

    def set_scenes(self, scenes: list[SceneRecord]) -> None:
        """Render search results in the table."""

        self._scenes = list(scenes)
        self.clear_dem_plan(update_map=False)
        self.results_table.blockSignals(True)
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(len(self._scenes))
        for row, scene in enumerate(self._scenes):
            check_item = QTableWidgetItem("")
            check_item.setFlags(check_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checked = not self._preferred_selected_scene_ids or scene.scene_id in self._preferred_selected_scene_ids
            check_item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.results_table.setItem(row, 0, check_item)
            values = [
                scene.scene_id,
                scene.acquisition_time,
                scene.platform,
                scene.orbit_direction,
                str(scene.relative_orbit),
                scene.polarization,
                f"{scene.size_mb:g} MB",
                scene.status,
                scene.local_path,
            ]
            for col, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.results_table.setItem(row, col, item)
        self.results_table.setSortingEnabled(True)
        self.results_table.blockSignals(False)
        self._apply_results_table_geometry()
        self.result_card.set_value(f"{len(self._scenes)} scenes")
        self.result_card.set_body("All scenes are checked for save/download by default.")
        self.download_step_tree.set_step_status(
            "2. Search Area",
            "ready" if self._scenes else "warning",
            f"{len(self._scenes)} scene(s) found.",
        )
        self.download_step_tree.set_step_status(
            "3. Scene Selection",
            "ready" if self._scenes else "pending",
            "Review and adjust selected scenes.",
        )
        if self._scenes:
            self.results_table.selectRow(0)
        else:
            self.scene_detail_text.clear()
        self._refresh_footprint_map()
        self._update_selection_summary()

    def set_preferred_selected_scene_ids(self, scene_ids: list[str]) -> None:
        """Remember project-level scene selections for the next rendered result table."""

        self._preferred_selected_scene_ids = {scene_id for scene_id in scene_ids if scene_id}

    def selected_scenes(self) -> list[SceneRecord]:
        """Return checked scenes from the results table."""

        scene_by_id = {scene.scene_id: scene for scene in self._scenes}
        selected: list[SceneRecord] = []
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                scene_id_item = self.results_table.item(row, 1)
                if scene_id_item is not None and scene_id_item.text() in scene_by_id:
                    selected.append(scene_by_id[scene_id_item.text()])
        return selected

    def apply_download_results(self, results: list[DownloadResult]) -> None:
        """Update scene status and local path after downloads."""

        result_by_scene = {result.scene.scene_id: result for result in results if result.product_type.upper() == "SLC"}
        updated: list[SceneRecord] = []
        for scene in self._scenes:
            result = result_by_scene.get(scene.scene_id)
            updated.append(result.scene if result else scene)
        self._scenes = updated
        for result in result_by_scene.values():
            self._update_scene_row(result.scene.scene_id, result.status, result.local_path)
        self._update_scene_detail_from_selection(update_map=False)
        self.task_card.set_value(f"{len(results)} tasks")
        completed = sum(result.status == "completed" for result in results)
        skipped = sum(result.status == "skipped" for result in results)
        failed = sum(result.status == "failed" for result in results)
        cancelled = sum(result.status == "cancelled" for result in results)
        dem_result = next((result for result in results if result.product_type.upper() == "DEM"), None)
        self.task_card.set_body(
            f"{completed} completed, {skipped} skipped, {failed} failed, {cancelled} cancelled."
        )
        self.task_progress_panel.apply_state(DownloadStateReducer.from_results(list(results)))
        self.download_step_tree.set_step_status(
            "4. Download",
            "failed" if failed else "ready",
            f"{completed} completed, {failed} failed, {cancelled} cancelled.",
        )
        if results and not failed and not cancelled:
            self.download_step_tree.set_step_status("5. Import", "ready", "Downloaded workspace can be imported.")
        if dem_result is not None and dem_result.message:
            self.download_status_label.setText(dem_result.message)
        elif dem_result is None:
            self.download_status_label.setText("Download finished." if results else "No active download.")

    def apply_task_update(self, task: DownloadTask, completed_count: int, total_count: int) -> None:
        """Reflect a task status update in the table and progress summary."""

        self._download_task_updates[task.task_id] = task
        if self._planned_download_tasks:
            self._planned_download_tasks = [
                task if planned.task_id == task.task_id else planned for planned in self._planned_download_tasks
            ]
        if task.product_type.upper() == "SLC":
            updated: list[SceneRecord] = []
            for scene in self._scenes:
                if scene.scene_id == task.scene.scene_id:
                    updated.append(scene.with_status(task.status, task.local_path))
                else:
                    updated.append(scene)
            self._scenes = updated
            self._update_scene_row(task.scene.scene_id, task.status, task.local_path)

        tasks_for_summary = self._planned_download_tasks or list(self._download_task_updates.values())
        self.task_progress_panel.apply_state(DownloadStateReducer.from_tasks(tasks_for_summary, active_task=task))
        task_progress = self._task_progress_text(task)
        total_progress = self._total_progress_text()
        if task_progress or total_progress:
            self.download_status_label.setText(
                f"{task.product_type}: {task.status} ({completed_count}/{total_count})"
                + (f" | {task_progress}" if task_progress else "")
                + (f"\nTotal: {total_progress}" if total_progress else "")
            )
        self.task_card.set_value(f"{completed_count}/{total_count} tasks")
        self.task_card.set_body(
            " | ".join(part for part in [task.message or task.local_path or task.scene.scene_id, task_progress] if part)
        )
        self.download_step_tree.set_step_status(
            "4. Download",
            "running" if task.status == "running" else task.status,
            f"{task.product_type}: {task.status} ({completed_count}/{total_count})",
        )

    def clear_results(self) -> None:
        """Clear rendered search results while keeping the activity log."""

        self._scenes = []
        self.clear_dem_plan(update_map=False)
        self.results_table.setRowCount(0)
        self.scene_detail_text.clear()
        self.footprint_map.clear()
        self.result_card.set_value("0 scenes")
        self.result_card.set_body("Run search to list matching scenes.")
        self.task_card.set_value("0 tasks")
        self.task_card.set_body("Select scenes to download SLC ZIPs and EOF orbits.")
        self._planned_download_tasks = []
        self._download_task_updates = {}
        self.task_progress_panel.reset()
        self.download_step_tree.set_step_status("2. Search Area", "pending", "Ready for search.")
        self.download_step_tree.set_step_status("3. Scene Selection", "pending", "No scenes selected.")
        self.download_step_tree.set_step_status("4. Download", "pending", "No download plan.")
        self.download_step_tree.set_step_status("5. Import", "pending", "Download workspace is not ready.")
        self._update_selection_summary()

    def append_log(self, message: str) -> None:
        """Append one status line to the page log."""

        append_text_preserving_scroll(self.log_text, f"{message}\n")

    def _handle_aoi_mode_changed(self) -> None:
        mode = str(self.aoi_mode_combo.currentData() or "bbox")
        self.aoi_stack.setCurrentIndex({"bbox": 0, "wkt": 1, "kml": 2}.get(mode, 0))

    def _set_all_scene_checks(self, state: Qt.CheckState) -> None:
        """Set all result checkboxes and refresh selection counts."""

        self.results_table.blockSignals(True)
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 0)
            if item is not None:
                item.setCheckState(state)
        self.results_table.blockSignals(False)
        self._update_selection_summary()

    def _update_selection_summary(self) -> None:
        """Update the selected-scene affordance and summary card."""

        selected_count = len(self.selected_scenes())
        total_count = len(self._scenes)
        self.selection_label.setText(f"{selected_count} selected of {total_count}")
        if total_count:
            self.result_card.set_value(f"{total_count} scenes")
            self.result_card.set_body(f"{selected_count} selected for save/download.")
            self.download_step_tree.set_step_status(
                "3. Scene Selection",
                "ready" if selected_count else "warning",
                f"{selected_count} of {total_count} selected.",
            )
        else:
            self.result_card.set_value("0 scenes")
            self.result_card.set_body("Run search to list matching scenes.")
        if self._scenes:
            self.footprint_map.set_highlight(self._current_scene_id(), self._selected_scene_ids())

    def _selected_scene_from_current_row(self) -> SceneRecord | None:
        row = self.results_table.currentRow()
        if row < 0:
            return None
        scene_id_item = self.results_table.item(row, 1)
        if scene_id_item is None:
            return None
        scene_id = scene_id_item.text()
        return next((scene for scene in self._scenes if scene.scene_id == scene_id), None)

    def _update_scene_detail_from_selection(self, *, update_map: bool = True) -> None:
        """Render a compact scene detail panel for the selected result."""

        scene = self._selected_scene_from_current_row()
        if scene is None:
            if self.scene_detail_text.toPlainText():
                self.scene_detail_text.clear()
            if update_map:
                self.footprint_map.set_highlight("", self._selected_scene_ids())
            return

        detail = "\n".join(
            [
                scene.scene_id,
                "",
                f"Acquisition time: {scene.acquisition_time}",
                f"Platform: {scene.platform}",
                f"Orbit direction: {scene.orbit_direction}",
                f"Relative orbit: {scene.relative_orbit}",
                f"Polarization: {scene.polarization}",
                f"Size: {scene.size_mb:g} MB",
                f"Footprint: {'available' if scene.footprint_geojson else 'missing'}",
                f"Status: {scene.status}",
                f"Local path: {scene.local_path or '-'}",
            ]
        )
        if self.scene_detail_text.toPlainText() != detail:
            self.scene_detail_text.setPlainText(detail)
        if update_map:
            self.footprint_map.set_highlight(scene.scene_id, self._selected_scene_ids())

    def _update_scene_row(self, scene_id: str, status: str, local_path: str) -> None:
        for row in range(self.results_table.rowCount()):
            scene_id_item = self.results_table.item(row, 1)
            if scene_id_item is None or scene_id_item.text() != scene_id:
                continue
            status_item = self.results_table.item(row, 8)
            path_item = self.results_table.item(row, 9)
            if status_item is not None:
                status_item.setText(status)
            if path_item is not None:
                path_item.setText(local_path)
            break

    def _current_scene_id(self) -> str:
        scene = self._selected_scene_from_current_row()
        return scene.scene_id if scene is not None else ""

    def _selected_scene_ids(self) -> set[str]:
        return {scene.scene_id for scene in self.selected_scenes()}

    def _refresh_footprint_map(self) -> None:
        try:
            criteria = self.criteria()
        except Exception:
            criteria = None
        self.footprint_map.set_data(
            criteria,
            self._scenes,
            highlighted_scene_id=self._current_scene_id(),
            selected_scene_ids=self._selected_scene_ids(),
        )
        self.footprint_map.set_dem_bbox(self._dem_plan.planned_bbox_snwe if self._dem_plan is not None else None)

    def _apply_results_table_geometry(self) -> None:
        header = self.results_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        header.setDefaultSectionSize(150)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate(self.TABLE_COLUMN_WIDTHS):
            self.results_table.setColumnWidth(column, width)

    def set_dem_plan(self, plan: DemCoveragePlan | None, *, update_map: bool = False) -> None:
        """Store and visualize the latest DEM coverage planning result."""

        self._dem_plan = plan
        if update_map:
            self.footprint_map.set_dem_bbox(plan.planned_bbox_snwe if plan is not None else None)
        if plan is not None:
            label = dem_label_for_source(plan.source_id)
            self.task_card.set_body(f"DEM plan ready: {label} / {plan.planning_mode}.")

    def clear_dem_plan(self, *, update_map: bool = True) -> None:
        """Clear the current DEM planning result and map overlay."""

        self._dem_plan = None
        if update_map:
            self.footprint_map.set_dem_bbox(None)

    @classmethod
    def _task_progress_text(cls, task: DownloadTask) -> str:
        parts = []
        if task.bytes_done or task.bytes_total:
            if task.bytes_total:
                parts.append(f"{cls._format_bytes(task.bytes_done)} / {cls._format_bytes(task.bytes_total)}")
            else:
                parts.append(cls._format_bytes(task.bytes_done))
        if task.speed_bps > 0 and task.status == "running":
            parts.append(f"{cls._format_bytes(task.speed_bps)}/s")
        if task.eta_seconds is not None and task.status == "running":
            parts.append(f"ETA {cls._format_duration(task.eta_seconds)}")
        if task.backend:
            parts.append(f"via {task.backend}")
        return ", ".join(parts)

    def _total_progress_text(self) -> str:
        tasks = list(self._download_task_updates.values())
        total = sum(task.bytes_total for task in tasks if task.bytes_total)
        done = sum(task.bytes_done for task in tasks if task.bytes_done)
        speed = sum(task.speed_bps for task in tasks if task.status == "running")
        if not total and not done and speed <= 0:
            return ""
        parts = []
        if total:
            parts.append(f"{self._format_bytes(done)} / {self._format_bytes(total)}")
        elif done:
            parts.append(self._format_bytes(done))
        if speed > 0:
            parts.append(f"{self._format_bytes(speed)}/s")
        if total and speed > 0 and done < total:
            parts.append(f"ETA {self._format_duration((total - done) / speed)}")
        return ", ".join(parts)

    @staticmethod
    def _format_bytes(value: float | int) -> str:
        size = float(value or 0)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size) < 1024.0 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{size:.1f} TB"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(int(seconds), 0)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes:02d}m"
        if minutes:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"
