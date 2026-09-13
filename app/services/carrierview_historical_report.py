"""Offline historical timeline analysis; no network, decisions dispatched or import."""
from datetime import datetime
from zoneinfo import ZoneInfo


def historical_report(candidate, detail, position_envelope, history_envelope):
    timeline, stops = [], []
    for kind in ("pickup", "destination"):
        matches = [stop for stop in detail["locations"] if stop.get("type") == kind]
        if len(matches) != 1:
            raise ValueError("Unique pickup and destination required")
        stop = matches[0]
        zone = ZoneInfo(candidate["locations"][kind]["timezone_name"])
        start = datetime.fromisoformat(stop["dateFrom"]).replace(tzinfo=zone)
        end = datetime.fromisoformat(stop["dateTo"]).replace(tzinfo=zone)
        row = {"kind": kind, "appointment_start": start.isoformat(), "appointment_end": end.isoformat(),
               "timezone": zone.key, "arrived_at": None, "departed_at": None,
               "arrival_vs_window": "UNKNOWN", "dwell_seconds": None}
        moments = {}
        for action, key in (("arrived", "arrived_utc"), ("departed", "departed_utc")):
            value = stop.get(key)
            if not value:
                continue
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                raise ValueError("Historical event must have an explicit UTC offset")
            moments[action] = moment
            row[action + "_at"] = moment.astimezone(zone).isoformat()
            timeline.append({"event": kind + "_" + action, "source_timestamp": value,
                             "timestamp": moment.isoformat()})
        if "arrived" in moments:
            row["arrival_vs_window"] = ("EARLY" if moments["arrived"] < start else
                                        "LATE" if moments["arrived"] > end else "WITHIN_WINDOW")
        if set(moments) == {"arrived", "departed"}:
            seconds = (moments["departed"] - moments["arrived"]).total_seconds()
            row["dwell_seconds"] = seconds if seconds >= 0 else None
        stops.append(row)
    timeline.sort(key=lambda event: datetime.fromisoformat(event["timestamp"]))
    history = history_envelope.get("data", {})
    positions = history.get("positions", [])
    pagination = history.get("pagination", {})
    # Numeric timestamps are preserved privately. Units and provider ordering remain unverified.
    last = position_envelope.get("data", {}).get("position")
    return {
        "booking_reference": str(detail["load_id"]), "provider_id": str(detail["id"]),
        "mode": "READ_ONLY_HISTORICAL_REPLAY", "credential_class": "tenant",
        "owner_reported_completed": True,
        "stops": stops, "timeline": timeline,
        "delivery_arrived": detail.get("delivery_arrived"),
        "delivery_departed": detail.get("delivery_departed"),
        "app_status": (detail.get("track_driver") or {}).get("app_status"),
        "time_remaining_seconds": detail.get("time_left_sec"),
        "distance_remaining_meters": detail.get("distance_left_meters"),
        "last_position_returned": isinstance(last, dict),
        "numeric_position_timestamp_units_verified": False,
        "history_records_received": len(positions), "history_pagination": pagination,
        "full_gps_replay_verified": False,
        "arrival_assessment": "NO_LATE_ARRIVAL_OBSERVED" if all(
            row["arrival_vs_window"] in {"EARLY", "WITHIN_WINDOW"} for row in stops) else "REVIEW_REQUIRED",
        "tracking_acceptance": "UNKNOWN", "rc_and_signed_rc": "UNKNOWN",
        "pod_and_billing_readiness": "UNVERIFIED",
        "documents_api": "UNSUPPORTED_UNKNOWN",
        "ui_reconciled": False, "imported": False, "live_validated": False,
    }
