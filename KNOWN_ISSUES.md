# Known issues - Ascend write note v0 2026-09-20

Private-internal-note write is **FIELD LIVE_VALIDATED** for Avery 0.1.10 smoke on
load 1763 only (`04e0617`: 403 PASS; A `d5c8a6cd` OWNER_PATH/`already_open`;
B `9eff223c` VERIFIED SAVE_STAY `already_open` `note_present=true`
`bridge_version=0.1.10`). Whole-form Save can still submit unrelated dirty fields —
documented on the receipt, not eliminated. Harvest `ACTIVE_VIEW_UNVERIFIED` is
independent. Demo approval mint is not production authority. Other writes stay
blocked. See docs/ASCEND_WRITE_NOTE_V0.md.

# Known issues - capability map v0 2026-09-20

The capability matrix is a foundation, not a complete LIVE Ascend API. `GET /v1/ascend/loads/{id}`
returns only last harvested board fields (ID / pick / drop / load_status). Load Basics atlas
labels other than those board columns have no cached values. Status write is a 501 stub
(APPROVAL_REQUIRED when implemented). Assign, expenses, public notes, documents, and
communications stay FORBIDDEN or NOT_STARTED. Private-note `#scratch` / WHOLE_FORM_SAVE
landed with PR #8 and is FIELD LIVE_VALIDATED for the 1763 SAVE_STAY already_open path
only. No scheduled server board sync and no verify-after-write on this slice. Next LIVE
field after note VERIFIED: status change.

# Known issues - portable bridge v0 2026-09-19

Track B is a demo/unpacked foundation, not a store product. The Ascend facade reads stored harvest
only; it is not an Ascend API and not LIVE_VALIDATED. Agent Bearer (`DEMO_AGENT`) skips the popup
for API auth only; harvest still needs Bridge on an Ascend tab. After Load unpacked, 0.1.1 tries
isolated reinject on open Ascend tabs; a full Active Loads reload is still required when the
browser blocks that inject or the tab is not exact `/` or `/loads`. Remaining gaps: FreightDesk
Cloud OAuth/device-code auth, multi-tenant agent identity, HTTPS cloud API origin, Chrome/Edge
store listing and icons, Firefox, full dashboard shipment list from harvest, stronger token
storage, operational values, general writes, AUTO_MAP, and any LIVE_VALIDATED harvest or note
write. Localhost host permissions must be replaced before store submission. Revoke stops further
accepted posts; the last snapshot stays readable on the facade. BL live ops and X1 native
enrollment are unchanged.
See docs/AGENT_ASCEND_API_V0.md, docs/ASCEND_FACADE_V0.md and docs/ASCEND_WRITE_NOTE_V0.md.

# Known issues - audit repair 2026-09-13


Fresh Windows CI exposed two portability defects: CRLF checkout changed the pinned adaptation hash,
and .NET Framework's redirected-input writer inserted an encoding preamble into native binary frames.
Git attributes preserve the reviewed LF bytes; the launcher source now prevents the preamble, with
console/headless synthetic regressions. The installed host is unchanged; deployment and real pairing
remain outside this work. Hosted full-suite verification of these fixes is tracked in PR #1.

A01-A10 repairs are implemented in source; see [the repair handoff](docs/WEBBRIDGE_V2_AUDIT_FIXES.md).
Earlier unconditional acceptance missed reproduced defects. V2 remains offline, not LIVE_VALIDATED.
A 19-field fixture now fits (15,298 graph / 29,802 combined bytes); a 32-field fixture still safely
exceeds the unchanged combined payload limit. Large unrelated chrome may stop at WORKSPACE_BOUND.
Generic fields/tables, conditional semantics, installed MV3/host lifecycle, cross-section performance
and Phases 3-7 remain deferred or UNKNOWN. Metadata authorizes no values, writes or V2 AUTO_MAP.
History reports have explicit finite bounds; full-history pagination is future work.
Source-only rollback is rehearsed; a live version-pinned package/migration remains separately
authorized future work. The separately referenced revised plan remains unavailable.

## Historical pre-audit status (current limits above supersede older completion claims)

# Known issues — after exact X1 metadata capture

## V2 provider migration remains unvalidated

The isolated-draft gaps below are now resolved in the real synthetic pipeline; see
[the acceptance handoff](docs/WEBBRIDGE_V2_PHASES_0_2_ACCEPTANCE.md). V1 stays default. There is no live
V2 toggle or authorized migration command. A future packaged, version-pinned migration needs separate
authorization. Operational field meanings, full section coverage, inaccessible frames/closed roots,
AX/paint channels and roadmap Phases 3–7 remain unvalidated/deferred. The separately referenced revised
implementation-plan document remains unavailable and is not claimed reviewed.

The V1/V2 sibling-region mismatch and duplicate progress sequence were found and fixed offline.
Runtime completion is atomic within its existing transaction; coordinator recovery is separate.

## Historical draft gaps — resolved by the acceptance handoff above

The authorized Phases 0–2 draft passes 61 focused synthetic tests, but remains outside the
actual X1 host/worker/content/map-store pipeline. Typed evidence/visibility and reference-resolution
contracts, source-incorporation records, V1 compatibility and integrated failure/cleanup tests are
unfinished. TestRuns graph persistence must not be mistaken for a completed provider map.
See [the revised-brief comparison](docs/WEBBRIDGE_V2_PHASES_0_2_REVIEW.md). Its referenced separate
IMPLEMENTATION_PLAN_REVISED document was not provided/found at the expected project-doc path.

A draft consistency bug was found and fixed: capture now snapshots scalar proof bindings instead
of retaining the mutable runtime object. Focused replacement/change tests now pass. This was an
offline draft defect, not evidence of another live Ascend failure. Two existing dependency warnings
remain. No live action, new grant or V2 capability promotion occurred.

## WebBridge V2 design gaps — no production changes in source audit

The [source audit](docs/BROWSER_INTELLIGENCE_CODE_HARVEST.md) proposes replacing the limited
snapshot/diff/locator internals with indexed graphs and bounded candidate algorithms. None of
the reviewed projects proves exact business ownership or read-only effect from similarity alone.
SPA causal ownership, virtualized coverage and real cross-section behavior remain unresolved
validation requirements. V2 has not been implemented or live-tested.

