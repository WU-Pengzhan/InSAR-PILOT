from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from insar_pilot.backends.isce3 import (
    NisarInsarValidator,
    NisarIsce3RuntimeProbe,
    NisarRifgPlanBuilder,
    NisarRifgValidator,
)
from insar_pilot.domain.local_data import AssetRef, LocalSARProduct, SourceSnapshot, stable_product_id
from insar_pilot.domain.task_runtime import RuntimeProfile


def _product(native_id: str, day: int, *, track: int = 13) -> LocalSARProduct:
    start = datetime(2026, 1, day, tzinfo=timezone.utc)
    return LocalSARProduct(
        product_id=stable_product_id("NISAR", "RSLC", native_id),
        native_product_id=native_id,
        mission="NISAR",
        platform="NISAR",
        product_type="RSLC",
        acquisition_mode="SCIENCE",
        acquisition_layout="FREQUENCY_SWATHS",
        start_time=start,
        end_time=start + timedelta(minutes=1),
        orbit_direction="DESCENDING",
        orbit_identity=None,
        track=track,
        frame=71,
        relative_orbit=None,
        frequency_bands=("A", "B"),
        polarizations=("HH", "HV"),
        footprint_wkt="POLYGON ((-118 36 1000,-117 36 900,-117 35 800,-118 36 1000))",
        assets=(AssetRef(f"/readonly/{native_id}.h5", "source_product"),),
        native_metadata={"identification": {"lookDirection": "Left"}},
        reader_id="nisar.rslc",
        reader_schema_version=1,
        source_snapshot=SourceSnapshot("file", 100, day),
    )


