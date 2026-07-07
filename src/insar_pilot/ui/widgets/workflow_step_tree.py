"""Workflow step tree widgets for GIS-style task pages."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

from insar_pilot.i18n import tr


@dataclass(frozen=True)
class WorkflowStep:
    """Compact workflow step definition for the left-side task tree."""

    title: str
    status: str = "pending"
    detail: str = ""


class WorkflowStepTree(QTreeWidget):
    """SARscape-style step tree with status and short details."""

    STATUS_LABEL_KEYS = {
        "done": "widget.step_state.done",
        "success": "widget.step_state.done",
        "ready": "widget.step_state.ready",
        "running": "widget.step_state.running",
        "warning": "widget.step_state.warning",
        "failed": "widget.step_state.failed",
        "error": "widget.step_state.failed",
        "pending": "widget.step_state.pending",
        "blocked": "widget.step_state.blocked",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("workflowStepTree")
        self.setHeaderLabels([tr("widget.step_tree.step"), tr("widget.step_tree.state")])
        self.setRootIsDecorated(True)
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMinimumWidth(210)

    def set_steps(self, steps: list[WorkflowStep | tuple[str, str, str]]) -> None:
        """Replace the displayed steps."""

        self.clear()
        for raw_step in steps:
            if isinstance(raw_step, WorkflowStep):
                step = raw_step
            else:
                title, status, detail = raw_step
                step = WorkflowStep(title=title, status=status, detail=detail)
            item = QTreeWidgetItem([step.title, self._state_text(step.status)])
            item.setData(0, Qt.ItemDataRole.UserRole, step.status)
            if step.detail:
                item.setToolTip(0, step.detail)
                item.setToolTip(1, step.detail)
            self.addTopLevelItem(item)
        for column in range(self.columnCount()):
            self.resizeColumnToContents(column)

    def set_step_status(self, title: str, status: str, detail: str = "") -> None:
        """Update a single step by title when it exists."""

        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            if item.text(0) != title:
                continue
            item.setText(1, self._state_text(status))
            item.setData(0, Qt.ItemDataRole.UserRole, status)
            if detail:
                item.setToolTip(0, detail)
                item.setToolTip(1, detail)
            break

    @classmethod
    def _state_text(cls, status: str) -> str:
        key = status.strip().lower() or "pending"
        label_key = cls.STATUS_LABEL_KEYS.get(key)
        return tr(label_key) if label_key else key.title()
