"""Wheel routing for scrollable controls nested in the Data page."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QScrollArea


class NestedScrollFilter(QObject):
    """Pass boundary wheel movement from an inner control to the page.

    Qt's item/text views normally consume wheel events even when their own
    scrollbar cannot move.  Inside the Data page's QScrollArea that creates
    several dead zones where the page appears to stutter or stop scrolling.
    """

    def __init__(
        self,
        scroll_widget: QAbstractScrollArea,
        outer_scroll: QScrollArea | None = None,
    ) -> None:
        super().__init__(scroll_widget)
        self.scroll_widget = scroll_widget
        self.outer_scroll = outer_scroll

    def set_outer_scroll(self, outer_scroll: QScrollArea) -> None:
        """Set the page scroll area after the control panel is assembled."""

        self.outer_scroll = outer_scroll

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.Wheel:
            scrollbar = self.scroll_widget.verticalScrollBar()
            angle_delta = event.angleDelta().y()
            pixel_delta = event.pixelDelta().y()
            delta = pixel_delta or angle_delta
            at_top = scrollbar.value() <= scrollbar.minimum()
            at_bottom = scrollbar.value() >= scrollbar.maximum()
            if (delta > 0 and not at_top) or (delta < 0 and not at_bottom):
                return False
            if self.outer_scroll is not None:
                outer_bar = self.outer_scroll.verticalScrollBar()
                if pixel_delta:
                    distance = pixel_delta
                else:
                    wheel_steps = angle_delta / 120.0
                    distance = wheel_steps * QApplication.wheelScrollLines() * max(outer_bar.singleStep(), 16)
                outer_bar.setValue(outer_bar.value() - round(distance))
                event.accept()
                return True
        return False
