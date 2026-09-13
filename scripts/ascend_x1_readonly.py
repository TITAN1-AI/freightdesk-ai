"""Owner-executed local release of the first X1 identity-only test. Never launches a browser."""

import argparse
import json

from executors.ascend_extension.controller import prepare, safe_code
from executors.ascend_extension.pairing import PairingRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare"])
    parser.add_argument("--owner-executed", action="store_true", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--service-date", choices=["2026-09-11"], required=True)
    parser.add_argument("--supersedes-attempt", choices=["owner-x1-identity-1755-20260911-01"])
    args = parser.parse_args()
    # This oracle is scoped to this owner-approved validation case, never to general board behavior.
    pickups = ["1755", "1756", "1757", "1758", "1759", "1762", "1768", "1769"]
    deliveries = ["1761", "1766", "1767"]
    print(
        "Authorize exactly four X1 reads in one selected Ascend tab; final action opens only 1755 for identity."
    )
    print(
        "Operating date 2026-09-11; board date format US; expected pickups 8 / deliveries 3. No operational detail extraction or writes."
    )
    if args.supersedes_attempt:
        print(
            "New authorization after the reviewed ACTIVE_VIEW_UNVERIFIED stop; prior consumed grant remains unchanged."
        )
    if (
        input("Type AUTHORIZE X1 IDENTITY ONLY to prepare the one-use 10-minute local release: ")
        != "AUTHORIZE X1 IDENTITY ONLY"
    ):
        raise SystemExit("READ_RELEASE_REQUIRED")
    try:
        grant = prepare(
            PairingRepository(),
            args.attempt_id,
            args.service_date,
            pickups,
            deliveries,
            supersedes_attempt=args.supersedes_attempt,
        )
        print(
            json.dumps(
                {
                    "state": "PREPARED",
                    "attempt_id": grant["attempt_id"],
                    "expires_at": grant["expires_at"],
                    "production_reads_executed": False,
                    "production_writes": False,
                }
            )
        )
    except Exception as error:
        raise SystemExit(safe_code(error)) from None


if __name__ == "__main__":
    main()
