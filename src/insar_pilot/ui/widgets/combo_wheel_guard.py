"""Interaction guards for scrollable desktop forms."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QAbstractButton, QAbstractScrollArea, QAbstractSpinBox, QComboBox, QWidget


WHEEL_GUARD_PROPERTY = "comboWheelGuardInstalled"
WHEEL_PASSTHROUGH_PROPERTY = "wheelPassthroughInstalled"
BUTTON_FOCUS_GUARD_PROPERTY = "buttonFocusGuardInstalled"


class ComboWheelGuard(QObject):
    """Route wheel gestures from passive form controls back to their scroll area."""

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        if event.type() != QEvent.Type.Wheel:
            return False
        if isinstance(obj, QComboBox):
            view = obj.view()
            if view is not None and view.isVisible():
                return False
            return _forward_wheel_to_parent_scroll(obj, event)
        if isinstance(obj, (QAbstractButton, QAbstractSpinBox)):
            return _forward_wheel_to_parent_scroll(obj, event)
        return False


def install_no_wheel_on_combos(root: QWidget) -> ComboWheelGuard:
    """Install one shared wheel filter on selection controls below ``root``."""

    guard = getattr(root, "_combo_wheel_guard", None)
    if not isinstance(guard, ComboWheelGuard):
        guard = ComboWheelGuard(root)
        setattr(root, "_combo_wheel_guard", guard)

    for combo in root.findChildren(QComboBox):
        if combo.property(WHEEL_GUARD_PROPERTY):
            continue
        combo.installEventFilter(guard)
        combo.setProperty(WHEEL_GUARD_PROPERTY, True)
        combo.setProperty(WHEEL_PASSTHROUGH_PROPERTY, True)
    for widget in [*root.findChildren(QAbstractButton), *root.findChildren(QAbstractSpinBox)]:
        if widget.property(WHEEL_PASSTHROUGH_PROPERTY):
            continue
        widget.installEventFilter(guard)
        widget.setProperty(WHEEL_PASSTHROUGH_PROPERTY, True)
    return guard


def _forward_wheel_to_parent_scroll(widget: QWidget, event) -> bool:
    amount = _wheel_scroll_amount(widget, event)
    area = _nearest_scroll_area(widget, amount)
    if area is None:
        event.accept()
        return True

    bar = area.verticalScrollBar()
    if bar is not None and amount:
        next_value = max(bar.minimum(), min(bar.maximum(), bar.value() + amount))
        bar.setValue(next_value)
    event.accept()
    return True


def _wheel_scroll_amount(widget: QWidget, event) -> int:
    pixel_delta = event.pixelDelta().y()
    if pixel_delta:
        amount = -pixel_delta
    else:
        angle_delta = event.angleDelta().y()
        if not angle_delta:
            return 0
        lines = QApplication.wheelScrollLines() or 3
        step = 24
        area = _nearest_scroll_area(widget, 0)
        if area is not None:
            step = max(area.verticalScrollBar().singleStep(), step)
        amount = -int((angle_delta / 120.0) * lines * step)
    return -amount if event.inverted() else amount


def _nearest_scroll_area(widget: QWidget, amount: int) -> QAbstractScrollArea | None:
    fallback: QAbstractScrollArea | None = None
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea):
            bar = parent.verticalScrollBar()
            if bar is not None and bar.isVisible():
                fallback = fallback or parent
                if amount > 0 and bar.value() < bar.maximum():
                    return parent
                if amount < 0 and bar.value() > bar.minimum():
                    return parent
                if amount == 0:
                    return parent
        parent = parent.parentWidget()
    return fallback


def install_no_scroll_button_focus(root: QWidget) -> None:
    """Keep button clicks from moving focus and forcing scroll-area jumps."""

    for button in root.findChildren(QAbstractButton):
        if button.property(BUTTON_FOCUS_GUARD_PROPERTY):
            continue
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty(BUTTON_FOCUS_GUARD_PROPERTY, True)
