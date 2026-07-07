"""Unified processing setup page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.widgets.command_preview import CommandPreview
from insar_pilot.ui.widgets.geometry_verify_panel import GeometryVerifyPanel
from insar_pilot.ui.widgets.page_scaffold import ActionBar, InlineAlert, PageScaffold, SectionPanel
from insar_pilot.ui.widgets.path_picker_row import PathPickerRow
from insar_pilot.ui.widgets.preflight_check_list import PreflightCheckList
from insar_pilot.ui.widgets.property_form import PropertyForm
from insar_pilot.ui.widgets.summary_card import SummaryCard
from insar_pilot.ui.widgets.technical_details_panel import TechnicalDetailsPanel
from insar_pilot.ui.widgets.wizard_action_bar import WizardActionBar
from insar_pilot.ui.widgets.workflow_step_tree import WorkflowStep, WorkflowStepTree


class ProcessingSetupPage(PageScaffold):
    """One-page setup workbench for Sentinel-1 stack generation."""

    def __init__(self, parent=None) -> None:
        super().__init__(
            "Processing Setup",
            "Follow each setup step, confirm parameters, then generate the processing workflow.",
            parent,
        )
        self._build_workbench_shell()
        self._build_summary_cards()
        self._build_environment_and_sources()
        self._build_geometry_section()
        self._build_stack_section()
        self._build_preflight_section()
        self._build_generation_section()
        self._build_wizard_actions()

    def _build_workbench_shell(self) -> None:
        self.workbench_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setup_step_tree = WorkflowStepTree()
        self.setup_step_tree.set_steps(
            [
                WorkflowStep("1. Environment", "pending", "Runtime and shell readiness"),
                WorkflowStep("2. Data", "pending", "Input, orbit, DEM, and work folder"),
                WorkflowStep("3. Geometry", "pending", "AOI, bbox, and IW swaths"),
                WorkflowStep("4. Parameters", "pending", "Processing mode and looks"),
                WorkflowStep("5. Preflight", "pending", "Blockers and warnings"),
                WorkflowStep("6. Generate", "pending", "Create run_files workflow"),
            ]
        )
        self.workbench_splitter.addWidget(self.setup_step_tree)

        self.workbench_content = QWidget()
        self.workbench_content_layout = QVBoxLayout(self.workbench_content)
        self.workbench_content_layout.setContentsMargins(0, 0, 0, 0)
        self.workbench_content_layout.setSpacing(8)
        self.workbench_splitter.addWidget(self.workbench_content)
        self.workbench_splitter.setStretchFactor(0, 0)
        self.workbench_splitter.setStretchFactor(1, 1)
        self.workbench_splitter.setSizes([250, 1000])
        self.content_layout.addWidget(self.workbench_splitter, 1)

    def _add_workbench_widget(self, widget: QWidget) -> None:
        self.workbench_content_layout.addWidget(widget)

    def _build_summary_cards(self) -> None:
        self.summary_card_container = QWidget(self)
        self.summary_card_container.setObjectName("processingSetupSummaryCards")
        self.summary_card_container.hide()
        self.dataset_card = SummaryCard(
            "Dataset",
            "Not prepared",
            "Select Sentinel-1 ZIP/SAFE inputs and build the manifest.",
            self.summary_card_container,
        )
        self.orbit_card = SummaryCard("EOF Orbit", "Not set", "Point to local EOF orbit files.")
        self.dem_card = SummaryCard("DEM", "Not set", "GeoTIFF or prepared DEM.")
        self.source_card = SummaryCard("AOI Source", "Manual", "AOI can auto-fill the processing bbox.")
        self.bbox_card = SummaryCard("Processing BBox (SNWE)", "Not set", "Final geographic processing boundary.")
        self.iw_card = SummaryCard("IW Swaths", "IW1 IW2 IW3", "At least one IW must be selected.")
        self.plan_card = SummaryCard(
            "Processing Plan",
            "Not generated",
            "Review workflow, coreg, looks, and parallel settings before generation.",
        )
        self.parallel_card = SummaryCard("Parallelism", "num_proc = 1", "Used by generation and run_file batching.")
        self.summary_cards = [
            self.dataset_card,
            self.orbit_card,
            self.dem_card,
            self.source_card,
            self.bbox_card,
            self.iw_card,
            self.plan_card,
            self.parallel_card,
        ]
        for card in self.summary_cards:
            card.setParent(self.summary_card_container)
            card.hide()

    def _build_environment_and_sources(self) -> None:
        section = SectionPanel("Environment and Data Sources")
        grid = PropertyForm("Required Parameters", label_width=150)
        grid.set_row_heights(54, full_row_height=48)
        self.shell_init_row = PathPickerRow()
        self.conda_env_edit = QLineEdit()
        self.isce_root_row = PathPickerRow()
        self.isce_root_row.line_edit.setPlaceholderText("Processing runtime root or conda env prefix")
        self.input_path_row = PathPickerRow(compact=True)
        self.orbit_path_row = PathPickerRow(compact=True)
        self.dem_path_row = PathPickerRow(compact=True)
        self.dem_reference_combo = QComboBox()
        self.dem_reference_combo.addItem("Select GeoTIFF height reference", "")
        self.dem_reference_combo.addItem("EGM96 geoid -> convert to WGS84", "egm96")
        self.dem_reference_combo.addItem("EGM2008 geoid -> convert to WGS84", "egm2008")
        self.dem_reference_combo.addItem("Already WGS84 ellipsoid", "wgs84")
        self.aux_path_row = PathPickerRow(compact=True)
        self.work_dir_row = PathPickerRow(compact=True)
        self.extract_checkbox = QCheckBox("Extract ZIP files to SAFE before workflow generation")
        self.extract_dir_row = PathPickerRow(compact=True)
        self.runtime_summary_label = QLabel("")
        self.runtime_summary_label.setObjectName("runtimeSummaryLabel")
        self.runtime_summary_label.setWordWrap(True)
        self.runtime_summary_label.hide()
        grid.add_row("SLC folder", self.input_path_row)
        grid.add_row("EOF folder", self.orbit_path_row)
        grid.add_row("DEM path", self.dem_path_row)
        grid.add_row("Height ref", self.dem_reference_combo)
        grid.add_row("AUX folder", self.aux_path_row)
        grid.add_row("Work folder", self.work_dir_row)
        grid.add_full_row(self.extract_checkbox)
        grid.add_row("SAFE folder", self.extract_dir_row)
        self.parameter_grid = grid
        section.content_layout.addWidget(grid)

        actions = ActionBar()
        self.validate_env_button = QPushButton("Validate Environment")
        self.prepare_button = QPushButton("Validate and Prepare Data")
        self.inspect_button = QPushButton("Inspect Inputs")
        self.validate_env_button.setIcon(IconProvider.icon("check"))
        self.prepare_button.setIcon(IconProvider.icon("run"))
        self.inspect_button.setIcon(IconProvider.icon("search"))
        self.validate_env_button.setProperty("role", "secondary")
        self.prepare_button.setProperty("role", "primary")
        self.inspect_button.setProperty("role", "secondary")
        actions.layout.addWidget(self.validate_env_button)
        actions.layout.addWidget(self.prepare_button)
        actions.layout.addWidget(self.inspect_button)
        actions.layout.addStretch(1)
        section.content_layout.addWidget(actions)

        self.validation_text = QPlainTextEdit()
        self.validation_text.setReadOnly(True)
        self.validation_text.setPlaceholderText("Environment validation results will appear here.")
        self.inputs_text = QPlainTextEdit()
        self.inputs_text.setReadOnly(True)
        self.inputs_text.setPlaceholderText("Prepared input manifest, DEM, and AUX summary will appear here.")
        section.content_layout.addWidget(self.validation_text)
        section.content_layout.addWidget(self.inputs_text)
        self.extract_dir_row.setEnabled(False)
        self._add_workbench_widget(section)

    def _build_geometry_section(self) -> None:
        section = SectionPanel(
            "AOI / BBox / IW",
            "Confirm the final SNWE bbox and Sentinel-1 IW swaths passed to the processing runtime.",
        )
        form = PropertyForm("Geometry Parameters")
        self.aoi_file_row = PathPickerRow(secondary_label="Import AOI")
        self.use_common_overlap_check = QCheckBox("Use common overlap (allow empty bbox)")
        self.bbox_south_edit = self._line("e.g. 33.85")
        self.bbox_north_edit = self._line("e.g. 33.90")
        self.bbox_west_edit = self._line("e.g. -118.28")
        self.bbox_east_edit = self._line("e.g. -118.04")
        form.add_row("AOI file (KML/SHP)", self.aoi_file_row)
        form.add_full_row(self.use_common_overlap_check)
        form.add_row("South", self.bbox_south_edit)
        form.add_row("North", self.bbox_north_edit)
        form.add_row("West", self.bbox_west_edit)
        form.add_row("East", self.bbox_east_edit)
        self.geometry_parameter_grid = form
        section.content_layout.addWidget(form)

        swath_row = QHBoxLayout()
        swath_row.setSpacing(10)
        swath_row.addWidget(QLabel("IW swaths"))
        self.iw1_check = QCheckBox("IW1")
        self.iw2_check = QCheckBox("IW2")
        self.iw3_check = QCheckBox("IW3")
        for checkbox, object_name in (
            (self.iw1_check, "iw1Check"),
            (self.iw2_check, "iw2Check"),
            (self.iw3_check, "iw3Check"),
        ):
            checkbox.setObjectName(object_name)
            checkbox.setChecked(True)
            swath_row.addWidget(checkbox)
        swath_row.addStretch(1)
        section.content_layout.addLayout(swath_row)

        actions = ActionBar()
        self.recommend_iw_button = QPushButton("Recommend IW")
        self.verify_button = QPushButton("Verify Geometry")
        self.export_verify_button = QPushButton("Export Verify PNG")
        self.confirm_button = QPushButton("Confirm AOI/BBox/IW")
        self.recommend_iw_button.setIcon(IconProvider.icon("settings"))
        self.verify_button.setIcon(IconProvider.icon("preview"))
        self.export_verify_button.setIcon(IconProvider.icon("save"))
        self.confirm_button.setIcon(IconProvider.icon("check"))
        for button in (self.recommend_iw_button, self.verify_button, self.export_verify_button):
            button.setProperty("role", "secondary")
            actions.layout.addWidget(button)
        self.confirm_button.setProperty("role", "primary")
        actions.layout.addWidget(self.confirm_button)
        actions.layout.addStretch(1)
        section.content_layout.addWidget(actions)

        self.verify_panel = GeometryVerifyPanel()
        section.content_layout.addWidget(self.verify_panel)
        self.verify_alert_label = QLabel("")
        self.verify_alert_label.setStyleSheet("color: #b64646; font-weight: 700;")
        self.verify_alert_label.setWordWrap(True)
        self.verify_alert_label.hide()
        section.content_layout.addWidget(self.verify_alert_label)
        self.verify_notes = QPlainTextEdit()
        self.verify_notes.setReadOnly(True)
        self.verify_notes.setPlaceholderText(
            "AOI import, IW recommendation, and geometry verification notes will appear here."
        )
        section.content_layout.addWidget(self.verify_notes)
        self._add_workbench_widget(section)

    def _build_stack_section(self) -> None:
        section = SectionPanel("Processing Parameters", "Core processing parameters before generating the workflow.")
        form = PropertyForm("Processing Controls")
        self.workflow_combo = QComboBox()
        self.workflow_combo.addItems(["interferogram", "slc", "correlation", "offset"])
        self.coreg_combo = QComboBox()
        self.coreg_combo.addItems(["NESD", "geometry"])
        self.range_looks_spin = QSpinBox()
        self.range_looks_spin.setRange(1, 50)
        self.azimuth_looks_spin = QSpinBox()
        self.azimuth_looks_spin.setRange(1, 50)
        self.num_proc_spin = QSpinBox()
        self.num_proc_spin.setRange(1, 64)
        self.polarization_combo = QComboBox()
        self.polarization_combo.addItems(["vv", "vh"])
        self.reference_date_edit = QLineEdit()
        self.reference_date_edit.setPlaceholderText("YYYYMMDD (optional)")
        self.num_connections_spin = QSpinBox()
        self.num_connections_spin.setRange(1, 50)
        form.add_row("Workflow", self.workflow_combo)
        form.add_row("Coregistration", self.coreg_combo)
        form.add_row("Range looks", self.range_looks_spin)
        form.add_row("Azimuth looks", self.azimuth_looks_spin)
        form.add_row("Parallel tasks", self.num_proc_spin)
        form.add_row("Polarization", self.polarization_combo)
        form.add_row("Reference date", self.reference_date_edit)
        form.add_row("Connections", self.num_connections_spin)
        self.processing_parameter_grid = form
        section.content_layout.addWidget(form)
        self.reference_hint_label = QLabel("Leave empty to let the workflow choose the reference date.")
        self.reference_hint_label.setWordWrap(True)
        self.num_proc_hint = QLabel(
            "The GUI uses num_proc as the run_file subcommand concurrency cap. "
            "Each step may still contain fewer commands."
        )
        self.num_proc_hint.setWordWrap(True)
        section.content_layout.addWidget(self.reference_hint_label)
        section.content_layout.addWidget(self.num_proc_hint)
        self._add_workbench_widget(section)

    def _build_preflight_section(self) -> None:
        section = SectionPanel(
            "Preflight",
            "Check paths, permissions, prepared inputs, run_files/configs conflicts, "
            "and runtime capability before generation.",
        )
        self.preflight_alert = InlineAlert("Preflight refreshes before command preview or workflow generation.", "info")
        self.preflight_check_list = PreflightCheckList()
        self.preflight_text = self.preflight_check_list
        section.content_layout.addWidget(self.preflight_alert)
        section.content_layout.addWidget(self.preflight_check_list)
        self._add_workbench_widget(section)

    def _build_generation_section(self) -> None:
        section = SectionPanel("Workflow Generation", "Generate the executable workflow after preflight is clear.")
        actions = ActionBar()
        self.preview_command_button = QPushButton("Preview Command")
        self.rescan_button = QPushButton("Re-scan run_files")
        self.generate_button = QPushButton("Generate Workflow")
        self.preview_command_button.setIcon(IconProvider.icon("preview"))
        self.rescan_button.setIcon(IconProvider.icon("refresh"))
        self.generate_button.setIcon(IconProvider.icon("generate"))
        self.preview_command_button.setProperty("role", "secondary")
        self.rescan_button.setProperty("role", "secondary")
        self.generate_button.setProperty("role", "primary")
        actions.layout.addWidget(self.preview_command_button)
        actions.layout.addWidget(self.rescan_button)
        actions.layout.addWidget(self.generate_button)
        actions.layout.addStretch(1)
        section.content_layout.addWidget(actions)

        self.technical_details_panel = TechnicalDetailsPanel("Technical Details / Command Preview")
        self.runtime_diagnostics_text = QPlainTextEdit()
        self.runtime_diagnostics_text.setReadOnly(True)
        self.runtime_diagnostics_text.setPlaceholderText("Runtime diagnostics will appear here.")
        self.technical_details_panel.content_layout.addWidget(self.runtime_diagnostics_text)
        self.command_preview = CommandPreview()
        self.command_preview_text = self.command_preview
        self.technical_details_panel.content_layout.addWidget(self.command_preview)

        self.runfile_estimate_text = QPlainTextEdit()
        self.runfile_estimate_text.setReadOnly(True)
        self.runfile_estimate_text.setPlaceholderText(
            "Run-file command counts and parallelism estimates appear after generation."
        )
        self.technical_details_panel.content_layout.addWidget(self.runfile_estimate_text)
        section.content_layout.addWidget(self.technical_details_panel)
        self._add_workbench_widget(section)

    def _build_wizard_actions(self) -> None:
        self.wizard_action_bar = WizardActionBar()
        self.wizard_action_bar.run_button.setText("Generate")
        self.wizard_action_bar.next_button.setText("Preview >")
        self.wizard_action_bar.back_button.setEnabled(False)
        self.wizard_action_bar.cancel_button.setEnabled(False)
        self.wizard_action_bar.next_button.clicked.connect(self.preview_command_button.click)
        self.wizard_action_bar.run_button.clicked.connect(self.generate_button.click)
        self.content_layout.addWidget(self.wizard_action_bar)

    @staticmethod
    def _line(placeholder: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        return edit

    def selected_swaths(self) -> str:
        values = []
        if self.iw1_check.isChecked():
            values.append("1")
        if self.iw2_check.isChecked():
            values.append("2")
        if self.iw3_check.isChecked():
            values.append("3")
        return " ".join(values)

    def set_selected_swaths(self, text: str) -> None:
        tokens = set(text.split())
        self.iw1_check.setChecked("1" in tokens)
        self.iw2_check.setChecked("2" in tokens)
        self.iw3_check.setChecked("3" in tokens)

    def set_bbox_components(self, south: str, north: str, west: str, east: str) -> None:
        self.bbox_south_edit.setText(south)
        self.bbox_north_edit.setText(north)
        self.bbox_west_edit.setText(west)
        self.bbox_east_edit.setText(east)

    def bbox_components(self) -> tuple[str, str, str, str]:
        return (
            self.bbox_south_edit.text().strip(),
            self.bbox_north_edit.text().strip(),
            self.bbox_west_edit.text().strip(),
            self.bbox_east_edit.text().strip(),
        )

    def set_bbox_enabled(self, enabled: bool) -> None:
        self.bbox_south_edit.setEnabled(enabled)
        self.bbox_north_edit.setEnabled(enabled)
        self.bbox_west_edit.setEnabled(enabled)
        self.bbox_east_edit.setEnabled(enabled)
