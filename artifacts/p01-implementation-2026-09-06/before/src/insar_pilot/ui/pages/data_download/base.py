"""Shared base for data-download control sections."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from insar_pilot.ui.widgets.collapsible_section import CollapsibleSection


class DownloadSection(CollapsibleSection):
    """Collapsible control section with the page's transparent form labels."""

    @staticmethod
    def _form_label(text: str) -> QLabel:
        """Build a transparent form label that matches the rest of the shell."""

        label = QLabel(text)
        label.setProperty("formLabel", True)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setWordWrap(False)
        return label
