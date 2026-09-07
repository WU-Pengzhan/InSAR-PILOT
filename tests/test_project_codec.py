"""Binary project packaging, bounded decoding and crash-safe migration."""

import hashlib
import json
import zlib

import pytest

from insar_pilot.domain.engine import canonical
from insar_pilot.infrastructure.engine_store import EngineStore, atomic_json
from insar_pilot.infrastructure.project_codec import (
    HEADER,
    MAGIC,
    MAX_DOCUMENT_BYTES,
    VERSION,
    UnsupportedProjectEncoding,
    decode_project_document,
    encode_project_document,
    read_project_document,
)
from insar_pilot.infrastructure.project_file import inspect_project


def test_new_project_is_binary_and_roundtrips_unicode(tmp_path):
    store = EngineStore.create(tmp_path / "项目", "研究 空格", filename="研究.pilot")
    data = store.project_file.read_bytes()
    assert data.startswith(MAGIC)
    with pytest.raises((UnicodeError, ValueError)):
        json.loads(data)
    assert "研究".encode() not in data
    assert read_project_document(store.project_file) == store.project()
    store.revise(1, name="新名称")
    assert store.project_file.read_bytes().startswith(MAGIC)
    assert inspect_project(store.project_file)["status"] == "ready"


def test_plain_web_entry_is_read_only_on_open_and_packed_on_save(tmp_path):
    store = EngineStore.create(tmp_path / "old", "Old")
    body = store.project()
    body.pop("format")
    atomic_json(store.project_file, body)
    with store.connection() as db:
        db.execute("UPDATE project SET body=?", (canonical(body),))
    original = store.project_file.read_bytes()
    reopened = EngineStore(store.project_file)
    assert reopened.project_file.read_bytes() == original
    assert reopened.project()["project_id"] == body["project_id"]
    reopened.revise(1, name="Saved")
    assert reopened.project_file.read_bytes().startswith(MAGIC)
    assert read_project_document(reopened.project_file)["project_id"] == body["project_id"]
    assert "format" not in read_project_document(reopened.project_file)


@pytest.mark.parametrize("corruption", ["header", "payload", "checksum", "size", "trailing", "magic"])
def test_damaged_container_is_rejected(corruption):
    data = bytearray(encode_project_document({"name": "science"}))
    if corruption == "header":
        data = data[:12]
    elif corruption == "payload":
        data = data[:-3]
    elif corruption == "checksum":
        data[HEADER.size - 1] ^= 1
    elif corruption == "size":
        data[14] ^= 1
    elif corruption == "trailing":
        data += b"extra"
    else:
        data[1] ^= 1
    with pytest.raises(ValueError):
        decode_project_document(bytes(data))


def test_unknown_container_version_and_expansion_limits(tmp_path):
    valid = encode_project_document({"name": "test"})
    modified = valid[: len(MAGIC)] + b"\x02" + valid[len(MAGIC) + 1 :]
    with pytest.raises(UnsupportedProjectEncoding):
        decode_project_document(modified)
    path = tmp_path / "future.pilot"
    path.write_bytes(modified)
    assert inspect_project(path)["status"] == "unsupported"
    raw = b"x" * (MAX_DOCUMENT_BYTES + 1)
    compressed = zlib.compress(raw)
    # A false small header cannot bypass the decompression limit.
    with pytest.raises(ValueError):
        decode_project_document(HEADER.pack(MAGIC, VERSION, 1, hashlib.sha256(raw).digest()) + compressed)
    with pytest.raises(ValueError):
        encode_project_document({"too_big": "x" * MAX_DOCUMENT_BYTES})


def test_failed_replacement_preserves_original_and_aborts_pending(tmp_path, monkeypatch):
    store = EngineStore.create(tmp_path / "atomic", "Atomic")
    original = store.project_file.read_bytes()
    with monkeypatch.context() as patch:

        def fail(*args):
            raise OSError("simulated replacement failure")

        patch.setattr("insar_pilot.infrastructure.engine_store.os.replace", fail)
        with pytest.raises(OSError):
            store.revise(1, name="Uncommitted")
    assert store.project_file.read_bytes() == original
    assert EngineStore(store.root).project()["revision"] == 1
    assert not list(store.root.glob(".*.pilot.*"))
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM pending_revision").fetchone()[0] == 0


def test_binary_file_published_before_database_commit_recovers(tmp_path, monkeypatch):
    store = EngineStore.create(tmp_path / "recover", "Recover", filename="named.pilot")
    with monkeypatch.context() as patch:

        def fail(*args):
            raise OSError("simulated commit failure")

        patch.setattr(EngineStore, "_commit_revision", staticmethod(fail))
        with pytest.raises(OSError):
            store.revise(1, name="Recovered")
    assert store.project()["revision"] == 1
    assert read_project_document(store.project_file)["revision"] == 2
    reopened = EngineStore(store.root)
    assert reopened.project()["name"] == "Recovered"
    assert reopened.events()[-1]["event_type"] == "project.revised"
    assert not (store.root / "project.pilot").exists()
