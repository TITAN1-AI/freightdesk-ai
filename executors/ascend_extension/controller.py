"""Four-step, one-use X1 identity test. Host owns release, policy, replay and receipt validation.

No browser, HTTP, operational adapter or canonical-store executor is imported here.
"""

import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import ROOT
from app.models.domain import ActionPolicy
from app.policies.engine import PolicyEngine
from executors.ascend_extension.contracts import OPERATIONS, ReadCommand
from executors.ascend_extension.detail_diagnostics import DetailContainerDiagnostic
from executors.ascend_extension.native import canonical
from executors.ascend_extension.pairing import ACTOR, TENANT
from executors.ascend_extension.view_contract import AscendLoadBoardViewContract
from integrations.ascend.board_dates import local_date

STEPS = OPERATIONS[:4]
ERRORS = frozenset(
    {
        "READ_RELEASE_REQUIRED",
        "READ_POLICY_BLOCKED",
        "READ_TEST_CONSUMED",
        "READ_TEST_EXPIRED",
        "READ_SEQUENCE_INVALID",
        "COMMAND_NOT_ALLOWED",
        "PAIRING_LOST",
        "NO_ELIGIBLE_TAB",
        "TAB_SELECTION_REQUIRED",
        "TAB_STATE_CHANGED",
        "SESSION_UNVERIFIED",
        "ACTIVE_VIEW_UNVERIFIED",
        "ACTIVE_VIEW_CHANGED",
        "ACTIVE_VIEW_NOT_ACTIVE_LOADS",
        "BOARD_SCHEMA_INVALID",
        "BOARD_MISMATCH",
        "BOARD_CHANGED",
        "EXACT_LOAD_MISSING",
        "OPENER_AMBIGUOUS",
        "UNSAFE_OPENER",
        "DETAIL_IDENTITY_MISSING",
        "DETAIL_IDENTITY_AMBIGUOUS",
        "DETAIL_IDENTITY_CONFLICT",
        "IDENTITY_BOUND_EXCEEDED",
        "READ_TIMEOUT",
        "RECEIPT_INVALID",
        "READ_PERSIST_FAILED",
        "READ_EXECUTION_FAILED",
        "DUPLICATE_REQUEST",
    }
)


def safe_code(error):
    value = error if isinstance(error, str) else str(error.args[0]) if len(error.args) == 1 else ""
    if value == "duplicate_request":
        return "DUPLICATE_REQUEST"
    return value if value in ERRORS else "READ_EXECUTION_FAILED"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Route(Strict):
    tab_id: int = Field(ge=0)
    document_id: str = Field(pattern=r"^[a-f0-9]{32}$", min_length=32, max_length=32)
    eligible_tab_count: int = Field(ge=1, le=100)
    origin: Literal["https://ascendtms.com"]
    path: Literal["/", "/loads", "/login.html"]


class Row(Strict):
    load_id: str = Field(pattern=r"^[0-9]{1,20}$", min_length=1, max_length=20)
    pick_date: str | None = Field(default=None, pattern=r"^\d{2}/\d{2}/\d{4}$", min_length=10, max_length=10)
    drop_date: str | None = Field(default=None, pattern=r"^\d{2}/\d{2}/\d{4}$", min_length=10, max_length=10)


class SessionEvidence(Strict):
    authenticated_app: bool
    login_form_present: bool
    nav_markers: list[
        Literal[
            "Dashboard", "Loads", "Customers", "Carriers", "Locations", "Reporting", "Accounting", "Settings"
        ]
    ] = Field(max_length=8)


class BoardEvidence(Strict):
    view_contract: AscendLoadBoardViewContract
    source_view: Literal["ACTIVE_LOADS"]
    coverage: Literal["VISIBLE_BOARD_ONLY"]
    rows: list[Row] = Field(min_length=1, max_length=100)
    board_hash: str = Field(pattern=r"^[a-f0-9]{64}$", min_length=64, max_length=64)


