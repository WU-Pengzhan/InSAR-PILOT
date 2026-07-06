"""Workflow step tree widgets for GIS-style task pages."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem


@dataclass(frozen=True)
class WorkflowStep:
    """Compact workflow step definition for the left-side task tree."""

    title: str
    status: str = "pending"
    detail: str = ""


class WorkflowStepTree(QTreeWidget):
    """SARscape-style step tree with status and short details."""

    STATUS_LABELS = {
        "done": "Done",
        "success": "Done",
        "ready": "Ready",
        "running": "Running",
        "warning": "Warning",
        "failed": "Failed",
        "error": "Failed",
        "pending": "Pending",
        "blocked": "Blocked",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("workflowStepTree")
        self.setHeaderLabels(["Step", "State"])
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
        return cls.STATUS_LABELS.get(key, key.title())
