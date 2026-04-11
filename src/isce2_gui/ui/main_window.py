"""Main application window."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QToolBar,
    QToolBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
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
from isce2_gui.services.env_probe import EnvironmentProbe
from isce2_gui.services.command_plan import CommandPlan
from isce2_gui.services.dem_preparer import DemPreparationService
from isce2_gui.services.input_catalog import InputCatalogReport, InputCatalogService
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


class MainWindow(QMainWindow):
    """Minimal but usable Milestone 1 desktop GUI."""

    def __init__(self, project: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.project_store = ProjectStore()
        self.environment_probe = EnvironmentProbe()
        self.dem_preparation_service = DemPreparationService()
        self.input_catalog_service = InputCatalogService()
        self.workflow_service = StackWorkflowService()
        self.output_discovery_service = OutputDiscoveryService()
        self.visualization_service = VisualizationService()
        self.runner = ProcessRunner(project.environment, self)
        self._last_catalog_report: InputCatalogReport | None = None
        self._pending_preparation: dict[str, object] | None = None
        self._pending_visualization: VisualizationBuildResult | None = None
        self._last_visualization_saved_status: ProjectStatus | None = None
        self._stop_requested = False

        self.setWindowTitle("ISCE2 Sentinel-1 GUI")
        self.resize(1440, 900)

        self._build_ui()
        self._connect_runner()
        self._populate_form_from_project()
        self.refresh_steps_view()
        self.refresh_outputs_view()
        self.refresh_status_labels()

    def _build_ui(self) -> None:
        self._build_toolbar()

        central = QWidget(self)
        root_layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Orientation.Horizontal, central)
        root_layout.addWidget(splitter)
        self.setCentralWidget(central)

        left_panel = QWidget(splitter)
        left_layout = QVBoxLayout(left_panel)
        self.toolbox = QToolBox(left_panel)
        left_layout.addWidget(self.toolbox)
        splitter.addWidget(left_panel)

        right_tabs = QTabWidget(splitter)
        splitter.addWidget(right_tabs)
        splitter.setStretchFactor(1, 2)

        self._build_environment_page()
        self._build_inputs_page()
        self._build_execution_page()
        self._build_visualization_page()

        self.steps_tree = QTreeWidget()
        self.steps_tree.setHeaderLabels(["Step", "Status", "Exit", "Log", "Message"])
        self.steps_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.steps_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.steps_tree.customContextMenuRequested.connect(self._open_steps_context_menu)
        self.steps_tree.itemSelectionChanged.connect(self._update_action_states)
        right_tabs.addTab(self.steps_tree, "Steps")

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        right_tabs.addTab(self.log_view, "Logs")

        self.outputs_tree = QTreeWidget()
        self.outputs_tree.setHeaderLabels(["Name", "Kind", "Path"])
        right_tabs.addTab(self.outputs_tree, "Outputs")

        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        self.preview_image_label = QLabel("No preview generated yet.")
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.preview_image_label.setMinimumSize(480, 320)
        self.preview_image_label.setScaledContents(False)
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(False)
        self.preview_scroll.setWidget(self.preview_image_label)
        preview_layout.addWidget(self.preview_scroll)
        self.preview_meta_text = QPlainTextEdit()
        self.preview_meta_text.setReadOnly(True)
        preview_layout.addWidget(self.preview_meta_text)
        right_tabs.addTab(preview_tab, "Preview")

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Project", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_button = QPushButton("New Project")
        new_button.clicked.connect(self.new_project)
        toolbar.addWidget(new_button)

        open_button = QPushButton("Open Project")
        open_button.clicked.connect(self.open_project)
        toolbar.addWidget(open_button)

        save_button = QPushButton("Save Project")
        save_button.clicked.connect(self.save_project)
        toolbar.addWidget(save_button)

    def _build_environment_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox("Environment")
        form = QFormLayout(group)
        self.shell_init_edit = QLineEdit()
        self.conda_env_edit = QLineEdit()
        self.isce_root_edit = QLineEdit()

        form.addRow("Shell init", self._path_field(self.shell_init_edit, self._browse_shell_init))
        form.addRow("Conda env", self.conda_env_edit)
        form.addRow("ISCE2 root", self._path_field(self.isce_root_edit, self._browse_isce_root))
        layout.addWidget(group)

        button_row = QHBoxLayout()
        self.validate_button = QPushButton("Validate Environment")
        self.validate_button.clicked.connect(self.validate_environment)
        button_row.addWidget(self.validate_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.validation_text = QPlainTextEdit()
        self.validation_text.setReadOnly(True)
        layout.addWidget(self.validation_text)

        self.toolbox.addItem(page, "1. Environment")

    def _build_inputs_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        source_group = QGroupBox("Data Precheck (SLC / Orbit / DEM)")
        source_form = QFormLayout(source_group)
        self.input_path_edit = QLineEdit()
        self.orbit_path_edit = QLineEdit()
        self.dem_path_edit = QLineEdit()
        self.dem_reference_combo = QComboBox()
        self.dem_reference_combo.addItem("Select for GeoTIFF DEM", "")
        self.dem_reference_combo.addItem("EGM96 geoid -> convert to WGS84", "egm96")
        self.dem_reference_combo.addItem("Already WGS84 ellipsoid", "wgs84")
        self.aux_path_edit = QLineEdit()
        self.work_dir_edit = QLineEdit()
        self.extract_checkbox = QCheckBox("Extract ZIP files to SAFE before workflow generation")
        self.extract_checkbox.toggled.connect(self._toggle_extract_widgets)
        self.extract_dir_edit = QLineEdit()

        source_form.addRow("Sentinel-1 input folder", self._path_field(self.input_path_edit, self._browse_input_dir))
        source_form.addRow("Orbit folder", self._path_field(self.orbit_path_edit, self._browse_orbit_dir))
        source_form.addRow("DEM path", self._path_field(self.dem_path_edit, self._browse_dem_file))
        source_form.addRow("GeoTIFF height ref", self.dem_reference_combo)
        source_form.addRow("AUX folder", self._path_field(self.aux_path_edit, self._browse_aux_dir))
        source_form.addRow("Working directory", self._path_field(self.work_dir_edit, self._browse_work_dir))
        source_form.addRow("", self.extract_checkbox)
        source_form.addRow("Extracted SAFE dir", self._path_field(self.extract_dir_edit, self._browse_extract_dir))
        layout.addWidget(source_group)

        processing_group = QGroupBox("Processing Plan")
        processing_form = QFormLayout(processing_group)
        self.bbox_south_edit = QLineEdit()
        self.bbox_north_edit = QLineEdit()
        self.bbox_west_edit = QLineEdit()
        self.bbox_east_edit = QLineEdit()
        self.bbox_south_edit.setPlaceholderText("e.g. 33.68")
        self.bbox_north_edit.setPlaceholderText("e.g. 34.03")
        self.bbox_west_edit.setPlaceholderText("e.g. -118.48")
        self.bbox_east_edit.setPlaceholderText("e.g. -117.99")
        self.bbox_hint = QLabel("Leave all four bbox fields empty to use stack common overlap.")
        self.workflow_combo = QComboBox()
        self.workflow_combo.addItems(["interferogram", "slc", "correlation", "offset"])
        self.coreg_combo = QComboBox()
        self.coreg_combo.addItems(["NESD", "geometry"])
        self.num_connections_spin = QSpinBox()
        self.num_connections_spin.setRange(1, 50)
        self.azimuth_looks_spin = QSpinBox()
        self.azimuth_looks_spin.setRange(1, 50)
        self.range_looks_spin = QSpinBox()
        self.range_looks_spin.setRange(1, 50)
        self.num_proc_spin = QSpinBox()
        self.num_proc_spin.setRange(1, 64)
        self.num_proc_spin.valueChanged.connect(lambda _: self._refresh_runfile_estimates())
        self.num_proc_hint = QLabel(
            "Used by stackSentinel and run_file subcommand concurrency limit. "
            "It does not guarantee each step uses exactly this many tasks."
        )
        self.num_proc_hint.setWordWrap(True)
        self.swath_edit = QLineEdit()
        self.polarization_combo = QComboBox()
        self.polarization_combo.addItems(["vv", "vh"])
        self.reference_date_edit = QLineEdit()

        processing_form.addRow("BBox South", self.bbox_south_edit)
        processing_form.addRow("BBox North", self.bbox_north_edit)
        processing_form.addRow("BBox West", self.bbox_west_edit)
        processing_form.addRow("BBox East", self.bbox_east_edit)
        processing_form.addRow("", self.bbox_hint)
        processing_form.addRow("Workflow", self.workflow_combo)
        processing_form.addRow("Coregistration", self.coreg_combo)
        processing_form.addRow("Connections", self.num_connections_spin)
        processing_form.addRow("Azimuth looks", self.azimuth_looks_spin)
        processing_form.addRow("Range looks", self.range_looks_spin)
        processing_form.addRow("ISCE parallel tasks (--num_proc)", self.num_proc_spin)
        processing_form.addRow("", self.num_proc_hint)
        processing_form.addRow("Swaths", self.swath_edit)
        processing_form.addRow("Polarization", self.polarization_combo)
        processing_form.addRow("Reference date", self.reference_date_edit)
        layout.addWidget(processing_group)

        input_buttons = QHBoxLayout()
        self.prepare_data_button = QPushButton("Validate & Prepare Data")
        self.prepare_data_button.clicked.connect(self.prepare_data_sources)
        input_buttons.addWidget(self.prepare_data_button)
        self.inspect_inputs_button = QPushButton("Inspect Inputs")
        self.inspect_inputs_button.clicked.connect(self.inspect_inputs)
        input_buttons.addWidget(self.inspect_inputs_button)
        input_buttons.addStretch(1)
        layout.addLayout(input_buttons)

        self.inputs_text = QPlainTextEdit()
        self.inputs_text.setReadOnly(True)
        layout.addWidget(self.inputs_text)

        self.toolbox.addItem(page, "2. Inputs")

    def _build_execution_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        status_group = QGroupBox("Execution Status")
        status_layout = QFormLayout(status_group)
        self.project_status_value = QLabel("-")
        self.current_step_value = QLabel("-")
        self.work_dir_value = QLabel("-")
        status_layout.addRow("Project status", self.project_status_value)
        status_layout.addRow("Current step", self.current_step_value)
        status_layout.addRow("Resolved work dir", self.work_dir_value)
        layout.addWidget(status_group)

        button_grid = QGridLayout()
        self.generate_button = QPushButton("Generate Workflow")
        self.generate_button.clicked.connect(self.generate_workflow)
        self.run_next_button = QPushButton("Run Next Step")
        self.run_next_button.clicked.connect(self.run_next_step)
        self.run_selected_button = QPushButton("Run Selected Step")
        self.run_selected_button.clicked.connect(self.run_selected_step)
        self.run_all_button = QPushButton("Run Remaining Steps")
        self.run_all_button.clicked.connect(self.run_remaining_steps)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_execution)
        self.refresh_outputs_button = QPushButton("Refresh Outputs")
        self.refresh_outputs_button.clicked.connect(self.refresh_outputs_view)

        button_grid.addWidget(self.generate_button, 0, 0)
        button_grid.addWidget(self.run_next_button, 0, 1)
        button_grid.addWidget(self.run_selected_button, 1, 0)
        button_grid.addWidget(self.run_all_button, 1, 1)
        button_grid.addWidget(self.stop_button, 2, 0)
        button_grid.addWidget(self.refresh_outputs_button, 2, 1)
        layout.addLayout(button_grid)
        self.runfile_estimate_text = QPlainTextEdit()
        self.runfile_estimate_text.setReadOnly(True)
        self.runfile_estimate_text.setPlaceholderText(
            "Run-file command estimates appear here after workflow generation."
        )
        layout.addWidget(self.runfile_estimate_text)
        layout.addStretch(1)

        self.toolbox.addItem(page, "3. Execute")

    def _build_visualization_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        mode_group = QGroupBox("Visualization Mode")
        mode_form = QFormLayout(mode_group)
        self.visual_mode_combo = QComboBox()
        self.visual_mode_combo.addItem("SLC", "slc")
        self.visual_mode_combo.addItem("Interferogram", "interferogram")
        self.visual_mode_combo.addItem("SLC Background + INT Phase Overlay", "overlay")
        self.visual_mode_combo.currentIndexChanged.connect(self._update_visualization_mode_ui)
        mode_form.addRow("Mode", self.visual_mode_combo)
        layout.addWidget(mode_group)

        inputs_group = QGroupBox("Inputs")
        inputs_form = QFormLayout(inputs_group)
        self.visual_primary_path_edit = QLineEdit()
        self.visual_secondary_path_edit = QLineEdit()
        self.visual_primary_browse_button = QPushButton("Browse")
        self.visual_primary_browse_button.clicked.connect(self._browse_visual_primary)
        self.visual_primary_from_outputs_button = QPushButton("Use Selected Output")
        self.visual_primary_from_outputs_button.clicked.connect(self._fill_visual_primary_from_outputs)
        self.visual_secondary_browse_button = QPushButton("Browse")
        self.visual_secondary_browse_button.clicked.connect(self._browse_visual_secondary)
        self.visual_secondary_from_outputs_button = QPushButton("Use Selected Output")
        self.visual_secondary_from_outputs_button.clicked.connect(self._fill_visual_secondary_from_outputs)
        self.visual_export_dir_edit = QLineEdit()
        self.visual_export_dir_browse_button = QPushButton("Browse")
        self.visual_export_dir_browse_button.clicked.connect(self._browse_visual_export_dir)

        self.visual_primary_row_widget = self._visual_path_field(
            self.visual_primary_path_edit,
            self.visual_primary_browse_button,
            self.visual_primary_from_outputs_button,
        )
        self.visual_secondary_row_widget = self._visual_path_field(
            self.visual_secondary_path_edit,
            self.visual_secondary_browse_button,
            self.visual_secondary_from_outputs_button,
        )
        self.visual_export_dir_row_widget = self._visual_path_field(
            self.visual_export_dir_edit,
            self.visual_export_dir_browse_button,
            None,
        )
        inputs_form.addRow("Primary input", self.visual_primary_row_widget)
        inputs_form.addRow("Secondary input", self.visual_secondary_row_widget)
        inputs_form.addRow("Export directory", self.visual_export_dir_row_widget)
        layout.addWidget(inputs_group)

        params_group = QGroupBox("Render Parameters")
        params_form = QFormLayout(params_group)
        self.visual_range_looks_spin = QSpinBox()
        self.visual_range_looks_spin.setRange(1, 100)
        self.visual_azimuth_looks_spin = QSpinBox()
        self.visual_azimuth_looks_spin.setRange(1, 100)
        self.visual_overlay_brightness_spin = QDoubleSpinBox()
        self.visual_overlay_brightness_spin.setRange(0.05, 5.0)
        self.visual_overlay_brightness_spin.setDecimals(2)
        self.visual_overlay_brightness_spin.setSingleStep(0.05)
        self.visual_overlay_brightness_spin.setValue(0.5)
        params_form.addRow("Range looks (rlks)", self.visual_range_looks_spin)
        params_form.addRow("Azimuth looks (alks)", self.visual_azimuth_looks_spin)
        params_form.addRow("Overlay brightness", self.visual_overlay_brightness_spin)
        layout.addWidget(params_group)

        button_row = QHBoxLayout()
        self.visual_preview_button = QPushButton("Preview")
        self.visual_preview_button.clicked.connect(self.run_visualization_preview)
        self.visual_export_button = QPushButton("Export BMP")
        self.visual_export_button.clicked.connect(self.run_visualization_export)
        self.visual_refresh_outputs_button = QPushButton("Refresh Outputs")
        self.visual_refresh_outputs_button.clicked.connect(self.refresh_outputs_view)
        button_row.addWidget(self.visual_preview_button)
        button_row.addWidget(self.visual_export_button)
        button_row.addWidget(self.visual_refresh_outputs_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.visual_status_text = QPlainTextEdit()
        self.visual_status_text.setReadOnly(True)
        self.visual_status_text.setPlaceholderText("Visualization logs and metadata will appear here.")
        layout.addWidget(self.visual_status_text)

        self.toolbox.addItem(page, "4. Visualize")

    def _connect_runner(self) -> None:
        self.runner.log_emitted.connect(self.append_log)
        self.runner.command_started.connect(self._handle_command_started)
        self.runner.command_finished.connect(self._handle_command_finished)
        self.runner.queue_finished.connect(self._handle_queue_finished)
        self.runner.runner_state_changed.connect(self._handle_runner_state_changed)

    def _path_field(self, edit: QLineEdit, browse_callback) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit)
        button = QPushButton("Browse")
        button.clicked.connect(browse_callback)
        layout.addWidget(button)
        return widget

    def _visual_path_field(
        self,
        edit: QLineEdit,
        browse_button: QPushButton,
        outputs_button: QPushButton | None,
    ) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit)
        layout.addWidget(browse_button)
        if outputs_button is not None:
            layout.addWidget(outputs_button)
        return widget

    def _toggle_extract_widgets(self, checked: bool) -> None:
        self.extract_dir_edit.setEnabled(checked)

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

    def _browse_visual_primary(self) -> None:
        self._browse_file_into(self.visual_primary_path_edit, "Select primary visualization input")

    def _browse_visual_secondary(self) -> None:
        self._browse_file_into(self.visual_secondary_path_edit, "Select secondary visualization input")

    def _browse_visual_export_dir(self) -> None:
        self._browse_dir_into(self.visual_export_dir_edit, "Select visualization export directory")

    def _fill_visual_primary_from_outputs(self) -> None:
        selected = self._selected_output_file_path()
        if selected is None:
            QMessageBox.warning(self, "No output file selected", "Select a file in Outputs tab first.")
            return
        self.visual_primary_path_edit.setText(selected)

    def _fill_visual_secondary_from_outputs(self) -> None:
        selected = self._selected_output_file_path()
        if selected is None:
            QMessageBox.warning(self, "No output file selected", "Select a file in Outputs tab first.")
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

    def _browse_dir_into(self, edit: QLineEdit, title: str) -> None:
        path = QFileDialog.getExistingDirectory(self, title, edit.text() or str(Path.home()))
        if path:
            edit.setText(path)

    def _browse_file_into(self, edit: QLineEdit, title: str) -> None:
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
        try:
            south, north, west, east = self.project.workflow.bbox_components()
        except ValueError:
            south, north, west, east = "", "", "", ""
        self.bbox_south_edit.setText(south)
        self.bbox_north_edit.setText(north)
        self.bbox_west_edit.setText(west)
        self.bbox_east_edit.setText(east)
        self.workflow_combo.setCurrentText(self.project.workflow.workflow)
        self.coreg_combo.setCurrentText(self.project.workflow.coregistration)
        self.num_connections_spin.setValue(self.project.workflow.num_connections)
        self.azimuth_looks_spin.setValue(self.project.workflow.azimuth_looks)
        self.range_looks_spin.setValue(self.project.workflow.range_looks)
        self.num_proc_spin.setValue(self.project.workflow.num_proc)
        self.swath_edit.setText(self.project.workflow.swath_numbers)
        self.polarization_combo.setCurrentText(self.project.workflow.polarization)
        self.reference_date_edit.setText(self.project.workflow.reference_date)

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
        self._render_preparation_summary()
        self._refresh_runfile_estimates()
        self._update_action_states()

    def _update_project_from_form(self) -> None:
        previous_signature = self.project.state.prepared_signature
        self.project.environment = EnvironmentConfig(
            shell_init_path=self.shell_init_edit.text().strip(),
            conda_env_name=self.conda_env_edit.text().strip(),
            isce_root=self.isce_root_edit.text().strip(),
        )
        bbox_parts = [
            self.bbox_south_edit.text().strip(),
            self.bbox_north_edit.text().strip(),
            self.bbox_west_edit.text().strip(),
            self.bbox_east_edit.text().strip(),
        ]
        bbox_snwe = ""
        if any(bbox_parts):
            bbox_snwe = " ".join(part for part in bbox_parts if part)

        self.project.workflow = WorkflowConfig(
            input_path=self.input_path_edit.text().strip(),
            orbit_path=self.orbit_path_edit.text().strip(),
            dem_path=self.dem_path_edit.text().strip(),
            dem_height_reference=str(self.dem_reference_combo.currentData() or ""),
            aux_path=self.aux_path_edit.text().strip(),
            work_dir=self.work_dir_edit.text().strip(),
            bbox_snwe=bbox_snwe,
            extract_zips=self.extract_checkbox.isChecked(),
            extract_dir=self.extract_dir_edit.text().strip(),
            workflow=self.workflow_combo.currentText(),
            coregistration=self.coreg_combo.currentText(),
            num_connections=self.num_connections_spin.value(),
            azimuth_looks=self.azimuth_looks_spin.value(),
            range_looks=self.range_looks_spin.value(),
            swath_numbers=self.swath_edit.text().strip() or "1 2 3",
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

    def _render_preparation_summary(self) -> None:
        prepared = self.project.state.prepared_inputs
        if not prepared.entries:
            self.inputs_text.setPlainText("Data has not been prepared yet.")
            return

        lines: list[str] = []
        lines.extend(prepared.notes)
        if self.project.state.prepared_dem_path:
            lines.extend(["", f"Prepared DEM: {self.project.state.prepared_dem_path}"])
        lines.extend(["", "Prepared inputs:"])
        lines.extend(f"- {entry.path}" for entry in prepared.entries)
        self.inputs_text.setPlainText("\n".join(lines))

    def _commit_preparation_result(self, prepared: PreparedInputs, dem_path: str, signature: str) -> None:
        self.project.state.prepared_inputs = prepared
        self.project.state.prepared_dem_path = dem_path
        self.project.state.prepared_signature = signature
        self.project.state.last_error = ""
        self.project.state.status = ProjectStatus.READY
        self.project.state.current_step = "data preparation"
        self.project_store.save(self.project)
        self._render_preparation_summary()
        self.refresh_status_labels()
        self._update_action_states()

    def _update_action_states(self) -> None:
        busy = self.runner.is_running()
        has_selected_step = self._selected_step() is not None
        self.generate_button.setEnabled((not busy) and self._is_prepared_for_current_sources())
        self.run_next_button.setEnabled(not busy)
        self.run_selected_button.setEnabled((not busy) and has_selected_step)
        self.run_all_button.setEnabled(not busy)
        self.validate_button.setEnabled(not busy)
        self.inspect_inputs_button.setEnabled(not busy)
        self.prepare_data_button.setEnabled(not busy)
        self.stop_button.setEnabled(busy)
        self.visual_preview_button.setEnabled(not busy)
        self.visual_export_button.setEnabled(not busy)
        self.visual_primary_browse_button.setEnabled(not busy)
        self.visual_secondary_browse_button.setEnabled(not busy)
        self.visual_primary_from_outputs_button.setEnabled(not busy)
        self.visual_secondary_from_outputs_button.setEnabled(not busy)
        self.visual_export_dir_browse_button.setEnabled(not busy)

    def refresh_status_labels(self) -> None:
        self.project_status_value.setText(self.project.state.status.value)
        self.current_step_value.setText(self.project.state.current_step or "-")
        try:
            self.work_dir_value.setText(str(self.project.resolved_work_dir()))
        except ValueError:
            self.work_dir_value.setText("-")

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
        self.statusBar().showMessage("Input inspection finished.", 5000)

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
        self._populate_form_from_project()
        self.refresh_steps_view()
        self.refresh_outputs_view()
        self.refresh_status_labels()
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
        self._populate_form_from_project()
        self.refresh_steps_view()
        self.refresh_outputs_view()
        self.refresh_status_labels()
        self._refresh_runfile_estimates()

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

    def run_next_step(self) -> None:
        self._update_project_from_form()
        step = self.workflow_service.next_runnable_step(self.project)
        if step is None:
            QMessageBox.information(self, "No runnable steps", "There are no remaining run files to execute.")
            return
        self._run_steps([step])

    def run_selected_step(self) -> None:
        self._update_project_from_form()
        step = self._selected_step()
        if step is None:
            QMessageBox.information(
                self,
                "No step selected",
                "Select a run step in the Steps tab, then click 'Run Selected Step'.",
            )
            return
        if not step.path:
            self._show_error("Invalid step", f"{step.name} does not have a valid run file path.")
            return
        if not Path(step.path).expanduser().exists():
            self._show_error("Run file missing", f"Run file was not found for {step.name}:\n{step.path}")
            return

        self.statusBar().showMessage(
            "Running selected step only. Downstream step statuses are left unchanged.",
            7000,
        )
        self._run_steps([step])

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
        self._set_form_row_visible(self.visual_secondary_row_widget, is_overlay)
        self._set_form_row_visible(self.visual_overlay_brightness_spin, is_overlay)
        if mode == "slc":
            self.visual_primary_path_edit.setPlaceholderText(
                "Select .slc/.slc.vrt/.slc.full.vrt or a file with sibling .xml"
            )
        elif mode == "interferogram":
            self.visual_primary_path_edit.setPlaceholderText(
                "Select .int/.int.vrt/.int.full.vrt or a file with sibling .xml"
            )
        else:
            self.visual_primary_path_edit.setPlaceholderText(
                "Select SLC input (.slc/.vrt/.xml)"
            )
            self.visual_secondary_path_edit.setPlaceholderText(
                "Select interferogram input (.int/.vrt/.xml)"
            )

    @staticmethod
    def _set_form_row_visible(widget: QWidget, visible: bool) -> None:
        parent = widget.parentWidget()
        if parent is None:
            return
        form = parent.layout()
        if not isinstance(form, QFormLayout):
            return
        for row in range(form.rowCount()):
            row_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if row_item is None:
                continue
            if row_item.widget() is widget:
                label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                if label_item is not None and label_item.widget() is not None:
                    label_item.widget().setVisible(visible)
                widget.setVisible(visible)
                return

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
        if not preview_path.exists():
            return False
        if not preview_path.is_file():
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

    def _run_visualization(
        self,
        request: VisualizationRequest,
        *,
        action: str,
        render_signature: str,
    ) -> None:
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
        self._refresh_runfile_estimates()
        self._update_action_states()

    def refresh_outputs_view(self) -> None:
        self.outputs_tree.clear()
        try:
            work_dir = self.project.resolved_work_dir()
        except ValueError:
            return
        if not work_dir.exists():
            return

        for node in self.output_discovery_service.discover(work_dir):
            self.outputs_tree.addTopLevelItem(self._output_item(node))
        self.outputs_tree.expandToDepth(1)

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

    def _validate_data_source_inputs(self) -> list[str]:
        errors: list[str] = []
        workflow = self.project.workflow

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

        try:
            workflow.normalized_bbox()
        except ValueError as exc:
            errors.append(str(exc))

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

    def _selected_step(self) -> RunStep | None:
        if not hasattr(self, "steps_tree"):
            return None
        step_item = self._step_item_from_item(self.steps_tree.currentItem())
        if step_item is None:
            return None
        step_name = str(step_item.data(0, Qt.ItemDataRole.UserRole) or step_item.text(0)).strip()
        if not step_name:
            return None
        return self._find_step(step_name)

    def _open_steps_context_menu(self, pos) -> None:
        item = self.steps_tree.itemAt(pos)
        step_item = self._step_item_from_item(item)
        if step_item is None:
            return

        self.steps_tree.setCurrentItem(step_item)
        menu = QMenu(self)
        run_action = menu.addAction("Run Selected Step")
        run_action.setEnabled((not self.runner.is_running()) and self._selected_step() is not None)
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
        if not hasattr(self, "runfile_estimate_text"):
            return
        if not self.project.state.steps:
            self.runfile_estimate_text.setPlainText(
                "Generate workflow first. Run-file command estimates will appear here."
            )
            return

        current_parallel = max(1, self.project.workflow.num_proc)
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
        self.runfile_estimate_text.setPlainText("\n".join(lines))

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
