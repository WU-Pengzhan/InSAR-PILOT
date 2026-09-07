"""Read-only project entry recognition, independent of the Web and Qt interfaces."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from insar_pilot.domain.engine import Profile, digest, validate_public_snapshot
from insar_pilot.infrastructure.project_codec import UnsupportedProjectEncoding, read_project_document

FORMAT = "insar-pilot-web"


def project_filename(name: str) -> str:
    """Use a portable single path component; never silently sanitize user names."""
    name = name.strip()
    if not name or name in {".", ".."} or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        raise ValueError("Project name must be a valid file name without path separators.")
    if (
        name.endswith((".", " "))
        or name.split(".")[0].upper()
        in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
        or len((name + ".pilot").encode("utf-8")) > 240
    ):
        raise ValueError("Project name is not portable or is too long.")
    return name + ".pilot"


def resolve_project_file(path: str | Path) -> Path:
    source = Path(path).expanduser().resolve()
    if source.is_dir():
        candidates = [p for p in source.iterdir() if p.is_file() and p.suffix.lower() == ".pilot"]
        if len(candidates) != 1:
            raise ValueError("Select the unique .pilot file; the directory has no entry or has multiple entries.")
        source = candidates[0]
    if source.suffix.lower() != ".pilot":
        raise ValueError("Select a .pilot project file.")
    if not source.is_file():
        raise FileNotFoundError("Project file is missing.")
    # A second marker can cause later directory-based workers to open a different file.
    if len([p for p in source.parent.iterdir() if p.is_file() and p.suffix.lower() == ".pilot"]) != 1:
        raise ValueError("Multiple .pilot entries in one project directory; resolve the duplicate first.")
    return source


def validate_header(body: Any) -> None:
    if not isinstance(body, dict) or type(body.get("schema_version")) is not int or body["schema_version"] != 2:
        raise ValueError("Unsupported Web project schema.")
    if body.get("format", FORMAT) != FORMAT:
        raise ValueError("Unsupported project format.")
    for key in ("project_id", "name", "profile"):
        if not isinstance(body.get(key), str) or not body[key].strip():
            raise ValueError(f"Invalid project field: {key}.")
    if type(body.get("revision")) is not int or body["revision"] < 1:
        raise ValueError("Invalid project revision.")
    if type(body.get("profile_locked")) is not bool:
        raise ValueError("Invalid profile lock.")
    for key, kind in (("datasets", list), ("pipelines", dict), ("settings", dict)):
        if not isinstance(body.get(key), kind):
            raise ValueError(f"Invalid project field: {key}.")
    if "aoi" not in body or (body["aoi"] is not None and not isinstance(body["aoi"], dict)):
        raise ValueError("Invalid project AOI.")
    if type(body.get("storage_layout_version", 1)) is not int or body.get("storage_layout_version", 1) not in (1, 2):
        raise ValueError("Unsupported project storage layout.")
    Profile(body["profile"])
    validate_public_snapshot(body)


def inspect_project(path: str | Path, *, include_definition: bool = False) -> dict[str, Any]:
    """Never initialize a DB, register a project, or recover pending revisions here."""
    result: dict[str, Any] = {"status": "invalid", "message": "", "project_file": str(path)}
    try:
        entry = resolve_project_file(path)
        result.update(project_file=str(entry), root=str(entry.parent))
        body = read_project_document(entry)
        if not isinstance(body, dict):
            raise ValueError("Project file must be a JSON object.")
        if (
            "format" not in body
            and "project_id" not in body
            and any(isinstance(body.get(k), dict) for k in ("workspace", "workflow", "download"))
        ):
            from insar_pilot.services.project_store import ProjectStore

            ProjectStore().load(entry)
            result.update(
                status="legacy",
                message="Import this desktop project into a new directory.",
                name=body.get("name") or entry.stem,
            )
            return result
        if body.get("format", FORMAT) != FORMAT or body.get("schema_version") != 2:
            result.update(status="unsupported", message="Unsupported project format or version.")
            return result
        validate_header(body)
        result.update({k: body[k] for k in ("project_id", "name", "profile", "schema_version", "revision")})
        db_path = entry.parent / ".insar_pilot" / "state.sqlite"
        if not db_path.is_file():
            result.update(status="incomplete", message="The companion project database is missing.")
            return result
        with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)) as db:
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                result.update(status="unsupported", message="Unsupported project database version.")
                return result
            row = db.execute("SELECT body FROM project WHERE id=1").fetchone()
            if not row:
                raise ValueError("Project database has no project definition.")
            accepted = json.loads(row[0])
            validate_header(accepted)
            if accepted["project_id"] != body["project_id"]:
                result.update(status="conflict", message="Project file and database identities differ.")
                return result
            pending_row = db.execute("SELECT body FROM pending_revision WHERE id=1").fetchone()
            pending = json.loads(pending_row[0]) if pending_row else None
            if pending is not None:
                validate_header(pending)
                if pending["project_id"] != accepted["project_id"] or pending["revision"] != accepted["revision"] + 1:
                    raise ValueError("Invalid pending project revision.")
                if pending.get("storage_layout_version", 1) != accepted.get("storage_layout_version", 1):
                    raise ValueError("Pending revision cannot change storage layout.")
                if pending.get("format") != accepted.get("format") or (
                    accepted["profile_locked"]
                    and (not pending["profile_locked"] or pending["profile"] != accepted["profile"])
                ):
                    raise ValueError("Pending revision cannot change format or unlock the profile.")
            if digest(body) != digest(accepted) and (pending is None or digest(body) != digest(pending)):
                result.update(status="modified", message="External edits need explicit validation and import.")
                return result
        result.update(status="ready", message="Project is ready to open.")
        if include_definition:
            result["definition"] = body
    except UnsupportedProjectEncoding as exc:
        result.update(status="unsupported", message=str(exc))
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        result.update(status="invalid", message=str(exc))
    return result
