"""Task Runtime adapter for the official NISAR ISCE3 InSAR workflow."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from json import JSONDecodeError
from pathlib import Path
from typing import Protocol, cast

from insar_pilot.backends.isce3.nisar import (
    NisarRifgPlan,
    NisarRifgRunner,
    NisarRifgRunReport,
)
from insar_pilot.domain.local_data import AssetRef, JsonValue
from insar_pilot.domain.task_runtime import RuntimeProfile, TaskBackendResult, TaskRunRequest
from insar_pilot.providers.task_runtime import TaskCancelled, TaskExecutionContext


class _Runner(Protocol):
    def run(
        self,
        plan: NisarRifgPlan,
        profile: RuntimeProfile,
        *,
        frequency: str,
        polarization: str,
        cancel_check: Callable[[], bool] | None = None,
        timeout_seconds: float | None = None,
    ) -> NisarRifgRunReport: ...


class NisarIsce3TaskBackend:
    """Execute an existing, auditable runconfig through ``nisar.workflows.insar``."""

    backend_id = "isce3.nisar_rifg"
    _TASK_ID = "nisar.run_product"

    def __init__(self, runner: _Runner | None = None) -> None:
        self._runner = runner or NisarRifgRunner()

    def supports(self, task_id: str) -> bool:
        return task_id == self._TASK_ID

    def run(
        self,
        request: TaskRunRequest,
        profile: RuntimeProfile,
        context: TaskExecutionContext,
    ) -> TaskBackendResult:
        if not self.supports(request.task_id):
            raise ValueError(f"Unsupported NISAR ISCE3 task: {request.task_id}")
        runconfig = _single_runconfig(request.inputs)
        plan, frequency, polarization = _plan_from_runconfig(runconfig, profile)
        timeout = _optional_timeout(request.parameters.get("timeout_seconds"))
        context.log(
            "info",
            "Starting official NISAR ISCE3 product workflow.",
            product_type=plan.product_type,
            runconfig=str(runconfig),
        )
        report = self._runner.run(
            plan,
            profile,
            frequency=frequency,
            polarization=polarization,
            cancel_check=context.cancellation.is_cancelled,
            timeout_seconds=timeout,
        )
        if context.cancellation.is_cancelled():
            raise TaskCancelled(f"NISAR {plan.product_type} workflow was cancelled.")
        exit_code = report.exit_code if report.succeeded else (report.exit_code or 3)
        context.log(
            "info" if report.succeeded else "error",
            report.message,
            exit_code=exit_code,
            log_path=report.log_path,
        )
        return TaskBackendResult(
            outputs=(report.output_product,),
            exit_code=exit_code,
            message=report.message,
        )


def _single_runconfig(inputs: tuple[AssetRef, ...]) -> Path:
    assets = tuple(asset for asset in inputs if asset.role == "runconfig")
    if len(assets) != 1:
        raise ValueError("NISAR product execution requires exactly one runconfig asset.")
    asset = assets[0]
    if asset.subdataset is not None:
        raise ValueError("A NISAR runconfig cannot be an HDF5 subdataset.")
    path = Path(asset.uri).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"NISAR runconfig was not found: {path}")
    return path


def _plan_from_runconfig(
    runconfig: Path,
    profile: RuntimeProfile,
) -> tuple[NisarRifgPlan, str, str]:
    try:
        text = runconfig.read_text(encoding="utf-8")
        root = _mapping(json.loads(text), "runconfig document")
    except (JSONDecodeError, OSError) as exc:
        raise ValueError(f"NISAR runconfig must be readable JSON-compatible YAML: {runconfig}") from exc

    groups = _child(_child(root, "runconfig"), "groups")
    primary = _child(groups, "primary_executable")
    paths = _child(groups, "product_path_group")
    processing = _child(groups, "processing")
    subset = _child(processing, "input_subset")
    product_type = _required_string(primary.get("product_type"), "product_type").upper()
    if product_type not in {"RIFG", "RUNW", "GUNW"}:
        raise ValueError(f"Unsupported NISAR InSAR product type in runconfig: {product_type}")
    output_path = _required_string(paths.get("sas_output_file"), "sas_output_file")
    scratch_path = _required_string(paths.get("scratch_path"), "scratch_path")
    frequencies = _mapping(subset.get("list_of_frequencies"), "list_of_frequencies")
    if len(frequencies) != 1:
        raise ValueError("Task execution requires exactly one NISAR frequency in runconfig.")
    frequency, polarizations_value = next(iter(frequencies.items()))
    if not isinstance(frequency, str) or not isinstance(polarizations_value, (list, tuple)):
        raise TypeError("NISAR frequency/polarization selection is malformed.")
    if len(polarizations_value) != 1 or not isinstance(polarizations_value[0], str):
        raise ValueError("Task execution requires exactly one NISAR polarization in runconfig.")
    python_executable = _required_string(profile.settings.get("python_executable"), "python_executable")
    output_role = product_type.lower()
    plan = NisarRifgPlan(
        runconfig_path=str(runconfig),
        runconfig_text=text,
        command=(python_executable, "-m", "nisar.workflows.insar", str(runconfig)),
        output_product=AssetRef(output_path, output_role, media_type="application/x-hdf5"),
        scratch_dir=scratch_path,
        product_type=product_type,
    )
    return plan, frequency.upper(), polarizations_value[0].upper()


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise TypeError(f"{field_name} must be a string-keyed mapping.")
    return cast(Mapping[str, object], value)


def _child(parent: Mapping[str, object], key: str) -> Mapping[str, object]:
    return _mapping(parent.get(key), key)


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"NISAR runconfig requires {field_name}.")
    return value.strip()


def _optional_timeout(value: JsonValue | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError("timeout_seconds must be a positive number.")
    return float(value)


__all__ = ["NisarIsce3TaskBackend"]
