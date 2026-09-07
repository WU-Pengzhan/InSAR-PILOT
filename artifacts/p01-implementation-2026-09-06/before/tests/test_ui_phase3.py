import os
import sys

from PySide6.QtCore import QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.bootstrap import create_default_project
from insar_pilot.services.preflight import PreflightCheck, PreflightReport
from insar_pilot.services.result_catalog import ResultProduct
from insar_pilot.ui.fonts import build_ui_font, resolve_ui_font_family
from insar_pilot.ui.icons import BrandAssets, IconProvider
from insar_pilot.ui.pages.data_download.scroll_filter import NestedScrollFilter
from insar_pilot.ui.pages.processing_setup_page import ProcessingSetupPage
from insar_pilot.ui.pages.project_start_page import ProjectStartPage
from insar_pilot.ui.pages.results_page import ResultsPage
from insar_pilot.ui.styles.tokens import DARK_TOKENS, LIGHT_TOKENS, active_tokens
from insar_pilot.ui.task_pool import BackgroundTaskPool
from insar_pilot.ui.theme import apply_theme, build_light_stylesheet
from insar_pilot.ui.widgets.combo_wheel_guard import (
    WHEEL_GUARD_PROPERTY,
    WHEEL_PASSTHROUGH_PROPERTY,
    install_no_wheel_on_combos,
)
from insar_pilot.ui.widgets.command_preview import CommandPreview
from insar_pilot.ui.widgets.footprint_map import FootprintMapWidget
from insar_pilot.ui.widgets.log_console import LogConsole
from insar_pilot.ui.widgets.parameter_grid import ParameterGrid
from insar_pilot.ui.widgets.preflight_check_list import PreflightCheckList
from insar_pilot.ui.widgets.preview_panel import PreviewPanel
from insar_pilot.ui.widgets.property_form import PropertyForm
from insar_pilot.ui.widgets.run_step_monitor import RunStepMonitor
from insar_pilot.ui.widgets.top_workflow_stepper import TopWorkflowStepper
from insar_pilot.ui.widgets.workflow_step_tree import WorkflowStepTree

_QT_APP: QApplication | None = None


def _qt_app() -> QApplication:
    global _QT_APP
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    _QT_APP = app if app is not None else QApplication([])
    _QT_APP.setQuitOnLastWindowClosed(False)
    return _QT_APP


def _disable_startup_account_checks(monkeypatch) -> None:
    """Keep MainWindow layout tests independent of workstation credentials."""

    from insar_pilot.ui.controllers import download_controller as controller_module

    monkeypatch.setattr(controller_module, "load_earthdata_credentials", lambda: None)
    monkeypatch.setattr(controller_module, "load_tianditu_key", lambda: None)
    monkeypatch.setattr(controller_module, "load_opentopography_key", lambda: None)


def test_icon_provider_falls_back_without_qtawesome(monkeypatch):
    _qt_app()
    monkeypatch.setitem(sys.modules, "qtawesome", None)

    icon = IconProvider.icon("download")

    assert icon.isNull() is False


def test_brand_assets_return_non_empty_qt_images():
    _qt_app()

    assert BrandAssets.icon().isNull() is False
    assert BrandAssets.pixmap().isNull() is False


def test_stylesheet_is_composed_from_phase4_gis_modules():
    stylesheet = build_light_stylesheet()

    assert "font-size: 12pt" in stylesheet
    assert "font-family:" in stylesheet
    assert "Noto Sans CJK SC" in stylesheet
    assert "font-weight: 450" in stylesheet
    assert "min-height: 32px" in stylesheet
    assert "QPushButton:pressed" in stylesheet
    assert "padding: 7px 15px 5px 17px" in stylesheet
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


def test_ui_font_prefers_a_unified_chinese_latin_family():
    _qt_app()
    assert resolve_ui_font_family(["DejaVu Sans", "Noto Sans CJK SC"]) == "Noto Sans CJK SC"
    assert resolve_ui_font_family(["Ubuntu", "DejaVu Sans"]) == "Ubuntu"

    font = build_ui_font(point_size=12)

    assert font.pointSizeF() == 12


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


