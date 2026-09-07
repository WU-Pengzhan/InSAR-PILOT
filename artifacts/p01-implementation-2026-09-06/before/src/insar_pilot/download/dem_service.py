"""Standalone DEM planning and download services."""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import requests

from insar_pilot.download.geometry import aoi_geojson_from_inputs, bounds_from_geojson
from insar_pilot.download.models import DemCoveragePlan, DownloadResult, DownloadTask, SceneRecord, SearchCriteria
from insar_pilot.download.network import NetworkConfig
from insar_pilot.services.iw_recommendation import IwRecommendationResult, IwRecommendationService

ProgressCallback = Callable[[DownloadTask], None]
CancelCheck = Callable[[], bool]

DEM_SOURCE_LABELS = {
    "COP30": "COP30 (Copernicus Global DSM 30m)",
    "AW3D30_E": "AW3D30_E (ALOS World 3D Ellipsoidal, 30m)",
}

DEM_SOURCE_HEIGHT_REFERENCES = {
    "COP30": "egm2008",
    "AW3D30_E": "wgs84",
}

def dem_height_reference_for_source(source_id: str) -> str:
    """Return the Data Sources DEM reference value for one DEM source."""

    return DEM_SOURCE_HEIGHT_REFERENCES.get(source_id.strip().upper(), "egm2008")


def dem_label_for_source(source_id: str) -> str:
    """Return the user-facing DEM source label."""

    return DEM_SOURCE_LABELS.get(source_id.strip().upper(), source_id.strip().upper() or "DEM")


def create_dem_task(output_dir: str | Path, source_id: str) -> DownloadTask:
    """Create one placeholder DEM task for the standalone workspace."""

    normalized = source_id.strip().upper() or "COP30"
    scene = SceneRecord(
        scene_id=f"{normalized}_DEM",
        acquisition_time="",
        platform="Copernicus DEM" if normalized == "COP30" else "OpenTopography",
        orbit_direction="",
        relative_orbit=0,
        polarization="",
        size_mb=0.0,
    )
    local_path = Path(output_dir).expanduser() / "DEM" / f"{normalized.lower()}_dem.tif"
    return DownloadTask(
        task_id="dem-001",
        scene=scene,
        output_dir=str(Path(output_dir).expanduser()),
        product_type="DEM",
        local_path=str(local_path),
        message=f"DEM source: {dem_label_for_source(normalized)}",
    )


