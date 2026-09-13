"""Copy only the legacy M1 demo database into the approved runtime; keep original intact."""
import sqlite3

from app.core.config import ROOT
from app.core.runtime import RuntimePaths


def main():
    destination = RuntimePaths.from_environment().ensure().path("Data", "booking-logistics", "demo.sqlite3")
    if destination.exists():
        print("Existing runtime demo database retained; no overwrite.")
        return
    source = ROOT / "data/booking-logistics/demo.sqlite3"
    if not source.exists():
        print("No legacy demo database; next startup will seed synthetic fixtures.")
        return
    origin = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    try:
        unsafe = origin.execute("SELECT COUNT(*) FROM records WHERE kind='shipment' AND "
            "(json_extract(body,'$.demo') IS NOT 1 OR id NOT LIKE 'DEMO-%')").fetchone()[0]
        if unsafe:
            raise ValueError("Migration permits only labeled demo shipments")
        destination.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(destination)
        try:
            origin.backup(target)
        finally:
            target.close()
    finally:
        origin.close()
    print("Legacy synthetic demo database copied to the approved runtime; original retained.")


if __name__ == "__main__":
    main()
