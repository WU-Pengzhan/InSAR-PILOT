"""P01 identity, integrity, complete geometry and acquisition contracts."""

from __future__ import annotations

import io
import json
import zipfile

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

from insar_pilot.application import acquisition, engine_download
from insar_pilot.application.acquisition_aoi import file_wkt
from insar_pilot.application.acquisition_dem import coverage, scene_bounds
from insar_pilot.download.cop30_service import Cop30AwsDemService
from insar_pilot.download.integrity import receipt_path, validate_source
from insar_pilot.download.models import SceneRecord
from insar_pilot.download.orbit_service import OrbitDownloadService
from insar_pilot.infrastructure.application_state import ApplicationState
from insar_pilot.infrastructure.engine_store import ConflictError

SCENE = "S1D_IW_SLC__1SDV_20260102T120000_20260102T120030_000001_000001_0001"


def product(letter="D", offset=0):
    return {
        "remote_product_id": SCENE.replace("S1D", "S1" + letter),
        "provider_id": "asf-sentinel-1",
        "mission": "SENTINEL-1",
        "platform": "SENTINEL-1" + letter,
        "polarizations": ["VV"],
        "acquisition_time": "2026-01-02T12:00:00Z",
        "size_bytes": None,
        "download_url": "https://example.invalid/source?token=fixture-only",
        "footprint": mapping(box(100 + offset, 30, 102 + offset, 32)),
    }


def save_product(app):
    p = product()
    app.save_search([{"page": {"items": [p]}}])
    return p


def safe_bytes(scene=SCENE, iw=(1, 2, 3)):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        root = scene + ".SAFE"
        archive.writestr(root + "/manifest.safe", "<XFDU/>")
        for i in iw:
            xml = "<product><geolocationGrid>"
            for lon, lat in [(100 + i / 2, 30), (101 + i / 2, 32)]:
                xml += (
                    f"<geolocationGridPoint><longitude>{lon}</longitude>"
                    f"<latitude>{lat}</latitude></geolocationGridPoint>"
                )
            xml += "</geolocationGrid></product>"
            archive.writestr(root + f"/annotation/s1d-iw{i}-slc-vv.xml", xml)
            archive.writestr(root + f"/measurement/s1d-iw{i}-slc-vv.tiff", b"II*\x00measurement-fixture")
    return buffer.getvalue()


def scene(letter="D"):
    return SceneRecord(
        SCENE.replace("S1D", "S1" + letter), "2026-01-02T12:00:00Z", "SENTINEL-1" + letter, "ASCENDING", 1, "VV", 0
    )


def eof_file(tmp_path, letter="D", xml_letter=None, orbit_type="POEORB", end="20260103T005942"):
    name = f"S1{letter}_OPER_AUX_{orbit_type}_OPOD_20260122T000000_V20260101T225942_{end}.EOF"
    xml = (
        f"<Earth_Explorer_File><Mission>Sentinel-1{xml_letter or letter}</Mission>"
        f"<File_Type>AUX_{orbit_type}</File_Type>"
    )
    xml += (
        "<Validity_Start>UTC=2026-01-01T22:59:42</Validity_Start><Validity_Stop>UTC=2026-01-03T00:59:42</Validity_Stop>"
    )
    for time in ["2026-01-01T22:59:42", "2026-01-03T00:59:42"]:
        xml += (
            f"<OSV><UTC>UTC={time}</UTC>"
            + "".join(f"<{k}>1.0</{k}>" for k in ["X", "Y", "Z", "VX", "VY", "VZ"])
            + "</OSV>"
        )
    path = tmp_path / name
    path.write_text(xml + "</Earth_Explorer_File>")
    return path


@pytest.mark.parametrize("letter", list("ABCD"))
def test_eof_preserves_abcd_and_validates_full_interval(tmp_path, letter):
    assert OrbitDownloadService._mission(scene(letter)) == "S1" + letter
    OrbitDownloadService.validate(eof_file(tmp_path, letter), scene(letter))