def test_preview_panel_calculates_decode_allowance_without_limiting_source_resolution():
    source_size = QSize(45081, 5062)

    required_mb = PreviewPanel._required_allocation_limit_mb(source_size)

    assert required_mb == 935
    assert required_mb > 256


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
    assert page.parameter_grid.label_width == 150
    assert page.parameter_grid.row_height == 54
    assert page.parameter_grid.layout.columnMinimumWidth(0) == 150
    labels = [label.text() for label in page.findChildren(QLabel) if label.objectName() == "propertyFormLabel"]
    assert "SLC folder" in labels
    assert "Sentinel-1 input folder" not in labels
    visible_text = "\n".join(label.text() for label in page.findChildren(QLabel) if label.isVisible())
    assert "WSL2/conda runtime" not in visible_text
    assert "Runtime uses the environment" not in visible_text
    assert page.summary_card_container.isVisible() is False
    assert page.summary_card_container.parent() is page
    assert page.setup_step_tree.topLevelItemCount() == 6
    assert page.scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.workbench_scroll.widget() is page.workbench_content
    assert page.workbench_splitter.widget(0) is page.setup_step_tree
    assert page.workbench_splitter.widget(1) is page.workbench_scroll
    assert page.wizard_action_bar.parentWidget() is page.workbench_content
    page.setup_step_tree.set_step_status_by_key("geometry", "success", "Verified")
    geometry_item = page.setup_step_tree.topLevelItem(2)
    assert geometry_item.data(0, Qt.ItemDataRole.UserRole) == "success"
    assert geometry_item.toolTip(0) == "Verified"
    page.set_selected_swaths("1 3")
    assert page.selected_swaths() == "1 3"
    page.set_bbox_components("1", "2", "3", "4")
    assert page.bbox_components() == ("1", "2", "3", "4")


def test_processing_setup_scroll_keeps_workflow_rail_fixed():
    app = _qt_app()
    page = ProcessingSetupPage()
    page.resize(1280, 720)
    page.show()
    app.processEvents()

    scroll_bar = page.workbench_scroll.verticalScrollBar()
    before = page.setup_step_tree.geometry()
    assert scroll_bar.maximum() > 0

    scroll_bar.setValue(min(600, scroll_bar.maximum()))
    app.processEvents()

    assert scroll_bar.value() > 0
    assert page.setup_step_tree.geometry() == before
    assert page.scroll_area.verticalScrollBar().maximum() == 0
    page.close()


def test_sentinel1_visualization_ui_defaults_do_not_change_processing_looks():
    app = _qt_app()
    page = ResultsPage()
    project = create_default_project()
    page.resize(1600, 820)
    page.show()
    app.processEvents()

    assert page.visual_range_looks_spin.value() == 10
    assert page.visual_azimuth_looks_spin.value() == 2
    assert project.visualization.range_looks == 10
    assert project.visualization.azimuth_looks == 2
    assert project.workflow.range_looks == 1
    assert project.workflow.azimuth_looks == 1
    assert not hasattr(page, "main_splitter")
    assert not hasattr(page, "controls_workspace")
    assert page.preview_panel.height() >= 480
    assert page.advanced_section.content.isHidden()
    assert page.details_section.content.isHidden()

    preview_width = page.preview_panel.width()
    page.advanced_section.toggle_button.setChecked(True)
    app.processEvents()
    assert page.preview_panel.width() == preview_width
    page.close()


def test_parameter_grid_uses_stable_editor_geometry():
    _qt_app()
    grid = ParameterGrid("Required")
    editor = QLineEdit()

    grid.add_row("SLC folder", editor)

    assert grid.layout.columnMinimumWidth(0) == ParameterGrid.LABEL_COLUMN_WIDTH
    assert grid.layout.rowMinimumHeight(1) == ParameterGrid.ROW_MIN_HEIGHT
    assert editor.minimumHeight() >= ParameterGrid.EDITOR_MIN_HEIGHT


def test_results_hidden_visualization_rows_do_not_leave_blank_space():
    app = _qt_app()
    page = ResultsPage()
    page.resize(1280, 720)
    page.show()
    product = ResultProduct(
        "wrapped_interferogram:20240101_20240113:filtered",
        "wrapped_interferogram",
        "/tmp/filt_fine.int.vrt",
        "INT",
        reference_date="20240101",
        secondary_date="20240113",
        variant="filtered",
    )
    page.set_products([product], product.product_id)
    page.set_product_kind(product.kind)
    app.processEvents()

    assert page.render_style_combo.isVisible()
    assert page.brightness_spin.isVisible()
    assert page.range_mode_combo.isHidden()
    assert page.preview_panel.width() > 1000

    page.render_style_combo.setCurrentIndex(page.render_style_combo.findData("phase"))
    page.set_product_kind(product.kind)
    assert page.brightness_spin.isHidden()

    page.set_product_kind("coherence")
    assert page.render_style_combo.isHidden()
    assert page.preview_panel.color_legend.isVisible()
    assert not page.colormap_combo.isHidden()
    page.close()


def test_footprint_map_empty_startup_does_not_show_no_geometry_note():
    _qt_app()
    widget = FootprintMapWidget()

    html = widget._leaflet_html({}, [], fit_bounds=True)

    assert "No footprint geometry available for current results." not in html


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


