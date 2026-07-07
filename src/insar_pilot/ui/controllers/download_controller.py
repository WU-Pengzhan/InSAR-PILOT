"""Data-download workflow controller extracted from MainWindow.

Owns the five background QThread+worker pipelines (SLC download, ASF search,
Earthdata credential test, Tianditu key test, OpenTopography key test) and the
data-download page slots/handlers. Behavior is identical to the code that
previously lived on ``MainWindow``; the controller keeps a reference to the
window for a handful of shell-level callbacks (error dialogs, summary refresh,
and the cross-domain "use workspace as data sources" bridge).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from insar_pilot.download import (
    DownloadService,
    DownloadStorage,
    DownloadTask,
    SearchService,
    create_dem_task,
)
from insar_pilot.download.credentials import load_earthdata_credentials
from insar_pilot.download.map_credentials import load_tianditu_key
from insar_pilot.download.opentopography_credentials import load_opentopography_key
from insar_pilot.download.tile_proxy import TiandituTileProxy
from insar_pilot.services.preflight import PreflightService
from insar_pilot.ui.download_worker import (
    CredentialWorker,
    DownloadWorker,
    OpenTopographyKeyWorker,
    SearchWorker,
    TiandituKeyWorker,
)
from insar_pilot.ui.pages.data_download_page import DataDownloadPage

if TYPE_CHECKING:
    from insar_pilot.ui.main_window import MainWindow


class DownloadController(QObject):
    """Coordinates the data-download page and its background pipelines."""

    def __init__(
        self,
        window: MainWindow,
        page: DataDownloadPage,
        *,
        download_service: DownloadService,
        search_service: SearchService,
        preflight_service: PreflightService,
        tianditu_tile_proxy: TiandituTileProxy,
    ) -> None:
        super().__init__(window)
        self._window = window
        self.data_download_page = page
        self.download_service = download_service
        self.download_search_service = search_service
        self.preflight_service = preflight_service
        self.tianditu_tile_proxy = tianditu_tile_proxy

        self._download_page_status = "Ready"
        self._download_page_message = "Define AOI, dates, and Sentinel-1 SLC filters."
        self._download_thread: QThread | None = None
        self._download_worker: DownloadWorker | None = None
        self._download_search_thread: QThread | None = None
        self._download_search_worker: SearchWorker | None = None
        self._credential_thread: QThread | None = None
        self._credential_worker: CredentialWorker | None = None
        self._tianditu_thread: QThread | None = None
        self._tianditu_worker: TiandituKeyWorker | None = None
        self._tianditu_check_origin = "idle"
        self._opentopography_thread: QThread | None = None
        self._opentopography_worker: OpenTopographyKeyWorker | None = None
        self._opentopography_check_origin = "idle"
        self._active_search_output_dir = ""
        self._download_tasks: list[DownloadTask] = []
        self._download_task_status: dict[str, str] = {}
        self._download_task_message: dict[str, str] = {}
        self._download_credentials_ok = False

    # ------------------------------------------------------------------
    # Shell-facing accessors (read by MainWindow summary/nav; written by the
    # project-form loader on load).
    # ------------------------------------------------------------------
    @property
    def page_status(self) -> str:
        return self._download_page_status

    @property
    def page_message(self) -> str:
        return self._download_page_message

    def set_page_state(self, status: str, message: str) -> None:
        self._download_page_status = status
        self._download_page_message = message

    def active_background_threads(self) -> list[tuple[str, QThread]]:
        candidates = [
            ("download", self._download_thread),
            ("search", self._download_search_thread),
            ("Earthdata test", self._credential_thread),
            ("Tianditu key test", self._tianditu_thread),
            ("OpenTopography key test", self._opentopography_thread),
        ]
        return [(name, thread) for name, thread in candidates if thread is not None and thread.isRunning()]

    def cancel_active_download(self) -> None:
        if (
            self._download_thread is not None
            and self._download_thread.isRunning()
            and self._download_worker is not None
        ):
            self._download_worker.cancel()

    # ------------------------------------------------------------------
    # Browse helpers
    # ------------------------------------------------------------------
    def _browse_download_output_dir(self) -> None:
        self._window._browse_dir_into(
            self.data_download_page.output_dir_row.line_edit, "Select Sentinel-1 download workspace"
        )

    def _browse_download_aoi_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self._window,
            "Select AOI KML file",
            self.data_download_page.aoi_file_row.line_edit.text() or str(Path.home()),
            "KML files (*.kml);;All files (*)",
        )
        if path:
            self.data_download_page.aoi_file_row.line_edit.setText(path)

    # ------------------------------------------------------------------
    # Credentials / keys population and testing
    # ------------------------------------------------------------------
    def _download_storage(self) -> DownloadStorage:
        output_dir = self.data_download_page.output_dir()
        if not output_dir:
            raise ValueError("Choose an output directory for the standalone download workspace first.")
        return DownloadStorage(output_dir)

    def _populate_download_credentials(self) -> None:
        credentials = load_earthdata_credentials()
        if credentials is not None:
            self.data_download_page.set_credential_inputs(
                credentials.username,
                credentials.password,
                source=credentials.source,
            )

    def _populate_tianditu_key(self) -> None:
        self.data_download_page.set_tianditu_basemap_state(
            available=False,
            preferred_basemap="External Imagery",
        )
        key = load_tianditu_key()
        if key is not None:
            self.tianditu_tile_proxy.update_key(key.key)
            self.data_download_page.set_tianditu_key(key.key, source=key.source)
            self.data_download_page.set_tianditu_status(
                f"Loaded Tianditu key from {key.source}. Checking availability in the background."
            )
            self._start_tianditu_key_check(key.key, origin="startup", save_on_success=False)
        else:
            self.tianditu_tile_proxy.update_key("")
            self.data_download_page.set_tianditu_key("")
            self.data_download_page.set_tianditu_status(
                "Tianditu key is optional. External Imagery is active until Tianditu is configured."
            )

    def _populate_opentopography_key(self) -> None:
        self.data_download_page.set_opentopography_available(False)
        key = load_opentopography_key()
        if key is not None:
            self.data_download_page.set_opentopography_key(key.key, source=key.source)
            self.data_download_page.set_opentopography_status(
                f"Loaded OpenTopography key from {key.source}. Checking availability in the background."
            )
            self._start_opentopography_key_check(key.key, origin="startup", save_on_success=False)
        else:
            self.data_download_page.set_opentopography_key("")
            self.data_download_page.set_opentopography_status(
                "OpenTopography key is required for DEM download. Validate your key to enable DEM controls."
            )

    def _start_tianditu_key_check(self, key: str, *, origin: str, save_on_success: bool) -> None:
        if self._tianditu_thread is not None:
            return
        self._tianditu_check_origin = origin
        network = self.data_download_page.network_config()
        if origin == "manual":
            self.data_download_page.set_tianditu_busy(True)
            self.data_download_page.set_tianditu_status("Testing Tianditu basemap key...")
            self.data_download_page.append_log("Testing Tianditu basemap key in the background...")
        self._tianditu_thread = QThread(self)
        self._tianditu_worker = TiandituKeyWorker(key, network=network, save_on_success=save_on_success)
        self._tianditu_worker.moveToThread(self._tianditu_thread)
        self._tianditu_thread.started.connect(self._tianditu_worker.run)
        self._tianditu_worker.finished.connect(self._handle_tianditu_key_test_finished)
        self._tianditu_worker.finished.connect(self._tianditu_thread.quit)
        self._tianditu_thread.finished.connect(self._tianditu_worker.deleteLater)
        self._tianditu_thread.finished.connect(self._tianditu_thread.deleteLater)
        self._tianditu_thread.finished.connect(self._clear_tianditu_worker_refs)
        self._tianditu_thread.start()

    def _start_opentopography_key_check(self, key: str, *, origin: str, save_on_success: bool) -> None:
        if self._opentopography_thread is not None:
            return
        self._opentopography_check_origin = origin
        network = self.data_download_page.network_config()
        if origin == "manual":
            self.data_download_page.set_opentopography_busy(True)
            self.data_download_page.set_opentopography_status("Testing OpenTopography API key...")
            self.data_download_page.append_log("Testing OpenTopography DEM key in the background...")
        self._opentopography_thread = QThread(self)
        self._opentopography_worker = OpenTopographyKeyWorker(key, network=network, save_on_success=save_on_success)
        self._opentopography_worker.moveToThread(self._opentopography_thread)
        self._opentopography_thread.started.connect(self._opentopography_worker.run)
        self._opentopography_worker.finished.connect(self._handle_opentopography_key_test_finished)
        self._opentopography_worker.finished.connect(self._opentopography_thread.quit)
        self._opentopography_thread.finished.connect(self._opentopography_worker.deleteLater)
        self._opentopography_thread.finished.connect(self._opentopography_thread.deleteLater)
        self._opentopography_thread.finished.connect(self._clear_opentopography_worker_refs)
        self._opentopography_thread.start()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search_sentinel_download_scenes(self) -> None:
        if self._download_search_thread is not None:
            self._window._show_error("Search already running", "Wait for the current ASF search to finish first.")
            return
        try:
            criteria = self.data_download_page.criteria()
            self._validate_download_search_criteria(criteria)
        except Exception as exc:
            self._window._show_error("Search setup failed", str(exc))
            self.data_download_page.append_log(f"Search setup failed: {exc}")
            return

        output_dir = self.data_download_page.output_dir()
        network = self.data_download_page.network_config()
        self._active_search_output_dir = output_dir
        self.data_download_page.set_search_busy(True)
        self.data_download_page.append_log(
            f"Searching ASF for Sentinel-1 SLC scenes from {criteria.start_date} to {criteria.end_date}..."
        )
        if not output_dir:
            self.data_download_page.append_log("No workspace selected; search results will be shown but not saved.")
        self._download_page_status = "Searching"
        self._download_page_message = "ASF search is running in the background."
        self._window._sync_summary_sidebar()
        self._download_search_thread = QThread(self)
        self._download_search_worker = SearchWorker(
            self.download_search_service,
            criteria,
            output_dir=output_dir,
            network=network,
        )
        self._download_search_worker.moveToThread(self._download_search_thread)
        self._download_search_thread.started.connect(self._download_search_worker.run)
        self._download_search_worker.finished.connect(self._handle_download_search_finished)
        self._download_search_worker.failed.connect(self._handle_download_search_failed)
        self._download_search_worker.finished.connect(self._download_search_thread.quit)
        self._download_search_worker.failed.connect(self._download_search_thread.quit)
        self._download_search_thread.finished.connect(self._download_search_worker.deleteLater)
        self._download_search_thread.finished.connect(self._download_search_thread.deleteLater)
        self._download_search_thread.finished.connect(self._clear_download_search_worker_refs)
        self._download_search_thread.start()

    def _handle_download_search_finished(self, scenes, saved_path: str) -> None:
        scene_list = list(scenes)
        self.data_download_page.set_search_busy(False)
        self.data_download_page.set_scenes(scene_list)
        if saved_path:
            self.data_download_page.append_log(
                f"ASF search completed with {len(scene_list)} scenes. Results saved to {saved_path}."
            )
            message = f"{len(scene_list)} ASF scenes available in {self._active_search_output_dir}."
        else:
            self.data_download_page.append_log(
                f"ASF search completed with {len(scene_list)} scenes. Select a workspace before saving or downloading."
            )
            message = f"{len(scene_list)} ASF scenes available. Workspace not selected."
        self._download_page_status = "Ready"
        self._download_page_message = message
        self._window._sync_summary_sidebar()

    def _handle_download_search_failed(self, message: str) -> None:
        self.data_download_page.set_search_busy(False)
        detail = self._friendly_network_error(message)
        self.data_download_page.append_log(f"ASF search failed: {detail}")
        self._download_page_status = "Search failed"
        self._download_page_message = detail
        self._window._sync_summary_sidebar()

    def _clear_download_search_worker_refs(self) -> None:
        self._download_search_thread = None
        self._download_search_worker = None

    @staticmethod
    def _validate_download_search_criteria(criteria) -> None:
        if not criteria.start_date.strip() or not criteria.end_date.strip():
            raise ValueError("Start date and end date are required.")
        if not DownloadController._is_supported_download_date(criteria.start_date):
            raise ValueError("Start date must use YYYY-MM-DD or YYYYMMDD format.")
        if not DownloadController._is_supported_download_date(criteria.end_date):
            raise ValueError("End date must use YYYY-MM-DD or YYYYMMDD format.")
        if criteria.aoi_mode == "kml":
            if not criteria.aoi_file.strip():
                raise ValueError("Choose an AOI KML file before searching.")
            if not Path(criteria.aoi_file).expanduser().is_file():
                raise ValueError(f"AOI file was not found: {criteria.aoi_file}")
        elif criteria.aoi_mode == "wkt":
            if not criteria.wkt.strip():
                raise ValueError("WKT AOI is required when WKT input is selected.")
        elif not criteria.bbox.strip():
            raise ValueError("AOI bbox is required when BBOX input is selected.")

    @staticmethod
    def _is_supported_download_date(value: str) -> bool:
        text = value.strip()
        if re.fullmatch(r"\d{8}", text):
            try:
                datetime.strptime(text, "%Y%m%d")
            except ValueError:
                return False
            return True
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            try:
                datetime.strptime(text, "%Y-%m-%d")
            except ValueError:
                return False
            return True
        return False

    @staticmethod
    def _friendly_network_error(message: str) -> str:
        """Add context for common ASF/CMR connectivity failures."""

        lower = message.lower()
        if "proxyerror" in lower or "proxy" in lower:
            return (
                f"{message} Current proxy settings appear to be unreachable. "
                "Check HTTP_PROXY/HTTPS_PROXY/ALL_PROXY in the WSL environment, or unset them before launching."
            )
        if "cmr.earthdata.nasa.gov" in lower:
            return (
                f"{message} ASF search uses NASA CMR (cmr.earthdata.nasa.gov); "
                "being able to open search.asf.alaska.edu in a browser does not "
                "guarantee this API endpoint is reachable."
            )
        if "timeout" in lower or "timed out" in lower:
            return f"{message} The request timed out; the GUI remains usable while the background worker finishes."
        return message

    def test_asf_download_credentials(self) -> None:
        if self._credential_thread is not None:
            self._window._show_error(
                "Connection test already running",
                "Wait for the current ASF connection test to finish first.",
            )
            return
        username, password = self.data_download_page.credential_inputs()
        network = self.data_download_page.network_config()
        self.data_download_page.set_credential_status("Testing ASF Earthdata connection...")
        self._download_credentials_ok = False
        self.data_download_page.test_credentials_button.setEnabled(False)
        self.data_download_page.append_log("Testing ASF Earthdata connection in the background...")
        self._credential_thread = QThread(self)
        self._credential_worker = CredentialWorker(
            username,
            password,
            save_netrc=self.data_download_page.should_save_netrc(),
            network=network,
        )
        self._credential_worker.moveToThread(self._credential_thread)
        self._credential_thread.started.connect(self._credential_worker.run)
        self._credential_worker.finished.connect(self._handle_credential_test_finished)
        self._credential_worker.finished.connect(self._credential_thread.quit)
        self._credential_thread.finished.connect(self._credential_worker.deleteLater)
        self._credential_thread.finished.connect(self._credential_thread.deleteLater)
        self._credential_thread.finished.connect(self._clear_credential_worker_refs)
        self._credential_thread.start()

    def _handle_credential_test_finished(self, result, saved_path: str, endpoint_checks) -> None:
        self.data_download_page.test_credentials_button.setEnabled(True)
        self.data_download_page.set_credential_status(result.message)
        self._download_credentials_ok = bool(result.ok)
        for check in endpoint_checks:
            status = "OK" if check.ok else "FAILED"
            self.data_download_page.append_log(f"{check.name}: {status} ({check.message})")
        if saved_path:
            self.data_download_page.append_log(
                f"Saved Earthdata credentials to {saved_path}." if not saved_path.startswith("Saving ") else saved_path
            )
            if not saved_path.startswith("Saving "):
                self._populate_download_credentials()
        self.data_download_page.append_log(result.message)
        self._download_page_status = "Credentials OK" if result.ok else "Credential failed"
        self._download_page_message = result.message
        self._window._sync_summary_sidebar()

    def _clear_credential_worker_refs(self) -> None:
        self._credential_thread = None
        self._credential_worker = None

    def test_tianditu_basemap_key(self) -> None:
        if self._tianditu_thread is not None:
            self._window._show_error(
                "Tianditu key test already running",
                "Wait for the current basemap key test to finish first.",
            )
            return
        key = self.data_download_page.tianditu_key()
        self._start_tianditu_key_check(key, origin="manual", save_on_success=True)

    def test_opentopography_key(self) -> None:
        if self._opentopography_thread is not None:
            self._window._show_error(
                "OpenTopography key test already running",
                "Wait for the current DEM key test to finish first.",
            )
            return
        key = self.data_download_page.opentopography_key()
        self._start_opentopography_key_check(key, origin="manual", save_on_success=True)

    def _handle_tianditu_key_test_finished(self, result, saved_path: str) -> None:
        origin = self._tianditu_check_origin
        if origin == "manual":
            self.data_download_page.set_tianditu_busy(False)

        if result.ok:
            key = self.data_download_page.tianditu_key()
            self.tianditu_tile_proxy.update_key(key)
            self.data_download_page.set_tianditu_basemap_state(
                available=True,
                preferred_basemap="Tianditu Imagery",
            )
            self.data_download_page.set_tianditu_status(result.message)
        else:
            self.data_download_page.set_tianditu_basemap_state(
                available=False,
                preferred_basemap="External Imagery",
            )
            if origin == "startup":
                self.data_download_page.set_tianditu_status(
                    "Saved Tianditu key could not be validated. External Imagery is active."
                )
            else:
                self.data_download_page.set_tianditu_status(result.message)

        if origin == "manual":
            if saved_path:
                self.data_download_page.append_log(
                    f"Saved Tianditu key to {saved_path}." if not saved_path.startswith("Saving ") else saved_path
                )
            self.data_download_page.append_log(result.message)

    def _clear_tianditu_worker_refs(self) -> None:
        self._tianditu_thread = None
        self._tianditu_worker = None
        self._tianditu_check_origin = "idle"

    def _handle_opentopography_key_test_finished(self, result, saved_path: str) -> None:
        origin = self._opentopography_check_origin
        if origin == "manual":
            self.data_download_page.set_opentopography_busy(False)

        self.data_download_page.set_opentopography_available(result.ok)
        self.data_download_page.set_opentopography_status(result.message)
        if origin == "manual":
            if saved_path:
                self.data_download_page.append_log(
                    f"Saved OpenTopography key to {saved_path}."
                    if not saved_path.startswith("Saving ")
                    else saved_path
                )
            self.data_download_page.append_log(result.message)

    def _clear_opentopography_worker_refs(self) -> None:
        self._opentopography_thread = None
        self._opentopography_worker = None
        self._opentopography_check_origin = "idle"

    # ------------------------------------------------------------------
    # Selection / download orchestration
    # ------------------------------------------------------------------
    def clear_sentinel_download_results(self) -> None:
        self.data_download_page.clear_results()
        self.data_download_page.append_log("Search results cleared.")
        self._download_page_status = "Ready"
        self._download_page_message = "Define AOI, dates, and Sentinel-1 SLC filters."
        self._window._sync_summary_sidebar()

    def save_selected_sentinel_scenes(self) -> None:
        try:
            storage = self._download_storage()
        except Exception as exc:
            self._window._show_error("Save selected scenes failed", str(exc))
            return

        selected = self.data_download_page.selected_scenes()
        if not selected:
            self._window._show_error("No scenes selected", "Select at least one scene in the search results table.")
            return

        path = storage.save_selected_scenes(selected)
        self.data_download_page.append_log(f"Saved {len(selected)} selected scenes to {path}.")
        self._download_page_status = "Selected"
        self._download_page_message = f"{len(selected)} selected scenes saved."
        self._window._sync_summary_sidebar()

    def download_selected_sentinel_scenes(self) -> None:
        if self._download_thread is not None:
            self._window._show_error(
                "Download already running", "Wait for the current download to finish or cancel it first."
            )
            return
        capability = self.preflight_service.check_aria2_capability()
        self.data_download_page.set_aria2_capability(capability.aria2c_available, capability.aria2c_path)
        if not capability.aria2c_available:
            self._window._show_error(
                "aria2c missing",
                "SLC downloads require aria2c for multipart resumable transfers. "
                "Activate the insar conda environment or install aria2c, then try again.",
            )
            return
        if not self._download_credentials_ok:
            self._window._show_error(
                "ASF credentials not verified",
                "Test ASF Earthdata credentials successfully before starting downloads.",
            )
            return
        try:
            storage = self._download_storage()
        except Exception as exc:
            self._window._show_error("Download setup failed", str(exc))
            return

        selected = self.data_download_page.selected_scenes()
        if not selected:
            self._window._show_error("No scenes selected", "Select at least one scene before downloading.")
            return
        criteria = self.data_download_page.criteria()
        include_dem = self.data_download_page.should_download_dem()
        dem_source = self.data_download_page.dem_source()
        dem_api_key = self.data_download_page.opentopography_key()
        if include_dem and not dem_api_key.strip():
            self._window._show_error("DEM key missing", "Validate an OpenTopography key before enabling DEM download.")
            return

        storage.save_selected_scenes(selected)
        tasks = self.download_service.create_tasks(
            selected,
            storage.output_dir,
            include_orbits=self.data_download_page.include_orbits(),
        )
        if include_dem:
            tasks.append(create_dem_task(storage.output_dir, dem_source))
        storage.save_download_tasks(tasks)
        username, password = self.data_download_page.credential_inputs()
        network = self.data_download_page.network_config()
        self._download_tasks = tasks
        self._download_task_status = {task.task_id: task.status for task in tasks}
        self._download_task_message = {task.task_id: task.message for task in tasks}
        self._download_thread = QThread(self)
        self._download_worker = DownloadWorker(
            self.download_service,
            storage,
            tasks,
            username=username,
            password=password,
            criteria=criteria,
            download_dem=include_dem,
            dem_source=dem_source,
            dem_api_key=dem_api_key,
            network=network,
        )
        self._download_worker.moveToThread(self._download_thread)
        self._download_thread.started.connect(self._download_worker.run)
        self._download_worker.task_updated.connect(self._handle_download_task_updated)
        self._download_worker.dem_plan_ready.connect(self._handle_dem_plan_ready)
        self._download_worker.log.connect(self.data_download_page.append_log)
        self._download_worker.finished.connect(self._handle_download_finished)
        self._download_worker.failed.connect(self._handle_download_failed)
        self._download_worker.finished.connect(self._download_thread.quit)
        self._download_worker.failed.connect(self._download_thread.quit)
        self._download_thread.finished.connect(self._download_worker.deleteLater)
        self._download_thread.finished.connect(self._download_thread.deleteLater)
        self._download_thread.finished.connect(self._clear_download_worker_refs)
        self.data_download_page.set_download_busy(True)
        self.data_download_page.set_download_tasks(tasks)
        self.data_download_page.append_log(f"Started {len(tasks)} download tasks in {storage.output_dir}.")
        self._download_page_status = "Downloading"
        self._download_page_message = f"{len(tasks)} download tasks running."
        self._window._sync_summary_sidebar()
        self._download_thread.start()

    def cancel_sentinel_download(self) -> None:
        if self._download_worker is not None:
            self._download_worker.cancel()

    def _handle_download_task_updated(self, task: DownloadTask) -> None:
        previous_status = self._download_task_status.get(task.task_id, "")
        previous_message = self._download_task_message.get(task.task_id, "")
        self._download_task_status[task.task_id] = task.status
        self._download_task_message[task.task_id] = task.message
        completed = self._download_completed_task_count()
        total = len(self._download_tasks)
        self.data_download_page.apply_task_update(task, completed, total)
        terminal = {"completed", "skipped", "failed", "cancelled"}
        should_log = task.status in terminal or (
            task.status == "running" and (previous_status != "running" or task.message != previous_message)
        )
        if should_log and task.message:
            suffix = f" -> {task.local_path}" if task.product_type.upper() == "ORBIT" and task.local_path else ""
            self.data_download_page.append_log(f"{task.task_id} [{task.product_type}]: {task.message}{suffix}")

    def _handle_download_finished(self, results) -> None:
        result_list = list(results)
        self.data_download_page.apply_download_results(result_list)
        completed = sum(result.status == "completed" for result in result_list)
        skipped = sum(result.status == "skipped" for result in result_list)
        failed = sum(result.status == "failed" for result in result_list)
        cancelled = sum(result.status == "cancelled" for result in result_list)
        self.data_download_page.append_log(
            f"Download finished: {completed} completed, {skipped} skipped, {failed} failed, {cancelled} cancelled."
        )
        self.data_download_page.set_download_busy(False)
        self._download_page_status = "Downloaded" if failed == 0 and cancelled == 0 else "Download issues"
        self._download_page_message = (
            f"{completed} completed, {skipped} skipped, {failed} failed, {cancelled} cancelled."
        )
        self._window._sync_summary_sidebar()

    def _handle_dem_plan_ready(self, plan) -> None:
        self.data_download_page.set_dem_plan(plan)
        if plan.planned_bbox_snwe is not None:
            bbox_text = " ".join(f"{value:g}" for value in plan.planned_bbox_snwe)
            self.data_download_page.append_log(f"Planned DEM bbox ({plan.planning_mode}): {bbox_text}")

    def _handle_download_failed(self, message: str) -> None:
        self.data_download_page.append_log(f"Download worker failed: {message}")
        self.data_download_page.set_download_busy(False)
        self._download_page_status = "Download failed"
        self._download_page_message = message
        self._window._sync_summary_sidebar()

    def _clear_download_worker_refs(self) -> None:
        self._download_thread = None
        self._download_worker = None

    def _download_completed_task_count(self) -> int:
        terminal = {"completed", "skipped", "failed", "cancelled"}
        return sum(status in terminal for status in self._download_task_status.values())

    def use_download_workspace_as_data_sources(self) -> None:
        try:
            storage = self._download_storage()
        except Exception as exc:
            self._window._show_error("Download workspace missing", str(exc))
            return
        slc_dir = storage.output_dir / "SLC"
        orbit_dir = storage.output_dir / "Orbit"
        dem_plan = storage.load_dem_plan()
        if not slc_dir.is_dir():
            self._window._show_error("SLC folder missing", f"No SLC folder exists yet: {slc_dir}")
            return
        self._window.input_path_edit.setText(str(slc_dir))
        if orbit_dir.is_dir():
            self._window.orbit_path_edit.setText(str(orbit_dir))
        if dem_plan is not None and dem_plan.dem_path:
            self._window.dem_path_edit.setText(dem_plan.dem_path)
            index = self._window.dem_reference_combo.findData(dem_plan.dem_height_reference)
            self._window.dem_reference_combo.setCurrentIndex(index if index >= 0 else 0)
        self._window._update_project_from_form()
        if dem_plan is not None and dem_plan.dem_path:
            self.data_download_page.append_log(
                "Filled Data Sources with the download workspace SLC/Orbit folders and DEM."
            )
        else:
            self.data_download_page.append_log("Filled Data Sources with the download workspace SLC/Orbit folders.")
        self._download_page_status = "Ready for Data Sources"
        self._download_page_message = (
            "SLC/Orbit/DEM paths were filled into Data Sources. Run Validate & Prepare Data next."
            if dem_plan is not None and dem_plan.dem_path
            else "SLC/Orbit paths were filled into Data Sources. Run Validate & Prepare Data next."
        )
        self._window._sync_summary_sidebar()

    def open_download_workspace(self) -> None:
        try:
            storage = self._download_storage()
        except Exception as exc:
            self._window._show_error("Download workspace missing", str(exc))
            return
        storage.output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(storage.output_dir)))

    def _refresh_download_capability(self) -> None:
        capability = self.preflight_service.check_aria2_capability()
        self.data_download_page.set_aria2_capability(
            capability.aria2c_available,
            capability.aria2c_path,
        )
