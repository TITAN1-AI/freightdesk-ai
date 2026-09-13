import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from app.models.domain import AuditEvent, Model


class Store:
    """Single-process transactional persistence. Every key is tenant scoped."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                tenant TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY (tenant, kind, id));
            CREATE TABLE IF NOT EXISTS receipts (
                tenant TEXT NOT NULL, source TEXT NOT NULL, id TEXT NOT NULL, digest TEXT NOT NULL,
                PRIMARY KEY (tenant, source, id));
            CREATE TABLE IF NOT EXISTS audit (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
                BEGIN SELECT RAISE(ABORT, 'Audit is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
                BEGIN SELECT RAISE(ABORT, 'Audit is append-only'); END;
            PRAGMA user_version=1;
        """)

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def put(self, tenant: str, kind: str, key: str, value: Model | dict):
        body = value.model_dump_json() if isinstance(value, Model) else json.dumps(value)
        self.db.execute("INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(tenant,kind,id) "
                        "DO UPDATE SET body=excluded.body", (tenant, kind, key, body))

    def get(self, tenant: str, kind: str, key: str):
        row = self.db.execute("SELECT body FROM records WHERE tenant=? AND kind=? AND id=?",
                              (tenant, kind, key)).fetchone()
        if not row:
            raise KeyError("Record not found")
        return json.loads(row[0])

    def all(self, tenant: str, kind: str):
        return [json.loads(row[0]) for row in self.db.execute(
            "SELECT body FROM records WHERE tenant=? AND kind=? ORDER BY id", (tenant, kind))]

    def audit(self, event: AuditEvent):
        # Only structured, application-authored explanations; no raw commands, provider bodies or secrets.
        self.db.execute("INSERT INTO audit(tenant,body) VALUES (?,?)",
                        (event.tenant_id, event.model_dump_json()))

    def timeline(self, tenant: str, limit: int = 150):
        return [json.loads(row[0]) for row in self.db.execute(
            "SELECT body FROM audit WHERE tenant=? ORDER BY seq DESC LIMIT ?", (tenant, limit))]

    def close(self):
        self.db.close()
