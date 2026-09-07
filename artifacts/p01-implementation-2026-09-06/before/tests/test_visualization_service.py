from pathlib import Path

from insar_pilot.services.visualization_service import VisualizationRequest, VisualizationService


def test_build_slc_visualization_without_looks(tmp_path: Path):
    source = tmp_path / "input.slc"
    source.write_text("x", encoding="utf-8")
    Path(f"{source}.xml").write_text("<xml/>", encoding="utf-8")
    work_dir = tmp_path / "work"
    logs_dir = tmp_path / "logs"
    work_dir.mkdir()

    request = VisualizationRequest(
        mode="slc",
        primary_input_path=str(source),
        azimuth_looks=1,
        range_looks=1,
        work_dir=str(work_dir),
        output_bmp_path=str(tmp_path / "preview.bmp"),
    )
    result = VisualizationService().build(request, logs_dir)

    assert "-e='abs(a)'" in result.plan.command
    assert "source_mode = \"amplitude_real\"" in result.plan.command
    assert "output_mode = \"slc_grayscale\"" in result.plan.command
    assert "log1p" in result.plan.command
    assert "gdal_translate -of BMP" in result.plan.command
    assert "looks.py" not in result.plan.command
    assert result.output_bmp_path.endswith(".bmp")


def test_build_interferogram_visualization_with_looks(tmp_path: Path):
    source = tmp_path / "fine.int"
    source.write_text("x", encoding="utf-8")
    Path(f"{source}.xml").write_text("<xml/>", encoding="utf-8")
    work_dir = tmp_path / "work"
    logs_dir = tmp_path / "logs"
    work_dir.mkdir()

    request = VisualizationRequest(
        mode="interferogram",
        primary_input_path=str(source),
        azimuth_looks=3,
        range_looks=5,
        work_dir=str(work_dir),
        output_bmp_path=str(tmp_path / "int.bmp"),
    )
    result = VisualizationService().build(request, logs_dir)

    assert "looks.py" in result.plan.command
    assert "-a 3" in result.plan.command
    assert "-r 5" in result.plan.command
    assert "output_mode = \"phase_color\"" in result.plan.command


def test_build_overlay_visualization_includes_imagemath(tmp_path: Path):
    intf = tmp_path / "pair.int"
    intf.write_text("x", encoding="utf-8")
    Path(f"{intf}.xml").write_text("<xml/>", encoding="utf-8")
    work_dir = tmp_path / "work"
    logs_dir = tmp_path / "logs"
    work_dir.mkdir()

    request = VisualizationRequest(
        mode="overlay",
        primary_input_path=str(intf),
        azimuth_looks=2,
        range_looks=4,
        overlay_brightness=0.6,
        work_dir=str(work_dir),
        output_bmp_path=str(tmp_path / "overlay.bmp"),
    )
    result = VisualizationService().build(request, logs_dir)

    assert "abs(a)*0.6;arg(a);abs(a)" in result.plan.command
    assert "int_2alks_4rlks.int" in result.plan.command
    assert "source_mode = \"amp_phase_mask_3band\"" in result.plan.command
    assert "output_mode = \"phase_color\"" in result.plan.command
    assert "--a=" in result.plan.command
    assert "--b=" not in result.plan.command
    assert "overlay.unw" in result.plan.command
    assert "python -c" in result.plan.command
    assert "crop_valid_extent = True" in result.plan.command


def test_overlay_visualization_migrates_legacy_slc_plus_int_request(tmp_path: Path):
    slc = tmp_path / "ref.slc"
    intf = tmp_path / "pair.int"
    for source in (slc, intf):
        source.write_text("x", encoding="utf-8")
        Path(f"{source}.xml").write_text("<xml/>", encoding="utf-8")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    request = VisualizationRequest(
        mode="overlay",
        primary_input_path=str(slc),
        secondary_input_path=str(intf),
        work_dir=str(work_dir),
        output_bmp_path=str(tmp_path / "overlay.bmp"),
    )
    result = VisualizationService().build(request, tmp_path / "logs")

    assert f"Overlay INT input: {intf}" in result.summary
    assert f"Overlay SLC input: {slc}" in result.summary
    assert "a*0.5;arg(b);abs(b)" in result.plan.command
    assert str(slc) in result.plan.command
    assert "--b=" in result.plan.command


