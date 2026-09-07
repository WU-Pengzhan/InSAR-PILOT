"""Structured extraction from existing scientific evidence, not log-derived success."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from insar_pilot.domain.engine import QCCheck, QCMetric, QCReport


def reevaluate(store: Any, run_id: str, policy_version: str, thresholds: list[dict[str, Any]]) -> QCReport:
    """Apply new scientific rules to saved facts while retaining structural checks."""
    previous = store.latest_qc(run_id)
    if previous is None:
        raise ValueError("There are no saved metrics to re-evaluate.")
    observations = {c["metric"]["metric_id"]: QCMetric(**c["metric"]) for c in previous["checks"] if c.get("metric")}
    checks = [c for c in previous["checks"] if c["check"]["metric_id"] == "output.contract"]
    rules = {item["metric_id"]: item for item in thresholds}
    if "output.contract" in rules:
        raise ValueError("Structural output contracts cannot be replaced by scientific thresholds.")
    for metric_id in sorted((observations.keys() | rules.keys()) - {"output.contract"}):
        rule = rules.get(metric_id, {})
        check = QCCheck(
            metric_id,
            metric_id,
            minimum=rule.get("minimum"),
            maximum=rule.get("maximum"),
            blocking=rule.get("blocking", False),
            version=policy_version,
        )
        checks.append(check.evaluate(observations.get(metric_id)))
    report = QCReport(policy_version=policy_version, checks=tuple(checks))
    store.evaluate_qc(run_id, report)
    return report


def structural_report(valid: bool, reason: str, metrics: tuple[QCMetric, ...] = ()) -> QCReport:
    required = QCCheck("output.contract", "output.contract", expected=True, blocking=True)
    checks = [required.evaluate(QCMetric("output.contract", valid, source=reason))]
    checks.extend(QCCheck(m.metric_id, m.metric_id).evaluate(m) for m in metrics)
    return QCReport(checks=tuple(checks))


def sentinel_metrics(workspace: Path, official_label: str) -> tuple[QCMetric, ...]:
    metrics: list[QCMetric] = []
    roots = {"average_baseline": "baselines", "pairs_misreg": "misreg", "timeseries_misreg": "misreg"}
    root = roots.get(official_label)
    if root is None:
        return ()
    for path in sorted((workspace / root).rglob("*.txt")):
        if path.stat().st_size > 2 * 1024 * 1024:
            continue
        for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            match = re.fullmatch(r"\s*([^:]+):\s*([-+\d.eE]+)\s*", line)
            if not match:
                continue
            label, text = match.groups()
            try:
                value = float(text)
            except ValueError:
                continue
            unit = "m" if label.startswith(("Bperp", "Bpar")) else ""
            metrics.append(
                QCMetric(
                    f"{root}.{path.relative_to(workspace)}.{number}.{label.strip()}",
                    value,
                    unit,
                    f"{path}:{number}",
                    scope=str(path.relative_to(workspace)),
                )
            )
    return tuple(metrics)
