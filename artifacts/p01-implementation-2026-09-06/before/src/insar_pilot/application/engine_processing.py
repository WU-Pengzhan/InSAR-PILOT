"""Adapters for existing official processors; no application-owned SAR algorithms."""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path
from typing import Any

from insar_pilot.backends.isce3.nisar import NisarInsarValidator, NisarRifgPlanBuilder
from insar_pilot.domain.engine import SENTINEL_LABELS, ArtifactOutput, OutputAsset, QCMetric
from insar_pilot.domain.local_data import AssetRef
from insar_pilot.domain.project import InputEntry, PreparedInputs, ProjectDocument, WorkflowConfig
from insar_pilot.domain.task_runtime import RuntimeProfile
from insar_pilot.providers.local import build_default_local_reader_registry
from insar_pilot.services.official_processing_paths import Isce2TopsStageDiscovery
from insar_pilot.services.runfile_plan import (
    build_parallel_batch_command,
    parse_run_file,
    split_batches_for_parallelism,
)
from insar_pilot.services.stack_generator import StackWorkflowService


def runtime_environment(profile: dict[str, Any]) -> dict[str, str]:
    python = Path(profile["python_executable"]).expanduser().resolve(strict=True)
    prefix = python.parent.parent
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment["CONDA_PREFIX"] = str(prefix)
    environment["PATH"] = f"{prefix / 'bin'}:/usr/local/bin:/usr/bin:/bin"
    environment["PROJ_DATA"] = str(prefix / "share" / "proj")
    environment["GDAL_DATA"] = str(prefix / "share" / "gdal")
    if profile.get("omp_threads") is not None:
        threads = int(profile["omp_threads"])
        if not 1 <= threads <= (os.cpu_count() or 1):
            raise ValueError("OpenMP thread count is outside the available CPU range.")
        environment["OMP_NUM_THREADS"] = str(threads)
    stack = prefix / "share" / "isce2" / "topsStack"
    if stack.is_dir():
        extras = [str(p) for p in (prefix / "lib").glob("python*/site-packages/isce/applications")]
        extras += [str(p.parent) for p in (prefix / "lib").glob("python*/site-packages/snaphu/snaphu")]
        environment["PATH"] = ":".join([str(stack), *extras, environment["PATH"]])
        environment["PYTHONPATH"] = str(stack.parent)
        environment["ISCE_ROOT"] = str(prefix)
    if profile.get("network_mode", "direct") == "direct":
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            environment.pop(key, None)
    return environment


def input_path(store: Any, pipeline: dict[str, Any], role: str) -> Path:
    ids = pipeline["inputs"].get(role, [])
    if len(ids) != 1:
        raise ValueError(f"Exactly one {role} artifact is required.")
    return Path(store.artifact(ids[0])["assets"][0]["uri"])


def build_nisar(store: Any, pipeline: dict[str, Any], workspace: Path) -> list[str]:
    params = pipeline["parameters"]
    if params.get("compute_mode", "CPU") != "CPU":
        raise ValueError("CUDA execution is not yet validated by this adapter; select CPU.")
    registry = build_default_local_reader_registry()
    reference = registry.read(AssetRef(str(input_path(store, pipeline, "reference")), "source_product"))
    secondary = registry.read(AssetRef(str(input_path(store, pipeline, "secondary")), "source_product"))
    profile = RuntimeProfile("web-nisar", "isce3.nisar_rifg", pipeline["environment"])
    template = params["template_path"]
    if "_template_content" in pipeline:
        frozen = workspace / "validated-template.yaml"
        frozen.write_text(pipeline["_template_content"])
        template = str(frozen)
    plan = NisarRifgPlanBuilder().build(
        reference,
        secondary,
        AssetRef(str(input_path(store, pipeline, "dem")), "dem"),
        output_dir=workspace,
        template_path=template,
        profile=profile,
        frequency=params.get("frequency", "A"),
        polarization=params.get("polarization", "HH"),
        product_type=params.get("product_type", "GUNW"),
        geocode_bounds=tuple(params["geocode_bounds"]) if params.get("geocode_bounds") else None,
    )
    NisarRifgPlanBuilder().write_runconfig(plan)
    for directory in ("products", "scratch", "logs"):
        (workspace / directory).mkdir(exist_ok=True)
    return list(plan.command)


