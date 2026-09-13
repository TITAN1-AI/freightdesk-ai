"""Historical candidate discovery only; no replay actions or import."""
import re

from app.services.carrierview_discovery import candidate_summary

SERVICE_REASON = "CarrierView API requires manager/admin credential; Avery employee token is not API-eligible."


def company_matches(profile):
    names = []
    def visit(node, depth=0):
        if not isinstance(node, dict) or depth > 4:
            return
        for key in ("company_name", "companyName"):
            if isinstance(node.get(key), str):
                names.append(node[key])
        company = node.get("company")
        if isinstance(company, dict):
            for key in ("name", "company_name", "legal_name"):
                if isinstance(company.get(key), str):
                    names.append(company[key])
        elif isinstance(company, str):
            names.append(company)
        for key in ("data", "profile", "user"):
            visit(node.get(key), depth + 1)
    visit(profile)
    normalized = {re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip() for name in names}
    return normalized == {"booking logistics llc"}


async def discover_past(adapter, persist):
    profile, _ = await adapter._request("GET", "/api/profile", "profile_discovery", discovery=True)
    persist("profile", profile)
    result = {"credential_class": "tenant", "executed_by": "FreightDesk/Avery",
              "profile_success": True, "company_identity_matches": company_matches(profile),
              "past_loads_requested": False, "imported": False, "live_validated": False}
    if not result["company_identity_matches"]:
        return {**result, "status": "STOPPED_COMPANY_IDENTITY_UNVERIFIED"}
    loads, _ = await adapter._request("GET", "/api/loads", "past_loads_discovery",
                                    params={"filter": "past"}, discovery=True)
    persist("past-loads", loads)
    return {**result, "past_loads_requested": True, "past_loads_success": True,
            **candidate_summary(loads), "status": "AWAITING_OWNER_SHIPMENT_RECONCILIATION"}
