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

from insar_pilot.i18n import tr
from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.pages.data_download.base import DownloadSection


class CredentialsSection(DownloadSection):
    """ASF Earthdata account credentials and connection test."""

    def __init__(self, parent=None) -> None:
        super().__init__(tr("download.credentials.title"), parent, expanded=True)
        credentials_form = QFormLayout()
        credentials_form.setContentsMargins(0, 0, 0, 0)
        credentials_form.setSpacing(10)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText(tr("download.credentials.username_placeholder"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText(tr("download.credentials.password_placeholder"))
        self.credential_status_label = QLabel(tr("download.credentials.not_tested"))
        self.credential_status_label.setWordWrap(True)
        self.credential_hint_label = QLabel(tr("download.credentials.hint"))
        self.credential_hint_label.setProperty("emptyState", True)
        self.credential_hint_label.setWordWrap(True)
        self.save_netrc_checkbox = QCheckBox(tr("download.credentials.save_netrc"))
        credentials_form.addRow(self._form_label(tr("download.credentials.username")), self.username_edit)
        credentials_form.addRow(self._form_label(tr("download.credentials.password")), self.password_edit)
        credentials_form.addRow(self._form_label(tr("download.status_label")), self.credential_status_label)
        credentials_form.addRow("", self.save_netrc_checkbox)
        self.content_layout.addLayout(credentials_form)
        self.content_layout.addWidget(self.credential_hint_label)
        credentials_actions = QHBoxLayout()
        self.test_credentials_button = QPushButton(tr("download.credentials.test_button"))
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
            self.credential_status_label.setText(tr("download.credentials.loaded", source=source))

    def should_save_netrc(self) -> bool:
        """Return whether credentials should be persisted to ~/.netrc."""

        return self.save_netrc_checkbox.isChecked()


class BasemapSection(DownloadSection):
    """Optional Tianditu basemap API key controls."""

    def __init__(self, parent=None) -> None:
        super().__init__(tr("download.basemap.title"), parent, expanded=False)
        basemap_form = QFormLayout()
        basemap_form.setContentsMargins(0, 0, 0, 0)
        basemap_form.setSpacing(10)
        self.tianditu_key_edit = QLineEdit()
        self.tianditu_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.tianditu_key_edit.setPlaceholderText(tr("download.basemap.key_placeholder"))
        self.tianditu_status_label = QLabel(tr("download.basemap.key_optional"))
        self.tianditu_status_label.setWordWrap(True)
        basemap_form.addRow(self._form_label(tr("download.basemap.key_label")), self.tianditu_key_edit)
        basemap_form.addRow(self._form_label(tr("download.status_label")), self.tianditu_status_label)
        self.content_layout.addLayout(basemap_form)
        self.test_tianditu_button = QPushButton(tr("download.key.test_save"))
        self.test_tianditu_button.setIcon(IconProvider.icon("check"))
        self.test_tianditu_button.setProperty("role", "secondary")
        self.content_layout.addWidget(self.test_tianditu_button)
        basemap_hint = QLabel(tr("download.basemap.hint"))
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
            self.tianditu_status_label.setText(tr("download.basemap.key_loaded", source=source))
        else:
            self.tianditu_status_label.setText(tr("download.basemap.key_optional"))

    def set_tianditu_status(self, message: str) -> None:
        """Update the Tianditu key status message."""

        self.tianditu_status_label.setText(message)

    def set_tianditu_busy(self, busy: bool) -> None:
        """Toggle the Tianditu key check button while validation runs."""

        self.test_tianditu_button.setEnabled(not busy)
        self.test_tianditu_button.setText(tr("download.key.testing") if busy else tr("download.key.test_save"))
