"""Unified AOI + processing bbox + IW selection page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.ui.widgets.geometry_verify_panel import GeometryVerifyPanel
from insar_pilot.ui.widgets.path_picker_row import PathPickerRow
from insar_pilot.ui.widgets.summary_card import SummaryCard


class AoiIwPage(QWidget):
    """Single entry point to finalize processing bbox and IW parameters."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.source_card = SummaryCard("AOI Source", "Manual", "AOI file can auto-fill the processing bbox.")
        self.bbox_card = SummaryCard("Processing BBox (SNWE)", "Not set", "Final processing bbox in decimal degrees.")
        self.iw_card = SummaryCard("IW Selection", "IW1 IW2 IW3", "At least one IW must be selected.")
        cards.addWidget(self.source_card, 1)
        cards.addWidget(self.bbox_card, 1)
        cards.addWidget(self.iw_card, 1)
        layout.addLayout(cards)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.aoi_file_row = PathPickerRow(secondary_label="Import AOI")
        self.use_common_overlap_check = QCheckBox("Use common overlap (allow empty processing bbox)")
        self.bbox_south_edit = self._line("e.g. 33.85")
        self.bbox_north_edit = self._line("e.g. 33.90")
        self.bbox_west_edit = self._line("e.g. -118.28")
        self.bbox_east_edit = self._line("e.g. -118.04")
        form.addRow("AOI file (KML/SHP)", self.aoi_file_row)
        form.addRow("", self.use_common_overlap_check)
        form.addRow("South", self.bbox_south_edit)
        form.addRow("North", self.bbox_north_edit)
        form.addRow("West", self.bbox_west_edit)
        form.addRow("East", self.bbox_east_edit)
        layout.addLayout(form)

        swath_row = QHBoxLayout()
        swath_row.setSpacing(10)
        swath_row.addWidget(QLabel("IW swaths"))
        self.iw1_check = QCheckBox("IW1")
        self.iw2_check = QCheckBox("IW2")
        self.iw3_check = QCheckBox("IW3")
        self.iw1_check.setObjectName("iw1Check")
        self.iw2_check.setObjectName("iw2Check")
        self.iw3_check.setObjectName("iw3Check")
        self.iw1_check.setChecked(True)
        self.iw2_check.setChecked(True)
        self.iw3_check.setChecked(True)
        swath_row.addWidget(self.iw1_check)
        swath_row.addWidget(self.iw2_check)
        swath_row.addWidget(self.iw3_check)
        swath_row.addStretch(1)
        layout.addLayout(swath_row)

        helper = QLabel(
            "AOI file is user input data. Processing bbox is a stack parameter (SNWE decimal degrees). "
            "You can auto-fill from AOI and still manually adjust bbox/IW."
        )
        helper.setWordWrap(True)
        layout.addWidget(helper)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.recommend_iw_button = QPushButton("Recommend IW")
        self.verify_button = QPushButton("Verify Geometry")
        self.export_verify_button = QPushButton("Export Verify PNG")
        self.confirm_button = QPushButton("Confirm AOI+BBox+IW")
        self.recommend_iw_button.setProperty("role", "secondary")
        self.verify_button.setProperty("role", "secondary")
        self.export_verify_button.setProperty("role", "secondary")
        self.confirm_button.setProperty("role", "primary")
        actions.addWidget(self.recommend_iw_button)
        actions.addWidget(self.verify_button)
        actions.addWidget(self.export_verify_button)
        actions.addWidget(self.confirm_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.verify_panel = GeometryVerifyPanel()
        layout.addWidget(self.verify_panel, 1)

        self.verify_alert_label = QLabel("")
        self.verify_alert_label.setObjectName("inlineErrorText")
        self.verify_alert_label.setWordWrap(True)
        self.verify_alert_label.hide()
        layout.addWidget(self.verify_alert_label)

        self.verify_notes = QPlainTextEdit()
        self.verify_notes.setReadOnly(True)
        self.verify_notes.setPlaceholderText("AOI import, IW recommendation, and verify notes will appear here.")
        layout.addWidget(self.verify_notes)

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
