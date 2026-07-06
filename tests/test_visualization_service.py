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
    slc = tmp_path / "ref.slc"
    intf = tmp_path / "pair.int"
    slc.write_text("x", encoding="utf-8")
    intf.write_text("x", encoding="utf-8")
    Path(f"{slc}.xml").write_text("<xml/>", encoding="utf-8")
    Path(f"{intf}.xml").write_text("<xml/>", encoding="utf-8")
    work_dir = tmp_path / "work"
    logs_dir = tmp_path / "logs"
    work_dir.mkdir()

    request = VisualizationRequest(
        mode="overlay",
        primary_input_path=str(slc),
        secondary_input_path=str(intf),
        azimuth_looks=2,
        range_looks=4,
        overlay_brightness=0.6,
        work_dir=str(work_dir),
        output_bmp_path=str(tmp_path / "overlay.bmp"),
    )
    result = VisualizationService().build(request, logs_dir)

    assert "abs(a)*0.6;arg(b)" in result.plan.command
    assert "slc_amp_2alks_4rlks.float" in result.plan.command
    assert "source_mode = \"amp_phase_2band\"" in result.plan.command
    assert "output_mode = \"phase_color\"" in result.plan.command
    assert "--a=" in result.plan.command
    assert "--b=" in result.plan.command
    assert "overlay.unw" in result.plan.command
    assert "python -c" in result.plan.command


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
