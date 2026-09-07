"""Versioned binary envelope for project intent (not encryption).

The bounded JSON payload remains data, never executable serialization.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import struct
import zlib
from pathlib import Path
from typing import Any

from insar_pilot.domain.engine import canonical

MAGIC = b"\x89PILOT\r\n\x1a\n"
VERSION = 1
HEADER = struct.Struct(">10sBI32s")
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_FILE_BYTES = 9 * 1024 * 1024


class UnsupportedProjectEncoding(ValueError):
    """A newer container needs a compatible application."""


def encode_project_document(body: dict[str, Any]) -> bytes:
    raw = canonical(body).encode("utf-8")
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError("Project description exceeds 8 MiB.")
    return HEADER.pack(MAGIC, VERSION, len(raw), hashlib.sha256(raw).digest()) + zlib.compress(raw)


def decode_project_document(data: bytes) -> dict[str, Any]:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Project file exceeds its size limit.")
    if data.startswith(MAGIC):
        if len(data) < HEADER.size:
            raise ValueError("Project file header is truncated.")
        _, version, size, checksum = HEADER.unpack(data[: HEADER.size])
        if version != VERSION:
            raise UnsupportedProjectEncoding("Unsupported .pilot container version.")
        if size > MAX_DOCUMENT_BYTES:
            raise ValueError("Project description exceeds 8 MiB.")
        try:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(data[HEADER.size :], MAX_DOCUMENT_BYTES + 1)
        except zlib.error as exc:
            raise ValueError("Project payload is damaged.") from exc
        if (
            len(raw) != size
            or len(raw) > MAX_DOCUMENT_BYTES
            or not decoder.eof
            or decoder.unused_data
            or decoder.unconsumed_tail
        ):
            raise ValueError("Project payload size or stream is invalid.")
        if not hmac.compare_digest(hashlib.sha256(raw).digest(), checksum):
            raise ValueError("Project integrity check failed.")
    else:
        # Existing Web/desktop JSON entries are readable, never rewritten on open.
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ValueError("Project description exceeds 8 MiB.")
        raw = data
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError("Not a readable .pilot project document.") from exc
    if not isinstance(body, dict):
        raise ValueError("Project document must contain an object.")
    return body


def read_project_document(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return decode_project_document(stream.read(MAX_FILE_BYTES + 1))