Legacy webbridge.js graph() reads values/text to compute value presence; the validated
workspace.js metadata capture is a different path. V2 must enforce privacy at collection,
including value-getter tests, rather than treating values_included=false as never-read proof.
No claim of leakage from the successful exact capture is made by this research.

Direct code harvest needs exact-file notices and dependency review. Skyvern AGPL, axe-core MPL,
Crawl4AI's extra attribution terms and the Healenium source-artifact provenance gap are recorded
in [the provenance plan](docs/WEBBRIDGE_V2_PROVENANCE.md). No upstream code was incorporated.

## Latest: exact capture succeeded; historical invalidation cause still unknown

On 2026-09-12 the fifth/final authorized agent iteration passed session/readiness, dispatch/ACK,
exact provider LOAD/1763 identity and one Load Basics metadata-only map (19 candidate fields).
Authority is REVOKED and cleanup COMPLETE; the live loop is closed. No further retry is prepared.

The live section mismatch is now understood: selected current-route Load Basics control and
unique matching H1, with the visible form region in a later sibling branch. Existing ancestor
roots contained navigation and were correctly rejected. The narrow sibling proof now succeeds,
while identity, ambiguity, visibility, field bounds and write blocks remain enforced.

The earlier owner-run DOCUMENT_CHANGED occurred after fresh session proof but before dispatch.
Its branch was not persisted and it did not recur, so historical cause remains UNKNOWN.
Coordinator masking as SESSION_UNVERIFIED is corrected. The introduced causal ACK binding
omission and browser-chrome focus issue were also corrected and independently tested.

Remaining limits: CURRENT_VISIBLE_SECTION_ONLY metadata; candidate field meanings are not
validated against operational values. Other real loads/sections, general OBSERVE lifecycle,
AUTO_MAP controls and drift behavior remain unvalidated. OWNER_REVIEW_REQUIRED is the next
navigation gate, with read authority already closed; it does not authorize continuation.
No new enrollment, login, re-pairing or owner retry is needed for the completed exact task.
Final relevant suite: 411 passed; two existing dependency warnings. See
[ASCEND_X1_SESSION_CAUSAL_DEBUG.md](docs/ASCEND_X1_SESSION_CAUSAL_DEBUG.md).
Earlier unknown-section/no-live statements below are historical preparation records.

## X1 0.6.2 reliability corrections — offline verified, live structure still unknown

The review's coordination/diagnostic defects are corrected; see
[ASCEND_X1_MAPPING_RELIABILITY.md](docs/ASCEND_X1_MAPPING_RELIABILITY.md). The real selected-state and
section-target relationship behind WORKSPACE_SECTION_UNVERIFIED remains unobserved. New diagnostics
will distinguish the exact predicate; no selector or live capability was guessed. A dispatched
non-load or ambiguous workspace still stops. Owner waiting remains bounded by the original job lease.
No live retry ran. Database-unavailable fallback cannot persist into an unavailable database and
reports fixed failure with UNKNOWN cleanup. Existing dependency warnings remain documented.

## Historical pre-fix review — superseded by X1 0.6.2 above

See [ASCEND_WORKFLOW_REVIEW.md](docs/ASCEND_WORKFLOW_REVIEW.md) for evidence and exact source locations.
Newest persisted live stop is WORKSPACE_SECTION_UNVERIFIED after successful workspace proof;
zero maps. The resolver does not preserve whether zero or multiple section roots caused rejection.
Offline reproductions confirm observer removal on session refresh, a permanent READ_JOB_ACTIVE
dependency wait, and fatal drift from optional fields across different loads. Normal status hides
already-safe stop/stage evidence; owner focus and startup wake timing lack a complete handoff test.
Healthy 20-second native heartbeat ACKs also wake execution: the 60-second alarm alone is not
a proven timeout cause. No production fixes or live run were performed during this review.

## 2026-09-12: X1 0.6.1 CURRENT_LOAD immediate handoff (offline)

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
validated content command receipt; COMPLETED means successful canonical provider-map validation
and local map persistence (no canonical shipment mutation). Neither dispatch nor ACK proves DOM identity.
Session proof is bounded at 30 seconds for CURRENT_LOAD; dispatch at 8 seconds; acknowledgement at 3;
acknowledged capture at 5, within existing 12-second executor authority and 3-second DOM capture budget.
Overall job expiry remains a cleanup fallback. Failed jobs/audit stay intact; no replay/reset.

No live execution/new job/lease occurred here. Owner reloads existing X1 to 0.6.1; no re-pair.
Same one-command retry, no ID or manual lease steps. See docs/ASCEND_MAPPING_ORCHESTRATOR.md.
OBSERVE change-driven continuation and owner-opened next-cohort workspaces are preserved.
No new LIVE_VALIDATED promotion, provider writes, operational extraction or identity-gate relaxation.


## 2026-09-11: Mapping Orchestrator V1 / X1 0.6.0 (offline)

Read docs/ASCEND_MAPPING_ORCHESTRATOR.md. A single protected-owner Map Ascend action or
scripts.ascend_mapping_orchestrator start manages durable stages, IDs, session-only preflight,
bounded mapping authority, automatic starting capture, navigation review, qualified AUTO_MAP,
reports and cleanup. A repeated click preserves the active job. Interrupted capture never retries.
The existing extension/native transport, provider workspace contracts and WebBridge sensors are reused.
Planning/accounting operations scope is still unverified and fails closed; Active Loads remains
VISIBLE_BOARD_ONLY. Representative cohort loads are owner-opened; reviewed sections traverse automatically.
General AUTO_MAP still requires controlled cohort return receipts. Read/write field mappings remain
unvalidated. No new LIVE_VALIDATED promotion and no live job/lease/attempt was created this turn.
The old manual -02 ID and all prior audit remain intact. The orchestrator supersedes manual per-step
lease/session/capture/report commands as the normal owner workflow; advanced diagnostics retain IDs.
Owner first reloads existing X1 to 0.6.0, opens 1763 / Load Basics, then runs the single documented start
command. No re-pair, Computer Use, Playwright live run, vendor request or production write here.


## 2026-09-11: X1 0.5.1 OBSERVE capture diagnostics (offline)

