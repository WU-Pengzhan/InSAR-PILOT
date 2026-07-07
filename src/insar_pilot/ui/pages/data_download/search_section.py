"""Search-definition control block for the data download page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QStackedWidget,
)

from insar_pilot.download.models import SearchCriteria
from insar_pilot.i18n import tr
from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.pages.data_download.base import DownloadSection
from insar_pilot.ui.widgets.path_picker_row import PathPickerRow


class SearchSection(DownloadSection):
    """AOI, date, orbit, and polarization query controls plus search actions."""

    def __init__(self, parent=None) -> None:
        super().__init__(tr("download.search.title"), parent, expanded=True)
        self.setProperty("density", "compact")
        self.content_layout.setContentsMargins(10, 4, 10, 10)
        self.content_layout.setSpacing(6)
        self.search_definition_section = self

        self.aoi_mode_combo = QComboBox()
        self.aoi_mode_combo.addItem("BBOX", "bbox")
        self.aoi_mode_combo.addItem("WKT", "wkt")
        self.aoi_mode_combo.addItem(tr("download.search.aoi_mode.kml"), "kml")
        self.bbox_edit = QLineEdit()
        self.bbox_edit.setPlaceholderText("minLon,minLat,maxLon,maxLat")
        self.wkt_edit = QLineEdit()
        self.wkt_edit.setPlaceholderText("POLYGON((lon lat, ...))")
        self.aoi_file_row = PathPickerRow()
        self.aoi_file_row.line_edit.setPlaceholderText(tr("download.search.aoi_file_placeholder"))
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
        self.relative_orbit_edit.setPlaceholderText(tr("download.search.optional"))
        self.polarization_combo = QComboBox()
        for value in ("ANY", "VV", "VH", "VV+VH"):
            self.polarization_combo.addItem(value, value)

        quick_form = QFormLayout()
        quick_form.setContentsMargins(0, 0, 0, 0)
        quick_form.setHorizontalSpacing(10)
        quick_form.setVerticalSpacing(6)
        quick_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.search_definition_form = quick_form
        quick_form.addRow(self._form_label(tr("download.search.dataset")), self.platform_combo)
        quick_form.addRow(self._form_label(tr("download.search.start_date")), self.start_date_edit)
        quick_form.addRow(self._form_label(tr("download.search.end_date")), self.end_date_edit)
        quick_form.addRow(self._form_label(tr("download.search.aoi_type")), self.aoi_mode_combo)
        quick_form.addRow(self._form_label(tr("download.search.aoi")), self.aoi_stack)
        quick_form.addRow(self._form_label(tr("download.search.orbit_direction")), self.orbit_direction_combo)
        quick_form.addRow(self._form_label(tr("download.search.relative_orbit")), self.relative_orbit_edit)
        quick_form.addRow(self._form_label(tr("download.search.polarization")), self.polarization_combo)
        self.content_layout.addLayout(quick_form)
        self._apply_search_definition_compact_geometry()

        query_actions = QHBoxLayout()
        query_actions.setSpacing(8)
        self.search_button = QPushButton(tr("download.search.button"))
        self.search_button.setIcon(IconProvider.icon("search"))
        self.search_button.setProperty("role", "primary")
        self.clear_button = QPushButton(tr("download.search.clear"))
        self.clear_button.setIcon(IconProvider.icon("refresh"))
        self.clear_button.setProperty("role", "secondary")
        self.search_button.setFixedHeight(38)
        self.clear_button.setFixedHeight(38)
        query_actions.addWidget(self.search_button, 1)
        query_actions.addWidget(self.clear_button, 1)
        self.content_layout.addLayout(query_actions)

        self.aoi_mode_combo.currentIndexChanged.connect(self._handle_aoi_mode_changed)
        self._handle_aoi_mode_changed()

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

    def _handle_aoi_mode_changed(self) -> None:
        mode = str(self.aoi_mode_combo.currentData() or "bbox")
        self.aoi_stack.setCurrentIndex({"bbox": 0, "wkt": 1, "kml": 2}.get(mode, 0))

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
