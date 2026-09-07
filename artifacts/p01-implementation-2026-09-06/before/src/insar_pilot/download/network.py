"""Network configuration for ASF search, authentication, and downloads."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class NetworkConfig:
    """Explicit network policy for remote ASF/Earthdata calls."""

    mode: str = "direct"
    http_proxy: str = ""
    https_proxy: str = ""
    timeout_seconds: float = 20.0

    def normalized_mode(self) -> str:
        """Return a known connection mode."""

        mode = self.mode.strip().lower().replace(" ", "_")
        return mode if mode in {"direct", "environment", "manual"} else "direct"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> NetworkConfig:
        """Build network config from persisted JSON data."""

        data = dict(payload)
        data.setdefault("mode", "direct")
        data.setdefault("http_proxy", "")
        data.setdefault("https_proxy", "")
        data.setdefault("timeout_seconds", 20.0)
        data["timeout_seconds"] = float(data["timeout_seconds"] or 20.0)
        return cls(**data)

    def proxy_dict(self) -> dict[str, str]:
        """Return requests-compatible proxies for manual mode."""

        if self.normalized_mode() != "manual":
            return {}
        proxies: dict[str, str] = {}
        if self.http_proxy.strip():
            proxies["http"] = self.http_proxy.strip()
        if self.https_proxy.strip():
            proxies["https"] = self.https_proxy.strip()
        return proxies

    def session(self) -> requests.Session:
        """Create a requests session honoring this network policy."""

        session = requests.Session()
        mode = self.normalized_mode()
        if mode == "direct":
            session.trust_env = False
        elif mode == "environment":
            session.trust_env = True
        else:
            session.trust_env = False
            session.proxies.update(self.proxy_dict())
        return session

    def describe(self) -> str:
        """Return a short user-facing description."""

        mode = self.normalized_mode()
        if mode == "direct":
            return "Direct connection; environment proxy variables are ignored."
        if mode == "environment":
            env = {
                key: value
                for key, value in os.environ.items()
                if key.lower() in {"http_proxy", "https_proxy", "all_proxy"}
            }
            return f"Using environment proxy settings: {env or 'none set'}."
        proxies = self.proxy_dict()
        return f"Using manual proxy settings: {proxies or 'none set'}."