Owner session owner-x1-mapping-20260911-01 persisted zero provider maps. Local audit shows
session VERIFIED at 2026-09-12T02:08:41.468188Z, mapping dispatch at 02:08:41.491432Z,
and READ_TIMEOUT recorded at 02:11:48.689305Z (187.198 seconds later). The configured
read deadline was 12 seconds; the audit gap is not proof of DOM execution duration.
No internal capture stage/count was persisted, so the precise live timeout cause remains UNKNOWN.
Code inspection found page-wide visibility checks before bounds and repeated workspace discovery.
0.5.1 filters semantic candidates before layout checks, uses a 3-second cooperative capture deadline,
revalidates within the discovered shell, and records bounded metadata-only stage receipts through
the existing paired channel. Renderer/process suspension can still exceed wall-clock deadlines;
the host retains the last received stage and rejects late maps. No timeout increase or transport redesign.

New unused prepared session: owner-x1-mapping-20260911-02. OBSERVE only; cohort
1763,1755,1769,1737; first retry is enforced as 1763 / Load Basics, one capture maximum.
No session enabled, installed extension reloaded, vendor execution or live promotion here.
Old audit is preserved. Read docs/ASCEND_X1_OBSERVE_RETRY.md before owner execution.
Operational detail facts remain UNKNOWN; maps CANDIDATE_ONLY and metadata only.


## 2026-09-11: workspace Mapping Mode prepared; live compatibility/coverage unknown

Source0.5.0 is offline-tested, not live-run. Actual persistent-shell/section selectors, field mappings,
optional/conditional fields and cross-view lifecycle semantics remain unverified. Owner-observed section
names are supported vocabulary, not proof of live selectors. Unknown labels/areas are redacted and
remain unclassified. Only the current visible section is captured; static text without a safe observed
control relationship remains unmapped. Normal hints are best effort; hidden/fleeting sections or worker
suspension can cause missed observations. No 5-10-second operational answer guarantee is claimed.
First AUTO_MAP cohort is 3-5 IDs. Normal modes have no mandatory ID list; AUTO_MAP requires reviewed
navigation and successful reviewed cohort cycles, while OBSERVE learns unknown structure passively. AUTO_MAP supports reviewed same-document role=tab navigation only; full-document transitions
and unobserved controls remain unverified. Bounds/revoke/expiry/conflicts stop without crawling/retries. See
[Mapping Mode handoff](docs/ASCEND_X1_MAPPING_MODE.md). Current operational values and read mappings
remain UNKNOWN/unvalidated; preserved board LIVE_VALIDATED scope does not extend to Mapping Mode.
No live actions performed; old proposed panel-detail -03 is superseded. Existing dependency warnings
remain. Do not revisit healthy enrollment/native/board systems as part of this milestone.


## 2026-09-11: detail -02 exhausted an unclassified 12-container snapshot bound

Runtime prerequisites and exact1755 FIND succeeded. The local failure is OPEN_READONLY, not field
mapping. DETAIL_BOUND_CONTAINERS had three possible12-item checks; no measured/category breakdown
was retained. Pre-click snapshot is strongly suggested by35ms elapsed, not proven by click receipts.
Old snapshot counted all matching layout containers before relevance/visibility and traversed their
forms/headings. 0.4.3 fixes this offline using causal roots and category-specific bounds. It has not
been live run. No invented exact count, provider selectors or capability promotion. Existing identity,
field/write limits remain. -02 consumed; -03 proposed only. See docs/ASCEND_X1_CAUSAL_CONTAINERS.md.

## 2026-09-11: X1 board failure lacks structural evidence; 0.4.2 correction offline

The 22:29:36 UTC BOARD_SCHEMA_INVALID receipt contains only ACTIVE_LOADS view proof. No exact
predicate/header count/cell width/required-header mapping/clone/init state can be recovered locally.
Source 0.4.2 removes a reproduced empty-header-clone selection defect, uses semantic header mapping
with unchanged full-schema checks, waits for bounded stable rendering, and persists safe structural
diagnostics plus predicates. It has not been run on the current provider DOM. Unknown live schema
drift must remain unknown; no claim that the selector reproduction proves this run's cause.
The owner revoked the latest lease at 22:31:43 UTC. Retained board data predates this run and is
not current evidence. Reload plus a fresh short owner lease is needed for a future board-only check;
no refresh/re-pair/detail queue. See docs/ASCEND_X1_BOARD_SCHEMA.md. No live execution this turn.
Targeted checks pass after updating an old permission-list test to the existing 0.4.1 scripting
permission. No additional permission was introduced. Existing dependency deprecations remain.

## 2026-09-11: source X1 0.4.1 lifecycle correction (offline only)

Local evidence shows a fresh 8-row Active Loads receipt at 22:04:35 UTC, then CONTENT_SCRIPT_STALE
at 22:04:40. Current count was retained after failure. Initial handshake category/builds were not
persisted. Deterministic defect: stored REFRESH_ASCEND_TAB prevented subsequent tab handshakes even
after manual refresh/login. Do not tell the owner to refresh/re-pair again.

Source0.4.1 adds a manifest/worker/content/host/controller build handshake, document generation,
fixed packaged top-frame ISOLATED reinjection and precise missing/old/port/document/protocol/policy
states. The scripting API capability is newly declared; host permissions remain Ascend-only.
Versioned dispatch prevents old surviving listeners from executing reads. Current vs retained board
evidence is explicit. Source update preserves durable enrollment; expired leases alone need renewal.
See docs/ASCEND_X1_CONTENT_LIFECYCLE.md for evidence, limits, permission change and owner retry.
260 targeted offline tests passed; Ruff and JS syntax passed. At 22:24:20 UTC final local check,
the existing lease had expired at 22:19:34 UTC (not revoked); the next owner retry needs renewal.
No live run, lease enable, re-enrollment or detail attempt was executed. Board LIVE_VALIDATED scope
is preserved; this recovery and all operational detail mappings remain not live validated.


## 2026-09-11: X1 operational detail contract v1 prepared offline (source 0.4.0)

Added bounded WebBridge DOMSnapshot/DOMDiff, BrowserSensor, LocatorGraph, AdaptiveLocator,
ProviderContract and EvidenceScorer components to X1's existing transport. Exact provider detail
identity precedes metadata-only mapping of 19 operational fields. LEVEL_1/2 can verify an observed
read mapping; LEVEL_3 remains PROPOSED and conflicts UNKNOWN. Every contract remains CANDIDATE_ONLY;
no automatic activation, private values, finance/notes, writes or vendor LIVE_VALIDATED promotion.