def test_overlay_visualization_uses_int_first_and_optional_slc_second(tmp_path: Path):
    intf = tmp_path / "pair.int"
    slc = tmp_path / "reference.slc"
    for source in (intf, slc):
        source.write_text("x", encoding="utf-8")
        Path(f"{source}.xml").write_text("<xml/>", encoding="utf-8")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    request = VisualizationRequest(
        mode="overlay",
        primary_input_path=str(intf),
        secondary_input_path=str(slc),
        crop_valid_extent=False,
        work_dir=str(work_dir),
        output_bmp_path=str(tmp_path / "overlay.bmp"),
    )
    result = VisualizationService().build(request, tmp_path / "logs")

    assert f"Overlay INT input: {intf}" in result.summary
    assert f"Overlay SLC input: {slc}" in result.summary
    assert "crop_valid_extent = False" in result.plan.command
    assert "Crop to INT valid-data extent: no" in result.summary


def test_build_slc_visualization_with_looks_uses_amplitude_looks(tmp_path: Path):
    source = tmp_path / "input.slc"
    source.write_text("x", encoding="utf-8")
    Path(f"{source}.xml").write_text("<xml/>", encoding="utf-8")
    work_dir = tmp_path / "work"
    logs_dir = tmp_path / "logs"
    work_dir.mkdir()

    request = VisualizationRequest(
        mode="slc",
        primary_input_path=str(source),
        azimuth_looks=2,
        range_looks=5,
        work_dir=str(work_dir),
        output_bmp_path=str(tmp_path / "preview.bmp"),
    )
    result = VisualizationService().build(request, logs_dir)

    assert "looks.py" in result.plan.command
    assert "primary_amp_2alks_5rlks.float" in result.plan.command
    assert "source_mode = \"amplitude_real\"" in result.plan.command


def test_build_from_vrt_adds_conversion_commands(tmp_path: Path):
    source = tmp_path / "fine.int.full.vrt"
    source.write_text("<vrt/>", encoding="utf-8")
    work_dir = tmp_path / "work"
    logs_dir = tmp_path / "logs"
    work_dir.mkdir()

    request = VisualizationRequest(
        mode="interferogram",
        primary_input_path=str(source),
        work_dir=str(work_dir),
        output_bmp_path=str(tmp_path / "from_vrt.bmp"),
    )
    result = VisualizationService().build(request, logs_dir)

    assert "gdal_translate -of ENVI" in result.plan.command
    assert "gdal2isce_xml.py -i" in result.plan.command


def test_build_rejects_unparseable_input(tmp_path: Path):
    source = tmp_path / "bad.bin"
    source.write_text("x", encoding="utf-8")
    work_dir = tmp_path / "work"
    logs_dir = tmp_path / "logs"
    work_dir.mkdir()

    request = VisualizationRequest(
        mode="slc",
        primary_input_path=str(source),
        work_dir=str(work_dir),
        output_bmp_path=str(tmp_path / "bad.bmp"),
    )

    try:
        VisualizationService().build(request, logs_dir)
    except ValueError as exc:
        assert "not parseable" in str(exc)
    else:
        raise AssertionError("Expected unparseable visualization input to be rejected.")


def test_build_signature_changes_when_input_timestamp_changes(tmp_path: Path):
    source = tmp_path / "input.slc"
    source.write_text("x", encoding="utf-8")
    Path(f"{source}.xml").write_text("<xml/>", encoding="utf-8")

    request = VisualizationRequest(
        mode="slc",
        primary_input_path=str(source),
        work_dir=str(tmp_path),
        output_bmp_path=str(tmp_path / "preview.bmp"),
    )
    service = VisualizationService()
    sig1 = service.build_signature(request)
    source.write_text("xy", encoding="utf-8")
    sig2 = service.build_signature(request)

    assert sig1 != sig2


