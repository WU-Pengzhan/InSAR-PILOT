"""Safe command planning and execution for openSEPPO NISAR RSLC subsets."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from insar_pilot.download.geometry import bounds_from_wkt, wkt_from_aoi_file
from insar_pilot.download.network import NetworkConfig


@dataclass(frozen=True)
class NisarSubsetPlan:
    command: tuple[str, ...]
    input_products: tuple[str, ...]
    output_dir: str
    aoi_file: str
    aoi_wkt: str


@dataclass(frozen=True)
class NisarSubsetRunReport:
    succeeded: bool
    exit_code: int
    elapsed_seconds: float
    log_path: str
    outputs: tuple[str, ...]
    message: str


class OpenSeppoSubsetPlanBuilder:
    def build(
        self,
        inputs: tuple[str | Path, ...],
        aoi_file: str | Path,
        output_dir: str | Path,
        *,
        executable: str | Path,
        frequency: str = "A",
        polarizations: tuple[str, ...] = (),
        all_frequencies: bool = False,
        min_height: float | None = None,
        max_height: float | None = None,
        quicklook: bool = False,
        cache: str | Path | None = None,
        keep_cached: bool = False,
        verbose: bool = False,
    ) -> NisarSubsetPlan:
        sources = tuple(_normalize_input(item) for item in inputs)
        if not sources:
            raise ValueError("At least one NISAR RSLC input is required.")
        program = Path(executable).expanduser().resolve()
        if not program.is_file():
            raise FileNotFoundError(f"openSEPPO executable was not found: {program}")
        aoi_path = Path(aoi_file).expanduser().resolve()
        aoi_wkt = wkt_from_aoi_file(aoi_path)
        min_lon, min_lat, max_lon, max_lat = bounds_from_wkt(aoi_wkt)
        target = Path(output_dir).expanduser().resolve()
        normalized_frequency = frequency.strip().upper()
        if normalized_frequency not in {"A", "B"}:
            raise ValueError("NISAR subset frequency must be A or B.")
        normalized_polarizations = tuple(item.strip().upper() for item in polarizations if item.strip())
        if any(item not in {"HH", "HV", "VV", "VH"} for item in normalized_polarizations):
            raise ValueError("NISAR subset polarization must be HH, HV, VV, or VH.")
        command = [
            str(program),
            "-i",
            *sources,
            "-o",
            str(target),
            "-projwin",
            f"{min_lon:.12g}",
            f"{max_lat:.12g}",
            f"{max_lon:.12g}",
            f"{min_lat:.12g}",
            "-projwin_srs",
            "EPSG:4326",
            "-f",
            normalized_frequency,
        ]
        if normalized_polarizations:
            command.extend(("-vars", *normalized_polarizations))
        if all_frequencies:
            command.append("--all_freq")
        if min_height is not None:
            command.extend(("--min_height", f"{min_height:g}"))
        if max_height is not None:
            command.extend(("--max_height", f"{max_height:g}"))
        if quicklook:
            command.append("-ql")
        if cache is not None:
            cache_value = str(cache).strip()
            if not cache_value:
                raise ValueError("openSEPPO cache must be a directory or 'y'.")
            if cache_value.lower() != "y":
                cache_value = str(Path(cache_value).expanduser().resolve())
            command.extend(("-cache", cache_value))
            if keep_cached:
                command.append("-keep")
        elif keep_cached:
            raise ValueError("keep_cached requires an explicit cache directory.")
        if verbose:
            command.append("-v")
        return NisarSubsetPlan(tuple(command), sources, str(target), str(aoi_path), aoi_wkt)


class OpenSeppoSubsetRunner:
    def run(
        self,
        plan: NisarSubsetPlan,
        *,
        cancel_check: Callable[[], bool] | None = None,
        timeout_seconds: float | None = None,
        network: NetworkConfig | None = None,
    ) -> NisarSubsetRunReport:
        target = Path(plan.output_dir)
        if target.exists() and any(target.iterdir()):
            return NisarSubsetRunReport(False, 2, 0.0, "", (), f"Output directory is not empty: {target}")
        target.mkdir(parents=True, exist_ok=True)
        log_path = target / "openseppo_subset.log"
        started = time.monotonic()
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as captured:
            process = subprocess.Popen(  # noqa: S603 - validated executable and fixed argv; no shell.
                plan.command,
                stdout=captured,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                env=_network_environment(network or NetworkConfig()),
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
            captured.seek(0)
            log_path.write_text(captured.read(), encoding="utf-8")
        outputs = tuple(str(path) for path in sorted(target.glob("*.h5")) if path.is_file())
        succeeded = exit_code == 0 and len(outputs) == len(plan.input_products)
        if cancelled:
            message = "NISAR AOI subset cancelled."
        elif timed_out:
            message = "NISAR AOI subset timed out."
        elif not succeeded:
            message = f"openSEPPO exited with status {exit_code} and produced {len(outputs)} HDF5 file(s)."
        else:
            message = f"Created {len(outputs)} AOI-constrained RSLC subset(s)."
        return NisarSubsetRunReport(succeeded, exit_code, time.monotonic() - started, str(log_path), outputs, message)


def _normalize_input(value: str | Path) -> str:
    text = str(value).strip()
    parsed = urlsplit(text)
    if parsed.scheme:
        if parsed.scheme not in {"https", "s3"}:
            raise ValueError(f"Unsupported openSEPPO input URL scheme: {parsed.scheme}")
        if not parsed.netloc or not parsed.path.lower().endswith(".h5"):
            raise ValueError(f"NISAR RSLC URL must identify an HDF5 granule: {text}")
        return text
    source = Path(text).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"NISAR RSLC input was not found: {source}")
    return str(source)


def _network_environment(network: NetworkConfig) -> dict[str, str]:
    environment = os.environ.copy()
    mode = network.normalized_mode()
    if mode == "environment":
        return environment
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        environment.pop(name, None)
    if mode == "manual":
        proxies = network.proxy_dict()
        if proxies.get("http"):
            environment["HTTP_PROXY"] = proxies["http"]
            environment["http_proxy"] = proxies["http"]
        if proxies.get("https"):
            environment["HTTPS_PROXY"] = proxies["https"]
            environment["https_proxy"] = proxies["https"]
    return environment


__all__ = [
    "NisarSubsetPlan",
    "NisarSubsetRunReport",
    "OpenSeppoSubsetPlanBuilder",
    "OpenSeppoSubsetRunner",
]
