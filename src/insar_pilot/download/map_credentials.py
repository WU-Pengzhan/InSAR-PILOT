"""User-level map provider credentials for the download footprint map."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

import requests

from insar_pilot.download.network import NetworkConfig

TIANDITU_ENV_VAR = "INSAR_PILOT_TIANDITU_KEY"
TIANDITU_CONFIG_PATH = Path.home() / ".config" / "insar_pilot" / "tianditu.json"


@dataclass(frozen=True)
class TiandituKey:
    """Tianditu API key loaded from a local user-controlled source."""

    key: str
    source: str


@dataclass(frozen=True)
class TiandituKeyCheck:
    """Result of validating a Tianditu API key against one WMTS tile."""

    ok: bool
    message: str


def load_tianditu_key(config_path: str | Path | None = None) -> TiandituKey | None:
    """Load a Tianditu API key from environment or user config."""

    env_key = os.environ.get(TIANDITU_ENV_VAR, "").strip()
    if env_key:
        return TiandituKey(key=env_key, source=f"environment variable {TIANDITU_ENV_VAR}")

    path = Path(config_path).expanduser() if config_path else TIANDITU_CONFIG_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    key = str(payload.get("key", "")).strip()
    if not key:
        return None
    return TiandituKey(key=key, source=str(path))


def save_tianditu_key(key: str, config_path: str | Path | None = None) -> Path:
    """Persist a Tianditu API key to user config with owner-only permissions."""

    key = key.strip()
    if not key:
        raise ValueError("Tianditu API key is required.")

    path = Path(config_path).expanduser() if config_path else TIANDITU_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"key": key}, indent=2) + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path


def test_tianditu_key(
    key: str,
    *,
    network: NetworkConfig | None = None,
    timeout: float | None = None,
) -> TiandituKeyCheck:
    """Validate a Tianditu API key with a small WMTS tile request."""

    key = key.strip()
    if not key:
        return TiandituKeyCheck(False, "Tianditu API key is required.")

    network = network or NetworkConfig()
    timeout = float(timeout if timeout is not None else network.timeout_seconds)
    session = network.session()
    url = (
        "https://t0.tianditu.gov.cn/img_w/wmts?"
        "SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default"
        "&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX=1&TILEROW=0&TILECOL=1"
        f"&tk={key}"
    )
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.ProxyError as exc:
        return TiandituKeyCheck(False, f"Tianditu key test failed: proxy is not reachable ({exc}).")
    except requests.exceptions.Timeout:
        return TiandituKeyCheck(False, f"Tianditu key test failed: request timed out after {timeout:g}s.")
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        return TiandituKeyCheck(False, f"Tianditu key test failed: HTTP {status}.")
    except Exception as exc:
        return TiandituKeyCheck(False, f"Tianditu key test failed: {exc}")

    content_type = response.headers.get("content-type", "").lower()
    content_start = response.content[:32].lower()
    looks_like_image = (
        content_type.startswith("image/")
        or content_start.startswith(b"\xff\xd8")
        or content_start.startswith(b"\x89png")
    )
    if not looks_like_image:
        return TiandituKeyCheck(False, "Tianditu key test failed: service did not return a map tile image.")
    return TiandituKeyCheck(True, "Tianditu key is valid.")