def test_nested_text_view_routes_boundary_wheel_to_data_page_scroll():
    app = _qt_app()
    outer = QScrollArea()
    outer.setWidgetResizable(True)
    content = QWidget()
    content.setMinimumHeight(900)
    layout = QVBoxLayout(content)
    inner = QPlainTextEdit("short text")
    inner.setMaximumHeight(100)
    layout.addWidget(inner)
    layout.addStretch(1)
    outer.setWidget(content)
    outer.resize(300, 180)
    outer.show()
    scroll_filter = NestedScrollFilter(inner, outer)
    inner.viewport().installEventFilter(scroll_filter)
    app.processEvents()

    outer_bar = outer.verticalScrollBar()
    outer_bar.setValue(outer_bar.minimum())
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

    QApplication.sendEvent(inner.viewport(), event)

    assert outer_bar.value() > outer_bar.minimum()
    outer.close()


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
    logo_label = page.findChild(QLabel, "startBrandLogo")
    assert logo_label is not None
    assert logo_label.pixmap() is not None
    assert logo_label.pixmap().isNull() is False
    assert "InSAR-PILOT" in page.version_label.text()
    assert "9.9.9" in page.version_label.text()
    assert "Project folders are required." in page.notice_label.text()
    recent_row = page.recent_list.itemWidget(page.recent_list.item(0))
    assert recent_row is not None
    recent_labels = recent_row.findChildren(QLabel)
    assert recent_labels
    for label in recent_labels:
        assert label.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction


def test_main_window_uses_four_industrial_workflow_pages(monkeypatch):
    from insar_pilot.ui import main_window as main_window_module
    from insar_pilot.ui.main_window import MainWindow

    class _FixedSettings:
        def language(self):
            return "en"

        def set_language(self, language):
            self.language_value = language

        def theme(self):
            return "light"

        def set_theme(self, theme):
            self.theme_value = theme

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
    _disable_startup_account_checks(monkeypatch)
    monkeypatch.setattr(main_window_module, "AppSettings", _FixedSettings)
    window = MainWindow(create_default_project())
    try:
        assert window.windowTitle() == "InSAR-PILOT"
        assert window.windowIcon().isNull() is False
        assert isinstance(window.workflow_stepper, TopWorkflowStepper)
        step_labels = [
            button.text()
            for button in window.workflow_stepper.findChildren(QPushButton)
            if button.objectName() == "topWorkflowStepButton"
        ]
        assert step_labels == ["Data", "Setup", "Run", "Results"]
        assert window.workflow_stepper.parent().objectName() == "toolbarContext"
        assert window.toolbar_context.parentWidget() is window.main_toolbar
        assert not window.findChild(QWidget, "projectHeader")
        assert window.header_project_label.maximumWidth() == 220
        assert window.header_current_step_label.maximumWidth() == 140
        assert window.data_download_page.header.isHidden()
        assert window.processing_setup_page.header.isHidden()
        assert window.run_monitor_page.header.isHidden()
        assert not hasattr(window.results_page, "header")
        assert window.page_stack.count() == 5
        assert not hasattr(window, "legacy_data_sources_page")
        assert not hasattr(window, "legacy_aoi_iw_page")
        assert not hasattr(window, "legacy_processing_page")
        assert isinstance(window.log_view, LogConsole)
        assert window.log_view.document().maximumBlockCount() == LogConsole.DEFAULT_MAX_BLOCKS
        assert isinstance(window.data_download_page.log_text, LogConsole)
        assert isinstance(window.download_controller._short_task_pool, BackgroundTaskPool)
        assert not hasattr(window.download_controller, "_credential_thread")
        assert not hasattr(window.download_controller, "_tianditu_thread")
        assert not hasattr(window.download_controller, "_opentopography_thread")
        assert window.page_stack.currentWidget() is window.project_start_page
        assert window.minimumWidth() >= 1366
        assert not hasattr(window, "body_splitter")
        assert not hasattr(window, "workflow_nav")
        assert window.project_inspector_dock.windowTitle() == "Project Inspector"
        assert window.project_inspector_dock.isVisible() is False
        assert window.log_dock.isHidden()
        window.run_controller._handle_runner_state_changed("running")
        assert window.log_dock.isHidden()
        assert window.menuBar().actions()[0].text() == "Project"
        assert window.view_menu.title() == "View"
        assert any(action.text() == "Project Inspector" for action in window.view_menu.actions())
        assert window.main_toolbar.objectName() == "mainWorkflowToolbar"
        assert not hasattr(window, "new_button")
        assert not hasattr(window, "open_button")
        assert not hasattr(window, "save_button")
        assert all(
            not button.isEnabled()
            for button in window.workflow_stepper.findChildren(QPushButton)
            if button.objectName() == "topWorkflowStepButton"
        )
        assert window.data_sources_page is window.processing_setup_page
        assert window.aoi_iw_page is window.processing_setup_page
        assert window.processing_page is window.processing_setup_page
        window.resize(1366, 768)
        window.resize(1600, 980)
        assert "ISCE" not in window.windowTitle().upper()
        assert "ISCE" not in window.header_project_label.text().upper()
        assert isinstance(window.run_monitor_page.run_step_monitor, RunStepMonitor)
        assert not hasattr(window.results_page, "visual_parameter_grid")
        assert window.results_page.preview_panel.minimumHeight() >= 360
        combos = window.findChildren(QComboBox)
        assert combos
        assert all(combo.property(WHEEL_GUARD_PROPERTY) for combo in combos)
        buttons = window.findChildren(QAbstractButton)
        assert buttons
        # Buttons stay keyboard-focusable (tab) but never grab focus on click.
        assert all(button.focusPolicy() == Qt.FocusPolicy.TabFocus for button in buttons)
        assert all(button.property(WHEEL_PASSTHROUGH_PROPERTY) for button in buttons)
        spin_boxes = window.findChildren(QSpinBox)
        assert spin_boxes
        assert all(spin.property(WHEEL_PASSTHROUGH_PROPERTY) for spin in spin_boxes)
    finally:
        window.close()


