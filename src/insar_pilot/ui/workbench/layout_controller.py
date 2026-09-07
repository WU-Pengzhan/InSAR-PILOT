"""Centralized Normal/Maximized layout policy for the new Workbench."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, Signal

from insar_pilot.ui.features.search.workspace import SearchWorkspace


class WorkbenchLayoutMode(str, Enum):
    NORMAL = "normal"
    MAXIMIZED = "maximized"


@dataclass(frozen=True)
class WorkbenchLayoutSpec:
    filter_ratio: float
    filter_minimum: int
    map_ratio: float


LAYOUT_SPECS = {
    WorkbenchLayoutMode.NORMAL: WorkbenchLayoutSpec(
        filter_ratio=0.24,
        filter_minimum=280,
        map_ratio=0.58,
    ),
    WorkbenchLayoutMode.MAXIMIZED: WorkbenchLayoutSpec(
        filter_ratio=0.20,
        filter_minimum=300,
        map_ratio=0.64,
    ),
}


class WorkbenchLayoutController(QObject):
    """Apply the only two supported Workbench layout strategies."""

    modeChanged = Signal(str)

    def __init__(self, workspace: SearchWorkspace, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self._mode = WorkbenchLayoutMode.NORMAL

    @property
    def mode(self) -> WorkbenchLayoutMode:
        return self._mode

    def apply(self, mode: WorkbenchLayoutMode) -> None:
        spec = LAYOUT_SPECS[mode]
        main_width = max(self.workspace.main_splitter.width(), self.workspace.width(), 1)
        filter_width = max(spec.filter_minimum, int(main_width * spec.filter_ratio))
        filter_width = min(filter_width, max(spec.filter_minimum, int(main_width * 0.36)))
        self.workspace.main_splitter.setSizes([filter_width, max(1, main_width - filter_width)])

        content_height = max(self.workspace.map_results_splitter.height(), self.workspace.height(), 1)
        map_height = max(1, int(content_height * spec.map_ratio))
        self.workspace.map_results_splitter.setSizes([map_height, max(1, content_height - map_height)])
        self.workspace.setProperty("layoutMode", mode.value)

        changed = mode != self._mode
        self._mode = mode
        if changed:
            self.modeChanged.emit(mode.value)

