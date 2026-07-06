"""Local WMTS tile proxy for mainland-friendly basemap access."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import PurePosixPath
from typing import ClassVar
from urllib.parse import quote

import requests

from insar_pilot.download.network import NetworkConfig


class TiandituTileProxy:
    """Serve Tianditu tiles over localhost using server-side requests."""

    allowed_layers: ClassVar[set[str]] = {"img", "cia", "ter", "cta", "esri_img", "esri_topo"}

    def __init__(self, network: NetworkConfig | None = None) -> None:
        self.network = network or NetworkConfig(mode="direct")
        self.session = self.network.session()
        self.session.headers.update({"User-Agent": "ISCE2-GUI Tianditu Proxy/1.0"})
        self._key = ""
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the localhost tile proxy if it is not already running."""

        if self._server is not None:
            return
        server = ThreadingHTTPServer(("127.0.0.1", 0), self._make_handler())
        server.daemon_threads = True
        server.proxy = self  # type: ignore[attr-defined]
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, name="tianditu-tile-proxy", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the localhost tile proxy."""

        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None

    def update_key(self, key: str) -> None:
        """Update the Tianditu key used for upstream tile fetches."""

        self._key = key.strip()

    @property
    def base_url(self) -> str:
        """Return the localhost base URL for proxied tiles."""

        if self._server is None:
            return ""
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/tianditu"

    def upstream_url(self, layer: str, z: int, x: int, y: int, *, scheme: str = "https") -> str:
        """Build one upstream Tianditu WMTS URL."""

        if layer == "esri_img":
            return f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        if layer == "esri_topo":
            return f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"
        return (
            f"{scheme}://t0.tianditu.gov.cn/{quote(layer)}_w/wmts?"
            "SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
            f"&LAYER={quote(layer)}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles"
            f"&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk={quote(self._key)}"
        )

    def fetch_tile(self, layer: str, z: int, x: int, y: int) -> tuple[int, str, bytes]:
        """Fetch one tile from Tianditu using direct server-side requests."""

        if layer not in self.allowed_layers:
            return 404, "text/plain; charset=utf-8", b"Unknown Tianditu layer."
        if layer in {"img", "cia", "ter", "cta"} and not self._key:
            return 503, "text/plain; charset=utf-8", b"Tianditu key is not configured."

        timeout = self.network.timeout_seconds
        if layer in {"esri_img", "esri_topo"}:
            try:
                response = self.session.get(self.upstream_url(layer, z, x, y), timeout=timeout)
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "image/jpeg")
                    return 200, content_type, response.content
            except requests.RequestException:
                pass
            return 502, "text/plain; charset=utf-8", b"Esri tile fetch failed."

        for scheme in ("https", "http"):
            try:
                response = self.session.get(self.upstream_url(layer, z, x, y, scheme=scheme), timeout=timeout)
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "image/jpeg")
                    return 200, content_type, response.content
            except requests.RequestException:
                continue
        return 502, "text/plain; charset=utf-8", b"Tianditu tile fetch failed."

    def _make_handler(self):
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                path = PurePosixPath(self.path.split("?", 1)[0])
                parts = path.parts
                if len(parts) != 6 or parts[1] != "tianditu":
                    self.send_error(404)
                    return
                _, _, layer, z_text, x_text, y_text = parts
                try:
                    z = int(z_text)
                    x = int(x_text)
                    y = int(y_text)
                except ValueError:
                    self.send_error(400)
                    return
                status, content_type, payload = proxy.fetch_tile(layer, z, x, y)
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                proxy._write_payload(self.wfile, payload)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        return Handler

    @staticmethod
    def _write_payload(stream, payload: bytes) -> bool:
        """Write a tile response unless the client already closed the socket."""

        try:
            stream.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return False
        return True
