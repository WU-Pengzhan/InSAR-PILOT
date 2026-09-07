"""Render full-resolution quicklooks for core radar products."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from insar_pilot import __version__
from insar_pilot.domain.project import APP_METADATA_DIR
from insar_pilot.services.command_plan import CommandPlan


@dataclass
class VisualizationRequest:
    mode: str = ""
    primary_input_path: str = ""
    secondary_input_path: str = ""
    range_looks: int = 1
    azimuth_looks: int = 1
    overlay_brightness: float = 0.5
    crop_valid_extent: bool = True
    work_dir: str = ""
    output_bmp_path: str = ""
    output_path: str = ""
    product_kind: str = ""
    render_style: str = ""
    colormap: str = "viridis"
    range_mode: str = "auto"
    range_min: float | None = None
    range_max: float | None = None
    metadata_path: str = ""
    product_id: str = ""
    product_label: str = ""


@dataclass
class VisualizationBuildResult:
    plan: CommandPlan
    output_path: str
    log_path: str
    job_dir: str
    summary: str
    render_signature: str = ""
    action: str = "preview"
    metadata_path: str = ""

    @property
    def output_bmp_path(self) -> str:
        """Compatibility alias for controllers created before PNG support."""

        return self.output_path


class VisualizationService:
    """Build shell command plans for visualization products."""

    _SUPPORTED_GDAL_INPUTS = {".vrt", ".tif", ".tiff"}
    _SUPPORTED_MODES = {
        "slc_amplitude",
        "wrapped_phase",
        "int_slc_overlay",
        "coherence",
        "unwrapped_phase",
        "custom_scalar",
    }
    _PERCENTILE_LOW = 2.0
    _PERCENTILE_HIGH = 99.5

    def build_signature(self, request: VisualizationRequest) -> str:
        mode = self._normalized_mode(request)
        primary_input = request.primary_input_path
        secondary_input = request.secondary_input_path
        if mode == "int_slc_overlay":
            primary_input, secondary_input = self._resolve_overlay_inputs(request)
        payload = {
            "mode": mode,
            "primary_input_path": str(Path(primary_input).expanduser()),
            "range_looks": int(request.range_looks),
            "azimuth_looks": int(request.azimuth_looks),
            "overlay_brightness": float(request.overlay_brightness),
            "crop_valid_extent": bool(request.crop_valid_extent),
            "colormap": request.colormap.strip().lower(),
            "range_mode": request.range_mode.strip().lower(),
            "range_min": request.range_min,
            "range_max": request.range_max,
            "product_id": request.product_id,
            "primary_snapshot": self._path_snapshot(primary_input),
            "secondary_snapshot": self._path_snapshot(secondary_input),
        }
        return json.dumps(payload, sort_keys=True)

    def build(self, request: VisualizationRequest, logs_dir: Path) -> VisualizationBuildResult:
        mode = self._normalized_mode(request)
        if mode not in self._SUPPORTED_MODES:
            raise ValueError(f"Unsupported visualization mode: {request.mode}")

        if request.azimuth_looks < 1 or request.range_looks < 1:
            raise ValueError("Azimuth/range looks must be >= 1.")

        work_dir = Path(request.work_dir).expanduser()
        if not work_dir.exists():
            raise ValueError(f"Working directory was not found: {work_dir}")

        output = Path(request.output_path or request.output_bmp_path).expanduser()
        output_format = output.suffix.lower()
        if output_format not in {".bmp", ".png"}:
            raise ValueError("Output path must end with .png or .bmp.")
        metadata_path = Path(request.metadata_path).expanduser() if request.metadata_path else None

        stamp = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
        visualize_root = work_dir / APP_METADATA_DIR / "visualize"
        cache_root = visualize_root / "cache"
        job_dir = cache_root / f"job_{stamp}_{mode}"
        output_parent = output.parent
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"visualize_{stamp}.log"

        commands: list[str] = [
            f"mkdir -p {self._q(str(job_dir))}",
            f"mkdir -p {self._q(str(output_parent))}",
            f"rm -f {self._q(str(output))}",
        ]
        if metadata_path is not None:
            commands.extend(
                [
                    f"mkdir -p {self._q(str(metadata_path.parent))}",
                    f"rm -f {self._q(str(metadata_path))}",
                ]
            )
        notes = [f"Mode: {mode}", f"Output image: {output}"]

        if mode == "slc_amplitude":
            prepared = self._prepare_input(
                role="primary",
                role_kind="slc",
                raw_path=request.primary_input_path,
                job_dir=job_dir,
                commands=commands,
            )
            slc_amplitude = self._prepare_amplitude_for_visualization(
                source=prepared,
                role="primary",
                azimuth_looks=request.azimuth_looks,
                range_looks=request.range_looks,
                job_dir=job_dir,
                commands=commands,
            )
            notes.append(f"SLC input: {prepared}")
            notes.append(f"SLC amplitude source: {slc_amplitude}")
            self._append_phase_amplitude_render(
                commands=commands,
                source=slc_amplitude,
                source_mode="amplitude_real",
                output_mode="slc_grayscale",
                job_dir=job_dir,
                output_path=output,
                crop_valid_extent=False,
                metadata_path=metadata_path,
                metadata=self._metadata_payload(request, mode),
            )
        elif mode == "wrapped_phase":
            prepared = self._prepare_input(
                role="primary",
                role_kind="int",
                raw_path=request.primary_input_path,
                job_dir=job_dir,
                commands=commands,
            )
            rendered = self._apply_looks_if_needed(
                source=prepared,
                role="primary",
                role_kind="int",
                azimuth_looks=request.azimuth_looks,
                range_looks=request.range_looks,
                job_dir=job_dir,
                commands=commands,
            )
            notes.append(f"Interferogram input: {prepared}")
            notes.append(f"Interferogram render source: {rendered}")
            self._append_phase_amplitude_render(
                commands=commands,
                source=rendered,
                source_mode="complex",
                output_mode="phase_color",
                job_dir=job_dir,
                output_path=output,
                crop_valid_extent=request.crop_valid_extent,
                metadata_path=metadata_path,
                metadata=self._metadata_payload(request, mode),
            )
        elif mode == "int_slc_overlay":
            overlay_input, slc_input = self._resolve_overlay_inputs(request)
            int_prepared = self._prepare_input(
                role="int",
                role_kind="int",
                raw_path=overlay_input,
                job_dir=job_dir,
                commands=commands,
            )
            int_rendered = self._apply_looks_if_needed(
                source=int_prepared,
                role="int",
                role_kind="int",
                azimuth_looks=request.azimuth_looks,
                range_looks=request.range_looks,
                job_dir=job_dir,
                commands=commands,
            )
            overlay = job_dir / "overlay.unw"
            notes.append(f"Overlay INT input: {int_prepared}")
            if slc_input:
                slc_prepared = self._prepare_input(
                    role="slc",
                    role_kind="slc",
                    raw_path=slc_input,
                    job_dir=job_dir,
                    commands=commands,
                )
                slc_amplitude = self._prepare_amplitude_for_visualization(
                    source=slc_prepared,
                    role="slc",
                    azimuth_looks=request.azimuth_looks,
                    range_looks=request.range_looks,
                    job_dir=job_dir,
                    commands=commands,
                )
                self._append_same_size_check(commands, slc_amplitude, int_rendered)
                expression = f"a*{request.overlay_brightness:g};arg(b);abs(b)"
                commands.append(
                    "imageMath.py "
                    f"-e={self._q(expression)} "
                    f"-o {self._q(str(overlay))} "
                    "-s BIL -t float "
                    f"--a={self._q(str(slc_amplitude))} "
                    f"--b={self._q(str(int_rendered))}"
                )
                notes.append(f"Overlay SLC input: {slc_prepared}")
                notes.append(f"Overlay SLC amplitude source: {slc_amplitude}")
                notes.append("Overlay amplitude: abs(SLC); phase: arg(INT); validity: abs(INT) > 0")
            else:
                expression = f"abs(a)*{request.overlay_brightness:g};arg(a);abs(a)"
                commands.append(
                    "imageMath.py "
                    f"-e={self._q(expression)} "
                    f"-o {self._q(str(overlay))} "
                    "-s BIL -t float "
                    f"--a={self._q(str(int_rendered))}"
                )
                notes.append("Overlay amplitude fallback: abs(INT); phase: arg(INT)")
            notes.append(f"Overlay render source: {overlay}")
            notes.append(f"Overlay brightness: {request.overlay_brightness:g}")
            self._append_phase_amplitude_render(
                commands=commands,
                source=overlay,
                source_mode="amp_phase_mask_3band",
                output_mode="phase_color",
                job_dir=job_dir,
                output_path=output,
                crop_valid_extent=request.crop_valid_extent,
                metadata_path=metadata_path,
                metadata=self._metadata_payload(request, mode),
            )
        elif mode == "coherence":
            prepared = self._prepare_input(
                role="coherence",
                role_kind="cor",
                raw_path=request.primary_input_path,
                job_dir=job_dir,
                commands=commands,
            )
            rendered = self._apply_looks_if_needed(
                source=prepared,
                role="coherence",
                role_kind="cor",
                azimuth_looks=request.azimuth_looks,
                range_looks=request.range_looks,
                job_dir=job_dir,
                commands=commands,
            )
            notes.append(f"Coherence input: {prepared}")
            self._append_scalar_render(
                commands=commands,
                source=rendered,
                scalar_mode="coherence",
                output_path=output,
                job_dir=job_dir,
                crop_valid_extent=request.crop_valid_extent,
                range_mode="fixed",
                range_min=0.0,
                range_max=1.0,
                metadata_path=metadata_path,
                metadata=self._metadata_payload(request, mode),
            )
        else:
            is_custom = mode == "custom_scalar"
            prepared = self._prepare_input(
                role="custom" if is_custom else "unwrapped",
                role_kind="float" if is_custom else "unw",
                raw_path=request.primary_input_path,
                job_dir=job_dir,
                commands=commands,
            )
            rendered = self._apply_looks_if_needed(
                source=prepared,
                role="custom" if is_custom else "unwrapped",
                role_kind="float" if is_custom else "unw",
                azimuth_looks=request.azimuth_looks,
                range_looks=request.range_looks,
                job_dir=job_dir,
                commands=commands,
            )
            notes.append(
                f"{'Custom scalar' if is_custom else 'Unwrapped phase'} input: {prepared}"
            )
            self._append_scalar_render(
                commands=commands,
                source=rendered,
                scalar_mode="custom_scalar" if is_custom else "unwrapped_phase",
                output_path=output,
                job_dir=job_dir,
                crop_valid_extent=request.crop_valid_extent,
                range_mode=request.range_mode,
                range_min=request.range_min,
                range_max=request.range_max,
                metadata_path=metadata_path,
                metadata=self._metadata_payload(request, mode),
            )

        notes.append(f"Looks: azimuth={request.azimuth_looks}, range={request.range_looks}")
        if mode in {"slc_amplitude", "wrapped_phase", "int_slc_overlay"}:
            notes.append("Stretch: robust log1p with percentiles P2-P99.5")
        elif mode == "coherence":
            notes.append("Color range: fixed 0-1; colormap: viridis")
        elif mode == "unwrapped_phase":
            notes.append("Color range: P2-P98 auto or user-defined; colormap: viridis")
        else:
            notes.append("Custom scalar range: P2-P98 auto or user-defined; colormap: viridis")
        notes.append("Renderer: numpy + GDAL (mdx not required)")
        if mode != "slc_amplitude":
            notes.append(
                "Crop to INT valid-data extent: "
                + ("yes" if request.crop_valid_extent else "no")
            )
        full_command = " && ".join(commands)
        plan = CommandPlan(
            label=f"Visualize ({mode})",
            command=full_command,
            cwd=str(work_dir),
            log_path=str(log_path),
            step_name="visualization",
            kind="visualization",
            metadata={
                "mode": mode,
                "output_path": str(output),
                "output_bmp_path": str(output),
                "metadata_path": str(metadata_path) if metadata_path else "",
                "job_dir": str(job_dir),
                "summary": "\n".join(notes),
            },
        )

        return VisualizationBuildResult(
            plan=plan,
            output_path=str(output),
            log_path=str(log_path),
            job_dir=str(job_dir),
            summary="\n".join(notes),
            metadata_path=str(metadata_path) if metadata_path else "",
        )

    def _prepare_input(
        self,
        role: str,
        role_kind: str,
        raw_path: str,
        job_dir: Path,
        commands: list[str],
    ) -> Path:
        if not raw_path.strip():
            raise ValueError(f"Missing input path for {role}.")
        source = Path(raw_path).expanduser()
        if not source.exists():
            raise ValueError(f"Input was not found for {role}: {source}")

        if source.suffix.lower() == ".xml":
            data_path = source.with_suffix("")
            if not data_path.exists():
                raise ValueError(f"Metadata exists but data file is missing for {role}: {data_path}")
            return data_path

        if Path(f"{source}.xml").exists():
            return source

        if source.suffix.lower() in self._SUPPORTED_GDAL_INPUTS:
            ext = self._role_extension(role_kind)
            converted = job_dir / f"{role}_converted{ext}"
            commands.append(
                f"gdal_translate -of ENVI {self._q(str(source))} {self._q(str(converted))}"
            )
            commands.append(f"gdal2isce_xml.py -i {self._q(str(converted))}")
            return converted

        raise ValueError(
            f"{role} input is not parseable. Provide a .xml file, a data file with sibling .xml, "
            "or a .vrt/.tif/.tiff source."
        )

    def _apply_looks_if_needed(
        self,
        source: Path,
        role: str,
        role_kind: str,
        azimuth_looks: int,
        range_looks: int,
        job_dir: Path,
        commands: list[str],
    ) -> Path:
        if azimuth_looks == 1 and range_looks == 1:
            return source

        ext = self._role_extension(role_kind)
        looked = job_dir / f"{role}_{azimuth_looks}alks_{range_looks}rlks{ext}"
        commands.append(
            "looks.py "
            f"-i {self._q(str(source))} "
            f"-o {self._q(str(looked))} "
            f"-a {azimuth_looks} "
            f"-r {range_looks}"
        )
        return looked

    def _prepare_amplitude_for_visualization(
        self,
        source: Path,
        role: str,
        azimuth_looks: int,
        range_looks: int,
        job_dir: Path,
        commands: list[str],
    ) -> Path:
        amplitude = job_dir / f"{role}_amp.float"
        commands.append(
            "imageMath.py "
            "-e='abs(a)' "
            f"-o {self._q(str(amplitude))} "
            "-t float "
            f"--a={self._q(str(source))}"
        )

        if azimuth_looks == 1 and range_looks == 1:
            return amplitude

        looked = job_dir / f"{role}_amp_{azimuth_looks}alks_{range_looks}rlks.float"
        commands.append(
            "looks.py "
            f"-i {self._q(str(amplitude))} "
            f"-o {self._q(str(looked))} "
            f"-a {azimuth_looks} "
            f"-r {range_looks}"
        )
        return looked

    def _append_phase_amplitude_render(
        self,
        commands: list[str],
        source: Path,
        source_mode: str,
        output_mode: str,
        job_dir: Path,
        output_path: Path,
        crop_valid_extent: bool,
        metadata_path: Path | None,
        metadata: dict[str, object],
    ) -> None:
        ppm_path = job_dir / "render.ppm"
        script = """
