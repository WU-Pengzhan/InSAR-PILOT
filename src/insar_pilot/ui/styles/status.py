"""Status and badge QSS."""

from insar_pilot.ui.styles.tokens import TOKENS

STATUS_QSS = f"""
QLabel[badge="true"] {{
    border-radius: 2px;
    padding: 4px 8px;
    font-size: 11.5pt;
    font-weight: 700;
}}
QLabel[badge="true"][tone="neutral"] {{
    background: #ebeff5;
    color: #4a596e;
}}
QLabel[badge="true"][tone="ready"],
QLabel[badge="true"][tone="success"],
QLabel[badge="true"][tone="ok"] {{
    background: {TOKENS["success_bg"]};
    color: {TOKENS["success_text"]};
}}
QLabel[badge="true"][tone="running"] {{
    background: {TOKENS["running_bg"]};
    color: {TOKENS["running_text"]};
}}
QLabel[badge="true"][tone="warning"] {{
    background: {TOKENS["warning_bg"]};
    color: {TOKENS["warning_text"]};
}}
QLabel[badge="true"][tone="failed"],
QLabel[badge="true"][tone="error"],
QLabel[badge="true"][tone="blocker"] {{
    background: {TOKENS["error_bg"]};
    color: {TOKENS["error_text"]};
}}
QFrame#inlineAlert[tone="info"] {{
    background: #e8f2fb;
    border: 1px solid #b8d2ed;
}}
QFrame#inlineAlert[tone="warning"] {{
    background: {TOKENS["warning_bg"]};
    border: 1px solid #e4c792;
}}
QFrame#inlineAlert[tone="blocker"],
QFrame#inlineAlert[tone="error"] {{
    background: {TOKENS["error_bg"]};
    border: 1px solid #e0b0b0;
}}
"""
