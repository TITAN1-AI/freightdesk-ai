# Separate Ascend diagnostic handoff

LATEST: diagnostic 01 is consumed with a one-row BOARD_READ scope mismatch, zero details. The prepared
command now targets owner-multi-system-ascend-diagnostic-20260911-02 and includes presentation normalization.
Read ASCEND_BOARD_NORMALIZATION.md; earlier attempt-01 instructions below are historical, not a retry.

Attempt: owner-multi-system-ascend-diagnostic-20260911-01. Prepared, not executed.
The consumed owner-multi-system-20260911-01 Ascend phase remains stopped. Its unused CarrierView,
Outlook/report phases are not resumed, consumed or modified by this diagnostic.

Owner executes from the FreightDesk AI project:

```powershell
.\.tools\python\python.exe -m scripts.ascend_multisystem_diagnostic --owner-authorized
```

Local Python Playwright, headed Edge msedge, existing profile
C:\FreightDeskRuntime\Browser\booking-logistics\ascend, same-process owner login confirmation,
normal application networking, and OWNER_ATTESTED Booking Logistics identity. Existing session,
pause, policy, expiry, exact-load, bounded-control and no-write gates remain. No model/page content
can add actions. No CarrierView/Graph adapter or multi-system phase dispatcher is invoked.

Reads the authoritative source manifest through read-only SQLite. Refreshes Active Loads and requires
the exact supplied Sept 11 pickup/delivery ID sets and 8/3 counts. Max 11 detail opens in numeric order:
1755,1756,1757,1758,1759,1761,1762,1766,1767,1768,1769. Only approved bounded detail sections/labels;
no financial tab, writes, communications, uploads, raw DOM, cookies or network payload inspection.
Unknown detail identity stops; unknown optional field mappings are retained as UNKNOWN metadata.

## Isolated persistence

C:\FreightDeskRuntime\Data\booking-logistics\ascend\diagnostics.sqlite3 contains only diagnostic_grant,
diagnostic_checkpoint and diagnostic_failure records. No operational candidate or raw field values
are persisted. Checkpoints/failures use new unique IDs rather than overwriting prior observations.
The one-use diagnostic grant is claimed by future owner execution, never resets other run grants.

After session verification: SESSION_CONFIRMED. After Active Loads selection: ACTIVE_LOADS_VIEW_SELECTED.
BOARD_READ records row count, pickup/delivery counts, starting SHA256 board digest and reconciliation.
Mismatch stops before any detail. BEGIN_DETAIL_READS precedes deterministic sequential traversal.
OPENING_LOAD records approved current/affected ID and completed count before each load. Identity
success records LOAD_IDENTITY_VERIFIED; successful extraction records LOAD_DETAIL_READ_COMPLETE with
metadata only, then COMPLETED_LOAD_COUNT_UPDATED durably records the increment. Intermediate stages
and recognized section names support failure localization. Field groups record PRESENT/MISSING/UNKNOWN
and scoped mapping evidence; they do not certify a general provider contract or assignment semantics.

Failure records phase, execution_stage, affected ID, completed count, fixed underlying error_code and
safe reason, starting digest, last-known reconciliation and whether current board knowledge exists.
During detail failures the current board remains UNKNOWN; initial reconciliation is not current proof.
Known load-identity failures identify that mapping; otherwise failed_field_or_mapping stays UNKNOWN.
No next load/retry follows a failure. Cleanup errors cannot replace the first recorded failure.

After all 11 details, refresh Active Loads and persist ending hash/counts. Require exact 8/3 identities
and start/end hash equality before ASCEND_DIAGNOSTIC_COMPLETE. This does not authorize any other phase.
Earlier successful per-load checkpoints are diagnostic metadata only, not committed operational facts.

Only approved identifiers, fixed schema labels, group presence/mapping states, counts, hashes and
timestamps are stored/printed. No raw phone/name/address/reference values, HTML, notes, credentials,
session contents or provider exception messages. Body/field values used for extraction/hash comparison
exist transiently in memory and are discarded.

Verification: 30 targeted tests pass; Ruff and offline CLI help pass. Tests cover board checkpoint,
pre-load/success/increment checkpoints, first/Nth failure, affected IDs/counts, primary error retention,
start/end mismatch, exact counts, isolated stores and no phase advancement. No live execution occurred.
