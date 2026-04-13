"""Light professional desktop stylesheet for the Stage 2 shell."""

from __future__ import annotations


def build_light_stylesheet() -> str:
    """Return the default light-only stylesheet for scientific desktop workflows."""

    return """
    QWidget {
        background: #f4f6f9;
        color: #202734;
        font-size: 11pt;
    }
    QMainWindow, QFrame, QScrollArea, QPlainTextEdit, QTreeWidget, QListWidget, QLineEdit,
    QComboBox, QSpinBox, QDoubleSpinBox {
        background: #ffffff;
        color: #202734;
    }
    QPlainTextEdit, QTreeWidget, QListWidget, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        border: 1px solid #cfd7e3;
        border-radius: 6px;
        padding: 6px;
        selection-background-color: #d9e9f8;
    }
    QSplitter::handle {
        background: #e2e8f0;
        width: 1px;
        height: 1px;
    }
    QPushButton {
        background: #ffffff;
        color: #243042;
        border: 1px solid #b7c6da;
        border-radius: 6px;
        padding: 8px 12px;
        min-height: 20px;
        font-weight: 500;
    }
    QPushButton:hover {
        background: #edf4fc;
        border-color: #7fa4cc;
    }
    QPushButton:pressed {
        background: #dde9f7;
        border-color: #5f86b2;
    }
    QPushButton:disabled {
        color: #8a96aa;
        background: #f2f5f9;
        border-color: #d6dde9;
    }
    QPushButton[role="primary"] {
        background: #2f5f94;
        color: #ffffff;
        border: 1px solid #2a5686;
        font-weight: 600;
    }
    QPushButton[role="primary"]:hover {
        background: #2a5686;
        border-color: #244a74;
    }
    QPushButton[role="primary"]:pressed {
        background: #244a74;
    }
    QPushButton[role="secondary"] {
        background: #ffffff;
        color: #243042;
        border: 1px solid #b7c6da;
    }
    QPushButton[role="secondary"]:hover {
        background: #edf4fc;
        border-color: #7fa4cc;
    }
    QPushButton[role="secondary"]:pressed {
        background: #dde9f7;
        border-color: #5f86b2;
    }
    QPushButton[role="danger"] {
        background: #fff3f3;
        color: #8a2d2d;
        border: 1px solid #dfb3b3;
        font-weight: 600;
    }
    QPushButton[role="danger"]:hover {
        background: #ffeaea;
    }
    QLabel#headerTitle {
        font-size: 17pt;
        font-weight: 700;
        color: #1f2a3a;
    }
    QLabel#headerSubTitle {
        color: #627084;
    }
    QFrame#summaryCard {
        background: #ffffff;
        border: 1px solid #d3dce8;
        border-radius: 8px;
    }
    QLabel#summaryCardTitle {
        color: #607187;
        font-size: 9.5pt;
        font-weight: 600;
        text-transform: uppercase;
    }
    QLabel#summaryCardValue {
        color: #202734;
        font-size: 12pt;
        font-weight: 700;
    }
    QLabel#summaryCardBody {
        color: #5e6a7d;
    }
    QLabel[emptyState="true"] {
        background: #f7f9fc;
        border: 1px dashed #c9d4e2;
        border-radius: 6px;
        color: #55657b;
        padding: 10px;
    }
    QLabel[badge="true"] {
        border-radius: 10px;
        padding: 2px 6px;
        font-size: 8.5pt;
        font-weight: 700;
    }
    QLabel[badge="true"][tone="neutral"] {
        background: #ebeff5;
        color: #4a596e;
    }
    QLabel[badge="true"][tone="ready"],
    QLabel[badge="true"][tone="success"] {
        background: #e7f4ec;
        color: #2f6b45;
    }
    QLabel[badge="true"][tone="running"] {
        background: #e8f2fb;
        color: #2f5f94;
    }
    QLabel[badge="true"][tone="warning"] {
        background: #fff3df;
        color: #8a6532;
    }
    QLabel[badge="true"][tone="failed"],
    QLabel[badge="true"][tone="error"] {
        background: #fdeaea;
        color: #8a2d2d;
    }
    QToolButton {
        background: transparent;
        border: none;
        color: #2d3a4c;
        font-weight: 600;
        padding: 4px 0;
    }
    QListWidget#workflowNav {
        background: #ffffff;
        border: 1px solid #d0d9e6;
        border-radius: 8px;
        padding: 6px;
        selection-background-color: #e7f1fb;
        selection-color: #1f3550;
    }
    QListWidget#workflowNav::item {
        background: transparent;
        border: none;
        border-radius: 0;
        padding: 0;
        margin: 0;
    }
    QListWidget#workflowNav::item:hover {
        background: transparent;
    }
    QListWidget#workflowNav::item:selected {
        background: transparent;
        color: #1f3550;
    }
    QFrame#workflowNavItem {
        background: #ffffff;
        border: 1px solid transparent;
        border-radius: 6px;
    }
    QFrame#workflowNavItem[selected="true"] {
        background: #e3eefb;
        border: 1px solid #93b4da;
    }
    QLabel#workflowNavItemTitle {
        color: #243245;
        font-size: 11pt;
        font-weight: 600;
        background: transparent;
    }
    QFrame#workflowNavItem[selected="true"] QLabel#workflowNavItemTitle {
        color: #1f3550;
    }
    QFrame#workflowNavItem QLabel[badge="true"] {
        margin-left: 6px;
    }
    QListWidget#workflowNav QLabel {
        font-size: 11pt;
        font-weight: 600;
        color: #243245;
    }
    QDockWidget {
        color: #243245;
    }
    QDockWidget::title {
        background: #eef3f8;
        padding: 8px;
        border-bottom: 1px solid #d2dbe8;
    }
    QCheckBox#iw1Check,
    QCheckBox#iw2Check,
    QCheckBox#iw3Check {
        border: 1px solid #c7d4e4;
        border-radius: 6px;
        padding: 4px 8px;
        spacing: 6px;
        font-weight: 600;
    }
    QCheckBox#iw1Check {
        background: #eef3f9;
        color: #2d425d;
        border-color: #c4d2e2;
    }
    QCheckBox#iw2Check {
        background: #edf6ef;
        color: #2f5a3b;
        border-color: #bfd8c5;
    }
    QCheckBox#iw3Check {
        background: #fbf2e7;
        color: #6a4e2a;
        border-color: #e0cdb4;
    }
    QCheckBox#iw1Check::indicator,
    QCheckBox#iw2Check::indicator,
    QCheckBox#iw3Check::indicator {
        width: 14px;
        height: 14px;
        border: 1px solid #8ea0b6;
        border-radius: 3px;
        background: #ffffff;
    }
    QCheckBox#iw1Check::indicator:checked {
        background: #8aa1bd;
        border-color: #708aa7;
    }
    QCheckBox#iw2Check::indicator:checked {
        background: #7cbf87;
        border-color: #5b9d66;
    }
    QCheckBox#iw3Check::indicator:checked {
        background: #d6a061;
        border-color: #b88245;
    }
    QCheckBox#iw1Check:disabled,
    QCheckBox#iw2Check:disabled,
    QCheckBox#iw3Check:disabled {
        color: #8a96aa;
        background: #f2f5f9;
        border-color: #d6dde9;
    }
    """
