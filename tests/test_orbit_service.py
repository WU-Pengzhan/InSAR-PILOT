"""Public precise-EOF acquisition with identity and structural validation."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from test_p01_acquisition import eof_file, scene

from insar_pilot.download.models import DownloadTask
from insar_pilot.download.orbit_service import OrbitDownloadService


def task(root: Path) -> DownloadTask:
    return DownloadTask(task_id="orbit-001", scene=scene(), output_dir=str(root), product_type="ORBIT")


@pytest.mark.parametrize("letter", list("ABCD"))
def test_mission_detection_requires_consistent_identity(letter):
    assert OrbitDownloadService._mission(scene(letter)) == "S1" + letter
    with pytest.raises(ValueError, match="unique"):
        OrbitDownloadService._mission(replace(scene(letter), platform="Sentinel-1Z", scene_id="unknown"))


def test_conflicting_satellite_identity_is_rejected():
    with pytest.raises(ValueError, match="unique"):
        OrbitDownloadService._mission(replace(scene("A"), platform="Sentinel-1B"))


def test_full_scene_interval_is_required():
    start, stop = OrbitDownloadService._scene_interval(scene())
    assert start == datetime(2026, 1, 2, 12, 0, 0)
    assert stop == datetime(2026, 1, 2, 12, 0, 30)
    with pytest.raises(ValueError, match="start and stop"):
        OrbitDownloadService._scene_interval(replace(scene(), scene_id="unknown", file_name=""))


def test_orbit_name_must_cover_stop_as_well_as_start():
    name = "S1D_OPER_AUX_POEORB_OPOD_x_V20260101T225942_20260102T120015.EOF"
    start, stop = OrbitDownloadService._scene_interval(scene())
    assert OrbitDownloadService._orbit_name_matches(name, start)
    assert not OrbitDownloadService._orbit_name_matches(name, start, stop)
    assert not OrbitDownloadService._orbit_name_matches("garbage.EOF", start)


def test_reuse_requires_valid_xml_and_complete_interval(tmp_path, monkeypatch):
    folder = tmp_path / "Orbit"
    folder.mkdir()
    existing = eof_file(folder)
    service = OrbitDownloadService()
    monkeypatch.setattr(service, "candidates", lambda *args: pytest.fail("valid cache must avoid network"))
    result = service.download(task(tmp_path))
    assert result.status == "skipped"
    assert result.local_path == str(existing)


def test_invalid_cached_eof_is_quarantined_and_not_reported_success(tmp_path, monkeypatch):
    folder = tmp_path / "Orbit"
    folder.mkdir()
    existing = eof_file(folder)
    existing.write_bytes(b"invalid")
    service = OrbitDownloadService()
    monkeypatch.setattr(service, "candidates", lambda *args: [])
    result = service.download(task(tmp_path))
    assert result.status == "unavailable"
    assert not existing.exists()
    assert list(folder.glob(".invalid/*/*.EOF"))


def test_cancel_before_network(tmp_path, monkeypatch):
    service = OrbitDownloadService()
    monkeypatch.setattr(service, "candidates", lambda *args: pytest.fail("cancelled request must avoid network"))
    assert service.download(task(tmp_path), cancel_check=lambda: True).status == "cancelled"


def test_catalogue_error_preserves_failure(tmp_path, monkeypatch):
    service = OrbitDownloadService()

    def fail(*args):
        raise RuntimeError("catalogue unavailable")

    monkeypatch.setattr(service, "candidates", fail)
    result = service.download(task(tmp_path))
    assert result.status == "failed"
    assert "catalogue unavailable" in result.message
