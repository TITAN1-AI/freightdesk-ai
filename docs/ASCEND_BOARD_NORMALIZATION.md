# Active Loads presentation normalization — owner handoff

Previous attempt owner-multi-system-ascend-diagnostic-20260911-01 stopped at BOARD_READ:
one visible row, one pickup, no delivery, zero detail completions; exact-eleven scope gate rejected it.
The saved evidence does not identify search/filter/page/render state. A retained search is plausible,
not proven. No detail-contract failure was reached. No live run occurred during this correction.

Prepared independent attempt: owner-multi-system-ascend-diagnostic-20260911-02 (unused).

```powershell
.\.tools\python\python.exe -m scripts.ascend_multisystem_diagnostic --owner-authorized
```

Run from the FreightDesk AI project. Existing headed Python Playwright/msedge/profile, same-process
owner confirmation, normal application networking and OWNER_ATTESTED Booking Logistics tenant remain.
No CarrierView/Outlook/multi-system phase advancement, production writes or new profile.

## Fixed normalization actions

Navigate /loads and select the existing semantic Active Loads control. Require its visible selected
state via aria-selected/aria-current or supported active classes. Wait for a unique, visible data-bearing
grid with the observed 33-column contract. Header-only clones never qualify. The DOM table index is
observed afresh from that validated structure; no fixed table index or provider-generated selector.

Inside that table's observed DataTables wrapper only:

- Clear its unique nonempty search input with fill(''), without Enter or submission.
- Select the observed value 100 in the unique page-size control when current numeric size is smaller.
  If that option is unavailable, stop; do not guess another setting.
- If pagination info proves a later page, click the uniquely observed presentation First/page-1 control.
  Reject submit/reset/file/password controls and non-fragment navigation destinations.

No shipment status/assignment, saved fact, account preference, notes, upload or communication controls
are invoked. Recognized status/date/branch/user/column filters are described by category, presence and
safe selected-state enums. Nonneutral unsupported filters stop with board_filter_requires_observed_reset_contract;
no guessed reset logic or arbitrary DOM click/action dispatcher. Unknown wrappers/ambiguous controls stop.
No DataTables internal API, localStorage/cookies or network traffic inspection is used.

Observe DOM stabilization (one second unchanged, no visible processing indicator), bounded to 15 seconds
per observation period, 3 seconds per frame evaluation. Initial read + at most three presentation changes
+ final scope observation: five periods maximum. Final observation can wait the full render bound when
scope is still wrong. Polling never repeats a failed action. Zero qualifying data rows remains a safe stop,
not permission to select a header clone as a data grid. Unknown non-DOM filtering remains a limitation.

## Scope, provenance and freshness

Require exact pickup IDs 1755,1756,1757,1758,1759,1762,1768,1769 and delivery IDs 1761,1766,1767.
Counts must be 8 and 3 with 11 unique matching operational loads. A count match with different IDs, or
any extra date-matching ID, fails. Other active rows on other service dates are outside this target scope.
Do not drop unexpected rows to force reconciliation.

Before details, save source_view=ACTIVE_LOADS, normalized_board_hash, normalized_board_observed_at,
starting pickup/delivery counts and observed/missing/unexpected ID sets. The semantic SHA256 digest
uses sorted target-date operational rows/approved field values only; it excludes table index, row
ordering, pagination, search/page-size state and UI metadata. Raw row values never enter diagnostics.
Actual observed shipment-state changes alter that digest. At the end, normalize/read again; require
the same exact scope/counts and semantic hash. Maximum 11 detail opens, unchanged bounded detail reader.

Diagnostics stay in C:\FreightDeskRuntime\Data\booking-logistics\ascend\diagnostics.sqlite3:
execution stage, safe code/reason, observed row/total/page/page-size counts, empty/nonempty search state,
supported filter metadata, normalization actions, safe approved/missing/unexpected numeric IDs,
semantic/start/end hashes and per-load progress. No private search strings or row contents are saved.
Earlier grants and checkpoints remain untouched; the new grant is claimed only on owner execution.

Targeted fixtures cover retained one-row search, clearing it, page-size/first-page normalization,
clone rejection, exact scope, wrong/extra IDs, unsupported filters, no shipment mutation, semantic hash
stability for presentation changes, state-change detection, and separate old/new attempt grants.
Verification: 24 targeted tests passed; Ruff passed. Two existing dependency deprecation warnings remain.
