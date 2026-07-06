"""Run monitor page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from insar_pilot.ui.widgets.page_scaffold import StatusStrip
from insar_pilot.ui.widgets.run_step_monitor import RunStepMonitor
from insar_pilot.ui.widgets.summary_card import SummaryCard
from insar_pilot.ui.widgets.wizard_action_bar import WizardActionBar


class RunMonitorPage(QWidget):
    """Execution monitoring and failure recovery page."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.status_strip = StatusStrip()
        self.project_status_label = QLabel("Status: -")
        self.current_step_label = QLabel("Step: -")
        self.work_dir_label = QLabel("Work dir: -")
        for label in (self.project_status_label, self.current_step_label, self.work_dir_label):
            label.setObjectName("summaryCardTitle")
            self.status_strip.layout.addWidget(label)
        self.status_strip.layout.addStretch(1)
        layout.addWidget(self.status_strip)

        self.status_card = SummaryCard("Project Status", "-", "Execution state across run_files.", self)
        self.current_step_card = SummaryCard("Current Step", "-", "Currently active workflow step.", self)
        self.work_dir_card = SummaryCard("Work Directory", "-", "Resolved project work directory.", self)
        for card in (self.status_card, self.current_step_card, self.work_dir_card):
            card.hide()

        button_grid = QGridLayout()
        self.run_next_button = QPushButton("Run Next Step")
        self.run_selected_button = QPushButton("Run Selected Step")
        self.run_all_button = QPushButton("Run Remaining Steps")
        self.stop_button = QPushButton("Stop")
        self.refresh_outputs_button = QPushButton("Refresh Outputs")
        self.run_next_button.setProperty("role", "primary")
        self.run_selected_button.setProperty("role", "secondary")
        self.run_all_button.setProperty("role", "secondary")
        self.stop_button.setProperty("role", "danger")
        self.refresh_outputs_button.setProperty("role", "secondary")
        button_grid.addWidget(self.run_next_button, 0, 0)
        button_grid.addWidget(self.run_selected_button, 0, 1)
        button_grid.addWidget(self.run_all_button, 1, 0)
        button_grid.addWidget(self.stop_button, 1, 1)
        button_grid.addWidget(self.refresh_outputs_button, 2, 0, 1, 2)
        layout.addLayout(button_grid)

        self.empty_state_label = QLabel(
            "No run files yet. Generate workflow in Processing Setup to populate executable steps."
        )
        self.empty_state_label.setProperty("emptyState", True)
        self.empty_state_label.setWordWrap(True)
        layout.addWidget(self.empty_state_label)

        self.run_step_monitor = RunStepMonitor()
        self.steps_tree = self.run_step_monitor.steps_tree
        self.command_detail_text = self.run_step_monitor.command_detail_text
        self.runfile_estimate_text = self.run_step_monitor.runfile_estimate_text
        layout.addWidget(self.run_step_monitor, 1)

        self.run_wizard_bar = WizardActionBar()
        self.run_wizard_bar.back_button.setEnabled(False)
        self.run_wizard_bar.next_button.setText("Selected >")
        self.run_wizard_bar.run_button.setText("Run Next")
        self.run_wizard_bar.cancel_button.setText("Stop")
        self.run_wizard_bar.run_button.clicked.connect(self.run_next_button.click)
        self.run_wizard_bar.next_button.clicked.connect(self.run_selected_button.click)
        self.run_wizard_bar.cancel_button.clicked.connect(self.stop_button.click)
        layout.addWidget(self.run_wizard_bar)