class DemCoveragePlanner:
    """Plan a conservative DEM bbox from downloaded SLC burst geometry."""

    def __init__(self, iw_service: IwRecommendationService | None = None) -> None:
        self.iw_service = iw_service or IwRecommendationService()

    def plan(
        self,
        criteria: SearchCriteria,
        scenes: list[SceneRecord],
        source_id: str,
    ) -> DemCoveragePlan:
        """Plan DEM coverage from local SLC products with scene-footprint fallback."""

        bbox = self._aoi_bbox(criteria)
        bbox_text = self._snwe_text(bbox)
        warnings: list[str] = []
        notes = [
            f"DEM source: {dem_label_for_source(source_id)}",
            f"AOI bbox used for DEM planning (SNWE): {bbox_text}",
            f"Selected scenes for DEM planning: {len(scenes)}",
        ]
        burst_boxes: list[tuple[float, float, float, float]] = []
        fallback_boxes: list[tuple[float, float, float, float]] = []
        used_burst_union = False

        for scene in scenes:
            local_path = Path(scene.local_path).expanduser() if scene.local_path else None
            if local_path is None or not local_path.exists():
                fallback = self._scene_bbox(scene)
                if fallback is not None:
                    fallback_boxes.append(fallback)
                    warnings.append(
                        f"{scene.scene_id}: local SLC path is unavailable; used scene footprint bbox for DEM planning."
                    )
                else:
                    warnings.append(
                        f"{scene.scene_id}: local SLC path is unavailable and no scene footprint bbox exists."
                    )
                continue
            try:
                result = self.iw_service.recommend(str(local_path), bbox_text)
            except Exception as exc:
                fallback = self._scene_bbox(scene)
                if fallback is not None:
                    fallback_boxes.append(fallback)
                    warnings.append(
                        f"{scene.scene_id}: burst parsing failed ({exc}); used scene footprint bbox for DEM planning."
                    )
                else:
                    warnings.append(f"{scene.scene_id}: burst parsing failed and no fallback footprint exists ({exc}).")
                continue

            scene_boxes = self._expanded_burst_boxes(result)
            if scene_boxes:
                burst_boxes.extend(scene_boxes)
                used_burst_union = True
                notes.append(f"{scene.scene_id}: burst-aware DEM planning used {len(scene_boxes)} burst boxes.")
            else:
                fallback = self._scene_bbox(scene)
                if fallback is not None:
                    fallback_boxes.append(fallback)
                    warnings.append(
                        f"{scene.scene_id}: no AOI-intersecting bursts were selected; "
                        "used scene footprint bbox for DEM planning."
                    )
                else:
                    warnings.append(
                        f"{scene.scene_id}: no AOI-intersecting bursts were selected and no fallback exists."
                    )

        all_boxes = burst_boxes + fallback_boxes
        planned_bbox = self._union_bbox(all_boxes if all_boxes else [])
        if planned_bbox is None:
            planned_bbox = bbox
            warnings.append(
                "DEM planning fell back to the AOI bbox because no scene or burst coverage could be derived."
            )
        planning_mode = "burst_union" if used_burst_union else "scene_fallback"
        notes.append(f"DEM planning mode: {planning_mode}")
        notes.append(f"Planned DEM bbox (SNWE): {self._snwe_text(planned_bbox)}")
        if fallback_boxes and used_burst_union:
            notes.append(f"Fallback scene footprint contributors: {len(fallback_boxes)}")

        return DemCoveragePlan(
            source_id=source_id.strip().upper() or "COP30",
            selected_scene_ids=[scene.scene_id for scene in scenes],
            planned_bbox_snwe=planned_bbox,
            planning_mode=planning_mode,
            dem_height_reference=dem_height_reference_for_source(source_id),
            warnings=warnings,
            notes=notes,
        )

    @staticmethod
    def _aoi_bbox(criteria: SearchCriteria) -> tuple[float, float, float, float]:
        geometry = aoi_geojson_from_inputs(
            criteria.aoi_mode,
            bbox=criteria.bbox,
            wkt=criteria.wkt,
            aoi_file=criteria.aoi_file,
        )
        bounds = bounds_from_geojson([geometry] if geometry else [])
        if bounds is None:
            raise ValueError("Could not derive AOI geometry for DEM planning.")
        min_lon, min_lat, max_lon, max_lat = bounds
        return min_lat, max_lat, min_lon, max_lon

    @staticmethod
    def _scene_bbox(scene: SceneRecord) -> tuple[float, float, float, float] | None:
        bounds = bounds_from_geojson([scene.footprint_geojson] if scene.footprint_geojson else [])
        if bounds is None:
            return None
        min_lon, min_lat, max_lon, max_lat = bounds
        return min_lat, max_lat, min_lon, max_lon

    def _expanded_burst_boxes(self, result: IwRecommendationResult) -> list[tuple[float, float, float, float]]:
        boxes: list[tuple[float, float, float, float]] = []
        for swath, selected_ids in result.auto_selected_bursts.items():
            bursts = result.bursts.get(swath, [])
            if not bursts:
                continue
            available = sorted(item.burst_id for item in bursts)
            expanded = self._expand_burst_ids(selected_ids, available)
            lookup = {item.burst_id: item.bbox_snwe for item in bursts}
            boxes.extend(lookup[burst_id] for burst_id in expanded if burst_id in lookup)
        return boxes

    @staticmethod
    def _expand_burst_ids(selected_ids: list[int], available_ids: list[int]) -> list[int]:
        ordered = sorted(set(int(value) for value in selected_ids if int(value) in set(available_ids)))
        if not ordered:
            return []
        min_id = ordered[0]
        max_id = ordered[-1]
        contiguous = [value for value in available_ids if min_id <= value <= max_id]
        if len(contiguous) >= 2:
            return contiguous
        only = contiguous[0] if contiguous else ordered[0]
        position = available_ids.index(only)
        if position + 1 < len(available_ids):
            return [only, available_ids[position + 1]]
        if position - 1 >= 0:
            return [available_ids[position - 1], only]
        return [only]

    @staticmethod
    def _union_bbox(
        bboxes: list[tuple[float, float, float, float]],
    ) -> tuple[float, float, float, float] | None:
        if not bboxes:
            return None
        south = min(item[0] for item in bboxes)
        north = max(item[1] for item in bboxes)
        west = min(item[2] for item in bboxes)
        east = max(item[3] for item in bboxes)
        return south, north, west, east

    @staticmethod
    def _snwe_text(bbox: tuple[float, float, float, float]) -> str:
        return " ".join(f"{value:g}" for value in bbox)


