"""Durable, owner-authorized coordination of the existing X1 metadata executor.

No browser API, selector, provider request, write action or credential lives here.
A persisted owner job is authority to coordinate bounded leases, not to expand them.
"""
import json
import math
import secrets
import sqlite3
from contextlib import contextmanager
from typing import Literal

from pydantic import Field, model_validator

from executors.ascend_extension.controller import Strict
from executors.ascend_extension.bridge_build import BUILD
from executors.ascend_extension.mapping_store import report_maps, require_mapping_validation
from executors.ascend_extension.runtime import RuntimeAccess, runtime_code
from executors.ascend_extension.workspace_contracts import AscendProviderMap, MappingSessionApproval

STAGES = (
    "PREFLIGHT", "WAITING_FOR_ASCEND", "WAITING_FOR_READ_JOB", "WAITING_FOR_OWNER_WORKSPACE", "VERIFY_SESSION", "RESOLVE_SCOPE", "ACQUIRE_MAPPING_LEASE", "CAPTURE_CURRENT_WORKSPACE_NOW",
    "RESOLVE_WORKSPACE", "VERIFY_WORKSPACE_IDENTITY", "CAPTURE_STARTING_SECTION", "DISCOVER_NAVIGATION",
    "OWNER_REVIEW_REQUIRED", "AUTO_MAP", "VALIDATE_CONTRACTS", "REPORT", "CLEANUP", "COMPLETE", "STOPPED",
)
MATURITY = ("UNKNOWN", "OBSERVED", "REVIEWED_NAVIGATION", "AUTO_MAP_VALIDATED", "READ_MAPPING_VALIDATED", "WRITE_MAPPING_VALIDATED")
SESSION_PROOF_SECONDS = 30
CAPTURE_DISPATCH_SECONDS = 8
CAPTURE_ACK_SECONDS = 3
CAPTURE_COMPLETE_SECONDS = 5
OWNER_PRESENCE_SECONDS = 3

TERMINAL = {"COMPLETE", "STOPPED"}
# These are owner hypotheses, not provider lifecycle classifications or navigable contracts.
OPERATIONS_VIEWS = {
    "PLANNING_LOADS": {"contract": "UNKNOWN", "lifecycle": "UNKNOWN"},
    "ACTIVE_LOADS": {"contract": "LIVE_VALIDATED", "coverage": "VISIBLE_BOARD_ONLY", "lifecycle": "UNKNOWN"},
    "READY_FOR_ACCOUNTING": {"contract": "UNKNOWN", "lifecycle": "UNKNOWN"},
}
ACTIONS = {
    "SIGN_IN_TO_ASCEND": "Open Ascend and sign in, then return to the load you want to map.",
    "SELECT_ASCEND_TAB": "Select the intended Ascend tab in X1.",
    "RELOAD_EXTENSION": "Reload the installed X1 extension and refresh the existing Ascend tab.",
    "OPEN_ASCEND": "Open Edge with the installed X1 extension and Ascend.",
    "OPEN_APPROVED_LOAD": "Open the next representative load in Ascend; capture will start automatically.",
    "OPEN_LOAD_WORKSPACE": "Open a load workspace in Ascend; capture will start automatically.",
    "VALIDATE_REPRESENTATIVE_COHORT": "Starting-section mapping is preserved. Validate a representative cohort to qualify automatic section traversal.",
    "REVIEW_NEW_NAVIGATION": "Review the proposed read-only section controls once to continue.",
    "REVIEW_OPERATIONS_SCOPE": "Planning and accounting view controls need provider verification before an operations-wide job.",
    "REVIEW_CAPTURE_FAILURE": "Review the preserved capture report before starting a new job.",
    "COMPLETE_ENROLLMENT": "Complete local X1 enrollment before mapping.",
    "RESUME_MAPPING": "Mapping is paused. Resume when ready.",
    "READ_JOB_ACTIVE": "Another active read job owns access. Finish or cancel that job first.",
    "FOCUS_ASCEND_WORKSPACE": "Return to the approved load workspace in Ascend. Mapping will continue when owner presence is verified.",
}


def failure_message(code):
    return {
        "CURRENT_LOAD_CAPTURE_NOT_DISPATCHED": "The current-workspace capture was queued but not dispatched within eight seconds. Access was closed.",
        "CAPTURE_ACKNOWLEDGEMENT_TIMEOUT": "The workspace executor did not acknowledge the dispatched capture within three seconds. Access was closed.",
        "WORKSPACE_CAPTURE_TIMEOUT": "The acknowledged workspace capture did not complete within five seconds. Access was closed.",
        "SESSION_PROOF_TIMEOUT": "Session verification did not finish within thirty seconds. Access was closed.",
        "NO_FOREGROUND_ASCEND_WORKSPACE": "The selected Ascend workspace was not foreground with owner presence when checked. Access was closed.",
        "EXPECTED_LOAD_NOT_OPEN": "The open workspace did not match the expected load. No structure was captured.",
        "STARTING_SECTION_MISMATCH": "The open section did not match the requested starting section. No structure was captured.",
        "READ_TIMEOUT": "Workspace capture did not finish within its deadline. The last completed stage and existing evidence were preserved.",
        "SESSION_UNVERIFIED": "Ascend session proof was lost. Mapping stopped and temporary access was closed.",
        "DOCUMENT_CHANGED": "The Ascend document binding changed. Mapping stopped and temporary access was closed.",
        "TAB_STATE_CHANGED": "The Ascend tab binding changed. Mapping stopped and temporary access was closed.",
        "CONTENT_SCRIPT_PORT_STALE": "The verified content connection was lost. Mapping stopped and temporary access was closed.",
        "WORKSPACE_CHANGED": "Workspace identity or provider structure changed. Mapping stopped for review.",
        "WORKSPACE_SECTION_UNVERIFIED": "The workspace was identified, but its current section was not uniquely established. Review the preserved structural predicate.",
        "COORDINATOR_FAILED": "Local mapping coordination failed. A sanitized failure receipt was preserved; inspect it before another job.",
        "WORKSPACE_SCOPE_DENIED": "The open workspace did not match the approved target. No mapping was accepted for that target.",
        "NOT_A_LOAD_WORKSPACE": "The selected Ascend page was not a verified load workspace. Open a load before a new mapping job.",
        "OWNER_CANCELLED": "Mapping was cancelled. Temporary access was closed and evidence was preserved.",
        "READ_LEASE_EXPIRED": "The approved mapping time ended. Temporary access was closed.",
        "RUNTIME_SEQUENCE_INVALID": "An unfinished step was found after restart. Access was closed without replaying it.",
    }.get(code, "Mapping stopped at a safety or execution gate. Evidence was preserved; review the report before starting again.")