class FindEvidence(Strict):
    view_contract: AscendLoadBoardViewContract
    load_id: str
    exact_row: Literal[True]
    board_hash: str

    @field_validator("exact_row", mode="before")
    @classmethod
    def exact_boolean(cls, value):
        if value is not True:
            raise ValueError("RECEIPT_INVALID")
        return value


class IdentityEvidence(Strict):
    container_diagnostic: DetailContainerDiagnostic | None = None

    @field_validator("container_diagnostic")
    @classmethod
    def causal_container_proof(cls, value):
        if value is not None and (value.failed_category is not None or not value.row_verified
            or not value.opener_verified or not value.click_dispatched or value.selected_level is None
            or not value.ranked_candidates):
            raise ValueError("DETAIL_IDENTITY_MISSING")
        return value
    view_contract: AscendLoadBoardViewContract
    expected_load_id: str
    observed_load_id: str
    identity_strategy: Literal[
        "PROVIDER_DETAIL_FIELD", "PROVIDER_OPENER_IDENTITY", "PROVIDER_SELECTED_ROW_BINDING"
    ]
    confidence: Literal["VERIFIED"]
    board_hash: str
    row_match: Literal[True]
    opener_belongs_to_row: Literal[True]
    unique_panel: Literal[True]
    detail_field_match: bool
    direct_panel_reference: bool
    opener_identity_match: bool
    selection_transition: bool
    newly_visible: bool

    @field_validator("row_match", "opener_belongs_to_row", "unique_panel", mode="before")
    @classmethod
    def exact_boolean(cls, value):
        if value is not True:
            raise ValueError("RECEIPT_INVALID")
        return value


class Request(Strict):
    kind: Literal["READ_REQUEST"]
    command: ReadCommand
    route: Route


class Result(Strict):
    kind: Literal["READ_RESULT"]
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$", min_length=32, max_length=32)
    command_request_id: str
    route: Route
    evidence: dict | None
    error_code: str | None


def policy_gate(repo):
    if PolicyEngine(ROOT / "config" / "policies.json").evaluate("read_ascend") != ActionPolicy.ALLOW:
        raise PermissionError("READ_POLICY_BLOCKED")
    path = repo.paths.path("Data", TENANT, "ascend.sqlite3")
    if path.exists():
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            for (body,) in db.execute(
                "SELECT body FROM records WHERE tenant=? AND kind=?", (TENANT, "ascend_controls")
            ):
                value = json.loads(body)
                if value.get("paused", True) or value.get("human_takeover", True):
                    raise PermissionError("READ_POLICY_BLOCKED")


@contextmanager
def ledger(repo):
    with repo.database() as db:
        db.execute("CREATE TABLE IF NOT EXISTS x1_read_grants(id TEXT PRIMARY KEY, body TEXT)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS x1_read_events(request_id TEXT PRIMARY KEY, attempt_id TEXT, body TEXT)"
        )
        for table in ("x1_read_grants", "x1_read_events"):
            for action in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action} BEFORE {action} ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'append_only_x1_read_ledger'); END"
                )
        yield db


