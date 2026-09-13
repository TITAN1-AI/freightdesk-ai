"""Exact-reference historical evidence collection, with no canonical side effects."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from integrations.carrierview.errors import ContractMismatch


def records(envelope):
    value = envelope.get("data")
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        lists = [value[k] for k in ("loads", "items", "results", "data") if isinstance(value.get(k), list)]
        if len(lists) == 1:
            return lists[0]
    raise ContractMismatch("historical_list_shape_unresolved")


def exact_record(envelope, provider_id, booking_ref):
    value = envelope.get("data")
    if isinstance(value, dict) and isinstance(value.get("load"), dict):
        value = value["load"]
    if not isinstance(value, dict):
        raise ContractMismatch("exact_load_shape_unresolved")
    if str(value.get("id")) != provider_id or str(value.get("load_id")) != booking_ref:
        raise ContractMismatch("exact_historical_identity_mismatch")
    return value


def reconcile_list_detail(candidate, detail):
    comparisons = {}
    for key in ("driver_phone", "integration_type"):
        comparisons[key] = (candidate.get(key) == detail.get(key)) if candidate.get(key) is not None else None
    old, new = candidate.get("locations"), detail.get("locations")
    if isinstance(new, list):
        kinds = [stop.get("type") for stop in new if isinstance(stop, dict)]
        if len(kinds) != len(new) or len(set(kinds)) != len(kinds):
            raise ContractMismatch("historical_stop_identity_ambiguous")
        new = {stop["type"]: stop for stop in new}
    for kind in ("pickup", "destination"):
        a = old.get(kind, {}) if isinstance(old, dict) else {}
        b = new.get(kind, {}) if isinstance(new, dict) else {}
        comparisons[kind + "_address"] = (a["address"] == b.get("address")) if "address" in a else None
        if "dateTo" not in b:
            for field in ("date_to", "timezone_name"):
                comparisons[kind + "_" + field] = (a[field] == b.get(field)) if field in a else None
            continue
        try:
            zone = ZoneInfo(a["timezone_name"])
            local_end = datetime.fromisoformat(b["dateTo"]).replace(tzinfo=zone)
            utc_end = datetime.fromisoformat(a["date_to"].replace("Z", "+00:00"))
            comparisons[kind + "_date_to"] = utc_end.tzinfo is not None and local_end == utc_end
            comparisons[kind + "_timezone_name"] = local_end.tzname() == b.get("timezone") == a.get("tz_name")
        except (KeyError, ValueError, TypeError, ZoneInfoNotFoundError):
            comparisons[kind + "_date_to"] = None
            comparisons[kind + "_timezone_name"] = None
    return comparisons


async def collect_historical(adapter, candidate, booking_ref, persist, cached_detail=None):
    provider_id = str(candidate["id"])
    if str(candidate.get("load_id")) != booking_ref or adapter.config.discovery_provider_id != provider_id:
        raise PermissionError("Owner exact-reference binding required")
    base = "/api/loads/" + adapter.provider_id(provider_id)
    if cached_detail is None:
        raw, _ = await adapter._request("GET", base, "exact_load_discovery", discovery=True)
    else:
        raw = cached_detail
    persist("exact-load", raw)
    detail = exact_record(raw, provider_id, booking_ref)
    checks = reconcile_list_detail(candidate, detail)
    if any(value is False for value in checks.values()):
        raise ContractMismatch("historical_list_detail_conflict")
    if any(value is None for value in checks.values()):
        raise ContractMismatch("historical_list_detail_incomplete")
    result = {"booking_reference": booking_ref, "provider_id": provider_id,
              "credential_class": adapter.config.credential_class.value,
              "exact_load_success": True, "list_detail_reconciliation": checks,
              "imported": False, "ui_reconciled": False, "live_validated": False}
    # Each exact-load endpoint is requested once. Failure stops, without retry or widening scope.
    for name, suffix, operation in [
        ("last-position", "/last-position", "exact_position_discovery"),
        ("positions-history", "/positions-history", "exact_history_discovery"),
    ]:
        envelope, _ = await adapter._request("GET", base + suffix, operation, discovery=True)
        persist(name, envelope)
        result[name + "_success"] = True
    return result
