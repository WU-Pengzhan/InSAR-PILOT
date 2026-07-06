"""Top-level module stepper for the GIS workbench shell."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QSizePolicy


class TopWorkflowStepper(QFrame):
    """Horizontal workflow navigation that replaces the left module rail."""

    currentChanged = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("topWorkflowStepper")
        self._buttons: list[QPushButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idClicked.connect(self.currentChanged.emit)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(3, 3, 3, 3)
        self.layout.setSpacing(2)

    def set_steps(self, steps: list[tuple[str, str]]) -> None:
        """Replace the visible steps with ``(label, tooltip)`` tuples."""

        for button in self._buttons:
            self._group.removeButton(button)
            self.layout.removeWidget(button)
            button.deleteLater()
        self._buttons.clear()

        for index, (label, tooltip) in enumerate(steps):
            button = QPushButton(label)
            button.setObjectName("topWorkflowStepButton")
            button.setCheckable(True)
            button.setToolTip(tooltip)
            button.setProperty("stepIndex", index)
            button.setProperty("stepState", "pending")
            self._group.addButton(button, index)
            self.layout.addWidget(button)
            self._buttons.append(button)
        if self._buttons:
            self._buttons[0].setChecked(True)

    def set_current_index(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def set_step_enabled(self, index: int, enabled: bool) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setEnabled(enabled)

    def set_step_state(self, index: int, state: str) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setProperty("stepState", state)
            self._buttons[index].style().unpolish(self._buttons[index])
            self._buttons[index].style().polish(self._buttons[index])