A new one-use owner detail queue pins one ID from a fresh Active Loads board and its semantic hash,
then performs FIND/OPEN/identity/discovery and stops. Append-only candidate versions, atomic receipt
persistence, safe metadata report and offline drift/identity/security tests are implemented.
Proposed unused ID owner-x1-detail-20260911-01 is not consumed. No live runtime schema change, lease,
read, host execution, extension reload or re-pair was performed. Read access remains revoked.
See docs/ASCEND_X1_DETAIL_CONTRACT.md for exact six-minute owner-lease steps and stop conditions.
244 targeted offline tests passed; Ruff, JavaScript syntax and runtime Node fixtures passed.
Existing dependency deprecation warnings remain. No live execution.

The earlier board runtime remains LIVE_VALIDATED (three cycles, 11 visible loads, one proposal,
two no-ops and no post-revoke board reads). Detail mappings remain UNKNOWN / not LIVE_VALIDATED;
VISIBLE_BOARD_ONLY and OWNER_ATTESTED limitations remain. No all-load detail batch is prepared.


## 2026-09-11: X1 0.3.1 local tab-lifecycle diagnosis (no live execution)

Owner confirms durable enrollment/reconnect worked. Existing runtime receipts prove one eligible
Ascend tab at `/`, two authenticated session reads and successful automatic binding, followed by
ASCEND_NAVIGATE_ACTIVE_LOADS / READ_TIMEOUT at its 12-second deadline. No board receipt/proposal.
The underlying browser timeout cause and tab/reload ordering were not persisted. The observed
15-minute read lease expired at 19:09:30 UTC; no new lease or enrollment was created here.

Source 0.3.1 adds version-aware, lease-gated bounded refresh for an existing stale tab, port reuse,
explicit navigation transition/fresh-document proof, distinct discovery/view/scheduler statuses,
and safe stage/wake/count diagnostics. Extension alarms are the execution owner after CLI exit.
WAITING_FOR_ASCEND now requires a zero-tab observation; initial state is DISCOVERING_ASCEND.
Reload is required to adopt source changes. Existing enrollment is preserved; owner retry needs a
fresh read lease because the inspected lease expired. See docs/ASCEND_X1_TAB_LIFECYCLE.md for the
12-question evidence table, limits, recovery rules and exact owner commands. No automatic live run.

215 targeted offline tests passed; Ruff and JavaScript syntax checks passed. Existing dependency
deprecation warnings remain. No live compatibility promotion for 0.3.1.



## 2026-09-11: persistent operating model implemented; provider compatibility still unverified

Source X1 0.3.0 removes repeated bootstrap/one-shot setup from normal operation after explicit durable
enrollment and read-lease enable. No real persistent enrollment or lease has been created, and the
extension/source update is not installed by this task. Actual restart/reconnect/automatic navigation
compatibility still needs the bounded owner-run plan in docs/ASCEND_X1_RUNTIME.md. Earlier -01 remains
consumed; old audits/grants are retained. No current connected/PAIRED claim is inferred from fixtures.

The actual selected-view signal absent in the first live failure remains unknown. The view contract
continues to fail closed; persistent mode does not bypass it. Detail identity and field mappings remain
unverified against real Ascend. READ_LOAD/STOPS/ASSIGNMENT return UNKNOWN fields until an observed
contract exists. ID/date hashes do not detect assignment/rate changes. Visible board coverage does not
establish whole-account absence; no pagination or canonical apply is implemented.

Booking Logistics identity remains OWNER_ATTESTED, not a provider-derived account identifier.
Persistent local enrollment and app authentication must not be described as provider tenant verification.

Eight-hour lease expiry requires explicit renewal; password/MFA remains manual; multiple unbound
authenticated tabs need owner selection. Security mismatch, ambiguous DOM or uncertain detail clicks
stop rather than retry blindly. Dashboard owner-session expiry may require its private launcher again;
that is separate from enrollment and the native read lease. Existing dependency warnings remain.

Final combined targeted run: 232 passed. Existing native self-tests pass with lazily constructed
enrollment dependencies; config-only tests do not access credentials or persistent enrollment.

## 2026-09-11: X1 view compatibility awaits observation; first grant consumed

The first live extension test passed session verification then stopped ACTIVE_VIEW_UNVERIFIED before
board extraction. Version 0.2.0 saved no selected-view candidates, so the actual view and exact absent
or conflicting DOM state are unknown. Its detector omitted parent li.active and aria-current=true
already accepted by the older normalizer. Source 0.2.1 repairs that gap and adds bounded independent
provider-view contracts/diagnostics; real DOM compatibility remains NOT LIVE_VALIDATED.

Prior owner-x1-identity-1755-20260911-01 is consumed and its selected-tab port invalidated. Last verified
pairing has expired; latest pairing audit reports PAIRING_ALREADY_CONSUMED. This is separate from the
Active Loads failure, not evidence of a broken transport or lost Ascend login. No re-pair authorized now.
An extension Reload is required for new source and itself discards pairing. A future owner-authorized
retry needs renewal, explicit tab selection and a fresh read release; prepared unused -02 can only
supersede this exact reviewed consumed failure, never reset it. No grant was created here.

117 targeted tests passed with two existing dependency warnings. Safe state classes/labels are
allowlisted; unsupported live markers continue to fail closed. Do not retry automatically, force 8/3
counts, weaken the view gate or resume Playwright identity experiments. Current STOP and conditional
owner steps: [ASCEND_X1_VIEW_CONTRACT.md](docs/ASCEND_X1_VIEW_CONTRACT.md). Older pending-test and
no-successor statements below are historical.

## 2026-09-11: pairing succeeds; extension provider reads await first owner test

Owner's 0.1.2 PAIRED / PAIRING_SUCCESS result resolves the earlier local pairing transport blocker.
Only local transport is LIVE_VALIDATED (OWNER_REPORTED). The new 0.2.0 read controller has offline
evidence only; actual Ascend DOM compatibility/session, board reconciliation and detail identity
remain NOT LIVE_VALIDATED through X1. No provider-derived Booking Logistics identity is claimed.

This first release requires the owner to manually open Active Loads before tab selection. It reads
only the current visible board, not pagination or whole-account coverage; no automatic navigation or
filter edits. The one-test 2026-09-11 US date / exact 8/3 oracle must still apply, otherwise STOP.
Tab reload/navigation, native restart, pairing loss, expired grant or failed identity cannot resume
a consumed test. Pairing/read grants expire after ten minutes; Reload requires fresh pairing. One
prepared read grant cannot be replaced or renewed by this release. A dropped connection can leave
DISPATCHED/UNKNOWN; this is consumed uncertainty, not verified identity.

