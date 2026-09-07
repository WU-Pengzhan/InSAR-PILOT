"""Behavioral tests for ASF/Earthdata session + cookie authentication helpers."""

from __future__ import annotations

import base64
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import pytest
from requests.cookies import RequestsCookieJar, create_cookie

from insar_pilot.download import session_auth
from insar_pilot.download.network import NetworkConfig


def _asf_cookie(jar) -> None:
    jar.set_cookie(create_cookie(name="asf-urs", value="token", domain=".asf.alaska.edu"))


class _FakeResponse:
    def __init__(self, status_code: int = 200, url: str = "https://example.test") -> None:
        self.status_code = status_code
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _RecordingSession:
    def __init__(self, response: _FakeResponse | None = None, *, head_error: bool = False) -> None:
        self._response = response or _FakeResponse()
        self._head_error = head_error
        self.get_calls: list[dict] = []
        self.head_calls: list[str] = []

    def get(self, url, headers=None, timeout=None, allow_redirects=None):
        self.get_calls.append({"url": url, "headers": headers or {}})
        return self._response

    def head(self, url, timeout=None, allow_redirects=None):
        self.head_calls.append(url)
        if self._head_error:
            raise RuntimeError("network down")
        return self._response


def test_auth_url_with_app_type_adds_app_type_query() -> None:
    url = session_auth.auth_url_with_app_type("https://urs.earthdata.nasa.gov/oauth/authorize?client_id=abc")
    assert "app_type=401" in url
    assert "client_id=abc" in url
    # Existing app_type is preserved (setdefault, not overwrite).
    kept = session_auth.auth_url_with_app_type("https://x.test/a?app_type=200")
    assert "app_type=200" in kept
    assert "app_type=401" not in kept


def test_has_asf_cookie_detects_known_cookie_names() -> None:
    jar = MozillaCookieJar()
    assert session_auth.has_asf_cookie(jar) is False
    _asf_cookie(jar)
    assert session_auth.has_asf_cookie(jar) is True


def test_cookie_is_valid_accepts_200_and_307_and_swallows_errors() -> None:
    network = NetworkConfig()
    assert session_auth.cookie_is_valid(_RecordingSession(_FakeResponse(200)), network) is True
    assert session_auth.cookie_is_valid(_RecordingSession(_FakeResponse(307)), network) is True
    assert session_auth.cookie_is_valid(_RecordingSession(_FakeResponse(500)), network) is False
    assert session_auth.cookie_is_valid(_RecordingSession(head_error=True), network) is False


def test_obtain_asf_cookie_sends_basic_auth_and_persists_file_backed_jar(tmp_path: Path) -> None:
    cookie_path = tmp_path / "cookies.txt"
    jar = MozillaCookieJar(str(cookie_path))
    _asf_cookie(jar)
    session = _RecordingSession(_FakeResponse(200))

    session_auth.obtain_asf_cookie(session, jar, "alice", "secret", NetworkConfig())

    # Basic auth header carried the base64(user:pass) token.
    sent = session.get_calls[0]["headers"]["Authorization"]
    expected = base64.b64encode(b"alice:secret").decode("ascii")
    assert sent == f"Basic {expected}"
    # app_type appended to the default authorize URL.
    assert "app_type=401" in session.get_calls[0]["url"]
    # File-backed jar was persisted to disk.
    assert cookie_path.exists()


def test_obtain_asf_cookie_raises_when_no_cookie_returned(tmp_path: Path) -> None:
    jar = MozillaCookieJar(str(tmp_path / "cookies.txt"))  # empty -> no asf cookie
    session = _RecordingSession(_FakeResponse(200))

    with pytest.raises(RuntimeError, match="no ASF download cookie"):
        session_auth.obtain_asf_cookie(session, jar, "alice", "secret", NetworkConfig())


def test_obtain_asf_cookie_tolerates_non_persistable_requests_jar() -> None:
    """Regression: the Earthdata reauth fallback can pass a RequestsCookieJar
    (session.cookies) which has no .save(); obtaining a cookie must not crash.

    On the pre-fix code this raised AttributeError: 'RequestsCookieJar' object
    has no attribute 'save'.
    """

    jar = RequestsCookieJar()
    _asf_cookie(jar)
    session = _RecordingSession(_FakeResponse(200))

    # Must complete without raising even though the jar cannot be saved to disk.
    session_auth.obtain_asf_cookie(session, jar, "alice", "secret", NetworkConfig())
    assert session.get_calls  # the login request was still issued


def test_bulk_session_reuses_existing_valid_cookie_jar(tmp_path: Path, monkeypatch) -> None:
    # Point HOME at tmp so the real ~/.bulk_download_cookiejar.txt is not touched.
    monkeypatch.setenv("HOME", str(tmp_path))
    cookie_path = tmp_path / ".bulk_download_cookiejar.txt"
    jar = MozillaCookieJar(str(cookie_path))
    _asf_cookie(jar)
    jar.save(ignore_discard=True, ignore_expires=True)

    fake = _RecordingSession(_FakeResponse(200))

    class _FakeNetwork:
        timeout_seconds = 5.0

        def session(self):
            return fake

    session = session_auth.bulk_session(network=_FakeNetwork())

    # A valid pre-existing cookie short-circuits: the session is returned with
    # its earthdata attributes populated and a HEAD validation was performed.
    assert session is fake
    assert fake.head_calls  # cookie validity was checked
    assert getattr(session, "_asf_cookie_jar", None) is not None