def nisar_outputs(workspace: Path, parameters: dict[str, Any]) -> tuple[list[ArtifactOutput], list[QCMetric]]:
    import h5py

    target = parameters.get("product_type", "GUNW")
    frequency, polarization = parameters.get("frequency", "A"), parameters.get("polarization", "HH")
    output: list[ArtifactOutput] = []
    metrics: list[QCMetric] = []
    products = sorted((workspace / "products").glob("*.h5"))
    products += [p for kind in ("RIFG", "RUNW") if (p := workspace / "scratch" / f"{kind}.h5").is_file()]
    found: set[str] = set()
    for path in products:
        with h5py.File(path, "r") as container:
            raw = container["/science/LSAR/identification/productType"][()]
            kind = raw.decode() if isinstance(raw, bytes) else str(raw)
        if kind not in {"RIFG", "RUNW", "GUNW"}:
            continue
        report = NisarInsarValidator().validate(path, product_type=kind, frequency=frequency, polarization=polarization)
        if not report.valid:
            raise ValueError(f"Invalid {kind}: {report.reason_codes}")
        if report.phase_dtype != ("complex64" if kind == "RIFG" else "float32") or report.coherence_dtype != "float32":
            raise ValueError(f"Unexpected {kind} scientific dtypes.")
        spatial: dict[str, Any] = {"grid_kind": "radar", "shape": list(report.shape)}
        with h5py.File(path, "r") as container:
            if kind == "GUNW":
                # ISCE3 0.25 stores coordinate axes on each product grid, not on
                # frequencyA; wrapped and unwrapped grids may have different looks.
                grid = container[report.phase_dataset.rsplit("/", 1)[0]]
                x, y = grid["xCoordinates"][:], grid["yCoordinates"][:]
                epsg = int(grid["projection"][()])
                if len(x) != report.shape[1] or len(y) != report.shape[0] or len(x) < 2 or len(y) < 2:
                    raise ValueError("GUNW coordinate axis contract failed.")
                import numpy as np

                if not (
                    np.isfinite(x).all()
                    and np.isfinite(y).all()
                    and (np.diff(x) > 0).all()
                    and (np.diff(y) < 0).all()
                    and np.allclose(np.diff(x), x[1] - x[0])
                    and np.allclose(np.diff(y), y[1] - y[0])
                ):
                    raise ValueError("GUNW requires finite, regular eastward/north-up coordinate axes.")
                spatial = {
                    "grid_kind": "map",
                    "crs": f"EPSG:{epsg}",
                    "shape": list(report.shape),
                    "bounds": [
                        float(x[0] - (x[1] - x[0]) / 2),
                        float(y[-1] + (y[1] - y[0]) / 2),
                        float(x[-1] + (x[1] - x[0]) / 2),
                        float(y[0] - (y[1] - y[0]) / 2),
                    ],
                }
            import numpy as np

            coherence = container[report.coherence_dataset]
            stride = max(1, int(max(coherence.shape) / 512))
            sample = coherence[::stride, ::stride]
            valid = sample[np.isfinite(sample)]
            if valid.size:
                if valid.min() < 0 or valid.max() > 1.00001:
                    raise ValueError("Coherence is outside its physical range.")
                metrics.append(
                    QCMetric(
                        f"{kind}.coherence.mean",
                        float(valid.mean()),
                        "1",
                        str(path),
                        sampling=f"stride={stride}; finite samples including zero",
                    )
                )
                for quantile in (5, 50, 95):
                    metrics.append(
                        QCMetric(
                            f"{kind}.coherence.p{quantile}",
                            float(np.percentile(valid, quantile)),
                            "1",
                            str(path),
                            sampling=f"stride={stride}; finite samples including zero",
                        )
                    )
            identification = container["/science/LSAR/identification"]

            def scalar(name: str, group: Any = identification) -> str | None:
                if name not in group:
                    return None
                value = group[name][()]
                return value.decode() if isinstance(value, bytes) else str(value)

            pair_dates = [scalar("referenceZeroDopplerStartTime"), scalar("secondaryZeroDopplerStartTime")]
            look_direction = scalar("lookDirection")
            frequency_path = (
                f"/science/LSAR/{kind}/{'grids' if kind == 'GUNW' else 'swaths'}/frequency{frequency}/centerFrequency"
            )
            wavelength = 299792458.0 / float(container[frequency_path][()]) if frequency_path in container else None
        logical = [("phase", report.phase_dataset, "rad"), ("coherence", report.coherence_dataset, "1")]
        if kind != "RIFG":
            component = report.phase_dataset.rsplit("/", 1)[0] + "/connectedComponents"
            with h5py.File(path, "r") as container:
                if (
                    component not in container
                    or container[component].shape != report.shape
                    or container[component].dtype.kind not in "iu"
                ):
                    raise ValueError(f"Invalid connected components contract for {kind}.")
            logical.append(("connected_components", component, "label"))
        for role, dataset, unit in logical:
            output.append(
                ArtifactOutput(
                    f"{kind}.{role}",
                    (OutputAsset(str(path), role, dataset),),
                    {
                        "phase_dataset": dataset,
                        "product_type": kind,
                        "logical_role": role,
                        "unit": unit,
                        "wavelength": wavelength,
                        "pair_dates": pair_dates if all(pair_dates) else None,
                        "look_direction": look_direction,
                        "missing_metadata": ["phase_convention", "reference"] + ([] if wavelength else ["wavelength"]),
                        "coherence_dataset": report.coherence_dataset,
                        "frequency": frequency,
                        "polarization": polarization,
                    },
                    spatial,
                )
            )
        found.add(kind)
    if target not in found:
        raise ValueError(f"Required {target} output is missing.")
    return output, metrics