import numpy as np
from osgeo import gdal

gdal.UseExceptions()

src = "__SRC__"
ppm = "__PPM__"
output = "__OUTPUT__"
metadata_path = "__METADATA_PATH__"
metadata = __METADATA__
source_mode = "__SOURCE_MODE__"
output_mode = "__OUTPUT_MODE__"
crop_valid_extent = __CROP_VALID_EXTENT__
ds = gdal.Open(src, gdal.GA_ReadOnly)
if ds is None:
    raise RuntimeError(f"Cannot open overlay source: {src}")

if source_mode == "complex":
    data = ds.GetRasterBand(1).ReadAsArray().astype(np.complex64)
    amp = np.abs(data).astype(np.float32)
    phase = np.angle(data).astype(np.float32)
    phase_valid = np.isfinite(data.real) & np.isfinite(data.imag) & (np.abs(data) > 0.0)
elif source_mode == "amp_phase_2band":
    amp = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    phase = ds.GetRasterBand(2).ReadAsArray().astype(np.float32)
    phase_valid = np.isfinite(phase) & np.isfinite(amp) & (amp > 0.0)
elif source_mode == "amp_phase_mask_3band":
    amp = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    phase = ds.GetRasterBand(2).ReadAsArray().astype(np.float32)
    mask = ds.GetRasterBand(3).ReadAsArray().astype(np.float32)
    phase_valid = np.isfinite(phase) & np.isfinite(mask) & (mask > 0.0)
