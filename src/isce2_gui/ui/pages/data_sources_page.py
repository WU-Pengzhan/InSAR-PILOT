"""Data Sources page for practitioner-oriented workflow."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from isce2_gui.ui.widgets.collapsible_section import CollapsibleSection
from isce2_gui.ui.widgets.path_picker_row import PathPickerRow
from isce2_gui.ui.widgets.summary_card import SummaryCard


class DataSourcesPage(QWidget):
    """Collect runtime and local source inputs before downstream planning."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self.dataset_card = SummaryCard("Dataset", "Not prepared", "Select a folder with Sentinel-1 ZIP/SAFE inputs.")
        self.orbit_card = SummaryCard("Orbit", "Not set", "Point to local EOF orbit files.")
        self.dem_card = SummaryCard("DEM", "Not set", "GeoTIFF or native ISCE DEM path.")
        cards_row.addWidget(self.dataset_card, 1)
        cards_row.addWidget(self.orbit_card, 1)
        cards_row.addWidget(self.dem_card, 1)
        layout.addLayout(cards_row)

        self.environment_section = CollapsibleSection("Environment & Runtime", expanded=False)
        env_form = QFormLayout()
        env_form.setContentsMargins(0, 0, 0, 0)
        env_form.setSpacing(10)
        env_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.shell_init_row = PathPickerRow()
        self.conda_env_edit = QLineEdit()
        self.isce_root_row = PathPickerRow()
        env_form.addRow("Shell init", self.shell_init_row)
        env_form.addRow("Conda env", self.conda_env_edit)
        env_form.addRow("ISCE2 root", self.isce_root_row)
        self.environment_section.content_layout.addLayout(env_form)
        layout.addWidget(self.environment_section)

        source_form = QFormLayout()
        source_form.setSpacing(10)
        source_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.input_path_row = PathPickerRow()
        self.orbit_path_row = PathPickerRow()
        self.dem_path_row = PathPickerRow()
        self.dem_reference_combo = QComboBox()
        self.dem_reference_combo.addItem("Select for GeoTIFF DEM", "")
        self.dem_reference_combo.addItem("EGM96 geoid -> convert to WGS84", "egm96")
        self.dem_reference_combo.addItem("Already WGS84 ellipsoid", "wgs84")
        self.aux_path_row = PathPickerRow()
        self.work_dir_row = PathPickerRow()
        self.extract_checkbox = QCheckBox("Extract ZIP files to SAFE before workflow generation")
        self.extract_dir_row = PathPickerRow()
        source_form.addRow("Sentinel-1 input folder", self.input_path_row)
        source_form.addRow("Orbit folder", self.orbit_path_row)
        source_form.addRow("DEM path", self.dem_path_row)
        source_form.addRow("GeoTIFF height ref", self.dem_reference_combo)
        source_form.addRow("AUX folder", self.aux_path_row)
        source_form.addRow("Working directory", self.work_dir_row)
        source_form.addRow("", self.extract_checkbox)
        source_form.addRow("Extracted SAFE dir", self.extract_dir_row)
        layout.addLayout(source_form)

        actions = QHBoxLayout()
        self.validate_env_button = QPushButton("Validate Environment")
        self.prepare_button = QPushButton("Validate Prepare Data")
        self.inspect_button = QPushButton("Inspect Inputs")
        self.validate_env_button.setProperty("role", "secondary")
        self.prepare_button.setProperty("role", "primary")
        self.inspect_button.setProperty("role", "secondary")
        actions.addWidget(self.validate_env_button)
        actions.addWidget(self.prepare_button)
        actions.addWidget(self.inspect_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.validation_text = QPlainTextEdit()
        self.validation_text.setReadOnly(True)
        self.validation_text.setPlaceholderText("Environment validation results will appear here.")
        layout.addWidget(self.validation_text)

        self.inputs_text = QPlainTextEdit()
        self.inputs_text.setReadOnly(True)
        self.inputs_text.setPlaceholderText("Prepared input and DEM summary will appear here.")
        layout.addWidget(self.inputs_text, 1)

        self.extract_dir_row.setEnabled(False)
