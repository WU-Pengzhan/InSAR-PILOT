"""Light professional desktop stylesheet for the industrial shell."""

from __future__ import annotations

from insar_pilot.ui.styles import BASE_QSS, COMPONENT_QSS, STATUS_QSS, WIDGET_QSS


def build_light_stylesheet() -> str:
    """Return the default light stylesheet for scientific desktop workflows."""

    return "\n".join((BASE_QSS, COMPONENT_QSS, STATUS_QSS, WIDGET_QSS))