elif source_mode == "amplitude_real":
    amp = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    phase = np.zeros_like(amp, dtype=np.float32)
    phase_valid = np.isfinite(amp) & (amp > 0.0)
else:
    raise RuntimeError(f"Unsupported source mode: {source_mode}")

amp_clean = np.nan_to_num(amp, nan=0.0, posinf=0.0, neginf=0.0)
if output_mode == "phase_color":
    amp_clean = np.where(phase_valid, amp_clean, 0.0)
alog = np.log1p(np.maximum(amp_clean, 0.0))
valid = np.isfinite(alog) & (amp_clean > 0.0)
if np.any(valid):
    lo, hi = np.percentile(alog[valid], [2.0, 99.5])
    if not np.isfinite(lo):
        lo = 0.0
    if not np.isfinite(hi) or hi <= lo:
        hi = lo + 1.0
else:
    lo, hi = 0.0, 1.0
v = np.clip((alog - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)

if output_mode == "slc_grayscale":
    # Keep SLC quicklook readable without washing out bright scatterers.
    v_disp = np.power(v, 1.15)
    rgb = np.repeat(v_disp[:, :, None], 3, axis=2)
elif output_mode == "phase_color":
    h = ((np.nan_to_num(phase, nan=0.0) + np.pi) / (2.0 * np.pi)) % 1.0
    # Slightly reduced saturation to avoid overly neon phase quicklooks.
    s = np.full_like(h, 0.65, dtype=np.float32)

    i = np.floor(h * 6.0).astype(np.int32)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)

    mod = i % 6
    r = np.select([mod == 0, mod == 1, mod == 2, mod == 3, mod == 4, mod == 5], [v, q, p, p, t, v], default=v)
    g = np.select([mod == 0, mod == 1, mod == 2, mod == 3, mod == 4, mod == 5], [t, v, v, q, p, p], default=v)
    b = np.select([mod == 0, mod == 1, mod == 2, mod == 3, mod == 4, mod == 5], [p, p, t, v, v, q], default=v)
    rgb = np.stack([r, g, b], axis=-1)
