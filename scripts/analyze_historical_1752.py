"""Analyze saved exact-reference evidence only. Never reads a token or makes a request."""
import json

from app.core.runtime import RuntimePaths
from app.services.carrierview_historical import exact_record, records, reconcile_list_detail
from app.services.carrierview_historical_report import historical_report


def main():
    paths = RuntimePaths.from_environment()
    root = paths.path("Data", "booking-logistics")
    source = sorted((root / "discovery").glob("*/past-loads.json"))[-1]
    matches = [row for row in records(json.loads(source.read_text())) if str(row.get("load_id")) == "1752"]
    if len(matches) != 1:
        raise ValueError("Historical candidate ambiguous")
    runs = sorted(path for path in (root / "historical-1752").iterdir()
                  if (path / "positions-history.json").exists())
    run = runs[-1]
    detail = exact_record(json.loads((run / "exact-load.json").read_text()), str(matches[0]["id"]), "1752")
    if not all(value is True for value in reconcile_list_detail(matches[0], detail).values()):
        raise ValueError("List/detail reconciliation incomplete")
    report = historical_report(matches[0], detail,
        json.loads((run / "last-position.json").read_text()),
        json.loads((run / "positions-history.json").read_text()))
    target = paths.path("Data", "booking-logistics", "historical-1752", "replay-report.json")
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Historical analysis stopped; evidence or timestamp mapping needs review.") from None
