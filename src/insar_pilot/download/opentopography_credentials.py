"""User-level OpenTopography credentials for DEM downloads."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

import requests

from insar_pilot.download.network import NetworkConfig


OPENTOPOGRAPHY_ENV_VAR = "INSAR_PILOT_OPENTOPOGRAPHY_KEY"
OPENTOPOGRAPHY_CONFIG_PATH = Path.home() / ".config" / "insar_pilot" / "opentopography.json"
OPENTOPOGRAPHY_TEST_URL = "https://portal.opentopography.org/API/globaldem"


@dataclass(frozen=True)
class OpenTopographyKey:
    """OpenTopography API key loaded from a user-controlled source."""

    key: str
    source: str


@dataclass(frozen=True)
class OpenTopographyKeyCheck:
    """Result of validating an OpenTopography API key."""

    ok: bool
    message: str


def load_opentopography_key(config_path: str | Path | None = None) -> OpenTopographyKey | None:
    """Load an OpenTopography API key from environment or user config."""

    env_key = os.environ.get(OPENTOPOGRAPHY_ENV_VAR, "").strip()
    if env_key:
        return OpenTopographyKey(key=env_key, source=f"environment variable {OPENTOPOGRAPHY_ENV_VAR}")

    path = Path(config_path).expanduser() if config_path else OPENTOPOGRAPHY_CONFIG_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    key = str(payload.get("key", "")).strip()
    if not key:
        return None
    return OpenTopographyKey(key=key, source=str(path))


def save_opentopography_key(key: str, config_path: str | Path | None = None) -> Path:
    """Persist an OpenTopography API key with owner-only permissions."""

    key = key.strip()
    if not key:
        raise ValueError("OpenTopography API key is required.")

    path = Path(config_path).expanduser() if config_path else OPENTOPOGRAPHY_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"key": key}, indent=2) + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path


def test_opentopography_key(
    key: str,
    *,
    network: NetworkConfig | None = None,
    timeout: float | None = None,
) -> OpenTopographyKeyCheck:
    """Validate an OpenTopography API key with a tiny DEM request."""

    key = key.strip()
    if not key:
        return OpenTopographyKeyCheck(False, "OpenTopography API key is required.")

    network = network or NetworkConfig()
    timeout = float(timeout if timeout is not None else network.timeout_seconds)
    session = network.session()
    params = {
        "demtype": "COP30",
        "south": "30.0",
        "north": "30.01",
        "west": "120.0",
        "east": "120.01",
        "outputFormat": "GTiff",
        "API_Key": key,
    }
    try:
        response = session.get(OPENTOPOGRAPHY_TEST_URL, params=params, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.ProxyError as exc:
        return OpenTopographyKeyCheck(False, f"OpenTopography key test failed: proxy is not reachable ({exc}).")
    except requests.exceptions.Timeout:
        return OpenTopographyKeyCheck(
            False,
            f"OpenTopography key test failed: request timed out after {timeout:g}s.",
        )
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        return OpenTopographyKeyCheck(False, f"OpenTopography key test failed: HTTP {status}.")
    except Exception as exc:
        return OpenTopographyKeyCheck(False, f"OpenTopography key test failed: {exc}")

    if not _looks_like_tiff(response.content[:64], response.headers.get("content-type", "")):
        snippet = response.text[:120].strip() if response.text else ""
        message = "OpenTopography key test failed: service did not return a GeoTIFF DEM."
        if snippet:
            message += f" Response preview: {snippet}"
        return OpenTopographyKeyCheck(False, message)
    return OpenTopographyKeyCheck(True, "OpenTopography key is valid.")


def _looks_like_tiff(content_start: bytes, content_type: str) -> bool:
    lowered = content_type.lower()
    if "tiff" in lowered or "geotiff" in lowered or "octet-stream" in lowered:
        return True
    return content_start.startswith(b"II*\x00") or content_start.startswith(b"MM\x00*")
