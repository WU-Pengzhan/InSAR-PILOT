from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from insar_pilot.domain.local_data import AssetRef, LocalReaderError, ReaderErrorCode
from insar_pilot.providers.local import (
    NisarRslcReader,
    ReaderContext,
    Sentinel1SafeReader,
    build_default_local_reader_registry,
)

SENTINEL_MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<xfdu:XFDU xmlns:xfdu="urn:ccsds:schema:xfdu:1"
  xmlns:safe="http://www.esa.int/safe/sentinel-1.0"
  xmlns:s1="http://www.esa.int/safe/sentinel-1.0/sentinel-1"
  xmlns:s1sarl1="http://www.esa.int/safe/sentinel-1.0/sentinel-1/sar/level-1"
  xmlns:gml="http://www.opengis.net/gml">
  <metadataSection>
    <metadataObject ID="platform"><metadataWrap><xmlData><safe:platform>
      <safe:familyName>SENTINEL-1</safe:familyName><safe:number>{platform}</safe:number>
      <safe:instrument><safe:familyName abbreviation="SAR">Synthetic Aperture Radar</safe:familyName>
        <safe:extension><s1sarl1:instrumentMode><s1sarl1:mode>{mode}</s1sarl1:mode></s1sarl1:instrumentMode></safe:extension>
      </safe:instrument>
    </safe:platform></xmlData></metadataWrap></metadataObject>
    <metadataObject ID="measurementOrbitReference"><metadataWrap><xmlData><safe:orbitReference>
      <safe:orbitNumber type="start">56943</safe:orbitNumber>
      <safe:relativeOrbitNumber type="start">171</safe:relativeOrbitNumber>
      <safe:extension><s1:orbitProperties><s1:pass>ASCENDING</s1:pass></s1:orbitProperties></safe:extension>
    </safe:orbitReference></xmlData></metadataWrap></metadataObject>
    <metadataObject ID="generalProductInformation"><metadataWrap><xmlData>
      <s1sarl1:standAloneProductInformation>
        <s1sarl1:productType>{product_type}</s1sarl1:productType>
        <s1sarl1:transmitterReceiverPolarisation>VV</s1sarl1:transmitterReceiverPolarisation>
        <s1sarl1:transmitterReceiverPolarisation>VH</s1sarl1:transmitterReceiverPolarisation>
      </s1sarl1:standAloneProductInformation>
    </xmlData></metadataWrap></metadataObject>
    <metadataObject ID="acquisitionPeriod"><metadataWrap><xmlData><safe:acquisitionPeriod>
      <safe:startTime>2024-12-11T09:55:08.158756</safe:startTime>
      <safe:stopTime>2024-12-11T09:55:35.105043</safe:stopTime>
    </safe:acquisitionPeriod></xmlData></metadataWrap></metadataObject>
    <metadataObject ID="measurementFrameSet"><metadataWrap><xmlData><safe:frameSet><safe:frame>
      <safe:footPrint><gml:coordinates>31.4,120.3 31.8,122.9 30.2,123.2 29.8,120.7</gml:coordinates></safe:footPrint>
    </safe:frame></safe:frameSet></xmlData></metadataWrap></metadataObject>
    <metadataObject ID="processing"><metadataWrap><xmlData><safe:processing><safe:facility>
      <safe:software name="Sentinel-1 IPF" version="003.90" />
    </safe:facility></safe:processing></xmlData></metadataWrap></metadataObject>
  </metadataSection>