def failed_predicate(job, code=None):
    """Use the most specific validated section receipt without changing its stop gate."""
    section = (job.get("diagnostic") or {}).get("section_diagnostic") or {}
    if (code or job.get("stop_code")) == "WORKSPACE_SECTION_UNVERIFIED":
        if section.get("v2_diagnostic"):
            return section["v2_diagnostic"]["predicate"]
        route = section.get("route_heading_diagnostic") or {}
        sibling = route.get("sibling_form_diagnostic") or {}
        specific = sibling.get("failed_predicate") or route.get("failed_predicate")
        if specific:
            return specific
    return section.get("failed_predicate") or job.get("failed_predicate")


class MappingIntent(Strict):
    causal_trace: bool = False
    scope: Literal["CURRENT_LOAD", "CURRENT_OPERATIONS", "VALIDATION_COHORT", "OWNER_NAVIGATION_OBSERVE"] = "CURRENT_LOAD"
    load_ids: list[str] | None = Field(default=None, min_length=3, max_length=5)
    expected_load_id: str | None = Field(default=None, pattern=r"^[0-9]{1,20}$")
    starting_section: Literal["Load Basics"] | None = None
    minutes: int = Field(default=10, ge=1, le=20)
    max_workspaces: int = Field(default=5, ge=1, le=20)
    max_sections: int = Field(default=40, ge=1, le=100)
    max_contracts: int = Field(default=1000, ge=1, le=3000)

    @model_validator(mode="after")
    def scope_binding(self):
        if self.scope == "VALIDATION_COHORT":
            if self.load_ids is None:
                raise ValueError("WORKSPACE_SCOPE_DENIED")
            MappingSessionApproval.exact_sample(self.load_ids)
        elif self.load_ids is not None:
            raise ValueError("WORKSPACE_SCOPE_DENIED")
        if self.expected_load_id and self.scope != "CURRENT_LOAD":
            raise ValueError("WORKSPACE_SCOPE_DENIED")
        if self.starting_section and not self.expected_load_id:
            raise ValueError("WORKSPACE_SCOPE_DENIED")
        return self


