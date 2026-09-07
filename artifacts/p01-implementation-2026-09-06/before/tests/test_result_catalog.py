from pathlib import Path

from insar_pilot.services.result_catalog import ResultCatalogService


def _write_vrt(path: Path, width: int = 120, height: int = 45) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<VRTDataset rasterXSize="{width}" rasterYSize="{height}"></VRTDataset>',
        encoding="utf-8",
    )


def test_catalog_collapses_sidecars_and_matches_reference_slc(tmp_path: Path):
    work = tmp_path / "work"
    slc_dir = work / "merged" / "SLC" / "20240101"
    _write_vrt(slc_dir / "20240101.slc.full.vrt")
    (slc_dir / "20240101.slc.full.xml").write_text("<image/>", encoding="utf-8")
    pair = work / "merged" / "interferograms" / "20240101_20240113"
    _write_vrt(pair / "fine.int.full.vrt")
    _write_vrt(pair / "filt_fine.int.vrt")
    _write_vrt(pair / "filt_fine.cor.vrt")
    _write_vrt(pair / "filt_fine.unw.vrt")

    products = ResultCatalogService().discover(work, reference_date="20240101")

    assert [product.kind for product in products] == [
        "slc",
        "wrapped_interferogram",
        "wrapped_interferogram",
        "coherence",
        "unwrapped_phase",
    ]
    slc = products[0]
    assert slc.path.endswith(".full.vrt")
    assert (slc.width, slc.height) == (120, 45)
    interferograms = [item for item in products if item.kind == "wrapped_interferogram"]
    assert {item.variant for item in interferograms} == {"filtered", "unfiltered"}
    assert all(item.paired_slc_path == slc.path for item in interferograms)
    assert len({item.product_id for item in products}) == len(products)


def test_catalog_warns_when_interferogram_reference_slc_is_missing(tmp_path: Path):
    pair = tmp_path / "merged" / "interferograms" / "20240101_20240113"
    _write_vrt(pair / "filt_fine.int.vrt")

    products = ResultCatalogService().discover(tmp_path)

    assert len(products) == 1
    assert products[0].paired_slc_path == ""
    assert "abs(INT)" in products[0].warning


def test_catalog_classifies_supported_custom_file(tmp_path: Path):
    source = tmp_path / "20240101_20240113" / "filt_fine.cor.vrt"
    _write_vrt(source, 33, 22)

    product = ResultCatalogService().product_from_path(source)

    assert product.kind == "coherence"
    assert product.pair_label == "20240101 / 20240113"
    assert (product.width, product.height) == (33, 22)
    assert product.product_id.startswith("custom:coherence:")


def test_catalog_rejects_non_radar_custom_file(tmp_path: Path):
    source = tmp_path / "notes.txt"
    source.write_text("not a result", encoding="utf-8")

    try:
        ResultCatalogService().product_from_path(source)
    except ValueError as exc:
        assert "ISCE" in str(exc)
    else:
        raise AssertionError("Expected a non-radar custom file to be rejected.")


def test_catalog_accepts_geometry_raster_through_advanced_browser(tmp_path: Path):
    source = tmp_path / "geom_reference" / "hgt.rdr.full.vrt"
    _write_vrt(source, 48, 32)

    product = ResultCatalogService().product_from_path(source)

    assert product.kind == "custom_raster"
    assert product.display_name.startswith("Other raster")
    assert (product.width, product.height) == (48, 32)