def _template(path: Path) -> Path:
    value = {
        "runconfig": {
            "name": "test",
            "groups": {
                "input_file_group": {},
                "dynamic_ancillary_file_group": {},
                "primary_executable": {"product_type": "GUNW"},
                "product_path_group": {},
                "processing": {
                    "input_subset": {"list_of_frequencies": {"A": ["HH"]}},
                    "geocode": {"top_left": {}, "bottom_right": {}},
                    "dense_offsets": {"enabled": True},
                    "rubbersheet": {"enabled": True},
                },
                "logging": {"path": "/readonly/old.log"},
            },
        }
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _profile(python_executable: str = "/runtime/python") -> RuntimeProfile:
    return RuntimeProfile(
        "nisar-local",
        "isce3.nisar_rifg",
        {"python_executable": python_executable},
    )


def test_rifg_plan_rewrites_only_inputs_outputs_and_selection(tmp_path: Path) -> None:
    template = _template(tmp_path / "template.json")
    output = tmp_path / "new-run"

    plan = NisarRifgPlanBuilder().build(
        _product("REFERENCE", 1),
        _product("SECONDARY", 13),
        AssetRef("/readonly/dem.vrt", "prepared_dem"),
        output_dir=output,
        template_path=template,
        profile=_profile(),
        frequency="B",
        polarization="HV",
    )
    payload = json.loads(plan.runconfig_text)
    groups = payload["runconfig"]["groups"]

    assert groups["input_file_group"] == {
        "reference_rslc_file": "/readonly/REFERENCE.h5",
        "secondary_rslc_file": "/readonly/SECONDARY.h5",
    }
    assert groups["dynamic_ancillary_file_group"]["dem_file"] == "/readonly/dem.vrt"
    assert groups["primary_executable"]["product_type"] == "RIFG"
    assert groups["processing"]["input_subset"]["list_of_frequencies"] == {"B": ["HV"]}
    assert groups["processing"]["dense_offsets"]["enabled"] is True
    assert groups["logging"]["path"] == str(output / "logs/insar_workflow.log")
    assert plan.command == (
        "/runtime/python",
        "-m",
        "nisar.workflows.insar",
        str(output / "runconfig/nisar_rifg.json"),
    )
    assert plan.output_product.uri == str(output / "products/RIFG_product.h5")
    assert not output.exists()


def test_runconfig_write_is_atomic_and_requires_explicit_replace(tmp_path: Path) -> None:
    builder = NisarRifgPlanBuilder()
    plan = builder.build(
        _product("REFERENCE", 1),
        _product("SECONDARY", 2),
        AssetRef("/readonly/dem.vrt", "dem"),
        output_dir=tmp_path / "output",
        template_path=_template(tmp_path / "template.json"),
        profile=_profile(),
        frequency="A",
        polarization="HH",
    )

    path = builder.write_runconfig(plan)
    assert path.read_text(encoding="utf-8") == plan.runconfig_text
    with pytest.raises(FileExistsError):
        builder.write_runconfig(plan)
    builder.write_runconfig(plan, replace_existing=True)


def test_gunw_plan_sets_product_contract_and_geocode_bounds(tmp_path: Path) -> None:
    output = tmp_path / "gunw-run"
    plan = NisarRifgPlanBuilder().build(
        _product("REFERENCE", 1),
        _product("SECONDARY", 13),
        AssetRef("/readonly/dem.vrt", "prepared_dem"),
        output_dir=output,
        template_path=_template(tmp_path / "template.json"),
        profile=_profile(),
        frequency="A",
        polarization="HH",
        product_type="GUNW",
        geocode_bounds=(429520.0, 3835120.0, 438880.0, 3823920.0),
    )

    payload = json.loads(plan.runconfig_text)
    groups = payload["runconfig"]["groups"]
    assert groups["primary_executable"]["product_type"] == "GUNW"
    assert groups["processing"]["geocode"]["top_left"] == {
        "x_abs": 429520.0,
        "y_abs": 3835120.0,
    }
    assert groups["processing"]["geocode"]["bottom_right"] == {
        "x_abs": 438880.0,
        "y_abs": 3823920.0,
    }
    assert plan.product_type == "GUNW"
    assert plan.output_product.uri == str(output / "products/GUNW_product.h5")


@pytest.mark.parametrize(
    ("secondary", "frequency", "polarization", "message"),
    [
        (_product("WRONG_TRACK", 2, track=99), "A", "HH", "incompatible"),
        (_product("SECONDARY", 2), "C", "HH", "Frequency"),
        (_product("SECONDARY", 2), "A", "VV", "Polarization"),
    ],
)
def test_plan_rejects_incompatible_or_unavailable_pair_choices(
    tmp_path: Path,
    secondary: LocalSARProduct,
    frequency: str,
    polarization: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        NisarRifgPlanBuilder().build(
            _product("REFERENCE", 1),
            secondary,
            AssetRef("/readonly/dem.vrt", "dem"),
            output_dir=tmp_path / "output",
            template_path=_template(tmp_path / "template.json"),
            profile=_profile(),
            frequency=frequency,
            polarization=polarization,
        )


def _probe_executable(path: Path, output: str, *, exit_code: int = 0) -> Path:
    path.write_text(f"#!/bin/sh\nprintf %s '{output}'\nexit {exit_code}\n", encoding="utf-8")
    path.chmod(0o700)
    return path


def test_runtime_probe_checks_exact_workflow_and_gdal_drivers(tmp_path: Path) -> None:
    healthy_payload = json.dumps(
        {
            "isce3": "0.25.12",
            "nisar": "0.25.12",
            "gdal": "3.12.4",
            "drivers": {"HDF5": True, "HDF5Image": True},
            "epsg_ok": True,
        }
    )
    healthy = _probe_executable(tmp_path / "healthy", healthy_payload)
    report = NisarIsce3RuntimeProbe().probe(_profile(str(healthy)))
    assert report.available
    assert dict(report.versions)["isce3"] == "0.25.12"

    missing_driver_payload = json.dumps(
        {
            "isce3": "0.25.12",
            "nisar": "0.25.12",
            "gdal": "3.12.4",
            "drivers": {"HDF5": True, "HDF5Image": False},
            "epsg_ok": True,
        }
    )
    missing_driver = _probe_executable(tmp_path / "missing-driver", missing_driver_payload)
    unavailable = NisarIsce3RuntimeProbe().probe(_profile(str(missing_driver)))
    assert not unavailable.available
    assert unavailable.reason_codes == ("gdal_hdf5_driver_missing",)


def test_runtime_probe_explains_missing_environment_and_workflow_dependency(tmp_path: Path) -> None:
    probe = NisarIsce3RuntimeProbe()
    no_python = probe.probe(_profile(str(tmp_path / "missing-python")))
    assert no_python.reason_codes == ("python_executable_missing",)

    pyaps = _probe_executable(tmp_path / "pyaps-missing", "No module named 'pyaps3'", exit_code=1)
    missing_dependency = probe.probe(_profile(str(pyaps)))
    assert missing_dependency.reason_codes == ("pyaps3_missing",)


def test_rifg_validator_checks_product_type_datasets_and_shape(tmp_path: Path) -> None:
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "RIFG.h5"
    with h5py.File(path, "w") as container:
        identification = container.create_group("/science/LSAR/identification")
        identification.create_dataset("productType", data="RIFG")
        interferogram = container.create_group("/science/LSAR/RIFG/swaths/frequencyA/interferogram/HH")
        interferogram.create_dataset("wrappedInterferogram", shape=(12, 8), dtype="complex64")
        interferogram.create_dataset("coherenceMagnitude", shape=(12, 8), dtype="float32")

    report = NisarRifgValidator().validate(path, frequency="A", polarization="HH")

    assert report.valid
    assert report.shape == (12, 8)
    assert report.wrapped_dtype == "complex64"
    assert report.coherence_dtype == "float32"


def test_rifg_validator_rejects_missing_output(tmp_path: Path) -> None:
    report = NisarRifgValidator().validate(tmp_path / "missing.h5", frequency="A", polarization="HH")
    assert not report.valid
    assert report.reason_codes == ("output_missing",)


@pytest.mark.parametrize(
    ("product_type", "base", "phase_name"),
    [
        ("RUNW", "/science/LSAR/RUNW/swaths/frequencyA/interferogram/HH", "unwrappedPhase"),
        ("GUNW", "/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH", "unwrappedPhase"),
    ],
)
def test_insar_validator_checks_unwrapped_product_contracts(
    tmp_path: Path, product_type: str, base: str, phase_name: str
) -> None:
    h5py = pytest.importorskip("h5py")
    path = tmp_path / f"{product_type}.h5"
    with h5py.File(path, "w") as container:
        identification = container.create_group("/science/LSAR/identification")
        identification.create_dataset("productType", data=product_type)
        interferogram = container.create_group(base)
        interferogram.create_dataset(phase_name, shape=(9, 7), dtype="float32")
        interferogram.create_dataset("coherenceMagnitude", shape=(9, 7), dtype="float32")
        interferogram.create_dataset("connectedComponents", shape=(9, 7), dtype="uint16")

    report = NisarInsarValidator().validate(
        path, product_type=product_type, frequency="A", polarization="HH"
    )

    assert report.valid
    assert report.shape == (9, 7)
    assert report.phase_dtype == "float32"
