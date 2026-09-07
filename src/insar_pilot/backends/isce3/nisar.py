"""Read-only runtime probing and auditable NISAR InSAR runconfig planning."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from importlib import import_module
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from insar_pilot.domain.local_data import AssetRef, LocalSARProduct
from insar_pilot.domain.task_runtime import RuntimeProfile
from insar_pilot.services.product_compatibility import PairCompatibilityService

_BACKEND_ID = "isce3.nisar_rifg"
_SUPPORTED_PRODUCT_TYPES = frozenset({"RIFG", "RUNW", "GUNW"})
_PROBE_SCRIPT = """
import json
import isce3
import nisar
from osgeo import gdal
from osgeo import osr
import nisar.workflows.insar
drivers = {
    name: bool(gdal.GetDriverByName(name))
    for name in ("HDF5", "HDF5Image")
}
spatial_ref = osr.SpatialReference()
epsg_ok = spatial_ref.ImportFromEPSG(4326) == 0
print(json.dumps({
    "isce3": getattr(isce3, "__version__", "unknown"),
    "nisar": getattr(nisar, "__version__", getattr(isce3, "__version__", "unknown")),
    "gdal": gdal.__version__,
    "drivers": drivers,
    "epsg_ok": epsg_ok,
}))
""".strip()


@dataclass(frozen=True)
class NisarRuntimeProbeReport:
    available: bool
    reason_codes: tuple[str, ...]
    versions: tuple[tuple[str, str], ...] = ()
    message: str = ""


@dataclass(frozen=True)
class NisarRifgPlan:
    runconfig_path: str
    runconfig_text: str
    command: tuple[str, ...]
    output_product: AssetRef
    scratch_dir: str
    product_type: str = "RIFG"


@dataclass(frozen=True)
class NisarRifgValidationReport:
    valid: bool
    reason_codes: tuple[str, ...]
    product_path: str
    frequency: str
    polarization: str
    shape: tuple[int, ...] = ()
    wrapped_dtype: str = ""
    coherence_dtype: str = ""
    message: str = ""


@dataclass(frozen=True)
class NisarRifgRunReport:
    succeeded: bool
    exit_code: int
    elapsed_seconds: float
    log_path: str
    output_product: AssetRef
    validation: NisarRifgValidationReport | NisarInsarValidationReport | None = None
    message: str = ""


@dataclass(frozen=True)
class NisarInsarValidationReport:
    valid: bool
    reason_codes: tuple[str, ...]
    product_path: str
    product_type: str
    frequency: str
    polarization: str
    phase_dataset: str = ""
    coherence_dataset: str = ""
    shape: tuple[int, ...] = ()
    phase_dtype: str = ""
    coherence_dtype: str = ""
    message: str = ""


class NisarIsce3RuntimeProbe:
    """Probe the exact workflow import and GDAL HDF5 drivers without processing data."""

    def probe(self, profile: RuntimeProfile, *, timeout_seconds: float = 20.0) -> NisarRuntimeProbeReport:
        if profile.backend_id != _BACKEND_ID:
            return NisarRuntimeProbeReport(False, ("backend_profile_mismatch",))
        python_executable = profile.settings.get("python_executable")
        if not isinstance(python_executable, str) or not python_executable.strip():
            return NisarRuntimeProbeReport(False, ("python_executable_missing",))
        path = Path(python_executable).expanduser()
        if not path.is_file():
            return NisarRuntimeProbeReport(False, ("python_executable_missing",), message=str(path))
        environment = _runtime_environment(profile, path)
        try:
            result = subprocess.run(
                (str(path), "-c", _PROBE_SCRIPT),
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return NisarRuntimeProbeReport(False, ("runtime_probe_failed",), message=str(exc))
        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip()
            reason = "workflow_import_failed"
            if "pyaps3" in message:
                reason = "pyaps3_missing"
            elif "No module named 'isce3'" in message or 'No module named "isce3"' in message:
                reason = "isce3_missing"
            return NisarRuntimeProbeReport(False, (reason,), message=message[-4000:])
        try:
            payload = json.loads(result.stdout)
            drivers = payload.get("drivers", {})
            if not isinstance(drivers, dict) or not all(drivers.get(name) for name in ("HDF5", "HDF5Image")):
                return NisarRuntimeProbeReport(False, ("gdal_hdf5_driver_missing",))
            if payload.get("epsg_ok") is not True:
                return NisarRuntimeProbeReport(False, ("proj_database_unavailable",))
            versions = tuple(
                sorted(
                    (key, str(value))
                    for key, value in payload.items()
                    if key in {"gdal", "isce3", "nisar"}
                )
            )
        except (JSONDecodeError, AttributeError, TypeError) as exc:
            return NisarRuntimeProbeReport(False, ("runtime_probe_invalid_output",), message=str(exc))
        return NisarRuntimeProbeReport(True, (), versions)


class NisarRifgPlanBuilder:
    """Derive a new RIFG runconfig from a validated mission template."""

    MAX_TEMPLATE_BYTES = 2 * 1024 * 1024

    def build(
        self,
        reference: LocalSARProduct,
        secondary: LocalSARProduct,
        dem: AssetRef,
        *,
        output_dir: str | Path,
        template_path: str | Path,
        profile: RuntimeProfile,
        frequency: str,
        polarization: str,
        product_type: str = "RIFG",
        geocode_bounds: tuple[float, float, float, float] | None = None,
    ) -> NisarRifgPlan:
        if profile.backend_id != _BACKEND_ID:
            raise ValueError("Runtime profile does not belong to the NISAR RIFG backend.")
        report = PairCompatibilityService().check(reference, secondary)
        if not report.compatible or report.mission != "NISAR":
            reasons = ", ".join(report.reason_codes)
            raise ValueError(f"NISAR RIFG inputs are incompatible: {reasons}")
        normalized_frequency = frequency.strip().upper()
        normalized_polarization = polarization.strip().upper()
        normalized_product_type = product_type.strip().upper()
        if normalized_product_type not in _SUPPORTED_PRODUCT_TYPES:
            raise ValueError(f"Unsupported NISAR InSAR product type: {normalized_product_type}")
        if normalized_frequency not in report.common_frequency_bands:
            raise ValueError(f"Frequency is not common to the pair: {normalized_frequency}")
        if normalized_polarization not in report.common_polarizations:
            raise ValueError(f"Polarization is not common to the pair: {normalized_polarization}")
        if dem.subdataset is not None or dem.role not in {"dem", "prepared_dem"}:
            raise ValueError("NISAR RIFG requires a file-based DEM asset.")

        template = self._load_template(Path(template_path).expanduser())
        groups = _required_dict(_required_dict(template, "runconfig"), "groups")
        inputs = _required_dict(groups, "input_file_group")
        ancillary = _required_dict(groups, "dynamic_ancillary_file_group")
        primary = _required_dict(groups, "primary_executable")
        paths = _required_dict(groups, "product_path_group")
        processing = _required_dict(groups, "processing")
        subset = _required_dict(processing, "input_subset")

        target_dir = Path(output_dir).expanduser()
        products_dir = target_dir / "products"
        scratch_dir = target_dir / "scratch"
        product_name = normalized_product_type.lower()
        runconfig_path = target_dir / "runconfig" / f"nisar_{product_name}.json"
        output_product_path = products_dir / f"{normalized_product_type}_product.h5"
        inputs["reference_rslc_file"] = _source_uri(reference)
        inputs["secondary_rslc_file"] = _source_uri(secondary)
        ancillary["dem_file"] = dem.uri
        primary["product_type"] = normalized_product_type
        paths["product_path"] = str(products_dir)
        paths["scratch_path"] = str(scratch_dir)
        paths["sas_output_file"] = str(output_product_path)
        logging_group = groups.get("logging")
        if isinstance(logging_group, dict):
            logging_group["path"] = str(target_dir / "logs" / "insar_workflow.log")
        subset["list_of_frequencies"] = {normalized_frequency: [normalized_polarization]}
        if geocode_bounds is not None:
            geocode = _required_dict(processing, "geocode")
            top_left_x, top_left_y, bottom_right_x, bottom_right_y = geocode_bounds
            if top_left_x >= bottom_right_x or top_left_y <= bottom_right_y:
                raise ValueError("Geocode bounds must be ordered as left, top, right, bottom.")
            _required_dict(geocode, "top_left").update({"x_abs": top_left_x, "y_abs": top_left_y})
            _required_dict(geocode, "bottom_right").update(
                {"x_abs": bottom_right_x, "y_abs": bottom_right_y}
            )

        python_executable = profile.settings.get("python_executable")
        if not isinstance(python_executable, str) or not python_executable.strip():
            raise ValueError("Runtime profile requires python_executable.")
        text = json.dumps(template, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
        return NisarRifgPlan(
            runconfig_path=str(runconfig_path),
            runconfig_text=text,
            command=(python_executable, "-m", "nisar.workflows.insar", str(runconfig_path)),
            output_product=AssetRef(
                str(output_product_path), product_name, media_type="application/x-hdf5"
            ),
            scratch_dir=str(scratch_dir),
            product_type=normalized_product_type,
        )

    def write_runconfig(self, plan: NisarRifgPlan, *, replace_existing: bool = False) -> Path:
        """Atomically write only the planned config; this never starts ISCE3."""

        target = Path(plan.runconfig_path)
        if target.exists() and not replace_existing:
            raise FileExistsError(f"Runconfig already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temp_path = Path(stream.name)
                stream.write(plan.runconfig_text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, target)
        except OSError:
            if temp_path is not None:
                with suppress(OSError):
                    temp_path.unlink(missing_ok=True)
            raise
        return target

    def _load_template(self, path: Path) -> dict[str, object]:
        if not path.is_file():
            raise FileNotFoundError(f"NISAR runconfig template was not found: {path}")
        if path.stat().st_size > self.MAX_TEMPLATE_BYTES:
            raise ValueError(f"NISAR runconfig template is too large: {path}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except JSONDecodeError as exc:
            raise ValueError("NISAR runconfig template must use JSON-compatible YAML.") from exc
        if not isinstance(value, dict):
            raise TypeError("NISAR runconfig template must contain an object.")
        return value


class NisarRifgValidator:
    """Validate the minimum ISCE3 RIFG contract without loading full rasters."""

    def validate(self, product_path: str | Path, *, frequency: str, polarization: str) -> NisarRifgValidationReport:
        source = Path(product_path).expanduser()
        normalized_frequency = frequency.strip().upper()
        normalized_polarization = polarization.strip().upper()
        if not source.is_file():
            return NisarRifgValidationReport(
                False, ("output_missing",), str(source), normalized_frequency, normalized_polarization
            )
        try:
            h5py = import_module("h5py")
        except ImportError:
            return NisarRifgValidationReport(
                False, ("h5py_missing",), str(source), normalized_frequency, normalized_polarization
            )
        base = f"/science/LSAR/RIFG/swaths/frequency{normalized_frequency}/interferogram"
        wrapped_path = f"{base}/{normalized_polarization}/wrappedInterferogram"
        coherence_path = f"{base}/{normalized_polarization}/coherenceMagnitude"
        try:
            with h5py.File(source, "r") as container:
                product_type = _hdf5_text(container, "/science/LSAR/identification/productType")
                reasons: list[str] = []
                if product_type.upper() != "RIFG":
                    reasons.append("wrong_product_type")
                if wrapped_path not in container:
                    reasons.append("wrapped_interferogram_missing")
                if coherence_path not in container:
                    reasons.append("coherence_missing")
                if reasons:
                    return NisarRifgValidationReport(
                        False,
                        tuple(reasons),
                        str(source),
                        normalized_frequency,
                        normalized_polarization,
                    )
                wrapped = container[wrapped_path]
                coherence = container[coherence_path]
                if tuple(wrapped.shape) != tuple(coherence.shape) or len(wrapped.shape) != 2:
                    reasons.append("raster_shape_mismatch")
                if any(int(length) <= 0 for length in wrapped.shape):
                    reasons.append("empty_raster")
                return NisarRifgValidationReport(
                    not reasons,
                    tuple(reasons),
                    str(source),
                    normalized_frequency,
                    normalized_polarization,
                    tuple(int(length) for length in wrapped.shape),
                    str(wrapped.dtype),
                    str(coherence.dtype),
                )
        except (OSError, TypeError, ValueError) as exc:
            return NisarRifgValidationReport(
                False,
                ("hdf5_unreadable",),
                str(source),
                normalized_frequency,
                normalized_polarization,
                message=str(exc),
            )


class NisarInsarValidator:
    """Validate RIFG, RUNW, or GUNW product contracts using HDF5 metadata only."""

    def validate(
        self,
        product_path: str | Path,
        *,
        product_type: str,
        frequency: str,
        polarization: str,
    ) -> NisarInsarValidationReport:
        source = Path(product_path).expanduser()
        normalized_type = product_type.strip().upper()
        normalized_frequency = frequency.strip().upper()
        normalized_polarization = polarization.strip().upper()
        if normalized_type not in _SUPPORTED_PRODUCT_TYPES:
            return NisarInsarValidationReport(
                False,
                ("unsupported_product_type",),
                str(source),
                normalized_type,
                normalized_frequency,
                normalized_polarization,
            )
        if not source.is_file():
            return NisarInsarValidationReport(
                False,
                ("output_missing",),
                str(source),
                normalized_type,
                normalized_frequency,
                normalized_polarization,
            )
        try:
            h5py = import_module("h5py")
        except ImportError:
            return NisarInsarValidationReport(
                False,
                ("h5py_missing",),
                str(source),
                normalized_type,
                normalized_frequency,
                normalized_polarization,
            )

        if normalized_type == "RIFG":
            base = f"/science/LSAR/RIFG/swaths/frequency{normalized_frequency}/interferogram"
            phase_path = f"{base}/{normalized_polarization}/wrappedInterferogram"
            coherence_path = f"{base}/{normalized_polarization}/coherenceMagnitude"
            connected_path = ""
        elif normalized_type == "RUNW":
            base = f"/science/LSAR/RUNW/swaths/frequency{normalized_frequency}/interferogram"
            phase_path = f"{base}/{normalized_polarization}/unwrappedPhase"
            coherence_path = f"{base}/{normalized_polarization}/coherenceMagnitude"
            connected_path = f"{base}/{normalized_polarization}/connectedComponents"
        else:
            base = f"/science/LSAR/GUNW/grids/frequency{normalized_frequency}/unwrappedInterferogram"
            phase_path = f"{base}/{normalized_polarization}/unwrappedPhase"
            coherence_path = f"{base}/{normalized_polarization}/coherenceMagnitude"
            connected_path = f"{base}/{normalized_polarization}/connectedComponents"

        try:
            with h5py.File(source, "r") as container:
                actual_type = _hdf5_text(container, "/science/LSAR/identification/productType").upper()
                reasons: list[str] = []
                if actual_type != normalized_type:
                    reasons.append("wrong_product_type")
                if phase_path not in container:
                    reasons.append("phase_dataset_missing")
                if coherence_path not in container:
                    reasons.append("coherence_missing")
                if connected_path and connected_path not in container:
                    reasons.append("connected_components_missing")
                if reasons:
                    return NisarInsarValidationReport(
                        False,
                        tuple(reasons),
                        str(source),
                        normalized_type,
                        normalized_frequency,
                        normalized_polarization,
                        phase_path,
                        coherence_path,
                    )
                phase = container[phase_path]
                coherence = container[coherence_path]
                if tuple(phase.shape) != tuple(coherence.shape) or len(phase.shape) != 2:
                    reasons.append("raster_shape_mismatch")
                if any(int(length) <= 0 for length in phase.shape):
                    reasons.append("empty_raster")
                if connected_path and tuple(container[connected_path].shape) != tuple(phase.shape):
                    reasons.append("connected_components_shape_mismatch")
                return NisarInsarValidationReport(
                    not reasons,
                    tuple(reasons),
                    str(source),
                    normalized_type,
                    normalized_frequency,
                    normalized_polarization,
                    phase_path,
                    coherence_path,
                    tuple(int(length) for length in phase.shape),
                    str(phase.dtype),
                    str(coherence.dtype),
                )
        except (OSError, TypeError, ValueError) as exc:
            return NisarInsarValidationReport(
                False,
                ("hdf5_unreadable",),
                str(source),
                normalized_type,
                normalized_frequency,
                normalized_polarization,
                phase_path,
                coherence_path,
                message=str(exc),
            )


class NisarRifgRunner:
    """Execute one planned ISCE3 workflow with cancellation and an auditable log."""

    def run(
        self,
        plan: NisarRifgPlan,
        profile: RuntimeProfile,
        *,
        frequency: str,
        polarization: str,
        cancel_check: Callable[[], bool] | None = None,
        timeout_seconds: float | None = None,
    ) -> NisarRifgRunReport:
        probe = NisarIsce3RuntimeProbe().probe(profile)
        if not probe.available:
            return NisarRifgRunReport(
                False,
                2,
                0.0,
                "",
                plan.output_product,
                message=f"ISCE3 runtime unavailable: {', '.join(probe.reason_codes)}. {probe.message}".strip(),
            )
        runconfig = Path(plan.runconfig_path)
        if not runconfig.is_file():
            return NisarRifgRunReport(
                False, 2, 0.0, "", plan.output_product, message=f"Runconfig does not exist: {runconfig}"
            )
        output_path = Path(plan.output_product.uri)
        if output_path.exists():
            return NisarRifgRunReport(
                False, 2, 0.0, "", plan.output_product, message=f"Output already exists: {output_path}"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Path(plan.scratch_dir).mkdir(parents=True, exist_ok=True)
        product_name = plan.product_type.lower()
        log_path = runconfig.parent.parent / "logs" / f"nisar_{product_name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        python_path = Path(plan.command[0]).expanduser()
        environment = _runtime_environment(profile, python_path)
        started = time.monotonic()
        with log_path.open("w", encoding="utf-8") as log:
            log.write("$ " + " ".join(plan.command) + "\n")
            log.flush()
            process = subprocess.Popen(  # noqa: S603 - fixed argv; no shell.
                plan.command,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                env=environment,
            )
            deadline = started + timeout_seconds if timeout_seconds is not None else None
            cancelled = False
            timed_out = False
            while process.poll() is None:
                if cancel_check is not None and cancel_check():
                    cancelled = True
                    process.terminate()
                    break
                if deadline is not None and time.monotonic() >= deadline:
                    timed_out = True
                    process.terminate()
                    break
                time.sleep(0.2)
            if cancelled or timed_out:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
            exit_code = int(process.wait())
            log.write(f"\n[exit={exit_code}]\n")
        elapsed = time.monotonic() - started
        if cancelled:
            return NisarRifgRunReport(
                False,
                exit_code,
                elapsed,
                str(log_path),
                plan.output_product,
                message=f"NISAR {plan.product_type} run cancelled.",
            )
        if timed_out:
            return NisarRifgRunReport(
                False,
                exit_code,
                elapsed,
                str(log_path),
                plan.output_product,
                message=f"NISAR {plan.product_type} run timed out.",
            )
        if exit_code != 0:
            return NisarRifgRunReport(
                False,
                exit_code,
                elapsed,
                str(log_path),
                plan.output_product,
                message=f"ISCE3 {plan.product_type} exited with status {exit_code}.",
            )
        if plan.product_type == "RIFG":
            validation: NisarRifgValidationReport | NisarInsarValidationReport = (
                NisarRifgValidator().validate(
                    output_path, frequency=frequency, polarization=polarization
                )
            )
        else:
            validation = NisarInsarValidator().validate(
                output_path,
                product_type=plan.product_type,
                frequency=frequency,
                polarization=polarization,
            )
        return NisarRifgRunReport(
            validation.valid,
            exit_code,
            elapsed,
            str(log_path),
            plan.output_product,
            validation,
            (
                f"ISCE3 {plan.product_type} completed and validated."
                if validation.valid
                else f"{plan.product_type} output validation failed."
            ),
        )


def _required_dict(parent: dict[str, object], key: str) -> dict[str, object]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"NISAR runconfig template is missing object: {key}")
    return value


def _source_uri(product: LocalSARProduct) -> str:
    sources = tuple(asset for asset in product.assets if asset.role == "source_product" and asset.subdataset is None)
    if len(sources) != 1:
        raise ValueError(f"Product requires exactly one source_product asset: {product.product_id}")
    return sources[0].uri


def _hdf5_text(container: Any, path: str) -> str:
    if path not in container:
        return ""
    value = container[path][()]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def _runtime_environment(profile: RuntimeProfile, python_executable: Path) -> dict[str, str]:
    environment = os.environ.copy()
    configured = profile.settings.get("proj_data")
    if isinstance(configured, str) and configured.strip():
        environment["PROJ_DATA"] = configured
        return environment
    inferred = python_executable.resolve().parent.parent / "share" / "proj"
    if (inferred / "proj.db").is_file():
        environment["PROJ_DATA"] = str(inferred)
    return environment


__all__ = [
    "NisarInsarValidationReport",
    "NisarInsarValidator",
    "NisarIsce3RuntimeProbe",
    "NisarRifgPlan",
    "NisarRifgPlanBuilder",
    "NisarRifgRunReport",
    "NisarRifgRunner",
    "NisarRifgValidationReport",
    "NisarRifgValidator",
    "NisarRuntimeProbeReport",
]
