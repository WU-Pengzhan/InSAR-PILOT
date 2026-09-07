"""Behavioral tests for the EOF orbit download service helpers and flow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from insar_pilot.download.models import DownloadTask, SceneRecord
from insar_pilot.download.orbit_service import OrbitDownloadService


def _scene(**overrides) -> SceneRecord:
    defaults = dict(
        scene_id="S1A_IW_SLC__1SDV_20240101T000000_20240101T000030_TEST",
        acquisition_time="2024-01-01T00:00:00Z",
        platform="Sentinel-1A",
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarization="VV",
        size_mb=1000.0,
    )
    defaults.update(overrides)
    return SceneRecord(**defaults)


def _task(tmp_path: Path, scene: SceneRecord) -> DownloadTask:
    return DownloadTask(task_id="orbit-001", scene=scene, output_dir=str(tmp_path), product_type="ORBIT")


def test_mission_detection_from_scene_id_and_platform():
    assert OrbitDownloadService._mission(_scene(scene_id="S1A_IW_SLC")) == "S1A"
    assert OrbitDownloadService._mission(_scene(scene_id="S1B_IW_SLC")) == "S1B"
    assert OrbitDownloadService._mission(_scene(scene_id="S1C_IW_SLC")) == "S1C"
    # Falls back to platform text when scene id lacks the mission token.
    assert OrbitDownloadService._mission(_scene(scene_id="unknown", platform="Sentinel-1B")) == "S1B"


def test_scene_datetime_parses_iso_and_scene_id_token():
    iso = OrbitDownloadService._scene_datetime(_scene(acquisition_time="2024-01-01T00:00:00Z"))
    assert iso.year == 2024 and iso.month == 1 and iso.day == 1

    # Empty acquisition time forces parsing the 15-char token from the scene id.
    from_token = OrbitDownloadService._scene_datetime(
        _scene(acquisition_time="", scene_id="S1A_IW_SLC__1SDV_20240301T101500_x_TEST")
    )
    assert from_token == datetime(2024, 3, 1, 10, 15, 0)


def test_scene_datetime_raises_when_undeterminable():
    with pytest.raises(ValueError, match="Could not determine acquisition time"):
        OrbitDownloadService._scene_datetime(_scene(acquisition_time="", scene_id="no_time_here", file_name=""))


def test_orbit_name_matches_only_when_acquisition_within_validity_window():
    name = "S1A_OPER_AUX_POEORB_OPOD_x_V20231231T225942_20240102T005942.EOF"
    inside = datetime(2024, 1, 1, 0, 0, 0)
    outside = datetime(2024, 2, 1, 0, 0, 0)
    assert OrbitDownloadService._orbit_name_matches(name, inside) is True
    assert OrbitDownloadService._orbit_name_matches(name, outside) is False
    # Malformed name never matches.
    assert OrbitDownloadService._orbit_name_matches("garbage.EOF", inside) is False


def test_download_skips_when_matching_orbit_already_exists(tmp_path: Path):
    scene = _scene()
    orbit_dir = tmp_path / "Orbit"
    orbit_dir.mkdir()
    existing = orbit_dir / "S1A_OPER_AUX_POEORB_OPOD_x_V20231231T225942_20240102T005942.EOF"
    existing.write_bytes(b"orbit")

    result = OrbitDownloadService().download(_task(tmp_path, scene))

    assert result.status == "skipped"
    assert result.local_path == str(existing)


def test_download_returns_cancelled_before_network(tmp_path: Path):
    result = OrbitDownloadService().download(_task(tmp_path, _scene()), cancel_check=lambda: True)

    assert result.status == "cancelled"


def test_download_reports_failure_when_no_eof_produced(tmp_path: Path, monkeypatch):
    service = OrbitDownloadService()
    monkeypatch.setattr(service, "_download_eofs_function", lambda: lambda *a, **k: None)

    result = service.download(_task(tmp_path, _scene()))

    assert result.status == "failed"
    assert "no EOF file" in result.message


def test_download_eofs_function_requires_sentineleof(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "eof.download":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)

    with pytest.raises(RuntimeError, match="sentineleof is required"):
        OrbitDownloadService._download_eofs_function()
