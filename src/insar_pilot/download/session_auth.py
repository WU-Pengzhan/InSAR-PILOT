"""ASF/Earthdata session creation and cookie authentication helpers.

Extracted from ``download_service`` so the SLC orchestrator stays focused on the
download loop. These functions mirror the ASF bulk-download authentication flow
(reusable cookie jar + Earthdata OAuth) and carry no Qt or task-state coupling.
"""

from __future__ import annotations

import base64
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asf_search as asf
import requests

from insar_pilot.download.network import NetworkConfig


def bulk_session(username: str = "", password: str = "", network: NetworkConfig | None = None) -> requests.Session:
    """Create a bulk-download style session with reusable ASF cookies."""

    network = network or NetworkConfig()
    if username.strip() and password:
        session = asf.ASFSession()
        mode = network.normalized_mode()
        if mode == "direct":
            session.trust_env = False
        elif mode == "environment":
            session.trust_env = True
        else:
            session.trust_env = False
            session.proxies.update(network.proxy_dict())
        session._earthdata_username = username.strip()
        session._earthdata_password = password
        session._asf_cookie_jar = session.cookies
        session.auth_with_creds(username.strip(), password)
        return cast(requests.Session, session)

    session = network.session()
    cookie_path = Path.home() / ".bulk_download_cookiejar.txt"
    cookie_jar = MozillaCookieJar(str(cookie_path))
    if cookie_path.exists():
        try:
            cookie_jar.load(ignore_discard=True, ignore_expires=True)
        except Exception:
            cookie_jar = MozillaCookieJar(str(cookie_path))
    session.cookies = cookie_jar  # type: ignore[assignment]
    session._earthdata_username = username.strip()  # type: ignore[attr-defined]
    session._earthdata_password = password  # type: ignore[attr-defined]
    session._asf_cookie_jar = cookie_jar  # type: ignore[attr-defined]
    if has_asf_cookie(cookie_jar) and cookie_is_valid(session, network):
        return session
    if username.strip() and password:
        obtain_asf_cookie(session, cookie_jar, username.strip(), password, network)
        return session
    return session


def has_asf_cookie(cookie_jar: MozillaCookieJar) -> bool:
    return any(cookie.name in {"asf-urs", "urs_user_already_logged", "urs-access-token"} for cookie in cookie_jar)


def cookie_is_valid(session: requests.Session, network: NetworkConfig) -> bool:
    try:
        response = session.head(
            "https://urs.earthdata.nasa.gov/profile",
            timeout=network.timeout_seconds,
            allow_redirects=True,
        )
    except Exception:
        return False
    return response.status_code in {200, 307}


def obtain_asf_cookie(
    session: requests.Session,
    cookie_jar: MozillaCookieJar,
    username: str,
    password: str,
    network: NetworkConfig,
    auth_url: str = "",
) -> None:
    """Authenticate like ASF bulk-download scripts and persist cookies."""

    if not auth_url:
        auth_url = (
            "https://urs.earthdata.nasa.gov/oauth/authorize"
            "?client_id=BO_n7nTIlMljdvU6kRRB3g"
            "&redirect_uri=https://auth.asf.alaska.edu/login"
            "&response_type=code&state="
        )
    auth_url = auth_url_with_app_type(auth_url)
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    response = session.get(
        auth_url,
        headers={"Authorization": f"Basic {token}"},
        timeout=network.timeout_seconds,
        allow_redirects=True,
    )
    response.raise_for_status()
    if not has_asf_cookie(cookie_jar):
        raise RuntimeError("Earthdata login succeeded but no ASF download cookie was returned.")
    cookie_jar.save(ignore_discard=True, ignore_expires=True)


def auth_url_with_app_type(auth_url: str) -> str:
    split = urlsplit(auth_url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.setdefault("app_type", "401")
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))