@pytest.mark.parametrize(
    "kwargs", [{"letter": "A"}, {"xml_letter": "A"}, {"orbit_type": "RESORB"}, {"end": "20260102T120015"}]
)
def test_eof_rejects_wrong_satellite_type_or_partial_time(tmp_path, kwargs):
    with pytest.raises(ValueError):
        OrbitDownloadService.validate(eof_file(tmp_path, **kwargs), scene())


def test_eof_missing_precise_has_no_fallback(tmp_path, monkeypatch):
    service = OrbitDownloadService()
    monkeypatch.setattr(service, "candidates", lambda *args: [])
    from insar_pilot.download.download_service import DownloadService

    task = DownloadService().create_tasks([scene()], tmp_path)[1]
    result = service.download(task)
    assert result.status == "unavailable"
    assert not list(tmp_path.rglob("*.EOF"))


def test_zip_checks_all_bytes_and_exact_safe_identity(tmp_path):
    path = tmp_path / (SCENE + ".zip")
    path.write_bytes(safe_bytes())
    assert "zip_crc_all_members" in validate_source(path, "SLC")["checks"]
    wrong = tmp_path / (SCENE.replace("S1D", "S1A") + ".zip")
    wrong.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="identity"):
        validate_source(wrong, "SLC")
    path.write_bytes(b"x")
    with pytest.raises(ValueError):
        validate_source(path, "SLC")


def test_dem_uses_all_iw_and_multiple_frames_with_margin(tmp_path):
    path = tmp_path / (SCENE + ".zip")
    path.write_bytes(safe_bytes())
    assert scene_bounds(path) == (100.5, 30.0, 102.5, 32.0)
    resolved = coverage([product()], 20000, {SCENE: str(path)})
    assert resolved["verified_geometry"] is True
    assert resolved["bounds"][0] < 100.5 and resolved["bounds"][2] > 102.5
    assert coverage([product(), product("C", 2)])["bounds"][2] > 104
    path.write_bytes(safe_bytes(iw=(1,)))
    with pytest.raises(ValueError, match="IW1/IW2/IW3"):
        coverage([product()], 20000, {SCENE: str(path)})


@pytest.mark.parametrize("bounds", [(179, 20, 180, 21), (-170, 20, 170, 21), (0, 88.9, 1, 89)])
def test_dem_rejects_unsuitable_extent(bounds):
    p = product()
    p["footprint"] = mapping(box(*bounds))
    with pytest.raises(ValueError):
        coverage([p])


def test_dem_coverage_checks_pixels_extent_and_height_reference(tmp_path):
    path = tmp_path / "dem.tif"

    def raster(nodata=False):
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=10,
            height=10,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(100, 31, 0.1, 0.1),
            nodata=-9999,
        ) as dst:
            a = np.ones((1, 10, 10), dtype="float32")
            if nodata:
                a[0, 0, 0] = -9999
            dst.write(a)

    raster()
    service = Cop30AwsDemService(workers=2)
    service._validate_coverage(path, (30, 31, 100, 101))
    receipt = json.loads(receipt_path(path).read_text())
    assert receipt["height_reference"] == "egm2008" and receipt["height_conversion_applied"] is False
    with pytest.raises(ValueError, match="extent"):
        service._validate_coverage(path, (29, 31, 100, 101))
    raster(True)
    with pytest.raises(ValueError, match="missing"):
        service._validate_coverage(path, (30, 31, 100, 101))


@pytest.mark.parametrize(
    "orbits,dem,roles",
    [
        (False, False, ["SLC"]),
        (True, False, ["SLC", "ORBIT"]),
        (False, True, ["SLC", "DEM"]),
        (True, True, ["SLC", "ORBIT", "DEM"]),
    ],
)
def test_preview_freezes_four_combinations_without_fetch_url(tmp_path, orbits, dem, roles):
    app = ApplicationState(tmp_path / "state")
    p = save_product(app)
    plan = acquisition.preview(app, {"product_ids": [p["product_key"]], "include_orbits": orbits, "include_dem": dem})
    assert [f["role"] for f in plan["files"]] == roles
    assert "fixture-only" not in json.dumps(plan)
    assert app.acquisition_plan(plan["plan_id"]) == json.loads(json.dumps(plan))


