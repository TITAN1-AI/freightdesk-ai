## Current handoff: X1 0.6.2 Mapping Reliability Fix Pack

Use [ASCEND_X1_MAPPING_RELIABILITY.md](ASCEND_X1_MAPPING_RELIABILITY.md) for corrected behavior,
integrated offline verification and the next owner-only 1763/Load Basics procedure. Reload0.6.2;
no re-pair/new manual attemptID/live execution here. The 0.6.1 procedure below is historical.

## Earlier 2026-09-12: X1 0.6.1 CURRENT_LOAD immediate handoff (offline)

The first live orchestrator CURRENT_LOAD job has zero maps. Local sanitized audit corrects the
coarse expired-job report: mapping was queued at 03:22:55.347215Z, dispatched at 03:23:15.307047Z,
and rejected at 03:23:15.322125Z with MAPPING_OWNER_NOT_PRESENT. Session receipts succeeded.
No evidence establishes a load/DOM incompatibility. The audit does not establish why foreground
presence was absent at execution. The host emitted a dispatch; no useful WebBridge inspection followed.

Two code defects were corrected: probe-to-mapping lease replacement invalidated the port and let
the worker wait for a later wake; CURRENT_LOAD inherited the normal OBSERVE quiet-wait treatment
of owner-presence rejection, hiding it until the job deadline. The worker now rebinds within the
same bounded wake and gives queued capture priority over ordinary cadence. No owner navigation
hint or manual Capture button is needed for CURRENT_LOAD. Orchestrated failures remain explicit.

Persisted capture lifecycle: NOT_REQUESTED / QUEUED / DISPATCHED / ACKNOWLEDGED / COMPLETED,
with requested/dispatched/acknowledged/completed timestamps. DISPATCH is a host event; ACK is a
validated content command receipt; COMPLETED means successful provider-map schema validation
and local map persistence (no canonical shipment mutation). Neither dispatch nor ACK proves DOM identity.
Session proof is bounded at 30 seconds for CURRENT_LOAD; dispatch at 8 seconds; acknowledgement at 3;
acknowledged capture at 5, within existing 12-second executor authority and 3-second DOM capture budget.
Overall job expiry remains a cleanup fallback. Failed jobs/audit stay intact; no replay/reset.

No live execution/new job/lease occurred here. Owner reloads existing X1 to 0.6.1; no re-pair.
Same one-command retry, no ID or manual lease steps. See docs/ASCEND_MAPPING_ORCHESTRATOR.md.
OBSERVE change-driven continuation and owner-opened next-cohort workspaces are preserved.
No new LIVE_VALIDATED promotion, provider writes, operational extraction or identity-gate relaxation.

# Ascend Mapping Orchestrator V1 — X1 0.6.1

Implemented and tested offline. No live mapping job, lease, navigation review, enrollment change,
or vendor execution was performed during implementation. Earlier manual attempt IDs are preserved;
owner-x1-mapping-20260911-02 was not consumed by this work.

## Owner workflow

The owner chooses a scope and selects **Map Ascend** in the protected owner dashboard.
The alternative is one local command, run from the FreightDesk AI repository:

```powershell
.\.tools\python\python.exe -m scripts.ascend_mapping_orchestrator start
```

FreightDesk generates IDs, closes stale mapping leases, verifies the session, queues the first
workspace capture, follows reviewed navigation where qualified, saves versions, reports and closes
temporary authority. No capture/status/report/disable sequence is part of the ordinary workflow.
The CLI follows the job and prints stage changes; Ctrl+C cancels and cleans up. The dashboard and
native-host receipt hooks coordinate the same durable job. Repeated Start clicks return the current
unfinished job rather than minting another attempt.

The owner still signs in, selects the correct foreground Ascend tab/workspace, and reviews unknown
navigation once. Representative cohort members are owner-opened; no other-load opener or crawler
has been authorized/implemented. Within a verified load, qualified AUTO_MAP traverses reviewed
sections and returns to the starting section without additional clicks.

## Exact first controlled validation

1. Owner reloads the existing X1 package to **0.6.1** and refreshes the existing Ascend tab. No re-pair.
2. Open **Load 1763 → Load Basics**, keep the Ascend tab foreground, and execute just:

```powershell
.\.tools\python\python.exe -m scripts.ascend_mapping_orchestrator start --expected-load-id 1763 --starting-section "Load Basics"
```

