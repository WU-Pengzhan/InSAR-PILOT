import os
import sys

from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QAbstractButton, QApplication, QCheckBox, QComboBox, QLineEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget
from PySide6.QtCore import QPoint, QPointF, Qt

from insar_pilot.bootstrap import create_default_project
from insar_pilot.services.preflight import PreflightCheck, PreflightReport
from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.pages.project_start_page import ProjectStartPage
from insar_pilot.ui.pages.processing_setup_page import ProcessingSetupPage
from insar_pilot.ui.theme import build_light_stylesheet
from insar_pilot.ui.widgets.command_preview import CommandPreview
from insar_pilot.ui.widgets.combo_wheel_guard import WHEEL_GUARD_PROPERTY, WHEEL_PASSTHROUGH_PROPERTY, install_no_wheel_on_combos
from insar_pilot.ui.widgets.parameter_grid import ParameterGrid
from insar_pilot.ui.widgets.preflight_check_list import PreflightCheckList
from insar_pilot.ui.widgets.property_form import PropertyForm
from insar_pilot.ui.widgets.run_step_monitor import RunStepMonitor
from insar_pilot.ui.widgets.top_workflow_stepper import TopWorkflowStepper
from insar_pilot.ui.widgets.workflow_step_tree import WorkflowStepTree


def _qt_app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_icon_provider_falls_back_without_qtawesome(monkeypatch):
    _qt_app()
    monkeypatch.setitem(sys.modules, "qtawesome", None)

    icon = IconProvider.icon("download")

    assert icon.isNull() is False


def test_stylesheet_is_composed_from_phase4_gis_modules():
    stylesheet = build_light_stylesheet()

    assert "font-size: 12.5pt" in stylesheet
    assert "font-family:" in stylesheet
    assert "min-height: 40px" in stylesheet
    assert "QPushButton:pressed" in stylesheet
    assert "padding: 8px 15px 6px 17px" in stylesheet
    assert "QComboBox::drop-down" in stylesheet
    assert "QComboBox::down-arrow" in stylesheet
    assert "arrow-down-16.png" in stylesheet
    assert 'QFrame#collapsibleSection[density="compact"]' in stylesheet
    assert "QLabel {" in stylesheet
    assert "background: transparent" in stylesheet
    assert "QMenuBar" in stylesheet
    assert "QToolBar" in stylesheet
    assert "QFrame#sectionPanel" in stylesheet
    assert "QFrame#parameterGrid" in stylesheet
    assert "QFrame#propertyForm" in stylesheet
    assert "QFrame#topWorkflowStepper" in stylesheet
    assert "QTreeWidget#workflowStepTree" in stylesheet
    assert "QLabel[formLabel=\"true\"]" in stylesheet


def test_preflight_check_list_renders_blockers_and_warnings():
    _qt_app()
    widget = PreflightCheckList()
    report = PreflightReport(
        [
            PreflightCheck("input", "Input", "blocker", "Missing input"),
            PreflightCheck("aria2", "aria2c", "warning", "Missing aria2"),
        ]
    )

    widget.set_report(report)

    assert "blocker" in widget.toPlainText()
    assert widget.layout.count() == 3


def test_command_preview_preserves_plain_text_compatibility():
    _qt_app()
    preview = CommandPreview()

    preview.set_metadata("Work directory: /tmp/work")
    preview.setPlainText("stackSentinel.py -s manifest")

    assert preview.toPlainText() == "stackSentinel.py -s manifest"
    assert "/tmp/work" in preview.meta_label.text()


def test_processing_setup_page_exposes_legacy_aliases():
    _qt_app()
    page = ProcessingSetupPage()

    required = [
        "shell_init_row",
        "input_path_row",
        "aoi_file_row",
        "setup_step_tree",
        "parameter_grid",
        "workflow_combo",
        "preflight_check_list",
        "technical_details_panel",
        "command_preview_text",
        "wizard_action_bar",
        "generate_button",
        "rescan_button",
    ]

    for name in required:
        assert hasattr(page, name)
    assert isinstance(page.setup_step_tree, WorkflowStepTree)
    assert isinstance(page.parameter_grid, PropertyForm)
    assert hasattr(page, "runtime_diagnostics_text")
    assert page.summary_card_container.isVisible() is False
    assert page.summary_card_container.parent() is page
    assert page.setup_step_tree.topLevelItemCount() == 6
    page.set_selected_swaths("1 3")
    assert page.selected_swaths() == "1 3"
    page.set_bbox_components("1", "2", "3", "4")
    assert page.bbox_components() == ("1", "2", "3", "4")


def test_parameter_grid_uses_stable_editor_geometry():
    _qt_app()
    grid = ParameterGrid("Required")
    editor = QLineEdit()

    grid.add_row("Sentinel-1 input folder", editor)

    assert grid.layout.columnMinimumWidth(0) == ParameterGrid.LABEL_COLUMN_WIDTH
    assert grid.layout.rowMinimumHeight(1) == ParameterGrid.ROW_MIN_HEIGHT
    assert editor.minimumHeight() >= ParameterGrid.EDITOR_MIN_HEIGHT


