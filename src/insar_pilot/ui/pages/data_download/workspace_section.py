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

from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.pages.data_download.base import DownloadSection
from insar_pilot.ui.widgets.path_picker_row import PathPickerRow


class WorkspaceSection(DownloadSection):
    """Output directory, orbit toggle, and aria2 backend status."""

    def __init__(self, parent=None) -> None:
        super().__init__("Download Workspace", parent, expanded=True)
        workspace_form = QFormLayout()
        workspace_form.setContentsMargins(0, 0, 0, 0)
        workspace_form.setSpacing(10)
        self.output_dir_row = PathPickerRow()
        self.output_dir_row.line_edit.setPlaceholderText("~/sentinel1_downloads")
        workspace_form.addRow(self._form_label("Output directory"), self.output_dir_row)
        self.include_orbits_checkbox = QCheckBox("Download matching EOF orbit files")
        self.include_orbits_checkbox.setChecked(True)
        workspace_form.addRow("", self.include_orbits_checkbox)
        self.content_layout.addLayout(workspace_form)
        workspace_hint = QLabel(
            "SLC ZIPs are saved to SLC/. If enabled, matching EOF orbit files are saved to Orbit/."
        )
        workspace_hint.setProperty("emptyState", True)
        workspace_hint.setWordWrap(True)
        self.content_layout.addWidget(workspace_hint)
        self.aria2_status_label = QLabel("Checking aria2c availability...")
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
            self.aria2_status_label.setText(
                f"aria2c available: {path}. SLC downloads use the aria2c multipart resumable backend."
            )
        else:
            self.aria2_status_label.setText(
                "aria2c was not found on PATH. SLC downloads require aria2c for multipart resumable downloads."
            )


class DemSection(DownloadSection):
    """OpenTopography key validation and DEM-download options."""

    def __init__(self, parent=None) -> None:
        super().__init__("DEM Download", parent, expanded=False)
        self.opentopography_available = False
        dem_form = QFormLayout()
        dem_form.setContentsMargins(0, 0, 0, 0)
        dem_form.setSpacing(10)
        self.opentopography_key_edit = QLineEdit()
        self.opentopography_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.opentopography_key_edit.setPlaceholderText("OpenTopography API key")
        self.opentopography_status_label = QLabel(
            "OpenTopography key is required for DEM download. Validate your key to enable DEM controls."
        )
        self.opentopography_status_label.setWordWrap(True)
        self.download_dem_checkbox = QCheckBox("Download matching DEM after SLC download")
        self.download_dem_checkbox.setEnabled(False)
        self.dem_source_combo = QComboBox()
        self.dem_source_combo.addItem("COP30 (Copernicus Global DSM 30m)", "COP30")
        self.dem_source_combo.addItem("AW3D30_E (ALOS World 3D Ellipsoidal, 30m)", "AW3D30_E")
        self.dem_source_combo.setEnabled(False)
        dem_form.addRow(self._form_label("OpenTopography key"), self.opentopography_key_edit)
        dem_form.addRow(self._form_label("Status"), self.opentopography_status_label)
        dem_form.addRow("", self.download_dem_checkbox)
        dem_form.addRow(self._form_label("DEM source"), self.dem_source_combo)
        self.content_layout.addLayout(dem_form)
        self.test_opentopography_button = QPushButton("Test and Save Key")
        self.test_opentopography_button.setIcon(IconProvider.icon("check"))
        self.test_opentopography_button.setProperty("role", "secondary")
        self.content_layout.addWidget(self.test_opentopography_button)
        dem_hint = QLabel(
            "DEM coverage is planned after SLC download using local burst footprints. "
            "COP30 uses EGM2008 heights; AW3D30_E is already ellipsoidal."
        )
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
            self.opentopography_status_label.setText(f"Loaded OpenTopography key from {source}.")
        else:
            self.opentopography_status_label.setText(
                "OpenTopography key is required for DEM download. Validate your key to enable DEM controls."
            )

    def set_opentopography_status(self, message: str) -> None:
        """Update the OpenTopography key status message."""

        self.opentopography_status_label.setText(message)

    def set_opentopography_busy(self, busy: bool) -> None:
        """Toggle the OpenTopography key action while validation runs."""

        self.test_opentopography_button.setEnabled(not busy)
        self.test_opentopography_button.setText("Testing Key..." if busy else "Test and Save Key")

    def set_opentopography_available(self, available: bool) -> None:
        """Enable or disable DEM controls based on OpenTopography key health."""

        self.opentopography_available = bool(available)
        self.download_dem_checkbox.setEnabled(self.opentopography_available)
        self.dem_source_combo.setEnabled(self.opentopography_available)
        if not self.opentopography_available:
            self.download_dem_checkbox.setChecked(False)
