"""Status and badge QSS."""

from insar_pilot.ui.styles.tokens import FONT_SIZES, LIGHT_TOKENS, RADIUS


def build_status_qss(TOKENS: dict[str, str] = LIGHT_TOKENS) -> str:
    """Return the status/badge QSS for the given token palette."""

    return f"""
QLabel[badge="true"] {{
    border-radius: {RADIUS["sm"]}px;
    padding: 4px 8px;
    font-size: {FONT_SIZES["caption"]}pt;
    font-weight: 700;
}}
QLabel[badge="true"][tone="neutral"] {{
    background: {TOKENS["surface_muted"]};
    color: {TOKENS["text_subtle"]};
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
    background: {TOKENS["info_bg"]};
    border: 1px solid {TOKENS["info_border"]};
}}
QFrame#inlineAlert[tone="warning"] {{
    background: {TOKENS["warning_bg"]};
    border: 1px solid {TOKENS["warning_border"]};
}}
QFrame#inlineAlert[tone="blocker"],
QFrame#inlineAlert[tone="error"] {{
    background: {TOKENS["error_bg"]};
    border: 1px solid {TOKENS["error_border"]};
}}
QLabel#inlineErrorText {{
    color: {TOKENS["error_text"]};
    font-weight: 700;
}}
"""


STATUS_QSS = build_status_qss()
