"""Explicit owner-local X1 enrollment/revocation; never launches a host or browser."""

import argparse
import json

from executors.ascend_extension.enrollment import EnrollmentRepository
from executors.ascend_extension.pairing import PairingRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "revoke", "status"])
    parser.add_argument("--owner-executed", action="store_true", required=True)
    args = parser.parse_args()
    repository = EnrollmentRepository(PairingRepository())
    try:
        if args.action == "prepare":
            print(
                "Enroll the pinned X1 extension on this Windows installation. Read access stays disabled until enabled separately."
            )
            if input("Type ENROLL X1 READ ONLY to prepare the initial enrollment: ") != "ENROLL X1 READ ONLY":
                raise PermissionError("owner_enrollment_required")
            repository.prepare(owner_authorized=True)
            response = {
                "state": "ENROLLMENT_PREPARED",
                "bootstrap_file": "C:\\FreightDeskRuntime\\Data\\booking-logistics\\ascend-native\\enrollment-bootstrap.json",
            }
        elif args.action == "revoke":
            response = repository.revoke(owner_authorized=True)
        else:
            response = repository.summary()
        print(json.dumps(response | {"production_reads_executed": False, "production_writes": False}))
    except Exception:
        raise SystemExit(
            "Enrollment action stopped; inspect the local enrollment state. No private details printed."
        ) from None


if __name__ == "__main__":
    main()
