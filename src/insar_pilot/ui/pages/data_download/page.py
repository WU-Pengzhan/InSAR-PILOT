"""Standalone Sentinel-1 data download page assembly."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.download.network import NetworkConfig
from insar_pilot.ui.pages.data_download.actions_section import ActionsSection
from insar_pilot.ui.pages.data_download.credentials_section import BasemapSection, CredentialsSection
from insar_pilot.ui.pages.data_download.results_panel import ResultsController
from insar_pilot.ui.pages.data_download.search_section import SearchSection
from insar_pilot.ui.pages.data_download.workspace_section import DemSection, WorkspaceSection
from insar_pilot.ui.widgets.summary_card import SummaryCard
from insar_pilot.ui.widgets.wizard_action_bar import WizardActionBar
from insar_pilot.ui.widgets.workflow_step_tree import WorkflowStep, WorkflowStepTree


class DataDownloadPage(QWidget):
    """ASF-like Sentinel-1 search workspace for standalone data preparation."""

    CONTROL_MIN_WIDTH = 500
    CONTROL_MAX_WIDTH = 760
    CONTROL_SAFE_MIN_WIDTH = 540
    CONTROL_RECOMMENDED_MIN_WIDTH = 560
    CONTROL_RECOMMENDED_MAX_WIDTH = 680
    CONTROL_RECOMMENDED_RATIO = 0.32

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
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
        self.result_card = SummaryCard(
            "Scene Selection", "0 scenes", "ASF search results and selected scenes appear here."
        )
        self.task_card = SummaryCard(
            "Download Tasks", "0 tasks", "Download SLC ZIPs, EOF orbit files, and optional DEM."
        )
        for card in (self.status_card, self.result_card, self.task_card):
            card.setProperty("flatSummary", True)
        self.status_card.hide()

        self._search = SearchSection()
        control_layout.addWidget(self._search)
        self._basemap = BasemapSection()
        control_layout.addWidget(self._basemap)
        self._credentials = CredentialsSection()
        control_layout.addWidget(self._credentials)
        self._workspace = WorkspaceSection()
        control_layout.addWidget(self._workspace)
        self._dem = DemSection()
        control_layout.addWidget(self._dem)
        self._actions = ActionsSection()
        control_layout.addWidget(self._actions)

        self._results = ResultsController(
            download_step_tree=self.download_step_tree,
            result_card=self.result_card,
            task_card=self.task_card,
            selection_label=self._actions.selection_label,
            task_progress_panel=self._actions.task_progress_panel,
            download_status_label=self._actions.download_status_label,
            criteria_provider=self._search.criteria,
            parent=self,
        )

        detail_label = QLabel("Scene Detail")
        detail_label.setObjectName("summaryCardTitle")
        control_layout.addWidget(detail_label)
        control_layout.addWidget(self._results.scene_detail_text)
        log_label = QLabel("Activity Log")
        log_label.setObjectName("summaryCardTitle")
        control_layout.addWidget(log_label)
        control_layout.addWidget(self._results.log_text, 1)
        self._reorder_control_panel(
            control_layout,
            [
                self.download_step_tree,
                self._credentials,
                self._search,
                self._basemap,
                self._dem,
                self.result_card,
                detail_label,
                self._results.scene_detail_text,
                self._workspace,
                self._actions,
                self.task_card,
                log_label,
                self._results.log_text,
            ],
        )
        self.download_wizard_bar = WizardActionBar()
        self.download_wizard_bar.back_button.setEnabled(False)
        self.download_wizard_bar.next_button.setText("Search >")
        self.download_wizard_bar.run_button.setText("Download")
        self.download_wizard_bar.next_button.clicked.connect(self._search.search_button.click)
        self.download_wizard_bar.run_button.clicked.connect(self._actions.download_selected_button.click)
        self.download_wizard_bar.cancel_button.clicked.connect(self._actions.cancel_download_button.click)
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
        self.map_results_splitter.addWidget(self._results.footprint_map)

        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(8)
        results_label = QLabel("Scenes")
        results_label.setObjectName("summaryCardTitle")
        results_layout.addWidget(results_label)
        results_layout.addWidget(self._results.results_table, 1)
        self.map_results_splitter.addWidget(results_panel)
        self.map_results_splitter.setStretchFactor(0, 5)
        self.map_results_splitter.setStretchFactor(1, 2)
        self.map_results_splitter.setSizes([780, 250])
        map_workspace_layout.addWidget(self.map_results_splitter, 1)
        self.main_splitter.addWidget(map_workspace)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([620, 1100])

        self._actions.select_all_button.clicked.connect(
            lambda: self._results.set_all_scene_checks(Qt.CheckState.Checked)
        )
        self._actions.select_none_button.clicked.connect(
            lambda: self._results.set_all_scene_checks(Qt.CheckState.Unchecked)
        )
        self._expose_public_surface()
        if self._results.footprint_map.fallback_reason:
            self.append_log(f"Footprint map fallback: {self._results.footprint_map.fallback_reason}")

    def _adopt(self, source: object, *names: str) -> None:
        """Re-expose a child widget or bound method under the page's namespace."""

        for name in names:
            setattr(self, name, getattr(source, name))

    def _expose_public_surface(self) -> None:
        """Keep the compatibility surface MainWindow/DownloadController call directly."""

        self.search_definition_section = self._search
        self.credentials_section = self._credentials
        self._adopt(
            self._search,
            "search_definition_form", "aoi_mode_combo", "bbox_edit", "wkt_edit", "aoi_file_row",
            "aoi_stack", "platform_combo", "start_date_edit", "end_date_edit", "orbit_direction_combo",
            "relative_orbit_edit", "polarization_combo", "search_button", "clear_button",
            "criteria", "_handle_aoi_mode_changed",
        )
        self._adopt(
            self._credentials,
            "username_edit", "password_edit", "credential_status_label", "credential_hint_label",
            "save_netrc_checkbox", "test_credentials_button", "credential_inputs",
            "set_credential_inputs", "should_save_netrc",
        )
        self._adopt(
            self._basemap,
            "tianditu_key_edit", "tianditu_status_label", "test_tianditu_button", "tianditu_key",
            "set_tianditu_key", "set_tianditu_status", "set_tianditu_busy",
        )
        self._adopt(
            self._workspace,
            "output_dir_row", "include_orbits_checkbox", "aria2_status_label",
            "output_dir", "include_orbits", "set_aria2_capability",
        )
        self._adopt(
            self._dem,
            "opentopography_key_edit", "opentopography_status_label", "download_dem_checkbox",
            "dem_source_combo", "test_opentopography_button", "should_download_dem", "dem_source",
            "opentopography_key", "set_opentopography_key", "set_opentopography_status",
            "set_opentopography_busy", "set_opentopography_available",
        )
        self._adopt(
            self._actions,
            "select_all_button", "select_none_button", "save_selected_button", "download_selected_button",
            "cancel_download_button", "use_as_sources_button", "open_workspace_button", "selection_label",
            "task_progress_panel", "download_progress_bar", "download_status_label",
        )
        self._adopt(
            self._results,
            "footprint_map", "results_table", "scene_detail_text", "log_text", "set_download_tasks",
            "set_scenes", "set_preferred_selected_scene_ids", "selected_scenes", "apply_download_results",
            "apply_task_update", "clear_results", "append_log", "set_dem_plan", "clear_dem_plan",
            "set_tianditu_proxy_url", "set_tianditu_available", "set_preferred_basemap", "set_tianditu_basemap_state",
        )

    @staticmethod
    def _reorder_control_panel(layout: QVBoxLayout, widgets: list[QWidget]) -> None:
        for widget in widgets:
            layout.removeWidget(widget)
        for widget in widgets:
            layout.addWidget(
                widget,
                1 if isinstance(widget, QPlainTextEdit) and widget.placeholderText().startswith("ASF search") else 0,
            )

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

    def network_config(self) -> NetworkConfig:
        """Return the internal default network behavior for remote calls."""

        return NetworkConfig()

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
            self._results.clear_task_updates()
            self.download_step_tree.set_step_status("4. Download", "running", "Download worker is active.")
        else:
            self.download_step_tree.set_step_status("4. Download", "pending", "Ready to download selected scenes.")
        available = self._dem.opentopography_available
        self.download_selected_button.setEnabled(not busy)
        self.cancel_download_button.setEnabled(busy)
        self.search_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        self.save_selected_button.setEnabled(not busy)
        self.include_orbits_checkbox.setEnabled(not busy)
        self.download_dem_checkbox.setEnabled((not busy) and available)
        self.dem_source_combo.setEnabled((not busy) and available)
        self.test_opentopography_button.setEnabled(not busy)
