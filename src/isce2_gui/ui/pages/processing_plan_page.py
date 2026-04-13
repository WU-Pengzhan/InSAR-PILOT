"""Processing plan page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from isce2_gui.ui.widgets.collapsible_section import CollapsibleSection
from isce2_gui.ui.widgets.summary_card import SummaryCard


class ProcessingPlanPage(QWidget):
    """Workflow planning before generation."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.plan_card = SummaryCard("Processing Plan", "Not generated", "Review workflow and advanced controls before generation.")
        self.parallel_card = SummaryCard("Parallelism", "num_proc = 1", "Used for stackSentinel and run-file batching.")
        cards.addWidget(self.plan_card, 1)
        cards.addWidget(self.parallel_card, 1)
        layout.addLayout(cards)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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
        self.reference_hint_label = QLabel("Leave empty to let workflow choose the reference date.")
        self.reference_hint_label.setWordWrap(True)
        form.addRow("Workflow", self.workflow_combo)
        form.addRow("Coregistration", self.coreg_combo)
        form.addRow("Range looks", self.range_looks_spin)
        form.addRow("Azimuth looks", self.azimuth_looks_spin)
        form.addRow("ISCE parallel tasks (--num_proc)", self.num_proc_spin)
        form.addRow("Polarization", self.polarization_combo)
        form.addRow("Reference date", self.reference_date_edit)
        layout.addLayout(form)
        layout.addWidget(self.reference_hint_label)

        self.advanced_section = CollapsibleSection("Advanced Parameters", expanded=False)
        advanced_form = QFormLayout()
        advanced_form.setSpacing(10)
        advanced_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.num_connections_spin = QSpinBox()
        self.num_connections_spin.setRange(1, 50)
        advanced_form.addRow("Connections", self.num_connections_spin)
        self.num_proc_hint = QLabel(
            "The GUI uses num_proc as the run_file subcommand concurrency cap. "
            "Each step may still contain fewer commands than num_proc."
        )
        self.num_proc_hint.setWordWrap(True)
        advanced_form.addRow("", self.num_proc_hint)
        self.advanced_section.content_layout.addLayout(advanced_form)
        layout.addWidget(self.advanced_section)

        actions = QHBoxLayout()
        self.preview_command_button = QPushButton("Preview Command")
        self.rescan_button = QPushButton("Re-scan Existing run_files")
        self.generate_button = QPushButton("Generate Workflow")
        self.preview_command_button.setProperty("role", "secondary")
        self.rescan_button.setProperty("role", "secondary")
        self.generate_button.setProperty("role", "primary")
        actions.addWidget(self.preview_command_button)
        actions.addWidget(self.rescan_button)
        actions.addWidget(self.generate_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.command_preview_text = QPlainTextEdit()
        self.command_preview_text.setReadOnly(True)
        self.command_preview_text.setPlaceholderText("Generated stackSentinel.py command will appear here.")
        layout.addWidget(self.command_preview_text)

        self.runfile_estimate_text = QPlainTextEdit()
        self.runfile_estimate_text.setReadOnly(True)
        self.runfile_estimate_text.setPlaceholderText("Run-file command estimates appear here after generation.")
        layout.addWidget(self.runfile_estimate_text, 1)
