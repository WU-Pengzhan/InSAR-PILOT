"""Shared pytest setup: force headless Qt before any Qt import."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("INSAR_PILOT_MAP_BACKEND", "native")
