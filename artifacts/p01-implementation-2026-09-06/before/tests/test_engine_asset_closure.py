"""Storage freezes virtual products and detects changes to imported dependencies."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from insar_pilot.domain.engine import Profile
from insar_pilot.infrastructure.asset_closure import copy_closure
from insar_pilot.infrastructure.engine_store import EngineStore


def test_vrt_dependencies_are_frozen_and_original_is_unchanged(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    data = work / "raw.bin"
    data.write_bytes(b"pixels")
    vrt = work / "image.vrt"
    text = '<VRTDataset><SourceFilename relativeToVRT="1">raw.bin</SourceFilename></VRTDataset>'
    vrt.write_text(text)
    staging, final = tmp_path / "staging", tmp_path / "final"
    mapping = copy_closure([vrt], work, staging, final)
    staging.rename(final)
    copied = final / mapping[vrt].relative_to(staging)
    dependency = Path(ET.parse(copied).find("SourceFilename").text)
    data.write_bytes(b"changed")
    assert dependency.read_bytes() == b"pixels"
    assert vrt.read_text() == text


def test_virtual_zip_requires_registered_source_and_preserves_member(tmp_path):
    archive = tmp_path / "source.zip"
    archive.write_bytes(b"archive")
    work = tmp_path / "work"
    work.mkdir()
    vrt = work / "burst.slc.vrt"
    vrt.write_text(f"<VRTDataset><SourceFilename>/vsizip/{archive}/scene.SAFE/image.tiff</SourceFilename></VRTDataset>")
    with pytest.raises(ValueError, match="escapes workspace"):
        copy_closure([vrt], work, tmp_path / "rejected", tmp_path / "unused")
    staging, final = tmp_path / "staging", tmp_path / "final"
    mapping = copy_closure([vrt], work, staging, final, {archive})
    assert mapping[archive].read_bytes() == b"archive"
    text = ET.parse(mapping[vrt]).find("SourceFilename").text
    assert text.startswith(f"/vsizip/{final}") and text.endswith("/scene.SAFE/image.tiff")


def test_imported_dem_dependency_change_is_detected(tmp_path):
    data = tmp_path / "height.tif"
    data.write_bytes(b"heights")
    vrt = tmp_path / "height.vrt"
    vrt.write_text('<VRTDataset><SourceFilename relativeToVRT="1">height.tif</SourceFilename></VRTDataset>')
    store = EngineStore.create(tmp_path / "project", "DEM")
    artifact = store.register_source(vrt, "DEM", Profile.UNASSIGNED)
    assert len(artifact["assets"]) == 2
    data.write_bytes(b"changed heights")
    assert store.availability(artifact) == (False, "input_changed")


def test_safe_directory_member_changes_are_detected(tmp_path):
    safe = tmp_path / "scene.SAFE"
    safe.mkdir()
    (safe / "manifest.safe").write_bytes(b"manifest")
    store = EngineStore.create(tmp_path / "project", "SAFE")
    artifact = store.register_source(safe, "Sentinel1SLC", Profile.SENTINEL1_TOPS)
    assert store.availability(artifact)[0]
    (safe / "measurement.tiff").write_bytes(b"new")
    assert store.availability(artifact) == (False, "input_changed")
