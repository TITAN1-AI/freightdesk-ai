"""Explicit owner controls for a local read lease; never launches browsers or vendor calls."""

import argparse
import json

from executors.ascend_extension.pairing import PairingRepository
from executors.ascend_extension.runtime import RuntimeAccess, runtime_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["status", "enable", "disable", "pause", "resume", "rebind", "detail"]
    )
    parser.add_argument("--owner-executed", required=True, action="store_true")
    parser.add_argument("--hours", type=float, default=8)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--load-id")
    args = parser.parse_args()
    access = RuntimeAccess(PairingRepository())
    try:
        if args.action == "enable":
            result = access.enable(
                owner_authorized=True, hours=args.hours, interval_seconds=args.interval_seconds
            )
        elif args.action == "disable":
            result = access.disable(owner_authorized=True)
        elif args.action in {"pause", "resume"}:
            result = access.set_paused(args.action == "pause", owner_authorized=True)
        elif args.action == "rebind":
            result = access.request_rebind(owner_authorized=True)
        elif args.action == "detail":
            result = access.queue_detail(args.load_id, owner_authorized=True)
        else:
            result = access.status()
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({"state": "STOPPED", "error_code": runtime_code(error), "production_writes": False}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