Operational extraction remains blocked after identity success. Playwright identity discovery remains
CLOSED. See [current owner handoff](docs/ASCEND_X1_READONLY.md); older pending startup/pairing sections
below are historical. Existing dependency deprecation warnings remain documented; no vendor check here.

## Native launcher buffers incremental traffic; installed fix pending

The existing CopyTo launcher fails a compiled small-frame fixture before stdin EOF. Explicit relay
Flush fixes two successive frames offline. The installed binary remains unchanged until owner runs
RebuildLauncher. Existing registration is valid in both registry views; do not rerun Register (its
other-view guard intentionally rejects duplicate entries). Paths/imports are valid and clean.
Live audit proves HELLO/DPAPI/one-use gates passed with zero consumed pairings, but lacks frame-output
checkpoints. Do not invent an exact Edge-side error or rejected proof. New startup JSONL and owner-only
self-test cover that gap. No browser/vendor run, bootstrap or pairing retry here. See
docs/ASCEND_NATIVE_STARTUP.md; owner self-test must finish before any later pairing retry.

## 2026-09-11: reachable native host; original pairing failure not attributable yet

Owner confirms local host reachability and completed registration. Real pairing has not succeeded.
0.1.1 did not retain the specific failure: swallowed parse/schema/native exceptions, error polling
overwrite and a synchronous connect/epoch edge case are now fixed/instrumented in 0.1.2. These defects
explain missing diagnostics, not a proven cause of the owner's particular handshake failure.
Persistent panel/explicit Import cover popup/file-picker lifecycle uncertainty without DevTools.
Next owner retry needs reload and fresh Pair; consumed/expired old state was not privately inspected.
No live action/registry/new bootstrap in this task. Unavailable runtime cannot persist a diagnostic;
PAIRING_PERSIST_FAILED makes that visible. Ascend reads/writes and READ_ONLY_READY remain blocked.
See docs/ASCEND_NATIVE_MESSAGING.md for exact flow and safe audit schema.

## 2026-09-11: native deployment and live read release remain unverified

Native pairing/status host and owner-run setup are implemented and offline-tested, not registered or
paired with the installed Edge extension. Owner must capture its actual ID locally; no ID was guessed.
Unsigned launcher depends on current checkout/Python and the Windows .NET Framework compiler. Actual
registry/ACL deployment, Edge launch and real handshake remain owner-executed checks, not live evidence.
No persistent browser key: restart/reload/lost worker/host crash requires explicit new Pair/import.
Expired bootstrap files are invalid even if a crash leaves them; Reset removes them. ID changes require
deliberate migration, never silent rebinding. Source 0.1.1 awaits owner reload after reviewed preparation.

PAIRED proves only a local channel. All vendor reads remain blocked; no READ_ONLY_READY in this build.
Policy-bound controller transport, owner-tab routing/lifecycle invalidation, bounded stabilization and
identity-only receipt must precede the first live plan. Current OPEN returns identity_verified=false;
do not bypass this with operational reads or revive Playwright identity experiments. No new live grant.
See docs/ASCEND_NATIVE_MESSAGING.md. Existing dependency deprecation warnings remain.

## Latest: Playwright identity experiments closed; extension production prerequisites remain

Final grant consumed at board_tables 9/8; no opener record or identity contract. An extension can
retain interactive context but cannot manufacture provider identity. Existing row evidence supports
board-row reads only. X1 is offline: private pairing/DPAPI provisioning and native launcher/helpers now
have an offline foundation, but real registration/pairing, signing, production tab routing,
stabilization/lifecycle receipts and actual detail DOM contract remain unverified or unreleased.
No row-bound detail fallback or write authorization.

## Final targeted identity validation pending

One final owner-executed attempt is prepared, not run: owner-ascend-final-identity-1755-20260911-01.
Identity remains unverified. Failure after its grant is consumed requires an engineering comparison
of an authenticated-session extension bridge versus evidence-supported row-bound identity; no retry,
new Playwright identity grant or weakened gate. Prior bound measurements remain unrecoverable.

## Latest: old causal bound measurement is unrecoverable

The consumed causal attempt saved one shared error for frame eligibility, frame count, candidate count
and descendant count gates. No category/count or opener checkpoint exists. Do not guess the fired branch.
Targeted refactor is offline-only; real identity remains unknown. No new live attempt is prepared.
See docs/ASCEND_TARGETED_IDENTITY.md. Stop Playwright experiments if a future final targeted attempt fails.

## Latest blocker: provider binding between row 1755 and opened detail remains unknown

Identity diagnostic -01 is consumed and found no candidate fields or contract. A same-page modal is
plausible, not proven. Prepared causal diagnostic inspects one exact opener and changed detail surfaces.
Unknown script semantics, redacted paths/attributes, frame replacement, missing stable DOM binding and
multiple surfaces fail closed. No identity gate weakening or new operational LIVE_VALIDATED claim.
See docs/ASCEND_CAUSAL_IDENTITY.md; earlier prepared/not-run identity entries below are historical.

## Current blocker: opened load 1755 identity representation

Normalization is proven by diagnostic 02; do not rework it. The old visible-label identity scan could
not verify 1755. Actual identity representation remains unobserved. Separate one-load diagnostic is
prepared; it may emit a scoped contract only from consistent live identity evidence. Unknown query/route
semantics and duplicate/conflicting sources stop. No new vendor read or general contract validation yet.

## Current blocker: incomplete Active Loads presentation state

Diagnostic 01 reached BOARD_READ with 1 row / 1 pickup / 0 deliveries and stopped before details.
Specific cause (search/status/date/user/page/async state) remains unproven. New diagnostic 02 prepares
bounded DataTables presentation normalization and exact scope diagnostics. Unrecognized active filters,
missing selection evidence, wrappers or reset controls stop; they are not guessed. Zero data-bearing grids
cannot be normalized using header clones. No vendor action or detail-page modification occurred here.

## Next boundary: isolated Ascend diagnostic, owner execution only

The prior failure still has no recoverable root cause. Separate attempt
owner-multi-system-ascend-diagnostic-20260911-01 is prepared, not run; no selector fix was guessed.
Checkpoints are metadata-only and do not become operational candidate evidence or authorize later phases.
Field mappings remain unknown until observed; failure-time board freshness is unknown unless reread.
See docs/ASCEND_MULTI_SYSTEM_DIAGNOSTIC.md. Existing multi-system phase grants remain untouched.

