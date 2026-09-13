# All Loads structural diagnostic — 2026-09-10

## Latest: observed evidence applied; next owner command

The completed owner-table-schema-001 returned TABLE_STRUCTURE_OBSERVED with 9 candidates. The real
visible grid has 48 data rows and 33 headers/cells; its header clone has no rows. Page size is 100.
The existing evidence contains 13 Sept 11 matching rows/16 date occurrences, at Pick Date index 5 and
Drop Date index 7. The diagnostic's null IDs reflected unrecognized Load ID, not missing provider IDs.

The ops parser now uses this observed v1 schema, matching whitespace/case only. It validates all named
columns, 33 cells per row and no spans/index conflicts; unsupported columns 19/23 are never extracted.
Only a unique visible data-bearing grid may be selected; zero-row clones are excluded regardless of
table order. Matching rows yield load_id/status/tracking/customer/pick/drop/carrier/driver/equipment/
power_unit/trailer/truck_status from that same row. No surrounding DOM identity inference.
Facts stay in the private runtime operations store with run/column/contract provenance. Board-only
queue construction does not open details or infer phones, stops, notes, rates, timezone or live tracking.
Pick/drop queues overlap when appropriate. Expected 8/3 counts are comparison targets only.

COMPLETE_CURRENT_BOARD requires a recognized pagination information label proving start=1, end=total=
visible row count, both next/previous disabled, and an observed page size accommodating those rows.
Absent/ambiguous controls retain VISIBLE_BOARD_ONLY. No clicks or API calls establish pagination.
No classification implies complete historical/system coverage.

New attempt owner-live-ops-002 was checked unused and remains unconsumed. Owner executes:

```powershell
Set-Location 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
.\.tools\python\python.exe -m scripts.ascend_browser login-discover-ops --owner-authorized --owner-attested-booking-logistics --origin https://ascendtms.com --service-date 2026-09-11 --board-date-format US --attempt-id owner-live-ops-002
```

No new live run occurred in this update. The following sections describe the earlier diagnostic handoff.
Offline verification: 15 targeted tests passed, then 149 broader Ascend/M4B/operations tests passed
in one run. Ruff passed; two existing dependency warnings. No full-project rerun was needed for this
adapter-local change; canonical policy, sending, and dashboard implementations were not changed.

The owner-executed owner-live-ops-001 reached All Loads and stopped with
ops_board_headers_missing_or_ambiguous. Runtime ledger inspection confirms consumed=true.
The sanitized result supports passage through session/navigation gates; the owner also visually
observed the board. This is separate from OWNER_ATTESTED Booking Logistics tenant identity.
No live table schema, dated manifest, detail read or session reuse is established by that result.

The old parser requires exact guessed labels under thead th/role=columnheader, then exactly one
recognized table across frames. The stop means that condition was not met. Which DOM representation
caused it is UNKNOWN until this diagnostic runs. Do not rerun that parser unchanged.

## Owner execution only

```powershell
Set-Location 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
.\.tools\python\python.exe -m scripts.ascend_browser login-diagnose-table --owner-authorized --owner-attested-booking-logistics --origin https://ascendtms.com --service-date 2026-09-11 --board-date-format US --attempt-id owner-table-schema-001
```

Uses local Python Playwright, headed Edge msedge and the existing persistent profile
C:\FreightDeskRuntime\Browser\booking-logistics\ascend. Normal application networking/service
workers are retained. Owner login and Enter confirmation retain the same page/context. The fixed
executor checks authentication, read policy, pause/takeover and expiry, then navigates only /loads.
There are no detail opens, pagination clicks, filters, load searches, manifest builds or vendor writes.
No Computer Use, API/network-body instrumentation, screenshots, cookies or storage inspection.

This is a separate one-use diagnostic grant. owner-live-ops-001 cannot be reused; bootstrap -02
and prior historical attempts are untouched. The new attempt is claimed only when the owner runs it.

## Contract evidence

Polls same-origin frames for up to 15 seconds of rendering, with bounded DOM evaluations and an
initial render grace period. Maximum 30 candidate tables/grids, 500 rows and 25,000 cells per grid.
No-data expiry preserves structural evidence as TABLE_STRUCTURE_INCOMPLETE, not a successful read.
Data readiness is an observation of rendered rows, not proof all asynchronous content has finished.

AscendAllLoadsTableContract version 1 records provider, source live browser DOM, timestamp, attempt,
frame and table index, positional selectors grounded in actual elements, header metadata, body and
pagination selectors, hidden/scroll/clone evidence, observable page size, and zero-based column indexes.
Selectors are snapshot proposals, not a stable cross-session contract. Fixed header clones remain
separate; their columns are never silently joined to another table body.

Actual schema labels preserve whitespace/case privately; comparison only normalizes whitespace/case.
Unsafe or dynamic header labels are presence-only. Form/filter option values are excluded. Cell title/
aria-label attributes may contain private values: only established schema labels are exported; unknown
cell labels remain presence-only. No general row text or control values leave the DOM collector.
Only the fixed 09/11/2026 date occurrence counts/indexes and strictly mapped numeric Booking references
are returned from rows. Counts cover loaded DOM, including hidden/clone rows, and are not unique loads.

Explicit Load #/Load Number/Load No., Pickup Date, Delivery Date and Status labels can yield scoped
OBSERVED_PROPOSAL mappings. Generic Pickup/Delivery, spans, competing labels, inconsistent cell counts,
or conflicting ARIA indexes remain UNKNOWN. Position alone never establishes date semantics.
This diagnostic never installs or enables a parser contract. Owner review and parser adaptation/testing
are needed before another operations discovery attempt can be prepared.

Sanitized JSON is saved only under C:\FreightDeskRuntime\Data\booking-logistics\ascend as
all-loads-table-contract-<timestamp>.json; it includes the attempt ID even on failure. The same sanitized
schema/count report is printed. Diagnostic grants use the isolated operations database, not canonical state.

## Current result

IMPLEMENTED and offline-tested only. No diagnostic live run was performed during this change.
Full suite: 355 passed; Ruff and JavaScript/dashboard checks passed, two existing warnings.
Table count, actual headers, load/pickup/delivery/status mappings, service-date counts and pagination
behavior all remain UNKNOWN. No new LIVE_VALIDATED capability or operational queue is claimed.
