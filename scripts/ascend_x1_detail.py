"""Owner-only one-load metadata discovery controls; never starts a browser or enables a lease."""

import argparse
import json

from executors.ascend_extension.detail_contract import AscendLoadDetailContract, sanitized_summary
from executors.ascend_extension.detail_diagnostics import DetailContainerDiagnostic
from executors.ascend_extension.pairing import PairingRepository
from executors.ascend_extension.runtime import RuntimeAccess, runtime_code


def report(access, attempt_id):
    # Read-only metadata projection, without loading enrollment or touching host/browser state.
    if not access.path.exists():
        return {"state": "NOT_OBSERVED", "production_writes": False}
    with access.database(readonly=True) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "runtime_detail_contracts" not in tables:
            return {"state": "NOT_OBSERVED", "production_writes": False}
        artifacts = (json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_detail_contracts ORDER BY id DESC"))
        artifact = next((r for r in artifacts if r["attempt_id"] == attempt_id), None)
        attempt_row = db.execute("SELECT body FROM runtime_detail_attempts WHERE id=?", (attempt_id,)).fetchone()
        consumed = attempt_row is not None
        attempt = json.loads(attempt_row[0]) if attempt_row else None
        failure = None
        if attempt:
            # Old receipts lacked attempt IDs. Bound that fallback to this queue's interval only;
            # never substitute the global runtime's most recent unrelated error.
            next_queue = min((v["queued_at"] for r in db.execute("SELECT body FROM runtime_detail_attempts")
                              if (v := json.loads(r[0]))["queued_at"] > attempt["queued_at"]), default=float("inf"))
            for row in db.execute("SELECT body FROM runtime_receipts ORDER BY rowid DESC"):
                receipt = json.loads(row[0])
                if receipt.get("error_code") and (receipt.get("attempt_id") == attempt_id or
                    "attempt_id" not in receipt and attempt["queued_at"] <= receipt.get("observed_at", 0) < next_queue):
                    failure = receipt
                    break
    if artifact is None:
        raw = (failure.get("evidence") or {}).get("detail_container_diagnostic") if failure else None
        try:
            detail = DetailContainerDiagnostic.model_validate(raw).model_dump() if raw else None
        except ValueError:
            detail = None
        return {"state": "NOT_OBSERVED", "attempt_consumed": consumed,
                "error_code": runtime_code(failure["error_code"]) if failure else None,
                "execution_stage": failure["operation"] if failure and failure.get("operation") in
                    {"ASCEND_GET_SESSION_STATE", "ASCEND_NAVIGATE_ACTIVE_LOADS", "ASCEND_GET_ACTIVE_LOADS",
                     "ASCEND_FIND_LOAD", "ASCEND_OPEN_LOAD_READONLY", "ASCEND_DISCOVER_DETAIL_CONTRACT"} else None,
                "detail_container_diagnostic": detail,
                "production_writes": False}
    contract = AscendLoadDetailContract.model_validate(artifact["contract"])
    return {"state": "DETAIL_DISCOVERY_COMPLETE", "attempt_consumed": consumed,
            "contract_version": artifact["contract_version"], "activation": "CANDIDATE_ONLY",
            "validation_load_id": contract.validation_load_id, "identity_strategy": contract.identity.identity_strategy,
            "detail_container_diagnostic": contract.identity.container_diagnostic.model_dump() if contract.identity.container_diagnostic else None,
            "values_included": False,
            "live_validated": False, "fields": sanitized_summary(contract), "production_writes": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["queue", "report"])
    parser.add_argument("--owner-executed", action="store_true", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--load-id")
    args = parser.parse_args()
    access = RuntimeAccess(PairingRepository())
    try:
        if args.action == "queue":
            access.queue_discovery(args.load_id, args.attempt_id, owner_authorized=True)
            output = {"state": "DETAIL_DISCOVERY_QUEUED", "attempt_consumed": True, "production_writes": False}
        else:
            output = report(access, args.attempt_id)
        print(json.dumps(output))
    except Exception as error:
        print(json.dumps({"state": "STOPPED", "error_code": runtime_code(error), "production_writes": False}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