The command manages stale mapping authority and the new internal session. It does not consume the
prepared manual -02 ID. Expected first receipt: a verified LOAD/1763 workspace, one starting-section
map and metadata-only proposals. Unknown navigation pauses at OWNER_REVIEW_REQUIRED with the
lease closed; review the proposed section names in the dashboard once. If no candidate can be
proved structurally, keep it unreviewed and inspect the preserved report. Do not invent selectors.

Current-load observation/review alone never qualifies general AUTO_MAP. After that single capture
is proven, select **Validate provider map** and supply the established representative cohort
1763,1755,1769,1737 in the dashboard. It automatically captures each owner-opened cohort workspace;
review unknown navigation once. Verified section traversal may then run as controlled validation.
No requirement to manually capture every section. Completed verified return cycles for every
cohort member qualify that observed navigation contract family; optional fields remain proposals.

No 5–10-second live timing guarantee exists yet. Scheduling, render delay and foreground focus
can affect latency. READ_TIMEOUT preserves the last completed capture stage and closes authority.

## Architecture and durable state

`executors/ascend_extension/mapping_orchestrator.py` coordinates RuntimeAccess, existing X1
BrowserSensor/DOMSnapshot/DOMDiff/LocatorGraph/AdaptiveLocator/EvidenceScorer, workspace/section
contracts, provider-map storage and AUTO_MAP. It contains no DOM selectors or browser/network API.

Explicit stages: PREFLIGHT, WAITING_FOR_ASCEND, VERIFY_SESSION, RESOLVE_SCOPE,
ACQUIRE_MAPPING_LEASE, RESOLVE_WORKSPACE, VERIFY_WORKSPACE_IDENTITY, CAPTURE_STARTING_SECTION,
DISCOVER_NAVIGATION, OWNER_REVIEW_REQUIRED, AUTO_MAP, VALIDATE_CONTRACTS, REPORT, CLEANUP,
COMPLETE, STOPPED. Resolution/identity stages describe evidence progress, not extra scrape operations.

The nonsynced `C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\mapping-orchestrator.sqlite3`
stores jobs and append-only stage events. Existing runtime tables retain grants, consumed requests,
provider maps, capture diagnostics and return cycles. No historical row or consumed request is deleted.
Versioned maps remain separate from the mutable job checkpoint.

Only a persisted top-level owner action authorizes a job. Background polling with no job is inert.
Preflight grants session-only authority (two minutes maximum, GET_SESSION_STATE only) while verifying
build/document/enrollment/pairing/session evidence. It cannot dispatch mapping. After successful
session proof it replaces that authority with a bounded mapping lease. Every new lease requires
fresh provider session verification in the existing executor. IDs and expiry are managed internally.

Default job duration: ten minutes, configurable 1–20; max five workspaces, forty section observations,
1000 field observations, and bounded capture attempts. One expired session-only probe may renew
inside the original deadline; captures never retry on uncertainty. No renewal extends the owner job.
Review, pause, cancellation, success and failure close owned temporary leases. Cohort waits retain
bounded authority only to observe the owner's next workspace change. An active unrelated read job
is not silently revoked. A grant committed before a lost coordinator checkpoint is found by its job
binding, audited and closed without replay. If both desktop/host are down, deadlines still prevent
future execution; recovery completes local cleanup when the coordinator resumes.

## Scope and maturity

| Scope | V1 behavior |
| --- | --- |
| CURRENT_LOAD | Owner-opened verified load; automatic initial capture, review if unknown, qualified AUTO_MAP if available. Optional exact-load/starting-section restriction. |
| VALIDATION_COHORT | 3–5 owner-selected representative loads, automatic capture on owner workspace changes, reviewed section traversal and verified returns. No automatic other-load navigation. |
| OWNER_NAVIGATION_OBSERVE | No permanent ID list; owner-present metadata observations on workspace/section changes under bounded authority. No traversal. |
| CURRENT_OPERATIONS | Prepared scope gate and view inventory; stops before operational manifest capture until Planning/accounting view controls and universe are provider-verified. |

Planning + Active as current/future operations and Ready for Accounting as post-delivery remain
OWNER_ATTESTED hypotheses. Lifecycle semantics remain UNKNOWN. Existing Active Loads reader and
its LIVE_VALIDATED VISIBLE_BOARD_ONLY coverage are preserved without reclassification.