class MappingOrchestrator:
    def __init__(self, access: RuntimeAccess):
        self.access = access
        self.clock = access.clock
        self.path = access.repo.path("mapping-orchestrator.sqlite3")

    @contextmanager
    def database(self, *, readonly=False):
        if readonly:
            db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                if not readonly:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, job_id TEXT, body TEXT)")
                    for verb in ("UPDATE", "DELETE"):
                        db.execute(f"CREATE TRIGGER IF NOT EXISTS events_no_{verb} BEFORE {verb} ON events BEGIN SELECT RAISE(ABORT,'append_only_mapping_audit'); END")
                    db.execute("CREATE TRIGGER IF NOT EXISTS jobs_no_delete BEFORE DELETE ON jobs BEGIN SELECT RAISE(ABORT,'preserve_mapping_jobs'); END")
                yield db
        finally:
            db.close()

    @staticmethod
    def _load(db):
        row = db.execute("SELECT body FROM jobs ORDER BY rowid DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def _save(self, db, job):
        db.execute("INSERT INTO jobs VALUES (?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body", (job["id"], json.dumps(job)))

    def _stage(self, db, job, stage, action=None):
        if stage not in STAGES or action is not None and action not in ACTIONS:
            raise ValueError("MAPPING_CONTRACT_INVALID")
        if job.get("stage") == stage and job.get("action") == action:
            return
        job.update(stage=stage, action=action, updated_at=self.clock())
        db.execute("INSERT INTO events(job_id,body) VALUES (?,?)", (job["id"], json.dumps({
            "stage": stage, "action": action, "at": self.clock(), "production_writes": False})))
        self._save(db, job)

    def start(self, intent=None, *, owner_authorized=False):
        self.access._owner(owner_authorized)
        intent = MappingIntent.model_validate(intent or {})
        with self.database() as db:
            prior = self._load(db)
            if prior and prior["stage"] not in TERMINAL:
                # A repeated click/restart resumes the existing job, never consumes a second attempt.
                return self._public(prior)
            job = dict(id=secrets.token_hex(16), owner_authorized=True, intent=intent.model_dump(), stage=None,
                started_at=self.clock(), deadline=self.clock()+intent.minutes*60, session_ids=[], lease_session=None,
                processed_versions=[], maps=[], cycles=[], observed_ids=[], review_sections=[], maturity="UNKNOWN",
                navigation_reviewed=False, drift=False, stop_code=None, failed_predicate=None, retry_safe=False, paused=False,
                capture_dispatch_state="NOT_REQUESTED", capture_requested_at=None, capture_dispatched_at=None, capture_acknowledged_at=None, capture_completed_at=None,
                cleanup_complete=False, report_ready=False, diagnostic=None, preflight={}, capture_pending=False, mode="OBSERVE", active_load=None,
                wake_pending=True, pending_capture_ready=False, session_requested_at=None, owner_presence_verified_at=None,
                recovery_count=0, await_owner_change=False, change_marker=None, production_writes=False, values_included=False)
            self._stage(db, job, "PREFLIGHT")
        return self.tick()

    def _lease_matches(self, job):
        return self.access.status().get("mapping_session_id") in job["session_ids"]

    def _close(self, job):
        # Never revoke a different job's authority after cancellation/restart races.
        if self._lease_matches(job):
            self.access.disable(owner_authorized=True, expected_mapping_session_ids=tuple(job["session_ids"]))
            job["wake_pending"] = True
        job["lease_session"] = None
        job["capture_pending"] = False
        job["cleanup_complete"] = True

    def _finish(self, db, job, code=None, action=None):
        job.update(stop_code=code, retry_safe=False, report_ready=True)
        self._stage(db, job, "REPORT")
        self._stage(db, job, "CLEANUP")
        self._close(job)
        self._stage(db, job, "STOPPED" if code else "COMPLETE", action)

    def _failure(self, db, job, code="COORDINATOR_FAILED"):
        """Persist only fixed codes and stages, including when cleanup itself fails."""
        diagnostic = job.get("diagnostic") or {}
        receipt = {"stage": job["stage"], "last_completed_dom_stage": diagnostic.get("stage"),
            "safe_stop_code": code, "failed_predicate": failed_predicate(job, code),
            "at": self.clock(), "production_writes": False}
        db.execute("INSERT INTO events(job_id,body) VALUES (?,?)", (job["id"], json.dumps(receipt)))
        job.update(stop_code=code, failure_receipt=receipt, report_ready=True, retry_safe=False)
        self._stage(db, job, "CLEANUP")
        try:
            self._close(job)
        except Exception:
            # Independent host policy still expires the lease; never claim cleanup succeeded.
            job["cleanup_complete"] = False
        self._stage(db, job, "STOPPED", "REVIEW_CAPTURE_FAILURE")
        self._save(db, job)

    def coordinator_failed(self, code="COORDINATOR_FAILED"):
        """Last-resort API/CLI loop boundary; no exception text reaches audit or output."""
        code = code if code == "COORDINATOR_FAILED" else runtime_code(code)
        if not self.path.exists():
            return {"status": "STOPPED", "stage": "STOPPED", "safe_stop_code": code,
                "last_completed_dom_stage": None, "failed_predicate": None, "owner_action": "REVIEW_CAPTURE_FAILURE",
                "owner_action_text": ACTIONS["REVIEW_CAPTURE_FAILURE"], "cleanup_state": "UNKNOWN",
                "cleanup_complete": False, "production_writes": False}
        with self.database() as db:
            job = self._load(db)
            if job and job["stage"] not in TERMINAL:
                self._failure(db, job, code)
            response = self._public(job)
        try:
            self._notify_committed()
        except Exception:
            # Preserve the committed failure receipt if the wake outbox is unavailable.
            # Pending notification remains durable; authority is never expanded here.
            pass
        return response

    def _notify_committed(self):
        # The notification is emitted only after the durable job/queue transaction commits.
        with self.database() as db:
            job = self._load(db)
            if not job or not job.get("wake_pending"):
                return
            if job["intent"].get("causal_trace", False) and not job.get("job_committed_traced") and self._lease_matches(job):
                self.access.causal_event("JOB_COMMITTED", metadata={"source": "COORDINATOR"})
                job["job_committed_traced"] = True
            self.access.notify_mapping_job()
            job["wake_pending"] = False
            self._save(db, job)

    def _wait(self, db, job, action):
        self._close(job)
        job["report_ready"] = bool(job["maps"])
        self._stage(db, job, "OWNER_REVIEW_REQUIRED", action)

    def _new_lease(self, db, job, *, probe=False, auto=False):
        generation = None
        if self.access.path.exists():
            with self.access.database(readonly=True) as runtime_db:
                state, previous = self.access._load(runtime_db)
            status = self.access._project(state, previous)
            generation = previous["generation"] if previous else None
        else:
            status = self.access.status()
        if status["read_access"] == "ENABLED" and status.get("mapping_session_id") not in job["session_ids"]:
            self._defer_lease(db, job, probe=probe, auto=auto)
            return False
        self._close(job)
        sid = "owner-x1-mapping-orch-" + secrets.token_hex(12)
        job["session_ids"].append(sid)
        job.update(lease_session=sid, session_requested_at=None, probe_pending=probe, cleanup_complete=False,
            capture_pending=False, pending_capture_ready=False, wake_pending=True, mode="AUTO_MAP" if auto else "OBSERVE")
        # Persist intent BEFORE granting: crash recovery can identify and close/adopt this exact lease.
        self._save(db, job)
        intent = job["intent"]
        remaining = max(1, min(20, math.ceil((job["deadline"]-self.clock())/60)))
        ids = intent["load_ids"] if intent["scope"] == "VALIDATION_COHORT" else [job["active_load"]] if job["active_load"] else [intent["expected_load_id"]] if intent["expected_load_id"] else None
        approval = MappingSessionApproval(session_id=sid, orchestrated=True, causal_trace=intent.get("causal_trace", False),
            session_only=probe, orchestrator_job_id=job["id"], authority_expires_at=float(job["deadline"]),
            capture_load_id=intent["expected_load_id"] if not auto else None, capture_section=intent["starting_section"] if not auto else None,
            mode="FIRST_VALIDATION" if intent["scope"] == "VALIDATION_COHORT" else "NORMAL_OWNER_PRESENT",
            operation_mode="AUTO_MAP" if auto else "OBSERVE", approved_load_ids=ids,
            minutes=min(2, remaining) if probe else remaining, max_captures=min(300, intent["max_sections"]+20),
            max_workspace_captures=intent["max_workspaces"], max_section_observations=intent["max_sections"],
            max_contract_observations=intent["max_contracts"])
        try:
            self.access.enable(mapping=approval, owner_authorized=True, expected_previous_generation=generation)
        except PermissionError as error:
            if error.args != ("READ_JOB_ACTIVE",):
                raise
            # The guarded runtime transaction created neither a grant nor a mapping session.
            job["session_ids"].remove(sid)
            self._defer_lease(db, job, probe=probe, auto=auto)
            return False
        # Clamp rounded-up minutes to the original owner deadline; no unbounded renewals.
        job["lease_session"] = sid
        job.pop("lease_continuation", None)
        return True

    def _defer_lease(self, db, job, *, probe, auto):
        job.update(lease_continuation={"probe": probe, "auto": auto}, lease_session=None,
            capture_pending=False, pending_capture_ready=False, cleanup_complete=True, wake_pending=True)
        self._stage(db, job, "WAITING_FOR_READ_JOB", "READ_JOB_ACTIVE")

    def _resume_lease(self, db, job):
        continuation = job.get("lease_continuation", {"probe": True, "auto": False})
        if not self._new_lease(db, job, **continuation):
            return
        if continuation["probe"] or not self._queue_capture(job):
            self._wait_for_owner(db, job)
        else:
            self._stage(db, job, "AUTO_MAP" if continuation["auto"] else "CAPTURE_CURRENT_WORKSPACE_NOW"
                if job["intent"]["scope"] == "CURRENT_LOAD" else "RESOLVE_WORKSPACE")

    def _queue_capture(self, job):
        if not self._owner_ready(self.access.status()):
            job["pending_capture_ready"] = True
            return False
        requested_at = self.clock()
        status = self.access.request_mapping_capture(owner_authorized=True, expected_mapping_session_id=job["lease_session"])
        if job["intent"].get("causal_trace", False):
            self.access.causal_event("CAPTURE_QUEUED", metadata={"source": "COORDINATOR"})
        job.update(capture_requested_at=requested_at, capture_dispatched_at=None, capture_acknowledged_at=None,
                   capture_completed_at=None, capture_dispatch_state="QUEUED", failed_predicate=None)
        job["capture_floor"] = status.get("mapping_capture_count", 0)
        job["capture_pending"] = True
        job["pending_capture_ready"] = False
        job["wake_pending"] = True
        return True

    def _owner_ready(self, status):
        verified_at = status.get("owner_presence_verified_at")
        return (status.get("owner_present") is True and isinstance(verified_at, (int, float))
            and 0 <= self.clock() - verified_at <= OWNER_PRESENCE_SECONDS)

    def _wait_for_owner(self, db, job):
        self._stage(db, job, "WAITING_FOR_OWNER_WORKSPACE", "FOCUS_ASCEND_WORKSPACE")

    def _records(self, job):
        if not self.access.path.exists():
            return [], []
        from executors.ascend_extension.mapping_store import _bounded_records
        sessions = job['session_ids']
        if not sessions:
            return [], []
        placeholders = ','.join('?' for _ in sessions)
        with self.access.database(readonly=True) as db:
            records = _bounded_records(db.execute(f"SELECT body FROM runtime_provider_maps WHERE json_extract(body,'$.session_id') IN ({placeholders}) ORDER BY id LIMIT 4097", sessions))
            cycles = _bounded_records(db.execute(f"SELECT body FROM runtime_auto_map_cycles WHERE json_extract(body,'$.session_id') IN ({placeholders}) ORDER BY id LIMIT 4097", sessions))
        return records, cycles

    def _navigation_available(self, observed):
        from executors.ascend_extension.auto_map import plan_auto_map
        try:
            with self.access.database(readonly=True) as db:
                plan_auto_map(db, {}, observed.model_dump())
            return True
        except PermissionError:
            return False

    def _auto_qualified(self, job):
        if job["intent"]["scope"] == "VALIDATION_COHORT":
            return True  # The controlled cohort is the validation procedure, never a qualification claim.
        try:
            with self.access.database(readonly=True) as db:
                require_mapping_validation(db)
            return True
        except PermissionError:
            return False

    def _consume_maps(self, db, job):
        records, cycles = self._records(job)
        job["cycles"] = cycles
        for record in records:
            if record["provider_map_version"] in job["processed_versions"]:
                continue
            m = AscendProviderMap.model_validate(record["map"])
            intent = job["intent"]
            if (intent["expected_load_id"] and m.workspace.load_id != intent["expected_load_id"]
                or intent["starting_section"] and not job["maps"] and m.section.section != intent["starting_section"]):
                raise PermissionError("WORKSPACE_SCOPE_DENIED")
            if job["active_load"] and m.workspace.load_id != job["active_load"]:
                raise PermissionError("WORKSPACE_CHANGED")
            job["capture_pending"] = False
            completed = {c["load_id"] for c in job["cycles"] if c["returned_to_start"]}
            if job["active_load"] is None and m.workspace.load_id in completed:
                # Owner revisited an already mapped workspace. Cancel the unexecuted read plan;
                # never traverse it again or fabricate a new workspace boundary.
                with self.access.database() as runtime_db:
                    state, current = self.access._load(runtime_db)
                    if current["mapping"]["session_id"] != job["lease_session"]:
                        raise PermissionError("READ_LEASE_REVOKED")
                    state["auto_plan"] = None
                    self.access._save(runtime_db, state)
                job["processed_versions"].append(record["provider_map_version"])
                job["await_owner_change"] = True
                job["change_marker"] = self.access.status().get("mapping_owner_change_at")
                continue
            self._stage(db, job, "VERIFY_WORKSPACE_IDENTITY")
            self._stage(db, job, "CAPTURE_STARTING_SECTION")
            job["processed_versions"].append(record["provider_map_version"])
            job["maps"].append(record)
            job["observed_ids"] = sorted(set(job["observed_ids"]+[m.workspace.load_id]))
            job["maturity"] = "OBSERVED"
            if record["structural_drift"]:
                job["drift"] = True
                raise PermissionError("WORKSPACE_CHANGED")
            if (len(job["observed_ids"]) > intent["max_workspaces"] or len(job["maps"]) > intent["max_sections"]
                or sum(len(r["map"]["section"]["fields"]) for r in job["maps"]) > intent["max_contracts"]):
                raise PermissionError("MAPPING_CONTRACT_BOUND")
            self._stage(db, job, "DISCOVER_NAVIGATION")
            if intent["scope"] == "OWNER_NAVIGATION_OBSERVE":
                job["await_owner_change"] = True
                job["change_marker"] = self.access.status().get("mapping_owner_change_at")
                self._stage(db, job, "RESOLVE_WORKSPACE")
                continue
            job["active_load"] = m.workspace.load_id
            nav = self._navigation_available(m)
            if nav:
                job["navigation_reviewed"] = True
                job["maturity"] = "REVIEWED_NAVIGATION"
            if job["mode"] == "AUTO_MAP":
                self._stage(db, job, "AUTO_MAP")
                if any(c["load_id"] == m.workspace.load_id and c["returned_to_start"] for c in cycles):
                    self._complete_workspace(db, job)
                continue
            if not nav:
                from executors.ascend_extension.auto_map import navigation_review_candidates
                job["review_sections"] = navigation_review_candidates(m)
                self._wait(db, job, "REVIEW_NEW_NAVIGATION")
                return
            if not self._auto_qualified(job):
                self._stage(db, job, "VALIDATE_CONTRACTS")
                self._finish(db, job, action="VALIDATE_REPRESENTATIVE_COHORT")
                return
            if not self._new_lease(db, job, auto=True):
                return
            if self._queue_capture(job):
                self._stage(db, job, "AUTO_MAP")
            else:
                self._wait_for_owner(db, job)
            return

    def _complete_workspace(self, db, job):
        self._stage(db, job, "VALIDATE_CONTRACTS")
        intent = job["intent"]
        completed = {c["load_id"] for c in job["cycles"] if c["returned_to_start"]}
        if intent["scope"] == "VALIDATION_COHORT" and completed != set(intent["load_ids"]):
            job["active_load"] = None
            job["await_owner_change"] = True
            job["change_marker"] = self.access.status().get("mapping_owner_change_at")
            self._stage(db, job, "RESOLVE_WORKSPACE", "OPEN_APPROVED_LOAD")
        else:
            if intent["scope"] == "VALIDATION_COHORT":
                self._qualify_cohort(job)
            job["maturity"] = "AUTO_MAP_VALIDATED"
            self._finish(db, job)

    def _qualify_cohort(self, job):
        # Every cohort member must have a fresh, build-matched, provider-verified return cycle.
        ids = set(job["intent"]["load_ids"])
        for load_id in ids:
            cycles = [c for c in job["cycles"] if c["load_id"] == load_id and c["returned_to_start"]]
            if not cycles or len(set(cycles[-1]["sections"])) < 2:
                raise PermissionError("MAPPING_VALIDATION_REQUIRED")
            records = [r for r in job["maps"] if r["map"]["workspace"]["load_id"] == load_id]
            if not records or any(r.get("build") != BUILD or r["structural_drift"] for r in records):
                raise PermissionError("MAPPING_VALIDATION_REQUIRED")
        with self.access.database() as runtime_db:
            receipt = {"mapper_version": 1, "operation_mode": "AUTO_MAP", "build": BUILD,
                "review_source": "OWNER_AUTHORIZED_COHORT_PROVIDER_RETURN_RECEIPTS", "job_id": job["id"],
                "session_ids": job["session_ids"], "reviewed_at": self.clock(), "normal_auto_map_qualified": True,
                "field_read_mappings_activated": False, "production_writes": False}
            runtime_db.execute("INSERT OR IGNORE INTO runtime_mapping_validations VALUES (?,?)", (job["id"], json.dumps(receipt)))

    def tick(self):
        try:
            result = self._tick()
            if self.path.exists():
                self._notify_committed()
            return result
        except Exception as error:
            code = runtime_code(error) if isinstance(error, PermissionError) else "COORDINATOR_FAILED"
            return self.coordinator_failed(code)

    def _tick(self):
        # Startup and ordinary status are inert until the owner has created a durable job.
        if not self.path.exists():
            return self.status()
        with self.database() as db:
            job = self._load(db)
            if not job or job["stage"] in TERMINAL or job["paused"]:
                return self._public(job)
            try:
                self.access.gate(self.access.repo)
                self.access.enrollment_guard()
                status = self.access.status()
                if self.access.path.exists():
                    with self.access.database(readonly=True) as runtime_db:
                        checkpoint, lease = self.access._load(runtime_db)
                    if lease and lease.get("mapping", {}).get("orchestrator_job_id") == job["id"]:
                        sid = lease["mapping"]["session_id"]
                        if sid not in job["session_ids"]:
                            job["session_ids"].append(sid)
                            job["lease_session"] = sid
                            # Grant/queue may have committed before the coordinator checkpoint.
                            # Preserve evidence, close authority; never replay uncertain capture work.
                            raise PermissionError("RUNTIME_SEQUENCE_INVALID")
                if status["paused"]:
                    self._wait(db, job, "RESUME_MAPPING")
                    job["paused"] = True
                elif self.clock() >= job["deadline"]:
                    self._finish(db, job, None if job["intent"]["scope"] == "OWNER_NAVIGATION_OBSERVE" and job["maps"] else "READ_LEASE_EXPIRED")
                elif status["read_access"] == "ENABLED" and not job["lease_session"] and status.get("mapping_session_id") in job["session_ids"]:
                    raise PermissionError("RUNTIME_SEQUENCE_INVALID")
                elif job["stage"] == "WAITING_FOR_READ_JOB" or job["stage"] == "OWNER_REVIEW_REQUIRED" and job.get("action") == "READ_JOB_ACTIVE":
                    if status["read_access"] != "ENABLED":
                        if job.get("lease_continuation"):
                            self._resume_lease(db, job)
                        else:
                            self._stage(db, job, "PREFLIGHT")
                            self._preflight(db, job, status)
                    else:
                        self._stage(db, job, "WAITING_FOR_READ_JOB", "READ_JOB_ACTIVE")
                elif job["stage"] == "OWNER_REVIEW_REQUIRED":
                    pass  # No lease, browser reads or auto-approval while waiting for review.
                elif job["stage"] in {"PREFLIGHT", "WAITING_FOR_ASCEND"}:
                    self._preflight(db, job, status)
                elif job["stage"] == "RESOLVE_WORKSPACE" and job["lease_session"] is None:
                    if self._new_lease(db, job, probe=True):
                        self._wait_for_owner(db, job)
                else:
                    self._advance(db, job, status)
            except Exception as error:
                self._failure(db, job, runtime_code(error) if isinstance(error, PermissionError) else "COORDINATOR_FAILED")
            self._save(db, job)
            return self._public(job)

    def _preflight(self, db, job, status):
        job["preflight"] = {"enrollment_verified": True, "extension_connected": status["extension"] == "CONNECTED",
            "native_host_connected": status["native_host"] == "CONNECTED", "pairing_valid": status["pairing"] == "VALID",
            "paused": status["paused"], "eligible_tab_count": status.get("eligible_tab_count")}
        if not job["session_ids"]:
            if status["read_access"] == "ENABLED":
                self._stage(db, job, "WAITING_FOR_READ_JOB", "READ_JOB_ACTIVE")
                return  # Never revoke authority belonging to another owner read job.
            if status["extension"] != "CONNECTED" or status["native_host"] != "CONNECTED" or status["pairing"] != "VALID":
                self._stage(db, job, "WAITING_FOR_ASCEND", "OPEN_ASCEND")
                return
        if self._new_lease(db, job, probe=True):
            self._wait_for_owner(db, job)

    def _sync_capture(self, job):
        if not job.get("capture_requested_at") or not self.access.path.exists():
            return
        with self.access.database(readonly=True) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='runtime_capture_events'").fetchone():
                return
            records = [json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_capture_events WHERE json_extract(body,'$.session_id')=? ORDER BY id", (job["lease_session"],))]
        fields = {"DISPATCHED": "capture_dispatched_at", "ACKNOWLEDGED": "capture_acknowledged_at", "COMPLETED": "capture_completed_at"}
        for event in records:
            if event["at"] >= job["capture_requested_at"]:
                job[fields[event["state"]]] = event["at"]
                job["capture_dispatch_state"] = event["state"]

    def _capture_deadline(self, job, status):
        if job["intent"]["scope"] != "CURRENT_LOAD":
            return
        now = self.clock()
        if (status["session"] != "AUTHENTICATED" and job.get("probe_pending")
            and job.get("session_requested_at") is not None and now-job["session_requested_at"] >= SESSION_PROOF_SECONDS):
            raise PermissionError("SESSION_PROOF_TIMEOUT")
        if not job["capture_pending"] or job.get("capture_completed_at") is not None:
            return
        dispatched, acknowledged = job.get("capture_dispatched_at"), job.get("capture_acknowledged_at")
        if dispatched is None and now-job["capture_requested_at"] >= CAPTURE_DISPATCH_SECONDS:
            raise PermissionError("CURRENT_LOAD_CAPTURE_NOT_DISPATCHED")
        if dispatched is not None and acknowledged is None and now-dispatched >= CAPTURE_ACK_SECONDS:
            raise PermissionError("CAPTURE_ACKNOWLEDGEMENT_TIMEOUT")
        if acknowledged is not None and now-acknowledged >= CAPTURE_COMPLETE_SECONDS:
            raise PermissionError("WORKSPACE_CAPTURE_TIMEOUT")

    def _advance(self, db, job, status):
        self._sync_capture(job)
        from executors.ascend_extension.mapping_diagnostics import MappingDiagnostic
        if status.get("mapping_diagnostic"):
            job["diagnostic"] = MappingDiagnostic.model_validate(status["mapping_diagnostic"]).model_dump()
        if not self._lease_matches(job):
            raise PermissionError("READ_LEASE_REVOKED")
        if status["read_access"] in {"REVOKED", "DISABLED"}:
            raise PermissionError("READ_LEASE_REVOKED")
        if status["read_access"] == "EXPIRED":
            self._capture_deadline(job, status)
            if job.get("probe_pending") and not job["capture_pending"] and job["recovery_count"] < 1:
                job["recovery_count"] += 1
                if self._new_lease(db, job, probe=True):
                    self._stage(db, job, "VERIFY_SESSION", "OPEN_ASCEND")
                return
            raise PermissionError("READ_LEASE_EXPIRED")
        if status["error_code"] in {"PROTOCOL_VERSION_MISMATCH", "CONTENT_SCRIPT_OLD_VERSION", "CONTENT_SCRIPT_INJECTION_BLOCKED", "CONTENT_SCRIPT_RECOVERY_FAILED"}:
            self._finish(db, job, status["error_code"], "RELOAD_EXTENSION")
            return
        if status["error_code"] in {"MAPPING_OWNER_NOT_PRESENT", "NO_FOREGROUND_ASCEND_WORKSPACE"}:
            if job["capture_pending"] or job["mode"] == "AUTO_MAP":
                raise PermissionError("NO_FOREGROUND_ASCEND_WORKSPACE")
            self._wait_for_owner(db, job)
            return
        # The existing executor owns its bounded content recovery. Never retry a capture after loss.
        if status["state"] == "STOPPED":
            raise PermissionError(status["error_code"] or "READ_EXECUTION_FAILED")
        self._capture_deadline(job, status)
        if not job["capture_pending"] and not self._owner_ready(status):
            self._wait_for_owner(db, job)
            return
        if job.get("probe_pending") and job.get("session_requested_at") is None:
            job["session_requested_at"] = self.clock()
        if status["extension"] != "CONNECTED" or status["native_host"] != "CONNECTED":
            if job["capture_pending"] or job["mode"] == "AUTO_MAP":
                raise PermissionError("CONTENT_SCRIPT_PORT_STALE")
            self._stage(db, job, "VERIFY_SESSION", "OPEN_ASCEND")
            return
        if status["session"] != "AUTHENTICATED":
            if job["capture_pending"] and status["error_code"] not in {None, "NAVIGATION_STARTED"}:
                code = runtime_code(status["error_code"])
                predicate = {"DOCUMENT_CHANGED": "DOCUMENT_BINDING_CHANGED", "TAB_STATE_CHANGED": "TAB_BINDING_CHANGED",
                    "CONTENT_SCRIPT_PORT_STALE": "CONTENT_CONNECTION_LOST", "CONTENT_SCRIPT_MISSING": "CONTENT_CONNECTION_MISSING",
                    "TAB_SELECTION_REQUIRED": "TAB_SELECTION_UNVERIFIED", "ASCEND_REAUTH_REQUIRED": "PROVIDER_SESSION_REJECTED",
                    "SESSION_UNVERIFIED": "SESSION_PROOF_REJECTED"}.get(code, "RUNTIME_ERROR_DURING_SESSION_REPROOF")
                job["failed_predicate"] = predicate + ("_BEFORE_CAPTURE_DISPATCH" if job.get("capture_dispatched_at") is None else "_AFTER_CAPTURE_DISPATCH")
                raise PermissionError(code)
            action = "SELECT_ASCEND_TAB" if status["state"] == "TAB_SELECTION_REQUIRED" else "SIGN_IN_TO_ASCEND" if status["state"] == "ASCEND_REAUTH_REQUIRED" else None
            self._stage(db, job, "VERIFY_SESSION", action)
            return
        if job.get("probe_pending"):
            handshake = status.get("document_handshake")
            if not handshake or any(handshake.get(k) != v for k, v in BUILD.items()) or handshake.get("content_script_version") != BUILD["extension_version"]:
                self._finish(db, job, "PROTOCOL_VERSION_MISMATCH", "RELOAD_EXTENSION")
                return
            self._stage(db, job, "RESOLVE_SCOPE")
            if job["intent"]["scope"] == "CURRENT_OPERATIONS":
                self._wait(db, job, "REVIEW_OPERATIONS_SCOPE")
                return
            # A probe lease cannot dispatch MAP. Replace it only after fresh provider session proof.
            self._stage(db, job, "ACQUIRE_MAPPING_LEASE")
            if not self._new_lease(db, job):
                return
            if self._queue_capture(job):
                self._stage(db, job, "CAPTURE_CURRENT_WORKSPACE_NOW" if job["intent"]["scope"] == "CURRENT_LOAD" else "RESOLVE_WORKSPACE")
            else:
                self._wait_for_owner(db, job)
            return
        if job.get("pending_capture_ready"):
            if not self._queue_capture(job):
                self._wait_for_owner(db, job)
                return
            self._stage(db, job, "CAPTURE_CURRENT_WORKSPACE_NOW" if job["intent"]["scope"] == "CURRENT_LOAD" else "AUTO_MAP" if job["mode"] == "AUTO_MAP" else "RESOLVE_WORKSPACE")
        if job["stage"] in {"VERIFY_SESSION", "WAITING_FOR_OWNER_WORKSPACE"}:
            self._stage(db, job, "AUTO_MAP" if job["mode"] == "AUTO_MAP" else "RESOLVE_WORKSPACE")
        self._consume_maps(db, job)
        if job["capture_pending"] and status.get("mapping_noop") and status.get("mapping_capture_count", 0) > job.get("capture_floor", 0):
            with self.access.database(readonly=True) as runtime_db:
                checkpoint, _ = self.access._load(runtime_db)
            if checkpoint["pending"] is None and not checkpoint.get("mapping_capture_requested"):
                job["capture_pending"] = False
                job["await_owner_change"] = True
                job["change_marker"] = status.get("mapping_owner_change_at")
        if job["stage"] in TERMINAL or job["stage"] == "OWNER_REVIEW_REQUIRED":
            return
        if job["await_owner_change"] and not job["capture_pending"] and status.get("mapping_owner_change_at") != job["change_marker"]:
            if not self._queue_capture(job):
                self._wait_for_owner(db, job)
                return
            job["await_owner_change"] = False
            job["change_marker"] = status.get("mapping_owner_change_at")
        diagnostic = status.get("mapping_diagnostic") or {}
        stages = {"ENTITY_DISCOVERY": "RESOLVE_WORKSPACE", "LOAD_WORKSPACE_CANDIDATE_FOUND": "VERIFY_WORKSPACE_IDENTITY", "WORKSPACE_IDENTITY_VERIFIED": "VERIFY_WORKSPACE_IDENTITY", "SECTION_IDENTIFIED": "CAPTURE_STARTING_SECTION", "STRUCTURE_CAPTURED": "CAPTURE_STARTING_SECTION"}
        if job["capture_pending"] and job["mode"] == "OBSERVE" and diagnostic.get("stage") in stages:
            self._stage(db, job, stages[diagnostic["stage"]])

    def review(self, sections, *, owner_authorized=False):
        self.access._owner(owner_authorized)
        from executors.ascend_extension.auto_map import approve_observed_navigation
        with self.database() as db:
            job = self._load(db)
            if not job or job["stage"] != "OWNER_REVIEW_REQUIRED" or job["action"] != "REVIEW_NEW_NAVIGATION" or not job["maps"]:
                raise PermissionError("NAVIGATION_CONTRACT_UNVERIFIED")
            if self.clock() >= job["deadline"]:
                self._finish(db, job, "READ_LEASE_EXPIRED")
            else:
                if not sections or not set(sections) <= set(job["review_sections"]):
                    raise PermissionError("NAVIGATION_CONTRACT_UNVERIFIED")
                record = job["maps"][-1]
                approve_observed_navigation(self.access, record["provider_map_version"], sections, owner_authorized=True)
                job.update(navigation_reviewed=True, maturity="REVIEWED_NAVIGATION")
                if self._auto_qualified(job):
                    if self._new_lease(db, job, auto=True):
                        if self._queue_capture(job):
                            self._stage(db, job, "AUTO_MAP")
                        else:
                            self._wait_for_owner(db, job)
                else:
                    # A current-load observation does not silently qualify general AUTO_MAP.
                    self._stage(db, job, "VALIDATE_CONTRACTS")
                    self._finish(db, job, action="VALIDATE_REPRESENTATIVE_COHORT")
            self._save(db, job)
            response = self._public(job)
        self._notify_committed()
        return response

    def control(self, action, *, owner_authorized=False):
        self.access._owner(owner_authorized)
        if action not in {"cancel", "pause", "resume"}:
            raise PermissionError("RUNTIME_SCOPE_INVALID")
        with self.database() as db:
            job = self._load(db)
            if not job or job["stage"] in TERMINAL:
                return self._public(job)
            if action == "cancel":
                self._finish(db, job, "OWNER_CANCELLED")
            elif action == "pause":
                job["paused"] = True
                self._wait(db, job, "RESUME_MAPPING")
            elif job["paused"]:
                job["paused"] = False
                job["wake_pending"] = True
                self._stage(db, job, "PREFLIGHT")
            self._save(db, job)
        return self.tick()

    def provider_maps(self):
        from integrations.ascend.provider_map_bundle import ProviderMapBundle
        if not self.path.exists():
            return ProviderMapBundle((), "UNKNOWN")
        with self.database(readonly=True) as db:
            job = self._load(db)
        return ProviderMapBundle(tuple(AscendProviderMap.model_validate(r["map"]) for r in job["maps"]), job["maturity"])

    def status(self, *, advanced=False):
        if not self.path.exists():
            return self._public(None)
        with self.database(readonly=True) as db:
            job = self._load(db)
            output = self._public(job)
            if advanced and job:
                output["advanced"] = {"job_id": job["id"], "session_ids": job["session_ids"], "stop_code": job["stop_code"], "diagnostic": job.get("diagnostic"), "preflight": job.get("preflight"),
                    "events": [json.loads(r[0]) for r in db.execute("SELECT body FROM events WHERE job_id=? ORDER BY seq", (job["id"],))]}
            return output

    def report(self, *, advanced=False):
        if not self.path.exists():
            return self.status()
        with self.database(readonly=True) as db:
            job = self._load(db)
        output = self._public(job)
        if job:
            output["contracts"] = [{"version": r["provider_map_version"], "load_id": r["map"]["workspace"]["load_id"],
                "section": r["map"]["section"]["section"], "field_count": len(r["map"]["section"]["fields"]), "activation": "CANDIDATE_ONLY"} for r in job["maps"]]
            output["operations_views"] = OPERATIONS_VIEWS
            if advanced:
                output["advanced_reports"] = [report_maps(self.access, sid) for sid in job["session_ids"]]
        return output

    @staticmethod
    def _public(job):
        if not job:
            return {"status": "IDLE", "stage": "PREFLIGHT", "message": "Choose what to map, then select Map Ascend.",
                "safe_stop_code": None, "last_completed_dom_stage": None, "failed_predicate": None,
                "owner_action": None, "owner_action_text": None, "cleanup_state": "NOT_REQUIRED", "production_writes": False}
        diagnostic = job.get("diagnostic") or {}
        return {"status": "PAUSED" if job["paused"] else job["stage"], "stage": job["stage"], "scope": job["intent"]["scope"],
            "workspaces_observed": len(job["observed_ids"]), "sections_observed": len({(r["map"]["workspace"]["load_id"],r["map"]["section"]["section"]) for r in job["maps"]}),
            "contracts_proposed": sum(len(r["map"]["section"]["fields"]) for r in job["maps"]), "contracts_validated": 0,
            **{k: job.get(k) for k in ("capture_dispatch_state", "capture_requested_at", "capture_dispatched_at", "capture_acknowledged_at", "capture_completed_at")},
            "coverage": "VERIFIED_SECTION_RETURN_CYCLES" if job["maturity"] == "AUTO_MAP_VALIDATED" else "OBSERVED_SECTIONS_ONLY",
            "maturity": job["maturity"], "drift_detected": job["drift"], "needs_review": job["stage"] == "OWNER_REVIEW_REQUIRED",
            "review_sections": job["review_sections"], "owner_action": job.get("action"),
            "owner_action_text": ACTIONS.get(job.get("action")), "safe_stop_code": job.get("stop_code"),
            "last_completed_dom_stage": diagnostic.get("stage"), "failed_predicate": failed_predicate(job),
            "message": failure_message(job["stop_code"]) if job["stage"] == "STOPPED" else ACTIONS.get(job.get("action"), "Mapping completed; the versioned report is ready." if job["stage"] == "COMPLETE" else "Mapping stopped; evidence and audit were preserved." if job["stage"] == "STOPPED" else "Mapping is progressing within the approved read scope."),
            "preserved": "Versioned metadata and audit history are preserved.", "retry_safe": job["retry_safe"],
            "cleanup_complete": job["cleanup_complete"],
            "cleanup_state": "COMPLETE" if job["cleanup_complete"] else "INCOMPLETE" if job["stage"] in TERMINAL else "AUTHORITY_ACTIVE" if job.get("lease_session") else "NOT_REQUIRED",
            "report_ready": job["report_ready"], "values_included": False,
            "live_validated": False, "production_writes": False}