def prepare(
    repo, attempt_id, service_date, pickups, deliveries, *, gate=policy_gate, supersedes_attempt=None
):
    """Only the owner CLI calls this. No host/extension message can prepare an authorization."""
    gate(repo)
    if not re.fullmatch(r"owner-x1-identity-1755-[a-z0-9-]{1,60}", attempt_id):
        raise ValueError("READ_RELEASE_REQUIRED")
    day = date.fromisoformat(service_date)
    if (
        not pickups
        or not deliveries
        or set(pickups) & set(deliveries)
        or len(set(pickups)) != len(pickups)
        or len(set(deliveries)) != len(deliveries)
        or any(not re.fullmatch(r"[0-9]{1,20}", n) for n in pickups + deliveries)
        or "1755" not in pickups
    ):
        raise ValueError("READ_RELEASE_REQUIRED")
    grant = {
        "attempt_id": attempt_id,
        "service_date": day.isoformat(),
        "pickups": sorted(pickups),
        "deliveries": sorted(deliveries),
        "load_id": "1755",
        "date_format": "US",
        "expires_at": int(repo.clock() + 600),
        "installation_id": repo.config()["installation_id"],
    }
    with ledger(repo) as db:
        previous = db.execute("SELECT id FROM x1_read_grants").fetchall()
        if previous:
            # One specifically reviewed successor can be prepared ONLY by explicit future owner CLI
            # execution. Never reset the old receipt/consumption or turn this into an auto-retry loop.
            prior = "owner-x1-identity-1755-20260911-01"
            successor = "owner-x1-identity-1755-20260911-02"
            if supersedes_attempt != prior or attempt_id != successor or previous != [(prior,)]:
                raise PermissionError("READ_TEST_CONSUMED")
            consumed = db.execute(
                "SELECT 1 FROM consumed WHERE kind=? AND id=?", ("x1-read", prior)
            ).fetchone()
            events = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT body FROM x1_read_events WHERE attempt_id=? ORDER BY rowid", (prior,)
                )
            ]
            if not consumed or not events or any(e.get("production_writes") is not False for e in events):
                raise PermissionError("READ_RELEASE_REQUIRED")
            last = events[-1]
            if (last.get("operation"), last.get("state"), last.get("error_code"), last.get("identity")) != (
                "ASCEND_GET_ACTIVE_LOADS",
                "STOPPED",
                "ACTIVE_VIEW_UNVERIFIED",
                "UNKNOWN",
            ):
                raise PermissionError("READ_RELEASE_REQUIRED")
            grant["supersedes_attempt"] = prior
        elif supersedes_attempt is not None:
            raise PermissionError("READ_RELEASE_REQUIRED")
        db.execute("INSERT INTO x1_read_grants VALUES (?,?)", (attempt_id, json.dumps(grant)))
    return grant


