"""Specialized widget QSS."""

WIDGET_QSS = """
QListWidget#workflowNav {
    background: #ffffff;
    border: 1px solid #bfc7d1;
    border-radius: 2px;
    padding: 2px;
    selection-background-color: #cfe3f8;
    selection-color: #1f2329;
}
QListWidget#workflowNav::item {
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
    margin: 0;
}
QListWidget#workflowNav::item:hover,
QListWidget#workflowNav::item:selected {
    background: transparent;
}
QFrame#workflowNavItem {
    background: #ffffff;
    border: 1px solid transparent;
    border-radius: 1px;
}
QFrame#workflowNavItem[selected="true"] {
    background: #cfe3f8;
    border: 1px solid #7fa8d3;
}
QLabel#workflowNavItemTitle {
    color: #20242b;
    font-size: 12pt;
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
    font-size: 12pt;
    font-weight: 600;
    color: #20242b;
}
QDockWidget {
    color: #243245;
}
QDockWidget::title {
    background: #eef3f8;
    padding: 8px;
    border-bottom: 1px solid #d2dbe8;
}
QWidget#projectHeader {
    background: #f7f9fb;
    border-bottom: 1px solid #d3dbe6;
}
QFrame#projectHeaderMeta {
    background: #ffffff;
    border: 1px solid #d6dde7;
    border-radius: 2px;
}
QFrame#projectHeaderMeta QLabel {
    color: #263343;
}
QFrame#topWorkflowStepper {
    background: #eef2f6;
    border: 1px solid #cad3df;
    border-radius: 2px;
}
QPushButton#topWorkflowStepButton {
    background: #f9fbfd;
    border: 1px solid transparent;
    border-radius: 2px;
    color: #243042;
    font-weight: 700;
    min-width: 92px;
    min-height: 32px;
    padding: 4px 10px;
}
QPushButton#topWorkflowStepButton:hover {
    background: #edf5fd;
    border-color: #8fb5dd;
}
QPushButton#topWorkflowStepButton:checked {
    background: #d7e9fb;
    border-color: #5d91c4;
    color: #18395b;
}
QPushButton#topWorkflowStepButton:pressed {
    background: #bfdaf2;
    padding: 5px 9px 3px 11px;
}
QPushButton#topWorkflowStepButton:disabled {
    color: #9aa4b2;
    background: #f3f5f8;
    border-color: transparent;
}
QPushButton#topWorkflowStepButton[stepState="ready"],
QPushButton#topWorkflowStepButton[stepState="success"] {
    border-bottom: 3px solid #3f8f5c;
}
QPushButton#topWorkflowStepButton[stepState="warning"] {
    border-bottom: 3px solid #c2903d;
}
QPushButton#topWorkflowStepButton[stepState="failed"] {
    border-bottom: 3px solid #b95555;
}
QWidget#projectStartPage {
    background: #f5f6f8;
}
QFrame#startRecentPanel,
QFrame#startActionPanel,
QFrame#startInfoPanel,
QFrame#startNoticePanel {
    background: #ffffff;
    border: 1px solid #c6ced8;
    border-radius: 2px;
}
QLabel#startPanelTitle {
    font-size: 16pt;
    font-weight: 700;
    color: #1f2329;
}
QLabel#startPanelHint,
QLabel#startInfoText,
QLabel#startNoticeText,
QLabel#startEmptyText {
    color: #586270;
    line-height: 140%;
}
QLabel#startInfoText {
    color: #243042;
    font-weight: 700;
}
QListWidget#startRecentList {
    background: #ffffff;
    border: 1px solid #d2dbe7;
    border-radius: 2px;
    padding: 4px;
}
QListWidget#startRecentList::item {
    border: 1px solid transparent;
    border-radius: 2px;
    margin: 4px;
}
QListWidget#startRecentList::item:hover {
    background: #edf5fd;
    border-color: #b8cfe7;
}
QListWidget#startRecentList::item:selected {
    background: #d7e9fb;
    border-color: #6f9ccc;
}
QWidget#startRecentRow {
    background: transparent;
}
QWidget#startEmptyRow {
    background: transparent;
}
QLabel#startRecentIcon {
    background: #eef4fb;
    border: 1px solid #c9d6e5;
    border-radius: 2px;
}
QLabel#startRecentName {
    color: #1f2329;
    font-size: 13pt;
    font-weight: 700;
}
QLabel#startRecentPath {
    color: #4f5c6e;
}
QLabel#startRecentStatus {
    color: #2f6b45;
    font-weight: 600;
}
QLabel#startRecentStatus[missing="true"] {
    color: #843232;
}
QWidget#dataControlPanel,
QWidget#dataMapWorkspace,
QFrame#dataMapWorkspace {
    background: #ffffff;
}
QFrame#dataMapWorkspace {
    border-left: 2px solid #aeb9c7;
}
QWidget#dataControlPanel QLabel,
QWidget#dataMapWorkspace QLabel,
QFrame#dataMapWorkspace QLabel {
    background: transparent;
}
QWidget#dataControlPanel QPlainTextEdit {
    background: #fbfcfe;
}
QSplitter#dataMainSplitter::handle {
    background: #d6dde7;
    width: 12px;
    border-left: 1px solid #aeb9c7;
    border-right: 1px solid #cfd7e3;
}
QSplitter#dataMainSplitter::handle:hover,
QSplitter#dataMainSplitter::handle:pressed {
    background: #b9c9dc;
    border-left: 1px solid #7895b4;
    border-right: 1px solid #7895b4;
}
QSplitter#dataMapResultsSplitter::handle {
    background: #d6dde7;
    height: 8px;
    border-top: 1px solid #c3ccd8;
    border-bottom: 1px solid #c3ccd8;
}
QSplitter#dataMapResultsSplitter::handle:hover,
QSplitter#dataMapResultsSplitter::handle:pressed {
    background: #b9c9dc;
}
QFrame#collapsibleSection {
    background: #ffffff;
    border: 1px solid #bfc7d1;
    border-radius: 2px;
}
QFrame#collapsibleSection QToolButton {
    background: #f9fbfd;
    border: none;
    border-bottom: 1px solid #d6dde7;
    padding: 8px 10px;
    font-weight: 700;
    text-align: left;
}
QFrame#collapsibleSection QToolButton:hover {
    background: #edf4fb;
}
QFrame#collapsibleSection QWidget#collapsibleContent {
    background: #ffffff;
}
QFrame#collapsibleSection[density="compact"] QToolButton {
    padding: 6px 10px;
}
QFrame#collapsibleSection[density="compact"] QWidget#collapsibleContent {
    background: #ffffff;
}
QFrame#collapsibleSection[density="compact"] QLineEdit,
QFrame#collapsibleSection[density="compact"] QComboBox,
QFrame#collapsibleSection[density="compact"] QStackedWidget {
    min-height: 36px;
    max-height: 36px;
}
QFrame#collapsibleSection[density="compact"] QPushButton {
    min-height: 38px;
    max-height: 38px;
    padding-top: 5px;
    padding-bottom: 5px;
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
