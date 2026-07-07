"""ASF Earthdata credentials and Tianditu basemap-key control blocks."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.pages.data_download.base import DownloadSection


class CredentialsSection(DownloadSection):
    """ASF Earthdata account credentials and connection test."""

    def __init__(self, parent=None) -> None:
        super().__init__("ASF Earthdata Account", parent, expanded=True)
        credentials_form = QFormLayout()
        credentials_form.setContentsMargins(0, 0, 0, 0)
        credentials_form.setSpacing(10)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Earthdata username")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Earthdata password")
        self.credential_status_label = QLabel("Connection has not been tested.")
        self.credential_status_label.setWordWrap(True)
        self.credential_hint_label = QLabel(
            "Recommended first step: test ASF Earthdata credentials before searching or downloading."
        )
        self.credential_hint_label.setProperty("emptyState", True)
        self.credential_hint_label.setWordWrap(True)
        self.save_netrc_checkbox = QCheckBox("Save credentials to ~/.netrc")
        credentials_form.addRow(self._form_label("Username"), self.username_edit)
        credentials_form.addRow(self._form_label("Password"), self.password_edit)
        credentials_form.addRow(self._form_label("Status"), self.credential_status_label)
        credentials_form.addRow("", self.save_netrc_checkbox)
        self.content_layout.addLayout(credentials_form)
        self.content_layout.addWidget(self.credential_hint_label)
        credentials_actions = QHBoxLayout()
        self.test_credentials_button = QPushButton("Test ASF Connection")
        self.test_credentials_button.setIcon(IconProvider.icon("account"))
        self.test_credentials_button.setProperty("role", "secondary")
        credentials_actions.addWidget(self.test_credentials_button, 1)
        self.content_layout.addLayout(credentials_actions)

    def credential_inputs(self) -> tuple[str, str]:
        """Return ASF Earthdata username/password fields."""

        return self.username_edit.text().strip(), self.password_edit.text()

    def set_credential_inputs(self, username: str, password: str, *, source: str = "") -> None:
        """Populate ASF Earthdata credentials from a local source."""

        self.username_edit.setText(username)
        self.password_edit.setText(password)
        if source:
            self.credential_status_label.setText(f"Loaded Earthdata credentials from {source}.")

    def should_save_netrc(self) -> bool:
        """Return whether credentials should be persisted to ~/.netrc."""

        return self.save_netrc_checkbox.isChecked()


class BasemapSection(DownloadSection):
    """Optional Tianditu basemap API key controls."""

    def __init__(self, parent=None) -> None:
        super().__init__("Basemap", parent, expanded=False)
        basemap_form = QFormLayout()
        basemap_form.setContentsMargins(0, 0, 0, 0)
        basemap_form.setSpacing(10)
        self.tianditu_key_edit = QLineEdit()
        self.tianditu_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.tianditu_key_edit.setPlaceholderText("Tianditu API key")
        self.tianditu_status_label = QLabel(
            "Tianditu key is optional. External Imagery will be used automatically until Tianditu is available."
        )
        self.tianditu_status_label.setWordWrap(True)
        basemap_form.addRow(self._form_label("Tianditu key"), self.tianditu_key_edit)
        basemap_form.addRow(self._form_label("Status"), self.tianditu_status_label)
        self.content_layout.addLayout(basemap_form)
        self.test_tianditu_button = QPushButton("Test and Save Key")
        self.test_tianditu_button.setIcon(IconProvider.icon("check"))
        self.test_tianditu_button.setProperty("role", "secondary")
        self.content_layout.addWidget(self.test_tianditu_button)
        basemap_hint = QLabel(
            "Tianditu is used by default for mainland-friendly basemaps. External Esri "
            "imagery and terrain layers are available only when selected on the map."
        )
        basemap_hint.setProperty("emptyState", True)
        basemap_hint.setWordWrap(True)
        self.content_layout.addWidget(basemap_hint)

    def tianditu_key(self) -> str:
        """Return the Tianditu API key entered for the basemap."""

        return self.tianditu_key_edit.text().strip()

    def set_tianditu_key(self, key: str, *, source: str = "") -> None:
        """Populate the Tianditu key and refresh the footprint map."""

        self.tianditu_key_edit.setText(key)
        if source:
            self.tianditu_status_label.setText(f"Loaded Tianditu key from {source}.")
        else:
            self.tianditu_status_label.setText(
                "Tianditu key is optional. External Imagery will be used automatically until Tianditu is available."
            )

    def set_tianditu_status(self, message: str) -> None:
        """Update the Tianditu key status message."""

        self.tianditu_status_label.setText(message)

    def set_tianditu_busy(self, busy: bool) -> None:
        """Toggle the Tianditu key check button while validation runs."""

        self.test_tianditu_button.setEnabled(not busy)
        self.test_tianditu_button.setText("Testing Key..." if busy else "Test and Save Key")