def test_wheel_guard_routes_checkbox_wheel_to_parent_scroll():
    app = _qt_app()
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    content = QWidget()
    content.setMinimumHeight(900)
    layout = QVBoxLayout(content)
    checkbox = QCheckBox("Use common overlap")
    layout.addWidget(checkbox)
    layout.addStretch(1)
    scroll.setWidget(content)
    scroll.resize(260, 160)
    scroll.show()
    app.processEvents()
    install_no_wheel_on_combos(scroll)

    bar = scroll.verticalScrollBar()
    bar.setValue(bar.minimum())
    event = QWheelEvent(
        QPointF(12, 12),
        QPointF(12, 12),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )

    QApplication.sendEvent(checkbox, event)

    assert checkbox.isChecked() is False
    assert bar.value() > bar.minimum()
    scroll.close()


def test_project_start_page_shows_recent_projects_and_notices(tmp_path):
    _qt_app()
    page = ProjectStartPage()
    project_root = tmp_path / "city_project"
    project_root.mkdir()

    page.set_version("9.9.9")
    page.set_notices(["Project folders are required.", "Runtime is validated in Setup."])
    page.set_recent_projects([{"name": "city_project", "path": str(project_root)}])

    assert page.recent_list.count() == 1
    assert page.recent_empty_label.isHidden() is True
    assert page.open_recent_button.isEnabled() is True
    assert "InSAR-PILOT" in page.version_label.text()
    assert "9.9.9" in page.version_label.text()
    assert "Project folders are required." in page.notice_label.text()


def test_main_window_uses_four_industrial_workflow_pages(monkeypatch):
    from insar_pilot.ui import main_window as main_window_module
    from insar_pilot.ui.main_window import MainWindow

    class _FixedSettings:
        def language(self):
            return "en"

        def set_language(self, language):
            self.language_value = language

        def restore_splitter(self, name, splitter):
            return False

        def save_splitter(self, name, splitter):
            return None

        def restore_dock_visibility(self, name, dock, *, default_visible=False):
            dock.setVisible(default_visible)

        def save_dock_visibility(self, name, dock):
            return None

        def sync(self):
            return None

    _qt_app()
    monkeypatch.setattr(main_window_module, "AppSettings", _FixedSettings)
    window = MainWindow(create_default_project())
    try:
        assert window.windowTitle() == "InSAR-PILOT"
        assert isinstance(window.workflow_stepper, TopWorkflowStepper)
        step_labels = [
            button.text()
            for button in window.workflow_stepper.findChildren(QPushButton)
            if button.objectName() == "topWorkflowStepButton"
        ]
        assert step_labels == ["Data", "Setup", "Run", "Results"]
        assert window.workflow_stepper.parent().objectName() == "projectHeader"
        assert window.page_stack.count() == 5
        assert window.page_stack.currentWidget() is window.project_start_page
        assert window.minimumWidth() >= 1366
        assert not hasattr(window, "body_splitter")
        assert not hasattr(window, "workflow_nav")
        assert window.project_inspector_dock.windowTitle() == "Project Inspector"
        assert window.project_inspector_dock.isVisible() is False
        assert window.menuBar().actions()[0].text() == "Project"
        assert window.view_menu.title() == "View"
        assert any(action.text() == "Project Inspector" for action in window.view_menu.actions())
        assert window.main_toolbar.objectName() == "mainWorkflowToolbar"
        assert not hasattr(window, "new_button")
        assert not hasattr(window, "open_button")
        assert not hasattr(window, "save_button")
        assert all(not button.isEnabled() for button in window.workflow_stepper.findChildren(QPushButton) if button.objectName() == "topWorkflowStepButton")
        assert window.data_sources_page is window.processing_setup_page
        assert window.aoi_iw_page is window.processing_setup_page
        assert window.processing_page is window.processing_setup_page
        window.resize(1366, 768)
        window.resize(1600, 980)
        assert "ISCE" not in window.windowTitle().upper()
        assert "ISCE" not in window.header_project_label.text().upper()
        assert isinstance(window.run_monitor_page.run_step_monitor, RunStepMonitor)
        assert isinstance(window.results_page.visual_parameter_grid, ParameterGrid)
        combos = window.findChildren(QComboBox)
        assert combos
        assert all(combo.property(WHEEL_GUARD_PROPERTY) for combo in combos)
        buttons = window.findChildren(QAbstractButton)
        assert buttons
        assert all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons)
        assert all(button.property(WHEEL_PASSTHROUGH_PROPERTY) for button in buttons)
        spin_boxes = window.findChildren(QSpinBox)
        assert spin_boxes
        assert all(spin.property(WHEEL_PASSTHROUGH_PROPERTY) for spin in spin_boxes)
    finally:
        window.close()
