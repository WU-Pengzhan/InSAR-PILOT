"""Credential discovery hooks for future ASF Earthdata integration."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from netrc import NetrcParseError, netrc
from pathlib import Path

import requests

from insar_pilot.download.network import NetworkConfig


@dataclass(frozen=True)
class EarthdataCredentials:
    """Earthdata credential pair loaded from the local environment."""

    username: str
    password: str
    source: str


@dataclass(frozen=True)
class CredentialCheck:
    """Result of an ASF/Earthdata credential connectivity check."""

    ok: bool
    message: str


@dataclass(frozen=True)
class EndpointCheck:
    """Connectivity result for one remote endpoint."""

    name: str
    url: str
    ok: bool
    message: str


def load_earthdata_credentials(netrc_path: str | Path | None = None) -> EarthdataCredentials | None:
    """Load Earthdata credentials from environment variables or netrc.

    No credentials are embedded in source code. Environment variables take
    precedence over `~/.netrc`.
    """

    username = os.environ.get("EARTHDATA_USERNAME", "").strip()
    password = os.environ.get("EARTHDATA_PASSWORD", "")
    if username and password:
        return EarthdataCredentials(username=username, password=password, source="environment")

    path = Path(netrc_path).expanduser() if netrc_path else Path.home() / ".netrc"
    if not path.exists():
        return None

    try:
        auth = netrc(str(path)).authenticators("urs.earthdata.nasa.gov")
    except (NetrcParseError, OSError):
        return None
    if not auth:
        return None
    login, _, secret = auth
    if not login or not secret:
        return None
    return EarthdataCredentials(username=login, password=secret, source=str(path))


def test_earthdata_connection(
    username: str,
    password: str,
    *,
    network: NetworkConfig | None = None,
    timeout: float | None = None,
) -> CredentialCheck:
    """Validate credentials against Earthdata without blocking indefinitely."""

    username = username.strip()
    if not username or not password:
        return CredentialCheck(False, "ASF Earthdata username and password are required.")
    network = network or NetworkConfig()
    timeout = float(timeout if timeout is not None else network.timeout_seconds)
    session = network.session()
    try:
        response = session.post(
            "https://urs.earthdata.nasa.gov/api/users/find_or_create_token",
            auth=(username, password),
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.exceptions.ProxyError as exc:
        return CredentialCheck(False, f"ASF Earthdata connection failed: proxy is not reachable ({exc}).")
    except requests.exceptions.Timeout:
        return CredentialCheck(False, f"ASF Earthdata connection failed: request timed out after {timeout:g}s.")
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        if status in {401, 403}:
            return CredentialCheck(False, "ASF Earthdata connection failed: username or password was rejected.")
        return CredentialCheck(False, f"ASF Earthdata connection failed: HTTP {status}.")
    except Exception as exc:
        return CredentialCheck(False, f"ASF Earthdata connection failed: {exc}")
    return CredentialCheck(True, "ASF Earthdata connection succeeded.")


def test_network_endpoints(network: NetworkConfig | None = None) -> list[EndpointCheck]:
    """Check common ASF/Earthdata endpoints with the selected network policy."""

    network = network or NetworkConfig()
    session = network.session()
    timeout = network.timeout_seconds
    endpoints = [
        ("ASF Vertex", "https://search.asf.alaska.edu/"),
        ("NASA CMR", "https://cmr.earthdata.nasa.gov/search/collections.json?page_size=1"),
        ("Earthdata URS", "https://urs.earthdata.nasa.gov/"),
        ("ASF Datapool", "https://datapool.asf.alaska.edu/"),
    ]
    checks: list[EndpointCheck] = []
    for name, url in endpoints:
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            ok = response.status_code < 500
            message = f"HTTP {response.status_code}"
        except requests.exceptions.ProxyError as exc:
            ok = False
            message = f"proxy error: {exc}"
        except requests.exceptions.Timeout:
            ok = False
            message = f"timeout after {timeout:g}s"
        except Exception as exc:
            ok = False
            message = str(exc)
        checks.append(EndpointCheck(name=name, url=url, ok=ok, message=message))
    return checks


def save_earthdata_netrc(username: str, password: str, netrc_path: str | Path | None = None) -> Path:
    """Persist Earthdata credentials to a netrc file with owner-only permissions."""

    username = username.strip()
    if not username or not password:
        raise ValueError("ASF Earthdata username and password are required.")

    path = Path(netrc_path).expanduser() if netrc_path else Path.home() / ".netrc"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        tokens = line.strip().split()
        # Match the Earthdata block by its exact machine host, not a substring:
        # a loose ``"urs.earthdata.nasa.gov" in line`` would also clobber an
        # unrelated ``machine urs.earthdata.nasa.gov.evil.com`` entry.
        if len(tokens) >= 2 and tokens[0] == "machine" and tokens[1] == "urs.earthdata.nasa.gov":
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("machine "):
                index += 1
            continue
        output.append(line)
        index += 1

    if output and output[-1].strip():
        output.append("")
    output.extend(
        [
            "machine urs.earthdata.nasa.gov",
            f"  login {username}",
            f"  password {password}",
        ]
    )
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path
