"""Single local owner entry point; IDs, reports and cleanup are orchestrator-owned."""
import argparse
import json
import time

from executors.ascend_extension.mapping_orchestrator import MappingIntent, MappingOrchestrator
from executors.ascend_extension.pairing import PairingRepository
from executors.ascend_extension.runtime import RuntimeAccess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "cancel", "pause", "resume", "review", "status", "report"])
    parser.add_argument("--scope", choices=["CURRENT_LOAD", "CURRENT_OPERATIONS", "VALIDATION_COHORT", "OWNER_NAVIGATION_OBSERVE"], default="CURRENT_LOAD")
    parser.add_argument("--load-ids")
    parser.add_argument("--expected-load-id")
    parser.add_argument("--starting-section", choices=["Load Basics"])
    parser.add_argument("--minutes", type=int, default=10)
    parser.add_argument("--sections")
    parser.add_argument("--advanced", action="store_true")
    parser.add_argument("--causal-trace", action="store_true", help="Enable bounded sanitized causal diagnostics for this job only.")
    args = parser.parse_args()
    orchestrator = MappingOrchestrator(RuntimeAccess(PairingRepository()))
    try:
        if args.action == "start":
            value = orchestrator.start(MappingIntent(scope=args.scope, load_ids=args.load_ids.split(",") if args.load_ids else None,
                expected_load_id=args.expected_load_id, starting_section=args.starting_section, minutes=args.minutes,
                causal_trace=args.causal_trace), owner_authorized=True)
        elif args.action in {"cancel", "pause", "resume"}:
            value = orchestrator.control(args.action, owner_authorized=True)
        elif args.action == "review":
            value = orchestrator.review((args.sections or "").split(","), owner_authorized=True)
        else:
            value = orchestrator.report(advanced=args.advanced) if args.action == "report" else orchestrator.status(advanced=args.advanced)
        previous = None
        while args.action in {"start", "resume", "review"}:
            projection = (value["stage"], value.get("owner_action"), value.get("workspaces_observed"), value.get("sections_observed"),
                value.get("safe_stop_code"), value.get("last_completed_dom_stage"), value.get("failed_predicate"), value.get("cleanup_state"))
            if projection != previous:
                print(json.dumps(value), flush=True)
                previous = projection
            if value["stage"] in {"COMPLETE", "STOPPED", "OWNER_REVIEW_REQUIRED"}:
                break
            time.sleep(2)
            value = orchestrator.tick()
        print(json.dumps(orchestrator.report() if args.action in {"start", "resume", "review"} else value), flush=True)
    except KeyboardInterrupt:
        print(json.dumps(orchestrator.control("cancel", owner_authorized=True)), flush=True)
    except Exception:
        # Never print private exception content or continue after an uncertain coordination failure.
        try:
            failure = orchestrator.coordinator_failed()
        except Exception:
            failure = {"status": "STOPPED", "safe_stop_code": "COORDINATOR_FAILED", "last_completed_dom_stage": None,
                "failed_predicate": None, "owner_action": "REVIEW_CAPTURE_FAILURE", "cleanup_state": "UNKNOWN", "production_writes": False}
        print(json.dumps(failure), flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
