"""Durable project revisions, runs, artifacts and replayable events.

SQLite owns runtime history. The packaged project definition is updated using a
write-ahead pending revision and atomic replacement, reconciled before new work.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from insar_pilot.domain.engine import (
    ArtifactOutput,
    PipelineDefinition,
    Profile,
    QCReport,
    RunStatus,
    StepDefinition,
    canonical,
    digest,
    identifier,
    new_id,
    snapshot,
    step_signature,
    utc_now,
    validate_public_snapshot,
)
from insar_pilot.infrastructure.engine_fingerprint import scientific_environment
from insar_pilot.infrastructure.project_codec import encode_project_document, read_project_document
from insar_pilot.infrastructure.project_file import inspect_project, resolve_project_file, validate_header
from insar_pilot.infrastructure.project_layout import ProjectLayout


class ConflictError(ValueError):
    """The operation no longer matches project intent or resource state."""


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(path, (canonical(value) + "\n").encode("utf-8"))


def atomic_project(path: Path, value: dict[str, Any]) -> None:
    atomic_bytes(path, encode_project_document(value))


def atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def file_snapshot(path: Path) -> dict[str, Any]:
    stat = path.stat()
    if path.is_dir():
        members = {
            str(p.relative_to(path)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(path.rglob("*"))
            if p.is_file()
        }
        return {
            "size": sum(v[0] for v in members.values()),
            "members": len(members),
            "tree_stat_digest": digest(members),
        }
    if not path.is_file():
        raise ValueError(f"Expected a regular file: {path}")
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS project (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revisions (revision INTEGER PRIMARY KEY, body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pending_revision (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY, body TEXT NOT NULL, created_by_run TEXT REFERENCES runs(run_id));
CREATE TABLE IF NOT EXISTS plans (plan_id TEXT PRIMARY KEY, body TEXT NOT NULL, submitted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS executions (execution_id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, pipeline_id TEXT NOT NULL, step_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','SUCCESS','FAILED','CANCELLED')),
  body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS run_inputs (
  run_id TEXT NOT NULL REFERENCES runs(run_id), artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
  role TEXT NOT NULL, PRIMARY KEY(run_id,artifact_id,role));
CREATE TABLE IF NOT EXISTS run_outputs (
  run_id TEXT NOT NULL REFERENCES runs(run_id), artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
  PRIMARY KEY(run_id,artifact_id));
CREATE TABLE IF NOT EXISTS lineage (
  child_id TEXT NOT NULL REFERENCES artifacts(artifact_id), parent_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
  PRIMARY KEY(child_id,parent_id));
CREATE TABLE IF NOT EXISTS active (
  pipeline_id TEXT NOT NULL, step_id TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES runs(run_id),
  PRIMARY KEY(pipeline_id,step_id));
CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(run_id), body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS qc (report_id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(run_id), body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL,
  event_type TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS layers (
  layer_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
  body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS run_step_history ON runs(pipeline_id,step_id,created_at);
CREATE TRIGGER IF NOT EXISTS immutable_terminal_run BEFORE UPDATE ON runs
  WHEN OLD.status IN ('SUCCESS','FAILED','CANCELLED') BEGIN SELECT RAISE(ABORT,'Terminal run is immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_artifact BEFORE UPDATE ON artifacts
  BEGIN SELECT RAISE(ABORT,'Artifact is immutable'); END;
"""


