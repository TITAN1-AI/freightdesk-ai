"""Atomic offline observation/evidence receipts. This store cannot open tenant production data."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from app.core.runtime import RuntimePaths
from executors.webbridge_v2.contracts import Binding, validate_graph


class OfflineObservationStore:
    def __init__(self, path: Path):
        paths = RuntimePaths.from_environment()
        base = paths.path("Data", "TestRuns")
        try:
            parts = path.absolute().relative_to(base.absolute()).parts
            checked = paths.path("Data", "TestRuns", *parts)
        except ValueError:
            raise PermissionError("V2_OFFLINE_STORE_ONLY") from None
        if not parts or checked.suffix != ".sqlite3":
            raise PermissionError("V2_OFFLINE_STORE_ONLY")
        checked.parent.mkdir(parents=True, exist_ok=True)
        self.path = checked
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS observations (
                    observation_id TEXT PRIMARY KEY, digest TEXT NOT NULL, graph TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS receipts (
                    observation_id TEXT PRIMARY KEY REFERENCES observations(observation_id),
                    digest TEXT NOT NULL, status TEXT NOT NULL CHECK(status='GRAPH_PERSISTED'));
            """)

    @contextmanager
    def connect(self):
        # Revalidate all components on every open, including replacements since initialization.
        paths = RuntimePaths.from_environment()
        relative = self.path.relative_to(paths.path("Data", "TestRuns"))
        checked = paths.path("Data", "TestRuns", *relative.parts)
        db = sqlite3.connect(checked)
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def persist(self, raw: dict, *, expected_binding: Binding, vocabulary: frozenset[str],
                before_receipt: Callable[[], None] | None = None) -> dict:
        try:
            if len(json.dumps(raw).encode()) > 262144:
                raise ValueError("BOUND")
            graph = validate_graph(raw, expected_binding=expected_binding, vocabulary=vocabulary)
            body = json.dumps(graph.model_dump(by_alias=True), sort_keys=True, separators=(",", ":"))
        except (ValidationError, ValueError, TypeError, RecursionError):
            raise PermissionError("V2_GRAPH_REJECTED") from None
        digest = hashlib.sha256(body.encode()).hexdigest()
        try:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                prior = db.execute("SELECT digest FROM observations WHERE observation_id=?", (graph.observation_id,)).fetchone()
                if prior:
                    receipt = db.execute("SELECT digest FROM receipts WHERE observation_id=?", (graph.observation_id,)).fetchone()
                    if prior[0] != digest or receipt != (digest,):
                        raise PermissionError("V2_OBSERVATION_CONFLICT")
                    return {"status": "GRAPH_PERSISTED", "observation_id": graph.observation_id, "digest": digest, "duplicate": True}
                db.execute("INSERT INTO observations VALUES (?,?,?)", (graph.observation_id, digest, body))
                if before_receipt:
                    before_receipt()  # Offline failure injection; never a browser callback.
                db.execute("INSERT INTO receipts VALUES (?,?,'GRAPH_PERSISTED')", (graph.observation_id, digest))
        except PermissionError as error:
            if error.args == ("V2_OBSERVATION_CONFLICT",):
                raise
            raise RuntimeError("V2_PERSIST_FAILED") from None
        except Exception:
            raise RuntimeError("V2_PERSIST_FAILED") from None
        return {"status": "GRAPH_PERSISTED", "observation_id": graph.observation_id, "digest": digest, "duplicate": False}
