"""Compatibility shim re-exporting :class:`DataDownloadPage`.

The Data Download page was split into focused section modules under the
``insar_pilot.ui.pages.data_download`` package. This module keeps the original
import path (``from insar_pilot.ui.pages.data_download_page import
DataDownloadPage``) working for MainWindow, DownloadController, and tests.
"""

from __future__ import annotations

from insar_pilot.ui.pages.data_download import DataDownloadPage

__all__ = ["DataDownloadPage"]
