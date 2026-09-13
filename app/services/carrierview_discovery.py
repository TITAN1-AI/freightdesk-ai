"""Owner-authorized envelope discovery. No canonical mapping, writes or import."""
import hashlib
import json
import re

from integrations.carrierview.errors import ContractMismatch


def candidate_summary(envelope):
    # Inspect only common structural containers; ambiguous nesting fails closed.
    found = []

    def visit(value, depth=0):
        if isinstance(value, list):
            if all(isinstance(item, dict) for item in value):
                found.append(value)
            return
        if isinstance(value, dict) and depth < 3:
            for key in ("data", "loads", "results", "items"):
                if key in value:
                    visit(value[key], depth + 1)

    visit(envelope)
    if len(found) != 1:
        raise ContractMismatch("candidate_container_unresolved")
    rows = found[0]

    def reference(value):
        if type(value) not in (str, int):
            return None
        value = str(value)
        # Never output arbitrary provider text, URLs, email, or full phone-like values.
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) or re.search(r"\d{10,}", value):
            return "[withheld]"
        return value

    return {
        "returned_candidate_count": len(rows),
        "candidates": [
            {
                "candidate": index + 1,
                "record_fingerprint": hashlib.sha256(
                    json.dumps(row, sort_keys=True).encode()).hexdigest()[:12],
                "booking_load_reference": reference(row.get("load_id")),
                "provider_id": reference(row.get("id")),
            }
            for index, row in enumerate(rows[:20])
        ],
        "display_limited_to": 20,
        "pagination_verified": False,
        "identity_reconciled": False,
        "imported": False,
        "live_validated": False,
    }


async def discover_candidates(adapter, persist):
    profile, _ = await adapter._request("GET", "/api/profile", "profile_discovery", discovery=True)
    persist("profile", profile)
    loads, _ = await adapter._request(
        "GET", "/api/loads", "loads_discovery", params={"filter": "active"}, discovery=True)
    persist("active-loads", loads)
    return {"credential_class": adapter.config.credential_class.value,
            "profile_success": True, "active_loads_success": True, **candidate_summary(loads)}
