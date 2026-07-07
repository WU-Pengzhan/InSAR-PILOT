"""Reusable component QSS."""

from insar_pilot.ui.styles.tokens import FONT_SIZES, LIGHT_TOKENS, RADIUS


def build_component_qss(TOKENS: dict[str, str] = LIGHT_TOKENS) -> str:
    """Return the reusable-component QSS for the given token palette."""

    return f"""
QLabel#headerTitle {{
    font-size: {FONT_SIZES["h2"]}pt;
    font-weight: 700;
    color: {TOKENS["text"]};
}}
QLabel#headerSubTitle {{
    color: {TOKENS["text_muted"]};
}}
QFrame#summaryCard,
QFrame#sectionPanel,
QFrame#taskProgressPanel {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QFrame#summaryCard[flatSummary="true"] {{
    background: transparent;
    border: none;
    border-top: 1px solid {TOKENS["border"]};
    border-radius: 0;
}}
QFrame#summaryCard[flatSummary="true"] QLabel#summaryCardTitle {{
    color: {TOKENS["text_subtle"]};
}}
QFrame#summaryCard[flatSummary="true"] QLabel#summaryCardBody {{
    color: {TOKENS["text_muted"]};
}}
QFrame#sectionPanel {{
    background: {TOKENS["surface"]};
}}
QFrame#pageHeader {{
    background: transparent;
    border: none;
}}
QFrame#actionBar {{
    background: {TOKENS["surface_alt"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QLabel#pageHeaderTitle {{
    color: {TOKENS["text"]};
    font-size: {FONT_SIZES["h2"]}pt;
    font-weight: 700;
}}
QLabel#pageHeaderSubtitle {{
    color: {TOKENS["text_muted"]};
}}
QLabel#sectionPanelTitle,
QLabel#summaryCardTitle {{
    color: {TOKENS["text_subtle"]};
    font-size: {FONT_SIZES["body_lg"]}pt;
    font-weight: 600;
}}
QLabel#summaryCardValue {{
    color: {TOKENS["text"]};
    font-size: {FONT_SIZES["h3"]}pt;
    font-weight: 700;
}}
QLabel#summaryCardBody {{
    color: {TOKENS["text_muted"]};
}}
QLabel[formLabel="true"] {{
    background: transparent;
    color: {TOKENS["text_subtle"]};
    padding: 0;
    margin: 0;
}}
QLabel[emptyState="true"],
QFrame#emptyState {{
    background: transparent;
    border: none;
    border-radius: 0;
    color: {TOKENS["text_muted"]};
    padding: 4px 2px;
}}
QFrame#statusStrip {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QFrame#preflightCheckItem {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QFrame#commandPreview {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QFrame#parameterGrid {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QLabel#parameterGridTitle {{
    background: {TOKENS["surface_muted"]};
    border-bottom: 1px solid {TOKENS["border"]};
    color: {TOKENS["text"]};
    font-size: {FONT_SIZES["body_lg"]}pt;
    font-weight: 700;
    padding: 5px 8px;
    min-height: 30px;
}}
QLabel#parameterGridLabel {{
    background: {TOKENS["surface_alt"]};
    border-right: 1px solid {TOKENS["border"]};
    border-bottom: 1px solid {TOKENS["border"]};
    color: {TOKENS["text_subtle"]};
    padding: 3px 8px;
    min-width: 185px;
    max-width: 185px;
    min-height: 34px;
}}
QFrame#parameterGrid QLineEdit,
QFrame#parameterGrid QComboBox,
QFrame#parameterGrid QSpinBox,
QFrame#parameterGrid QDoubleSpinBox {{
    border-radius: 0;
    border-left: 0;
    border-top: 0;
    border-right: 0;
    min-height: 32px;
    padding-top: 4px;
    padding-bottom: 4px;
}}
QFrame#parameterGrid QComboBox {{
    padding-left: 8px;
    padding-right: 32px;
}}
QFrame#propertyForm {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QLabel#propertyFormTitle {{
    color: {TOKENS["text"]};
    font-size: {FONT_SIZES["body_lg"]}pt;
    font-weight: 700;
    padding-bottom: 4px;
}}
QLabel#propertyFormLabel {{
    background: transparent;
    color: {TOKENS["text_subtle"]};
    padding: 0 8px 0 0;
}}
QFrame#propertyForm QLineEdit,
QFrame#propertyForm QComboBox,
QFrame#propertyForm QSpinBox,
QFrame#propertyForm QDoubleSpinBox {{
    min-height: 32px;
}}
QFrame#propertyForm QPushButton {{
    min-height: 32px;
    padding-top: 4px;
    padding-bottom: 4px;
}}
QFrame#propertyForm QCheckBox {{
    padding-top: 4px;
    padding-bottom: 4px;
}}
QLabel#runtimeSummaryLabel {{
    color: {TOKENS["text_muted"]};
    padding: 2px 0 6px 0;
}}
QFrame#wizardActionBar {{
    background: {TOKENS["surface_alt"]};
    border-top: 1px solid {TOKENS["border"]};
}}
QTreeWidget#workflowStepTree {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QFrame#runStepMonitor {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
QFrame#technicalDetailsPanel {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: {RADIUS["sm"]}px;
}}
"""


COMPONENT_QSS = build_component_qss()
