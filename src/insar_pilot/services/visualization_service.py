"""Render quicklook BMP previews for SLC and interferogram products."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import shlex

from insar_pilot.domain.project import APP_METADATA_DIR
from insar_pilot.services.command_plan import CommandPlan


@dataclass
class VisualizationRequest:
    mode: str
    primary_input_path: str
    secondary_input_path: str = ""
    range_looks: int = 1
    azimuth_looks: int = 1
    overlay_brightness: float = 0.5
    work_dir: str = ""
    output_bmp_path: str = ""


@dataclass
class VisualizationBuildResult:
    plan: CommandPlan
    output_bmp_path: str
    log_path: str
    job_dir: str
    summary: str
    render_signature: str = ""
    action: str = "preview"


class VisualizationService:
    """Build shell command plans for visualization products."""

    _SUPPORTED_GDAL_INPUTS = {".vrt", ".tif", ".tiff"}
    _SUPPORTED_MODES = {"slc", "interferogram", "overlay"}
    _PERCENTILE_LOW = 2.0
    _PERCENTILE_HIGH = 99.5

    def build_signature(self, request: VisualizationRequest) -> str:
        payload = {
            "mode": request.mode.strip().lower(),
            "primary_input_path": str(Path(request.primary_input_path).expanduser()),
            "secondary_input_path": str(Path(request.secondary_input_path).expanduser()),
            "range_looks": int(request.range_looks),
            "azimuth_looks": int(request.azimuth_looks),
            "overlay_brightness": float(request.overlay_brightness),
            "primary_snapshot": self._path_snapshot(request.primary_input_path),
            "secondary_snapshot": self._path_snapshot(request.secondary_input_path),
        }
        return json.dumps(payload, sort_keys=True)

    def build(self, request: VisualizationRequest, logs_dir: Path) -> VisualizationBuildResult:
        mode = request.mode.strip().lower()
        if mode not in self._SUPPORTED_MODES:
            raise ValueError(f"Unsupported visualization mode: {request.mode}")

        if request.azimuth_looks < 1 or request.range_looks < 1:
            raise ValueError("Azimuth/range looks must be >= 1.")

        work_dir = Path(request.work_dir).expanduser()
        if not work_dir.exists():
            raise ValueError(f"Working directory was not found: {work_dir}")

        output_bmp = Path(request.output_bmp_path).expanduser()
        if output_bmp.suffix.lower() != ".bmp":
            raise ValueError("Output path must end with .bmp.")

        stamp = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
        visualize_root = work_dir / APP_METADATA_DIR / "visualize"
        cache_root = visualize_root / "cache"
        job_dir = cache_root / f"job_{stamp}_{mode}"
        output_parent = output_bmp.parent
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"visualize_{stamp}.log"

        commands: list[str] = [
            f"mkdir -p {self._q(str(job_dir))}",
            f"mkdir -p {self._q(str(output_parent))}",
            f"rm -f {self._q(str(output_bmp))}",
        ]
        notes = [f"Mode: {mode}", f"Output BMP: {output_bmp}"]

        if mode == "slc":
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
                output_bmp=output_bmp,
            )
        elif mode == "interferogram":
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
                output_bmp=output_bmp,
            )
        else:
            slc_prepared = self._prepare_input(
                role="slc",
                role_kind="slc",
                raw_path=request.primary_input_path,
                job_dir=job_dir,
                commands=commands,
            )
            int_prepared = self._prepare_input(
                role="int",
                role_kind="int",
                raw_path=request.secondary_input_path,
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
            expression = f"abs(a)*{request.overlay_brightness:g};arg(b)"
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
            notes.append(f"Overlay INT input: {int_prepared}")
            notes.append(f"Overlay render source: {overlay}")
            notes.append(f"Overlay brightness: {request.overlay_brightness:g}")
            self._append_phase_amplitude_render(
                commands=commands,
                source=overlay,
                source_mode="amp_phase_2band",
                output_mode="phase_color",
                job_dir=job_dir,
                output_bmp=output_bmp,
            )

        notes.append(f"Looks: azimuth={request.azimuth_looks}, range={request.range_looks}")
        notes.append("Stretch: robust log1p with percentiles P2-P99.5")
        notes.append("Renderer: numpy + GDAL (mdx not required)")
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
                "output_bmp_path": str(output_bmp),
                "job_dir": str(job_dir),
                "summary": "\n".join(notes),
            },
        )

        return VisualizationBuildResult(
            plan=plan,
            output_bmp_path=str(output_bmp),
            log_path=str(log_path),
            job_dir=str(job_dir),
            summary="\n".join(notes),
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
            ext = ".slc" if role_kind == "slc" else ".int"
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

        ext = ".slc" if role_kind == "slc" else ".int"
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
        output_bmp: Path,
    ) -> None:
        ppm_path = job_dir / "render.ppm"
        script = """
import numpy as np
from osgeo import gdal

src = "__SRC__"
ppm = "__PPM__"
source_mode = "__SOURCE_MODE__"
output_mode = "__OUTPUT_MODE__"
ds = gdal.Open(src, gdal.GA_ReadOnly)
if ds is None:
    raise RuntimeError(f"Cannot open overlay source: {src}")

if source_mode == "complex":
    data = ds.GetRasterBand(1).ReadAsArray().astype(np.complex64)
    amp = np.abs(data).astype(np.float32)
    phase = np.angle(data).astype(np.float32)
elif source_mode == "amp_phase_2band":
    amp = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    phase = ds.GetRasterBand(2).ReadAsArray().astype(np.float32)
elif source_mode == "amplitude_real":
    amp = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    phase = np.zeros_like(amp, dtype=np.float32)
else:
    raise RuntimeError(f"Unsupported source mode: {source_mode}")

amp_clean = np.nan_to_num(amp, nan=0.0, posinf=0.0, neginf=0.0)
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

rgb = np.nan_to_num(rgb, nan=0.0, posinf=1.0, neginf=0.0)
rgb = np.clip(rgb * 255.0, 0.0, 255.0).astype(np.uint8)

height, width = rgb.shape[:2]
with open(ppm, "wb") as fh:
    fh.write(f"P6\\n{width} {height}\\n255\\n".encode("ascii"))
    fh.write(rgb.tobytes())
"""
        script = (
            script.replace("__SRC__", str(source) + ".vrt")
            .replace("__PPM__", str(ppm_path))
            .replace("__SOURCE_MODE__", source_mode)
            .replace("__OUTPUT_MODE__", output_mode)
        )
        commands.append(f"python -c {self._q(script)}")
        commands.append(f"gdal_translate -of BMP {self._q(str(ppm_path))} {self._q(str(output_bmp))}")

    @staticmethod
    def _q(value: str) -> str:
        return shlex.quote(value)

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