def build_sentinel_generation(store: Any, pipeline: dict[str, Any], workspace: Path) -> list[str]:
    params = pipeline["parameters"]
    allowed = {
        "bbox_snwe",
        "reference_date",
        "swath_numbers",
        "polarization",
        "num_connections",
        "azimuth_looks",
        "range_looks",
        "num_proc",
        "coregistration",
    }
    config = WorkflowConfig(**{k: v for k, v in params.items() if k in allowed})
    config.work_dir = str(workspace)
    config.workflow = "interferogram"
    config.dem_path = str(input_path(store, pipeline, "dem"))
    orbit_dir = workspace / "inputs" / "Orbit"
    orbit_dir.mkdir(parents=True)
    for aid in pipeline["inputs"].get("orbit", []):
        source = Path(store.artifact(aid)["assets"][0]["uri"])
        (orbit_dir / source.name).symlink_to(source)
    if not any(orbit_dir.iterdir()):
        raise ValueError("OrbitEOF input artifacts are required.")
    config.orbit_path = str(orbit_dir)
    config.aux_path = params.get("aux_path", "")
    sources = [Path(store.artifact(aid)["assets"][0]["uri"]) for aid in pipeline["inputs"].get("slc", [])]
    if len(sources) < 2:
        raise ValueError("TOPS requires at least two SLC sources.")
    manifest = workspace / "inputs" / "safe_inputs.txt"
    manifest.write_text("\n".join(map(str, sources)) + "\n")
    prepared = PreparedInputs(
        str(manifest), entries=[InputEntry(str(p), "safe" if p.is_dir() else "zip") for p in sources]
    )
    document = ProjectDocument(workflow=config)
    command = StackWorkflowService().build_generate_command(document, prepared)
    return shlex.split(command)


def sentinel_stage_commands(workspace: Path, step: dict[str, Any], logs: Path, parallel: int) -> list[list[str]]:
    discovered = Isce2TopsStageDiscovery().discover(workspace)
    labels = tuple(Path(s.source_path).name.split("_", 2)[-1] for s in discovered)
    if labels != SENTINEL_LABELS:
        raise ValueError(f"Official TOPS plan is incompatible with the validated stage mapping: {labels}")
    label = step["official_label"]
    matches = [s for s in discovered if Path(s.source_path).name.split("_", 2)[-1] == label]
    if len(matches) != 1:
        raise ValueError(f"Official plan does not provide the validated stage {label}.")
    batches = split_batches_for_parallelism(parse_run_file(Path(matches[0].source_path)), max(1, parallel))
    if not batches:
        raise ValueError("Official stage is empty.")
    return [
        [
            "bash",
            "-c",
            build_parallel_batch_command(
                batch, {c.index: str(logs / f"command_{c.index:04d}.combined.log") for c in batch}
            ),
        ]
        for batch in batches
    ]