## Historical multi-system stop cannot be attributed retrospectively

Only the Ascend grant exists for owner-multi-system-20260911-01. bounded_phase_failed was terminal-only;
there is no saved underlying exception, stage, completed-load evidence, board-change result or run-linked
audit. Detail contract failure is possible but unproven. Do not guess a load or call the board changed.
Future safe progress/error reporting is implemented and tested; no live attempt was launched to diagnose
the missing evidence. CarrierView/Outlook/report remain unused; later phases lack required Ascend evidence.

## Multi-system live result remains pending

Ascend detail mappings beyond observed labels, operational assignments, verified phones/complete stops,
CarrierView future-filter live behavior and tracking/app/external-type semantics are not yet established.
New workflow remains fail-closed. Owner oracle 7/1/3 is not provider evidence. Narrow Outlook claims
need trusted load/sender association and review; no unverified claim becomes a creation fact. Bounded
search misses are not absolute absence. Native creation wire/company mapping and communication effects
remain separate approval blockers. No new vendor action occurred during this preparation.

## Current CarrierView read boundary

Active Loads manifest owner-active-loads-20260911-02 is owner-reconciled (8/3 exact IDs); earlier failure
notes remain historical. Actual CarrierView results await owner execution. Active/past filters do not
prove future/all-record coverage; misses never prove absence. Native carrier_view is recognized, other
integration types and operational status meanings remain unknown. Board-only phone/stops are incomplete;
no creation pilot qualifies. Separate reconciliation report must not refresh Ascend evidence timestamps.

## Active Loads failed attempt lacks diagnostic provenance

owner-active-loads-20260911-01 consumed; no error/stage/view/count was saved and no manifest exists.
The startsWith/startswith bug in view selection is reproducible and fixed, but attributing that exact
production stop to it remains an inference. Actual view, valid-grid presence and row/pickup/delivery
counts are unknown for that attempt. Future failures now include safe reason/code and stage. No live
retry/new attempt this turn. 23 targeted tests and Ruff passed; authority/count gates unchanged.

## Latest: Active Loads is required before POC #002 operations

The old All Loads observation is stale and cannot supply the operational manifest. Active Loads must be
read afresh for 2026-09-11 and reconcile exactly to the owner-attested 8 pickup / 3 delivery events.
Any mismatch, ambiguous view/table, duplicate queue identity, absent pagination proof or changed evidence
hash fails closed before CarrierView, tracking, communication or canonical work. All Loads remains a
separate optional audit source; non-active service-date records never become operations candidates.

## Latest: observed grid contract implemented, pending owner execution

The saved owner-table-schema-001 established the 33-column data/header-clone structure. The ops parser
now excludes zero-row clones, validates observed named headers and exact row widths, and reads Load ID
from each matching row. Prior schema-unknown paragraphs below are historical. Actual queue IDs/counts
remain pending the corrected owner run; 13 matching rows/16 date occurrences alone do not identify queues.
Unknown pagination markup/totals retain VISIBLE_BOARD_ONLY; explicit single-page proof can establish
COMPLETE_CURRENT_BOARD, never system completeness. Details, verified phones/stops/timezones, CarrierView
tracking state and creation readiness remain unknown. The next run intentionally reads the board only.

## Current POC002 blocker: All Loads table schema

Owner-live-ops-001 consumed; runtime stop ops_board_headers_missing_or_ambiguous after authenticated
navigation. Old parser requires guessed exact header text and exactly one recognized table; the exact
DOM mismatch is not yet observed. Do not rerun unchanged. Separate owner-executed table diagnostic
is prepared; header clones, hidden columns, ARIA/cell labels and loaded-date occurrences are observed
without building a manifest. Snapshot mappings remain proposals; ambiguous mappings UNKNOWN.
Read docs/ASCEND_ALL_LOADS_TABLE.md. Earlier unexecuted/session-blocker statements are historical.

## POC #002 current boundary and unresolved operations evidence

Live operations are now priority. Real pickup/delivery queues, pilot identity and payload cannot be
reported before the owner executes login-discover-ops. 1760 delivered and 8/3 counts are owner reports,
not provider observations. The command requires explicit date/board format and covers only the visible
recognized board; unparsed dates, hidden filters/pagination and count mismatches remain review items.
No guessed IDs or forced count matching. Unknown driver phone differs from a verified empty phone.

CarrierView list pagination/negative-existence coverage remains unverified: bounded misses cannot justify
tracking creation. App/route flags and timestamps do not automatically prove live operational semantics.
Unknown timezone/window/stop sequence blocks readiness. Stop-company wire mapping is not in the existing
CreateLocation contract, and creation-triggered SMS/welcome effects are not established; disclose and
resolve before requesting a one-load write approval. No production writes or dispatch are enabled.
352 tests and all lint/JavaScript checks pass; two existing dependency warnings. See POC002 handoff.

## Latest M4B readiness and remaining uncertainty

Same-process networking restrictions are removed by explicit owner instruction: normal app traffic and
service workers are allowed, with no request filters/cookie inspection. Earlier network restrictions
below describe past runs/legacy diagnostics. The networking failure hypothesis has not been live-tested.
The same-process command now proposes a field contract from observed DOM rather than requiring an
existing file. Unrecognized detail identity/labels, non-semantic or ambiguous controls, duplicate values,
unsupported tabs and comparison conflicts stop the relevant action or remain UNKNOWN. Read discovery
does not claim complete Ascend schema coverage or infer missing values. Actual provider DOM remains
unobserved by this implementation until the owner executes the prepared command. No live run occurred.
Full offline suite: 342 passed; lint/JavaScript checks pass; two existing warnings remain. Detail identity
and recognized search/open controls remain fail-closed requirements if the actual DOM is unfamiliar.

## Continuity diagnosis remains unproven — offline implementation only

