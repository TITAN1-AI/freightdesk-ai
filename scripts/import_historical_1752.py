"""Explicit owner-approved offline import. No CarrierView credential or network access."""
import json

from app.core.runtime import RuntimePaths
from app.models.domain import utcnow
from app.services.carrierview_historical import records
from app.services.carrierview_poc import candidate_hash
from app.services.carrierview_replay_discovery import company_matches
from app.services.historical_import import import_historical
from app.services.store import Store


def main():
    paths = RuntimePaths.from_environment()
    root = paths.path("Data", "booking-logistics")
    run = sorted(p for p in (root / "historical-1752").iterdir()
                 if p.is_dir() and (p / "positions-history.json").exists())[-1]
    selection = json.loads((run / "owner-selection.json").read_text())
    source = paths.path("Data", "booking-logistics", "discovery", selection["source_run"])
    profile = json.loads((source / "profile.json").read_text())
    if not company_matches(profile):
        raise PermissionError("Company mismatch")
    matches = [row for row in records(json.loads((source / "past-loads.json").read_text()))
               if str(row.get("load_id")) == "1752"]
    if len(matches) != 1 or str(matches[0].get("id")) != "99616":
        raise PermissionError("Owner-approved identity mismatch")
    receipt = json.loads((run / "sanitized-receipt.json").read_text())
    if not all(receipt.get(key) is True for key in
               ("exact_load_success", "last-position_success", "positions-history_success")):
        raise PermissionError("Successful historical read receipts required")
    bundle = {"fixture": False, "candidate": matches[0], "profile": profile,
        "detail": json.loads((run / "exact-load.json").read_text()),
        "position": json.loads((run / "last-position.json").read_text()),
        "history": json.loads((run / "positions-history.json").read_text()),
        "observed_at": selection["observed_at"], "source_run": run.name}
    confirmation = {"approved": True, "reviewed_by": "owner", "reviewed_at": utcnow().isoformat(),
        "booking_reference": "1752", "provider_id": "99616", "evidence_hash": candidate_hash(bundle),
        "approval_basis": "Explicit owner UI reconciliation and historical canonical import authorization",
        "stops": {
            "pickup": {"appointment_start": "2026-09-03T11:00-05:00", "appointment_end": "2026-09-03T13:00-05:00",
                       "arrived_at": "2026-09-03T11:31-05:00", "departed_at": "2026-09-03T14:35-05:00"},
            "destination": {"appointment_start": "2026-09-04T06:00-05:00", "appointment_end": "2026-09-04T11:00-05:00",
                       "arrived_at": "2026-09-04T07:35-05:00", "departed_at": "2026-09-04T10:06-05:00"}}}
    store = Store(paths.path("Data", "booking-logistics", "carrierview.sqlite3"))
    try:
        result = import_historical(store, bundle, confirmation)
        paths.path("Data", "booking-logistics", "historical-1752", "owner-import-confirmation.json").write_text(
            json.dumps(confirmation, indent=2), encoding="utf-8")
        print(json.dumps(result))
    finally:
        store.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Historical import stopped: approval, identity, or evidence check failed.") from None
