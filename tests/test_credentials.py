"""Behavioral tests for Earthdata credential loading and connectivity checks."""

from __future__ import annotations

from pathlib import Path

import requests

from insar_pilot.download.credentials import (
    load_earthdata_credentials,
    save_earthdata_netrc,
)
from insar_pilot.download.credentials import (
    test_earthdata_connection as check_earthdata_connection,
)
from insar_pilot.download.credentials import (
    test_network_endpoints as check_network_endpoints,
)


class _FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            error.response = self  # type: ignore[assignment]
            raise error


class _FakeSession:
    """A session whose post/get either return a response or raise a set error."""

    def __init__(self, *, response: _FakeResponse | None = None, error: Exception | None = None) -> None:
        self._response = response or _FakeResponse()
        self._error = error

    def post(self, url, auth=None, timeout=None):
        if self._error:
            raise self._error
        return self._response

    def get(self, url, timeout=None, allow_redirects=None):
        if self._error:
            raise self._error
        return self._response


class _FakeNetwork:
    timeout_seconds = 5.0

    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def session(self) -> _FakeSession:
        return self._session


def test_load_earthdata_credentials_prefers_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EARTHDATA_USERNAME", "env_user")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "env_pass")

    creds = load_earthdata_credentials(tmp_path / ".netrc")

    assert creds is not None
    assert creds.username == "env_user"
    assert creds.source == "environment"


def test_load_earthdata_credentials_returns_none_when_netrc_missing(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)

    assert load_earthdata_credentials(tmp_path / "absent.netrc") is None


def test_load_earthdata_credentials_returns_none_for_unrelated_netrc(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    path = tmp_path / ".netrc"
    path.write_text("machine example.com\n  login x\n  password y\n", encoding="utf-8")

    assert load_earthdata_credentials(path) is None


def test_earthdata_connection_requires_username_and_password():
    result = check_earthdata_connection("", "secret")
    assert result.ok is False
    assert "required" in result.message


def test_earthdata_connection_success():
    network = _FakeNetwork(_FakeSession(response=_FakeResponse(200)))
    result = check_earthdata_connection("alice", "secret", network=network)
    assert result.ok is True
    assert "succeeded" in result.message


def test_earthdata_connection_rejects_bad_credentials():
    network = _FakeNetwork(_FakeSession(response=_FakeResponse(401)))
    result = check_earthdata_connection("alice", "wrong", network=network)
    assert result.ok is False
    assert "rejected" in result.message


def test_earthdata_connection_reports_timeout():
    network = _FakeNetwork(_FakeSession(error=requests.exceptions.Timeout()))
    result = check_earthdata_connection("alice", "secret", network=network, timeout=3)
    assert result.ok is False
    assert "timed out" in result.message


def test_earthdata_connection_reports_proxy_error():
    network = _FakeNetwork(_FakeSession(error=requests.exceptions.ProxyError("no proxy")))
    result = check_earthdata_connection("alice", "secret", network=network)
    assert result.ok is False
    assert "proxy is not reachable" in result.message


def test_network_endpoints_reports_status_and_errors():
    ok_network = _FakeNetwork(_FakeSession(response=_FakeResponse(200)))
    checks = check_network_endpoints(network=ok_network)
    assert len(checks) == 4
    assert all(check.ok for check in checks)
    assert checks[0].message == "HTTP 200"

    timeout_network = _FakeNetwork(_FakeSession(error=requests.exceptions.Timeout()))
    timed_out = check_network_endpoints(network=timeout_network)
    assert all(not check.ok for check in timed_out)
    assert "timeout" in timed_out[0].message


def test_network_endpoints_marks_5xx_as_down():
    network = _FakeNetwork(_FakeSession(response=_FakeResponse(503)))
    checks = check_network_endpoints(network=network)
    assert all(not check.ok for check in checks)
    assert checks[0].message == "HTTP 503"


def test_save_earthdata_netrc_replaces_existing_machine_block(tmp_path: Path):
    path = tmp_path / ".netrc"
    path.write_text(
        "machine example.com\n  login keep\n  password kept\n"
        "machine urs.earthdata.nasa.gov\n  login old\n  password stale\n",
        encoding="utf-8",
    )

    save_earthdata_netrc("newuser", "newpass", path)

    text = path.read_text(encoding="utf-8")
    assert "login newuser" in text
    assert "password newpass" in text
    assert "old" not in text
    assert "stale" not in text
    # The unrelated machine entry is preserved.
    assert "machine example.com" in text
    assert "login keep" in text
    # Only one earthdata machine block remains.
    assert text.count("machine urs.earthdata.nasa.gov") == 1
