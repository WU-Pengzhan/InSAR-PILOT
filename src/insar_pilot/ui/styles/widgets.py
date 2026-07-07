"""Specialized widget QSS."""

from insar_pilot.ui.styles.tokens import FONT_SIZES, LIGHT_TOKENS, RADIUS


def build_widget_qss(TOKENS: dict[str, str] = LIGHT_TOKENS) -> str:
    """Return the specialized-widget QSS for the given token palette."""

    return f"""
QListWidget#workflowNav {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
    padding: 2px;
    selection-background-color: {TOKENS["selection"]};
    selection-color: {TOKENS["text"]};
}}
QListWidget#workflowNav:focus {{
    border-color: {TOKENS["focus"]};
}}
QListWidget#workflowNav::item {{
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
    margin: 0;
}}
QListWidget#workflowNav::item:hover,
QListWidget#workflowNav::item:selected {{
    background: transparent;
}}
QFrame#workflowNavItem {{
    background: {TOKENS["surface"]};
    border: 1px solid transparent;
    border-radius: {RADIUS["sm"]}px;
}}
QFrame#workflowNavItem[selected="true"] {{
    background: {TOKENS["selection"]};
    border: 1px solid {TOKENS["checked_border"]};
}}
QLabel#workflowNavItemTitle {{
    color: {TOKENS["text"]};
    font-size: {FONT_SIZES["body"]}pt;
    font-weight: 600;
    background: transparent;
}}
QFrame#workflowNavItem[selected="true"] QLabel#workflowNavItemTitle {{
    color: {TOKENS["accent_pressed"]};
}}
QFrame#workflowNavItem QLabel[badge="true"] {{
    margin-left: 6px;
}}
QListWidget#workflowNav QLabel {{
    font-size: {FONT_SIZES["body"]}pt;
    font-weight: 600;
    color: {TOKENS["text"]};
}}
QDockWidget {{
    color: {TOKENS["text_subtle"]};
}}
QDockWidget::title {{
    background: {TOKENS["surface_alt"]};
    padding: 8px;
    border-bottom: 1px solid {TOKENS["border"]};
}}
QWidget#projectHeader {{
    background: {TOKENS["surface_alt"]};
    border-bottom: 1px solid {TOKENS["border"]};
}}
QFrame#projectHeaderMeta {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QFrame#projectHeaderMeta QLabel {{
    color: {TOKENS["text_subtle"]};
}}
QFrame#topWorkflowStepper {{
    background: {TOKENS["surface_alt"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QPushButton#topWorkflowStepButton {{
    background: {TOKENS["surface"]};
    border: 1px solid transparent;
    border-radius: {RADIUS["sm"]}px;
    color: {TOKENS["text"]};
    font-weight: 700;
    min-width: 92px;
    min-height: 32px;
    padding: 4px 10px;
}}
QPushButton#topWorkflowStepButton:hover {{
    background: {TOKENS["hover_bg"]};
    border-color: {TOKENS["hover_border"]};
}}
QPushButton#topWorkflowStepButton:checked {{
    background: {TOKENS["checked_bg"]};
    border-color: {TOKENS["checked_border"]};
    color: {TOKENS["accent_pressed"]};
}}
QPushButton#topWorkflowStepButton:pressed {{
    background: {TOKENS["pressed_bg"]};
    padding: 5px 9px 3px 11px;
}}
QPushButton#topWorkflowStepButton:focus {{
    border-color: {TOKENS["focus"]};
}}
QPushButton#topWorkflowStepButton:disabled {{
    color: {TOKENS["disabled_text"]};
    background: {TOKENS["disabled_bg"]};
    border-color: transparent;
}}
QPushButton#topWorkflowStepButton[stepState="ready"],
QPushButton#topWorkflowStepButton[stepState="success"] {{
    border-bottom: 3px solid {TOKENS["success_text"]};
}}
QPushButton#topWorkflowStepButton[stepState="warning"] {{
    border-bottom: 3px solid {TOKENS["warning_text"]};
}}
QPushButton#topWorkflowStepButton[stepState="failed"] {{
    border-bottom: 3px solid {TOKENS["error_text"]};
}}
QWidget#projectStartPage {{
    background: {TOKENS["surface_alt"]};
}}
QFrame#startRecentPanel,
QFrame#startActionPanel,
QFrame#startInfoPanel,
QFrame#startNoticePanel {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QLabel#startPanelTitle {{
    font-size: {FONT_SIZES["h2"]}pt;
    font-weight: 700;
    color: {TOKENS["text"]};
}}
QLabel#startPanelHint,
QLabel#startInfoText,
QLabel#startNoticeText,
QLabel#startEmptyText {{
    color: {TOKENS["text_muted"]};
    line-height: 140%;
}}
QLabel#startInfoText {{
    color: {TOKENS["text"]};
    font-weight: 700;
}}
QWidget#startBrandRow {{
    background: transparent;
}}
QLabel#startBrandLogo {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["md"]}px;
    padding: 3px;
}}
QLabel#startBrandName {{
    color: {TOKENS["accent_pressed"]};
    font-size: {FONT_SIZES["h1"]}pt;
    font-weight: 800;
}}
QLabel#startBrandSubtitle {{
    color: {TOKENS["text_muted"]};
    font-size: {FONT_SIZES["caption"]}pt;
}}
QListWidget#startRecentList {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
    padding: 4px;
}}
QListWidget#startRecentList::item {{
    border: 1px solid transparent;
    border-radius: {RADIUS["sm"]}px;
    margin: 4px;
}}
QListWidget#startRecentList::item:hover {{
    background: {TOKENS["hover_bg"]};
    border-color: {TOKENS["hover_border"]};
}}
QListWidget#startRecentList::item:selected {{
    background: {TOKENS["checked_bg"]};
    border-color: {TOKENS["checked_border"]};
}}
QWidget#startRecentRow {{
    background: transparent;
}}
QWidget#startEmptyRow {{
    background: transparent;
}}
QWidget#startRecentRow QLabel,
QWidget#startEmptyRow QLabel {{
    background: transparent;
}}
QLabel#startRecentIcon {{
    background: {TOKENS["hover_bg"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QLabel#startRecentName {{
    color: {TOKENS["text"]};
    font-size: {FONT_SIZES["h3"]}pt;
    font-weight: 700;
}}
QLabel#startRecentPath {{
    color: {TOKENS["text_muted"]};
}}
QLabel#startRecentStatus {{
    color: {TOKENS["success_text"]};
    font-weight: 600;
}}
QLabel#startRecentStatus[missing="true"] {{
    color: {TOKENS["error_text"]};
}}
QWidget#dataControlPanel,
QWidget#dataMapWorkspace,
QFrame#dataMapWorkspace {{
    background: {TOKENS["surface"]};
}}
QFrame#dataMapWorkspace {{
    border-left: 2px solid {TOKENS["border_strong"]};
}}
QWidget#dataControlPanel QLabel,
QWidget#dataMapWorkspace QLabel,
QFrame#dataMapWorkspace QLabel {{
    background: transparent;
}}
QWidget#dataControlPanel QPlainTextEdit {{
    background: {TOKENS["surface"]};
}}
QSplitter#dataMainSplitter::handle {{
    background: {TOKENS["border"]};
    width: 12px;
    border-left: 1px solid {TOKENS["border_strong"]};
    border-right: 1px solid {TOKENS["border"]};
}}
QSplitter#dataMainSplitter::handle:hover,
QSplitter#dataMainSplitter::handle:pressed {{
    background: {TOKENS["border_strong"]};
    border-left: 1px solid {TOKENS["pressed_border"]};
    border-right: 1px solid {TOKENS["pressed_border"]};
}}
QSplitter#dataMapResultsSplitter::handle {{
    background: {TOKENS["border"]};
    height: 8px;
    border-top: 1px solid {TOKENS["border"]};
    border-bottom: 1px solid {TOKENS["border"]};
}}
QSplitter#dataMapResultsSplitter::handle:hover,
QSplitter#dataMapResultsSplitter::handle:pressed {{
    background: {TOKENS["border_strong"]};
}}
QFrame#collapsibleSection {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QFrame#collapsibleSection QToolButton {{
    background: {TOKENS["surface_alt"]};
    border: none;
    border-bottom: 1px solid {TOKENS["border"]};
    padding: 8px 10px;
    font-weight: 700;
    text-align: left;
}}
QFrame#collapsibleSection QToolButton:hover {{
    background: {TOKENS["hover_bg"]};
}}
QFrame#collapsibleSection QWidget#collapsibleContent {{
    background: {TOKENS["surface"]};
}}
QFrame#collapsibleSection[density="compact"] QToolButton {{
    padding: 6px 10px;
}}
QFrame#collapsibleSection[density="compact"] QWidget#collapsibleContent {{
    background: {TOKENS["surface"]};
}}
QFrame#collapsibleSection[density="compact"] QLineEdit,
QFrame#collapsibleSection[density="compact"] QComboBox,
QFrame#collapsibleSection[density="compact"] QStackedWidget {{
    min-height: 32px;
    max-height: 32px;
}}
QFrame#collapsibleSection[density="compact"] QPushButton {{
    min-height: 32px;
    max-height: 32px;
    padding-top: 5px;
    padding-bottom: 5px;
}}
QCheckBox#iw1Check,
QCheckBox#iw2Check,
QCheckBox#iw3Check {{
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["lg"]}px;
    padding: 4px 8px;
    spacing: 6px;
    font-weight: 600;
}}
QCheckBox#iw1Check {{
    background: {TOKENS["info_bg"]};
    color: {TOKENS["info_text"]};
    border-color: {TOKENS["info_border"]};
}}
QCheckBox#iw2Check {{
    background: {TOKENS["success_bg"]};
    color: {TOKENS["success_text"]};
    border-color: {TOKENS["success_border"]};
}}
QCheckBox#iw3Check {{
    background: {TOKENS["warning_bg"]};
    color: {TOKENS["warning_text"]};
    border-color: {TOKENS["warning_border"]};
}}
QCheckBox#iw1Check::indicator,
QCheckBox#iw2Check::indicator,
QCheckBox#iw3Check::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {TOKENS["border_strong"]};
    border-radius: {RADIUS["sm"]}px;
    background: {TOKENS["surface"]};
}}
QCheckBox#iw1Check::indicator:checked {{
    background: {TOKENS["accent"]};
    border-color: {TOKENS["accent_pressed"]};
}}
QCheckBox#iw2Check::indicator:checked {{
    background: {TOKENS["success_text"]};
    border-color: {TOKENS["success_text"]};
}}
QCheckBox#iw3Check::indicator:checked {{
    background: {TOKENS["warning_text"]};
    border-color: {TOKENS["warning_text"]};
}}
QCheckBox#iw1Check:disabled,
QCheckBox#iw2Check:disabled,
QCheckBox#iw3Check:disabled {{
    color: {TOKENS["disabled_text"]};
    background: {TOKENS["disabled_bg"]};
    border-color: {TOKENS["disabled_border"]};
}}
"""


WIDGET_QSS = build_widget_qss()