Login/read share launch implementation/profile/channel/headed/JS/service-worker/extension settings.
The concrete behavioral difference is unrestricted manual-login networking versus GET/HEAD-only,
same-origin validation routing; this can block app resources or startup requests. Fresh-tab startup
also discards restored tabs, making tab-scoped sessionStorage/process-only authentication a plausible
alternative. Do not declare session expiry/storage loss/resource failure proven from the prior tiny DOM.
No safely comparable before/after metadata exists, and the owner forbids new live actions this turn.
New diagnose-continuity can collect aggregate counts after future authorized manual login and one reopen.
login-validate-1752 keeps that exact context alive and does not require cross-process persistence.
Attempt -02 remains reserved. Actual extraction still requires an observed verified live field contract;
none has been promoted from fixtures. No new M4B capability is LIVE_VALIDATED.
332 offline tests and lint/JavaScript checks pass; two prior dependency warnings remain.

## Latest structural diagnostic — session still unproven

2026-09-10 diagnose-session waited 15.011 seconds and inspected all Playwright frames. One same-origin
root frame, no child frames, readyState complete, body children 8, body text length 23; no login form,
expected nav text or authenticated-route anchors. Longer bounded rendering and all-frame/route inspection
did not establish authenticated app DOM. Do not infer expiry, wrong tenant or an asset/network cause;
no network/API traffic was inspected. Booking Logistics remains OWNER_ATTESTED. Root origin unchanged.
Load validation -02 remains unconsumed and prohibited pending resolution. The separate diagnostic uses
only the existing profile and cannot read loads or consume their grants. Its recommendation is not an
automatic change to load-validation policy or the LIVE_VALIDATED matrix.
Full suite: 322 passed; lint/JavaScript checks pass. Two pre-existing dependency warnings remain.

## 2026-09-10 — positive authenticated navigation evidence remains absent

The owner-attested bootstrap removes literal company/user text as a requirement. Its single authorized
attempt observed root path /, title AscendTMS, no login form and zero approved nav markers. Authentication
therefore remains unproven; an absent login form alone is insufficient. No /loads navigation or 1752
read occurred. Origin stays https://ascendtms.com and tenant remains owner-attested Booking Logistics.
Do not request another origin/login, infer session expiry/wrong account, substitute browsers, or retry
automatically. Why the controlled page exposes no navigation is unresolved. Live field DOM contract
also remains unverified; missing/ambiguous exact-load discovery or mappings must stop the next attempt.
The new diagnostic retains no HTML, screenshots, cookie values, notes or customer data. Provider tenant
verification remains unavailable separately from the explicit owner attestation. Earlier entries below
are historical and do not reinstate literal-company gating for this bounded Customer Zero bootstrap.
316 tests and all lint/JavaScript checks pass. Two existing dependency warnings remain.

## Latest M4B identity-only result

Shared local Python executor/profile/msedge channel is confirmed; no alternative browser is used for
validation. Persistent profile storage exists, but the authorized identity-only attempt at the owner
provided https://ascendtms.com did not establish company/user/dashboard identity. Same-origin frame
inspection found no match, and no foreign frame origin was inspected or detected. No load was opened.
Do not infer session expiry, wrong tenant, or root cause from this negative check. See runtime
ascend/identity-only-result.json. Identity CLI now refuses a missing profile and path/query/token URLs.
303 tests pass. Current user instruction forbids Computer Use/cloud/alternate-context substitution.

## M4B current blocker — account identity not established by controlled reader

Owner confirmed login and supplied the official origin and a Booking Logistics dashboard screenshot.
The controlled browser's top-level DOM did not expose the expected company/user indicators. The
live DOM/frame/session contract is unresolved; do not infer a wrong account or expired login.
Stopped before load 1752 discovery/read and set browser offline. No writes or validation promotion.
Sanitized stop evidence is in runtime ascend/phase1-1752-verification-stop.json. Prior pending-login
and never-launched statements below describe earlier checkpoints.

## M4B first live boundary

2026-09-09 update: owner authorized phase-one login/read for exactly 1752. The dedicated window is
open awaiting manual login/MFA. Earlier no-authorization statements below describe the first handoff;
operational writes remain blocked. Initial blank-window startup failed; the helper now opens its
replacement tab before closing startup tabs. Regression/full suite: 291 passed. No identity or load
read has occurred, so the live matrix remains unchanged.

* Offline implementation/tests complete; no real login, navigation, read or write authorized/executed.
  No M4B capability is LIVE_VALIDATED. See docs/ASCEND_ACCESS.md for the exact owner handoff.
* Login origin, independent company/account identity and DOM selectors need authorized observation.
  Fixture selectors cannot establish Ascend compatibility. Owner performs login/MFA manually.
* The dedicated profile has never launched. Real session reuse requires a separate authorized process,
  not a synthetic cookie test or the first successful login.
* Strict same-origin GET/HEAD routing blocks POST, other origins and WebSockets. If needed for reads,
  stop for review; never silently broaden routing. No general Ascend API is verified.
* Content fingerprints/repeated DOM values do not provide provider transaction/version semantics.
  Real mutation screens, create absence/idempotency and document resolution remain unverified; all
  production mutation methods are blocked. UNCERTAIN fixture actions cannot retry.
* Appointments retain raw text/unknown zones; literal differences do not prove timezone discrepancies.
  Live currency/units cannot be inherited from historical USD confirmation.
* Local comparison never fetches vendors. Outlook remains unavailable without explicit shipment
  correlation; only established cached CarrierView stop mappings are reused. Unmapped facts stay unknown.
* The dashboard needs the local server to load updated code; no server restart, new owner-view grant
  or canonical mutation was performed. Demo sessions cannot expose live facts. HTTP never launches
  browsers or approves/executes Ascend mutations.

## M4A committed history — remaining limitations

* Owner approved the mapping, USD and retention limitations. All 694 rows are committed to the
  historical store; identical re-import adds zero records and leaves audit unchanged. Expenses
  remain total expenses, not carrier pay. USD is owner evidence, not invented source metadata.
* 110 exact raw lanes versus the approximate 109 anchor: trim/casefold grouping yields 109.
  Raw city/state labels are not rewritten. All hard financial/count/date/status anchors pass.
* One Completed source row has no Last Drop Date. Do not infer its delivery date or treat source
  Completed as verified operational/billing readiness. One Driver Assigned row is historical export
  evidence only; it must not start active monitoring or scheduling.
* MC: 553 prefixed numeric strings (533 leading-zero portions), 139 prefix-only `MC`, two empty,
  one surrounding-whitespace value. DOT: 692 numeric strings including four whitespace cases,
  two empty. Preserve every raw value; no numeric identifier is invented/coerced.
* Local pickup/delivery date-times lack zones; date-only records have no invented midnight event.
  Exchange Rate Date is populated but has no established financial/event/FX semantics.
