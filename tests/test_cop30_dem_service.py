from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from insar_pilot.download.cop30_service import Cop30AwsDemService, DemDownloadService
from insar_pilot.download.dem_service import create_dem_task
from insar_pilot.download.models import DemCoveragePlan, DownloadResult


class _RangeResponse:
    def __init__(self, payload: bytes, start: int, end: int, total: int) -> None:
        self.payload = payload[start : end + 1]
        self.status_code = 206
        self.headers = {
            "Content-Range": f"bytes {start}-{end}/{total}",
            "ETag": '"fixture-v1"',
            "Content-Length": str(total),
        }

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        yield self.payload[:chunk_size]
        yield self.payload[chunk_size:]

    def close(self) -> None:
        return None


class _RangeSession:
    def __init__(self, payload: bytes, calls: list[str], lock: threading.Lock) -> None:
        self.payload = payload
        self.calls = calls
        self.lock = lock

    def head(self, url, **kwargs):
        return _RangeResponse(self.payload, 0, 0, len(self.payload))

    def get(self, url: str, *, headers: dict[str, str], stream: bool, timeout: tuple[float, float]):
        del url, stream, timeout
        value = headers["Range"].removeprefix("bytes=")
        start_text, end_text = value.split("-", maxsplit=1)
        start, end = int(start_text), int(end_text)
        with self.lock:
            self.calls.append(value)
        return _RangeResponse(self.payload, start, end, len(self.payload))

    def close(self) -> None:
        return None


class _RangeNetwork:
    timeout_seconds = 5.0

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls: list[str] = []
        self.lock = threading.Lock()

    def session(self) -> _RangeSession:
        return _RangeSession(self.payload, self.calls, self.lock)


def _plan(source_id: str = "COP30") -> DemCoveragePlan:
    return DemCoveragePlan(
        source_id=source_id,
        selected_scene_ids=["S1_TEST"],
        planned_bbox_snwe=(34.1, 34.2, 108.1, 108.2),
        planning_mode="burst_union",
        dem_height_reference="egm2008",
    )


def test_cop30_tile_urls_cover_integer_boundaries_and_negative_coordinates():
    tiles = Cop30AwsDemService.tiles_for_bbox((-1.2, 0.0, -2.1, -0.1))

    assert [tile.tile_id for tile in tiles] == [
        "Copernicus_DSM_COG_10_S02_00_W003_00_DEM",
        "Copernicus_DSM_COG_10_S02_00_W002_00_DEM",
        "Copernicus_DSM_COG_10_S02_00_W001_00_DEM",
        "Copernicus_DSM_COG_10_S01_00_W003_00_DEM",
        "Copernicus_DSM_COG_10_S01_00_W002_00_DEM",
        "Copernicus_DSM_COG_10_S01_00_W001_00_DEM",
    ]
    assert tiles[0].url.endswith(f"/{tiles[0].tile_id}/{tiles[0].tile_id}.tif")


def test_cop30_rejects_accidental_world_scale_requests():
    try:
        Cop30AwsDemService.tiles_for_bbox((-10.0, 10.0, 100.0, 120.0))
    except ValueError as exc:
        assert "maximum per task" in str(exc)
    else:
        raise AssertionError("world-scale request should have been rejected")


def test_cop30_range_download_resumes_parts_and_assembles_in_order(tmp_path: Path):
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff",
            width=8,
            height=8,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(108, 35, 1 / 3600, 1 / 3600),
        ) as dataset:
            dataset.write(np.ones((1, 8, 8), dtype="float32"))
        payload = memory.read()
    network = _RangeNetwork(payload)
    service = Cop30AwsDemService(workers=4)
    tile = service.tiles_for_bbox((34.1, 34.2, 108.1, 108.2))[0]
    tile_path = tmp_path / f"{tile.tile_id}.tif"
    Path(f"{tile_path}.part.000").write_bytes(payload[:2])
    Path(f"{tile_path}.identity.json").write_text(
        json.dumps({"bytes": len(payload), "etag": '"fixture-v1"', "workers": 4, "tile_id": tile.tile_id})
    )

    service._download_tile(
        tile,
        tile_path,
        len(payload),
        network,  # type: ignore[arg-type]
        base_bytes=0,
        task=create_dem_task(tmp_path, "COP30"),
        started=time.monotonic(),
        progress_callback=None,
        cancel_check=None,
    )

    assert tile_path.read_bytes() == payload
    size = math.ceil(len(payload) / 4)
    assert set(network.calls) == {
        f"{2 if start == 0 else start}-{min(start + size - 1, len(payload) - 1)}"
        for start in range(0, len(payload), size)
    }
    assert not list(tmp_path.glob("*.part.*"))


def test_cop30_download_caches_tile_and_crops_bbox(tmp_path: Path, monkeypatch):
    service = Cop30AwsDemService(workers=2)
    task = create_dem_task(tmp_path, "COP30")
    plan = _plan()
    downloaded: list[Path] = []
    cropped: list[tuple[list[Path], tuple[float, float, float, float]]] = []

    monkeypatch.setattr(service, "_remote_size", lambda url, network: 8)

    def fake_download(tile, tile_path, tile_size, network, **kwargs):
        del tile, tile_size, network, kwargs
        tile_path.write_bytes(b"II*\x00tile")
        downloaded.append(tile_path)

    def fake_crop(tile_paths, output_path, bbox):
        output_path.write_bytes(b"II*\x00subset")
        cropped.append((tile_paths, bbox))

    monkeypatch.setattr(service, "_download_tile", fake_download)
    monkeypatch.setattr(service, "_crop_tiles", fake_crop)
    monkeypatch.setattr(
        "insar_pilot.download.cop30_service.OpenTopographyDemService._geotiff_validation_error",
        lambda path: "",
    )

    result = service.download(task, plan)

    assert result.status == "completed"
    assert result.backend == "cop30-aws"
    assert Path(result.local_path).read_bytes() == b"II*\x00subset"
    assert downloaded[0].parent == tmp_path / "DEM" / "cache" / "cop30"
    assert cropped == [(downloaded, plan.planned_bbox_snwe)]


class _RecordingDownloader:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[str] = []

    def download(self, task, plan, **kwargs) -> DownloadResult:
        del kwargs
        self.calls.append(plan.source_id)
        return DownloadResult(
            task_id=task.task_id,
            scene=task.scene,
            product_type=task.product_type,
            status="completed",
            local_path=self.name,
        )


def test_dem_download_service_routes_cop30_without_opentopography_key(tmp_path: Path):
    cop30 = _RecordingDownloader("aws")
    opentopography = _RecordingDownloader("ot")
    router = DemDownloadService(cop30=cop30, opentopography=opentopography)

    cop_result = router.download(create_dem_task(tmp_path, "COP30"), _plan(), api_key="")
    aw_result = router.download(create_dem_task(tmp_path, "AW3D30_E"), _plan("AW3D30_E"), api_key="key")

    assert cop_result.local_path == "aws"
    assert aw_result.local_path == "ot"
    assert cop30.calls == ["COP30"]
    assert opentopography.calls == ["AW3D30_E"]

    unsupported = router.download(
        create_dem_task(tmp_path, "UNKNOWN"),
        _plan("UNKNOWN"),
    )
    assert unsupported.status == "failed"
    assert "unsupported DEM source" in unsupported.message