def test_idempotent_commit_save_only_and_project_revision(tmp_path):
    app = ApplicationState(tmp_path / "state")
    p = save_product(app)
    plan = acquisition.preview(
        app, {"product_ids": [p["product_key"]], "new_project": {"name": "P01", "path": str(tmp_path / "project")}}
    )
    body = {
        "plan_id": plan["plan_id"],
        "idempotency_key": "request-one",
        "start_download": False,
        "new_project": {"name": "P01", "path": str(tmp_path / "project")},
    }
    first = acquisition.commit(app, body)
    second = acquisition.commit(app, body)
    assert first == second and first["job"] is None
    assert len(app.recent()) == 1 and len(first["project"]["datasets"]) == 1
    pid = first["project"]["project_id"]
    add = acquisition.preview(app, {"product_ids": [p["product_key"]], "project_id": pid})
    store = app.project(pid)
    store.revise(store.project()["revision"], settings={"changed": True})
    with pytest.raises(ConflictError, match="revision"):
        acquisition.commit(
            app,
            {
                "plan_id": add["plan_id"],
                "idempotency_key": "request-two",
                "start_download": False,
                "project_id": pid,
                "expected_revision": add["expected_revision"],
            },
        )
    with pytest.raises(ConflictError, match="different"):
        acquisition.commit(app, {**body, "start_download": True}, testing=True)


def test_commit_deduplicates_active_attempt_and_recovers_queued_launch(tmp_path, monkeypatch):
    app = ApplicationState(tmp_path / "state")
    p = save_product(app)
    plan = acquisition.preview(app, {"product_ids": [p["product_key"]], "include_orbits": False})
    body = {"plan_id": plan["plan_id"], "idempotency_key": "request-one", "start_download": True}
    first = acquisition.commit(app, body, testing=True)
    again = acquisition.commit(app, {**body, "idempotency_key": "request-two"}, testing=True)
    assert first["job"]["job_id"] == again["job"]["job_id"] and len(app.downloads()) == 1
    launched = []
    monkeypatch.setattr(engine_download, "launch_worker", lambda app, job: launched.append(job["job_id"]))
    acquisition.commit(app, body)
    assert launched == [first["job"]["job_id"]]


def test_production_commit_checks_prerequisites_before_creating_project(tmp_path, monkeypatch):
    app = ApplicationState(tmp_path / "state")
    p = save_product(app)
    monkeypatch.setattr(
        acquisition,
        "readiness",
        lambda app: {
            "aria2_available": False,
            "credentials_configured": False,
            "gdal_available": False,
            "gdal_executable": None,
            "network": {},
        },
    )
    plan = acquisition.preview(
        app, {"product_ids": [p["product_key"]], "new_project": {"name": "P", "path": str(tmp_path / "project")}}
    )
    with pytest.raises(ValueError, match="Configure"):
        acquisition.commit(
            app,
            {
                "plan_id": plan["plan_id"],
                "idempotency_key": "request-block",
                "new_project": {"name": "P", "path": str(tmp_path / "project")},
                "start_download": True,
            },
        )
    assert not app.recent() and not app.downloads()


def test_kml_holes_preserved_and_multipart_rejected(tmp_path):
    path = tmp_path / "aoi.kml"
    outer = "0,0 3,0 3,3 0,3 0,0"
    hole = "1,1 1,2 2,2 2,1 1,1"
    polygon = (
        "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
        + outer
        + "</coordinates></LinearRing></outerBoundaryIs><innerBoundaryIs><LinearRing><coordinates>"
        + hole
        + "</coordinates></LinearRing></innerBoundaryIs></Polygon>"
    )
    path.write_text('<kml xmlns="http://www.opengis.net/kml/2.2">' + polygon + "</kml>")
    from shapely.wkt import loads

    assert len(loads(file_wkt(path)).interiors) == 1
    path.write_text('<kml xmlns="http://www.opengis.net/kml/2.2">' + polygon + polygon + "</kml>")
    with pytest.raises(ValueError, match="single"):
        file_wkt(path)
