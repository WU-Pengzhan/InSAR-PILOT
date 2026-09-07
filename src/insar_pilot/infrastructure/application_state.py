"""Local application registry and shared input library catalog."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

from insar_pilot.domain.engine import canonical, digest, new_id, utc_now
from insar_pilot.infrastructure.engine_store import ConflictError, EngineStore, file_snapshot
from insar_pilot.infrastructure.project_file import inspect_project


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
                CREATE TABLE IF NOT EXISTS remote_products_v2(product_key TEXT PRIMARY KEY,product_id TEXT,body TEXT);
                CREATE TABLE IF NOT EXISTS acquisition_plans(plan_id TEXT PRIMARY KEY,body TEXT);
                CREATE TABLE IF NOT EXISTS acquisition_submissions(
                    request_key TEXT PRIMARY KEY,signature TEXT,body TEXT);
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
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT path FROM projects WHERE project_id=?", (project["project_id"],)).fetchone()
            if old and Path(old[0]).resolve() != store.root:
                raise ConflictError(
                    "This project ID is registered at another location; use a separate migration or copy workflow."
                )
            occupied = db.execute("SELECT project_id FROM projects WHERE path=?", (str(store.root),)).fetchone()
            if occupied and occupied[0] != project["project_id"]:
                raise ConflictError("This location is registered to another project identity.")
            db.execute(
                "INSERT INTO projects VALUES(?,?,?) ON CONFLICT(project_id) "
                "DO UPDATE SET path=excluded.path,opened_at=excluded.opened_at",
                (project["project_id"], str(store.root), utc_now()),
            )
        return {**project, "project_file": str(store.project_file), "path": str(store.root)}

    def open_project(self, path: str | Path) -> dict[str, Any]:
        info = inspect_project(path)
        if info["status"] != "ready":
            raise ValueError(info["message"])
        with self.connection() as db:
            old = db.execute("SELECT path FROM projects WHERE project_id=?", (info["project_id"],)).fetchone()
        if old and Path(old[0]).resolve() != Path(info["root"]):
            raise ConflictError(
                "This project ID is registered at another location; use a separate migration or copy workflow."
            )
        return self.register(EngineStore(info["project_file"]))

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
        store = EngineStore(row[0])
        if store.project()["project_id"] != project_id:
            raise ConflictError("The registered location now belongs to a different project.")
        return store

    def recent(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT project_id,path,opened_at FROM projects ORDER BY opened_at DESC").fetchall()
        result = []
        for pid, path, opened in rows:
            info = inspect_project(path, include_definition=True)
            definition = info.pop("definition", {})
            available = info["status"] == "ready" and info.get("project_id") == pid
            active_jobs = None
            if available:
                try:
                    db_path = Path(path) / ".insar_pilot/state.sqlite"
                    with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)) as project_db:
                        active_jobs = project_db.execute(
                            "SELECT COUNT(*) FROM jobs WHERE json_extract(body,'$.status') IN ('QUEUED','RUNNING')"
                        ).fetchone()[0]
                except sqlite3.Error:
                    pass
            result.append(
                {
                    **definition,
                    "active_jobs": active_jobs,
                    **info,
                    "project_id": pid,
                    "path": path,
                    "name": info.get("name", Path(path).name),
                    "opened_at": opened,
                    "available": available,
                }
            )
        return result

    def library_register(self, path: str, metadata: dict[str, Any]) -> dict[str, Any]:
        source = Path(path).expanduser().resolve(strict=True)
        observation = file_snapshot(source)
        key = digest({"path": str(source), "snapshot": observation})
        with self.library_connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT body FROM library WHERE source_key=?", (key,)).fetchone()
            if existing:
                body = dict(json.loads(existing[0]))
                old = body["metadata"]
                keys = {
                    k for k in [old.get("product_key"), metadata.get("product_key"), *old.get("product_keys", [])] if k
                }
                # Keep the registered version and add associations/verified metadata.
                body["metadata"] = {**metadata, **old}
                if metadata.get("integrity"):
                    body["metadata"].update(integrity=metadata["integrity"], role=metadata.get("role"))
                body["metadata"]["product_keys"] = sorted(keys)
                db.execute("UPDATE library SET body=? WHERE source_key=?", (canonical(body), key))
                return body
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
                    key = digest({"provider": product["provider_id"], "product": product["remote_product_id"]})
                    product["product_key"] = key
                    db.execute(
                        "INSERT OR REPLACE INTO remote_products_v2 VALUES(?,?,?)",
                        (key, product["remote_product_id"], canonical(product)),
                    )
                    db.execute(
                        "INSERT OR REPLACE INTO remote_products VALUES(?,?)",
                        (product["remote_product_id"], canonical(product)),
                    )

    def remote(self, product_id: str) -> dict[str, Any]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT body FROM remote_products_v2 WHERE product_key=? OR product_id=?", (product_id, product_id)
            ).fetchall()
            if len(rows) > 1:
                raise ConflictError("Ambiguous product identity; use the provider-specific product key.")
            if rows:
                return dict(json.loads(rows[0][0]))
            row = db.execute("SELECT body FROM remote_products WHERE product_id=?", (product_id,)).fetchone()
        if row is None:
            raise KeyError(product_id)
        return dict(json.loads(row[0]))

    def save_acquisition_plan(self, plan: dict[str, Any]) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO acquisition_plans VALUES(?,?)", (plan["plan_id"], canonical(plan)))

    def acquisition_plan(self, plan_id: str) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute("SELECT body FROM acquisition_plans WHERE plan_id=?", (plan_id,)).fetchone()
        if not row:
            raise KeyError(plan_id)
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

    def download_page(self, offset: int = 0, limit: int = 10, state: str = "all", query: str = "") -> dict[str, Any]:
        active = "json_extract(d.body,'$.status') IN ('QUEUED','RUNNING')"
        clause = active if state == "active" else f"NOT ({active})" if state == "history" else "1"
        clause += " AND instr(lower(d.body),lower(?)) > 0"
        with self.connection() as db:
            count = db.execute(f"SELECT COUNT(*) FROM downloads d WHERE {clause}", (query,)).fetchone()[0]
            total = db.execute("SELECT COUNT(*) FROM downloads").fetchone()[0]
            running = db.execute(f"SELECT COUNT(*) FROM downloads d WHERE {active}").fetchone()[0]
            rows = db.execute(
                "SELECT d.body,c.pause_requested,c.continued_by FROM downloads d "
                f"LEFT JOIN download_controls c ON c.job_id=d.job_id WHERE {clause} "
                "ORDER BY d.rowid DESC LIMIT ? OFFSET ?",
                (query, min(50, max(1, limit)), max(0, offset)),
            ).fetchall()
        return {"items": [self._download_view(row) for row in rows], "count": count, "total": total, "active": running}

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
