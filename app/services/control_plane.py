import hashlib
from datetime import timedelta
from zoneinfo import ZoneInfo

from app.core.config import ROOT, Settings
from app.core.risk import classify
from app.core.state_machine import transition
from app.models.domain import (
    ActionPolicy, AgentState, ApprovalRequest, AuditEvent, AuthorizedIdentity, ExternalEvent,
    Risk, Role, Shipment, Status, SystemConnection, Task, utcnow,
)
from app.policies.engine import PolicyEngine
from app.security.authorization import authorize
from app.services.demo import demo_shipments
from app.services.store import Store


class ControlPlane:
    def __init__(self, store: Store, settings: Settings):
        self.store, self.settings = store, settings
        self.tenant = settings.tenant
        self.policies = PolicyEngine(ROOT / "config/policies.json")
        self.system = AuthorizedIdentity(id="avery-scheduler", tenant_id=self.tenant, role=Role.SYSTEM)
        with store.transaction():
            try:
                store.get(self.tenant, "agent", "avery")
            except KeyError:
                store.put(self.tenant, "agent", "avery", AgentState())
            # Seed once, never represent these as imported/live loads.
            if not store.all(self.tenant, "shipment"):
                for shipment in demo_shipments(self.tenant):
                    shipment.risk, shipment.risk_explanation, shipment.next_action = classify(
                        shipment, utcnow(), settings)
                    self.save(shipment)
                    self.schedule(shipment.id, utcnow() + timedelta(minutes=5))
                    self.audit("DEMO_SEEDED", shipment.risk_explanation, shipment.id, self.system,
                               facts={"source": "demo_fixture", "risk": shipment.risk})
                self.request_action_locked(self.system, "DEMO-1848", "routine_customer_update", "seed-approval")

    def audit(self, event, explanation, shipment_id=None, identity=None, **kwargs):
        self.store.audit(AuditEvent(tenant_id=self.tenant, shipment_id=shipment_id,
            actor_id=(identity or self.system).id, source="freightdesk_demo",
            event=event, explanation=explanation, **kwargs))

    def shipment(self, shipment_id: str) -> Shipment:
        return Shipment.model_validate(self.store.get(self.tenant, "shipment", shipment_id))

    def save(self, shipment: Shipment):
        if shipment.tenant_id != self.tenant:
            raise PermissionError("Tenant mismatch")
        self.store.put(self.tenant, "shipment", shipment.id, shipment)

    def agent(self):
        return AgentState.model_validate(self.store.get(self.tenant, "agent", "avery"))

    def overrides(self):
        try:
            return self.store.get(self.tenant, "settings", "policies")
        except KeyError:
            return {}

    def policy(self, action):
        return self.policies.evaluate(action, self.overrides())

    def check_running(self, shipment):
        if self.agent().status != "ACTIVE" or shipment.paused or shipment.human_takeover:
            raise ValueError("Avery or shipment is paused / under human control")

    def schedule(self, shipment_id, due_at):
        # One active review task per shipment; stable key is tenant-scoped by Store.
        task_id = f"review:{shipment_id}"
        try:
            old = Task.model_validate(self.store.get(self.tenant, "task", task_id))
            if old.status in {"QUEUED", "RUNNING"}:
                return
        except KeyError:
            pass
        self.store.put(self.tenant, "task", task_id,
            Task(id=task_id, tenant_id=self.tenant, shipment_id=shipment_id, due_at=due_at))

    def process_event(self, identity: AuthorizedIdentity, event: ExternalEvent):
        if event.tenant_id != self.tenant:
            raise PermissionError("Event tenant mismatch")
        with self.store.transaction():
            shipment = self.shipment(event.shipment_id)
            authorize(identity, self.tenant, "review" if event.kind == "REVIEW" else "transition", shipment)
            digest = hashlib.sha256(event.model_dump_json().encode()).hexdigest()
            row = self.store.db.execute("SELECT digest FROM receipts WHERE tenant=? AND source=? AND id=?",
                                       (self.tenant, event.source, event.id)).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError("Event identifier reused with different content")
                return {"duplicate": True, "shipment_id": shipment.id}
            self.check_running(shipment)
            if event.expected_version is not None and event.expected_version != shipment.version:
                raise ValueError("Shipment version changed; reread before applying this event")
            if event.kind == "TRANSITION":
                if event.expected_version is None or event.target_status is None:
                    raise ValueError("Transition needs target status and expected version")
                shipment = transition(shipment, event.target_status)
            now = utcnow()
            shipment.risk, shipment.risk_explanation, shipment.next_action = classify(shipment, now, self.settings)
            shipment.version += 1
            shipment.last_action = "Demo event processed: " + event.kind
            shipment.next_action_at = now + timedelta(minutes=5)
            self.save(shipment)
            self.store.db.execute("INSERT INTO receipts VALUES (?,?,?,?)",
                                  (self.tenant, event.source, event.id, digest))
            self.audit("EVENT_PROCESSED", shipment.risk_explanation, shipment.id, identity,
                       facts={"risk": shipment.risk, "status": shipment.status, "version": shipment.version,
                              "event_kind": event.kind}, verified=True)
            self.schedule(shipment.id, shipment.next_action_at)
            return {"duplicate": False, "shipment": shipment.model_dump(mode="json")}

    def draft(self, shipment):
        if not shipment.tracking.verified_at or shipment.tracking.source == "unknown":
            raise ValueError("Verified shipment facts required")
        # Deterministic draft: no LLM call, no invented positions or commitments.
        facts = [f"DEMO ONLY — {shipment.id}: {shipment.status.replace('_', ' ').lower()}.",
                 f"Prepared at {utcnow().isoformat()} from recorded source facts."]
        if shipment.tracking.location and shipment.tracking.last_position_at:
            facts.append(f"Last reported location: {shipment.tracking.location} at "
                         f"{shipment.tracking.last_position_at.isoformat()}.")
        if shipment.tracking.eta:
            facts.append(f"Reported ETA: {shipment.tracking.eta.isoformat()}.")
        facts.append(shipment.risk_explanation + ".")
        return " ".join(facts)

    def request_action_locked(self, identity, shipment_id, action, request_id):
        shipment = self.shipment(shipment_id)
        authorize(identity, self.tenant, "request_action", shipment)
        try:
            prior = self.store.get(self.tenant, "action_request", request_id)
            if prior["shipment_id"] != shipment_id or prior["action"] != action:
                raise ValueError("Request identifier reused for another action")
            return prior
        except KeyError:
            pass
        self.check_running(shipment)
        policy = self.policy(action)
        if policy == ActionPolicy.FORBIDDEN:
            self.audit("ACTION_FORBIDDEN", "Action denied by policy", shipment_id, identity,
                       action=action, policy=policy)
            return {"status": "FORBIDDEN"}
        if action != "routine_customer_update":
            raise ValueError("Execution for this action is not implemented in this milestone")
        shipment.risk, shipment.risk_explanation, shipment.next_action = classify(
            shipment, utcnow(), self.settings)
        draft = self.draft(shipment)
        if policy == ActionPolicy.APPROVAL_REQUIRED:
            approval = ApprovalRequest(tenant_id=self.tenant, shipment_id=shipment_id,
                action=action, explanation=draft, expected_version=shipment.version,
                expected_risk=shipment.risk, expires_at=utcnow() + timedelta(minutes=15))
            self.store.put(self.tenant, "approval", approval.id, approval)
            result = {"status": "APPROVAL_REQUIRED", "approval_id": approval.id}
            self.audit("APPROVAL_REQUESTED", "Review proposed demo customer update", shipment_id,
                       identity, action=action, policy=policy, approval_status="PENDING")
        else:
            self.simulate_action(identity, shipment, action, draft, policy)
            result = {"status": "SIMULATED", "draft": draft}
        result.update({"shipment_id": shipment_id, "action": action})
        self.store.put(self.tenant, "action_request", request_id, result)
        return result

    def request_action(self, identity, shipment_id, action, request_id):
        with self.store.transaction():
            return self.request_action_locked(identity, shipment_id, action, request_id)

    def simulate_action(self, identity, shipment, action, draft, policy):
        self.audit("ACTION_SIMULATED", "Demo customer update prepared; no message sent", shipment.id,
                   identity, action=action, policy=policy, execution_status="SIMULATED",
                   executor="demo", verified=False, facts={"draft": draft})
        shipment.last_action = "Customer update simulated (nothing sent)"
        self.save(shipment)

    def decide(self, identity, approval_id, decision):
        with self.store.transaction():
            authorize(identity, self.tenant, "approve")
            approval = ApprovalRequest.model_validate(self.store.get(self.tenant, "approval", approval_id))
            shipment = self.shipment(approval.shipment_id)
            if approval.status != "PENDING":
                raise ValueError("Approval already decided")
            if decision not in {"APPROVED", "REJECTED"}:
                raise ValueError("Invalid approval decision")
            if decision == "APPROVED":
                self.check_running(shipment)
                current_risk = classify(shipment, utcnow(), self.settings)[0]
                if (approval.expires_at <= utcnow() or shipment.version != approval.expected_version
                        or current_risk != approval.expected_risk):
                    approval.status = "EXPIRED"
                elif self.policy(approval.action) == ActionPolicy.FORBIDDEN:
                    raise PermissionError("Policy now forbids this action")
                else:
                    approval.status = "APPROVED"
                    self.simulate_action(identity, shipment, approval.action, approval.explanation,
                                         self.policy(approval.action))
            else:
                approval.status = "REJECTED"
            approval.decided_by, approval.decided_at = identity.id, utcnow()
            self.store.put(self.tenant, "approval", approval.id, approval)
            self.audit("APPROVAL_" + approval.status, "Demo approval decision recorded",
                       shipment.id, identity, action=approval.action, approval_status=approval.status)
            return approval.model_dump(mode="json")

    def set_pause(self, identity, paused, shipment_id=None, takeover=False):
        with self.store.transaction():
            shipment = self.shipment(shipment_id) if shipment_id else None
            authorize(identity, self.tenant, "pause", shipment)
            if shipment:
                shipment.paused, shipment.human_takeover = paused, takeover
                shipment.version += 1
                self.save(shipment)
            else:
                agent = self.agent()
                agent.status = "PAUSED" if paused else "ACTIVE"
                self.store.put(self.tenant, "agent", "avery", agent)
            self.audit("TAKEOVER" if takeover else ("PAUSED" if paused else "RESUMED"),
                       "Operator changed local automation state", shipment_id, identity)
            return {"paused": paused, "shipment_id": shipment_id, "human_takeover": takeover}

    def update_policy(self, identity, action, value):
        with self.store.transaction():
            authorize(identity, self.tenant, "configure")
            if action not in self.policies.rules:
                raise ValueError("Unknown action")
            overrides = self.overrides()
            overrides[action] = ActionPolicy(value)
            self.store.put(self.tenant, "settings", "policies", overrides)
            self.audit("POLICY_CHANGED", "Owner updated action policy", identity=identity,
                       action=action, policy=ActionPolicy(value))
            return {"action": action, "policy": value}

    def run_due(self):
        now = utcnow()
        with self.store.transaction():
            agent = self.agent()
            agent.last_heartbeat = now
            self.store.put(self.tenant, "agent", "avery", agent)
            if agent.status != "ACTIVE":
                return
            tasks = [Task.model_validate(t) for t in self.store.all(self.tenant, "task")]
        for task in tasks:
            if task.status != "QUEUED" or task.due_at > now:
                continue
            # Pause, claim, execution and result are serialized in this single-worker foundation.
            # No network I/O inside this transaction.
            with self.store.transaction():
                shipment = self.shipment(task.shipment_id)
                if self.agent().status != "ACTIVE" or shipment.paused or shipment.human_takeover:
                    continue
                task.attempts += 1
                try:
                    shipment.risk, shipment.risk_explanation, shipment.next_action = classify(
                        shipment, now, self.settings)
                    shipment.last_action = "Scheduled demo tracking review"
                    shipment.next_action_at = now + timedelta(minutes=5)
                    self.save(shipment)
                    task.status = "COMPLETED"
                    self.audit("TASK_COMPLETED", shipment.risk_explanation, shipment.id,
                               facts={"risk": shipment.risk, "task_kind": task.kind}, verified=True,
                               execution_status="COMPLETED")
                except Exception:
                    # Never persist raw exception messages, which may contain provider secrets.
                    task.last_error = "REVIEW_FAILED"
                    task.status = "FAILED" if task.attempts >= task.max_attempts else "QUEUED"
                    task.due_at = now + timedelta(seconds=min(900, 30 * 2 ** (task.attempts - 1)))
                    self.audit("TASK_FAILED", "Review failed; bounded retry or escalation required",
                               shipment.id, error_code=task.last_error, retry_count=task.attempts)
                self.store.put(self.tenant, "task", task.id, task)
                if task.status == "COMPLETED" and shipment.status != Status.CLOSED:
                    # History remains in append-only audit; the task record is the current next review.
                    self.schedule(shipment.id, shipment.next_action_at)

    def command(self, identity, command):
        authorize(identity, self.tenant, "read")
        words = command.strip().split()
        if not words:
            raise ValueError("Command is empty")
        verb = words[0].lower()
        if len(words) == 2 and verb in {"status", "pause", "resume", "takeover", "review"}:
            key = words[1].upper()
            if not key.startswith("DEMO-"):
                key = "DEMO-" + key
            if verb == "status":
                with self.store.transaction():
                    shipment = self.shipment(key)
                    authorize(identity, self.tenant, "read", shipment)
                    return {"reply": f"{key}: {shipment.status}. {shipment.risk_explanation}",
                            "shipment_id": key}
            if verb == "review":
                return self.process_event(identity, ExternalEvent(tenant_id=self.tenant,
                    shipment_id=key, source="dashboard", kind="REVIEW"))
            return self.set_pause(identity, verb != "resume", key, verb == "takeover")
        if command.strip().lower() in {"at risk", "missing pod", "deliveries today", "pickups tomorrow"}:
            with self.store.transaction():
                loads = [Shipment.model_validate(s) for s in self.store.all(self.tenant, "shipment")]
            query = command.strip().lower()
            zone = ZoneInfo(self.settings.timezone)
            today = utcnow().astimezone(zone).date()
            if query == "at risk":
                loads = [s for s in loads if s.risk in {Risk.AT_RISK, Risk.EXCEPTION}]
            elif query == "missing pod":
                loads = [s for s in loads if s.status in {Status.DELIVERED, Status.POD_PENDING}
                         and not any(d.kind == "POD" and d.verified for d in s.documents)]
            else:
                pickup = query == "pickups tomorrow"
                target = today + timedelta(days=1 if pickup else 0)
                loads = [s for s in loads if (s.origin if pickup else s.destination).appointment
                         .astimezone(zone).date() == target]
            return {"reply": ", ".join(s.id for s in loads) or "No matching demo loads"}
        raise ValueError("Supported: status/review/pause/resume/takeover <load>; at risk; missing pod; "
                         "deliveries today; pickups tomorrow")

    def snapshot(self, identity):
        authorize(identity, self.tenant, "read")
        # Only staff roles may obtain the control-tower projection.
        if identity.role not in {Role.OWNER, Role.OPERATIONS_USER, Role.SYSTEM}:
            raise PermissionError("Staff dashboard access required")
        with self.store.transaction():
            shipments = [Shipment.model_validate(s) for s in self.store.all(self.tenant, "shipment")]
            # Recompute time-sensitive risk for display; persisted facts remain untouched.
            for shipment in shipments:
                shipment.risk, shipment.risk_explanation, shipment.next_action = classify(
                    shipment, utcnow(), self.settings)
            audit = self.store.timeline(self.tenant)
            approvals = self.store.all(self.tenant, "approval")
            tasks = self.store.all(self.tenant, "task")
            today = utcnow().astimezone(ZoneInfo(self.settings.timezone)).date()
            day_start = utcnow().astimezone(ZoneInfo(self.settings.timezone)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            processed_today = self.store.db.execute(
                "SELECT COUNT(*) FROM audit WHERE tenant=? AND json_extract(body,'$.event')='EVENT_PROCESSED' "
                "AND datetime(json_extract(body,'$.timestamp')) >= datetime(?)",
                (self.tenant, day_start.isoformat())).fetchone()[0]
            all_events = self.store.db.execute("SELECT COUNT(*) FROM receipts WHERE tenant=?",
                                               (self.tenant,)).fetchone()[0]
            summary = {risk.value.lower(): sum(s.risk == risk for s in shipments) for risk in Risk}
            summary.update({
                "active_loads": sum(s.status != Status.CLOSED for s in shipments),
                "pickups_today": sum(s.origin.appointment.astimezone(ZoneInfo(self.settings.timezone)).date()
                                     == today for s in shipments),
                "deliveries_today": sum(s.destination.appointment.astimezone(ZoneInfo(self.settings.timezone)).date()
                                        == today for s in shipments),
                "tracking_pending": sum(not s.tracking.accepted for s in shipments),
                "tracking_stale": sum(s.tracking.last_position_at is not None and
                    (utcnow() - s.tracking.last_position_at).total_seconds() >= self.settings.stale_minutes * 60
                    for s in shipments if s.status not in {Status.DELIVERED, Status.POD_PENDING,
                    Status.POD_RECEIVED, Status.BILLING_READY, Status.CLOSED}),
                "bol_missing": sum(not any(d.kind == "BOL" and d.verified for d in s.documents) for s in shipments),
                "pod_pending": sum(s.status == Status.POD_PENDING for s in shipments),
                "billing_ready": sum(s.status == Status.BILLING_READY for s in shipments),
            })
            metrics = {"events_processed": all_events,
                "events_processed_today": processed_today,
                "queued_tasks": sum(t["status"] == "QUEUED" for t in tasks),
                "waiting_tasks": sum(s.paused or s.human_takeover for s in shipments),
                "completed_reviews_recent": sum(a["event"] == "TASK_COMPLETED" for a in audit),
                "simulated_actions_recent": sum(a["event"] == "ACTION_SIMULATED" for a in audit),
                "external_actions_completed": 0,
                "pending_approvals": sum(a["status"] == "PENDING" for a in approvals),
                "errors_recent": sum(a["error_code"] is not None for a in audit),
                "retries": sum(max(0, t["attempts"] - 1) for t in tasks),
                "escalations": sum(s.risk == Risk.EXCEPTION for s in shipments),
                "model_calls": 0, "model_cost_usd": 0, "browser_jobs": 0,
                "human_interventions_recent": sum(a["event"] in {"PAUSED", "TAKEOVER", "APPROVAL_APPROVED",
                                                                "APPROVAL_REJECTED"} for a in audit)}
            connections = [SystemConnection(name=name, detail=detail) for name, detail in [
                ("CarrierView", "Operational polling/writes disabled; historical validation is scoped in the protected POC matrix"),
                ("AscendTMS", "API unverified; browser read/reconciliation planned"),
                ("Outlook", "Read/draft and delta foundation tested; awaiting owner Microsoft OAuth; sending disabled"),
                ("Quo", "API / webhook adapter planned"),
                ("BrokerCarrier", "API / onboarding adapter planned"),
                ("Playwright worker", "Interface only; no authenticated session"),
                ("OpenClaw worker", "Interface only; bounded execution jobs planned"),
                ("Model provider", f"{self.settings.model_provider} / {self.settings.model}; calls disabled"),
            ]]
            connections[0].implemented = True
            connections[0].tested = True
            connections[0].status = "DISABLED"
            connections[2].implemented = True
            connections[2].tested = True
            return {"mode": self.settings.mode, "tenant": self.tenant, "timezone": self.settings.timezone,
                "generated_at": utcnow().isoformat(), "agent": self.agent().model_dump(mode="json"),
                "summary": summary, "metrics": metrics,
                "shipments": [s.model_dump(mode="json") for s in shipments],
                "approvals": approvals, "tasks": tasks, "audit": audit,
                "connections": [c.model_dump(mode="json") for c in connections],
                "policies": {a: self.policy(a) for a in self.policies.rules},
                "usage": [], "live_validated": False}
