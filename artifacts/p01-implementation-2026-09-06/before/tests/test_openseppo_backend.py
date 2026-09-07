from __future__ import annotations

from pathlib import Path

from insar_pilot.backends.openseppo import (
    OpenSeppoSubsetPlanBuilder,
    OpenSeppoSubsetRunner,
    _network_environment,
)
from insar_pilot.download.network import NetworkConfig


def _kml(path: Path) -> Path:
    path.write_text(
        """<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><Polygon><outerBoundaryIs>
<LinearRing><coordinates>-117.8,34.5 -117.6,34.5 -117.6,34.7 -117.8,34.7 -117.8,34.5</coordinates></LinearRing>
</outerBoundaryIs></Polygon></Placemark></kml>""",
        encoding="utf-8",
    )
    return path


def test_subset_plan_uses_aoi_envelope_and_never_writes_inputs(tmp_path: Path) -> None:
    source = tmp_path / "source.h5"
    source.write_bytes(b"unchanged")
    executable = tmp_path / "seppo_nisar_rslc_convert"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")

    plan = OpenSeppoSubsetPlanBuilder().build(
        (source,),
        _kml(tmp_path / "aoi.kml"),
        tmp_path / "output",
        executable=executable,
        frequency="A",
        polarizations=("HH",),
        min_height=0,
        max_height=3000,
    )

    assert plan.command[0] == str(executable.resolve())
    assert plan.command[plan.command.index("-projwin") + 1 : plan.command.index("-projwin") + 5] == (
        "-117.8",
        "34.7",
        "-117.6",
        "34.5",
    )
    assert plan.command[-6:] == ("-vars", "HH", "--min_height", "0", "--max_height", "3000")
    assert source.read_bytes() == b"unchanged"
    assert not Path(plan.output_dir).exists()


def test_subset_runner_requires_one_output_per_input(tmp_path: Path) -> None:
    source = tmp_path / "source.h5"
    source.write_bytes(b"source")
    executable = tmp_path / "fake-seppo"
    executable.write_text("#!/bin/sh\ntouch \"$4/subset.h5\"\n", encoding="utf-8")
    executable.chmod(0o700)
    plan = OpenSeppoSubsetPlanBuilder().build(
        (source,),
        _kml(tmp_path / "aoi.kml"),
        tmp_path / "output",
        executable=executable,
    )

    report = OpenSeppoSubsetRunner().run(plan)

    assert report.succeeded
    assert len(report.outputs) == 1
    assert Path(report.log_path).is_file()


def test_subset_plan_preserves_remote_hdf5_url_and_disables_full_cache_by_default(tmp_path: Path) -> None:
    executable = tmp_path / "seppo_nisar_rslc_convert"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    remote = "https://example.earthdatacloud.nasa.gov/NISAR_L1_PR_RSLC_TEST.h5"

    plan = OpenSeppoSubsetPlanBuilder().build(
        (remote,),
        _kml(tmp_path / "aoi.kml"),
        tmp_path / "output",
        executable=executable,
    )

    assert plan.input_products == (remote,)
    assert remote in plan.command
    assert "-cache" not in plan.command


def test_subset_plan_requires_explicit_cache_before_keep(tmp_path: Path) -> None:
    source = tmp_path / "source.h5"
    source.write_bytes(b"source")
    executable = tmp_path / "seppo_nisar_rslc_convert"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")

    try:
        OpenSeppoSubsetPlanBuilder().build(
            (source,),
            _kml(tmp_path / "aoi.kml"),
            tmp_path / "output",
            executable=executable,
            keep_cached=True,
        )
    except ValueError as exc:
        assert "requires an explicit cache" in str(exc)
    else:
        raise AssertionError("keep_cached must not silently enable a complete granule download")


def test_subset_plan_can_record_automatic_terrain_details(tmp_path: Path) -> None:
    source = tmp_path / "source.h5"
    source.write_bytes(b"source")
    executable = tmp_path / "seppo_nisar_rslc_convert"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")

    plan = OpenSeppoSubsetPlanBuilder().build(
        (source,),
        _kml(tmp_path / "aoi.kml"),
        tmp_path / "output",
        executable=executable,
        verbose=True,
    )

    assert plan.command[-1] == "-v"


def test_openseppo_network_environment_defaults_to_direct(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:8080")
    monkeypatch.setenv("https_proxy", "http://proxy.invalid:8080")

    direct = _network_environment(NetworkConfig())
    inherited = _network_environment(NetworkConfig(mode="environment"))

    assert "HTTPS_PROXY" not in direct
    assert "https_proxy" not in direct
    assert inherited["HTTPS_PROXY"] == "http://proxy.invalid:8080"
