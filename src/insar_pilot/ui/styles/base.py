"""Base widget and control QSS."""

from insar_pilot.ui.styles.tokens import FONT_SIZES, LIGHT_TOKENS, RADIUS


def build_base_qss(TOKENS: dict[str, str] = LIGHT_TOKENS) -> str:
    """Return the base widget/control QSS for the given token palette."""

    return f"""
QWidget {{
    background: {TOKENS["background"]};
    color: {TOKENS["text"]};
    font-family: "Segoe UI", "Microsoft YaHei UI", "Noto Sans", "Ubuntu", "Arial", sans-serif;
    font-size: {FONT_SIZES["body_lg"]}pt;
}}
QLabel {{
    background: transparent;
}}
QMainWindow, QMenuBar, QMenu, QToolBar, QStatusBar, QFrame, QScrollArea, QPlainTextEdit,
QTreeWidget, QTableWidget, QListWidget, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {TOKENS["surface"]};
    color: {TOKENS["text"]};
}}
QPlainTextEdit, QTreeWidget, QTableWidget, QListWidget, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
    padding: 4px;
    min-height: 32px;
    selection-background-color: {TOKENS["selection"]};
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    min-height: 32px;
    padding: 5px 10px;
}}
QComboBox {{
    padding: 5px 44px 5px 10px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 34px;
    border-left: 1px solid {TOKENS["border"]};
    background: {TOKENS["surface_muted"]};
}}
QComboBox::drop-down:hover {{
    background: {TOKENS["hover_bg"]};
}}
QComboBox::down-arrow {{
    image: url(:/qt-project.org/styles/commonstyle/images/arrow-down-16.png);
    width: 16px;
    height: 16px;
    margin: 0;
}}
QSpinBox, QDoubleSpinBox {{
    padding-right: 22px;
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover,
QPlainTextEdit:hover, QTreeWidget:hover, QTableWidget:hover, QListWidget:hover {{
    border-color: {TOKENS["border_strong"]};
}}
QPlainTextEdit:focus, QTreeWidget:focus, QTableWidget:focus, QListWidget:focus, QLineEdit:focus,
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {TOKENS["focus"]};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QPlainTextEdit:disabled {{
    color: {TOKENS["disabled_text"]};
    background: {TOKENS["disabled_bg"]};
    border-color: {TOKENS["disabled_border"]};
}}
QSplitter::handle {{
    background: {TOKENS["border"]};
    width: 2px;
    height: 2px;
}}
QSplitter::handle:hover {{
    background: {TOKENS["border_strong"]};
}}
QMenuBar {{
    border-bottom: 1px solid {TOKENS["border"]};
    padding: 1px 4px;
}}
QMenuBar::item {{
    padding: 4px 8px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: {TOKENS["selection"]};
}}
QMenu {{
    border: 1px solid {TOKENS["border_strong"]};
    padding: 4px;
}}
QMenu::item {{
    padding: 4px 22px 4px 22px;
}}
QMenu::item:selected {{
    background: {TOKENS["selection"]};
}}
QToolBar {{
    background: {TOKENS["surface_alt"]};
    border-bottom: 1px solid {TOKENS["border"]};
    spacing: 4px;
    padding: 3px;
}}
QPushButton {{
    background: {TOKENS["surface_alt"]};
    color: {TOKENS["text"]};
    border: 1px solid {TOKENS["border_strong"]};
    border-radius: {RADIUS["sm"]}px;
    padding: 6px 16px;
    min-height: 32px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {TOKENS["hover_bg"]};
    border-color: {TOKENS["hover_border"]};
}}
QPushButton:pressed {{
    background: {TOKENS["pressed_bg"]};
    border-color: {TOKENS["pressed_border"]};
    padding: 7px 15px 5px 17px;
}}
QPushButton:focus {{
    border-color: {TOKENS["focus"]};
}}
QPushButton:disabled {{
    color: {TOKENS["disabled_text"]};
    background: {TOKENS["disabled_bg"]};
    border-color: {TOKENS["disabled_border"]};
}}
QPushButton[role="primary"] {{
    background: {TOKENS["accent"]};
    color: {TOKENS["on_accent"]};
    border: 1px solid {TOKENS["accent_pressed"]};
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{
    background: {TOKENS["accent_hover"]};
    border-color: {TOKENS["accent_pressed"]};
}}
QPushButton[role="primary"]:pressed {{
    background: {TOKENS["accent_pressed"]};
    border-color: {TOKENS["accent_pressed"]};
    padding: 7px 15px 5px 17px;
}}
QPushButton[role="primary"]:focus {{
    border-color: {TOKENS["accent_pressed"]};
}}
QPushButton[role="secondary"] {{
    background: {TOKENS["surface"]};
    color: {TOKENS["text"]};
    border: 1px solid {TOKENS["border_strong"]};
}}
QPushButton[role="secondary"]:hover {{
    background: {TOKENS["hover_bg"]};
    border-color: {TOKENS["hover_border"]};
}}
QPushButton[role="secondary"]:pressed {{
    background: {TOKENS["pressed_bg"]};
    border-color: {TOKENS["pressed_border"]};
}}
QPushButton[role="secondary"]:disabled {{
    color: {TOKENS["disabled_text"]};
    background: {TOKENS["disabled_bg"]};
    border-color: {TOKENS["disabled_border"]};
}}
QPushButton[role="danger"] {{
    background: {TOKENS["danger_bg"]};
    color: {TOKENS["error_text"]};
    border: 1px solid {TOKENS["error_border"]};
    font-weight: 600;
}}
QPushButton[role="danger"]:hover {{
    background: {TOKENS["error_bg"]};
}}
QPushButton[role="danger"]:pressed {{
    background: {TOKENS["danger_pressed_bg"]};
    border-color: {TOKENS["danger_pressed_border"]};
    padding: 7px 15px 5px 17px;
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    color: {TOKENS["text"]};
    border-radius: {RADIUS["sm"]}px;
    padding: 5px 8px;
}}
QToolButton:hover {{
    background: {TOKENS["hover_bg"]};
    border-color: {TOKENS["hover_border"]};
}}
QToolButton:pressed {{
    background: {TOKENS["pressed_bg"]};
    border-color: {TOKENS["pressed_border"]};
    padding: 6px 7px 4px 9px;
}}
QToolButton:focus {{
    border-color: {TOKENS["focus"]};
}}
QCheckBox {{
    spacing: 6px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {TOKENS["border_strong"]};
    border-radius: {RADIUS["sm"]}px;
    background: {TOKENS["surface"]};
}}
QCheckBox::indicator:hover {{
    border-color: {TOKENS["accent"]};
}}
QCheckBox::indicator:checked {{
    background: {TOKENS["accent"]};
    border-color: {TOKENS["accent_pressed"]};
    image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png);
}}
QCheckBox:focus {{
    color: {TOKENS["text"]};
}}
QCheckBox:disabled {{
    color: {TOKENS["disabled_text"]};
}}
QCheckBox::indicator:disabled {{
    border-color: {TOKENS["disabled_border"]};
    background: {TOKENS["disabled_bg"]};
}}
QHeaderView::section {{
    background: {TOKENS["surface_muted"]};
    border: 0;
    border-right: 1px solid {TOKENS["border"]};
    border-bottom: 1px solid {TOKENS["border"]};
    padding: 8px 10px;
    font-weight: 600;
}}
QTableWidget::item,
QTreeWidget::item,
QListWidget::item {{
    min-height: 34px;
}}
QTableWidget::item:selected,
QTreeWidget::item:selected,
QListWidget::item:selected {{
    background: {TOKENS["selection"]};
    color: {TOKENS["text"]};
}}
QProgressBar {{
    background: {TOKENS["surface_muted"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
    text-align: center;
    color: {TOKENS["text"]};
    min-height: 18px;
}}
QProgressBar::chunk {{
    background: {TOKENS["accent"]};
    border-radius: {RADIUS["sm"]}px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {TOKENS["border_strong"]};
    min-height: 28px;
    border-radius: {RADIUS["sm"]}px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TOKENS["accent_hover"]};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {TOKENS["border_strong"]};
    min-width: 28px;
    border-radius: {RADIUS["sm"]}px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {TOKENS["accent_hover"]};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
    background: transparent;
    border: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QToolTip {{
    background: {TOKENS["surface"]};
    color: {TOKENS["text"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["md"]}px;
    padding: 4px 8px;
}}
"""


BASE_QSS = build_base_qss()