class EngineStore:
    def __init__(self, root: str | Path) -> None:
        inspection = inspect_project(root)
        if inspection["status"] not in {"ready", "modified"}:
            raise ValueError(inspection["message"])
        self.project_file = resolve_project_file(root)
        self.root = self.project_file.parent
        self.metadata = self.root / ".insar_pilot"
        self.db_path = self.metadata / "state.sqlite"
        if not self.db_path.is_file():
            raise FileNotFoundError("Not a next-generation project; use legacy import.")
        with self.connection() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ValueError("Unsupported state schema version.")
        self.recover_revision()
        self.layout = ProjectLayout(self.root, self.project().get("storage_layout_version", 1))

    @classmethod
    def create(
        cls,
        root: str | Path,
        name: str,
        profile: Profile = Profile.UNASSIGNED,
        *,
        initial_settings: dict[str, Any] | None = None,
        filename: str = "project.pilot",
        storage_layout_version: int = 1,
    ) -> EngineStore:
        path = Path(root).expanduser().resolve()
        if Path(filename).name != filename or not filename.endswith(".pilot") or "\\" in filename:
            raise ValueError("Invalid project entry filename.")
        if not name.strip():
            raise ValueError("Project name is required.")
        layout = ProjectLayout(path, storage_layout_version)
        path.mkdir(parents=True, exist_ok=True)
        if any(path.iterdir()):
            raise FileExistsError("A new project requires an empty directory.")
        metadata = path / ".insar_pilot"
        metadata.mkdir()
        db = sqlite3.connect(metadata / "state.sqlite")
        try:
            db.executescript(_SCHEMA)
            db.execute("PRAGMA user_version=1")
            body = {
                "schema_version": 2,
                "format": "insar-pilot-web",
                "project_id": new_id(),
                "name": name.strip(),
                "profile": profile.value,
                "profile_locked": False,
                "revision": 1,
                "aoi": None,
                "datasets": [],
                "pipelines": {},
                "settings": initial_settings or {},
            }
            if storage_layout_version != 1:
                body["storage_layout_version"] = storage_layout_version
            layout.initialize()
            db.execute("INSERT INTO project VALUES(1,?)", (canonical(body),))
            db.execute("INSERT INTO revisions VALUES(?,?,?)", (1, canonical(body), utc_now()))
            db.commit()
            atomic_project(path / filename, body)
        finally:
            db.close()

        return cls(path / filename)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def writer(self) -> Iterator[None]:
        import fcntl

        with (self.metadata / "writer.lock").open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def event(db: sqlite3.Connection, event_type: str, **payload: Any) -> None:
        db.execute(
            "INSERT INTO events(event_id,created_at,event_type,payload) VALUES(?,?,?,?)",
            (new_id(), utc_now(), event_type, canonical(payload)),
        )

    def project(self) -> dict[str, Any]:
        with self.connection() as db:
            return dict(json.loads(db.execute("SELECT body FROM project WHERE id=1").fetchone()[0]))

    def recover_revision(self) -> None:
        with self.writer(), self.connection() as db:
            pending = db.execute("SELECT body FROM pending_revision WHERE id=1").fetchone()
            if pending:
                proposed = json.loads(pending[0])
                on_disk = read_project_document(self.project_file)
                if digest(on_disk) == digest(proposed):
                    self.validate_definition(proposed)
                    self._commit_revision(db, proposed)
                elif digest(on_disk) != digest(
                    json.loads(db.execute("SELECT body FROM project WHERE id=1").fetchone()[0])
                ):
                    raise ConflictError("Pending revision conflicts with external edits.")
                db.execute("DELETE FROM pending_revision")

    @staticmethod
    def _commit_revision(db: sqlite3.Connection, body: dict[str, Any]) -> None:
        db.execute("UPDATE project SET body=? WHERE id=1", (canonical(body),))
        db.execute("INSERT INTO revisions VALUES(?,?,?)", (body["revision"], canonical(body), utc_now()))
        EngineStore.event(db, "project.revised", revision=body["revision"])

    def revise(self, expected_revision: int, **changes: Any) -> dict[str, Any]:
        if set(changes) - {"name", "aoi", "settings", "pipelines", "datasets", "profile", "profile_locked"}:
            raise ValueError("Unsupported project fields.")
        with self.writer():
            current = self.project()
            disk = read_project_document(self.project_file)
            if digest(disk) != digest(current):
                raise ConflictError("Project file was modified externally; import its edits explicitly.")
            if current["revision"] != expected_revision:
                raise ConflictError("Project revision changed.")
            proposed = {**current, **snapshot(changes), "revision": expected_revision + 1}
            validate_public_snapshot(proposed)
            Profile(proposed["profile"])
            if current["profile_locked"] and (
                proposed["profile"] != current["profile"] or not proposed["profile_locked"]
            ):
                raise ConflictError("Processing dataset permanently locked the project profile.")
            self.validate_definition(proposed)
            encode_project_document(proposed)
            with self.connection() as db:
                db.execute("INSERT INTO pending_revision VALUES(1,?)", (canonical(proposed),))
            atomic_project(self.project_file, proposed)
            with self.connection() as db:
                self._commit_revision(db, proposed)
                db.execute("DELETE FROM pending_revision")
            return proposed

    def validate_definition(self, body: dict[str, Any]) -> None:
        if not isinstance(body["name"], str) or not body["name"].strip():
            raise ValueError("Project name is required.")
        for dataset in body["datasets"]:
            if dataset["profile"] != body["profile"] or not body["profile_locked"]:
                raise ConflictError("Dataset binding and profile lock must be accepted together.")
            for aid in dataset["artifact_ids"]:
                if self.artifact(aid)["mission"] != body["profile"]:
                    raise ConflictError("Dataset contains an incompatible mission.")
        for pid, pipeline in body["pipelines"].items():
            if pid != pipeline["pipeline_id"] or pipeline["definition"]["profile"] != body["profile"]:
                raise ValueError("Pipeline identity or profile mismatch.")
            definition = pipeline["definition"]
            PipelineDefinition(
                definition["definition_id"],
                Profile(definition["profile"]),
                tuple(StepDefinition(**s) for s in definition["steps"]),
                definition["version"],
            )
            for ids in pipeline["inputs"].values():
                for aid in ids:
                    artifact = self.artifact(aid)
                    if artifact["mission"] not in {body["profile"], "unassigned"}:
                        raise ConflictError("Pipeline input has an incompatible mission.")

    def import_definition_edits(self, expected_revision: int) -> dict[str, Any]:
        """Accept a validated manual edit as a new revision with the same project identity."""
        with self.writer():
            current = self.project()
            if current["revision"] != expected_revision:
                raise ConflictError("Project revision changed.")
            proposed = read_project_document(self.project_file)
            validate_header(proposed)
            if proposed.get("storage_layout_version", 1) != current.get("storage_layout_version", 1):
                raise ValueError("Manual edits cannot change storage layout.")
            if proposed.get("format") != current.get("format"):
                raise ValueError("Manual edits cannot change project format.")
            if proposed.get("project_id") != current["project_id"] or proposed.get("schema_version") != 2:
                raise ValueError("Manual edits cannot change project identity or schema.")
            if set(proposed) != set(current):
                raise ValueError("Manual edits contain unsupported or missing fields.")
            if current["profile_locked"] and (
                proposed["profile"] != current["profile"] or not proposed["profile_locked"]
            ):
                raise ConflictError("Manual edits cannot unlock the processing profile.")
            Profile(proposed["profile"])
            validate_public_snapshot(proposed)
            self.validate_definition(proposed)
            proposed["revision"] = expected_revision + 1
            encode_project_document(proposed)
            with self.connection() as db:
                db.execute("INSERT INTO pending_revision VALUES(1,?)", (canonical(proposed),))
            atomic_project(self.project_file, proposed)
            with self.connection() as db:
                self._commit_revision(db, proposed)
                db.execute("DELETE FROM pending_revision")
            return dict(proposed)

    def attach_dataset(
        self,
        artifact_ids: list[str],
        profile: Profile,
        expected_revision: int,
        *,
        acquisition_plan_id: str | None = None,
        query_sources: list[Any] | None = None,
    ) -> dict[str, Any]:
        if not artifact_ids or profile is Profile.UNASSIGNED:
            raise ValueError("Attach requires processing artifacts and a mission profile.")
        artifacts = [self.artifact(a) for a in artifact_ids]
        if any(a["mission"] != profile.value for a in artifacts):
            raise ValueError("Mixed or incompatible mission selection.")
        current = self.project()
        if current["profile"] not in {Profile.UNASSIGNED.value, profile.value}:
            raise ConflictError("Dataset mission conflicts with project profile.")
        dataset = {
            "dataset_id": new_id(),
            "revision": 1,
            "profile": profile.value,
            "artifact_ids": list(dict.fromkeys(artifact_ids)),
            "created_at": utc_now(),
        }
        if acquisition_plan_id:
            dataset.update(acquisition_plan_id=acquisition_plan_id, query_sources=query_sources or [])
        return self.revise(
            expected_revision, profile=profile.value, profile_locked=True, datasets=[*current["datasets"], dataset]
        )

    def add_pipeline(
        self,
        definition: PipelineDefinition,
        inputs: dict[str, list[str]],
        parameters: dict[str, Any],
        environment: dict[str, Any],
        expected_revision: int,
    ) -> str:
        project = self.project()
        if project["profile"] != definition.profile.value or not project["profile_locked"]:
            raise ValueError("Attach a compatible processing dataset first.")
        for ids in inputs.values():
            for artifact_id in ids:
                self.artifact(artifact_id)
        pipeline_id = new_id()
        pipeline = {
            "pipeline_id": pipeline_id,
            "definition": definition.to_dict(),
            "inputs": inputs,
            "parameters": parameters,
            "environment": environment,
        }
        self.revise(expected_revision, pipelines={**project["pipelines"], pipeline_id: pipeline})
        return pipeline_id

    def register_source(
        self,
        path: str | Path,
        artifact_type: str,
        mission: Profile,
        metadata: dict[str, Any] | None = None,
        spatial: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = Path(path).expanduser().resolve(strict=True)
        from insar_pilot.infrastructure.source_closure import source_closure

        sources = source_closure(source)
        body: dict[str, Any] = {
            "artifact_id": new_id(),
            "type": artifact_type,
            "mission": mission.value,
            "created_by_run": None,
            "created_at": utc_now(),
            "integrity": "UNVERIFIED",
            "assets": [
                {
                    "uri": str(member),
                    "role": artifact_type if member == source else "sidecar_dependency",
                    "snapshot": file_snapshot(member),
                    "fingerprint_kind": "stat",
                    "fingerprint": digest(file_snapshot(member)),
                }
                for member in sources
            ],
            "metadata": metadata or {},
            "spatial": spatial or {},
            "temporal": {},
            "input_lineage": [],
            "provenance": {"kind": "external_import"},
        }
        with self.writer(), self.connection() as db:
            self._insert_artifact(db, body)
            self.event(db, "artifact.imported", artifact_id=body["artifact_id"])
        return body

    @staticmethod
    def _insert_artifact(db: sqlite3.Connection, body: dict[str, Any]) -> None:
        db.execute(
            "INSERT INTO artifacts VALUES(?,?,?)", (body["artifact_id"], canonical(body), body["created_by_run"])
        )
        for parent in body["input_lineage"]:
            db.execute("INSERT INTO lineage VALUES(?,?)", (body["artifact_id"], parent))
        if body.get("spatial"):
            layer = {
                "layer_id": new_id(),
                "artifact_id": body["artifact_id"],
                "visible": False,
                "style": {},
                "spatial": body["spatial"],
            }
            db.execute("INSERT INTO layers VALUES(?,?,?)", (layer["layer_id"], body["artifact_id"], canonical(layer)))

    def artifact(self, artifact_id: str) -> dict[str, Any]:
        return self._body("artifacts", "artifact_id", artifact_id)

    def run(self, run_id: str) -> dict[str, Any]:
        return self._body("runs", "run_id", run_id)

    def _body(self, table: str, key: str, value: str) -> dict[str, Any]:
        identifier(value)
        with self.connection() as db:
            row = db.execute(f"SELECT body FROM {table} WHERE {key}=?", (value,)).fetchone()
            if row is None:
                raise KeyError(value)
            return dict(json.loads(row[0]))

    def list_objects(self, kind: str) -> list[dict[str, Any]]:
        if kind not in {"runs", "jobs", "artifacts", "layers", "qc", "executions"}:
            raise ValueError("Unknown resource collection.")
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute(f"SELECT body FROM {kind} ORDER BY rowid")]

    def availability(self, artifact: dict[str, Any]) -> tuple[bool, str]:
        if not artifact["assets"]:
            return False, "source_not_acquired"
        for asset in artifact["assets"]:
            path = Path(asset["uri"])
            if not path.exists():
                return False, "input_missing"
            if asset.get("snapshot") != file_snapshot(path):
                return False, "input_changed"
        return True, ""

    def register_remote(self, product: dict[str, Any], mission: Profile) -> dict[str, Any]:
        body: dict[str, Any] = {
            "artifact_id": new_id(),
            "type": "NisarRSLC" if mission is Profile.NISAR else "Sentinel1SLC",
            "mission": mission.value,
            "created_by_run": None,
            "created_at": utc_now(),
            "integrity": "UNVERIFIED",
            "assets": [],
            "metadata": {
                "remote_product_id": product["remote_product_id"],
                "provider_id": product["provider_id"],
                "product_key": product.get("product_key"),
                "acquisition_time": product.get("acquisition_time"),
                "footprint": product.get("footprint"),
            },
            "spatial": {},
            "temporal": {},
            "input_lineage": [],
            "provenance": {"kind": "search_selection"},
        }
        with self.writer(), self.connection() as db:
            self._insert_artifact(db, body)
            self.event(db, "artifact.selected", artifact_id=body["artifact_id"])
        return body

    def resolve_remote(self, remote_product_id: str, local_artifact_id: str) -> None:
        """Accept acquired bytes as a new dataset revision, retaining the selection evidence."""
        project = self.project()
        old_ids = {
            a["artifact_id"]
            for a in self.list_objects("artifacts")
            if not a["assets"] and a["metadata"].get("remote_product_id") == remote_product_id
        }
        if not old_ids:
            return
        for dataset in project["datasets"]:
            if old_ids.intersection(dataset["artifact_ids"]):
                dataset["artifact_ids"] = [
                    local_artifact_id if aid in old_ids else aid for aid in dataset["artifact_ids"]
                ]
                dataset["revision"] += 1
        for pipeline in project["pipelines"].values():
            pipeline["inputs"] = {
                role: [local_artifact_id if aid in old_ids else aid for aid in ids]
                for role, ids in pipeline["inputs"].items()
            }
        self.revise(project["revision"], datasets=project["datasets"], pipelines=project["pipelines"])

    def _resolved_inputs(self, pipeline: dict[str, Any], step: dict[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for role, ids in pipeline["inputs"].items():
            for aid in ids:
                result.append({"role": role, "artifact_id": aid, "fingerprint": digest(self.artifact(aid)["assets"])})
        with self.connection() as db:
            for dependency in step["depends_on"]:
                row = db.execute(
                    "SELECT run_id FROM active WHERE pipeline_id=? AND step_id=?", (pipeline["pipeline_id"], dependency)
                ).fetchone()
                if not row:
                    raise ConflictError(f"Upstream step has no active result: {dependency}")
                outputs = db.execute("SELECT artifact_id FROM run_outputs WHERE run_id=?", (row[0],)).fetchall()
                for output in outputs:
                    aid = output[0]
                    result.append(
                        {"role": dependency, "artifact_id": aid, "fingerprint": digest(self.artifact(aid)["assets"])}
                    )
        return result

    def desired(self, pipeline_id: str, step_id: str) -> tuple[str, list[dict[str, Any]]]:
        pipeline = self.project()["pipelines"][pipeline_id]
        step = next(s for s in pipeline["definition"]["steps"] if s["step_id"] == step_id)
        inputs = self._resolved_inputs(pipeline, step)
        signature = step_signature(step, pipeline["parameters"], inputs, scientific_environment(pipeline))
        return signature, inputs

    def states(self, pipeline_id: str) -> list[dict[str, Any]]:
        pipeline = self.project()["pipelines"][pipeline_id]
        states: dict[str, dict[str, Any]] = {}
        with self.connection() as db:
            for step in pipeline["definition"]["steps"]:
                sid = step["step_id"]
                active = db.execute(
                    "SELECT run_id FROM active WHERE pipeline_id=? AND step_id=?", (pipeline_id, sid)
                ).fetchone()
                latest = db.execute(
                    "SELECT body FROM runs WHERE pipeline_id=? AND step_id=? ORDER BY rowid DESC LIMIT 1",
                    (pipeline_id, sid),
                ).fetchone()
                run = json.loads(latest[0]) if latest else None
                reasons: list[str] = []
                for role in step["input_roles"]:
                    if not pipeline["inputs"].get(role):
                        reasons.append(f"required_input_missing:{role}")
                try:
                    signature, inputs = self.desired(pipeline_id, sid)
                    for binding in inputs:
                        available, reason = self.availability(self.artifact(binding["artifact_id"]))
                        if not available:
                            reasons.append(reason)
                except (ConflictError, OSError, ValueError) as exc:
                    signature = ""
                    reasons.append(str(exc))
                for dep in step["depends_on"]:
                    if not states[dep]["active_usable"]:
                        reasons.append(f"upstream_not_current:{dep}")
                usable = False
                if active:
                    prior = self.run(active[0])
                    if prior["signature"] != signature:
                        reasons.append("scientific_inputs_changed")
                    for aid in prior.get("output_artifact_ids", []):
                        available, reason = self.availability(self.artifact(aid))
                        if not available:
                            reasons.append(reason)
                    if not self.qc_accepted(prior):
                        reasons.append("qc_gate_failed")
                    usable = not reasons
                if (
                    run
                    and run["status"] in {"QUEUED", "RUNNING"}
                    or (
                        run
                        and run["status"] in {"FAILED", "CANCELLED"}
                        and (
                            run["signature"] == signature or run["configuration_revision"] == self.project()["revision"]
                        )
                    )
                ):
                    status = run["status"]
                elif active and not usable:
                    status = "STALE"
                elif usable:
                    status = "SUCCESS"
                else:
                    status = "NOT_READY" if reasons else "READY"
                states[sid] = {
                    "step_id": sid,
                    "title": step["title"],
                    "status": status,
                    "active_run_id": active[0] if active else None,
                    "active_usable": usable,
                    "reasons": sorted(set(reasons)),
                    "latest_run_id": run["run_id"] if run else None,
                }
        return list(states.values())

    def create_plan(self, pipeline_id: str, through_step: str | None = None) -> dict[str, Any]:
        project = self.project()
        pipeline = project["pipelines"][pipeline_id]
        steps = pipeline["definition"]["steps"]
        if through_step:
            index = next((i for i, s in enumerate(steps) if s["step_id"] == through_step), None)
            if index is None:
                raise ValueError("Unknown requested pipeline step.")
            steps = steps[: index + 1]
        for step in steps:
            for role in step["input_roles"]:
                if not pipeline["inputs"].get(role):
                    raise ConflictError(f"required_input_missing:{role}")
        for ids in pipeline["inputs"].values():
            for aid in ids:
                ok, reason = self.availability(self.artifact(aid))
                if not ok:
                    raise ConflictError(reason)
        body = {
            "plan_id": new_id(),
            "execution_id": new_id(),
            "revision": project["revision"],
            "pipeline_id": pipeline_id,
            "pipeline_snapshot": snapshot(pipeline),
            "steps": steps,
            "created_at": utc_now(),
            "resource_estimate": None,
            "rerun_policy": "fresh_workspace_from_prepared_inputs",
        }
        body["pipeline_snapshot"]["_scientific_environment"] = scientific_environment(pipeline)
        body["working_directory"] = str(self.layout.workspaces / body["execution_id"])
        body["exact_inputs"] = [
            {"role": role, "artifact_id": aid, "assets": self.artifact(aid)["assets"]}
            for role, ids in pipeline["inputs"].items()
            for aid in ids
        ]
        body["requested_through_step"] = through_step
        template = pipeline["parameters"].get("template_path")
        if template:
            body["pipeline_snapshot"]["_template_content"] = Path(template).expanduser().read_text()
        with self.connection() as db:
            body["state_cursor"] = db.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]
            db.execute("INSERT INTO plans(plan_id,body) VALUES(?,?)", (body["plan_id"], canonical(body)))
            if self.layout.version == 2:
                atomic_json(self.metadata / "records" / "plans" / (body["plan_id"] + ".json"), body)
        return body

    def submit(self, plan_id: str) -> dict[str, Any]:
        with self.writer(), self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body,submitted FROM plans WHERE plan_id=?", (identifier(plan_id),)).fetchone()
            if not row:
                raise KeyError(plan_id)
            if row[1]:
                raise ConflictError("Plan already submitted.")
            plan: dict[str, Any] = json.loads(row[0])
            if self.project()["revision"] != plan["revision"]:
                raise ConflictError("Execution plan is stale.")
            frozen_environment = plan["pipeline_snapshot"].get("_scientific_environment")
            if frozen_environment is not None and frozen_environment != scientific_environment(
                plan["pipeline_snapshot"]
            ):
                raise ConflictError("Execution plan is stale; runtime or template changed.")
            cursor = db.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]
            if plan.get("state_cursor", cursor) != cursor:
                raise ConflictError("Execution plan is stale; project runtime state changed.")
            for ids in plan["pipeline_snapshot"]["inputs"].values():
                for aid in ids:
                    ok, reason = self.availability(self.artifact(aid))
                    if not ok:
                        raise ConflictError(reason)
            if db.execute(
                "SELECT 1 FROM runs WHERE pipeline_id=? AND status IN ('QUEUED','RUNNING')", (plan["pipeline_id"],)
            ).fetchone():
                raise ConflictError("Pipeline already has an active execution.")
            work = self.layout.workspaces / plan["execution_id"]
            work.mkdir()
            plan["working_directory"] = str(work)
            plan["run_ids"] = []
            for step in plan["steps"]:
                run_id, job_id = new_id(), new_id()
                run_dir = self.layout.runs / run_id
                (run_dir / "logs").mkdir(parents=True)
                prior = db.execute(
                    "SELECT run_id FROM runs WHERE pipeline_id=? AND step_id=? ORDER BY rowid DESC LIMIT 1",
                    (plan["pipeline_id"], step["step_id"]),
                ).fetchone()
                body = {
                    "run_id": run_id,
                    "job_id": job_id,
                    "pipeline_id": plan["pipeline_id"],
                    "step_id": step["step_id"],
                    "execution_id": plan["execution_id"],
                    "rerun_of": prior[0] if prior else None,
                    "parent_run_id": plan["run_ids"][-1] if plan["run_ids"] else None,
                    "status": "QUEUED",
                    "created_at": utc_now(),
                    "started_at": None,
                    "finished_at": None,
                    "parameter_snapshot": plan["pipeline_snapshot"]["parameters"],
                    "environment_snapshot": plan["pipeline_snapshot"]["environment"],
                    "configuration_revision": plan["revision"],
                    "signature": "",
                    "input_artifact_ids": [],
                    "output_artifact_ids": [],
                    "working_directory": str(work),
                    "commands": [],
                    "exit_code": None,
                    "stdout_log": str(run_dir / "logs" / "stdout.log"),
                    "stderr_log": str(run_dir / "logs" / "stderr.log"),
                    "failure_kind": None,
                }
                db.execute(
                    "INSERT INTO runs VALUES(?,?,?,?,?,?)",
                    (run_id, plan["pipeline_id"], step["step_id"], "QUEUED", canonical(body), body["created_at"]),
                )
                job = {
                    "job_id": job_id,
                    "run_id": run_id,
                    "status": "QUEUED",
                    "cancel_requested": False,
                    "pid": None,
                    "process_start": None,
                    "heartbeat": None,
                }
                db.execute("INSERT INTO jobs VALUES(?,?,?)", (job_id, run_id, canonical(job)))
                plan["run_ids"].append(run_id)
                atomic_json(run_dir / "snapshot.json", body)
                self.event(db, "run.queued", run_id=run_id, step_id=step["step_id"])
            db.execute("INSERT INTO executions VALUES(?,?)", (plan["execution_id"], canonical(plan)))
            db.execute("UPDATE plans SET submitted=1 WHERE plan_id=?", (plan_id,))
            return plan

    def begin(self, run_id: str, commands: list[list[str]], provenance: dict[str, Any]) -> dict[str, Any]:
        with self.writer(), self.connection() as db:
            run = self.run(run_id)
            if run["status"] != "QUEUED":
                raise ConflictError("Run cannot be started again.")
            plan = self._body("executions", "execution_id", run["execution_id"])
            pipeline = plan["pipeline_snapshot"]
            step = next(s for s in plan["steps"] if s["step_id"] == run["step_id"])
            inputs = []
            for role, ids in pipeline["inputs"].items():
                for aid in ids:
                    inputs.append(
                        {"role": role, "artifact_id": aid, "fingerprint": digest(self.artifact(aid)["assets"])}
                    )
            for dependency in step["depends_on"]:
                previous = next(self.run(rid) for rid in plan["run_ids"] if self.run(rid)["step_id"] == dependency)
                if previous["status"] != "SUCCESS":
                    raise ConflictError(f"Execution predecessor failed: {dependency}")
                for aid in previous["output_artifact_ids"]:
                    inputs.append(
                        {"role": dependency, "artifact_id": aid, "fingerprint": digest(self.artifact(aid)["assets"])}
                    )
            effective_environment = pipeline.get("_scientific_environment", pipeline["environment"])
            signature = step_signature(step, pipeline["parameters"], inputs, effective_environment)
            for binding in inputs:
                ok, reason = self.availability(self.artifact(binding["artifact_id"]))
                if not ok:
                    raise ConflictError(reason)
                db.execute("INSERT INTO run_inputs VALUES(?,?,?)", (run_id, binding["artifact_id"], binding["role"]))
            run.update(
                status="RUNNING",
                started_at=utc_now(),
                signature=signature,
                input_artifact_ids=[b["artifact_id"] for b in inputs],
                input_bindings=inputs,
                commands=commands,
                provenance=snapshot(provenance),
                effective_environment=effective_environment,
            )
            self._update_run(db, run)
            self._update_job(db, run["job_id"], status="RUNNING")
            self.event(db, "run.started", run_id=run_id)
            atomic_json(self.layout.runs / run_id / "snapshot.json", run)
            return run

    @staticmethod
    def _update_run(db: sqlite3.Connection, run: dict[str, Any]) -> None:
        db.execute("UPDATE runs SET status=?,body=? WHERE run_id=?", (run["status"], canonical(run), run["run_id"]))

    @staticmethod
    def _update_job(db: sqlite3.Connection, job_id: str, **fields: Any) -> None:
        body = json.loads(db.execute("SELECT body FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0])
        body.update(fields)
        db.execute("UPDATE jobs SET body=? WHERE job_id=?", (canonical(body), job_id))

    def update_job(self, job_id: str, **fields: Any) -> None:
        with self.connection() as db:
            self._update_job(db, job_id, **fields)

    def cancel(self, job_id: str) -> None:
        with self.writer(), self.connection() as db:
            job = self._body("jobs", "job_id", job_id)
            if job["status"] in {"SUCCESS", "FAILED", "CANCELLED"}:
                return
            self._update_job(db, job_id, cancel_requested=True)
            self.event(db, "job.cancel_requested", job_id=job_id)

    def cancelled(self, job_id: str) -> bool:
        return bool(self._body("jobs", "job_id", job_id)["cancel_requested"])

    def set_active(self, run_id: str) -> None:
        with self.writer(), self.connection() as db:
            run = self.run(run_id)
            if run["status"] != "SUCCESS" or not self.qc_accepted(run):
                raise ConflictError("Only a successful, QC-accepted run can be active.")
            signature, _ = self.desired(run["pipeline_id"], run["step_id"])
            if signature != run["signature"]:
                raise ConflictError("Restore compatible parameters and inputs before adopting this Run.")
            if any(not self.availability(self.artifact(aid))[0] for aid in run["output_artifact_ids"]):
                raise ConflictError("Historical output is missing or changed.")
            db.execute(
                "INSERT INTO active VALUES(?,?,?) ON CONFLICT(pipeline_id,step_id) "
                "DO UPDATE SET run_id=excluded.run_id",
                (run["pipeline_id"], run["step_id"], run_id),
            )
            self.event(db, "run.adopted", run_id=run_id)

    def latest_qc(self, run_id: str) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute("SELECT body FROM qc WHERE run_id=? ORDER BY rowid DESC LIMIT 1", (run_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def qc_accepted(self, run: dict[str, Any]) -> bool:
        report = self.latest_qc(run["run_id"])
        if report is None:
            return bool(run.get("qc_gate_passed", False))
        return all(not c["check"]["blocking"] or c["status"] == "PASS" for c in report["checks"])

    @staticmethod
    def _insert_qc(db: sqlite3.Connection, run_id: str, report: QCReport) -> None:
        from dataclasses import asdict

        body = {**asdict(report), "run_id": run_id, "gate_passed": report.gate_passed}
        db.execute("INSERT INTO qc VALUES(?,?,?)", (report.report_id, run_id, canonical(body)))

    def evaluate_qc(self, run_id: str, report: QCReport) -> None:
        """Append a policy evaluation without rewriting scientific history or inputs."""
        with self.writer(), self.connection() as db:
            run = self.run(run_id)
            if not RunStatus(run["status"]).terminal:
                raise ConflictError("Re-evaluation requires a completed Run.")
            self._insert_qc(db, run_id, report)
            self.event(db, "qc.evaluated", run_id=run_id, report_id=report.report_id, gate_passed=report.gate_passed)

    def finish(
        self,
        run_id: str,
        status: RunStatus,
        exit_code: int | None,
        outputs: list[dict[str, Any]] | None = None,
        report: QCReport | None = None,
        failure_kind: str | None = None,
        message: str = "",
    ) -> dict[str, Any]:
        if not status.terminal:
            raise ValueError("Finish requires terminal status.")
        with self.writer(), self.connection() as db:
            run = self.run(run_id)
            if RunStatus(run["status"]).terminal:
                raise ConflictError("Terminal Run is immutable.")
            if status is RunStatus.SUCCESS and run["status"] != "RUNNING":
                raise ConflictError("Unstarted Run cannot succeed.")
            if status is RunStatus.SUCCESS and (exit_code != 0 or report is None or not report.gate_passed):
                status, failure_kind = RunStatus.FAILED, "artifact_contract"
            if status is RunStatus.SUCCESS:
                execution = self._body("executions", "execution_id", run["execution_id"])
                step = next(s for s in execution["steps"] if s["step_id"] == run["step_id"])
                if step["output_roles"] and not outputs:
                    status, failure_kind = RunStatus.FAILED, "artifact_contract"
                    message = "Required output contract produced no artifacts."
            if status is RunStatus.SUCCESS:
                for aid in run["input_artifact_ids"]:
                    ok, reason = self.availability(self.artifact(aid))
                    if not ok:
                        status, failure_kind = RunStatus.FAILED, reason
            published: list[str] = []
            if status is RunStatus.SUCCESS:
                for artifact in outputs or []:
                    if artifact["created_by_run"] != run_id:
                        raise ValueError("Output belongs to another Run.")
                    self._insert_artifact(db, artifact)
                    published.append(artifact["artifact_id"])
                    db.execute("INSERT INTO run_outputs VALUES(?,?)", (run_id, artifact["artifact_id"]))
                    self.event(db, "artifact.published", artifact_id=artifact["artifact_id"], run_id=run_id)
            if report:
                self._insert_qc(db, run_id, report)
            run.update(
                status=status.value,
                exit_code=exit_code,
                finished_at=utc_now(),
                output_artifact_ids=published,
                qc_report_id=report.report_id if report else None,
                qc_gate_passed=bool(report and report.gate_passed),
                failure_kind=failure_kind,
                message=message,
            )
            self._update_run(db, run)
            self._update_job(db, run["job_id"], status=status.value, heartbeat=utc_now())
            if status is RunStatus.SUCCESS:
                try:
                    signature, _ = self.desired(run["pipeline_id"], run["step_id"])
                except (KeyError, StopIteration, ConflictError, OSError, ValueError):
                    signature = None
                if signature == run["signature"]:
                    db.execute(
                        "INSERT INTO active VALUES(?,?,?) ON CONFLICT(pipeline_id,step_id) "
                        "DO UPDATE SET run_id=excluded.run_id",
                        (run["pipeline_id"], run["step_id"], run_id),
                    )
            self.event(db, "run.finished", run_id=run_id, status=run["status"], failure_kind=failure_kind)
            return run

    def publish(self, run_id: str, output: ArtifactOutput) -> dict[str, Any]:
        run = self.run(run_id)
        if run["status"] != "RUNNING" or not output.assets:
            raise ConflictError("Only a running step can stage nonempty outputs.")
        artifact_id = new_id()
        target = self.layout.artifacts / artifact_id
        staging = self.layout.artifacts / f".{artifact_id}.partial"
        staging.mkdir()
        assets: list[dict[str, Any]] = []
        try:
            from insar_pilot.infrastructure.asset_closure import copy_closure

            sources = [Path(asset.path).resolve(strict=True) for asset in output.assets]
            if any(not p.is_relative_to(Path(run["working_directory"]).resolve()) for p in sources):
                raise ValueError("Processor outputs must belong to its isolated workspace.")
            external = {Path(a["uri"]) for aid in run["input_artifact_ids"] for a in self.artifact(aid)["assets"]}
            copied = copy_closure(sources, Path(run["working_directory"]), staging, target, external)
            roles = {Path(asset.path).resolve(): asset for asset in output.assets}
            ordered = list(dict.fromkeys([*sources, *copied]))
            for source in ordered:
                destination = copied[source]
                asset = roles.get(source)
                fingerprint = file_digest(destination)
                assets.append(
                    {
                        "uri": str(target / destination.relative_to(staging)),
                        "role": asset.role if asset else "sidecar_dependency",
                        "subdataset": asset.subdataset if asset else None,
                        "snapshot": file_snapshot(destination),
                        "fingerprint_kind": "sha256",
                        "fingerprint": fingerprint,
                    }
                )
            body = {
                "artifact_id": artifact_id,
                "type": output.artifact_type,
                "mission": self.project()["profile"],
                "created_by_run": run_id,
                "created_at": utc_now(),
                "integrity": "VALID",
                "assets": assets,
                "metadata": output.metadata,
                "spatial": output.spatial,
                "temporal": output.temporal,
                "input_lineage": list(dict.fromkeys(run["input_artifact_ids"])),
            }
            atomic_json(staging / "manifest.json", body)
            os.replace(staging, target)
            return body
        except BaseException:
            shutil.rmtree(staging)
            raise

    def publish_outputs(self, run_id: str, outputs: list[ArtifactOutput]) -> list[dict[str, Any]]:
        """Logical HDF5 datasets share one frozen physical container per Run."""
        from copy import deepcopy

        containers: dict[tuple[str, ...], dict[str, Any]] = {}
        result = []
        for output in outputs:
            key = tuple(str(Path(asset.path).resolve()) for asset in output.assets)
            if key not in containers:
                body = self.publish(run_id, output)
                containers[key] = body
            else:
                body = deepcopy(containers[key])
                body.update(
                    artifact_id=new_id(),
                    type=output.artifact_type,
                    metadata=output.metadata,
                    spatial=output.spatial,
                    temporal=output.temporal,
                )
                for asset, specification in zip(body["assets"], output.assets, strict=False):
                    asset.update(role=specification.role, subdataset=specification.subdataset)
                target = self.layout.artifacts / body["artifact_id"]
                target.mkdir()
                atomic_json(target / "manifest.json", body)
            result.append(body)
        return result

    def events(self, after: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        with self.connection() as db:
            return [
                {**dict(row), "payload": json.loads(row["payload"])}
                for row in db.execute(
                    "SELECT * FROM events WHERE sequence>? ORDER BY sequence LIMIT ?", (max(0, after), min(1000, limit))
                )
            ]
