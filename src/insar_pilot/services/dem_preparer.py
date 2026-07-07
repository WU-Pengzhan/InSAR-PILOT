"""Prepare user-provided DEM files for Sentinel-1 processing workflows."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from insar_pilot.domain.project import APP_METADATA_DIR, EnvironmentConfig
from insar_pilot.services.command_plan import CommandPlan
from insar_pilot.services.shell import ShellCommandBuilder


@dataclass
class GeoTiffInspection:
    is_geographic_wgs84: bool
    summary: str
    payload: dict


@dataclass
class DemPreparation:
    final_dem_path: str
    plans: list[CommandPlan] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class DemPreparationService:
    """Convert common DEM inputs into processing-ready DEM paths."""

    GEOTIFF_SUFFIXES = {".tif", ".tiff"}

    def __init__(
        self,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._runner = runner

    @classmethod
    def is_geotiff(cls, path: Path) -> bool:
        return path.suffix.lower() in cls.GEOTIFF_SUFFIXES

    def prepare(
        self,
        environment: EnvironmentConfig,
        input_path: str | Path,
        height_reference: str,
        work_dir: Path,
        logs_dir: Path,
    ) -> DemPreparation:
        source = Path(input_path).expanduser()
        if not source.exists():
            raise ValueError(f"DEM path was not found: {source}")

        if not self.is_geotiff(source):
            return DemPreparation(final_dem_path=str(source))

        inspection_log = logs_dir / "dem_inspect.log"
        inspection = self.inspect_geotiff(environment, source, inspection_log)
        if not inspection.is_geographic_wgs84:
            raise ValueError(
                "GeoTIFF DEM import currently requires a geographic WGS84 grid "
                "(for example EPSG:4326). Please reproject the DEM before import."
            )
        if height_reference not in {"egm96", "egm2008", "wgs84"}:
            raise ValueError(
                "Choose the GeoTIFF DEM height reference before generation: "
                "EGM96 geoid, EGM2008 geoid, or WGS84 ellipsoid."
            )

        dem_dir = work_dir / APP_METADATA_DIR / "dem_import"
        dem_dir.mkdir(parents=True, exist_ok=True)
        base_name = self._safe_name(source.stem) or "imported_dem"
        if height_reference == "wgs84":
            final_dem = dem_dir / f"{base_name}.dem.wgs84"
            self._cleanup_outputs(final_dem)
            notes = [
                f"GeoTIFF DEM detected: {source}",
                f"GeoTIFF inspection: {inspection.summary}",
                "User selected WGS84 ellipsoid heights; geoid correction will be skipped.",
                f"Prepared DEM target: {final_dem}",
            ]
            plans = [
                CommandPlan(
                    label="Import DEM GeoTIFF to ENVI",
                    command=(
                        f"gdal_translate -of ENVI "
                        f"{shlex.quote(str(source))} {shlex.quote(str(final_dem))}"
                    ),
                    cwd=str(work_dir),
                    log_path=str(logs_dir / "dem_import_gdal_translate.log"),
                    step_name="dem import",
                    kind="setup",
                ),
                CommandPlan(
                    label="Create processing metadata for DEM",
                    command=f"gdal2isce_xml.py -i {shlex.quote(str(final_dem))}",
                    cwd=str(work_dir),
                    log_path=str(logs_dir / "dem_import_gdal2isce.log"),
                    step_name="dem import",
                    kind="setup",
                ),
            ]
            return DemPreparation(final_dem_path=str(final_dem), plans=plans, notes=notes)

        if height_reference == "egm2008":
            final_dem = dem_dir / f"{base_name}.dem.wgs84"
            self._cleanup_outputs(final_dem)
            notes = [
                f"GeoTIFF DEM detected: {source}",
                f"GeoTIFF inspection: {inspection.summary}",
                "User selected EGM2008 geoid heights; the DEM will be corrected to WGS84 ellipsoid heights.",
                f"Prepared DEM target: {final_dem}",
            ]
            plans = [
                CommandPlan(
                    label="Convert DEM GeoTIFF from EGM2008 to WGS84 ellipsoid",
                    command=(
                        f"gdalwarp -overwrite -of ENVI "
                        f"-s_srs EPSG:4326+3855 -t_srs EPSG:4979 "
                        f"{shlex.quote(str(source))} {shlex.quote(str(final_dem))}"
                    ),
                    cwd=str(work_dir),
                    log_path=str(logs_dir / "dem_import_gdalwarp_egm2008.log"),
                    step_name="dem import",
                    kind="setup",
                ),
                CommandPlan(
                    label="Create processing metadata for DEM",
                    command=f"gdal2isce_xml.py -i {shlex.quote(str(final_dem))}",
                    cwd=str(work_dir),
                    log_path=str(logs_dir / "dem_import_gdal2isce.log"),
                    step_name="dem import",
                    kind="setup",
                ),
            ]
            return DemPreparation(final_dem_path=str(final_dem), plans=plans, notes=notes)

        isce_dem = dem_dir / f"{base_name}.dem"
        wgs84_dem = Path(f"{isce_dem}.wgs84")
        self._cleanup_outputs(isce_dem, wgs84_dem)
        notes = [
            f"GeoTIFF DEM detected: {source}",
            f"GeoTIFF inspection: {inspection.summary}",
            "User selected EGM96 geoid heights; the DEM will be corrected to WGS84 ellipsoid heights.",
            f"Prepared DEM target: {wgs84_dem}",
        ]
        plans = [
            CommandPlan(
                label="Import DEM GeoTIFF to ENVI",
                command=(
                    f"gdal_translate -of ENVI "
                    f"{shlex.quote(str(source))} {shlex.quote(str(isce_dem))}"
                ),
                cwd=str(work_dir),
                log_path=str(logs_dir / "dem_import_gdal_translate.log"),
                step_name="dem import",
                kind="setup",
            ),
            CommandPlan(
                label="Create processing metadata for DEM",
                command=f"gdal2isce_xml.py -i {shlex.quote(str(isce_dem))}",
                cwd=str(work_dir),
                log_path=str(logs_dir / "dem_import_gdal2isce.log"),
                step_name="dem import",
                kind="setup",
            ),
            CommandPlan(
                label="Convert DEM heights from EGM96 to WGS84",
                command=self._build_geoid_correction_command(isce_dem),
                cwd=str(work_dir),
                log_path=str(logs_dir / "dem_import_wgs84.log"),
                step_name="dem import",
                kind="setup",
            ),
        ]
        return DemPreparation(final_dem_path=str(wgs84_dem), plans=plans, notes=notes)

    def inspect_geotiff(
        self,
        environment: EnvironmentConfig,
        path: Path,
        log_path: Path | None = None,
    ) -> GeoTiffInspection:
        builder = ShellCommandBuilder(environment)
        completed = self._runner(
            builder.wrap(f"gdalinfo -json {shlex.quote(str(path))}"),
            capture_output=True,
            text=True,
        )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(stdout + stderr, encoding="utf-8")

        if completed.returncode != 0:
            detail = stderr.strip() or stdout.strip() or f"exit={completed.returncode}"
            raise RuntimeError(f"Could not inspect GeoTIFF DEM with gdalinfo: {detail}")

        payload = json.loads(stdout)
        summary = self._summarize_coordinate_system(payload)
        return GeoTiffInspection(
            is_geographic_wgs84=self._is_geographic_wgs84(payload),
            summary=summary,
            payload=payload,
        )

    @staticmethod
    def _safe_name(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")

    def _cleanup_outputs(self, *targets: Path) -> None:
        for target in targets:
            for candidate in self._sidecar_candidates(target):
                if not candidate.exists() or not candidate.is_file():
                    continue
                try:
                    candidate.unlink()
                except OSError as exc:
                    raise RuntimeError(
                        f"Could not remove stale DEM artifact before import: {candidate}"
                    ) from exc

    @staticmethod
    def _sidecar_candidates(base: Path) -> tuple[Path, ...]:
        return (
            base,
            Path(f"{base}.hdr"),
            Path(f"{base}.xml"),
            Path(f"{base}.vrt"),
            Path(f"{base}.aux.xml"),
        )

    @staticmethod
    def _wkt_text(payload: dict) -> str:
        coordinate_system = payload.get("coordinateSystem")
        if isinstance(coordinate_system, dict):
            for key in ("wkt", "wkt2", "proj4"):
                value = coordinate_system.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        if isinstance(coordinate_system, str):
            return coordinate_system
        return ""

    def _is_geographic_wgs84(self, payload: dict) -> bool:
        wkt = self._wkt_text(payload).upper()
        if not wkt:
            return False
        is_geographic = "GEOGCRS" in wkt or "GEOGCS" in wkt
        return is_geographic and "WGS 84" in wkt

    def _summarize_coordinate_system(self, payload: dict) -> str:
        wkt = self._wkt_text(payload)
        if not wkt:
            return "missing coordinate system metadata"
        upper = wkt.upper()
        if "GEOGCRS" in upper or "GEOGCS" in upper:
            if "WGS 84" in upper:
                return "geographic WGS84"
            return "geographic but not WGS84"
        if "PROJCRS" in upper or "PROJCS" in upper:
            return "projected coordinate system"
        return "unrecognized coordinate system"

    @staticmethod
    def _build_geoid_correction_command(isce_dem: Path) -> str:
        script = f"""
import isceobj
from contrib.demUtils.Correct_geoid_i2_srtm import Correct_geoid_i2_srtm

base = {str(isce_dem)!r}
dem = isceobj.createDemImage()
dem.load(base + ".xml")
dem.reference = "EGM96"
dem.renderHdr(base + ".xml")
converter = Correct_geoid_i2_srtm()
converter.outputFilename = base + ".wgs84"
out = converter(dem, -1)
out.setAccessMode("READ")
out.renderHdr()
"""
        return f"python -c {shlex.quote(script)}"
