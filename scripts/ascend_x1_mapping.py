"""Explicit owner mapping controls. No browser launch or direct vendor networking."""

import argparse
import json

from pydantic import ValidationError

from executors.ascend_extension.mapping_store import report_maps, record_mapping_validation
from executors.ascend_extension.auto_map import approve_navigation
from executors.ascend_extension.pairing import PairingRepository
from executors.ascend_extension.runtime import RuntimeAccess, runtime_code
from executors.ascend_extension.workspace_contracts import MappingSessionApproval


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["enable", "capture", "status", "report", "disable", "record-validation", "approve-navigation"])
    parser.add_argument("--owner-executed", required=True, action="store_true")
    parser.add_argument("--session-id")
    parser.add_argument("--mode", choices=["observe", "auto-map"], default="observe")
    parser.add_argument("--scope", choices=["validation", "normal"], default="validation")
    parser.add_argument("--sections", help="Owner-reviewed section names separated by commas")
    parser.add_argument("--load-ids", help="Required 3-5 load cohort for first validation; optional stricter scope in normal mode")
    parser.add_argument("--capture-load-id")
    parser.add_argument("--capture-section", choices=["Load Basics"])
    parser.add_argument("--minutes", type=int, default=20)
    parser.add_argument("--max-captures", type=int, default=120, help="Hard ceiling on all capture attempts, including unchanged samples")
    parser.add_argument("--max-workspace-captures", type=int, default=10)
    parser.add_argument("--max-section-observations", type=int, default=60)
    parser.add_argument("--max-contract-observations", type=int, default=1000)
    parser.add_argument("--owner-confirms-controlled-validation", action="store_true")
    args = parser.parse_args()
    access = RuntimeAccess(PairingRepository())
    try:
        if args.action == "enable":
            approval = MappingSessionApproval(session_id=args.session_id, capture_load_id=args.capture_load_id, capture_section=args.capture_section,
                mode="FIRST_VALIDATION" if args.scope == "validation" else "NORMAL_OWNER_PRESENT",
                operation_mode="OBSERVE" if args.mode == "observe" else "AUTO_MAP",
                approved_load_ids=[i.strip() for i in args.load_ids.split(",")] if args.load_ids else None,
                minutes=args.minutes, max_captures=args.max_captures, max_workspace_captures=args.max_workspace_captures,
                max_section_observations=args.max_section_observations, max_contract_observations=args.max_contract_observations)
            result = access.enable(owner_authorized=True, mapping=approval)
        elif args.action == "capture":
            result = access.request_mapping_capture(owner_authorized=True)
        elif args.action == "disable":
            result = access.disable(owner_authorized=True)
        elif args.action == "report":
            if not args.session_id:
                raise ValueError("MAPPING_CONTRACT_INVALID")
            result = report_maps(access, args.session_id)
        elif args.action == "record-validation":
            result = record_mapping_validation(access, args.session_id, owner_authorized=args.owner_confirms_controlled_validation)
        elif args.action == "approve-navigation":
            result = approve_navigation(access, args.session_id, [s.strip() for s in (args.sections or "").split(",")], owner_authorized=True)
        else:
            result = access.status()
        print(json.dumps(result))
    except Exception as error:
        code = "MAPPING_CONTRACT_INVALID" if isinstance(error, ValidationError) else runtime_code(error)
        print(json.dumps({"state": "STOPPED", "error_code": code, "production_writes": False}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
