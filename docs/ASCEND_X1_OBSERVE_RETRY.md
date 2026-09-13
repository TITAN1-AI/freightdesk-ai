Current product entry: [Mapping Orchestrator V1](ASCEND_MAPPING_ORCHESTRATOR.md).
The manual per-step commands below are advanced/historical; no live execution was performed.

# X1 0.5.1 OBSERVE single-capture retry

Preparation only. No live execution performed. Existing pairing/enrollment stays in place.
Disable the old lease before reloading the extension. In Edge Extensions, reload the existing X1
package (now 0.5.1), not a new installation. Refresh the existing Ascend tab once after reload.
Do not re-pair. Confirm the extension, worker and content version are 0.5.1.

Run in the FreightDesk AI project PowerShell:

```powershell
.\.tools\python\python.exe -m scripts.ascend_x1_mapping disable --owner-executed
```

After reload/refresh, manually open **Load 1763 → Load Basics**, keep that tab selected, and run:

```powershell
.\.tools\python\python.exe -m scripts.ascend_x1_mapping enable --owner-executed --mode observe --scope validation --session-id owner-x1-mapping-20260911-02 --load-ids 1763,1755,1769,1737 --capture-load-id 1763 --capture-section "Load Basics" --minutes 10 --max-captures 1 --max-workspace-captures 1 --max-section-observations 1 --max-contract-observations 64
.\.tools\python\python.exe -m scripts.ascend_x1_mapping capture --owner-executed
```

The capture command queues exactly one request for the existing scheduler. Keep 1763 / Load Basics
open while it runs. Do not additionally press the popup capture button or queue another request.
Inspect the local status after the scheduler has processed it:

```powershell
.\.tools\python\python.exe -m scripts.ascend_x1_mapping status --owner-executed
.\.tools\python\python.exe -m scripts.ascend_x1_mapping report --owner-executed --session-id owner-x1-mapping-20260911-02
.\.tools\python\python.exe -m scripts.ascend_x1_mapping disable --owner-executed
```

Expected successful receipt: MAPPING_OBSERVED, captures=1, loads_observed=["1763"],
sections_observed=["Load Basics"], one provider-map version, last diagnostic stage MAP_PERSISTED,
values_included=false, activation=CANDIDATE_ONLY, live_validated=false, production_writes=false.
Field-contract count is the actual number of observed structural controls and is not predetermined.
No requirement to visit other cohort loads or sections until this capture is reviewed.

Stage receipts: TAB_VERIFIED (host route), SESSION_VERIFIED, ENTITY_DISCOVERY,
LOAD_WORKSPACE_CANDIDATE_FOUND, WORKSPACE_IDENTITY_VERIFIED, SECTION_IDENTIFIED,
STRUCTURE_CAPTURED (extension), MAP_PERSISTED (host transaction only).
Each receipt records counts, elapsed_ms at that completed stage, timestamp and safe stop code.
Records are append-only in runtime_mapping_diagnostics in the approved nonsynced runtime database.
No values, raw labels, selectors, private DOM, tokens or URLs enter these diagnostic receipts.
Reports keep completed maps separate from diagnostic attempts. Stage receipts do not establish mappings.

Stop on NOT_A_LOAD_WORKSPACE, identity conflict/ambiguity, wrong target/section,
WORKSPACE_BOUND, READ_TIMEOUT, expired/revoked lease, session change, or persistence failure.
Do not retry automatically or enable AUTO_MAP. No provider writes or operational value extraction.
A main-thread or worker suspension may prevent further receipts; report the last actually received
stage rather than guessing. The original -01 session has no stage telemetry; its root cause is UNKNOWN.

This constrained target is optional diagnostic scope, not a permanent 3-5-load architecture restriction.
Normal owner-present mapping behavior and separately gated AUTO_MAP remain unchanged.

Offline verification: 198 targeted integration tests passed before the final deadline/scope regression additions; the affected mapping suites were rerun afterward. Packaged/dashboard JavaScript syntax and scoped Ruff checks passed. Existing dependency deprecation warnings remain. No live validation claim.
