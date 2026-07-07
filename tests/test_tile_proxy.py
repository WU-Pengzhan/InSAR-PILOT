"""Behavioral tests for the localhost Tianditu tile proxy."""

from __future__ import annotations

import requests

from insar_pilot.download.network import NetworkConfig
from insar_pilot.download.tile_proxy import TiandituTileProxy


class _FakeTileResponse:
    def __init__(self, *, status_code=200, content=b"\x89PNG", content_type="image/png") -> None:
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}


class _FakeTileSession:
    def __init__(self, response=None, *, error=None) -> None:
        self.headers: dict = {}
        self._response = response
        self._error = error
        self.urls: list[str] = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        if self._error:
            raise self._error
        return self._response


def _proxy_with_session(session) -> TiandituTileProxy:
    proxy = TiandituTileProxy(network=NetworkConfig(mode="direct"))
    proxy.session = session  # type: ignore[assignment]
    return proxy


def test_fetch_tile_rejects_unknown_layer():
    status, content_type, payload = _proxy_with_session(_FakeTileSession()).fetch_tile("bogus", 1, 2, 3)
    assert status == 404
    assert b"Unknown" in payload


def test_fetch_tile_requires_key_for_tianditu_layers():
    proxy = _proxy_with_session(_FakeTileSession())  # no key configured
    status, _, payload = proxy.fetch_tile("img", 1, 2, 3)
    assert status == 503
    assert b"key is not configured" in payload


def test_fetch_tile_returns_tianditu_image_when_key_present():
    session = _FakeTileSession(_FakeTileResponse(content=b"tiledata", content_type="image/jpeg"))
    proxy = _proxy_with_session(session)
    proxy.update_key("demo-key")

    status, content_type, payload = proxy.fetch_tile("img", 3, 4, 5)

    assert status == 200
    assert content_type == "image/jpeg"
    assert payload == b"tiledata"
    assert "img_w/wmts" in session.urls[0]
    assert "tk=demo-key" in session.urls[0]


def test_fetch_tile_esri_does_not_require_key():
    session = _FakeTileSession(_FakeTileResponse(content=b"esri", content_type="image/jpeg"))
    proxy = _proxy_with_session(session)

    status, _, payload = proxy.fetch_tile("esri_img", 3, 4, 5)

    assert status == 200
    assert payload == b"esri"
    assert "server.arcgisonline.com" in session.urls[0]


def test_fetch_tile_reports_bad_gateway_on_request_error():
    session = _FakeTileSession(error=requests.RequestException("boom"))
    proxy = _proxy_with_session(session)
    proxy.update_key("demo-key")

    status, _, payload = proxy.fetch_tile("img", 3, 4, 5)

    assert status == 502
    assert b"tile fetch failed" in payload
    # Both https and http schemes were attempted before giving up.
    assert len(session.urls) == 2


def test_esri_fetch_failure_reports_bad_gateway():
    session = _FakeTileSession(error=requests.RequestException("boom"))
    status, _, payload = _proxy_with_session(session).fetch_tile("esri_img", 3, 4, 5)
    assert status == 502
    assert b"Esri tile fetch failed" in payload


def test_start_exposes_localhost_base_url_and_serves_requests():
    proxy = TiandituTileProxy(network=NetworkConfig(mode="direct"))
    served: list[tuple] = []

    def _fake_fetch(layer, z, x, y):
        served.append((layer, z, x, y))
        return 200, "image/png", b"OKTILE"

    proxy.fetch_tile = _fake_fetch  # type: ignore[assignment]
    try:
        assert proxy.base_url == ""  # not started yet
        proxy.start()
        proxy.start()  # idempotent second call is a no-op
        base = proxy.base_url
        assert base.startswith("http://127.0.0.1:")

        response = requests.get(f"{base}/img/3/4/5", timeout=5)
        assert response.status_code == 200
        assert response.content == b"OKTILE"
        assert served == [("img", 3, 4, 5)]

        # A malformed path (wrong segment count) yields a 404 from the handler.
        bad = requests.get(f"{base.rsplit('/', 1)[0]}/notproxy/1/2", timeout=5)
        assert bad.status_code == 404
    finally:
        proxy.stop()

    assert proxy.base_url == ""


def test_write_payload_survives_broken_pipe():
    class _BrokenStream:
        def write(self, payload):
            raise BrokenPipeError("closed")

    assert TiandituTileProxy._write_payload(_BrokenStream(), b"x") is False

    class _OkStream:
        def __init__(self):
            self.data = b""

        def write(self, payload):
            self.data += payload

    ok = _OkStream()
    assert TiandituTileProxy._write_payload(ok, b"tile") is True
    assert ok.data == b"tile"