else:
    raise RuntimeError(f"Unsupported output mode: {output_mode}")

if crop_valid_extent and output_mode == "phase_color" and np.any(phase_valid):
    rows, cols = np.nonzero(phase_valid)
    rgb = rgb[rows.min():rows.max() + 1, cols.min():cols.max() + 1]

rgb = np.nan_to_num(rgb, nan=0.0, posinf=1.0, neginf=0.0)
rgb = np.clip(rgb * 255.0, 0.0, 255.0).astype(np.uint8)

height, width = rgb.shape[:2]
with open(ppm, "wb") as fh:
    fh.write(f"P6\\n{width} {height}\\n255\\n".encode("ascii"))
    fh.write(rgb.tobytes())

if metadata_path:
    import json
    metadata.update({
        "output_path": output,
        "output_width": int(width),
        "output_height": int(height),
        "source_width": int(ds.RasterXSize),
        "source_height": int(ds.RasterYSize),
        "display_range_min": float(lo),
        "display_range_max": float(hi),
    })
    with open(metadata_path, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2, sort_keys=True)
"""
        script = (
            script.replace("__SRC__", str(source) + ".vrt")
            .replace("__PPM__", str(ppm_path))
            .replace("__OUTPUT__", str(output_path))
            .replace("__METADATA_PATH__", str(metadata_path) if metadata_path else "")
            .replace("__METADATA__", repr(metadata))
            .replace("__SOURCE_MODE__", source_mode)
            .replace("__OUTPUT_MODE__", output_mode)
            .replace("__CROP_VALID_EXTENT__", "True" if crop_valid_extent else "False")
        )
        commands.append(f"python -c {self._q(script)}")
        driver = "PNG" if output_path.suffix.lower() == ".png" else "BMP"
        commands.append(f"gdal_translate -of {driver} {self._q(str(ppm_path))} {self._q(str(output_path))}")

    def _append_scalar_render(
        self,
        *,
        commands: list[str],
        source: Path,
        scalar_mode: str,
        output_path: Path,
        job_dir: Path,
        crop_valid_extent: bool,
        range_mode: str,
        range_min: float | None,
        range_max: float | None,
        metadata_path: Path | None,
        metadata: dict[str, object],
    ) -> None:
        normalized_range_mode = range_mode.strip().lower() or "auto"
        if normalized_range_mode not in {"auto", "fixed", "manual"}:
            raise ValueError(f"Unsupported scalar range mode: {range_mode}")
        if normalized_range_mode == "manual" and (
            range_min is None or range_max is None or range_max <= range_min
        ):
            raise ValueError("Manual color range requires maximum > minimum.")

        ppm_path = job_dir / "render.ppm"
        script = """