def test_new_product_request_writes_png_and_metadata(tmp_path: Path):
    source = tmp_path / "input.slc"
    source.write_text("x", encoding="utf-8")
    Path(f"{source}.xml").write_text("<xml/>", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    request = VisualizationRequest(
        product_kind="slc",
        product_id="slc:20240101",
        product_label="SLC · 2024-01-01",
        primary_input_path=str(source),
        work_dir=str(work),
        output_path=str(tmp_path / "preview.png"),
        metadata_path=str(tmp_path / "preview.json"),
    )

    result = VisualizationService().build(request, tmp_path / "logs")

    assert result.output_path.endswith(".png")
    assert result.metadata_path.endswith(".json")
    assert "gdal_translate -of PNG" in result.plan.command
    assert '"product_id": "slc:20240101"' not in result.plan.command
    assert "slc:20240101" in result.plan.command


def test_build_coherence_uses_fixed_viridis_range(tmp_path: Path):
    source = tmp_path / "filt_fine.cor"
    source.write_text("x", encoding="utf-8")
    Path(f"{source}.xml").write_text("<xml/>", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    request = VisualizationRequest(
        product_kind="coherence",
        primary_input_path=str(source),
        range_looks=5,
        azimuth_looks=2,
        work_dir=str(work),
        output_path=str(tmp_path / "coherence.png"),
    )

    result = VisualizationService().build(request, tmp_path / "logs")

    assert "coherence_2alks_5rlks.cor" in result.plan.command
    assert 'scalar_mode = "coherence"' in result.plan.command
    assert "lo, hi = 0.0, 1.0" in result.plan.command
    assert "Color range: fixed 0-1" in result.summary


def test_build_unwrapped_uses_phase_band_and_manual_range(tmp_path: Path):
    source = tmp_path / "filt_fine.unw"
    source.write_text("x", encoding="utf-8")
    Path(f"{source}.xml").write_text("<xml/>", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    request = VisualizationRequest(
        product_kind="unwrapped_phase",
        primary_input_path=str(source),
        range_mode="manual",
        range_min=-3.5,
        range_max=8.25,
        work_dir=str(work),
        output_path=str(tmp_path / "unwrapped.bmp"),
    )

    result = VisualizationService().build(request, tmp_path / "logs")

    assert "phase_band = 2 if ds.RasterCount >= 2 else 1" in result.plan.command
    assert "manual_min = -3.5" in result.plan.command
    assert "manual_max = 8.25" in result.plan.command
    assert "gdal_translate -of BMP" in result.plan.command


def test_build_rejects_invalid_manual_scalar_range(tmp_path: Path):
    source = tmp_path / "filt_fine.unw"
    source.write_text("x", encoding="utf-8")
    Path(f"{source}.xml").write_text("<xml/>", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    request = VisualizationRequest(
        product_kind="unwrapped_phase",
        primary_input_path=str(source),
        range_mode="manual",
        range_min=4.0,
        range_max=4.0,
        work_dir=str(work),
        output_path=str(tmp_path / "unwrapped.png"),
    )

    try:
        VisualizationService().build(request, tmp_path / "logs")
    except ValueError as exc:
        assert "maximum > minimum" in str(exc)
    else:
        raise AssertionError("Expected invalid manual range to be rejected.")


def test_build_custom_geometry_scalar_uses_first_band(tmp_path: Path):
    source = tmp_path / "hgt.rdr.full.vrt"
    source.write_text('<VRTDataset rasterXSize="12" rasterYSize="8"/>', encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    request = VisualizationRequest(
        product_kind="custom_raster",
        primary_input_path=str(source),
        work_dir=str(work),
        output_path=str(tmp_path / "height.png"),
    )

    result = VisualizationService().build(request, tmp_path / "logs")

    assert 'scalar_mode = "custom_scalar"' in result.plan.command
    assert "GetRasterBand(1)" in result.plan.command
    assert "Custom scalar range: P2-P98" in result.summary
