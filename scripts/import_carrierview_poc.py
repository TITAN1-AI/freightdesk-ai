"""Offline import after the owner reviews the staged data against the real CarrierView UI."""
from app.core.runtime import RuntimePaths
from app.services.carrierview_poc import UiReconciliation, import_reconciled_poc
from app.services.store import Store

if __name__ == "__main__":
    paths = RuntimePaths.from_environment()
    store = Store(paths.path("Data", "booking-logistics", "carrierview.sqlite3"))
    try:
        confirmation = UiReconciliation.model_validate_json(paths.path(
            "Data", "booking-logistics", "carrierview-ui-reconciliation.json").read_text(encoding="utf-8-sig"))
        import_reconciled_poc(store, "booking-logistics", confirmation)
        print("POC #001 imported after owner UI reconciliation. No external request was made.")
    except Exception:
        print("POC import stopped. Recheck the private candidate and UI reconciliation; no automatic retry.")
        raise SystemExit(1) from None
    finally:
        store.close()