class OpenTopographyDemService:
    """Download one DEM subset from the OpenTopography Global DEM API."""

    API_URL = "https://portal.opentopography.org/API/globaldem"

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
        """Download one planned DEM GeoTIFF into the standalone workspace."""

        api_key = api_key.strip()
        if not api_key:
            failed = task.with_updates(status="failed", message="OpenTopography API key is required for DEM download.")
            if progress_callback:
                progress_callback(failed)
            return self._result_from_task(failed)
        if plan.planned_bbox_snwe is None:
            failed = task.with_updates(status="failed", message="DEM coverage plan is missing a valid bbox.")
            if progress_callback:
                progress_callback(failed)
            return self._result_from_task(failed)

        network = network or NetworkConfig()
        dem_dir = Path(task.output_dir).expanduser() / "DEM"
        dem_dir.mkdir(parents=True, exist_ok=True)
        final_path = self._dem_path(dem_dir, plan)
        part_path = final_path.with_suffix(final_path.suffix + ".part")
        if final_path.exists() and final_path.stat().st_size > 0:
            validation_error = self._geotiff_validation_error(final_path)
            if not validation_error:
                skipped = task.with_updates(
                    status="skipped",
                    local_path=str(final_path),
                    bytes_total=final_path.stat().st_size,
                    bytes_done=final_path.stat().st_size,
                    message="DEM file already exists and passed integrity validation; skipped.",
                )
                if progress_callback:
                    progress_callback(skipped)
                return self._result_from_task(skipped)
            corrupt_path = self._quarantine_corrupt_file(final_path)
            if progress_callback:
                progress_callback(
                    task.with_updates(
                        status="running",
                        local_path=str(corrupt_path),
                        message=(
                            "Existing DEM failed integrity validation and was quarantined at "
                            f"{corrupt_path}: {validation_error}"
                        ),
                    )
                )
        south, north, west, east = plan.planned_bbox_snwe
        params = {
            "demtype": plan.source_id,
            "south": f"{south:.9f}",
            "north": f"{north:.9f}",
            "west": f"{west:.9f}",
            "east": f"{east:.9f}",
            "outputFormat": "GTiff",
            "API_Key": api_key,
        }
        running = task.with_updates(
            status="running",
            local_path=str(final_path),
            message=f"Downloading DEM from OpenTopography ({plan.source_id})...",
        )
        if progress_callback:
            progress_callback(running)
        return self._download_with_aria2(
            task,
            plan,
            api_key,
            network,
            params,
            final_path,
            part_path,
            progress_callback,
            cancel_check,
        )

    def _download_with_aria2(
        self,
        task: DownloadTask,
        plan: DemCoveragePlan,
        api_key: str,
        network: NetworkConfig,
        params: dict[str, str],
        final_path: Path,
        part_path: Path,
        progress_callback: ProgressCallback | None,
        cancel_check: CancelCheck | None,
    ) -> DownloadResult:
        aria2c = shutil.which("aria2c")
        if not aria2c:
            return self._failed_result(
                task,
                part_path,
                final_path,
                "aria2c is required for DEM download but was not found on PATH.",
                progress_callback,
            )

        prepared_url = requests.Request("GET", self.API_URL, params=params).prepare().url
        if not prepared_url:
            return self._failed_result(
                task,
                part_path,
                final_path,
                "could not construct the OpenTopography request URL.",
                progress_callback,
            )
        try:
            request_file = self._write_private_aria2_input(prepared_url, part_path)
        except OSError as exc:
            return self._failed_result(
                task,
                part_path,
                final_path,
                f"could not create the private aria2 request file: {exc}",
                progress_callback,
            )
        command = [
            aria2c,
            "--no-conf=true",
            "--continue=true",
            "--max-tries=3",
            "--retry-wait=5",
            "--allow-overwrite=true",
            "--auto-file-renaming=false",
            "--file-allocation=none",
            "--console-log-level=warn",
            "--summary-interval=1",
            "--show-console-readout=false",
            "--max-connection-per-server=4",
            "--split=4",
            "--min-split-size=1M",
            "--connect-timeout",
            str(max(int(network.timeout_seconds), 1)),
            "--timeout=120",
            "--input-file",
            request_file,
        ]
        command.extend(self._aria2_network_args(network))

        started = time.monotonic()
        initial_size = part_path.stat().st_size if part_path.exists() else 0
        process: subprocess.Popen[str] | None = None
        captured_output = ""
        last_emit = 0.0
        try:
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as process_output:
                try:
                    process = subprocess.Popen(  # noqa: S603 - argv list; shell is not used.
                        command,
                        stdout=process_output,
                        stderr=subprocess.STDOUT,
                        text=True,
                        shell=False,
                    )
                except Exception as exc:
                    return self._failed_result(
                        task,
                        part_path,
                        final_path,
                        f"could not start aria2c: {exc}",
                        progress_callback,
                    )

                while process.poll() is None:
                    self._protect_aria2_control_file(part_path)
                    if cancel_check and cancel_check():
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                        done = part_path.stat().st_size if part_path.exists() else 0
                        self._protect_aria2_control_file(part_path)
                        cancelled = task.with_updates(
                            status="cancelled",
                            local_path=str(part_path),
                            bytes_total=0,
                            bytes_done=done,
                            speed_bps=self._speed_bps(max(done - initial_size, 0), started),
                            eta_seconds=None,
                            backend="aria2",
                            message=f"DEM download cancelled; partial file kept at {part_path}.",
                        )
                        if progress_callback:
                            progress_callback(cancelled)
                        return self._result_from_task(cancelled)
                    now = time.monotonic()
                    if progress_callback and now - last_emit >= 0.5:
                        done = part_path.stat().st_size if part_path.exists() else 0
                        progress_callback(
                            task.with_updates(
                                status="running",
                                local_path=str(part_path),
                                bytes_total=0,
                                bytes_done=done,
                                speed_bps=self._speed_bps(max(done - initial_size, 0), started),
                                eta_seconds=None,
                                backend="aria2",
                                message=f"Downloading DEM with aria2c ({plan.source_id})...",
                            )
                        )
                        last_emit = now
                    time.sleep(0.1)
                process_output.flush()
                process_output.seek(0)
                captured_output = process_output.read()
        finally:
            Path(request_file).unlink(missing_ok=True)

        if process is None:
            return self._failed_result(
                task, part_path, final_path, "aria2c process did not start.", progress_callback
            )
        if process.returncode != 0:
            self._protect_aria2_control_file(part_path)
            detail = self._safe_aria2_excerpt(captured_output, api_key)
            message = f"aria2c exited with status {process.returncode}" + (f": {detail}" if detail else ".")
            return self._failed_result(task, part_path, final_path, message, progress_callback)
        if not part_path.exists() or part_path.stat().st_size <= 0:
            return self._failed_result(
                task,
                part_path,
                final_path,
                "aria2c completed without producing a DEM file.",
                progress_callback,
            )
        with part_path.open("rb") as handle:
            first_chunk = handle.read(64)
        if not self._looks_like_tiff(first_chunk, ""):
            preview = part_path.read_text(encoding="utf-8", errors="ignore")[:200].strip()
            part_path.unlink(missing_ok=True)
            Path(f"{part_path}.aria2").unlink(missing_ok=True)
            detail = self._safe_aria2_excerpt(preview, api_key)
            return self._failed_result(
                task,
                part_path,
                final_path,
                "OpenTopography did not return a GeoTIFF DEM."
                + (f" Response preview: {detail}" if detail else ""),
                progress_callback,
            )

        done = part_path.stat().st_size
        if progress_callback:
            progress_callback(
                task.with_updates(
                    status="running",
                    local_path=str(part_path),
                    bytes_total=done,
                    bytes_done=done,
                    speed_bps=0.0,
                    eta_seconds=None,
                    backend="aria2",
                    message=f"Validating downloaded DEM integrity ({plan.source_id})...",
                )
            )
        validation_error = self._geotiff_validation_error(part_path)
        if validation_error:
            return self._failed_result(
                task,
                part_path,
                final_path,
                "downloaded GeoTIFF is incomplete or corrupt: "
                f"{validation_error}. Keep the .part file for diagnosis and retry the DEM download.",
                progress_callback,
            )

        part_path.replace(final_path)
        completed = task.with_updates(
            status="completed",
            local_path=str(final_path),
            bytes_total=final_path.stat().st_size,
            bytes_done=final_path.stat().st_size,
            speed_bps=0.0,
            eta_seconds=0.0,
            backend="aria2",
            message=f"DEM download completed with aria2c ({plan.source_id}).",
        )
        if progress_callback:
            progress_callback(completed)
        return self._result_from_task(completed)

    @staticmethod
    def _dem_path(dem_dir: Path, plan: DemCoveragePlan) -> Path:
        south, north, west, east = plan.planned_bbox_snwe or (0.0, 0.0, 0.0, 0.0)
        name = (
            f"{plan.source_id.lower()}_"
            f"{south:.4f}_{north:.4f}_{west:.4f}_{east:.4f}".replace("-", "m").replace(".", "p")
        )
        return dem_dir / f"{name}.tif"

    @staticmethod
    def _looks_like_tiff(content_start: bytes, content_type: str) -> bool:
        lowered = content_type.lower()
        if "tiff" in lowered or "geotiff" in lowered or "octet-stream" in lowered:
            return True
        return content_start.startswith(b"II*\x00") or content_start.startswith(b"MM\x00*")

    @staticmethod
    def _write_private_aria2_input(url: str, part_path: Path) -> str:
        """Write a private aria2 task file so credentials stay out of argv."""

        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, prefix="insar_pilot_dem_", suffix=".aria2-input"
        ) as handle:
            handle.write(url)
            # With --input-file, dir/out must be per-task options. Global
            # --dir/--out values are ignored and aria2 otherwise uses the URL
            # basename ("globaldem"), leaving the expected .part path empty.
            handle.write(f"\n  dir={part_path.parent}\n")
            handle.write(f"  out={part_path.name}\n")
            path = handle.name
        Path(path).chmod(0o600)
        return path

    @staticmethod
    def _aria2_network_args(network: NetworkConfig) -> list[str]:
        mode = network.normalized_mode()
        if mode == "direct":
            return ["--all-proxy=", "--http-proxy=", "--https-proxy=", "--ftp-proxy="]
        if mode == "manual":
            args: list[str] = ["--all-proxy="]
            proxies = network.proxy_dict()
            if proxies.get("http"):
                args.extend(["--http-proxy", proxies["http"]])
            if proxies.get("https"):
                args.extend(["--https-proxy", proxies["https"]])
            return args
        return []

    @staticmethod
    def _safe_aria2_excerpt(text: str, api_key: str) -> str:
        """Return bounded aria2 diagnostics without exposing API credentials."""

        redacted = text.replace(api_key, "<redacted>") if api_key else text
        redacted = re.sub(r"(?i)(API_Key=)[^&\s]+", r"\1<redacted>", redacted)
        compact = " ".join(redacted.split())
        return compact[-1200:]

    @staticmethod
    def _protect_aria2_control_file(part_path: Path) -> None:
        """Keep aria2 resume metadata private because it may reference the API URL."""

        control_path = Path(f"{part_path}.aria2")
        if control_path.exists():
            with contextlib.suppress(OSError):
                control_path.chmod(0o600)

    @classmethod
    def _failed_result(
        cls,
        task: DownloadTask,
        part_path: Path,
        final_path: Path,
        detail: str,
        progress_callback: ProgressCallback | None,
    ) -> DownloadResult:
        failed = task.with_updates(
            status="failed",
            local_path=str(part_path if part_path.exists() else final_path),
            backend="aria2",
            message=f"DEM download failed: {detail}",
        )
        if progress_callback:
            progress_callback(failed)
        return cls._result_from_task(failed)

    @staticmethod
    def _geotiff_validation_error(path: Path) -> str:
        """Return an error when GDAL cannot decode every GeoTIFF raster block."""

        gdalinfo = shutil.which("gdalinfo")
        if not gdalinfo:
            return "gdalinfo was not found; full GeoTIFF integrity could not be verified"
        try:
            completed = subprocess.run(  # noqa: S603 - resolved executable and argv list; no shell.
                [gdalinfo, "-json", "-checksum", str(path)],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"gdalinfo integrity check could not run: {exc}"

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        error_lines = [line.strip() for line in stderr.splitlines() if line.lstrip().startswith("ERROR")]
        if completed.returncode != 0:
            return error_lines[-1] if error_lines else (stderr.strip() or f"gdalinfo exit={completed.returncode}")
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            return f"gdalinfo returned invalid metadata: {exc}"
        bands = payload.get("bands", [])
        if not isinstance(bands, list) or not bands:
            return "gdalinfo found no raster bands"
        invalid_checksum = any(isinstance(band, dict) and band.get("checksum") == -1 for band in bands)
        if error_lines or invalid_checksum:
            return error_lines[-1] if error_lines else "GDAL could not compute a raster checksum"
        return ""

    @staticmethod
    def _quarantine_corrupt_file(path: Path) -> Path:
        """Move an invalid final file aside without overwriting earlier evidence."""

        candidate = Path(f"{path}.corrupt")
        index = 1
        while candidate.exists():
            candidate = Path(f"{path}.corrupt.{index}")
            index += 1
        path.replace(candidate)
        return candidate

    @staticmethod
    def _speed_bps(bytes_done: int, started: float) -> float:
        elapsed = max(time.monotonic() - started, 0.001)
        return float(bytes_done) / elapsed

    @staticmethod
    def _result_from_task(task: DownloadTask) -> DownloadResult:
        return DownloadResult(
            task_id=task.task_id,
            scene=task.scene,
            product_type=task.product_type,
            status=task.status,
            local_path=task.local_path,
            message=task.message,
            bytes_total=task.bytes_total,
            bytes_done=task.bytes_done,
            speed_bps=task.speed_bps,
            eta_seconds=task.eta_seconds,
            backend=task.backend,
        )
