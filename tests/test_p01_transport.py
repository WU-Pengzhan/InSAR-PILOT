"""Real aria2 process against an isolated local HTTP fixture."""

from __future__ import annotations

import hashlib
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from test_p01_acquisition import SCENE, safe_bytes, scene

from insar_pilot.download.download_service import DownloadService
from insar_pilot.download.integrity import receipt_path
from insar_pilot.download.network import NetworkConfig


def test_real_aria2_replaces_invalid_source_and_reuses_validated_zip(tmp_path, monkeypatch):
    binary = shutil.which("aria2c") or "/home/griffin/miniconda3/envs/insar/bin/aria2c"
    if not Path(binary).is_file():
        pytest.skip("aria2c is unavailable")
    payload = safe_bytes()
    etag = '"' + hashlib.sha256(payload).hexdigest() + '"'

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Content-Type", "application/zip")
            self.send_header("ETag", etag)
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        original = shutil.which
        monkeypatch.setattr(
            "insar_pilot.download.download_service.shutil.which",
            lambda name: binary if name == "aria2c" else original(name),
        )
        service = DownloadService(max_retries=0)
        task = service.create_tasks([scene()], tmp_path, include_orbits=False)[0]
        task = task.with_updates(url=f"http://127.0.0.1:{server.server_port}/{SCENE}.zip")
        final = Path(task.local_path)
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_bytes(b"invalid")
        events = []
        with NetworkConfig().session() as session:
            result = service._download_slc(task, session, NetworkConfig(), events.append, None)
            assert result.status == "completed", result.message
            assert final.read_bytes() == payload
            assert receipt_path(final).is_file()
            assert list(final.parent.glob(".invalid/*/" + final.name))
            again = service._download_slc(task, session, NetworkConfig(), None, None)
            assert again.status == "skipped"
        assert any(t.status == "validating" for t in events)
        assert all(t.bytes_done <= len(payload) for t in events)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
