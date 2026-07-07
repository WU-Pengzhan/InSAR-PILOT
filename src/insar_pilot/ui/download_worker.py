"""Qt workers for background Sentinel-1 download-page network tasks."""

from __future__ import annotations

import time
from dataclasses import replace

from PySide6.QtCore import QObject, Signal, Slot

from insar_pilot.download import (
    DemCoveragePlanner,
    DownloadService,
    DownloadStorage,
    DownloadTask,
    NetworkConfig,
    OpenTopographyDemService,
    SearchService,
)
from insar_pilot.download.credentials import save_earthdata_netrc, test_earthdata_connection, test_network_endpoints
from insar_pilot.download.map_credentials import save_tianditu_key, test_tianditu_key
from insar_pilot.download.models import SearchCriteria
from insar_pilot.download.opentopography_credentials import save_opentopography_key, test_opentopography_key


class SearchWorker(QObject):
    """Run ASF scene search off the GUI thread."""

    finished = Signal(object, str)
    failed = Signal(str)

    def __init__(
        self,
        service: SearchService,
        criteria: SearchCriteria,
        *,
        output_dir: str = "",
        network: NetworkConfig | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.criteria = criteria
        self.output_dir = output_dir
        self.network = network or NetworkConfig()

    @Slot()
    def run(self) -> None:
        """Execute search and optionally persist results."""

        try:
            scenes = self.service.search(self.criteria, network=self.network)
            saved_path = ""
            if self.output_dir:
                storage = DownloadStorage(self.output_dir)
                saved_path = str(storage.save_search_results(scenes))
            self.finished.emit(scenes, saved_path)
        except Exception as exc:
            self.failed.emit(str(exc))


class CredentialWorker(QObject):
    """Run Earthdata credential checks off the GUI thread."""

    finished = Signal(object, str, object)

    def __init__(
        self,
        username: str,
        password: str,
        *,
        save_netrc: bool = False,
        network: NetworkConfig | None = None,
    ) -> None:
        super().__init__()
        self.username = username
        self.password = password
        self.save_netrc = save_netrc
        self.network = network or NetworkConfig()

    @Slot()
    def run(self) -> None:
        """Check credentials and optionally save them to netrc."""

        saved_path = ""
        endpoint_checks = test_network_endpoints(self.network)
        result = test_earthdata_connection(self.username, self.password, network=self.network)
        if result.ok and self.save_netrc:
            try:
                saved_path = str(save_earthdata_netrc(self.username, self.password))
            except Exception as exc:
                saved_path = f"Saving ~/.netrc failed: {exc}"
        self.finished.emit(result, saved_path, endpoint_checks)


class TiandituKeyWorker(QObject):
    """Validate and save a Tianditu key off the GUI thread."""

    finished = Signal(object, str)

    def __init__(
        self,
        key: str,
        *,
        network: NetworkConfig | None = None,
        save_on_success: bool = True,
    ) -> None:
        super().__init__()
        self.key = key
        self.network = network or NetworkConfig()
        self.save_on_success = save_on_success

    @Slot()
    def run(self) -> None:
        """Check the key and save it only after a successful tile request."""

        saved_path = ""
        result = test_tianditu_key(self.key, network=self.network)
        if result.ok and self.save_on_success:
            try:
                saved_path = str(save_tianditu_key(self.key))
            except Exception as exc:
                saved_path = f"Saving Tianditu key failed: {exc}"
        self.finished.emit(result, saved_path)


class OpenTopographyKeyWorker(QObject):
    """Validate and save an OpenTopography key off the GUI thread."""

    finished = Signal(object, str)

    def __init__(
        self,
        key: str,
        *,
        network: NetworkConfig | None = None,
        save_on_success: bool = True,
    ) -> None:
        super().__init__()
        self.key = key
        self.network = network or NetworkConfig()
        self.save_on_success = save_on_success

    @Slot()
    def run(self) -> None:
        """Check the key and save it only after a successful DEM API request."""

        saved_path = ""
        result = test_opentopography_key(self.key, network=self.network)
        if result.ok and self.save_on_success:
            try:
                saved_path = str(save_opentopography_key(self.key))
            except Exception as exc:
                saved_path = f"Saving OpenTopography key failed: {exc}"
        self.finished.emit(result, saved_path)


class DownloadWorker(QObject):
    """Run download tasks off the GUI thread and persist task state."""

    task_updated = Signal(object)
    dem_plan_ready = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    log = Signal(str)

    def __init__(
        self,
        service: DownloadService,
        storage: DownloadStorage,
        tasks: list[DownloadTask],
        *,
        username: str = "",
        password: str = "",
        criteria: SearchCriteria | None = None,
        download_dem: bool = False,
        dem_source: str = "COP30",
        dem_api_key: str = "",
        network: NetworkConfig | None = None,
        dem_planner: DemCoveragePlanner | None = None,
        dem_service: OpenTopographyDemService | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.storage = storage
        self.tasks = list(tasks)
        self.username = username
        self.password = password
        self.criteria = criteria
        self.download_dem = download_dem
        self.dem_source = dem_source
        self.dem_api_key = dem_api_key
        self.network = network or NetworkConfig()
        self.dem_planner = dem_planner or DemCoveragePlanner()
        self.dem_service = dem_service or OpenTopographyDemService()
        self._cancel_requested = False
        self._last_emit_by_task: dict[str, float] = {}
        self._last_save_by_task: dict[str, float] = {}

    @Slot()
    def run(self) -> None:
        """Execute downloads and emit progress updates."""

        try:
            self.storage.save_download_tasks(self.tasks)
            results = self.service.download(
                self.tasks,
                username=self.username,
                password=self.password,
                network=self.network,
                progress_callback=self._handle_task_update,
                cancel_check=lambda: self._cancel_requested,
            )
            if self.download_dem:
                dem_result = self._download_dem_after_slc(results)
                if dem_result is not None:
                    results.append(dem_result)
            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))

    @Slot()
    def cancel(self) -> None:
        """Request cancellation before the next streamed chunk or task."""

        if self._cancel_requested:
            return
        self._cancel_requested = True
        self.log.emit("Cancellation requested. Current partial file will be kept.")

    def _handle_task_update(self, task: DownloadTask) -> None:
        self.tasks = [task if existing.task_id == task.task_id else existing for existing in self.tasks]
        terminal = task.status in {"completed", "skipped", "failed", "cancelled"}
        now = time.monotonic()
        if terminal or now - self._last_save_by_task.get(task.task_id, 0.0) >= 0.5:
            self.storage.save_download_tasks(self.tasks)
            self._last_save_by_task[task.task_id] = now
        if terminal or now - self._last_emit_by_task.get(task.task_id, 0.0) >= 0.35:
            self.task_updated.emit(task)
            self._last_emit_by_task[task.task_id] = now

    def _download_dem_after_slc(self, results) -> object | None:
        dem_task = next((task for task in self.tasks if task.product_type.upper() == "DEM"), None)
        if dem_task is None:
            return None
        if self.criteria is None:
            failed = dem_task.with_updates(
                status="failed", message="DEM planning is missing the current search criteria."
            )
            self._handle_task_update(failed)
            return self.dem_service._result_from_task(failed)
        if self._cancel_requested:
            cancelled = dem_task.with_updates(status="cancelled", message="Download cancelled before DEM planning.")
            self._handle_task_update(cancelled)
            return self.dem_service._result_from_task(cancelled)

        local_scenes = self._local_slc_scenes_from_results(results)
        if not local_scenes:
            failed = dem_task.with_updates(
                status="failed", message="DEM download requires at least one downloaded SLC."
            )
            self._handle_task_update(failed)
            return self.dem_service._result_from_task(failed)

        planning = dem_task.with_updates(status="running", message="Planning DEM coverage from local SLC bursts...")
        self._handle_task_update(planning)
        plan = self.dem_planner.plan(self.criteria, local_scenes, self.dem_source)
        self.storage.save_dem_plan(plan)
        self.dem_plan_ready.emit(plan)
        self.log.emit(
            f"DEM planning completed using {plan.planning_mode}: "
            + (" ".join(f"{value:g}" for value in plan.planned_bbox_snwe) if plan.planned_bbox_snwe else "no bbox")
        )
        for warning in plan.warnings:
            self.log.emit(warning)
        dem_result = self.dem_service.download(
            planning,
            plan,
            api_key=self.dem_api_key,
            network=self.network,
            progress_callback=self._handle_task_update,
            cancel_check=lambda: self._cancel_requested,
        )
        if dem_result.status in {"completed", "skipped"}:
            updated_plan = replace(plan, dem_path=dem_result.local_path)
            self.storage.save_dem_plan(updated_plan)
            self.dem_plan_ready.emit(updated_plan)
        return dem_result

    @staticmethod
    def _local_slc_scenes_from_results(results) -> list:
        local_scenes = []
        for result in results:
            if result.product_type.upper() != "SLC":
                continue
            if result.status not in {"completed", "skipped"}:
                continue
            scene = result.scene.with_status("downloaded", result.local_path)
            local_scenes.append(scene)
        return local_scenes
