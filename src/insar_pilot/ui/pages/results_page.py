"""Results and visualization page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.ui.widgets.collapsible_section import CollapsibleSection
from insar_pilot.ui.widgets.parameter_grid import ParameterGrid
from insar_pilot.ui.widgets.path_picker_row import PathPickerRow
from insar_pilot.ui.widgets.preview_panel import PreviewPanel
from insar_pilot.ui.widgets.summary_card import SummaryCard


class ResultsPage(QWidget):
    """Outputs browser, preview, and visualization experience."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.output_card = SummaryCard("Outputs", "Not scanned", "Browse processing outputs and quicklooks.", self)
        self.preview_card = SummaryCard("Preview", "Idle", "Generate SLC, interferogram, or overlay quicklooks.", self)
        self.output_card.hide()
        self.preview_card.hide()

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        self.outputs_tree = QTreeWidget()
        self.outputs_tree.setHeaderLabels(["Name", "Kind", "Path"])
        left_layout.addWidget(self.outputs_tree, 1)
        self.empty_outputs_label = QLabel(
            "No outputs discovered yet. Run preparation and workflow steps, then click 'Refresh Outputs'."
        )
        self.empty_outputs_label.setProperty("emptyState", True)
        self.empty_outputs_label.setWordWrap(True)
        left_layout.addWidget(self.empty_outputs_label)
        self.refresh_outputs_button = QPushButton("Refresh Outputs")
        self.refresh_outputs_button.setProperty("role", "secondary")
        left_layout.addWidget(self.refresh_outputs_button)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        self.preview_panel = PreviewPanel()
        right_layout.addWidget(self.preview_panel, 1)

        self.visual_section = CollapsibleSection("Visualization Controls", expanded=True)
        visual_form = ParameterGrid("Visualization Parameters")
        self.visual_mode_combo = QComboBox()
        self.visual_mode_combo.addItem("SLC", "slc")
        self.visual_mode_combo.addItem("Interferogram", "interferogram")
        self.visual_mode_combo.addItem("SLC Background + INT Phase Overlay", "overlay")
        self.visual_primary_row = PathPickerRow(secondary_label="Use Selected Output")
        self.visual_secondary_row = PathPickerRow(secondary_label="Use Selected Output")
        self.visual_export_dir_row = PathPickerRow(secondary_label=None)
        self.visual_range_looks_spin = QSpinBox()
        self.visual_range_looks_spin.setRange(1, 100)
        self.visual_range_looks_spin.setValue(1)
        self.visual_azimuth_looks_spin = QSpinBox()
        self.visual_azimuth_looks_spin.setRange(1, 100)
        self.visual_azimuth_looks_spin.setValue(1)
        self.visual_overlay_brightness_spin = QDoubleSpinBox()
        self.visual_overlay_brightness_spin.setRange(0.05, 5.0)
        self.visual_overlay_brightness_spin.setDecimals(2)
        self.visual_overlay_brightness_spin.setSingleStep(0.05)
        self.visual_overlay_brightness_spin.setValue(0.5)
        visual_form.add_row("Mode", self.visual_mode_combo)
        visual_form.add_row("Primary input", self.visual_primary_row)
        self._secondary_label = visual_form.add_row("Secondary input", self.visual_secondary_row)
        visual_form.add_row("Export directory", self.visual_export_dir_row)
        visual_form.add_row("Range looks (rlks)", self.visual_range_looks_spin)
        visual_form.add_row("Azimuth looks (alks)", self.visual_azimuth_looks_spin)
        self._brightness_label = visual_form.add_row("Overlay brightness", self.visual_overlay_brightness_spin)
        self.visual_parameter_grid = visual_form
        self.visual_section.content_layout.addWidget(visual_form)

        actions = QHBoxLayout()
        self.visual_preview_button = QPushButton("Preview")
        self.visual_export_button = QPushButton("Export BMP")
        self.visual_preview_button.setProperty("role", "primary")
        self.visual_export_button.setProperty("role", "secondary")
        actions.addWidget(self.visual_preview_button)
        actions.addWidget(self.visual_export_button)
        actions.addStretch(1)
        self.visual_section.content_layout.addLayout(actions)

        self.visual_status_text = QPlainTextEdit()
        self.visual_status_text.setReadOnly(True)
        self.visual_status_text.setPlaceholderText("Visualization logs and metadata will appear here.")
        self.visual_section.content_layout.addWidget(self.visual_status_text)
        right_layout.addWidget(self.visual_section)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    def set_overlay_fields_visible(self, visible: bool) -> None:
        """Show or hide overlay-only controls together with their labels."""

        self.visual_secondary_row.setVisible(visible)
        if self._secondary_label is not None:
            self._secondary_label.setVisible(visible)
        self.visual_overlay_brightness_spin.setVisible(visible)
        if self._brightness_label is not None:
            self._brightness_label.setVisible(visible)
