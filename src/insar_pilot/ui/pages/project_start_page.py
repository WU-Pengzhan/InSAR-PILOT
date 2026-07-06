"""Start page shown until a project workspace is selected."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.ui.icons import BrandAssets, IconProvider


class ProjectStartPage(QWidget):
    """QGIS-style project landing surface for the workbench."""

    newProjectRequested = Signal()
    openProjectRequested = Signal()
    recentProjectRequested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("projectStartPage")
        self._recent_paths: list[str] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        self.recent_panel = self._build_recent_panel()
        self.side_panel = self._build_side_panel()
        layout.addWidget(self.recent_panel, 3)
        layout.addWidget(self.side_panel, 2)

    def _build_recent_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("startRecentPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)

        heading = QLabel("Recent Projects")
        heading.setObjectName("startPanelTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        heading.setMaximumHeight(34)
        hint = QLabel("Open an existing project workspace and continue from the saved processing state.")
        hint.setObjectName("startPanelHint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        hint.setMaximumHeight(56)
        panel_layout.addWidget(heading)
        panel_layout.addWidget(hint)

        self.recent_list = QListWidget()
        self.recent_list.setObjectName("startRecentList")
        self.recent_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.recent_list.setAlternatingRowColors(False)
        self.recent_list.itemActivated.connect(self._emit_recent_item)
        panel_layout.addWidget(self.recent_list, 1)

        self.recent_empty_label = QLabel("No recent projects yet. Create or open a project workspace to begin.")
        self.recent_empty_label.setObjectName("startEmptyText")
        self.recent_empty_label.setWordWrap(True)
        self.recent_empty_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        panel_layout.addWidget(self.recent_empty_label)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.open_recent_button = QPushButton("Open Selected")
        self.open_recent_button.setIcon(IconProvider.icon("folder"))
        self.open_recent_button.setProperty("role", "secondary")
        self.open_recent_button.clicked.connect(self._open_selected_recent)
        action_row.addWidget(self.open_recent_button)
        action_row.addStretch(1)
        panel_layout.addLayout(action_row)
        return panel

    def _build_side_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        actions = QFrame()
        actions.setObjectName("startActionPanel")
        action_layout = QVBoxLayout(actions)
        action_layout.setContentsMargins(18, 16, 18, 16)
        action_layout.setSpacing(12)
        action_title = QLabel("Project Workspace")
        action_title.setObjectName("startPanelTitle")
        action_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        action_title.setMaximumHeight(34)
        action_hint = QLabel(
            "Create a dedicated folder for downloads, logs, processing workspace, and quicklook outputs."
        )
        action_hint.setObjectName("startPanelHint")
        action_hint.setWordWrap(True)
        action_hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        action_hint.setMaximumHeight(70)
        action_layout.addWidget(action_title)
        action_layout.addWidget(action_hint)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.new_project_button = QPushButton("New Project")
        self.new_project_button.setIcon(IconProvider.icon("folder"))
        self.new_project_button.setProperty("role", "primary")
        self.open_project_button = QPushButton("Open Project")
        self.open_project_button.setIcon(IconProvider.icon("folder"))
        self.open_project_button.setProperty("role", "secondary")
        self.new_project_button.clicked.connect(self.newProjectRequested.emit)
        self.open_project_button.clicked.connect(self.openProjectRequested.emit)
        button_row.addWidget(self.new_project_button)
        button_row.addWidget(self.open_project_button)
        action_layout.addLayout(button_row)
        layout.addWidget(actions)

        info = QFrame()
        info.setObjectName("startInfoPanel")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(18, 16, 18, 16)
        info_layout.setSpacing(8)
        brand_row = QWidget()
        brand_row.setObjectName("startBrandRow")
        brand_layout = QHBoxLayout(brand_row)
        brand_layout.setContentsMargins(0, 0, 0, 4)
        brand_layout.setSpacing(12)
        self.logo_label = QLabel()
        self.logo_label.setObjectName("startBrandLogo")
        self.logo_label.setPixmap(BrandAssets.pixmap(size=QSize(58, 58)))
        self.logo_label.setFixedSize(64, 64)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(self.logo_label)

        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(2)
        brand_name = QLabel("InSAR-PILOT")
        brand_name.setObjectName("startBrandName")
        brand_name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        brand_subtitle = QLabel("Guided SAR/InSAR processing")
        brand_subtitle.setObjectName("startBrandSubtitle")
        brand_subtitle.setWordWrap(True)
        brand_text.addWidget(brand_name)
        brand_text.addWidget(brand_subtitle)
        brand_layout.addLayout(brand_text, 1)
        info_layout.addWidget(brand_row)

        info_title = QLabel("Version")
        info_title.setObjectName("startPanelTitle")
        info_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        info_title.setMaximumHeight(34)
        self.version_label = QLabel("InSAR-PILOT")
        self.version_label.setObjectName("startInfoText")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.version_label.setMaximumHeight(34)
        self.runtime_label = QLabel("Runtime is validated from the environment used to launch the application.")
        self.runtime_label.setObjectName("startPanelHint")
        self.runtime_label.setWordWrap(True)
        self.runtime_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.runtime_label.setMaximumHeight(60)
        info_layout.addWidget(info_title)
        info_layout.addWidget(self.version_label)
        info_layout.addWidget(self.runtime_label)
        layout.addWidget(info)

        notices = QFrame()
        notices.setObjectName("startNoticePanel")
        notice_layout = QVBoxLayout(notices)
        notice_layout.setContentsMargins(18, 16, 18, 16)
        notice_layout.setSpacing(8)
        notice_title = QLabel("Notices")
        notice_title.setObjectName("startPanelTitle")
        notice_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        notice_title.setMaximumHeight(34)
        self.notice_label = QLabel("")
        self.notice_label.setObjectName("startNoticeText")
        self.notice_label.setWordWrap(True)
        self.notice_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.notice_label.setMaximumHeight(160)
        notice_layout.addWidget(notice_title)
        notice_layout.addWidget(self.notice_label)
        notice_layout.addStretch(1)
        layout.addWidget(notices, 1)
        return container

    def set_recent_projects(self, projects: list[dict[str, str]]) -> None:
        """Render the recent project list."""

        self.recent_list.clear()
        self._recent_paths = []
        for project in projects:
            name = project.get("name", "").strip()
            path = project.get("path", "").strip()
            if not path:
                continue
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setSizeHint(QSize(0, 92))
            self.recent_list.addItem(item)
            self.recent_list.setItemWidget(item, self._build_recent_row(name or Path(path).name, path))
            self._recent_paths.append(path)

        has_recent = bool(self._recent_paths)
        if not has_recent:
            item = QListWidgetItem()
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setSizeHint(QSize(0, 118))
            self.recent_list.addItem(item)
            self.recent_list.setItemWidget(item, self._build_empty_recent_row())
        self.recent_empty_label.hide()
        self.recent_list.show()
        self.open_recent_button.setEnabled(has_recent)
        self.open_recent_button.setVisible(has_recent)
        if has_recent:
            self.recent_list.setCurrentRow(0)

    def set_version(self, version: str) -> None:
        self.version_label.setText(f"InSAR-PILOT {version}")

    def set_notices(self, notices: list[str]) -> None:
        self.notice_label.setText("\n".join(f"- {item}" for item in notices))

    def _build_recent_row(self, name: str, path: str) -> QWidget:
        row = QWidget()
        row.setObjectName("startRecentRow")
        row.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        icon = QLabel()
        icon.setObjectName("startRecentIcon")
        icon.setPixmap(IconProvider.icon("folder").pixmap(32, 32))
        icon.setFixedSize(38, 38)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(icon)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(3)
        name_label = QLabel(name)
        name_label.setObjectName("startRecentName")
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        path_label = QLabel(path)
        path_label.setObjectName("startRecentPath")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        path_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        path_label.setWordWrap(True)
        status_label = QLabel("Available" if Path(path).expanduser().exists() else "Missing on disk")
        status_label.setObjectName("startRecentStatus")
        status_label.setProperty("missing", not Path(path).expanduser().exists())
        status_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        status_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_col.addWidget(name_label)
        text_col.addWidget(path_label)
        text_col.addWidget(status_label)
        layout.addLayout(text_col, 1)
        return row

    def _build_empty_recent_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("startEmptyRow")
        row.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(4)
        title = QLabel("No recent projects")
        title.setObjectName("startRecentName")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        detail = QLabel("Create or open a project workspace to begin.")
        detail.setObjectName("startRecentPath")
        detail.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        detail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(title)
        layout.addWidget(detail)
        layout.addStretch(1)
        return row

    def _emit_recent_item(self, item: QListWidgetItem) -> None:
        path = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if path:
            self.recentProjectRequested.emit(path)

    def _open_selected_recent(self) -> None:
        item = self.recent_list.currentItem()
        if item is not None:
            self._emit_recent_item(item)
