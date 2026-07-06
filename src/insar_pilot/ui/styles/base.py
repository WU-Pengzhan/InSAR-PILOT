"""Base widget and control QSS."""

from insar_pilot.ui.styles.tokens import TOKENS

BASE_QSS = f"""
QWidget {{
    background: {TOKENS["background"]};
    color: {TOKENS["text"]};
    font-family: "Segoe UI", "Microsoft YaHei UI", "Noto Sans", "Ubuntu", "Arial", sans-serif;
    font-size: 12.5pt;
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
    border-radius: 2px;
    padding: 4px;
    min-height: 38px;
    selection-background-color: {TOKENS["selection"]};
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    min-height: 40px;
    padding: 7px 10px;
}}
QComboBox {{
    padding: 7px 44px 7px 10px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 38px;
    border-left: 1px solid {TOKENS["border"]};
    background: #e8edf3;
}}
QComboBox::drop-down:hover {{
    background: #ddebf9;
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
QPlainTextEdit:focus, QTreeWidget:focus, QTableWidget:focus, QListWidget:focus, QLineEdit:focus,
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {TOKENS["accent"]};
}}
QSplitter::handle {{
    background: #c7ced8;
    width: 2px;
    height: 2px;
}}
QSplitter::handle:hover {{
    background: #8fa2b8;
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
    background: #f6f7f9;
    border-bottom: 1px solid {TOKENS["border"]};
    spacing: 4px;
    padding: 3px;
}}
QPushButton {{
    background: #f6f7f9;
    color: #20242b;
    border: 1px solid {TOKENS["border_strong"]};
    border-radius: 2px;
    padding: 7px 16px;
    min-height: 40px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: #dcecfb;
    border-color: #5f8fbd;
}}
QPushButton:pressed {{
    background: #b8d2eb;
    border-color: #3f6f9f;
    padding: 8px 15px 6px 17px;
}}
QPushButton:disabled {{
    color: #8a96aa;
    background: #f2f5f9;
    border-color: #d6dde9;
}}
QPushButton[role="primary"] {{
    background: {TOKENS["accent"]};
    color: #ffffff;
    border: 1px solid #1e548a;
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{
    background: {TOKENS["accent_hover"]};
    border-color: #244a74;
}}
QPushButton[role="primary"]:pressed {{
    background: {TOKENS["accent_pressed"]};
    border-color: #0f365f;
    padding: 8px 15px 6px 17px;
}}
QPushButton[role="secondary"] {{
    background: {TOKENS["surface"]};
    color: #243042;
    border: 1px solid {TOKENS["border_strong"]};
}}
QPushButton[role="secondary"]:pressed {{
    background: #d2e4f6;
    border-color: #557fa8;
}}
QPushButton[role="danger"] {{
    background: #fff3f3;
    color: {TOKENS["error_text"]};
    border: 1px solid #dfb3b3;
    font-weight: 600;
}}
QPushButton[role="danger"]:hover {{
    background: #ffeaea;
}}
QPushButton[role="danger"]:pressed {{
    background: #f2caca;
    border-color: #be7e7e;
    padding: 8px 15px 6px 17px;
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    color: #20242b;
    padding: 5px 8px;
}}
QToolButton:hover {{
    background: #eaf2fb;
    border-color: #9eb8d4;
}}
QToolButton:pressed {{
    background: #c9deef;
    border-color: #6c93bb;
    padding: 6px 7px 4px 9px;
}}
QHeaderView::section {{
    background: #e9edf2;
    border: 0;
    border-right: 1px solid {TOKENS["border"]};
    border-bottom: 1px solid {TOKENS["border"]};
    padding: 8px 10px;
    font-weight: 600;
}}
QTableWidget::item,
QTreeWidget::item,
QListWidget::item {{
    min-height: 36px;
}}
QTableWidget::item:selected,
QTreeWidget::item:selected,
QListWidget::item:selected {{
    background: {TOKENS["selection"]};
    color: {TOKENS["text"]};
}}
"""