* Customer aliases, equipment families/lengths/features and recurring-note topics remain proposals.
  A scoped QuickPay keyword pattern is not an enforceable or owner-approved customer SOP.
* Real commit and post-commit profiles/distributions are validated for this export only.
  Real-source changed-version handling is not validated by synthetic conflict tests.
  Source private notes/driver information remain only in nonsynced raw/staged/committed evidence.
* Two rows lack carrier identity; seven lack equipment. They remain full-sample financial evidence
  and have separate missing-identity contexts, not fictitious named carrier/equipment profiles.
* Facility profiles cover 163 exact first/final endpoint identities, not all intermediate stops or
  verified legal facility entities. Raw address differences can split display-equivalent facilities.
* Customer pattern candidates are bounded keyword evidence, not approved SOPs. Internal historical
  revenue/expenses cannot establish present market rates, carrier pay, billing readiness or quotes.

## M3 remaining boundaries

* Owner confirms successful OAuth, exact mailbox identity, settings read, 5 real messages discovered
  and processed, and exactly 1 unsent draft manually verified in Outlook. Only those six capabilities
  are LIVE_VALIDATED; see LIVE_POC.md. General tenant/shared-mailbox support, classification accuracy
  and operational reliability are not established by this sample. No identifiers or tokens were inspected.
* Attachments were not exercised (0 stored), delta sync was not exercised, and no explicit real
  shipment correlation evidence was supplied. These remain NOT LIVE_VALIDATED. No sending, automatic
  canonical mutation, owner-email commands, webhooks or autonomous communications were exercised.
* Mail.Send remains Entra-configured but excluded from current OAuth requests; send HTTP execution
  remains blocked independently of policy/token scope. No email, Ascend, CarrierView or canonical
  shipment write occurred; the sole reported provider write was one unsent draft. Unknown future
  draft outcomes still require reconciliation; automated retries remain disabled. Do not run further
  Graph requests without explicit authorization.
* Attachment signature/context classification is provisional. No malware scan, OCR, signed-document
  validation, POD verification or billing-gate advancement is provided by M3.
* “ETA 2:30” lacks date, timezone and AM/PM. The extractor retains the literal and ambiguity, not 14:30.
  Most less-common fields rely on a structured injected ModelProvider; no remote model is enabled.
* Verified email sender proof must come from a reviewed identity mechanism. Display name/From alone
  does not authorize commands. Subject continuity alone does not bind a shipment.
* M4A now has a real Ascend export staged as described above. History commit still requires owner
  approval of the actual mapping and financial semantics. Conflicting historical versions remain staged.
  Current history query scans the bounded local store; large-scale indexing/semantic retrieval is future work.
* Runtime mail/document contents are private but not themselves DPAPI-encrypted; only OAuth cache is.
  Retention, ACL review and malware scanning remain deployment work. Existing two Starlette/httpx/anyio
  deprecation warnings persist; all tests pass.
* Dedicated owner cookie now covers `/api` for both live POC and mailbox views. Old browser sessions
  may require a fresh private launcher. Demo bootstrap still cannot authorize mail records.

1. CarrierView LIVE_VALIDATED applies only to its historical capabilities in LIVE_POC.md. The imported record
   is not an active monitoring job. General production modes, external writes and autonomous
   execution remain disabled. Load 1753 has not been read/imported.
2. Position history is partial: 10 of 218 reported records, page 1 of 22. No undocumented
   pagination request was invented. Full GPS replay/order, numeric timestamp units and freshness
   are unverified. Raw numeric timestamps are preserved without inventing UTC conversion.
3. CarrierView app_status=tracking does not establish canonical driver acceptance. Acceptance
   remains unknown. A completed historical load must not be treated as currently in transit
   because of that app field or assigned stale-tracking outreach.
4. Provider documents/POD API is unsupported/unknown. No verified signed RC, POD or billing
   readiness. Missing local document records mean unverified, not proof the documents never exist.
   Canonical DELIVERED is a derived mapping, not a billing/closure assertion.
5. Customer/driver name are not established by the imported facts and remain unknown. Source
   metadata privately preserves provider facts; dashboard excludes driver phones, signed URLs,
   carrier/customer contact records and raw payloads.
6. Real responses differ from provisional fixture schemas: list stops are keyed objects, detail
   stops are an array; last-position uses data.position; history uses data.positions/pagination.
   Historical importer handles observed shapes, but the general typed adapter's older provisional
   models still need alignment before general-purpose production mapping. Do not claim every
   adapter method/schema is live-validated from this POC.
7. Tenant is the owner-selected API service credential. Agent real API execution is blocked after
   two user_not_found responses. This is account-specific observed evidence plus owner direction,
   not independently verified documentation about every employee account.
8. Historical UI approval binds immutable evidence and source timestamps, without applying a
   real-time 15-minute freshness constraint. This exception is specific to owner-approved historical
   replay; it does not authorize treating old evidence as a current live snapshot.
9. Protected display uses separate eight-hour HttpOnly owner sessions created by a one-use
   three-minute private launcher grant. Demo sessions cannot unlock it. It remains local Windows-user
   trust, not remote multi-user production identity. No public ingress or tunnel.
10. Ledger is a single-process foundation: immutable claims, approvals, safe UNCERTAIN handling
    and SMS attempt budget are tested; no production dispatcher, distributed leases, reconciliation
    UI or real side effects. Attempted actions never auto-resend.
11. Webhook normalized schemas/auth are local only; vendor signatures/wire semantics/retry/order
    remain unknown. All inbound events stay quarantined without canonical mutation.
12. Live files stay under C:\FreightDeskRuntime; source remains OneDrive-synced. DPAPI protects
    at rest for this Windows user/machine, not against same-user malicious processes.
    Backup/restore rehearsals, managed secrets and retention remain future.
13. Full BOOK IT execution, other vendors, inference, browser workers and voice remain interfaces/
    incremental foundations. Local demo approval expiry materializes on attempted decision.
14. Audit triggers enforce application append-only behavior, not cryptographic tamper evidence.
    Recent UI metrics use 150 rows. Two upstream TestClient/anyio deprecation warnings remain.
    Full supply-chain, mobile/accessibility and cross-browser audits are pending.
15. Source uses process environment, without .env auto-loading. Start with scripts/start.ps1.
    Reopen protected POC with .tools/python/python.exe scripts/open_live_poc.py.
