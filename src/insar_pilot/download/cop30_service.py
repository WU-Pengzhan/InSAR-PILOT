"""Credential-free Copernicus GLO-30 tile download and AOI subsetting."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import requests

from insar_pilot.download.dem_service import (
    CancelCheck,
    OpenTopographyDemService,
    ProgressCallback,
)
from insar_pilot.download.integrity import quarantine, receipt_path
from insar_pilot.download.models import DemCoveragePlan, DownloadResult, DownloadTask
from insar_pilot.download.network import NetworkConfig
from insar_pilot.infrastructure.engine_store import atomic_json


class DemDownloader(Protocol):
    """Common service boundary used by the download worker."""

    def download(
        self,
        task: DownloadTask,
        plan: DemCoveragePlan,
        *,
        api_key: str,
        network: NetworkConfig | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> DownloadResult:
        """Download one planned DEM."""


class _DownloadCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class Cop30Tile:
    """One one-degree Copernicus GLO-30 COG tile."""

    latitude: int
    longitude: int
    tile_id: str
    url: str


class Cop30AwsDemService:
    """Download COP30 COG tiles from AWS Open Data and crop them with GDAL."""

    BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com"
    DEFAULT_WORKERS = 8
    MAX_TILES = 64
    READ_TIMEOUT_SECONDS = 180.0

    def __init__(self, *, workers: int = DEFAULT_WORKERS) -> None:
        if workers < 1 or workers > 16:
            raise ValueError("COP30 range worker count must be between 1 and 16.")
        self.workers = workers
        self._identities: dict[str, dict[str, object]] = {}
        self._cancel_check: CancelCheck | None = None

    def download(
        self,
        task: DownloadTask,
        plan: DemCoveragePlan,
        *,
        api_key: str = "",
        network: NetworkConfig | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> DownloadResult:
        """Download cached source tiles and create the requested COP30 GeoTIFF."""

        del api_key
        self._cancel_check = cancel_check
        if plan.source_id.strip().upper() != "COP30":
            return self._failed_result(
                task,
                Path(task.local_path or task.output_dir),
                "the AWS tile provider supports COP30 only",
                progress_callback,
            )
        if plan.planned_bbox_snwe is None:
            return self._failed_result(
                task,
                Path(task.local_path or task.output_dir),
                "DEM coverage plan is missing a valid bbox",
                progress_callback,
            )

        network = network or NetworkConfig()
        dem_dir = Path(task.output_dir).expanduser() / "DEM"
        cache_dir = dem_dir / "cache" / "cop30"
        dem_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        final_path = OpenTopographyDemService._dem_path(dem_dir, plan)
        part_path = final_path.with_suffix(final_path.suffix + ".part")

        existing = self._existing_result(task, final_path, progress_callback)
        if existing is not None:
            if plan.planning_mode == "full_scene_union":
                try:
                    self._validate_coverage(final_path, plan.planned_bbox_snwe)
                except (ValueError, OSError):
                    quarantine(final_path)
                else:
                    return existing
            else:
                return existing

        tiles = self.tiles_for_bbox(plan.planned_bbox_snwe)
        if not tiles:
            return self._failed_result(task, part_path, "no COP30 tiles intersect the planned bbox", progress_callback)

        started = time.monotonic()
        completed_bytes = 0
        tile_paths: list[Path] = []
        try:
            for index, tile in enumerate(tiles, start=1):
                if cancel_check and cancel_check():
                    raise _DownloadCancelled
                tile_path = cache_dir / f"{tile.tile_id}.tif"
                cached_size = tile_path.stat().st_size if tile_path.exists() else 0
                if cached_size and not OpenTopographyDemService._geotiff_validation_error(tile_path):
                    completed_bytes += cached_size
                    tile_paths.append(tile_path)
                    self._emit_running(
                        task,
                        progress_callback,
                        local_path=tile_path,
                        bytes_done=completed_bytes,
                        started=started,
                        message=f"Using cached COP30 tile {index}/{len(tiles)}: {tile.tile_id}.",
                    )
                    continue
                if tile_path.exists():
                    OpenTopographyDemService._quarantine_corrupt_file(tile_path)
                tile_size = self._remote_size(tile.url, network)
                self._emit_running(
                    task,
                    progress_callback,
                    local_path=tile_path,
                    bytes_done=completed_bytes,
                    started=started,
                    message=(
                        f"Downloading COP30 tile {index}/{len(tiles)} with "
                        f"{self.workers} parallel ranges: {tile.tile_id}."
                    ),
                )
                self._download_tile(
                    tile,
                    tile_path,
                    tile_size,
                    network,
                    base_bytes=completed_bytes,
                    task=task,
                    started=started,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                )
                validation_error = OpenTopographyDemService._geotiff_validation_error(tile_path)
                if validation_error:
                    raise RuntimeError(f"downloaded tile {tile.tile_id} failed validation: {validation_error}")
                completed_bytes += tile_size
                tile_paths.append(tile_path)

            if cancel_check and cancel_check():
                raise _DownloadCancelled
            self._emit_running(
                task,
                progress_callback,
                local_path=part_path,
                bytes_done=completed_bytes,
                started=started,
                message=f"Cropping and mosaicking {len(tile_paths)} COP30 tile(s) with GDAL...",
            )
            self._crop_tiles(tile_paths, part_path, plan.planned_bbox_snwe)
            validation_error = OpenTopographyDemService._geotiff_validation_error(part_path)
            if validation_error:
                raise RuntimeError(f"cropped COP30 GeoTIFF failed validation: {validation_error}")
            if cancel_check and cancel_check():
                raise _DownloadCancelled
            if plan.planning_mode == "full_scene_union":
                self._validate_coverage(part_path, plan.planned_bbox_snwe)
            part_path.replace(final_path)
            receipt = receipt_path(part_path)
            if receipt.exists():
                receipt.replace(receipt_path(final_path))
        except _DownloadCancelled:
            cancelled = task.with_updates(
                status="cancelled",
                local_path=str(part_path),
                bytes_done=completed_bytes,
                speed_bps=OpenTopographyDemService._speed_bps(completed_bytes, started),
                backend="cop30-aws",
                message="COP30 download cancelled; completed cache tiles and range parts were kept for retry.",
            )
            if progress_callback:
                progress_callback(cancelled)
            return OpenTopographyDemService._result_from_task(cancelled)
        except Exception as exc:
            return self._failed_result(task, part_path, str(exc), progress_callback)

        size = final_path.stat().st_size
        completed = task.with_updates(
            status="completed",
            local_path=str(final_path),
            bytes_total=size,
            bytes_done=size,
            speed_bps=0.0,
            eta_seconds=0.0,
            backend="cop30-aws",
            message=(
                f"COP30 DEM completed from {len(tile_paths)} AWS Open Data tile(s); source tiles cached in {cache_dir}."
            ),
        )
        if progress_callback:
            progress_callback(completed)
        return OpenTopographyDemService._result_from_task(completed)

    @classmethod
    def tiles_for_bbox(cls, bbox: tuple[float, float, float, float]) -> list[Cop30Tile]:
        """Return deterministic one-degree tiles intersecting an SNWE bbox."""

        south, north, west, east = bbox
        if not (-90.0 <= south < north <= 90.0):
            raise ValueError(f"invalid COP30 latitude bounds: south={south:g}, north={north:g}")
        if not (-180.0 <= west < east <= 180.0):
            raise ValueError("invalid COP30 longitude bounds or antimeridian crossing; split antimeridian AOIs first")
        latitudes = range(math.floor(south), math.ceil(north))
        longitudes = range(math.floor(west), math.ceil(east))
        tiles = [cls._tile(latitude, longitude) for latitude in latitudes for longitude in longitudes]
        if len(tiles) > cls.MAX_TILES:
            raise ValueError(f"planned COP30 extent needs {len(tiles)} tiles; maximum per task is {cls.MAX_TILES}")
        return tiles

    @classmethod
    def _tile(cls, latitude: int, longitude: int) -> Cop30Tile:
        lat = f"N{latitude:02d}_00" if latitude >= 0 else f"S{abs(latitude):02d}_00"
        lon = f"E{longitude:03d}_00" if longitude >= 0 else f"W{abs(longitude):03d}_00"
        tile_id = f"Copernicus_DSM_COG_10_{lat}_{lon}_DEM"
        return Cop30Tile(
            latitude=latitude,
            longitude=longitude,
            tile_id=tile_id,
            url=f"{cls.BASE_URL}/{tile_id}/{tile_id}.tif",
        )

    def _remote_size(self, url: str, network: NetworkConfig) -> int:
        session = network.session()
        response: requests.Response | None = None
        try:
            response = session.head(url, timeout=(max(network.timeout_seconds, 1.0), self.READ_TIMEOUT_SECONDS))
            response.raise_for_status()
            size = int(response.headers.get("Content-Length", 0) or 0)
            self._identities[url] = {"bytes": size, "etag": response.headers.get("ETag", "")}
        finally:
            if response is not None:
                response.close()
            session.close()
        if size <= 0:
            raise RuntimeError("COP30 tile server did not provide a valid Content-Length")
        return size

    def _download_tile(
        self,
        tile: Cop30Tile,
        tile_path: Path,
        tile_size: int,
        network: NetworkConfig,
        *,
        base_bytes: int,
        task: DownloadTask,
        started: float,
        progress_callback: ProgressCallback | None,
        cancel_check: CancelCheck | None,
    ) -> None:
        if tile.url not in self._identities:
            self._remote_size(tile.url, network)
        identity = {**self._identities.get(tile.url, {}), "workers": self.workers, "tile_id": tile.tile_id}
        etag = str(identity.get("etag", ""))
        marker = Path(str(tile_path) + ".identity.json")
        previous = json.loads(marker.read_text()) if marker.exists() else None
        reliable = bool(etag and not etag.startswith("W/"))
        if not reliable or previous != identity:
            for old in tile_path.parent.glob(tile_path.name + ".part.*"):
                if ".invalid-" not in old.name:
                    quarantine(old)
        atomic_json(marker, identity)
        chunk_size = math.ceil(tile_size / self.workers)
        ranges = [
            (index, start, min(start + chunk_size - 1, tile_size - 1))
            for index, start in enumerate(range(0, tile_size, chunk_size))
        ]
        for index, start, end in ranges:
            part_path = Path(f"{tile_path}.part.{index:03d}")
            if part_path.exists() and part_path.stat().st_size > end - start + 1:
                part_path.unlink()
        state_lock = threading.Lock()
        stop_event = threading.Event()
        state: dict[str, float] = {
            "bytes": sum(
                min(
                    (
                        Path(f"{tile_path}.part.{index:03d}").stat().st_size
                        if Path(f"{tile_path}.part.{index:03d}").exists()
                        else 0
                    ),
                    end - start + 1,
                )
                for index, start, end in ranges
            ),
            "last_emit": 0.0,
        }

        def fetch(item: tuple[int, int, int]) -> None:
            index, start, end = item
            part_path = Path(f"{tile_path}.part.{index:03d}")
            expected = end - start + 1
            existing = part_path.stat().st_size if part_path.exists() else 0
            if existing > expected:
                part_path.unlink()
                existing = 0
            if existing == expected:
                return
            request_start = start + existing
            last_error: Exception | None = None
            for attempt in range(3):
                if stop_event.is_set() or (cancel_check and cancel_check()):
                    raise _DownloadCancelled
                session = network.session()
                response: requests.Response | None = None
                try:
                    response = session.get(
                        tile.url,
                        headers={"Range": f"bytes={request_start}-{end}", **({"If-Match": etag} if reliable else {})},
                        stream=True,
                        timeout=(max(network.timeout_seconds, 1.0), self.READ_TIMEOUT_SECONDS),
                    )
                    response.raise_for_status()
                    if response.status_code != 206:
                        raise RuntimeError(f"COP30 tile server ignored byte range (HTTP {response.status_code})")
                    content_range = response.headers.get("Content-Range", "")
                    if content_range != f"bytes {request_start}-{end}/{tile_size}" or (
                        reliable and response.headers.get("ETag") != etag
                    ):
                        raise RuntimeError(f"unexpected COP30 Content-Range: {content_range or 'missing'}")
                    with part_path.open("ab") as handle:
                        for block in response.iter_content(256 * 1024):
                            if stop_event.is_set() or (cancel_check and cancel_check()):
                                raise _DownloadCancelled
                            if not block:
                                continue
                            if handle.tell() + len(block) > expected:
                                raise RuntimeError("COP30 server sent bytes beyond the requested range.")
                            handle.write(block)
                            with state_lock:
                                state["bytes"] += len(block)
                                now = time.monotonic()
                                if progress_callback and now - state["last_emit"] >= 0.5:
                                    self._emit_running(
                                        task,
                                        progress_callback,
                                        local_path=part_path,
                                        bytes_done=base_bytes + int(state["bytes"]),
                                        started=started,
                                        message=f"Downloading COP30 tile ranges: {tile.tile_id}.",
                                    )
                                    state["last_emit"] = now
                    if part_path.stat().st_size != expected:
                        raise RuntimeError(
                            f"COP30 range {index} is incomplete: {part_path.stat().st_size}/{expected} bytes"
                        )
                    return
                except _DownloadCancelled:
                    raise
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(2.0 * (attempt + 1))
                        existing = part_path.stat().st_size if part_path.exists() else 0
                        request_start = start + existing
                finally:
                    if response is not None:
                        response.close()
                    session.close()
            raise RuntimeError(f"COP30 range {index} failed after 3 attempts: {last_error}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = [pool.submit(fetch, item) for item in ranges]
            try:
                for future in concurrent.futures.as_completed(futures):
                    future.result()
            except Exception:
                stop_event.set()
                for future in futures:
                    future.cancel()
                raise

        assembled = tile_path.with_suffix(tile_path.suffix + ".part")
        with assembled.open("wb") as destination:
            for index, _start, _end in ranges:
                part_path = Path(f"{tile_path}.part.{index:03d}")
                with part_path.open("rb") as source:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
        if assembled.stat().st_size != tile_size:
            raise RuntimeError(f"assembled COP30 tile is incomplete: {assembled.stat().st_size}/{tile_size} bytes")
        error = OpenTopographyDemService._geotiff_validation_error(assembled)
        if error:
            quarantine(assembled)
            raise ValueError("Assembled COP30 tile is not a readable GeoTIFF: " + error)
        assembled.replace(tile_path)
        for index, _start, _end in ranges:
            Path(f"{tile_path}.part.{index:03d}").unlink(missing_ok=True)

    def _crop_tiles(
        self,
        tile_paths: list[Path],
        output_path: Path,
        bbox: tuple[float, float, float, float],
    ) -> None:
        gdalwarp = shutil.which("gdalwarp")
        if not gdalwarp:
            raise RuntimeError("gdalwarp is required to crop COP30 tiles but was not found on PATH")
        south, north, west, east = bbox
        output_path.unlink(missing_ok=True)
        command = [
            gdalwarp,
            "-overwrite",
            "-of",
            "GTiff",
            "-t_srs",
            "EPSG:4326",
            "-tr",
            str(1 / 3600),
            str(1 / 3600),
            "-tap",
            "-te_srs",
            "EPSG:4326",
            "-te",
            f"{west:.9f}",
            f"{south:.9f}",
            f"{east:.9f}",
            f"{north:.9f}",
            "-r",
            "bilinear",
            "-co",
            "TILED=YES",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "BIGTIFF=IF_SAFER",
            *[str(path) for path in tile_paths],
            str(output_path),
        ]
        with __import__("tempfile").TemporaryFile(mode="w+") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 900
            try:
                while process.poll() is None:
                    if self._cancel_check and self._cancel_check():
                        raise _DownloadCancelled
                    if time.monotonic() > deadline:
                        raise RuntimeError("GDAL mosaicking timed out.")
                    time.sleep(0.2)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            if process.returncode:
                raise RuntimeError(f"GDAL mosaicking failed (exit {process.returncode}).")
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise RuntimeError("gdalwarp completed without producing a COP30 GeoTIFF")

    def _validate_coverage(self, path: Path, bbox: tuple[float, float, float, float]) -> None:
        import numpy as np
        import rasterio

        south, north, west, east = bbox
        with rasterio.open(path) as raster:
            if raster.crs != rasterio.crs.CRS.from_epsg(4326):
                raise ValueError("DEM must be in EPSG:4326.")
            tolerance = max(abs(raster.res[0]), abs(raster.res[1])) * 0.51
            b = raster.bounds
            if (
                b.left > west + tolerance
                or b.bottom > south + tolerance
                or b.right < east - tolerance
                or b.top < north - tolerance
            ):
                raise ValueError("DEM raster does not cover the planned full-scene extent.")
            count = 0
            for _, window in raster.block_windows(1):
                if self._cancel_check and self._cancel_check():
                    raise _DownloadCancelled
                pixels = raster.read(1, window=window, masked=True)
                if np.any(np.ma.getmaskarray(pixels)) or not np.isfinite(pixels.data).all():
                    raise ValueError("DEM contains missing or non-finite pixels; coverage is incomplete.")
                count += pixels.size
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024**2), b""):
                if self._cancel_check and self._cancel_check():
                    raise _DownloadCancelled
                hasher.update(block)
        atomic_json(
            receipt_path(path),
            {
                "sha256": hasher.hexdigest(),
                "bytes": path.stat().st_size,
                "checks": ["raster_decode", "extent", "finite", "no_nodata"],
                "coverage_pixels": count,
                "height_reference": "egm2008",
                "height_conversion_applied": False,
            },
        )

    @staticmethod
    def _emit_running(
        task: DownloadTask,
        progress_callback: ProgressCallback | None,
        *,
        local_path: Path,
        bytes_done: int,
        started: float,
        message: str,
    ) -> None:
        if progress_callback:
            progress_callback(
                task.with_updates(
                    status="running",
                    local_path=str(local_path),
                    bytes_done=bytes_done,
                    speed_bps=OpenTopographyDemService._speed_bps(bytes_done, started),
                    backend="cop30-aws",
                    message=message,
                )
            )

    @staticmethod
    def _existing_result(
        task: DownloadTask,
        final_path: Path,
        progress_callback: ProgressCallback | None,
    ) -> DownloadResult | None:
        if not final_path.exists() or final_path.stat().st_size <= 0:
            return None
        validation_error = OpenTopographyDemService._geotiff_validation_error(final_path)
        if validation_error:
            OpenTopographyDemService._quarantine_corrupt_file(final_path)
            return None
        size = final_path.stat().st_size
        skipped = task.with_updates(
            status="skipped",
            local_path=str(final_path),
            bytes_total=size,
            bytes_done=size,
            backend="cop30-aws",
            message="COP30 DEM already exists and passed integrity validation; skipped.",
        )
        if progress_callback:
            progress_callback(skipped)
        return OpenTopographyDemService._result_from_task(skipped)

    @staticmethod
    def _failed_result(
        task: DownloadTask,
        local_path: Path,
        detail: str,
        progress_callback: ProgressCallback | None,
    ) -> DownloadResult:
        failed = task.with_updates(
            status="failed",
            local_path=str(local_path),
            backend="cop30-aws",
            message=f"COP30 DEM download failed: {detail}.",
        )
        if progress_callback:
            progress_callback(failed)
        return OpenTopographyDemService._result_from_task(failed)


class DemDownloadService:
    """Route each DEM product to a source-specific implementation."""

    def __init__(
        self,
        *,
        cop30: DemDownloader | None = None,
        opentopography: DemDownloader | None = None,
    ) -> None:
        self.cop30: DemDownloader = cop30 or Cop30AwsDemService()
        self.opentopography: DemDownloader = opentopography or OpenTopographyDemService()

    def download(
        self,
        task: DownloadTask,
        plan: DemCoveragePlan,
        *,
        api_key: str = "",
        network: NetworkConfig | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> DownloadResult:
        """Use AWS Open Data for COP30 and OpenTopography for AW3D30_E."""

        source_id = plan.source_id.strip().upper()
        if source_id == "COP30":
            service = self.cop30
        elif source_id == "AW3D30_E":
            service = self.opentopography
        else:
            return Cop30AwsDemService._failed_result(
                task,
                Path(task.local_path or task.output_dir),
                f"unsupported DEM source: {source_id or '<empty>'}",
                progress_callback,
            )
        return service.download(
            task,
            plan,
            api_key=api_key,
            network=network,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
