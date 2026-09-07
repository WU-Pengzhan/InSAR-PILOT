"""Small path and metadata helpers shared by local readers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from insar_pilot.domain.local_data import AssetRef, LocalReaderError, ReaderErrorCode

_FRACTIONAL_SECOND = re.compile(
    r"(?P<prefix>T\d{2}:\d{2}:\d{2})\.(?P<fraction>\d+)(?P<suffix>Z|[+-]\d{2}:?\d{2})?$"
)


def local_path(source: AssetRef, reader_id: str) -> Path:
    """Resolve a local file URI without accepting remote resources."""

    parsed = urlparse(source.uri)
    if parsed.scheme not in {"", "file"}:
        raise LocalReaderError(
            ReaderErrorCode.UNSUPPORTED_FORMAT,
            f"Reader {reader_id} accepts local paths only: {source.uri}",
            source=source,
            reader_id=reader_id,
        )
    if parsed.scheme == "file" and parsed.netloc not in {"", "localhost"}:
        raise LocalReaderError(
            ReaderErrorCode.UNSUPPORTED_FORMAT,
            f"Reader {reader_id} does not accept remote file authorities: {parsed.netloc}",
            source=source,
            reader_id=reader_id,
        )
    value = unquote(parsed.path) if parsed.scheme else source.uri
    return Path(value).expanduser()


def utc_datetime(value: str, field_name: str, source: AssetRef, reader_id: str) -> datetime:
    """Parse product timestamps, treating timezone-less mission metadata as UTC."""

    text = value.strip()
    if not text:
        raise LocalReaderError(
            ReaderErrorCode.MISSING_METADATA,
            f"Required timestamp is missing: {field_name}",
            source=source,
            reader_id=reader_id,
        )
    # NISAR metadata commonly uses nanosecond precision while Python's
    # datetime stores microseconds.  Normalize only the seconds fraction so
    # timezone offsets remain intact.
    match = _FRACTIONAL_SECOND.search(text)
    if match and len(match.group("fraction")) > 6:
        text = (
            text[: match.start("fraction")]
            + match.group("fraction")[:6]
            + text[match.end("fraction") :]
        )
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise LocalReaderError(
            ReaderErrorCode.MISSING_METADATA,
            f"Invalid timestamp in {field_name}: {value}",
            source=source,
            reader_id=reader_id,
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


__all__ = ["local_path", "utc_datetime"]
