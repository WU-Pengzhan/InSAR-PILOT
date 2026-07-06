"""Fixed wizard-style action bar."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton


class WizardActionBar(QFrame):
    """Bottom command row inspired by classic Windows/GIS workflow dialogs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("wizardActionBar")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 6, 8, 6)
        self.layout.setSpacing(8)

        self.help_button = QPushButton("Help")
        self.back_button = QPushButton("< Back")
        self.next_button = QPushButton("Next >")
        self.run_button = QPushButton("Run")
        self.cancel_button = QPushButton("Cancel")
        self.run_button.setProperty("role", "primary")
        self.cancel_button.setProperty("role", "danger")
        for button in (self.help_button, self.back_button, self.next_button):
            button.setProperty("role", "secondary")

        self.layout.addWidget(self.help_button)
        self.layout.addStretch(1)
        self.layout.addWidget(self.back_button)
        self.layout.addWidget(self.next_button)
        self.layout.addWidget(self.run_button)
        self.layout.addWidget(self.cancel_button)