import json
import numpy as np
from osgeo import gdal

gdal.UseExceptions()

src = "__SRC__"
ppm = "__PPM__"
output = "__OUTPUT__"
metadata_path = "__METADATA_PATH__"
metadata = __METADATA__
scalar_mode = "__SCALAR_MODE__"
range_mode = "__RANGE_MODE__"
manual_min = __RANGE_MIN__
manual_max = __RANGE_MAX__
crop_valid_extent = __CROP_VALID_EXTENT__

ds = gdal.Open(src, gdal.GA_ReadOnly)
if ds is None:
    raise RuntimeError(f"Cannot open scalar result: {src}")

if scalar_mode == "coherence":
    data = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    valid = np.isfinite(data) & (data > 0.0)
    lo, hi = 0.0, 1.0
elif scalar_mode == "unwrapped_phase":
    phase_band = 2 if ds.RasterCount >= 2 else 1
    data = ds.GetRasterBand(phase_band).ReadAsArray().astype(np.float32)
    if ds.RasterCount >= 2:
        amp = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
        valid = np.isfinite(data) & np.isfinite(amp) & (amp > 0.0)
    else:
        valid = np.isfinite(data) & (data != 0.0)
    if range_mode == "manual":
        lo, hi = float(manual_min), float(manual_max)
    elif np.any(valid):
        lo, hi = np.percentile(data[valid], [2.0, 98.0])
        if not np.isfinite(lo):
            lo = 0.0
        if not np.isfinite(hi) or hi <= lo:
            hi = lo + 1.0
    else:
        lo, hi = 0.0, 1.0
