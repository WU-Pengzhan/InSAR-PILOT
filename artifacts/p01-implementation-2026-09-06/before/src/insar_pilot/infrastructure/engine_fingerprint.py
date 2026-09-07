"""Small, deterministic runtime/template observations used in scientific signatures."""

import hashlib
import json
from pathlib import Path
from typing import Any

from insar_pilot.domain.engine import digest


def runtime_fingerprint(environment: dict[str, Any]) -> dict[str, Any]:
    executable = environment.get("python_executable")
    if not executable:
        return {"profile": environment, "runtime": "unspecified"}
    python = Path(executable).expanduser().resolve()
    if not python.is_file():
        return {"profile": environment, "runtime": "missing"}
    packages = {}
    for path in sorted((python.parent.parent / "conda-meta").glob("*.json")):
        body = json.loads(path.read_text())
        packages[body["name"]] = {k: body.get(k) for k in ("version", "build", "sha256", "md5")}
    stat = python.stat()
    return {"profile": environment, "python_stat": [stat.st_size, stat.st_mtime_ns], "conda_packages": packages}


def scientific_environment(pipeline: dict[str, Any]) -> dict[str, Any]:
    result = runtime_fingerprint(pipeline["environment"])
    template = pipeline["parameters"].get("template_path")
    if template:
        result["template_sha256"] = hashlib.sha256(Path(template).expanduser().read_bytes()).hexdigest()
    return result


def runtime_matches(pipeline: dict[str, Any]) -> bool:
    frozen = dict(pipeline.get("_scientific_environment", {}))
    frozen.pop("template_sha256", None)
    return not frozen or digest(frozen) == digest(runtime_fingerprint(pipeline["environment"]))
