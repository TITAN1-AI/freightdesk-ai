"""Ascend portable capability map and write stubs. Demo-gated, not LIVE_VALIDATED."""

from __future__ import annotations

from copy import deepcopy

from app.models.domain import ActionPolicy, AuditEvent
from app.services.ascend_atlas import (
    atlas_summary,
    load_capabilities,
    require_atlas_bindings,
)
from app.services.portable_leases import LOAD_STATUSES, PortableLeaseService


class AscendCapabilityService:
    def __init__(self, store, tenant: str, portable: PortableLeaseService):
        self.store = store
        self.tenant = tenant
        self.portable = portable
        require_atlas_bindings()
        self._catalog = load_capabilities()

    def catalog(self) -> dict:
        body = deepcopy(self._catalog)
        body["live_validated"] = False
        body["production_writes"] = False
        body["not_a_retail_api"] = True
        body["atlas"] = atlas_summary()
        return body

    def facade_load(self, load_id: str) -> dict:
        self.portable._require_demo()
        identity = _require_load_id(load_id)
        board = self.portable.facade_loads()
        harvest_available = bool(board.get("load_count"))
        match = next((row for row in board.get("loads") or [] if row.get("load_id") == identity), None)
        atlas = atlas_summary()
        return {
            "facade": "ascend",
            "source": "portable_harvest",
            "not_a_retail_api": True,
            "section": "Load Basics",
            "load_id": identity,
            "found": match is not None,
            "harvest_available": harvest_available,
            "evidence_class": "CANDIDATE",
            "live_validated": False,
            "production_writes": False,
            "lease_id": board.get("lease_id"),
            "lease_status": board.get("lease_status"),
            "harvested_at": board.get("harvested_at"),
            "revision": board.get("revision"),
            "pick_date": None if match is None else match.get("pick_date"),
            "drop_date": None if match is None else match.get("drop_date"),
            "fields": {} if match is None else dict(match.get("fields") or {}),
            "atlas": atlas,
            "atlas_fields": atlas["field_names"],
        }

    def refuse_write(self, load_id: str, capability: str, requested: dict | None = None) -> tuple[int, dict]:
        self.portable._require_demo()
        identity = _require_load_id(load_id)
        spec = (self._catalog.get("capabilities") or {}).get(capability)
        if spec is None:
            raise ValueError("capability_unknown")
        policy = ActionPolicy(spec["policy"])
        implementation = spec["implementation"]
        if policy == ActionPolicy.FORBIDDEN or implementation == "FORBIDDEN":
            code, result = 403, "FORBIDDEN"
        else:
            code, result = 501, "NOT_IMPLEMENTED"
        receipt = {
            "receipt": True,
            "capability": capability,
            "kind": spec.get("kind"),
            "load_id": identity,
            "result": result,
            "policy": policy.value,
            "intended_policy": spec["policy"],
            "implementation": implementation,
            "http_status": code,
            "silent_save_forbidden": True,
            "whole_form_save": False,
            "live_validated": False,
            "production_writes": False,
            "not_a_retail_api": True,
            "atlas": atlas_summary(),
            "requested": requested or {},
            "detail": _refusal_detail(capability, policy, implementation),
        }
        self._audit(identity, capability, result, code)
        return code, receipt

    def refuse_status(self, load_id: str, status: str, approval_token: str | None = None) -> tuple[int, dict]:
        if status not in LOAD_STATUSES:
            raise ValueError("row_status_invalid")
        requested = {"status": status, "approval_present": bool(approval_token)}
        return self.refuse_write(load_id, "write_status", requested)

    def _audit(self, load_id: str, capability: str, result: str, http_status: int) -> None:
        self.store.audit(AuditEvent(
            tenant_id=self.tenant,
            actor_id="portable-bridge",
            source="ascend_capability",
            event="ASCEND_WRITE_STUB",
            explanation="Demo write stub refused; no Ascend Save or mutation.",
            facts={
                "load_id": load_id,
                "capability": capability,
                "result": result,
                "http_status": http_status,
                "production_writes": False,
            },
            verified=False,
        ))


def _require_load_id(load_id: str) -> str:
    if not load_id.isdigit() or not (1 <= len(load_id) <= 20):
        raise ValueError("row_identity_invalid")
    return load_id


def _refusal_detail(capability: str, policy: ActionPolicy, implementation: str) -> str:
    if policy == ActionPolicy.FORBIDDEN or implementation == "FORBIDDEN":
        return f"{capability} is FORBIDDEN on the portable Bridge. Money and assign stay stubs."
    return (
        f"{capability} is not implemented. Intended policy is {policy.value}. "
        "No silent Save Load. Private note remains the in-flight LIVE write (PR #8)."
    )
