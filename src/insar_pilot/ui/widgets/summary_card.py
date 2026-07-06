"""Summary card widget used in page and sidebar layouts."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QVBoxLayout

from insar_pilot.ui.widgets.status_badge import StatusBadge


class SummaryCard(QFrame):
    """Compact high-level summary surface."""

    def __init__(
        self,
        title: str,
        value: str = "",
        body: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("summaryCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("summaryCardTitle")
        header.addWidget(self.title_label)
        header.addStretch(1)
        self.badge = StatusBadge("", "neutral")
        self.badge.hide()
        header.addWidget(self.badge)
        layout.addLayout(header)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("summaryCardValue")
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)

        self.body_label = QLabel(body)
        self.body_label.setObjectName("summaryCardBody")
        self.body_label.setWordWrap(True)
        layout.addWidget(self.body_label)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)

    def set_body(self, text: str) -> None:
        self.body_label.setText(text)

    def set_badge(self, text: str, tone: str) -> None:
        if text:
            self.badge.show()
            self.badge.set_status(text, tone)
        else:
            self.badge.hide()
