"""Shared page layout widgets for the industrial shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from insar_pilot.ui.styles import SPACE

# Micro-spacing for stacked title/subtitle text that is tighter than the base scale.
_TEXT_GAP = 2


class PageHeader(QFrame):
    """Consistent page title area with optional actions."""

    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("pageHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["md"])

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(_TEXT_GAP)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("pageHeaderTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("pageHeaderSubtitle")
        self.subtitle_label.setWordWrap(True)
        text_col.addWidget(self.title_label)
        text_col.addWidget(self.subtitle_label)
        layout.addLayout(text_col, 1)

        self.action_layout = QHBoxLayout()
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(SPACE["sm"])
        layout.addLayout(self.action_layout)


class PageScaffold(QWidget):
    """Scrollable page scaffold with a stable header and content column."""

    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        layout.setSpacing(SPACE["md"])
        self.header = PageHeader(title, subtitle)
        layout.addWidget(self.header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(SPACE["md"])
        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area, 1)


class SectionPanel(QFrame):
    """Framed section for compact professional forms."""

    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["md"], SPACE["md"], SPACE["md"])
        layout.setSpacing(10)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("sectionPanelTitle")
        layout.addWidget(self.title_label)
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setWordWrap(True)
            self.subtitle_label.setObjectName("summaryCardBody")
            layout.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        layout.addLayout(self.content_layout)


class ActionBar(QFrame):
    """Horizontal command area used at the end of task sections."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("actionBar")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        self.layout.setSpacing(SPACE["sm"])


class InlineAlert(QFrame):
    """Inline message block with a semantic tone."""

    def __init__(self, message: str = "", tone: str = "info", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("inlineAlert")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        layout.setSpacing(SPACE["sm"])
        self.label = QLabel(message)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_message(self, message: str, tone: str | None = None) -> None:
        self.label.setText(message)
        if tone:
            self.set_tone(tone)


class EmptyState(QFrame):
    """Shared empty state surface."""

    def __init__(self, title: str, body: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], 10, SPACE["md"], 10)
        layout.setSpacing(SPACE["xs"])
        self.title_label = QLabel(title)
        self.title_label.setObjectName("summaryCardValue")
        self.body_label = QLabel(body)
        self.body_label.setObjectName("summaryCardBody")
        self.body_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)


class StatusStrip(QFrame):
    """Compact row for multiple live state labels."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statusStrip")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        self.layout.setSpacing(10)