Maturity vocabulary: UNKNOWN → OBSERVED → REVIEWED_NAVIGATION → AUTO_MAP_VALIDATED.
READ_MAPPING_VALIDATED and WRITE_MAPPING_VALIDATED are separate reserved validation states;
this mapping job promotes neither. Normal AUTO_MAP still requires successful controlled cohort
return receipts. Reviewing provider tabs does not activate field values or writes. Only fixed
same-document provider navigation candidates can be reviewed; Save/Submit/action hubs remain
ineligible. No model selectors, arbitrary scripts, form submissions or operational mutations.

`ProviderMapBundle` feeds the existing `AscendLoadContextAssembler`. Without independently validated
read mappings and fresh provider observations it supplies identity only; other domains stay UNKNOWN.
ShipmentOrchestrator (Ascend/Outlook/BrokerCarrier/CarrierView) is deliberately not implemented.

## Failure and diagnostics

Normal UI shows what happened, preserved evidence, a single required owner action and cleanup state.
It never presents raw provider exceptions or asks the owner to interpret consumed IDs. No blind retry.
Advanced local CLI diagnostics are available through `status --advanced`; reports do not expose IDs
unless explicitly requested. Mapping diagnostics contain approved stage names, counts and elapsed
measurements only. No customer/driver values, cookies, tokens, raw DOM or browser-state dumps.

Remaining live blockers: workspace capture has not yet persisted in production; observed navigation
must be reviewed and controlled cohort returns demonstrated; operations view contracts and other-load
navigation remain unverified. Deployment reload is owner-executed. No new LIVE_VALIDATED promotion.

## Verification completed

217 targeted offline tests passed, including orchestrator state/lease/recovery, owner API boundaries,
fixture-rendered dashboard controls, workspace mapping, AUTO_MAP, content lifecycle, enrollment and
existing runtime regression tests. Scoped Ruff passed; 22 JavaScript syntax checks passed.
Two existing dependency deprecation warnings remain. Fixture dashboard rendering was visually inspected.
No live Ascend execution, actual job/lease creation, native registration or new LIVE_VALIDATED evidence.

Final affected-suite regression: 19 tests passed after adding the OBSERVE unchanged-capture/next-workspace case. An unchanged capture now releases the pending job step while retaining NO-OP history, so the next owner workspace change can proceed. Scoped lint passed again.

## Current-load retry after the handoff correction

Reload the existing extension to 0.6.1 and refresh Ascend once. Keep Load 1763 / Load Basics open.
Run the single command below, then return focus to that already-open Ascend workspace. Starting a
terminal command may move OS focus away from Edge; foreground presence is checked at execution,
not inferred from the workspace having been open earlier. No navigation or manual Capture click.

```powershell
.\.tools\python\python.exe -m scripts.ascend_mapping_orchestrator start --expected-load-id 1763 --starting-section "Load Basics"
```

Expected: VERIFY_SESSION → ACQUIRE_MAPPING_LEASE → CAPTURE_CURRENT_WORKSPACE_NOW →
DISPATCHED → ACKNOWLEDGED → VERIFY_WORKSPACE_IDENTITY → CAPTURE_STARTING_SECTION →
COMPLETED → DISCOVER_NAVIGATION → review/complete and cleanup. Transport evidence and job stages
are separate fields. Actual missing foreground, expected-load mismatch, section mismatch or a short
stage timeout stops without consuming another capture. Expiry no longer hides a presence rejection.

Safe stops: NO_FOREGROUND_ASCEND_WORKSPACE, EXPECTED_LOAD_NOT_OPEN, STARTING_SECTION_MISMATCH,
CURRENT_LOAD_CAPTURE_NOT_DISPATCHED, CAPTURE_ACKNOWLEDGEMENT_TIMEOUT, WORKSPACE_CAPTURE_TIMEOUT,
SESSION_PROOF_TIMEOUT; existing identity/session/drift/write gates also remain in force.

0.6.1 verification: 227 targeted offline tests passed, with two existing dependency warnings. The final queue-timestamp ordering adjustment was checked again with the immediate-capture suite. Scoped Ruff and 21 JavaScript syntax checks passed. No live execution or old-audit mutation.
