"""Reusable component QSS."""

from insar_pilot.ui.styles.tokens import TOKENS

COMPONENT_QSS = f"""
QLabel#headerTitle {{
    font-size: 15pt;
    font-weight: 700;
    color: #1f2329;
}}
QLabel#headerSubTitle {{
    color: #586270;
}}
QFrame#summaryCard,
QFrame#sectionPanel,
QFrame#taskProgressPanel {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: 2px;
}}
QFrame#summaryCard[flatSummary="true"] {{
    background: transparent;
    border: none;
    border-top: 1px solid {TOKENS["border"]};
    border-radius: 0;
}}
QFrame#summaryCard[flatSummary="true"] QLabel#summaryCardTitle {{
    color: #4a5665;
}}
QFrame#summaryCard[flatSummary="true"] QLabel#summaryCardBody {{
    color: #586270;
}}
QFrame#sectionPanel {{
    background: {TOKENS["surface"]};
}}
QFrame#pageHeader {{
    background: transparent;
    border: none;
}}
QFrame#actionBar {{
    background: #f4f6f8;
    border: 1px solid {TOKENS["border"]};
    border-radius: 2px;
}}
QLabel#pageHeaderTitle {{
    color: #1f2329;
    font-size: 15pt;
    font-weight: 700;
}}
QLabel#pageHeaderSubtitle {{
    color: {TOKENS["text_muted"]};
}}
QLabel#sectionPanelTitle,
QLabel#summaryCardTitle {{
    color: #3e4a57;
    font-size: 12.5pt;
    font-weight: 600;
}}
QLabel#summaryCardValue {{
    color: {TOKENS["text"]};
    font-size: 13pt;
    font-weight: 700;
}}
QLabel#summaryCardBody {{
    color: {TOKENS["text_muted"]};
}}
QLabel[formLabel="true"] {{
    background: transparent;
    color: #2f3d4f;
    padding: 0;
    margin: 0;
}}
QLabel[emptyState="true"],
QFrame#emptyState {{
    background: transparent;
    border: none;
    border-radius: 0;
    color: #55657b;
    padding: 4px 2px;
}}
QFrame#statusStrip {{
    background: #ffffff;
    border: 1px solid {TOKENS["border"]};
    border-radius: 2px;
}}
QFrame#preflightCheckItem {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: 2px;
}}
QFrame#commandPreview {{
    background: {TOKENS["surface"]};
    border: 1px solid {TOKENS["border"]};
    border-radius: 2px;
}}
QFrame#parameterGrid {{
    background: #ffffff;
    border: 1px solid {TOKENS["border"]};
    border-radius: 2px;
}}
QLabel#parameterGridTitle {{
    background: #e9edf2;
    border-bottom: 1px solid {TOKENS["border"]};
    color: #1f2329;
    font-size: 12.5pt;
    font-weight: 700;
    padding: 5px 8px;
    min-height: 30px;
}}
QLabel#parameterGridLabel {{
    background: #f0f2f5;
    border-right: 1px solid {TOKENS["border"]};
    border-bottom: 1px solid {TOKENS["border"]};
    color: #2f3945;
    padding: 3px 8px;
    min-width: 185px;
    max-width: 185px;
    min-height: 36px;
}}
QFrame#parameterGrid QLineEdit,
QFrame#parameterGrid QComboBox,
QFrame#parameterGrid QSpinBox,
QFrame#parameterGrid QDoubleSpinBox {{
    border-radius: 0;
    border-left: 0;
    border-top: 0;
    border-right: 0;
    min-height: 36px;
    padding-top: 5px;
    padding-bottom: 5px;
}}
QFrame#parameterGrid QComboBox {{
    padding-left: 8px;
    padding-right: 32px;
}}
QFrame#propertyForm {{
    background: #ffffff;
    border: 1px solid {TOKENS["border"]};
    border-radius: 2px;
}}
QLabel#propertyFormTitle {{
    color: #1f2329;
    font-size: 12.5pt;
    font-weight: 700;
    padding-bottom: 4px;
}}
QLabel#propertyFormLabel {{
    background: transparent;
    color: #2f3945;
    padding: 0 8px 0 0;
}}
QFrame#propertyForm QLineEdit,
QFrame#propertyForm QComboBox,
QFrame#propertyForm QSpinBox,
QFrame#propertyForm QDoubleSpinBox {{
    min-height: 34px;
}}
QFrame#propertyForm QPushButton {{
    min-height: 34px;
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
    background: #f4f6f8;
    border-top: 1px solid {TOKENS["border"]};
}}
QTreeWidget#workflowStepTree {{
    background: #ffffff;
    border: 1px solid {TOKENS["border"]};
    border-radius: 2px;
}}
QFrame#runStepMonitor {{
    background: #ffffff;
    border: 1px solid {TOKENS["border"]};
    border-radius: 2px;
}}
QFrame#technicalDetailsPanel {{
    background: #ffffff;
    border: 1px solid {TOKENS["border"]};
    border-radius: 2px;
}}
"""