def test_main_window_applies_language_and_theme_without_rebuilding(monkeypatch):
    from insar_pilot.i18n import set_shared_language
    from insar_pilot.ui import main_window as main_window_module
    from insar_pilot.ui.main_window import MainWindow

    class _LiveSettings:
        def __init__(self):
            self.language_value = "en"
            self.theme_value = "light"

        def language(self):
            return self.language_value

        def set_language(self, language):
            self.language_value = language

        def theme(self):
            return self.theme_value

        def set_theme(self, theme):
            self.theme_value = theme

        def restore_splitter(self, name, splitter):
            return False

        def save_splitter(self, name, splitter):
            return None

        def restore_dock_visibility(self, name, dock, *, default_visible=False):
            dock.setVisible(default_visible)

        def save_dock_visibility(self, name, dock):
            return None

        def recent_projects(self):
            return []

        def sync(self):
            return None

    app = _qt_app()
    _disable_startup_account_checks(monkeypatch)
    apply_theme(app, "light")
    monkeypatch.setattr(main_window_module, "AppSettings", _LiveSettings)
    window = MainWindow(create_default_project())
    runner = window.runner
    setup_page = window.processing_setup_page
    page_icons = [
        button.icon().cacheKey()
        for button in setup_page.findChildren(QPushButton)
        if not button.icon().isNull()
    ]
    try:
        chinese_action = next(
            action for action in window.language_action_group.actions() if action.data() == "zh"
        )
        chinese_action.trigger()
        app.processEvents()

        assert window.app_settings.language() == "zh"
        assert window.view_menu.title() == "视图"
        assert window.action_save_project.text() == "保存项目"
        assert window.action_exit.text() == "退出"
        assert window.menuBar().actions()[0].text() == "项目"
        assert window.run_monitor_page.run_step_monitor.steps_tree.headerItem().text(2) == "退出码"
        assert window.runner is runner
        assert window.processing_setup_page is setup_page

        dark_action = next(action for action in window.theme_action_group.actions() if action.data() == "dark")
        dark_action.trigger()
        app.processEvents()

        assert window.app_settings.theme() == "dark"
        assert active_tokens() is DARK_TOKENS
        assert app.styleSheet()
        refreshed_icons = [
            button.icon().cacheKey()
            for button in setup_page.findChildren(QPushButton)
            if not button.icon().isNull()
        ]
        assert refreshed_icons != page_icons
        assert window.runner is runner
        assert window.processing_setup_page is setup_page

        english_action = next(
            action for action in window.language_action_group.actions() if action.data() == "en"
        )
        english_action.trigger()
        app.processEvents()
        assert window.view_menu.title() == "View"
        assert window.action_save_project.text() == "Save Project"
        assert window.action_exit.text() == "Exit"
        assert window.run_monitor_page.current_step_card.title_label.text() == "Current Step"
        assert window.run_monitor_page.work_dir_card.title_label.text() == "Work Directory"
        assert window.run_monitor_page.run_wizard_bar.run_button.text() == "Run Next"
        assert window.processing_setup_page.iw_swaths_label.text() == "IW swaths"
        assert window.processing_setup_page.setup_step_tree.headerItem().text(1) == "State"
        assert window.data_download_page.results_table.horizontalHeaderItem(4).text() == "orbit_direction"
    finally:
        window.close()
        set_shared_language("en")
        apply_theme(app, "light")
        assert active_tokens() is LIGHT_TOKENS
