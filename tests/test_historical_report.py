from app.services.carrierview_historical_report import historical_report
from app.services.carrierview_historical import reconcile_list_detail


def example():
    candidate = {"driver_phone": "FIXTURE", "integration_type": "carrier_view", "locations": {
        kind: {"address": "Fixture", "date_to": "2026-09-04T16:00:00Z",
               "timezone_name": "America/Chicago", "tz_name": "CDT"} for kind in ("pickup", "destination")}}
    detail = {"id": "fixture", "load_id": "TEST-42", "driver_phone": "FIXTURE",
              "integration_type": "carrier_view", "locations": [
        {"type": kind, "address": "Fixture", "dateFrom": "2026-09-04 06:00",
         "dateTo": "2026-09-04 11:00", "timezone": "CDT",
         "arrived_utc": "2026-09-04T12:00:00Z", "departed_utc": "2026-09-04T13:00:00Z"}
        for kind in ("pickup", "destination")]}
    return candidate, detail


def test_list_utc_detail_local_appointments_reconcile():
    candidate, detail = example()
    assert all(reconcile_list_detail(candidate, detail).values())
    detail["locations"][0]["dateTo"] = "2026-09-04 12:00"
    assert reconcile_list_detail(candidate, detail)["pickup_date_to"] is False


def test_replay_assesses_historical_arrival_not_current_tracking_age():
    candidate, detail = example()
    report = historical_report(candidate, detail, {"data": {"position": None}},
                               {"data": {"positions": [], "pagination": {}}})
    assert report["arrival_assessment"] == "NO_LATE_ARRIVAL_OBSERVED"
    assert report["stops"][0]["dwell_seconds"] == 3600
    assert report["stops"][0]["arrived_at"].endswith("-05:00")
    assert not report["live_validated"] and not report["full_gps_replay_verified"]
    detail["locations"][0]["arrived_utc"] = "2026-09-04T17:00:00Z"
    assert historical_report(candidate, detail, {}, {})["arrival_assessment"] == "REVIEW_REQUIRED"