def workspace_inventory(workspace: Path) -> dict[str, tuple[int, int]]:
    return {
        str(p): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in workspace.rglob("*")
        if p.is_file()
        and not p.is_symlink()
        and not p.name.endswith(".log")
        and "inputs" not in p.relative_to(workspace).parts
    }


def sentinel_outputs(workspace: Path, before: dict[str, tuple[int, int]], step: dict[str, Any]) -> list[ArtifactOutput]:
    after = workspace_inventory(workspace)
    changed = [
        p
        for p, stat in after.items()
        if before.get(p) != stat and not set(Path(p).relative_to(workspace).parts) & {"run_files", "configs"}
    ]
    if not changed:
        raise ValueError("Official stage produced no changed scientific files.")
    output = [
        ArtifactOutput(
            step["official_label"],
            tuple(OutputAsset(p, "stage_output") for p in changed),
            {"official_stage": step["official_label"]},
        )
    ]
    # Keep the complete stage boundary, plus addressable raster products with
    # explicit radar coordinates. These are never assigned a map CRS by filename.
    for filename in changed:
        path = Path(filename)
        if path.suffix != ".vrt" or "merged" not in path.relative_to(workspace).parts:
            continue
        scientific_suffix = path.with_suffix("").suffix
        if scientific_suffix not in {".slc", ".int", ".cor", ".unw", ".conncomp", ".rdr"}:
            continue
        import rasterio

        with rasterio.open(path) as dataset:
            shape = [dataset.height, dataset.width]
            if min(shape) <= 0:
                raise ValueError(f"Invalid raster dimensions: {path}")
            metadata = {
                "official_stage": step["official_label"],
                "raster_format": "ISCE/GDAL",
                "dtype": dataset.dtypes[0],
                "bands": dataset.count,
                "nodata": dataset.nodata,
                "missing_metadata": ["wavelength", "phase_convention", "reference", "pair_dates"],
            }
            output.append(
                ArtifactOutput(
                    path.with_suffix("").name,
                    (OutputAsset(str(path), "raster"),),
                    metadata,
                    {"grid_kind": "radar", "shape": shape},
                )
            )
    return output


def application_provenance() -> dict[str, Any]:
    import hashlib
    import json
    import subprocess

    from insar_pilot import __version__

    source = Path(__file__).resolve().parents[1]
    frozen = source.parent / "provenance.json"
    if frozen.is_file():
        return dict(json.loads(frozen.read_text()))
    hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*.py")}
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    return {
        "software_version": __version__,
        "git_revision": revision,
        "source_hashes": hashes,
        "application_python": sys.version,
        "reproduction_limits": [
            "External inputs currently use stat-change detection; strong verification is separately recorded."
        ],
    }


def freeze_run_evidence(run_dir: Path, workspace: Path, runtime: dict[str, Any]) -> None:
    """Preserve source and native processor evidence independently of the workspace."""
    import shutil
    import subprocess
    import tarfile

    from insar_pilot.infrastructure.engine_store import atomic_json, file_digest

    config = run_dir / "config"
    config.mkdir(exist_ok=True)
    source = Path(__file__).resolve().parents[1]
    archive = config / "application-source.tar.gz"
    if not archive.exists():
        with tarfile.open(archive, "x:gz") as bundle:
            for path in sorted(source.rglob("*.py")):
                bundle.add(path, arcname=str(path.relative_to(source)))
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD", "--", "*.py", "pyproject.toml"], cwd=source, capture_output=True, check=True
            )
            (config / "tracked-source.diff").write_bytes(result.stdout)
        except (OSError, subprocess.CalledProcessError):
            pass
        atomic_json(config / "code-evidence.json", {"source_archive_sha256": file_digest(archive)})
    # Native logs are evidence, not executable pipeline step identities.
    for folder in ("logs", "configs", "run_files", "runconfig"):
        origin = workspace / folder
        if origin.is_dir():
            target = (run_dir / "logs" / "native") if folder == "logs" else (config / folder)
            shutil.copytree(origin, target, dirs_exist_ok=True)
    atomic_json(config / "runtime-profile.json", runtime)
