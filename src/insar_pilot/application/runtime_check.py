"""Read-only CPU runtime checks using the same environment as processing jobs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from insar_pilot.application.engine_processing import runtime_environment
from insar_pilot.domain.engine import utc_now

_SCRIPT = r"""
import importlib, json, shutil, subprocess, sys
checks = []
def check(name, operation):
    try:
        value = operation()
        checks.append({"name": name, "ok": bool(value), "detail": str(value) if value else "unavailable"})
    except Exception as exc:
        # Never return arbitrary exception text: native libraries may expose environment secrets.
        detail = "missing_module:" + str(exc.name) if isinstance(exc, ModuleNotFoundError) else type(exc).__name__
        checks.append({"name": name, "ok": False, "detail": detail})
def version(module):
    value = importlib.import_module(module)
    return getattr(value, "__version__", getattr(value, "release_version", "imported"))
def projection():
    from osgeo import osr
    return osr.SpatialReference().ImportFromEPSG(4326) == 0
def tool(name):
    path = shutil.which(name)
    if not path:
        return False
    return subprocess.run([sys.executable, path, "-h"], capture_output=True, timeout=8).returncode == 0
if PROCESSOR == "isce2":
    check("ISCE2", lambda: version("isce"))
    check("isceobj", lambda: bool(importlib.import_module("isceobj")))
    for name in ("stackSentinel.py", "SentinelWrapper.py"):
        check(name, lambda name=name: tool(name))
else:
    check("ISCE3", lambda: version("isce3"))
    check("nisar.workflows.insar", lambda: bool(importlib.import_module("nisar.workflows.insar")))
    for driver in ("HDF5", "HDF5Image"):
        check("GDAL " + driver,
              lambda driver=driver: bool(importlib.import_module("osgeo.gdal").GetDriverByName(driver)))
check("GDAL", lambda: version("osgeo.gdal"))
check("PROJ", projection)
print("PILOT_RUNTIME_CHECK=" + json.dumps(checks))
"""


def check_runtime(processor: str, python_executable: str | None = None) -> dict[str, Any]:
    if processor not in {"isce2", "isce3"}:
        raise ValueError("Choose isce2 or isce3.")
    python = str(Path(python_executable or sys.executable).expanduser().absolute())
    result: dict[str, Any] = {
        "processor": processor,
        "python_executable": python,
        "checked_at": utc_now(),
        "status": "UNAVAILABLE",
        "mode": "CPU",
        "checks": [],
        "cuda_validated": False,
    }
    if not Path(python).is_file() or not os.access(python, os.X_OK):
        result["reason"] = "python_unavailable"
        return result
    try:
        environment = runtime_environment({"python_executable": python})
        completed = subprocess.run(
            [python, "-c", "PROCESSOR = " + repr(processor) + "\n" + _SCRIPT],
            env=environment,
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
        if completed.returncode:
            result["reason"] = "probe_failed"
            return result
        line = next(line for line in reversed(completed.stdout.splitlines()) if line.startswith("PILOT_RUNTIME_CHECK="))
        checks = json.loads(line.split("=", 1)[1])
        if (
            not isinstance(checks, list)
            or not checks
            or any(
                not isinstance(c, dict)
                or not isinstance(c.get("ok"), bool)
                or not isinstance(c.get("name"), str)
                or not isinstance(c.get("detail"), str)
                for c in checks
            )
        ):
            raise ValueError("Invalid probe result")
        result["checks"] = checks
        result["status"] = "READY" if all(c["ok"] for c in checks) else "UNAVAILABLE"
        result["reason"] = "checks_passed" if result["status"] == "READY" else "requirements_missing"
    except subprocess.TimeoutExpired:
        result["status"] = "UNKNOWN"
        result["reason"] = "probe_timeout"
    except (OSError, ValueError, StopIteration):
        result["status"] = "UNKNOWN"
        result["reason"] = "probe_failed"
    return result