class ReadController:
    def __init__(self, repo, *, gate=policy_gate, clock=time.time):
        self.repo, self.gate, self.clock = repo, gate, clock
        self.grant = None
        self.index = 0
        self.pending = None
        self.route = None
        self.revision = None
        self.stopped = False
        self.view_diagnostic = None

    def check(self):
        self.gate(self.repo)
        if self.stopped or self.index >= len(STEPS):
            raise PermissionError("READ_TEST_CONSUMED")
        if not self.grant:
            with ledger(self.repo) as db:
                records = db.execute("""SELECT g.body FROM x1_read_grants g
                    WHERE NOT EXISTS (SELECT 1 FROM consumed c WHERE c.kind='x1-read' AND c.id=g.id)""").fetchall()
                if not records and db.execute("SELECT 1 FROM x1_read_grants").fetchone():
                    raise PermissionError("READ_TEST_CONSUMED")
            if len(records) != 1:
                raise PermissionError("READ_RELEASE_REQUIRED")
            self.grant = json.loads(records[0][0])
        if self.grant["installation_id"] != self.repo.config()["installation_id"]:
            raise PermissionError("READ_RELEASE_REQUIRED")
        if self.clock() >= self.grant["expires_at"]:
            raise PermissionError("READ_TEST_EXPIRED")
        if self.index == 0 and not self.pending:
            with ledger(self.repo) as db:
                if db.execute(
                    "SELECT 1 FROM consumed WHERE kind=? AND id=?", ("x1-read", self.grant["attempt_id"])
                ).fetchone():
                    raise PermissionError("READ_TEST_CONSUMED")

    def plan(self):
        self.check()
        return {
            k: self.grant[k]
            for k in ("attempt_id", "service_date", "load_id", "pickups", "deliveries", "expires_at")
        }

    def begin(self, raw):
        self.check()
        request = Request.model_validate(raw)
        command, route = request.command, request.route
        if command.operation not in STEPS:
            raise PermissionError("COMMAND_NOT_ALLOWED")
        if self.pending or command.operation != STEPS[self.index]:
            raise PermissionError("READ_SEQUENCE_INVALID")
        if command.load_id != (
            self.grant["load_id"] if self.index >= 2 else None
        ) or command.expected_revision != (self.revision if self.index >= 2 else None):
            raise PermissionError("READ_SEQUENCE_INVALID")
        if self.route and (route.tab_id, route.document_id, route.origin, route.path) != (
            self.route.tab_id,
            self.route.document_id,
            self.route.origin,
            self.route.path,
        ):
            raise PermissionError("TAB_STATE_CHANGED")
        self.repo.consume_request(command.request_id)
        if self.index == 0:
            with ledger(self.repo) as db:
                try:
                    db.execute("INSERT INTO consumed VALUES (?,?)", ("x1-read", self.grant["attempt_id"]))
                except sqlite3.IntegrityError:
                    raise PermissionError("READ_TEST_CONSUMED") from None
        self.route = route
        self.view_diagnostic = None
        self.pending = request
        self.deadline = self.clock() + 12
        self.persist(
            command.request_id + "-dispatch",
            {
                "request_id": command.request_id,
                "operation": command.operation,
                "state": "DISPATCHED",
                "identity": "UNKNOWN",
            },
        )
        return {
            "kind": "READ_DISPATCH",
            "command": command.model_dump(),
            "route": route.model_dump(),
            "deadline": self.deadline,
            "attempt_id": self.grant["attempt_id"],
        }

    def persist(self, event_id, value):
        safe = {
            "protocol": 1,
            "tenant_id": TENANT,
            "actor": ACTOR,
            "timestamp": datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
            "production_writes": False,
            **value,
        }
        try:
            with ledger(self.repo) as db:
                db.execute(
                    "INSERT INTO x1_read_events VALUES (?,?,?)",
                    (event_id, self.grant["attempt_id"], json.dumps(safe)),
                )
        except Exception:
            raise PermissionError("READ_PERSIST_FAILED") from None
        return safe

    def fail(self, error):
        code = safe_code(error)
        self.stopped = True
        if self.pending:
            return self.persist(
                self.pending.command.request_id,
                {
                    "request_id": self.pending.command.request_id,
                    "operation": self.pending.command.operation,
                    "state": "STOPPED",
                    "error_code": code,
                    "identity": "UNKNOWN",
                    **({"view_contract": self.view_diagnostic} if self.view_diagnostic else {}),
                },
            )
        return {"state": "STOPPED", "error_code": code, "identity": "UNKNOWN", "production_writes": False}

    def finish(self, raw):
        self.check()
        value = Result.model_validate(raw)
        self.repo.consume_request(value.request_id)
        if not self.pending or value.command_request_id != self.pending.command.request_id:
            raise PermissionError("READ_SEQUENCE_INVALID")
        if self.clock() >= self.deadline:
            raise PermissionError("READ_TIMEOUT")
        if value.route != self.route:
            raise PermissionError("TAB_STATE_CHANGED")
        if self.index >= 1 and isinstance(value.evidence, dict) and "view_contract" in value.evidence:
            view = AscendLoadBoardViewContract.model_validate(value.evidence["view_contract"])
            self.view_diagnostic = view.model_dump()
            if value.error_code is None:
                view.require_active()
            elif set(value.evidence) != {"view_contract"}:
                raise PermissionError("RECEIPT_INVALID")
        if value.error_code is not None:
            raise PermissionError(safe_code(value.error_code))
        command = self.pending.command
        base = {
            "attempt_id": self.grant["attempt_id"],
            "request_id": command.request_id,
            "operation": command.operation,
            "state": "READ_ONLY_READY",
            "extension_pairing_verified": True,
            "selected_tab": {"tab_id": self.route.tab_id, "document_id": self.route.document_id},
            "eligible_tab_count": self.route.eligible_tab_count,
            "origin": self.route.origin,
            "path": self.route.path,
            "tenant_identity": "Booking Logistics",
            "tenant_identity_source": "OWNER_ATTESTED",
            **({"view_contract": self.view_diagnostic} if self.view_diagnostic else {}),
        }
        if self.index == 0:
            evidence = SessionEvidence.model_validate(value.evidence)
            markers = set(evidence.nav_markers)
            authenticated = (
                self.route.path in {"/", "/loads"}
                and not evidence.login_form_present
                and {"Dashboard", "Loads"} <= markers
                and len(markers) >= 4
            )
            if evidence.authenticated_app != authenticated:
                raise PermissionError("RECEIPT_INVALID")
            base.update(
                authenticated_app=authenticated,
                login_form_present=evidence.login_form_present,
                nav_markers=sorted(markers),
                source="live extension DOM",
            )
            if not authenticated:
                self.stopped = True
                base.update(state="STOPPED", error_code="SESSION_UNVERIFIED", identity="UNKNOWN")
        elif self.index == 1:
            evidence = BoardEvidence.model_validate(value.evidence)
            rows = sorted((r.model_dump() for r in evidence.rows), key=lambda r: int(r["load_id"]))
            revision = hashlib.sha256(canonical(rows)).hexdigest()
            pickups = {
                r["load_id"]
                for r in rows
                if local_date(r["pick_date"], "US") == date.fromisoformat(self.grant["service_date"])
            }
            deliveries = {
                r["load_id"]
                for r in rows
                if local_date(r["drop_date"], "US") == date.fromisoformat(self.grant["service_date"])
            }
            if (
                len({r["load_id"] for r in rows}) != len(rows)
                or evidence.board_hash != revision
                or pickups != set(self.grant["pickups"])
                or deliveries != set(self.grant["deliveries"])
            ):
                raise PermissionError("BOARD_MISMATCH")
            self.revision = revision
            base.update(
                source_view="ACTIVE_LOADS",
                coverage="VISIBLE_BOARD_ONLY",
                observed_row_count=len(rows),
                service_date_row_count=len(pickups | deliveries),
                board_hash=revision,
                pickups=sorted(pickups),
                deliveries=sorted(deliveries),
                load_ids=sorted(pickups | deliveries),
                pickup_count=len(pickups),
                delivery_count=len(deliveries),
                reconciliation_state="RECONCILED",
                service_date=self.grant["service_date"],
                classification_source="FreightDesk derived from provider board dates",
            )
        elif self.index == 2:
            evidence = FindEvidence.model_validate(value.evidence)
            if (
                evidence.load_id != command.load_id
                or evidence.board_hash != self.revision
                or evidence.exact_row is not True
            ):
                raise PermissionError("EXACT_LOAD_MISSING")
            base.update(load_id=command.load_id, exact_row=True, board_hash=self.revision)
        else:
            evidence = IdentityEvidence.model_validate(value.evidence)
            if evidence.expected_load_id != command.load_id or evidence.observed_load_id != command.load_id:
                raise PermissionError("DETAIL_IDENTITY_CONFLICT")
            if evidence.board_hash != self.revision:
                raise PermissionError("BOARD_CHANGED")
            if not all(
                v is True for v in (evidence.row_match, evidence.opener_belongs_to_row, evidence.unique_panel)
            ):
                raise PermissionError("RECEIPT_INVALID")
            supported = (
                evidence.detail_field_match
                if evidence.identity_strategy == "PROVIDER_DETAIL_FIELD"
                else (
                    evidence.newly_visible
                    and evidence.direct_panel_reference
                    and (
                        evidence.opener_identity_match
                        if evidence.identity_strategy == "PROVIDER_OPENER_IDENTITY"
                        else evidence.selection_transition
                    )
                )
            )
            if not supported:
                raise PermissionError("DETAIL_IDENTITY_MISSING")
            base.update(
                provider="AscendTMS",
                expected_load_id=command.load_id,
                observed_load_id=command.load_id,
                identity_strategy=evidence.identity_strategy,
                confidence="VERIFIED",
                source="live extension DOM",
                state="IDENTITY_VERIFIED_READS_BLOCKED",
                operational_extraction=False,
                board_hash=self.revision,
                identity_evidence=evidence.model_dump(
                    exclude={
                        "expected_load_id",
                        "observed_load_id",
                        "identity_strategy",
                        "confidence",
                        "board_hash",
                        "view_contract",
                    }
                ),
            )
        receipt = self.persist(command.request_id, base)
        self.pending = None
        self.index += 1
        return receipt
