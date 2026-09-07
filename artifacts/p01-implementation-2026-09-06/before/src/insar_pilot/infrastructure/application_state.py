"""Local application registry and shared input library catalog."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from insar_pilot.domain.engine import canonical, digest, new_id, utc_now
from insar_pilot.infrastructure.engine_store import ConflictError, EngineStore, file_snapshot


class ApplicationState:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects(project_id TEXT PRIMARY KEY,path TEXT UNIQUE,opened_at TEXT);
                CREATE TABLE IF NOT EXISTS library(asset_id TEXT PRIMARY KEY,source_key TEXT UNIQUE,body TEXT);
                CREATE TABLE IF NOT EXISTS downloads(job_id TEXT PRIMARY KEY,body TEXT);
                CREATE TABLE IF NOT EXISTS download_controls(
                    job_id TEXT PRIMARY KEY,pause_requested INTEGER,continued_by TEXT);
                CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY,body TEXT);
                CREATE TABLE IF NOT EXISTS remote_products(product_id TEXT PRIMARY KEY,body TEXT);
            """)
        for name in ("Sentinel1", "NISAR", "Orbit", "DEM", "partial"):
            (self.root / "library" / name).mkdir(parents=True, exist_ok=True)
        with self.library_connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS library(asset_id TEXT PRIMARY KEY,source_key TEXT UNIQUE,body TEXT)")
            if db.execute("PRAGMA user_version").fetchone()[0] == 0:
                with self.connection() as old:
                    rows = old.execute("SELECT asset_id,source_key,body FROM library").fetchall()
                db.executemany("INSERT OR IGNORE INTO library VALUES(?,?,?)", rows)
                db.execute("PRAGMA user_version=1")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.root / "application.sqlite", timeout=30)
        db.execute("PRAGMA journal_mode=WAL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def register(self, store: EngineStore) -> dict[str, Any]:
        project = store.project()
        with self.connection() as db:
            db.execute(
                "INSERT INTO projects VALUES(?,?,?) ON CONFLICT(project_id) "
                "DO UPDATE SET path=excluded.path,opened_at=excluded.opened_at",
                (project["project_id"], str(store.root), utc_now()),
            )
        return project

    @contextmanager
    def library_connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.root / "library" / "library.sqlite", timeout=30)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def project(self, project_id: str) -> EngineStore:
        with self.connection() as db:
            row = db.execute("SELECT path FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if not row:
            raise KeyError(project_id)
        return EngineStore(row[0])

    def recent(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT project_id,path,opened_at FROM projects ORDER BY opened_at DESC").fetchall()
        result = []
        for pid, path, opened in rows:
            try:
                result.append({**EngineStore(path).project(), "path": path, "opened_at": opened, "available": True})
            except (OSError, ValueError):
                result.append({"project_id": pid, "path": path, "name": Path(path).name, "available": False})
        return result

    def library_register(self, path: str, metadata: dict[str, Any]) -> dict[str, Any]:
        source = Path(path).expanduser().resolve(strict=True)
        observation = file_snapshot(source)
        key = digest({"path": str(source), "snapshot": observation})
        with self.library_connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT body FROM library WHERE source_key=?", (key,)).fetchone()
            if existing:
                return dict(json.loads(existing[0]))
            body = {
                "asset_id": new_id(),
                "path": str(source),
                "snapshot": observation,
                "metadata": metadata,
                "created_at": utc_now(),
                "fingerprint_kind": "stat",
            }
            db.execute("INSERT INTO library VALUES(?,?,?)", (body["asset_id"], key, canonical(body)))
            return body

    def library(self) -> list[dict[str, Any]]:
        with self.library_connection() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT body FROM library ORDER BY rowid DESC")]

    def save_search(self, groups: list[dict[str, Any]]) -> None:
        with self.connection() as db:
            for group in groups:
                for product in (group.get("page") or {}).get("items", []):
                    db.execute(
                        "INSERT OR REPLACE INTO remote_products VALUES(?,?)",
                        (product["remote_product_id"], canonical(product)),
                    )

    def remote(self, product_id: str) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute("SELECT body FROM remote_products WHERE product_id=?", (product_id,)).fetchone()
        if row is None:
            raise KeyError(product_id)
        return dict(json.loads(row[0]))

    def save_download(self, job: dict[str, Any]) -> None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT body FROM downloads WHERE job_id=?", (job["job_id"],)).fetchone()
            if previous:
                stored = json.loads(previous[0])
                job = {**job, "cancel_requested": bool(stored.get("cancel_requested") or job.get("cancel_requested"))}
                if stored["status"] in {"SUCCESS", "FAILED", "CANCELLED"}:
                    return
            db.execute(
                "INSERT INTO downloads VALUES(?,?) ON CONFLICT(job_id) DO UPDATE SET body=excluded.body",
                (job["job_id"], canonical(job)),
            )

    def downloads(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            return [
                self._download_view(row)
                for row in db.execute(
                    "SELECT d.body,c.pause_requested,c.continued_by FROM downloads d "
                    "LEFT JOIN download_controls c ON c.job_id=d.job_id ORDER BY d.rowid DESC"
                )
            ]

    @staticmethod
    def _download_view(row: tuple[Any, ...]) -> dict[str, Any]:
        job = dict(json.loads(row[0]))
        job.update(pause_requested=bool(row[1]), continued_by=row[2])
        state = job["status"]
        if state in {"QUEUED", "RUNNING"} and job.get("cancel_requested"):
            state = "PAUSING" if job["pause_requested"] else "CANCELLING"
        elif state == "CANCELLED" and job["pause_requested"]:
            state = "PAUSED"
        job["display_status"] = "CONTINUED" if job["continued_by"] else state
        return job

    def download(self, job_id: str) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute(
                "SELECT d.body,c.pause_requested,c.continued_by FROM downloads d "
                "LEFT JOIN download_controls c ON c.job_id=d.job_id WHERE d.job_id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._download_view(row)

    def stop_download(self, job_id: str, *, pause: bool) -> bool:
        """Persist user intent separately, including for already-running legacy workers."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM downloads WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            job = json.loads(row[0])
            control = db.execute("SELECT continued_by FROM download_controls WHERE job_id=?", (job_id,)).fetchone()
            if (control and control[0]) or job["status"] not in {"QUEUED", "RUNNING", "CANCELLED"}:
                raise ConflictError("This download attempt has already finished.")
            if pause and job["status"] == "CANCELLED":
                raise ConflictError("A cancelled attempt cannot be paused; retry it instead.")
            needs_stop = job["status"] in {"QUEUED", "RUNNING"}
            job["cancel_requested"] = True
            db.execute("UPDATE downloads SET body=? WHERE job_id=?", (canonical(job), job_id))
            db.execute(
                "INSERT INTO download_controls VALUES(?,?,NULL) ON CONFLICT(job_id) "
                "DO UPDATE SET pause_requested=excluded.pause_requested",
                (job_id, int(pause)),
            )
        return needs_stop

    def continue_download(self, job_id: str, child: dict[str, Any], *, resume: bool) -> None:
        """Reserve exactly one continuation without rewriting a terminal attempt."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT d.body,c.pause_requested,c.continued_by FROM downloads d "
                "LEFT JOIN download_controls c ON c.job_id=d.job_id WHERE d.job_id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise KeyError(job_id)
            old = self._download_view(row)
            allowed = old["display_status"] == "PAUSED" if resume else old["display_status"] in {"FAILED", "CANCELLED"}
            if not allowed:
                raise ConflictError(
                    "Wait for the transfer to stop before continuing; an attempt can continue only once."
                )
            db.execute("INSERT INTO downloads VALUES(?,?)", (child["job_id"], canonical(child)))
            db.execute(
                "INSERT INTO download_controls VALUES(?,?,?) ON CONFLICT(job_id) "
                "DO UPDATE SET continued_by=excluded.continued_by",
                (job_id, int(old["pause_requested"]), child["job_id"]),
            )
