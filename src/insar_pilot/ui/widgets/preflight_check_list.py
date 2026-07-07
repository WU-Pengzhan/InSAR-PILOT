"""Preflight report widget."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from insar_pilot.services.preflight import PreflightReport
from insar_pilot.ui.widgets.status_badge import StatusBadge


class PreflightCheckList(QFrame):
    """Render preflight checks as scan-friendly status rows."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("preflightCheckList")
        self._report = PreflightReport()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        self.summary_label = QLabel("Preflight has not run yet.")
        self.summary_label.setWordWrap(True)
        self.layout.addWidget(self.summary_label)

    def set_report(self, report: PreflightReport) -> None:
        self._report = report
        self._clear_rows()
        if report.blockers:
            self.summary_label.setText(
                f"Preflight found {len(report.blockers)} blocker(s). Resolve them before generation."
            )
        elif report.warnings:
            self.summary_label.setText(f"Preflight completed with {len(report.warnings)} warning(s).")
        else:
            self.summary_label.setText("Preflight complete. No blockers found.")
        for check in report.checks:
            self.layout.addWidget(_PreflightRow(check.label, check.status, check.detail))

    def as_text(self) -> str:
        return self._report.as_text()

    def setPlainText(self, text: str) -> None:  # noqa: N802 - compatibility with QPlainTextEdit call sites
        self._clear_rows()
        self.summary_label.setText(text)

    def toPlainText(self) -> str:  # noqa: N802 - compatibility
        return self.summary_label.text()

    def clear(self) -> None:
        self.set_report(PreflightReport())

    def _clear_rows(self) -> None:
        while self.layout.count() > 1:
            item = self.layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


class _PreflightRow(QFrame):
    def __init__(self, label: str, status: str, detail: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("preflightCheckItem")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        badge_row = QVBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.setSpacing(4)
        self.badge = StatusBadge(status.upper(), status)
        self.label = QLabel(label)
        self.label.setObjectName("summaryCardValue")
        self.detail = QLabel(detail)
        self.detail.setObjectName("summaryCardBody")
        self.detail.setWordWrap(True)
        badge_row.addWidget(self.badge)
        badge_row.addWidget(self.label)
        layout.addLayout(badge_row)
        layout.addWidget(self.detail)