elif scalar_mode == "custom_scalar":
    data = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    valid = np.isfinite(data) & (data != 0.0)
    if range_mode == "manual":
        lo, hi = float(manual_min), float(manual_max)
    elif np.any(valid):
        lo, hi = np.percentile(data[valid], [2.0, 98.0])
        if not np.isfinite(lo):
            lo = 0.0
        if not np.isfinite(hi) or hi <= lo:
            hi = lo + 1.0
    else:
        lo, hi = 0.0, 1.0
else:
    raise RuntimeError(f"Unsupported scalar mode: {scalar_mode}")

scaled = np.clip((np.nan_to_num(data, nan=lo) - lo) / (hi - lo), 0.0, 1.0)
stops = np.array([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float32)
colors = np.array([
    [0.267004, 0.004874, 0.329415],
    [0.229739, 0.322361, 0.545706],
    [0.127568, 0.566949, 0.550556],
    [0.369214, 0.788888, 0.382914],
    [0.993248, 0.906157, 0.143936],
], dtype=np.float32)
rgb = np.stack([np.interp(scaled, stops, colors[:, channel]) for channel in range(3)], axis=-1)
rgb[~valid] = 0.0

crop = None
if crop_valid_extent and np.any(valid):
    rows, cols = np.nonzero(valid)
    crop = [int(cols.min()), int(rows.min()), int(cols.max()) + 1, int(rows.max()) + 1]
    rgb = rgb[rows.min():rows.max() + 1, cols.min():cols.max() + 1]

rgb = np.clip(rgb * 255.0, 0.0, 255.0).astype(np.uint8)
height, width = rgb.shape[:2]
with open(ppm, "wb") as fh:
    fh.write(f"P6\\n{width} {height}\\n255\\n".encode("ascii"))
    fh.write(rgb.tobytes())

if metadata_path:
    metadata.update({
        "output_path": output,
        "output_width": int(width),
        "output_height": int(height),
        "source_width": int(ds.RasterXSize),
        "source_height": int(ds.RasterYSize),
        "display_range_min": float(lo),
        "display_range_max": float(hi),
        "crop_pixel_bounds": crop,
    })
    with open(metadata_path, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2, sort_keys=True)
"""
        script = (
            script.replace("__SRC__", str(source) + ".vrt")
            .replace("__PPM__", str(ppm_path))
            .replace("__OUTPUT__", str(output_path))
            .replace("__METADATA_PATH__", str(metadata_path) if metadata_path else "")
            .replace("__METADATA__", repr(metadata))
            .replace("__SCALAR_MODE__", scalar_mode)
            .replace("__RANGE_MODE__", normalized_range_mode)
            .replace("__RANGE_MIN__", repr(range_min))
            .replace("__RANGE_MAX__", repr(range_max))
            .replace("__CROP_VALID_EXTENT__", "True" if crop_valid_extent else "False")
        )
        commands.append(f"python -c {self._q(script)}")
        driver = "PNG" if output_path.suffix.lower() == ".png" else "BMP"
        commands.append(f"gdal_translate -of {driver} {self._q(str(ppm_path))} {self._q(str(output_path))}")

    @staticmethod
    def _normalized_mode(request: VisualizationRequest) -> str:
        product_kind = request.product_kind.strip().lower()
        render_style = request.render_style.strip().lower()
        if product_kind:
            if product_kind == "slc":
                return "slc_amplitude"
            if product_kind == "wrapped_interferogram":
                return "wrapped_phase" if render_style == "phase" else "int_slc_overlay"
            if product_kind in {"coherence", "unwrapped_phase"}:
                return product_kind
            if product_kind == "custom_raster":
                return "custom_scalar"
            if product_kind in VisualizationService._SUPPORTED_MODES:
                return product_kind

        legacy_mode = request.mode.strip().lower()
        return {
            "slc": "slc_amplitude",
            "interferogram": "wrapped_phase",
            "overlay": "int_slc_overlay",
        }.get(legacy_mode, legacy_mode)

    @staticmethod
    def _role_extension(role_kind: str) -> str:
        return {
            "slc": ".slc",
            "int": ".int",
            "cor": ".cor",
            "unw": ".unw",
            "float": ".float",
        }.get(role_kind, ".dat")

    @staticmethod
    def _metadata_payload(request: VisualizationRequest, mode: str) -> dict[str, object]:
        return {
            "schema_version": 1,
            "application_version": __version__,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "product_id": request.product_id,
            "product_label": request.product_label,
            "product_kind": request.product_kind or mode,
            "render_style": request.render_style or mode,
            "primary_input_path": str(Path(request.primary_input_path).expanduser()),
            "secondary_input_path": str(Path(request.secondary_input_path).expanduser())
            if request.secondary_input_path
            else "",
            "range_looks": int(request.range_looks),
            "azimuth_looks": int(request.azimuth_looks),
            "crop_valid_extent": bool(request.crop_valid_extent),
            "overlay_brightness": float(request.overlay_brightness),
            "colormap": request.colormap,
            "range_mode": request.range_mode,
            "requested_range_min": request.range_min,
            "requested_range_max": request.range_max,
        }

    @staticmethod
    def _q(value: str) -> str:
        return shlex.quote(value)

    @staticmethod
    def _looks_like_interferogram(path_text: str) -> bool:
        name = Path(path_text.strip()).name.lower()
        return ".int" in name

    @classmethod
    def _resolve_overlay_inputs(cls, request: VisualizationRequest) -> tuple[str, str]:
        """Return ``(INT, optional SLC)`` and accept the legacy SLC+INT order."""

        primary = request.primary_input_path.strip()
        secondary = request.secondary_input_path.strip()
        if secondary and cls._looks_like_interferogram(secondary) and not cls._looks_like_interferogram(primary):
            return secondary, primary
        if cls._looks_like_interferogram(primary):
            return primary, secondary
        return primary, secondary

    def _append_same_size_check(self, commands: list[str], first: Path, second: Path) -> None:
        script = """
from osgeo import gdal

gdal.UseExceptions()
paths = ["__FIRST__", "__SECOND__"]
datasets = [gdal.Open(path + ".vrt", gdal.GA_ReadOnly) for path in paths]
sizes = [(ds.RasterXSize, ds.RasterYSize) for ds in datasets]
if sizes[0] != sizes[1]:
    raise RuntimeError(
        f"SLC and INT dimensions do not match after looks: {sizes[0]} != {sizes[1]}. "
        "Select the co-registered merged SLC from the same processing grid."
    )
"""
        script = script.replace("__FIRST__", str(first)).replace("__SECOND__", str(second))
        commands.append(f"python -c {self._q(script)}")

    @staticmethod
    def _path_snapshot(path_text: str) -> dict[str, object]:
        text = path_text.strip()
        if not text:
            return {"path": "", "exists": False}

        path = Path(text).expanduser()
        if not path.exists():
            return {"path": str(path), "exists": False}

        stat = path.stat()
        return {
            "path": str(path),
            "exists": True,
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
