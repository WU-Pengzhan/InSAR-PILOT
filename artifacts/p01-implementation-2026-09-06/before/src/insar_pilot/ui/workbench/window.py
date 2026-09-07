"""Independent shell for the next-generation InSAR-PILOT Workbench."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.application.search import SearchApplicationService
from insar_pilot.i18n import tr
from insar_pilot.providers.sar import build_default_sar_provider_registry
from insar_pilot.ui.features.search.inspector import ProductInspector
from insar_pilot.ui.features.search.presenter import SearchPresenter
from insar_pilot.ui.features.search.task_runner import SearchTaskRunner
from insar_pilot.ui.features.search.workspace import SearchWorkspace
from insar_pilot.ui.workbench.layout_controller import (
    WorkbenchLayoutController,
    WorkbenchLayoutMode,
)


class WorkbenchWindow(QMainWindow):
    """Search-first shell isolated from the legacy workflow MainWindow."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        search_service: SearchApplicationService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("nextWorkbenchWindow")
        self.setWindowTitle(tr("workbench.title"))
        self.resize(1440, 900)
        self.setMinimumSize(1100, 680)

        self.search_workspace = SearchWorkspace(self)
        self.setCentralWidget(self.search_workspace)
        self._build_docks()
        self._build_view_menu()

        service = search_service or SearchApplicationService(build_default_sar_provider_registry())
        self.search_task_runner = SearchTaskRunner(service, self)
        self.search_presenter = SearchPresenter(
            self.search_workspace,
            self.product_inspector,
            self.search_task_runner,
            service,
            self,
        )

        self.layout_controller = WorkbenchLayoutController(self.search_workspace, self)
        self.layout_controller.apply(WorkbenchLayoutMode.NORMAL)

    def _build_docks(self) -> None:
        self.inspector_dock = QDockWidget(tr("workbench.inspector.title"), self)
        self.inspector_dock.setObjectName("workbenchInspectorDock")
        self.inspector_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.product_inspector = ProductInspector()
        self.inspector_dock.setWidget(self.product_inspector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)

        self.activity_dock = QDockWidget(tr("workbench.activity.title"), self)
        self.activity_dock.setObjectName("workbenchActivityDock")
        self.activity_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.activity_tabs = QTabWidget()
        tasks = QWidget()
        tasks_layout = QVBoxLayout(tasks)
        tasks_layout.addWidget(QLabel(tr("workbench.tasks.empty")))
        tasks_layout.addStretch(1)
        self.activity_tabs.addTab(tasks, tr("workbench.tasks.title"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText(tr("workbench.logs.empty"))
        self.activity_tabs.addTab(self.log_view, tr("workbench.logs.title"))
        self.activity_dock.setWidget(self.activity_tabs)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.activity_dock)

        self.inspector_dock.hide()
        self.activity_dock.hide()

    def _build_view_menu(self) -> None:
        view_menu = self.menuBar().addMenu(tr("workbench.view"))
        inspector_action = self.inspector_dock.toggleViewAction()
        inspector_action.setText(tr("workbench.inspector.title"))
        activity_action = self.activity_dock.toggleViewAction()
        activity_action.setText(tr("workbench.activity.title"))
        view_menu.addAction(inspector_action)
        view_menu.addAction(activity_action)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_current_layout)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            QTimer.singleShot(0, self._apply_current_layout)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.search_task_runner.shutdown()
        super().closeEvent(event)

    def _apply_current_layout(self) -> None:
        mode = WorkbenchLayoutMode.MAXIMIZED if self.isMaximized() else WorkbenchLayoutMode.NORMAL
        self.layout_controller.apply(mode)
