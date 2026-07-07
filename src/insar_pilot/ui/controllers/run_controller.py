"""Run-monitor workflow controller extracted from MainWindow.

Owns the ProcessRunner-driven execution of the generated ``run_files``: building
the command queue, streaming state into the steps tree, and reacting to the
runner's command/queue signals (including the visualization and data-preparation
branches whose results feed the results/setup controllers). Behavior is
identical to the code that previously lived on ``MainWindow``; the controller
keeps a reference to the window for shell-level callbacks and shared run state.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMenu, QMessageBox, QTreeWidgetItem

from insar_pilot.domain.project import ProjectStatus, RunStep, RunSubcommand, StepStatus
from insar_pilot.services.command_plan import CommandPlan
from insar_pilot.services.runfile_plan import (
    build_parallel_batch_command,
    parse_result_markers,
    parse_run_file,
    split_batches_for_parallelism,
)
from insar_pilot.services.stack_generator import StackWorkflowService

if TYPE_CHECKING:
    from insar_pilot.ui.main_window import MainWindow


class RunController(QObject):
    """Coordinates the run-monitor page and the ProcessRunner execution queue."""

    def __init__(
        self,
        window: MainWindow,
        *,
        workflow_service: StackWorkflowService,
    ) -> None:
        super().__init__(window)
        self._window = window
        self.workflow_service = workflow_service

    # ------------------------------------------------------------------
    # Run actions
    # ------------------------------------------------------------------
    def run_next_step(self) -> None:
        self._window._update_project_from_form()
        step = self.workflow_service.next_runnable_step(self._window.project)
        if step is None:
            QMessageBox.information(
                self._window, "No runnable steps", "There are no remaining run files to execute."
            )
            return
        self._run_steps([step])

    def run_selected_step(self) -> None:
        self._window._update_project_from_form()
        steps = self._selected_steps()
        if not steps:
            QMessageBox.information(
                self._window,
                "No step selected",
                "Select one or more run steps in Run Monitor, then click 'Run Selected Step'.",
            )
            return
        for step in steps:
            if not step.path:
                self._window._show_error("Invalid step", f"{step.name} does not have a valid run file path.")
                return
            if not Path(step.path).expanduser().exists():
                self._window._show_error(
                    "Run file missing", f"Run file was not found for {step.name}:\n{step.path}"
                )
                return

        if len(steps) == 1:
            self._window.statusBar().showMessage(
                "Running selected step only. Downstream step statuses are left unchanged.",
                7000,
            )
        else:
            self._window.statusBar().showMessage(
                f"Running {len(steps)} selected steps in run-file order. Downstream statuses are left unchanged.",
                7000,
            )
        self._run_steps(steps)

    def run_remaining_steps(self) -> None:
        self._window._update_project_from_form()
        steps = self.workflow_service.remaining_steps(self._window.project)
        if not steps:
            QMessageBox.information(
                self._window, "No runnable steps", "There are no remaining run files to execute."
            )
            return
        self._run_steps(steps)

    def stop_execution(self) -> None:
        self._window._stop_requested = True
        self._window.runner.stop()

    def _run_steps(self, steps: list[RunStep]) -> None:
        if self._window.runner.is_running():
            QMessageBox.warning(self._window, "Busy", "Another command is already running.")
            return

        self._window._stop_requested = False
        plans: list[CommandPlan] = []
        runfile_parallel = max(1, self._window.project.workflow.num_proc)
        for step in steps:
            run_file = Path(step.path)
            try:
                parsed_batches = parse_run_file(run_file)
            except Exception as exc:
                self._window._show_error("Run file parsing failed", f"{step.name}: {exc}")
                return

            if not parsed_batches:
                self._window._show_error("Run file parsing failed", f"{step.name}: no executable commands found.")
                return

            batches = split_batches_for_parallelism(parsed_batches, runfile_parallel)
            command_logs = {
                cmd.index: str(self._window.project.logs_dir() / f"{step.name}.cmd_{cmd.index:03d}.log")
                for batch in batches
                for cmd in batch
            }
            step.subcommands = [
                RunSubcommand(
                    index=index,
                    command=command,
                    status=StepStatus.PENDING,
                    log_path=log_path,
                    exit_code=None,
                )
                for index, command, log_path in (
                    (cmd.index, cmd.command, command_logs[cmd.index])
                    for batch in batches
                    for cmd in batch
                )
            ]
            step.subcommands.sort(key=lambda item: item.index)
            step.status = StepStatus.PENDING
            step.exit_code = None
            step.last_message = ""
            step.log_path = str(self._window.project.logs_dir() / f"{step.name}.batch_001.log")

            total_batches = len(batches)
            for batch_index, batch in enumerate(batches, start=1):
                batch_log_path = str(self._window.project.logs_dir() / f"{step.name}.batch_{batch_index:03d}.log")
                plans.append(
                    CommandPlan(
                        label=f"{step.name} [batch {batch_index}/{total_batches}]",
                        command=build_parallel_batch_command(batch, command_logs),
                        cwd=str(self._window.project.resolved_work_dir()),
                        log_path=batch_log_path,
                        step_name=step.name,
                        is_generation=False,
                        kind="step_batch",
                        metadata={
                            "subcommand_indices": [cmd.index for cmd in batch],
                            "batch_index": batch_index,
                            "batch_total": total_batches,
                        },
                    )
                )

        self._window.project.state.status = ProjectStatus.RUNNING
        self._window.project.state.current_step = steps[0].name
        self._window.project.state.last_error = ""
        self._window.project_store.save(self._window.project)
        self._window.runner.run_queue(plans)
        self._window.refresh_status_labels()
        self._window._set_current_page("monitor")

    # ------------------------------------------------------------------
    # Runner signal handlers
    # ------------------------------------------------------------------
    def _handle_command_started(self, plan: CommandPlan) -> None:
        self._window.append_log(f"\n=== {plan.label} ===\n")
        self._window.project.state.current_step = plan.step_name or plan.label
        if plan.kind == "step_batch":
            step = self._find_step(plan.step_name)
            if step is not None:
                step.status = StepStatus.RUNNING
                step.exit_code = None
                for sub_index in plan.metadata.get("subcommand_indices", []):
                    subcommand = self._find_subcommand(step, int(sub_index))
                    if subcommand is not None:
                        subcommand.status = StepStatus.RUNNING
                        subcommand.exit_code = None
        elif plan.kind == "visualization":
            self._window.preview_image_label.setPixmap(QPixmap())
            self._window.preview_image_label.setText("Rendering preview ...")
            self._window.preview_image_label.resize(480, 320)
        self.refresh_steps_view()
        self._window.refresh_status_labels()
        self._window._sync_summary_sidebar()

    def _handle_command_finished(self, plan: CommandPlan, exit_code: int) -> None:
        stopped = self._window._stop_requested and exit_code != 0
        if plan.kind == "generation":
            if stopped:
                self._window.project.state.status = ProjectStatus.CANCELLED
            elif exit_code == 0:
                self.workflow_service.synchronize_project_steps(self._window.project)
                self._window.project.state.status = ProjectStatus.GENERATED
            else:
                self._window.project.state.status = ProjectStatus.FAILED
                self._window.project.state.last_error = f"Workflow generation failed with exit code {exit_code}"
        elif plan.kind == "step_batch":
            step = self._find_step(plan.step_name)
            if step is not None:
                sub_indices = [int(item) for item in plan.metadata.get("subcommand_indices", [])]
                marker_text = ""
                try:
                    marker_text = Path(plan.log_path).read_text(encoding="utf-8")
                except OSError:
                    marker_text = ""
                marker_codes = parse_result_markers(marker_text)
                for sub_index in sub_indices:
                    subcommand = self._find_subcommand(step, sub_index)
                    if subcommand is None:
                        continue
                    rc = marker_codes.get(sub_index)
                    if rc is None:
                        if stopped:
                            subcommand.status = StepStatus.CANCELLED
                            subcommand.exit_code = None
                        elif exit_code != 0:
                            subcommand.status = StepStatus.FAILED
                            subcommand.exit_code = -1
                        continue
                    subcommand.exit_code = rc
                    subcommand.status = StepStatus.SUCCESS if rc == 0 else StepStatus.FAILED

                failed_sub = next(
                    (
                        item
                        for item in sorted(step.subcommands, key=lambda cmd: cmd.index)
                        if item.status == StepStatus.FAILED
                    ),
                    None,
                )
                if stopped:
                    step.status = StepStatus.CANCELLED
                    step.exit_code = None
                    step.last_message = "Stopped by user."
                elif failed_sub is not None or exit_code != 0:
                    step.status = StepStatus.FAILED
                    step.exit_code = exit_code
                    failed_index = failed_sub.index if failed_sub is not None else "?"
                    failed_cmd = failed_sub.command if failed_sub is not None else "(unknown command)"
                    step.last_message = f"Failed subcommand #{failed_index}: {failed_cmd}"
                elif all(item.status == StepStatus.SUCCESS for item in step.subcommands):
                    step.status = StepStatus.SUCCESS
                    step.exit_code = 0
                    step.last_message = "All subcommands completed successfully."
                else:
                    step.status = StepStatus.RUNNING
                    step.exit_code = None
                    step.last_message = "Waiting for remaining batch commands."

            if stopped:
                self._window.project.state.status = ProjectStatus.CANCELLED
            elif step is None:
                if exit_code != 0:
                    self._window.project.state.status = ProjectStatus.FAILED
                    self._window.project.state.last_error = f"{plan.step_name} failed with exit code {exit_code}"
                else:
                    self._window.project.state.status = ProjectStatus.RUNNING
            elif step is not None and step.status == StepStatus.FAILED:
                self._window.project.state.status = ProjectStatus.FAILED
                self._window.project.state.last_error = (
                    step.last_message or f"{plan.step_name} failed with exit code {exit_code}"
                )
            elif all(item.status == StepStatus.SUCCESS for item in self._window.project.state.steps):
                self._window.project.state.status = ProjectStatus.COMPLETED
            else:
                self._window.project.state.status = ProjectStatus.RUNNING
        elif plan.kind == "visualization":
            pending = self._window._pending_visualization
            if exit_code != 0:
                self._window.project.state.last_error = f"Visualization failed with exit code {exit_code}"
                self._window.visual_status_text.setPlainText(
                    f"{pending.summary if pending else ''}\n\nStatus: failed (exit={exit_code})"
                )
                self._window.preview_image_label.setPixmap(QPixmap())
                self._window.preview_image_label.setText("Visualization failed. Check the log for details.")
                self._window.preview_image_label.resize(480, 320)
            else:
                if pending is not None:
                    if pending.action == "preview":
                        self._window.project.visualization.last_preview_path = pending.output_bmp_path
                        self._window.project.visualization.last_render_signature = pending.render_signature
                    self._window.project.visualization.last_log_path = pending.log_path
                    self._window.project.visualization.last_render_summary = pending.summary
                    if pending.action == "preview":
                        self._window.results_controller._display_preview_image(
                            pending.output_bmp_path, pending.summary
                        )
                    self._window.visual_status_text.setPlainText(
                        f"{pending.summary}\n\nStatus: success\n"
                        f"Output: {pending.output_bmp_path}\nLog: {pending.log_path}"
                    )
        else:
            if stopped:
                self._window.project.state.status = ProjectStatus.CANCELLED
            elif exit_code != 0:
                self._window.project.state.status = ProjectStatus.FAILED
                self._window.project.state.last_error = f"{plan.label} failed with exit code {exit_code}"

        self._window.project_store.save(self._window.project)
        self.refresh_steps_view()
        self._window.results_controller.refresh_outputs_view()
        self._window.refresh_status_labels()
        self._window._sync_summary_sidebar()

    def _handle_queue_finished(self, success: bool, message: str) -> None:
        if self._window._pending_visualization is not None:
            pending = self._window._pending_visualization
            self._window._pending_visualization = None
            if self._window._last_visualization_saved_status is not None:
                self._window.project.state.status = self._window._last_visualization_saved_status
            self._window._last_visualization_saved_status = None
            self._window.project.state.current_step = ""
            try:
                job_path = Path(pending.job_dir).expanduser().resolve()
                output_path = Path(pending.output_bmp_path).expanduser().resolve()
                if not output_path.is_relative_to(job_path):
                    shutil.rmtree(job_path, ignore_errors=True)
            except Exception:
                pass
            if success:
                self._window.project.state.last_error = ""
                self._window.statusBar().showMessage(f"Visualization completed: {pending.output_bmp_path}", 5000)
            else:
                self._window.statusBar().showMessage("Visualization failed. Check logs.", 5000)
            self._window.project_store.save(self._window.project)
            self._window.refresh_status_labels()
            self._window._update_action_states()
            self._window._sync_summary_sidebar()
            return

        if self._window._pending_preparation is not None:
            pending = self._window._pending_preparation
            self._window._pending_preparation = None
            if success:
                self._window.setup_controller._commit_preparation_result(
                    pending["prepared"],
                    str(pending["dem_path"]),
                    str(pending["signature"]),
                )
                message = "Data validation and preparation finished."
            else:
                self._window.project.state.status = ProjectStatus.FAILED
                self._window.project.state.last_error = (
                    self._window.project.state.last_error or "Data preparation failed."
                )
                self._window.project_store.save(self._window.project)

        if self._window._pending_preparation is None:
            if self._window._stop_requested and not success:
                self._window.project.state.status = ProjectStatus.CANCELLED
            elif success:
                if self._window.project.state.steps and all(
                    item.status == StepStatus.SUCCESS for item in self._window.project.state.steps
                ):
                    self._window.project.state.status = ProjectStatus.COMPLETED
                elif self._window.project.state.steps:
                    self._window.project.state.status = ProjectStatus.GENERATED
                elif self._window.setup_controller._is_prepared_for_current_sources():
                    self._window.project.state.status = ProjectStatus.READY
            elif self._window.project.state.status == ProjectStatus.RUNNING:
                self._window.project.state.status = ProjectStatus.FAILED

        if self._window._stop_requested and not success:
            self._window.project.state.status = ProjectStatus.CANCELLED
        self._window._stop_requested = False
        self._window.project_store.save(self._window.project)
        self._window.refresh_status_labels()
        self._window._update_action_states()
        self._window._sync_summary_sidebar()
        self._window.statusBar().showMessage(message, 5000)

    def _handle_runner_state_changed(self, state: str) -> None:
        if state == "running" and not self._window.log_dock.isVisible():
            self._window.log_dock.show()
        self._window._update_action_states()

    # ------------------------------------------------------------------
    # Steps view / selection
    # ------------------------------------------------------------------
    def refresh_steps_view(self) -> None:
        self._window.steps_tree.clear()
        for step in self._window.project.state.steps:
            item = QTreeWidgetItem(
                [
                    step.name,
                    step.status.value,
                    "" if step.exit_code is None else str(step.exit_code),
                    step.log_path,
                    step.last_message,
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, step.name)
            for subcommand in sorted(step.subcommands, key=lambda cmd: cmd.index):
                child = QTreeWidgetItem(
                    [
                        f"#{subcommand.index}: {subcommand.command}",
                        subcommand.status.value,
                        "" if subcommand.exit_code is None else str(subcommand.exit_code),
                        subcommand.log_path,
                        "",
                    ]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, step.name)
                item.addChild(child)
            self._window.steps_tree.addTopLevelItem(item)
        self._window.steps_tree.expandAll()
        self._window.run_monitor_page.empty_state_label.setVisible(
            self._window.steps_tree.topLevelItemCount() == 0
        )
        self._window.setup_controller._refresh_runfile_estimates()
        self._window._update_action_states()
        self._window._refresh_navigation_status()

    def _find_step(self, name: str) -> RunStep | None:
        for step in self._window.project.state.steps:
            if step.name == name:
                return step
        return None

    def _step_item_from_item(self, item: QTreeWidgetItem | None) -> QTreeWidgetItem | None:
        if item is None:
            return None
        current = item
        while current.parent() is not None:
            current = current.parent()
        return current

    def _selected_steps(self) -> list[RunStep]:
        selected_items = self._window.steps_tree.selectedItems()
        if not selected_items:
            current = self._window.steps_tree.currentItem()
            selected_items = [current] if current is not None else []

        names: set[str] = set()
        for item in selected_items:
            step_item = self._step_item_from_item(item)
            if step_item is None:
                continue
            step_name = str(step_item.data(0, Qt.ItemDataRole.UserRole) or step_item.text(0)).strip()
            if step_name:
                names.add(step_name)

        if not names:
            return []
        # Keep deterministic execution order by run-file order.
        return [step for step in self._window.project.state.steps if step.name in names]

    def _open_steps_context_menu(self, pos) -> None:
        item = self._window.steps_tree.itemAt(pos)
        step_item = self._step_item_from_item(item)
        if step_item is None:
            return

        step_name = str(step_item.data(0, Qt.ItemDataRole.UserRole) or step_item.text(0)).strip()
        if step_name:
            matching = self._window.steps_tree.findItems(step_name, Qt.MatchFlag.MatchExactly, 0)
            if matching and not matching[0].isSelected():
                self._window.steps_tree.clearSelection()
                matching[0].setSelected(True)
                self._window.steps_tree.setCurrentItem(matching[0])

        menu = QMenu(self._window)
        run_action = menu.addAction("Run Selected Step")
        run_action.setEnabled((not self._window.runner.is_running()) and bool(self._selected_steps()))
        chosen = menu.exec(self._window.steps_tree.viewport().mapToGlobal(pos))
        if chosen == run_action:
            self.run_selected_step()

    @staticmethod
    def _find_subcommand(step: RunStep, index: int) -> RunSubcommand | None:
        for item in step.subcommands:
            if item.index == index:
                return item
        return None

    def _handle_step_selection_changed(self) -> None:
        self._window._update_action_states()
        self._update_step_detail_panel()

    def _update_step_detail_panel(self) -> None:
        selected_steps = self._selected_steps()
        if len(selected_steps) > 1:
            lines = [f"Selected steps: {len(selected_steps)}", ""]
            lines.extend(f"- {step.name} ({step.status.value})" for step in selected_steps)
            self._window.command_detail_text.setPlainText("\n".join(lines))
            return

        item = self._window.steps_tree.currentItem()
        if item is None:
            self._window.command_detail_text.setPlainText("")
            return
        root = self._step_item_from_item(item)
        if root is None:
            return
        step = self._find_step(str(root.data(0, Qt.ItemDataRole.UserRole) or root.text(0)))
        if step is None:
            self._window.command_detail_text.setPlainText("")
            return
        lines = [
            f"Step: {step.name}",
            f"Status: {step.status.value}",
            f"Run file: {step.path}",
            f"Batch log: {step.log_path}",
            f"Message: {step.last_message or '-'}",
        ]
        if item.parent() is not None:
            text = item.text(0)
            try:
                sub_index = int(text.split(":", 1)[0].lstrip("#"))
            except ValueError:
                sub_index = -1
            sub = self._find_subcommand(step, sub_index)
            if sub is not None:
                lines.extend(
                    [
                        "",
                        f"Subcommand #{sub.index}",
                        f"Command: {sub.command}",
                        f"Status: {sub.status.value}",
                        f"Exit: {sub.exit_code if sub.exit_code is not None else '-'}",
                        f"Log: {sub.log_path}",
                    ]
                )
        else:
            if step.subcommands:
                lines.extend(["", "Subcommands:"])
                lines.extend(f"- #{sub.index}: {sub.command}" for sub in step.subcommands)
        self._window.command_detail_text.setPlainText("\n".join(lines))
