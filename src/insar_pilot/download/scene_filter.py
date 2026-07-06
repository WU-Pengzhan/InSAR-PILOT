"""Placeholder scene filtering helpers for Sentinel-1 search results."""

from __future__ import annotations

from insar_pilot.download.models import SceneRecord


def filter_by_orbit_direction(scenes: list[SceneRecord], orbit_direction: str) -> list[SceneRecord]:
    """Return scenes matching ASCENDING/DESCENDING, or all scenes for ANY."""

    value = orbit_direction.strip().upper()
    if value in {"", "ANY"}:
        return list(scenes)
    return [scene for scene in scenes if scene.orbit_direction.upper() == value]


def filter_by_relative_orbit(scenes: list[SceneRecord], relative_orbit: int | None) -> list[SceneRecord]:
    """Return scenes matching a relative orbit number when provided."""

    if relative_orbit is None:
        return list(scenes)
    return [scene for scene in scenes if scene.relative_orbit == relative_orbit]


def sort_by_time(scenes: list[SceneRecord], *, descending: bool = False) -> list[SceneRecord]:
    """Sort scenes by provider acquisition timestamp text."""

    return sorted(scenes, key=lambda scene: scene.acquisition_time, reverse=descending)


def filter_by_min_coverage(scenes: list[SceneRecord], min_coverage_percent: float | None) -> list[SceneRecord]:
    """Return scenes at or above a coverage threshold when provided."""

    if min_coverage_percent is None:
        return list(scenes)
    return [scene for scene in scenes if scene.coverage_percent >= min_coverage_percent]
