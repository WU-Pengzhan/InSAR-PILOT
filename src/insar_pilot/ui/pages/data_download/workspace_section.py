"""Download-workspace and DEM-download control blocks."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from insar_pilot.i18n import tr
from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.pages.data_download.base import DownloadSection
from insar_pilot.ui.widgets.path_picker_row import PathPickerRow


class WorkspaceSection(DownloadSection):
    """Output directory, orbit toggle, and aria2 backend status."""

    def __init__(self, parent=None) -> None:
        super().__init__(tr("download.workspace.title"), parent, expanded=True)
        workspace_form = QFormLayout()
        workspace_form.setContentsMargins(0, 0, 0, 0)
        workspace_form.setSpacing(10)
        self.output_dir_row = PathPickerRow()
        self.output_dir_row.line_edit.setPlaceholderText("~/sentinel1_downloads")
        workspace_form.addRow(self._form_label(tr("download.workspace.output_dir")), self.output_dir_row)
        self.include_orbits_checkbox = QCheckBox(tr("download.workspace.include_orbits"))
        self.include_orbits_checkbox.setChecked(True)
        workspace_form.addRow("", self.include_orbits_checkbox)
        self.content_layout.addLayout(workspace_form)
        workspace_hint = QLabel(tr("download.workspace.hint"))
        workspace_hint.setProperty("emptyState", True)
        workspace_hint.setWordWrap(True)
        self.content_layout.addWidget(workspace_hint)
        self.aria2_status_label = QLabel(tr("download.workspace.aria2_checking"))
        self.aria2_status_label.setProperty("emptyState", True)
        self.aria2_status_label.setWordWrap(True)
        self.content_layout.addWidget(self.aria2_status_label)

    def output_dir(self) -> str:
        """Return the selected standalone download workspace."""

        return self.output_dir_row.line_edit.text().strip()

    def include_orbits(self) -> bool:
        """Return whether orbit-file tasks should be created."""

        return self.include_orbits_checkbox.isChecked()

    def set_aria2_capability(self, available: bool, path: str = "") -> None:
        """Display current aria2c backend availability."""

        if available:
            self.aria2_status_label.setText(tr("download.aria2.available", path=path))
        else:
            self.aria2_status_label.setText(tr("download.aria2.missing"))


class DemSection(DownloadSection):
    """OpenTopography key validation and DEM-download options."""

    def __init__(self, parent=None) -> None:
        super().__init__(tr("download.dem.title"), parent, expanded=False)
        self.opentopography_available = False
        dem_form = QFormLayout()
        dem_form.setContentsMargins(0, 0, 0, 0)
        dem_form.setSpacing(10)
        self.opentopography_key_edit = QLineEdit()
        self.opentopography_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.opentopography_key_edit.setPlaceholderText(tr("download.dem.key_placeholder"))
        self.opentopography_status_label = QLabel(tr("download.dem.key_required"))
        self.opentopography_status_label.setWordWrap(True)
        self.download_dem_checkbox = QCheckBox(tr("download.dem.download_checkbox"))
        self.download_dem_checkbox.setEnabled(False)
        self.dem_source_combo = QComboBox()
        self.dem_source_combo.addItem(tr("download.dem.source.cop30"), "COP30")
        self.dem_source_combo.addItem(tr("download.dem.source.aw3d30"), "AW3D30_E")
        self.dem_source_combo.setEnabled(False)
        dem_form.addRow(self._form_label(tr("download.dem.key_label")), self.opentopography_key_edit)
        dem_form.addRow(self._form_label(tr("download.status_label")), self.opentopography_status_label)
        dem_form.addRow("", self.download_dem_checkbox)
        dem_form.addRow(self._form_label(tr("download.dem.source_label")), self.dem_source_combo)
        self.content_layout.addLayout(dem_form)
        self.test_opentopography_button = QPushButton(tr("download.key.test_save"))
        self.test_opentopography_button.setIcon(IconProvider.icon("check"))
        self.test_opentopography_button.setProperty("role", "secondary")
        self.content_layout.addWidget(self.test_opentopography_button)
        dem_hint = QLabel(tr("download.dem.hint"))
        dem_hint.setProperty("emptyState", True)
        dem_hint.setWordWrap(True)
        self.content_layout.addWidget(dem_hint)

    def should_download_dem(self) -> bool:
        """Return whether DEM download should run after SLC download."""

        return self.download_dem_checkbox.isChecked() and self.download_dem_checkbox.isEnabled()

    def dem_source(self) -> str:
        """Return the selected DEM source identifier."""

        return str(self.dem_source_combo.currentData() or "COP30")

    def opentopography_key(self) -> str:
        """Return the OpenTopography API key entered for DEM download."""

        return self.opentopography_key_edit.text().strip()

    def set_opentopography_key(self, key: str, *, source: str = "") -> None:
        """Populate the OpenTopography key and status from a local source."""

        self.opentopography_key_edit.setText(key)
        if source:
            self.opentopography_status_label.setText(tr("download.dem.key_loaded", source=source))
        else:
            self.opentopography_status_label.setText(tr("download.dem.key_required"))

    def set_opentopography_status(self, message: str) -> None:
        """Update the OpenTopography key status message."""

        self.opentopography_status_label.setText(message)

    def set_opentopography_busy(self, busy: bool) -> None:
        """Toggle the OpenTopography key action while validation runs."""

        self.test_opentopography_button.setEnabled(not busy)
        self.test_opentopography_button.setText(
            tr("download.key.testing") if busy else tr("download.key.test_save")
        )

    def set_opentopography_available(self, available: bool) -> None:
        """Enable or disable DEM controls based on OpenTopography key health."""

        self.opentopography_available = bool(available)
        self.download_dem_checkbox.setEnabled(self.opentopography_available)
        self.dem_source_combo.setEnabled(self.opentopography_available)
        if not self.opentopography_available:
            self.download_dem_checkbox.setChecked(False)
