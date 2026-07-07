"""Scene results, footprint map, detail, and activity-log behavior.

``ResultsController`` owns the widgets that render ASF search results (results
table and footprint map) plus the scene-detail and activity-log text edits that
live in the left control panel. It also owns the scene/task state and the
download-progress bookkeeping. Shared status widgets (step tree, summary cards,
task-progress panel, selection label, and download status label) and the search
criteria provider are injected by :class:`DataDownloadPage`; behavior is identical
to the code that previously lived directly on the page.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
)

from insar_pilot.controllers.download_coordinator import DownloadStateReducer
from insar_pilot.download.dem_service import dem_label_for_source
from insar_pilot.download.models import DemCoveragePlan, DownloadResult, DownloadTask, SceneRecord, SearchCriteria
from insar_pilot.ui.pages.data_download.scroll_filter import NestedScrollFilter
from insar_pilot.ui.widgets.footprint_map import FootprintMapWidget
from insar_pilot.ui.widgets.log_console import append_text_preserving_scroll


class ResultsController(QObject):
    """Owns the scene results table, footprint map, and scene/task state."""

    TABLE_COLUMNS = [
        "Select",
        "scene_id",
        "acquisition_time",
        "platform",
        "orbit_direction",
        "relative_orbit",
        "polarization",
        "size",
        "status",
        "local_path",
    ]
    TABLE_COLUMN_WIDTHS = [78, 300, 210, 150, 170, 150, 140, 110, 130, 420]

    def __init__(
        self,
        *,
        download_step_tree,
        result_card,
        task_card,
        selection_label,
        task_progress_panel,
        download_status_label,
        criteria_provider: Callable[[], SearchCriteria],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.download_step_tree = download_step_tree
        self.result_card = result_card
        self.task_card = task_card
        self.selection_label = selection_label
        self.task_progress_panel = task_progress_panel
        self.download_status_label = download_status_label
        self._criteria_provider = criteria_provider

        self._scenes: list[SceneRecord] = []
        self._dem_plan: DemCoveragePlan | None = None
        self._planned_download_tasks: list[DownloadTask] = []
        self._download_task_updates: dict[str, DownloadTask] = {}
        self._log_scroll_filters: list[NestedScrollFilter] = []
        self._preferred_selected_scene_ids: set[str] = set()

        self.footprint_map = FootprintMapWidget()
        self.footprint_map.setMinimumHeight(440)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(len(self.TABLE_COLUMNS))
        self.results_table.setHorizontalHeaderLabels(self.TABLE_COLUMNS)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.setMinimumHeight(190)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setWordWrap(False)
        self.results_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.results_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._apply_results_table_geometry()

        self.scene_detail_text = QPlainTextEdit()
        self.scene_detail_text.setReadOnly(True)
        self.scene_detail_text.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.scene_detail_text.setPlaceholderText(
            "Select a scene to inspect orbit, polarization, size, status, and local path."
        )
        self.scene_detail_text.setMinimumHeight(120)
        self.scene_detail_text.setMaximumHeight(150)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.log_text.setPlaceholderText("ASF search, selection, save, and download status will appear here.")
        self.log_text.setMinimumHeight(160)
        self.log_text.setMaximumHeight(260)
        self._install_nested_scroll_filter(self.scene_detail_text)
        self._install_nested_scroll_filter(self.log_text)

        self.results_table.itemSelectionChanged.connect(self._update_scene_detail_from_selection)
        self.results_table.itemChanged.connect(lambda _: self._update_selection_summary())
        self._update_selection_summary()

    def _install_nested_scroll_filter(self, text_edit: QPlainTextEdit) -> None:
        scroll_filter = NestedScrollFilter(text_edit)
        text_edit.viewport().installEventFilter(scroll_filter)
        self._log_scroll_filters.append(scroll_filter)

    def set_all_scene_checks(self, state: Qt.CheckState) -> None:
        """Set all result checkboxes and refresh selection counts."""

        self.results_table.blockSignals(True)
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 0)
            if item is not None:
                item.setCheckState(state)
        self.results_table.blockSignals(False)
        self._update_selection_summary()

    def clear_task_updates(self) -> None:
        """Reset per-task progress bookkeeping before a new download run."""

        self._download_task_updates = {}

    # Basemap / footprint-map delegation --------------------------------------
    def set_tianditu_proxy_url(self, base_url: str) -> None:
        """Provide the localhost tile proxy URL used by the embedded map."""

        self.footprint_map.set_tianditu_proxy_url(base_url)

    def set_tianditu_available(self, available: bool) -> None:
        """Enable or disable Tianditu layers in the embedded map."""

        self.footprint_map.set_tianditu_enabled(available)

    def set_preferred_basemap(self, name: str) -> None:
        """Select which basemap should be used on the next map refresh."""

        self.footprint_map.set_preferred_basemap(name)

    def set_tianditu_basemap_state(self, *, available: bool, preferred_basemap: str) -> None:
        """Update Tianditu availability and startup basemap together."""

        self.footprint_map.set_tianditu_basemap_state(
            enabled=available,
            preferred_basemap=preferred_basemap,
        )

    # Task / scene state ------------------------------------------------------
    def set_download_tasks(self, tasks: list[DownloadTask]) -> None:
        """Show the planned task set before the worker starts producing updates."""

        self._planned_download_tasks = list(tasks)
        self._download_task_updates = {task.task_id: task for task in self._planned_download_tasks}
        self.task_progress_panel.apply_state(DownloadStateReducer.from_tasks(self._planned_download_tasks))
        self.task_card.set_value(f"0/{len(self._planned_download_tasks)} tasks")
        self.task_card.set_body("Download plan ready. Waiting for worker updates.")
        if tasks:
            self.download_step_tree.set_step_status("4. Download", "ready", f"{len(tasks)} task(s) planned.")

    def set_scenes(self, scenes: list[SceneRecord]) -> None:
        """Render search results in the table."""

        self._scenes = list(scenes)
        self.clear_dem_plan(update_map=False)
        self.results_table.blockSignals(True)
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(len(self._scenes))
        for row, scene in enumerate(self._scenes):
            check_item = QTableWidgetItem("")
            check_item.setFlags(check_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checked = not self._preferred_selected_scene_ids or scene.scene_id in self._preferred_selected_scene_ids
            check_item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.results_table.setItem(row, 0, check_item)
            values = [
                scene.scene_id,
                scene.acquisition_time,
                scene.platform,
                scene.orbit_direction,
                str(scene.relative_orbit),
                scene.polarization,
                f"{scene.size_mb:g} MB",
                scene.status,
                scene.local_path,
            ]
            for col, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.results_table.setItem(row, col, item)
        self.results_table.setSortingEnabled(True)
        self.results_table.blockSignals(False)
        self._apply_results_table_geometry()
        self.result_card.set_value(f"{len(self._scenes)} scenes")
        self.result_card.set_body("All scenes are checked for save/download by default.")
        self.download_step_tree.set_step_status(
            "2. Search Area",
            "ready" if self._scenes else "warning",
            f"{len(self._scenes)} scene(s) found.",
        )
        self.download_step_tree.set_step_status(
            "3. Scene Selection",
            "ready" if self._scenes else "pending",
            "Review and adjust selected scenes.",
        )
        if self._scenes:
            self.results_table.selectRow(0)
        else:
            self.scene_detail_text.clear()
        self._refresh_footprint_map()
        self._update_selection_summary()

    def set_preferred_selected_scene_ids(self, scene_ids: list[str]) -> None:
        """Remember project-level scene selections for the next rendered result table."""

        self._preferred_selected_scene_ids = {scene_id for scene_id in scene_ids if scene_id}

    def selected_scenes(self) -> list[SceneRecord]:
        """Return checked scenes from the results table."""

        scene_by_id = {scene.scene_id: scene for scene in self._scenes}
        selected: list[SceneRecord] = []
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                scene_id_item = self.results_table.item(row, 1)
                if scene_id_item is not None and scene_id_item.text() in scene_by_id:
                    selected.append(scene_by_id[scene_id_item.text()])
        return selected

    def apply_download_results(self, results: list[DownloadResult]) -> None:
        """Update scene status and local path after downloads."""

        result_by_scene = {result.scene.scene_id: result for result in results if result.product_type.upper() == "SLC"}
        updated: list[SceneRecord] = []
        for scene in self._scenes:
            result = result_by_scene.get(scene.scene_id)
            updated.append(result.scene if result else scene)
        self._scenes = updated
        for result in result_by_scene.values():
            self._update_scene_row(result.scene.scene_id, result.status, result.local_path)
        self._update_scene_detail_from_selection(update_map=False)
        self.task_card.set_value(f"{len(results)} tasks")
        completed = sum(result.status == "completed" for result in results)
        skipped = sum(result.status == "skipped" for result in results)
        failed = sum(result.status == "failed" for result in results)
        cancelled = sum(result.status == "cancelled" for result in results)
        dem_result = next((result for result in results if result.product_type.upper() == "DEM"), None)
        self.task_card.set_body(
            f"{completed} completed, {skipped} skipped, {failed} failed, {cancelled} cancelled."
        )
        self.task_progress_panel.apply_state(DownloadStateReducer.from_results(list(results)))
        self.download_step_tree.set_step_status(
            "4. Download",
            "failed" if failed else "ready",
            f"{completed} completed, {failed} failed, {cancelled} cancelled.",
        )
        if results and not failed and not cancelled:
            self.download_step_tree.set_step_status("5. Import", "ready", "Downloaded workspace can be imported.")
        if dem_result is not None and dem_result.message:
            self.download_status_label.setText(dem_result.message)
        elif dem_result is None:
            self.download_status_label.setText("Download finished." if results else "No active download.")

    def apply_task_update(self, task: DownloadTask, completed_count: int, total_count: int) -> None:
        """Reflect a task status update in the table and progress summary."""

        self._download_task_updates[task.task_id] = task
        if self._planned_download_tasks:
            self._planned_download_tasks = [
                task if planned.task_id == task.task_id else planned for planned in self._planned_download_tasks
            ]
        if task.product_type.upper() == "SLC":
            updated: list[SceneRecord] = []
            for scene in self._scenes:
                if scene.scene_id == task.scene.scene_id:
                    updated.append(scene.with_status(task.status, task.local_path))
                else:
                    updated.append(scene)
            self._scenes = updated
            self._update_scene_row(task.scene.scene_id, task.status, task.local_path)

        tasks_for_summary = self._planned_download_tasks or list(self._download_task_updates.values())
        self.task_progress_panel.apply_state(DownloadStateReducer.from_tasks(tasks_for_summary, active_task=task))
        task_progress = self._task_progress_text(task)
        total_progress = self._total_progress_text()
        if task_progress or total_progress:
            self.download_status_label.setText(
                f"{task.product_type}: {task.status} ({completed_count}/{total_count})"
                + (f" | {task_progress}" if task_progress else "")
                + (f"\nTotal: {total_progress}" if total_progress else "")
            )
        self.task_card.set_value(f"{completed_count}/{total_count} tasks")
        self.task_card.set_body(
            " | ".join(part for part in [task.message or task.local_path or task.scene.scene_id, task_progress] if part)
        )
        self.download_step_tree.set_step_status(
            "4. Download",
            "running" if task.status == "running" else task.status,
            f"{task.product_type}: {task.status} ({completed_count}/{total_count})",
        )

    def clear_results(self) -> None:
        """Clear rendered search results while keeping the activity log."""

        self._scenes = []
        self.clear_dem_plan(update_map=False)
        self.results_table.setRowCount(0)
        self.scene_detail_text.clear()
        self.footprint_map.clear()
        self.result_card.set_value("0 scenes")
        self.result_card.set_body("Run search to list matching scenes.")
        self.task_card.set_value("0 tasks")
        self.task_card.set_body("Select scenes to download SLC ZIPs and EOF orbits.")
        self._planned_download_tasks = []
        self._download_task_updates = {}
        self.task_progress_panel.reset()
        self.download_step_tree.set_step_status("2. Search Area", "pending", "Ready for search.")
        self.download_step_tree.set_step_status("3. Scene Selection", "pending", "No scenes selected.")
        self.download_step_tree.set_step_status("4. Download", "pending", "No download plan.")
        self.download_step_tree.set_step_status("5. Import", "pending", "Download workspace is not ready.")
        self._update_selection_summary()

    def append_log(self, message: str) -> None:
        """Append one status line to the page log."""

        append_text_preserving_scroll(self.log_text, f"{message}\n")

    def _update_selection_summary(self) -> None:
        """Update the selected-scene affordance and summary card."""

        selected_count = len(self.selected_scenes())
        total_count = len(self._scenes)
        self.selection_label.setText(f"{selected_count} selected of {total_count}")
        if total_count:
            self.result_card.set_value(f"{total_count} scenes")
            self.result_card.set_body(f"{selected_count} selected for save/download.")
            self.download_step_tree.set_step_status(
                "3. Scene Selection",
                "ready" if selected_count else "warning",
                f"{selected_count} of {total_count} selected.",
            )
        else:
            self.result_card.set_value("0 scenes")
            self.result_card.set_body("Run search to list matching scenes.")
        if self._scenes:
            self.footprint_map.set_highlight(self._current_scene_id(), self._selected_scene_ids())

    def _selected_scene_from_current_row(self) -> SceneRecord | None:
        row = self.results_table.currentRow()
        if row < 0:
            return None
        scene_id_item = self.results_table.item(row, 1)
        if scene_id_item is None:
            return None
        scene_id = scene_id_item.text()
        return next((scene for scene in self._scenes if scene.scene_id == scene_id), None)

    def _update_scene_detail_from_selection(self, *, update_map: bool = True) -> None:
        """Render a compact scene detail panel for the selected result."""

        scene = self._selected_scene_from_current_row()
        if scene is None:
            if self.scene_detail_text.toPlainText():
                self.scene_detail_text.clear()
            if update_map:
                self.footprint_map.set_highlight("", self._selected_scene_ids())
            return

        detail = "\n".join(
            [
                scene.scene_id,
                "",
                f"Acquisition time: {scene.acquisition_time}",
                f"Platform: {scene.platform}",
                f"Orbit direction: {scene.orbit_direction}",
                f"Relative orbit: {scene.relative_orbit}",
                f"Polarization: {scene.polarization}",
                f"Size: {scene.size_mb:g} MB",
                f"Footprint: {'available' if scene.footprint_geojson else 'missing'}",
                f"Status: {scene.status}",
                f"Local path: {scene.local_path or '-'}",
            ]
        )
        if self.scene_detail_text.toPlainText() != detail:
            self.scene_detail_text.setPlainText(detail)
        if update_map:
            self.footprint_map.set_highlight(scene.scene_id, self._selected_scene_ids())

    def _update_scene_row(self, scene_id: str, status: str, local_path: str) -> None:
        for row in range(self.results_table.rowCount()):
            scene_id_item = self.results_table.item(row, 1)
            if scene_id_item is None or scene_id_item.text() != scene_id:
                continue
            status_item = self.results_table.item(row, 8)
            path_item = self.results_table.item(row, 9)
            if status_item is not None:
                status_item.setText(status)
            if path_item is not None:
                path_item.setText(local_path)
            break

    def _current_scene_id(self) -> str:
        scene = self._selected_scene_from_current_row()
        return scene.scene_id if scene is not None else ""

    def _selected_scene_ids(self) -> set[str]:
        return {scene.scene_id for scene in self.selected_scenes()}

    def _refresh_footprint_map(self) -> None:
        try:
            criteria = self._criteria_provider()
        except Exception:
            criteria = None
        self.footprint_map.set_data(
            criteria,
            self._scenes,
            highlighted_scene_id=self._current_scene_id(),
            selected_scene_ids=self._selected_scene_ids(),
        )
        self.footprint_map.set_dem_bbox(self._dem_plan.planned_bbox_snwe if self._dem_plan is not None else None)

    def _apply_results_table_geometry(self) -> None:
        header = self.results_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        header.setDefaultSectionSize(150)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate(self.TABLE_COLUMN_WIDTHS):
            self.results_table.setColumnWidth(column, width)

    def set_dem_plan(self, plan: DemCoveragePlan | None, *, update_map: bool = False) -> None:
        """Store and visualize the latest DEM coverage planning result."""

        self._dem_plan = plan
        if update_map:
            self.footprint_map.set_dem_bbox(plan.planned_bbox_snwe if plan is not None else None)
        if plan is not None:
            label = dem_label_for_source(plan.source_id)
            self.task_card.set_body(f"DEM plan ready: {label} / {plan.planning_mode}.")

    def clear_dem_plan(self, *, update_map: bool = True) -> None:
        """Clear the current DEM planning result and map overlay."""

        self._dem_plan = None
        if update_map:
            self.footprint_map.set_dem_bbox(None)

    @classmethod
    def _task_progress_text(cls, task: DownloadTask) -> str:
        parts = []
        if task.bytes_done or task.bytes_total:
            if task.bytes_total:
                parts.append(f"{cls._format_bytes(task.bytes_done)} / {cls._format_bytes(task.bytes_total)}")
            else:
                parts.append(cls._format_bytes(task.bytes_done))
        if task.speed_bps > 0 and task.status == "running":
            parts.append(f"{cls._format_bytes(task.speed_bps)}/s")
        if task.eta_seconds is not None and task.status == "running":
            parts.append(f"ETA {cls._format_duration(task.eta_seconds)}")
        if task.backend:
            parts.append(f"via {task.backend}")
        return ", ".join(parts)

    def _total_progress_text(self) -> str:
        tasks = list(self._download_task_updates.values())
        total = sum(task.bytes_total for task in tasks if task.bytes_total)
        done = sum(task.bytes_done for task in tasks if task.bytes_done)
        speed = sum(task.speed_bps for task in tasks if task.status == "running")
        if not total and not done and speed <= 0:
            return ""
        parts = []
        if total:
            parts.append(f"{self._format_bytes(done)} / {self._format_bytes(total)}")
        elif done:
            parts.append(self._format_bytes(done))
        if speed > 0:
            parts.append(f"{self._format_bytes(speed)}/s")
        if total and speed > 0 and done < total:
            parts.append(f"ETA {self._format_duration((total - done) / speed)}")
        return ", ".join(parts)

    @staticmethod
    def _format_bytes(value: float | int) -> str:
        size = float(value or 0)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size) < 1024.0 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{size:.1f} TB"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(int(seconds), 0)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes:02d}m"
        if minutes:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"
