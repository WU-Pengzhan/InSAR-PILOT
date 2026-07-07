"""Shared pytest setup: force headless Qt before any Qt import."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