</xfdu:XFDU>
"""


def _write_sentinel_zip(
    root: Path,
    *,
    platform: str = "A",
    mode: str = "IW",
    product_type: str = "SLC",
) -> Path:
    native_id = "S1A_IW_SLC__1SDV_20241211T095508_20241211T095535_056943_06FEA1_1C05"
    path = root / f"{native_id}.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            f"{native_id}.SAFE/manifest.safe",
            SENTINEL_MANIFEST.format(platform=platform, mode=mode, product_type=product_type),
        )
    return path


def test_sentinel_reader_reads_zip_and_unpacked_safe(tmp_path: Path) -> None:
    zip_path = _write_sentinel_zip(tmp_path)
    reader = Sentinel1SafeReader()
    source = AssetRef(str(zip_path), "source_product")

    assert reader.probe(source, ReaderContext()).supported
    product = reader.read(source, ReaderContext())

    assert product.mission == "SENTINEL-1"
    assert product.platform == "SENTINEL-1A"
    assert product.product_type == "SLC"
    assert product.acquisition_mode == "IW"
    assert product.acquisition_layout == "TOPS_SWATHS"
    assert product.relative_orbit == 171
    assert product.orbit_identity == "56943"
    assert product.polarizations == ("VH", "VV")
    assert product.frequency_bands == ("C",)
    assert product.footprint_wkt == "POLYGON((120.3 31.4,122.9 31.8,123.2 30.2,120.7 29.8,120.3 31.4))"
    assert product.native_metadata["ipf_version"] == "003.90"

    safe_path = tmp_path / f"{product.native_product_id}.SAFE"
    safe_path.mkdir()
    (safe_path / "manifest.safe").write_text(
        SENTINEL_MANIFEST.format(platform="D", mode="SM", product_type="SLC"),
        encoding="utf-8",
    )
    safe_product = reader.read(AssetRef(str(safe_path), "source_product"), ReaderContext())
    assert safe_product.platform == "SENTINEL-1D"
    assert safe_product.acquisition_layout == "STRIPMAP"
    assert safe_product.source_snapshot.source_kind == "directory"


def test_sentinel_reader_rejects_wrong_product_platform_and_corrupt_zip(tmp_path: Path) -> None:
    reader = Sentinel1SafeReader()
    grd = _write_sentinel_zip(tmp_path, product_type="GRD")
    report = reader.probe(AssetRef(str(grd), "source_product"), ReaderContext())
    assert not report.supported
    assert report.detected_product_type == "GRD"
    with pytest.raises(LocalReaderError) as wrong_product:
        reader.read(AssetRef(str(grd), "source_product"), ReaderContext())
    assert wrong_product.value.code == ReaderErrorCode.WRONG_PRODUCT_TYPE

    grd.unlink()
    unsupported = _write_sentinel_zip(tmp_path, platform="Z")
    with pytest.raises(LocalReaderError) as wrong_platform:
        reader.read(AssetRef(str(unsupported), "source_product"), ReaderContext())
    assert wrong_platform.value.code == ReaderErrorCode.UNSUPPORTED_PLATFORM

    corrupt = tmp_path / "broken.zip"
    corrupt.write_bytes(b"not a zip")
    with pytest.raises(LocalReaderError) as corrupt_error:
        reader.probe(AssetRef(str(corrupt), "source_product"), ReaderContext())
    assert corrupt_error.value.code == ReaderErrorCode.CORRUPT_CONTAINER


def _write_nisar(path: Path, *, product_type: str = "RSLC") -> None:
    h5py = pytest.importorskip("h5py")
    with h5py.File(path, "w") as container:
        identification = container.create_group("/science/LSAR/identification")
        values = {
            "missionId": "NISAR",
            "platformName": "NISAR",
            "productType": product_type,
            "productLevel": "L1",
            "granuleId": "NISAR_L1_PR_RSLC_TEST_001",
            "orbitPassDirection": "Descending",
            "absoluteOrbitNumber": 4783,
            "trackNumber": 13,
            "frameNumber": 71,
            "lookDirection": "Left",
            "radarBand": "L",
            "zeroDopplerStartTime": "2026-06-27T02:40:36.000000000",
            "zeroDopplerEndTime": "2026-06-27T02:41:14.999342105",
            "boundingPolygon": "POLYGON ((-118 36,-117 36,-117 35,-118 36))",
        }
        for key, value in values.items():
            identification.create_dataset(key, data=value)
        identification.create_dataset("listOfFrequencies", data=[b"A", b"B"])
        swaths = container.create_group("/science/LSAR/RSLC/swaths")
        for frequency in ("A", "B"):
            group = swaths.create_group(f"frequency{frequency}")
            group.create_dataset("listOfPolarizations", data=[b"HH", b"HV"])
            group.create_dataset("HH", shape=(2, 3), dtype="complex64", chunks=(1, 3))
            group.create_dataset("HV", shape=(2, 3), dtype="complex64", chunks=(1, 3))


def test_nisar_reader_reads_only_metadata_and_exposes_hdf5_assets(tmp_path: Path) -> None:
    path = tmp_path / "NISAR_L1_PR_RSLC_TEST_001.h5"
    _write_nisar(path)
    reader = NisarRslcReader()
    source = AssetRef(str(path), "source_product")

    assert reader.probe(source, ReaderContext()).supported
    product = reader.read(source, ReaderContext())

    assert product.mission == "NISAR"
    assert product.product_type == "RSLC"
    assert product.track == 13
    assert product.frame == 71
    assert product.frequency_bands == ("A", "B")
    assert product.polarizations == ("HH", "HV")
    datasets = [asset for asset in product.assets if asset.is_hdf5_subdataset]
    assert len(datasets) == 4
    assert datasets[0].subdataset == "/science/LSAR/RSLC/swaths/frequencyA/HH"
    metadata = product.native_metadata["datasets"]
    assert len(metadata) == 4


def test_nisar_reader_rejects_non_rslc_and_invalid_hdf5(tmp_path: Path) -> None:
    gunw = tmp_path / "NISAR_GUNW.h5"
    _write_nisar(gunw, product_type="GUNW")
    reader = NisarRslcReader()
    source = AssetRef(str(gunw), "source_product")

    report = reader.probe(source, ReaderContext())
    assert not report.supported
    assert report.detected_product_type == "GUNW"
    with pytest.raises(LocalReaderError) as wrong_product:
        reader.read(source, ReaderContext())
    assert wrong_product.value.code == ReaderErrorCode.WRONG_PRODUCT_TYPE

    invalid = tmp_path / "invalid.h5"
    invalid.write_bytes(b"not hdf5")
    with pytest.raises(LocalReaderError) as corrupt:
        reader.probe(AssetRef(str(invalid), "source_product"), ReaderContext())
    assert corrupt.value.code == ReaderErrorCode.CORRUPT_CONTAINER


def test_default_local_registry_dispatches_both_product_families(tmp_path: Path) -> None:
    sentinel_path = _write_sentinel_zip(tmp_path)
    nisar_path = tmp_path / "NISAR_L1_PR_RSLC_TEST_001.h5"
    _write_nisar(nisar_path)
    registry = build_default_local_reader_registry()

    sentinel = registry.read(AssetRef(str(sentinel_path), "source_product"))
    nisar = registry.read(AssetRef(str(nisar_path), "source_product"))

    assert sentinel.reader_id == "sentinel1.safe"
    assert nisar.reader_id == "nisar.rslc"
