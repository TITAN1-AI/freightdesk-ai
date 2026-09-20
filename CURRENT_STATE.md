# Current state — 2026-09-20

## Ascend write note v0.1.4 — atlas #scratch + explicit whole-form Save

Booking Logistics atlas: Private Load Note is `textarea#scratch` (Load Basics,
OBSERVE_OR_FILL); Public Load Note is `#notes`; there is no per-field save — only
whole-form Save / Save & Exit. Bridge **0.1.4** types `#scratch` only. Whole-form
Save requires an approval that sets `allow_whole_form_save: true` (or mint action
`ASCEND_ADD_INTERNAL_NOTE_VIA_SAVE`). Prefer stay-on-load Save; Save & Exit is used
only when that is the unique commit, then the load is re-opened to read `#scratch`.
Without the flag, behavior stays `NOTE_COMMIT_REQUIRES_OWNER_PATH`. Receipts document
`commit_kind=WHOLE_FORM_SAVE` and `whole_form_save_risk`. Status/assign/money/New Load
/public notes stay blocked. Harvest and agent Bearer unchanged. X1 untouched.
**Not LIVE_VALIDATED.** Handoff: [ASCEND_WRITE_NOTE_V0.md](docs/ASCEND_WRITE_NOTE_V0.md).

## Ascend write note v0.1.3 — field-fail opener and owner-path commit

Avery field report on load 1763 (PR #8 / 0.1.2): `403` without approval passed; mint+POST
went `DISPATCHED` then `FAILED` `LOAD_OPENER_UNVERIFIED`; note never appeared; Avery did
not click Save Load. Bridge popup showed harvest `ACTIVE_VIEW_UNVERIFIED`. Live label is
**Private Load Note**; the only commit seen was **Save & Exit to Load Board**.

Portable Bridge **0.1.3** opens a load without a verified Active Loads view (already-open
Private Load Note workspace, unique row View/Details/Open, or unique searchbox fill with
no submit). Whole-form **Save Load** / **Save & Exit** is `NOTE_COMMIT_REQUIRES_OWNER_PATH`
and is not clicked. Receipts add `stage` / `opener_strategy` / `note_label` / `commit_kind`.
Popup Last write is separate from harvest. X1 untouched. Harvest and agent Bearer unchanged.
**Not LIVE_VALIDATED.** Handoff: [ASCEND_WRITE_NOTE_V0.md](docs/ASCEND_WRITE_NOTE_V0.md).

## Ascend write note v0 — private internal note, APPROVAL_REQUIRED

First write on the portable/agent facade: `POST /v1/ascend/loads/{load_id}/notes` after a
one-use demo approval (`POST /v1/ascend/approvals` or the dashboard mint button). Default
ActionPolicy `ASCEND_ADD_INTERNAL_NOTE` is APPROVAL_REQUIRED. Receipts are CANDIDATE with
`PENDING_APPROVAL` | `DISPATCHED` | `VERIFIED` | `FAILED` — no silent success. Verify-after-write
requires note presence. Portable Bridge 0.1.3 can open a load without a verified Active Loads
view and type Private Load Note / Private/Internal Notes only; Save Load, Save & Exit, assign,
status, money, New Load and public notes stay blocked. Harvest and
agent Bearer reads are unchanged. X1 untouched. **Not LIVE_VALIDATED.** Handoff:
[ASCEND_WRITE_NOTE_V0.md](docs/ASCEND_WRITE_NOTE_V0.md).

Verification: 77 focused tests passed (`tests/test_ascend_notes.py`,
`tests/test_portable_bridge_extension.py`, `tests/test_portable_leases.py`,
`tests/test_ascend_facade.py`, `tests/test_agent_sessions.py`, `tests/test_api.py`,
`tests/test_control_plane.py`). New coverage: missing `allow_whole_form_save` stays
`NOTE_COMMIT_REQUIRES_OWNER_PATH`; flagged approval + fixture Save path VERIFIED;
`#scratch` typed and stay-on-load Save clicked; `#notes` never written. Ruff passed
on the changed modules. Node syntax passed on portable-bridge JS and
`portable-notes.js`. Two existing Starlette/AnyIO deprecation warnings remain.
No vendor write and no LIVE_VALIDATED claim.

# Current state — 2026-09-19

## Agent session auth v0 — Bearer for Avery, no popup

Demo-gated agent tokens let Avery call `GET /v1/ascend/status`, `GET /v1/ascend/loads`, and
existing `/v1/portable/leases` routes with `Authorization: Bearer` instead of the Bridge
popup “Demo sign-in”. Mint via `POST /v1/agent/session` or read
`Tokens/demo-agent-token.txt` (optional `FREIGHTDESK_AGENT_TOKEN`). Labeled
`auth_kind=DEMO_AGENT`, not cloud OAuth. Extension harvest path is unchanged: Bridge still
must sit on an authenticated Ascend tab to post harvest; the agent token is API auth only.
Handoff: [AGENT_ASCEND_API_V0.md](docs/AGENT_ASCEND_API_V0.md). X1 untouched. Not
LIVE_VALIDATED beyond the existing portable harvest.

Verification: 36 focused tests passed (`tests/test_agent_sessions.py`,
`tests/test_portable_leases.py`, `tests/test_ascend_facade.py`, `tests/test_api.py`,
`tests/test_portable_bridge_extension.py`). Ruff passed on the changed modules. Two
existing Starlette/AnyIO deprecation warnings remain. No vendor writes and no new
LIVE_VALIDATED claim.

## Portable bridge content attach after Load unpacked

Field test on main `8b0bb4a` passed harvest after a **manual** Ascend tab reload; without that
reload the popup stayed on harvest running, `harvest_count` 0, `extension_last_seen` null. Source
0.1.1 now pings the isolated content script, reinjects the packaged files on install/update and
harvest start, and may reload only exact `https://ascendtms.com/` or `/loads` (no query/fragment)
when install-time inject is not enough. Lease/facade contracts are unchanged. If reinject is
blocked, the popup is action-first: reload Active Loads (F5), then Start harvest. Not
LIVE_VALIDATED.

Verification: 5 portable-bridge extension tests passed (`tests/test_portable_bridge_extension.py`),
including Node syntax checks and an isolated inject/no-reload rehearsal. Ruff passed on the
changed Python test. Lease/facade contracts were not modified. No LIVE_VALIDATED claim.

## Ascend facade v0 — portable harvest reads for Avery/product

Closed-loop slice on the portable-bridge track: `GET /v1/ascend/loads` and `GET /v1/ascend/status`
normalize the latest stored `POST /v1/portable/harvest` snapshot. Empty harvest is `loads: []`
plus `harvest_available: false` (HTTP 200). Revoked leases keep last CANDIDATE evidence and reject
new posts. This is a **facade over UI harvest**, not an Ascend retail API and not LIVE_VALIDATED.
Handoff: [ASCEND_FACADE_V0.md](docs/ASCEND_FACADE_V0.md). Demo dashboard shows last harvest
count/timestamp on the existing Ascend panel. X1 native host is unchanged.

Verification: 5 facade tests plus prior portable/API checks passed (20 combined in the focused
rerun). Dashboard `portable-facade.js` and existing ascend-view rendering checks passed. No
LIVE_VALIDATED claim.

# Current state — 2026-09-15

## Portable browser bridge v0 — implemented offline (Track B)

Product-foundation slice: [portable handoff](docs/PORTABLE_BRIDGE.md),
[north star](docs/PORTABLE_BRIDGE_PRODUCT.md), unpacked extension
[extensions/portable-bridge/](extensions/portable-bridge/). Demo lease stub is
`/v1/portable/session|leases|harvest|status` on the existing `run.py` / `scripts/start.ps1`
demo server. Harvest is VISIBLE_BOARD_ONLY, CANDIDATE, `live_validated=false`,
`production_writes=false`. No native messaging, no X1/host changes, no store submission,
no cloud OAuth, and no LIVE_VALIDATED Ascend claim. Booking Logistics live ops remain
on the separate Avery stack.

Verification: 10 focused portable tests passed (`tests/test_portable_leases.py`,
`tests/test_portable_bridge_extension.py`); existing `tests/test_api.py` (7) still passed;
X1 manifest restriction test still passed; `node --check` on packaged JS passed; Ruff passed
on the new modules. Full-suite `scripts/test.ps1` results stay in the audit-repair section
below until a complete Windows run is recorded. Two existing Starlette/AnyIO deprecation
warnings remain. No vendor capability is newly LIVE_VALIDATED.

# Current state — 2026-09-13


## GitHub collaboration - 2026-09-13

Repository: https://github.com/TITAN1-AI/freightdesk-ai. Initially created private; the owner changed
it to PUBLIC on 2026-09-13, and GitHub visibility was verified. Runtime and secrets remain excluded.
CONTRIBUTING.md, task/PR templates and the Windows Offline checks workflow define the coding handoff.
Main is the integration branch; use scoped codex/<task> branches for changes. Full history preserves
6d4a781 and f2377b2. GitHub login stays in the Windows credential store; configuration is under the
nonsynced runtime. No collaborators are invited implicitly, and no provider authority is granted.
Local source/lint checks pass; the first hosted CI run is tracked separately from prior local tests.

## X1 / WebBridge V2 audit fixes — implemented offline

Owner authorized the A01–A10 repairs. See [the repair handoff](docs/WEBBRIDGE_V2_AUDIT_FIXES.md)
for findings, evidence, capacity limits and release boundaries. Coherent map/graph acquisition,
private-source exclusion, document-lifetime node IDs, compact wire, strict graph coherence,
field/domain checks and bounded indexed history are implemented. The actual synthetic chain and
an independent runtime-commit/process-exit/coordinator-restart path are covered by regressions.

V1 remains default. Compatibility v3 / graph v2 / wire v1 remain fixture/TestRuns-only and OBSERVE-only.
No installed-state or vendor action, new live authority, operational value extraction or capability
promotion occurred. Audited baseline is local commit 6d4a781; source hashes and source-only rollback
rehearsal are generated under TestRuns. No live V2 packaging command exists.

Verification: scripts/test.ps1 passed 960 tests (375.61s), full Ruff and synthetic dashboard checks.
Final audit/release rerun: 18 passed; final integrated rerun: 7 passed (including the additional
19-field full chain); final release rerun: 4 passed. These runs overlap: 965 distinct tests are covered
by the full suite plus five newly added cases. Node syntax checks passed. Two existing Starlette/AnyIO
deprecation warnings remain. No vendor capability is newly LIVE_VALIDATED.

## Historical 2026-09-12 acceptance — superseded by audit and repair handoff

# Current state — 2026-09-12

## WebBridge V2 Phases 0–2 — accepted OFFLINE

After the revised-brief review, owner authorized completion. See
[the acceptance handoff](docs/WEBBRIDGE_V2_PHASES_0_2_ACCEPTANCE.md).
Typed graph/evidence/visibility/reference contracts, bounded projector, generic section relationships,
versioned V1 compatibility and real runtime-owned map/graph/completion persistence are implemented.
Actual synthetic orchestrator → access → native codec → worker → router → content → DOM → persistence
passes, including both V1 section shapes, observer continuity, focus, variation, unrelated-authority
completion, review/revoke/cleanup, idempotence/conflicting digest, rollback and notification recovery.
V1 remains the ordinary live default. V2 is TestRuns-only, absent from the live manifest, OBSERVE-only
and cannot inherit AUTO_MAP approvals.

Verification: 428 relevant X1/WebBridge tests passed in 133.36s; seven additional boundary tests and
one additional integrated graph-bound case passed (436 distinct tests). A final 36-test diagnostic/
coordinator run overlaps the broader/boundary sets. The earlier 73 focused tests also overlap.
Changed Python Ruff and
all three V2 Node syntax checks passed. Two existing Starlette/AnyIO deprecation warnings remain.
Synthetic baseline: 14 visited/13 emitted, 17 edges, 14 geometry reads, frontier 2, 10,433 graph bytes,
approximately 0.4ms graph capture only. No end-to-end performance or Ascend validation claim.

Pinned Playwright adaptations and Apache LICENSE/NOTICE are recorded in
third_party/webbridge-v2-implementation.json. The separate referenced implementation-plan document
was not supplied/found and is not claimed reviewed. No live execution, operational values or reopened
grant. The five-iteration live authorization remains closed.

## Historical starting point — superseded by offline acceptance above

Owner said "proceed" after the source-audit handoff. An isolated V2 core, strict graph contracts,
TestRuns-only atomic-store utility and synthetic tests are drafted. They are not registered in X1
or used by ordinary live jobs. Focused tests: 61 passed, two existing dependency warnings. A
mutable proof-baseline bug found by those tests was corrected. No vendor execution occurred.

Owner then requested comparison with the revised Phases 0–2 brief. See
[the review](docs/WEBBRIDGE_V2_PHASES_0_2_REVIEW.md): real pipeline compatibility, owning-runtime-store
integration, fuller typed evidence/visibility, source-incorporation records and integrated acceptance
remain unfinished. Graph-only MAP_PERSISTED is not yet a complete provider-map result. Do not claim
Phases 0–2 complete or V2 LIVE_VALIDATED. The closed live-debugging authorization stays closed.

## Browser Intelligence / WebBridge V2 source audit — research complete, implementation proposed

Source-level review covers the seven requested frameworks plus rrweb, axe-core, Healenium and
Finder, with pinned revisions and module-level algorithm/license analysis. Deliverables start at
[BROWSER_INTELLIGENCE_CODE_HARVEST.md](docs/BROWSER_INTELLIGENCE_CODE_HARVEST.md): capability matrix,
top-ten harvests, current-component disposition, architecture, page schemas, roadmap and proposed
third-party provenance. X1 stays the sole authenticated sensor/executor; V2 uses one shared
document graph with control/schema views and retains identity/policy/evidence acceptance.

This milestone is research/design only. No production implementation, dependencies, provider
execution, extension reload, leases, selector changes or operational state changes occurred.
V2 is not LIVE_VALIDATED. Implementation requires owner approval; the completed exact X1 live
capture and closed five-iteration authorization below remain unchanged. Research artifact checks
are distinct from the historical production-code test results recorded below.

Research checks passed: nine Markdown deliverables, all 14 requested canonical model types,
70 local links, 153 pinned source-link occurrences and the 24-entry proposed YAML registry.
Source paths/ranges and the Healenium artifact hash were checked against downloaded source;
these checks do not constitute production tests, legal clearance or vendor validation.

## X1 exact Load 1763 / Load Basics capture succeeded — live loop closed

The fifth/final authorized iteration passed all three phases: fresh session/readiness →
dispatch/ACK with matching bindings, provider LOAD/1763 identity, and exactly one persisted
Load Basics metadata map. The map contains 19 candidate field proposals, CANDIDATE_ONLY,
values_included=false and production_writes=false. It is current-visible-section coverage only.
Actual extension/worker/content 0.6.2, controller/content protocol 3, native protocol 1,
trace revision 1 and workspace reader revision 2 were proved by signed receipts/handshake.

Capture measured 188 ms; final map receipt is 2026-09-12 16:40:33.931617 UTC. Job-owned authority
was revoked at 16:40:33.946733; cleanup COMPLETE, no post-revoke read receipt. Final UI stage is
OWNER_REVIEW_REQUIRED for a separate navigation milestone, with no active authority. Do not
approve navigation or start another live iteration from this completed authorization.

The section parser had required a semantic target/root that the live plain-container layout
did not expose. Bounded selected-current-route + matching heading + unique later sibling form
region now proves the observed section, excluding navigation/identity from capture. Exact
identity, presence, session, write and field-count gates remain. A separate causal ACK body-binding
defect and browser-chrome focus issue were fixed without resetting enrollment or relaxing proof.

The earlier DOCUMENT_CHANGED after a fresh mapping-lease session did not recur. Its exact
historical router branch remains UNKNOWN; it must not be described as failed authentication.
Precise underlying error reporting and opt-in causal tracing now preserve future evidence.

Final frozen relevant verification: 411 tests passed, scoped Ruff/Node passed, two existing
dependency deprecation warnings. Narrow A/B/C evidence is live validated; field semantics,
general Mapping Mode across loads and AUTO_MAP remain unvalidated. See
[ASCEND_X1_SESSION_CAUSAL_DEBUG.md](docs/ASCEND_X1_SESSION_CAUSAL_DEBUG.md) and LIVE_POC.md.
All earlier offline-only and retry notes below describe their historical milestones.

## X1 0.6.2 Mapping Reliability Fix Pack — implemented offline

The authoritative workflow-review findings are addressed in
[ASCEND_X1_MAPPING_RELIABILITY.md](docs/ASCEND_X1_MAPPING_RELIABILITY.md). Precise section diagnostics,
observer continuity, owner-readiness waiting, read-job dependency recovery, cross-load variation,
signed immediate wake hints and safe normal status/failure receipts are implemented. The integrated
offline chain joins actual coordinator/host/worker/router/content/reader/persistence boundaries.
It also exposed and fixed whole-number timestamp MAC serialization across Python/JavaScript.
Combined relevant verification: 361 tests passed, with two existing dependency deprecation warnings.
Final authority-race corrections added five regressions; 128 affected tests and the integrated path
passed afterward. Grant, queue and cleanup transactions preserve unrelated read authority.
Final direct-failure wake and expired-review persistence corrections passed 39 coordinator/API/
integrated tests. Follow-up counts overlap the combined suite; no failures remain in these checks.

No live provider execution or capability promotion occurred. Real Ascend section relationships
remain UNKNOWN. Owner reloads existing X1 0.6.2 and uses the single documented 1763/Load Basics
command when ready; no re-pair, separate lease enable, manual attempt ID or automatic live run.
For that CLI-only validation, finish existing jobs and stop any dashboard server still running old
Python code; the new CLI and reconnected native host coordinate the job without that stale process.
All operational writes and unverified navigation remain blocked. Earlier review findings below
describe the pre-fix state and preserved live evidence.

## 2026-09-12: workflow review; newer live stop found in local audit

Read [ASCEND_WORKFLOW_REVIEW.md](docs/ASCEND_WORKFLOW_REVIEW.md) before another retry.
Latest existing owner-run job, 13:55:37–13:55:40 UTC, was dispatched and acknowledged,
then reached WORKSPACE_IDENTITY_VERIFIED (one workspace, one identity signal, 12 distinct
recognized section controls). It stopped WORKSPACE_SECTION_UNVERIFIED; zero maps/cycles,
cleanup complete, no production writes. Exact failing code predicate is unique section
candidate count != 1; its measured count/relationship was not persisted. This is newer than
the owner-presence/expiry job described below. No new execution or capability promotion here.

Offline review reproduced three separate later-stage bugs: session refresh destroys the passive
mapping observer; READ_JOB_ACTIVE wait does not recover after the other lease ends; cross-load
optional fields cause fatal structural drift. Normal reporting also hides safe stage/error details.
Review diagnostics and documentation only were added; production fixes remain outstanding.
Recommend correcting these paths and exercising their integration before another owner live attempt.

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


## 2026-09-11: X1 0.5.0 OBSERVE + AUTO_MAP workspace architecture (offline)

Read docs/ASCEND_X1_MAPPING_MODE.md. OBSERVE learns unknown provider structure and drift through
owner-visited sections. AUTO_MAP traverses VERIFIED READ_ONLY_NAVIGATION controls within one exact
provider-proved LOAD workspace, rechecking session/lease/identity/control before each transition,
verifying the expected section afterward, and returning through a verified starting-section control.
No repeated manual tab visits are required once navigation is verified. No arbitrary selector/script,
write control, other-load opener or crawler is accepted. Known same-document role=tab controls only;
unobserved navigation/operational fields remain UNKNOWN. Tenant identity remains OWNER_ATTESTED.
The 3-5 load cohort is only controlled AUTO_MAP validation, with OBSERVE preparation for unknown UI.
Normal owner-present modes need no mandatory ID list; optional tighter scope remains. Normal AUTO_MAP
requires reviewed navigation and owner-confirmed successful cohort return cycles; OBSERVE evidence
alone cannot unlock it. Time/workspace/section/field/read-attempt bounds remain. Metadata contracts are
append-only candidates; controlled navigation approval does not activate field reads or writes.
Source0.5.0 preserves existing enrollment/transport/permissions, Active Loads and VISIBLE_BOARD_ONLY.
No live execution, lease mutation, registry change or new LIVE_VALIDATED promotion. Old proposed panel
-detail -03 is superseded. The handoff includes exact future owner commands and validation limits.
220 targeted offline cases passed; final affected reruns passed (latest: 32 cases). Ruff and package
JavaScript syntax passed; the two existing dependency deprecations remain.
The 5-10-second complete context target remains unproven; operational reads/context latency need
separate validation after the navigation cohort. Current context interface preserves unknown facts.

## 2026-09-11: source X1 0.4.3 causal detail-container correction (offline)

Owner detail attempt owner-x1-detail-20260911-02 is consumed. Local receipts show a fresh eight-row
board and successful exact1755 FIND, then ASCEND_OPEN_LOAD_READONLY / DETAIL_BOUND_CONTAINERS at
23:22:35 UTC. No field-mapping dispatch or contract. Old maximum12; measured count/category were
not persisted. Approximately35ms execution versus100ms minimum post-click wait strongly suggests
pre-click snapshot failure, but click timing was not recorded. Do not diagnose the healthy enrollment,
Native Messaging, scheduler, binding, session, view or board schema again.

0.4.3 removes unrelated snapshot containers from causal budgets and adds ranked provider relationships:
direct target A, new root B, newly-visible C, connected selection change D. Category bounds4/8/8/4,
unchanged identity64, opener-attributes24. Tied strongest roots stop; provider identity still precedes
all field mapping. Typed safe counts/stages/rank/bound diagnostics persist in attempt-linked receipts,
audit/status and reports. Prior missing counts remain unknown. Build reload required; no transport,
permission or board-schema change. Proposed unused -03 is preparation only, not queued or consumed.
No live execution or lease mutation occurred. See docs/ASCEND_X1_CAUSAL_CONTAINERS.md for evidence,
limits and exact owner commands. Contracts remain CANDIDATE_ONLY; detail mappings not LIVE_VALIDATED.
153 targeted offline tests passed; existing dependency deprecation warnings remain.

## 2026-09-11: source X1 0.4.2 board-schema correction (offline)

Owner-reported 0.4.1 lifecycle recovery is corroborated by local handshake/session/Active Loads
view receipts. The next board read failed BOARD_SCHEMA_INVALID at 22:29:36 UTC. Only view proof
was persisted; exact predicate, headers, row widths and live clone/alignment state are UNKNOWN.
Do not claim a fixture reconstructs the live failure. The old selector reproducibly lets an empty
header clone compete with a data-bearing grid; fixed positional/case-sensitive matching also differed
from the historical schema normalization. 0.4.2 fixes selection and semantic mapping while retaining
all 31 named headers, 33-column alignment, span/ambiguity guards and a bounded stabilization wait.
Typed structural diagnostics and safe schema_predicate now flow to receipts/audit/status/CLI/UI.

Read-only review at 22:33:23 UTC found owner revoke at 22:31:43 UTC. No successful board read in
that lease; last_board_sync 22:04:35 and retained count/hash are LAST_KNOWN_BOARD_EVIDENCE only.
Future owner retry requires extension reload to 0.4.2 and a fresh short board-only lease. No re-pair,
tab refresh or detail attempt. No live execution or lease change occurred here. See
docs/ASCEND_X1_BOARD_SCHEMA.md for the evidence table, safeguards and exact owner commands.
0.4.2 is not live validated; historical board-runtime scope, VISIBLE_BOARD_ONLY and UNKNOWN detail
mappings remain unchanged. The older retry instructions below are superseded for this failure.
254 targeted cases have passing results after correcting a stale pre-0.4.1 permission assertion;
the final affected 22-test rerun passed. Ruff/JS passed; existing dependency warnings remain.

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


## 2026-09-11: X1 persistent read-only Ascend board runtime LIVE_VALIDATED

Owner production observations are corroborated by read-only inspection of runtime.sqlite3 under
C:\FreightDeskRuntime\Data\booking-logistics\ascend-native (runtime_leases, runtime_events,
runtime_receipts, runtime_proposals and runtime_state). No live execution or runtime mutation was
performed during this evidence review. This update supersedes earlier preparation-only/retry status.

The owner-enabled lease began 2026-09-11 20:42:17 UTC, with 60-second configured cadence and
15-minute maximum duration. Three successful ASCEND_GET_ACTIVE_LOADS receipts occurred:

| Cycle | UTC observation | Visible rows | Proposal result |
| --- | --- | --- | --- |
| 1 | 20:42:28.187586 | 11 | BOARD_REFRESHED; exactly one UNAPPLIED proposal |
| 2 | 20:43:47.930661 | 11 | BOARD_UNCHANGED; NO-OP |
| 3 | 20:44:48.186533 | 11 | BOARD_UNCHANGED; NO-OP |

All three semantic hashes match and independently recompute from the stored ID/pick-date/drop-date
rows. Exactly one proposal exists for this lease, matching that hash, with canonical_mutation=false.
The first observation is new evidence, not proof that provider data changed during the lease.
No duplicate proposals were created. Actual intervals were approximately 79.74 and 60.26 seconds;
the configured cadence is not an exact delivery-time guarantee.

Six successful authenticated-session receipts and three independent provider-DOM ACTIVE_LOADS /
VERIFIED view receipts precede the three board reads. Board routes consistently show one eligible
tab at https://ascendtms.com/loads. All six board/view payloads pass the current typed contracts and
require_active gate on offline inspection. Tenant identity remains OWNER_ATTESTED Booking Logistics;
it is not provider-derived account verification. Durable enrollment/reconnect is supported by the
owner's previously reported restart validation, not a newly simulated restart in this review.

Owner revoke is recorded at 20:45:08.915408 UTC. The matching lease generation is revoked;
state=STOPPED, error_code=READ_LEASE_REVOKED, bound_tab=UNBOUND, no pending dispatch. There are zero
board dispatches and zero board receipts after revoke in the inspected ledger. Scheduler wake and
native heartbeat observations continue through at least 20:54:29 UTC without another board read.
The prior hash, 11-row count and 20:44:48 last-board-sync evidence remain retained. Owner confirms
pairing remained VALID and extension/native host CONNECTED after disable. This supports observed
revocation enforcement; it does not claim every possible in-flight race has been live exercised.

LIVE_VALIDATED: **X1 persistent read-only Ascend board runtime**, scoped to owner-enrolled connection,
one-tab automatic binding, authenticated session, independent Active Loads view proof, recurring
visible-board reads, one initial UNAPPLIED proposal, unchanged-hash no-op and the observed revoke
boundary. All inspected cycle/audit records report production_writes=false. No canonical mutation.

Remaining limitations: VISIBLE_BOARD_ONLY; no whole-account completeness or pagination claim.
Operational detail field mappings remain UNKNOWN / NOT LIVE_VALIDATED. Board hash covers only
load ID/pick/drop dates; it cannot establish unchanged assignments, rates or other detail fields.
No live validation of naturally changed-board refresh, long-duration reliability, exact-minute
scheduling, stale-script recovery, multiple-tab recovery or arbitrary restart scenarios follows
from these three cycles. No Ascend writes, communications, CarrierView/Outlook execution or automatic
canonical application is authorized. Read access remains revoked; do not enable or retry automatically.

Next recommended milestone: prepare an offline, bounded operational-detail field-contract plan
with explicit provenance/identity checks and UNKNOWN handling, for later separate owner approval.
No detail read is authorized by this promotion. No code changed; evidence reconciliation and typed
contract checks were performed locally, without another vendor read.


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


## 2026-09-11: X1 0.3.0 persistent read-only runtime prepared; no live enrollment/lease

Owner requests replacement of repeated pairing/grant/button work with one enrollment and a separately
enabled read lease. Implemented durable DPAPI enrollment, exact pinned native origin/device/installation
binding, automatic connection renewal, opaque-handle-only Edge persistence, safe authenticated-tab
routing and typed Active Loads navigation. Host-owned default five-minute board loop under an eight-hour
owner lease creates provenance-backed UNAPPLIED proposals only when the ID/pick/drop-date hash changes.
Lease/policy/pause/expiry/revoke/replay/session/view/identity gates remain independent; writes unavailable.

Protected local dashboard adds connection/session/lease/view/hash/count states and explicit Enable,
Disable, Pause/Resume, Rebind and Re-pair recovery. Demo login cannot authorize reads. Migration appends
new enrollment/runtime history without deleting consumed one-shot records. -02 is not the normal
operating model. Owner must enroll once and explicitly enable the first real lease; none created here.

Actual operational detail field contracts remain UNKNOWN; typed detail operations preserve empty
unknown results after provider identity verification. No assignment/stops/appointments LIVE_VALIDATED
claim. Visible-board-only coverage and ID/date-only change detection are explicit limits. Existing
transport/session observations remain scoped; all persistent behavior has offline evidence only.
See [architecture, migration, manual steps and first live plan](docs/ASCEND_X1_RUNTIME.md).

Final validation: 232 targeted tests passed, plus Ruff/JavaScript/Node checks and desktop/mobile
synthetic dashboard QA. Native self-test construction regressions were repaired without weakening
pinning or opening credentials in the self-test path. Two existing dependency warnings remain.

## 2026-09-11: X1 first read stopped at view identity; 0.2.1 prepared offline

Read-only local audit confirms consumed owner-x1-identity-1755-20260911-01: session succeeded on one
eligible /loads tab, then ASCEND_GET_ACTIVE_LOADS stopped ACTIVE_VIEW_UNVERIFIED before grid extraction.
No FIND/OPEN or production write. The old detector omitted parent li.active / aria-current=true;
its exact live missing signal and actual view are UNKNOWN because no candidate metadata was retained.

Source 0.2.1 adds AscendLoadBoardViewContract with independent DOM selection/title/panel/data proof,
strict host re-resolution, sanitized failure receipts and in-command view-change stops. Path, IDs
and 8/3 counts cannot prove Active Loads. No transport/permissions/pairing changes or live execution.
117 targeted tests pass; fixtures are not LIVE_VALIDATED provider compatibility.

The consumed stop invalidated the selected-tab binding. Last verified pairing is beyond its ten-minute
lifetime at the 17:47 UTC audit check; no currently usable pairing is claimed. No re-pair, new grant or
bootstrap here. Proposed unused -02 has a prepared owner-only successor CLI; old consumption remains
immutable and no third attempt is enabled. Future Reload/renewal/reselection/read release requires
separate owner authorization. STOP before live steps. See [current handoff](docs/ASCEND_X1_VIEW_CONTRACT.md).
This section supersedes older first-test-pending/grant-unused instructions below. Tenant remains
OWNER_ATTESTED; no Active Loads/detail/operational capability is promoted.

## 2026-09-11: local pairing transport validated by owner; X1 identity controller prepared

Owner reports installed X1 0.1.2 reached PAIRED / PAIRING_SUCCESS with reads/writes disabled.
ONLY Edge extension ↔ Native Messaging ↔ local FreightDesk host transport is newly LIVE_VALIDATED,
provenance OWNER_REPORTED. This supersedes the pending-pairing/startup status below, without inventing
installed binary details. Existing scoped Ascend/CarrierView/Microsoft/history evidence is unchanged.

X1 source 0.2.0 implements explicit eligible-tab routing and a separate host-authorized four-command
session → Active Loads → exact 1755 row → identity-only opener sequence. One local owner release,
strict one-use order, policy/pause gates, document/board binding and signed dispatch/results; unknown
commands, selectors, URLs, JS, operational reads and writes remain blocked. Board dates use the shared
existing parser before comparison with the case's exact 8/3 oracle. Tenant remains OWNER_ATTESTED.
Successful identity ends IDENTITY_VERIFIED_READS_BLOCKED with no operational extraction or vendor
capability promotion. See [owner steps and receipt contracts](docs/ASCEND_X1_READONLY.md).

No live extension read, installed-host execution, registry change, actual bootstrap or grant was
performed here. The proposed owner-x1-identity-1755-20260911-01 has not been created/consumed here.
Reload/fresh pairing and local owner preparation are required before manual four-step execution.
125 targeted native/controller/tab/identity/board tests passed, along with Ruff and JavaScript
syntax/bootstrap/popup checks. Two existing dependency deprecation warnings remain;
fixture DOM tests use isolated TestRuns profiles and intercepted synthetic pages, never the live profile.

## 2026-09-11: native relay defect reproduced; owner rebuild/self-test pending

Read-only local inspection confirms both HKCU Edge registry views point to the expected valid manifest,
exact owner-provided allowed origin and existing executable. Runtime launcher source matches the old
template; paths/Python are valid, required imports produce no stdout/stderr/warnings. Actual audit
reaches DPAPI and ONE_TIME_VALIDATION, not proof; consumed-pairing count zero. Host did start/read HELLO.
Old CopyTo relay fails an interactive small-frame fixture with stdin open; explicit per-write flush
passes. Source corrected, installed binary untouched. New early C#/Python startup diagnostics and
owner-run synthetic ping self-test preserve exact origin/DPAPI/read-write blocks; no new transport.
46 targeted native-host tests, Ruff and PowerShell syntax pass. No installed-host execution, registry
change, bootstrap or pairing retry. See docs/ASCEND_NATIVE_STARTUP.md: RebuildLauncher then owner self-test,
STOP before pairing. Extension Reload/re-registration not required. Actual Edge transfer remains to be
verified after rebuild; no new live validation claim or grant.

## 2026-09-11: X1 0.1.2 pairing import diagnostics

Owner reports 0.1.1 installed, exact ID captured/pinned, successful native registration and host
reachability (PAIRING_REQUIRED). Bootstrap import did not reach PAIRED. Old errors were swallowed/
collapsed, local popup errors could be overwritten by status polling, and synchronous connect errors
could be lost behind the async epoch guard. The original real failure's specific gate remains unknown.
0.1.2 instruments local file/schema/expiry/ID, native/DPAPI/one-use/proof/persistence/ack stages with fixed
safe codes. Adds persistent packaged panel and explicit Import button, input reset, six-field append-only
pairing_attempts audit under existing runtime bridge.sqlite3. NULL flags mean unmeasured, not false.
PAIRED requires a verified bound host acknowledgement; READ_ONLY_READY remains unavailable.
53 targeted tests pass; Node/JS/Ruff checks pass, two dependency warnings. Browser/crypto fixture exclusions
are deliberate. No private runtime inspection, actual bootstrap generation, registry or vendor execution.
Owner retry/reload to 0.1.2 and one fresh Pair are documented in docs/ASCEND_NATIVE_MESSAGING.md.

## 2026-09-11: X1 native pairing/registration foundation - offline only

Owner reports Edge unpacked 0.1.0 installed/enabled with no manifest errors. Source 0.1.1 now adds
manual popup native pairing and lifecycle states, exact locally captured extension-ID manifest,
bounded stdio Python host, fixed Windows launcher and owner-run registration/reset/uninstall helpers.
Pairing binds Windows user/runtime installation, tenant booking-logistics, actor FreightDesk/Avery
and protocol 1; DPAPI at rest, one-use ten-minute bootstrap, memory-only browser key, authenticated
messages, durable duplicates and append-only safe audit. No TCP or arbitrary JS/selector/write path.
See docs/ASCEND_NATIVE_MESSAGING.md for exact local capture, registration, pairing and recovery steps.

No actual ID capture, registry change, real pairing, extension reload, browser/vendor execution or
new grant occurred here. Production read dispatch remains independently blocked at host/worker/content/
executor; valid read commands return read_release_required. PAIRED is not READ_ONLY_READY. Production
tab/controller routing, stabilization and an identity-only OPEN receipt remain required before the
separately authorized 8-pickup/3-delivery -> exact 1755 -> provider identity -> STOP test.
No new LIVE_VALIDATED capability. Playwright detail-identity experiments remain permanently CLOSED.
Offline checks cover host/worker lifecycle, protocol interoperability, SID/DPAPI fixture primitives,
PowerShell syntax and Windows launcher compilation (executable not run). Final targeted suite: 45 passed,
one existing browser fixture intentionally excluded. Node lifecycle/isolation and scoped Ruff passed.
Two dependency warnings remain.

## Ascend executor pivot — X1 offline extension prototype

Final Playwright identity attempt consumed and failed: board_tables 9 > 8, pivot_required=true.
No new attempt/reset/bound increase. Detail identity experiments CLOSED; entry point disabled.
Prefer the extension as interactive executor candidate; keep proven Playwright board behavior.
X1 MV3 unpacked skeleton restricts host to ascendtms.com, typed reads only, production bootstrap/native
connection disabled. Added policy/tenant/actor/version gates, safe result projection, evidence audit
hooks and native framing/paired-message authentication components. The subsequent native foundation
above supersedes the original missing-pairing status. No actual host registration/production connection.
Actual detail binding and stop/assignment semantics remain unverified.
See docs/ASCEND_EXECUTOR_PIVOT.md for assessment, installation and separately authorized live plan.
Validation: 19 scoped regression tests; final extension suite 14 passed, plus unchanged-panel regression.
Bootstrap isolation, JS syntax and Ruff passed; two existing dependency warnings. No new live evidence.

## Final targeted identity attempt prepared — owner execution only

Owner authorized preparation of owner-ascend-final-identity-1755-20260911-01, verified unused locally.
No live execution or runtime grant creation during preparation. CLI requires this exact --attempt-id
and --owner-authorized. A separate final_causal_grant permits exactly one final run; prior consumed
causal grants remain intact. Any failure after final grant consumption mandates pivot, no additional
Playwright identity attempts. No operational extraction, other vendor calls or writes. See
 docs/ASCEND_TARGETED_IDENTITY.md for the command. Earlier disabled/unprepared statements are historical.

## Latest: causal bound failure; targeted refactor, live execution disabled

Causal attempt -01 consumed; board reconciled, then generic causal_scan_bound before opener metadata.
Exact bound/count were not saved and cannot be reconstructed. Locator resolution preceded the failure;
full row-binding evidence and safe opener metadata were not persisted. Broad candidate/descendant scans
are replaced by exact row/header selection, opener-first persistence and narrowed container identity scans.
Each bound now saves category/measured/maximum/phase. No new attempt ID or command; CLI stops before
runtime/browser access. One future unsuccessful owner-authorized final test mandates pivot, no repeated
Playwright experiments. See docs/ASCEND_TARGETED_IDENTITY.md. Existing identity/write gates unchanged.
Five targeted tests passed, including 17 browser scenarios and four exact bound cases; final two-test
pivot/disabled-entry rerun passed. Ruff/help passed; two existing dependency warnings remain.

## 1755 causal identity diagnostic prepared — offline only

Owner-executed identity attempt -01 is consumed: exact scope reconciled, zero identity candidates,
detail_identity_missing, no contract. Same-page panel is an unproven hypothesis; the ledger includes
/loads and redacted-path observations. New owner-ascend-causal-identity-1755-20260911-01 captures sanitized
opener structure and before/after container changes. Requires explicit detail identity or a provider
DOM opener/selection-to-panel binding; click alone fails. Existing normalization and operational identity
gates unchanged. No operational extraction or live run. See docs/ASCEND_CAUSAL_IDENTITY.md.
Validation: 25 targeted tests passed; final three-test causal rerun includes 16 browser scenarios.
Ruff/help passed; two existing dependency warnings. New attempt/database remains unused.

## 1755 identity-only diagnostic prepared (offline)

Saved diagnostic 02 proves normalization and exact Active Loads 12 rows / 8 pickups / 3 deliveries,
then fails detail_load_identity_unverified for 1755 at detail_identity_verification, zero completed loads.
Current blocker is detail identity only. Prepared owner-ascend-detail-identity-1755-20260911-01 reuses
unchanged normalization then opens only 1755. New bounded identity-only observer covers labeled/hidden
inputs, headings/tabs/panels/breadcrumbs, identity attributes and exact-row-linked route. Metadata and
approved IDs only, query/private values redacted. Conflicts/missing/ambiguity stop; no operational detail
extraction or automatic reader-contract activation. See docs/ASCEND_DETAIL_IDENTITY.md. No live execution.
Targeted checks passed: 21 identity/field-discovery tests, final 11-test identity rerun and one additional
stability timeout regression; Ruff and CLI help passed. Existing two dependency warnings remain.

## Active Loads normalization prepared — diagnostic 02, offline only

Saved diagnostic 01 failed BOARD_READ at 1 row / 1 pickup / 0 deliveries, zero detail reads. Scope
mismatch is proven; the specific retained filter/page/render cause was not captured. No detail fix guessed.
Diagnostic 02 now observes selected Active Loads + validated data grid, safely clears recognized table
search, normalizes observed page size/first page, settles rendering and verifies exact 11 IDs with 8/3.
Unknown active filters fail closed with metadata. Semantic board hashes exclude harmless presentation
state; actual row-state changes are detected. New attempt owner-multi-system-ascend-diagnostic-20260911-02
is unused; earlier grants untouched. No live execution. See docs/ASCEND_BOARD_NORMALIZATION.md.
Verification: 24 targeted tests and Ruff passed; two existing dependency warnings. No full-suite rerun.

## Separate Ascend-only diagnostic prepared — no live execution

owner-multi-system-ascend-diagnostic-20260911-01 has an owner-executed command and isolated
ascend/diagnostics.sqlite3 namespace. It refreshes exact 8/3 Active Loads, reads at most 11 details in
numeric order, durably checkpoints each identity/extraction/count, and verifies ending board hash/counts.
Only safe metadata is persisted; no operational facts or other system phases. First failure stops and
preserves its root code/stage/affected ID/count over cleanup errors. Original multi-system consumed and
unused phases remain unchanged. 30 targeted tests/Ruff/help pass. See docs/ASCEND_MULTI_SYSTEM_DIAGNOSTIC.md.

## 2026-09-11 — multi-system Ascend stop diagnosed locally

owner-multi-system-20260911-01 has only its Ascend phase grant consumed. No whole-run consumption
record exists; CarrierView/Outlook grants and report/evidence records are absent. No multi_ascend data,
per-load stage records, failure artifact or run-linked audit was persisted by the old implementation.
Root cause, affected load, completed in-memory reads, initial board agreement, final board change and
detail-contract condition therefore cannot be reconstructed. Zero persisted loads is not zero reads.
Added sanitized append-only progress/failure records with stage, fixed root code, approved affected ID,
completed count and observed board booleans. Preserve the first exception if browser cleanup also fails.
No speculative selector/mapping fix, vendor networking, new run or grant reset. Targeted 25 tests and
Ruff pass; two existing warnings. Original runtime records were inspected read-only and left unchanged.

## 2026-09-11 — controlled multi-system read phases prepared (offline)

Prepared owner-multi-system-20260911-01 against the exact owner-reconciled Active Loads scope.
Phases: same-process Ascend exact 11 details/current board check; tenant CarrierView active/future
plus unique details (14 GET max); assignment/gap-only Outlook (9 Graph GET/80 messages max); local
sanitized report. No vendor phase run or grant consumed. Owner 7/1/3 oracle is isolated after independent
classification, never assigned to loads. Unknown assignment/phone/stop/semantic evidence remains unknown.
Email claims stay review-required. Pilot eligibility is review only; no POST/canonical/write dispatcher.
Commands, evidence limits and stop conditions: docs/POC_002_MULTI_SYSTEM.md. This active/future plan
supersedes active/past for the multi-system run only; historical helpers retain their own scopes.
Verification: 104 targeted tests; full project regression 375 passed, Ruff and dashboard checks passed.
Two existing deprecation warnings remain. CLI help checked offline; all live phase grants remain unused.

## 2026-09-11 — reconciled Active Loads board; CarrierView read prepared

Owner confirms OPS_BOARD_RECONCILED, 12 rows, 8 pickups/3 deliveries for 2026-09-11. Local manifest
owner-active-loads-20260911-02 matches all 11 supplied IDs. Its VISIBLE_BOARD_ONLY coverage is preserved.
CarrierView helper is now bound to that exact scope. Plan: profile + active/past + at most 11 exact GETs
(14 max), tenant audit, no retry/write. Separate sanitized report preserves Ascend evidence unchanged.
Future/external-state semantics and verified absence remain unknown; no pilot qualifies yet. No new
vendor activity. 15 targeted tests/Ruff passed. See docs/POC_002_CARRIERVIEW_RECONCILIATION.md.

## 2026-09-11 — Active Loads attempt failure diagnosis (local only)

owner-active-loads-20260911-01 is consumed. Saved STOPPED_OPS_DISCOVERY has no error/stage/view/count
evidence; no candidate or manifest records exist. Exact runtime cause cannot be reconstructed.
Found and reproduced a likely cause: select_active_loads_view called JavaScript startsWith on a Python
href string, raising AttributeError for nonempty destinations before click. Corrected to startswith.
Unexpected exceptions now return fixed sanitized error_code/reason and recorded execution stage;
grid/row/queue counts are included only after observed. No exception payload/traceback is exported.
23 targeted tests and Ruff passed; two existing warnings. No live run/new attempt/vendor activity.
Active Loads authority and 8/3 reconciliation gates remain unchanged. Future owner-authorized live
attempt is needed to verify the fix, but none was prepared or consumed during this diagnosis.

## 2026-09-11 — POC #002 Active Loads exact-manifest implementation (offline)

Active Loads is now the only operational source for the 2026-09-11 manifest; All Loads is audit-only.
The reader structurally selects one visible semantic `Active Loads` control, then uses the existing
header/row validation and rejects ambiguous controls, header clones, duplicate load identities and
incomplete pagination proof. Each manifest persists observed_at, service date, source view, visible
board row count and an immutable evidence hash. Pick and drop are independently counted, including
same-day pickup/delivery loads. Exact 8 pickup / 3 delivery results yield OPS_BOARD_RECONCILED;
otherwise OPS_BOARD_MISMATCH reports the observed queue IDs and blocks CarrierView reconciliation and
all operational side effects. A future action requires a fresh Active Loads evidence-hash comparison.
All Loads extras are NON_ACTIVE_SERVICE_DATE_RECORDS and never expand the queue. No vendor activity,
live evidence or capability promotion occurred. Focused offline tests: 18 passed; two existing warnings.

## 2026-09-10 — observed All Loads parser correction (offline)

owner-table-schema-001 succeeded: 9 tables, real data grid 48 rows/33 headers/33 cells, zero-row
header clone, page size 100. Existing evidence has 13 matching rows/16 date occurrences for Sept 11;
old diagnostic load IDs were null because Load ID was not recognized. This supersedes schema-unknown
statements below. No new vendor activity or capability promotion during this change.
Operational parser now validates the observed v1 named columns and widths, excludes zero-row clones,
requires one visible data-bearing grid across frames, and rereads for consistency. Matched rows yield
the 12 requested board fields only, with Load ID from their own column 0. Board facts remain private;
derived pickup/drop queues can overlap and compare actual counts to 8/3 without forcing them.
The next login-discover-ops stays on the board: no details, phones, notes, finances or stop inference.
COMPLETE_CURRENT_BOARD requires explicit pagination totals plus disabled next/previous; otherwise
VISIBLE_BOARD_ONLY. Neither claims historical/system coverage. New prepared ID owner-live-ops-002
was verified unused, not consumed. Owner command: docs/ASCEND_ALL_LOADS_TABLE.md.
Verification: 15 targeted tests passed; broader Ascend/M4B plus operations regression ran once,
149 passed. Changed Python files pass Ruff. Two existing deprecation warnings remain.

## 2026-09-10 — All Loads schema diagnostic prepared

Owner-live-ops-001 is now confirmed consumed in the local ledger; saved stop is
ops_board_headers_missing_or_ambiguous. Owner observed All Loads, consistent with the workflow
passing its authenticated-session/navigation gates. Current blocker is table schema; older claims
below that this ops attempt has not run are historical. Tenant identity remains OWNER_ATTESTED.
Prepared separate login-diagnose-table, owner-table-schema-001, fixed date 2026-09-11, same-process
Python/msedge existing profile and normal networking. Structural schema/count evidence only; no
details, manifest or vendor writes. No live diagnostic was run here. Actual mappings remain UNKNOWN.
See docs/ASCEND_ALL_LOADS_TABLE.md for the owner command and evidence limits.
Verification: 355 offline tests passed; Ruff and all JavaScript/dashboard checks passed.
Two existing dependency deprecation warnings remain. No vendor networking was performed.

## ACTIVE PRIORITY — POC #002 LIVE OPERATIONS (offline preparation complete)

Owner's live operating board supersedes historical-load browser validation. Owner reports 1760 delivered,
approximately 8 pickups and 3 deliveries tomorrow. These are owner expectations only; actual loads,
calendar date and queue contents are not invented. No Ascend/CarrierView live action was performed here.

Implemented owner-executed login-discover-ops on the same local headed Python/msedge persistent session
with normal app networking. It prompts for the explicit operating date and board date format, then reads
only observed date-matching load identities with fixed read controls. Bound 500 visible rows/30 targets,
one-use dated grant, expiry/pause/session/exact detail/date-consistency/reread gates. Manifest coverage is
VISIBLE_BOARD_ONLY; pagination/hidden filters are not claimed complete and 8/3 counts are not forced.
Known fields/sections yield private provider facts and notes-presence only; unobserved/conflicting values
stay unverified. Preserve complete numbered stop groups; missing counts/zones/addresses block readiness.

New operations.sqlite3 is an isolated runtime store for provider candidates, tracking evidence, manifests
and proposal-only action ledger. No canonical shipment mutation. Both queues, sanitized owner report,
missing fields and count discrepancies are prepared by the read. CarrierView reconciliation is a separate
prepared tenant GET helper bounded to profile + active/past lists + selected exact matches, no fallback or
retry. A list miss is NOT_FOUND_IN_BOUNDED_READ because pagination is unverified, not proof of absence.
No inferred realtime tracking/ETA/POD state. Provider flags and raw Ascend status are separate from derived
classifications. READY candidates can yield hashed durable payload proposals; the ledger has no dispatch.
Company wire mapping and creation communication side effects remain unresolved pre-write blockers.

Created runtime operations/poc-002-plan.json with PENDING/null queues, not fake operational rows.
Owner command and full pilot/readback/UNCERTAIN/batch plan: docs/POC_002_LIVE_OPERATIONS.md.
No live read/write or POC002 LIVE_VALIDATED claim. Bootstrap -02 and historical attempt IDs untouched.
Full suite: 352 passed; lint/JavaScript/dashboard checks pass; two existing warnings. Focused operations
regressions cover date scope, raw/private separation, freshness/duplicates, payload idempotency and bounded GETs.

## Latest M4B — normal application networking and observed field proposals (OFFLINE ONLY)

Owner now explicitly authorizes normal app-generated traffic for the prepared same-process run. This
supersedes earlier statements requiring same-origin GET/HEAD as its safety boundary. login-validate-1752
uses existing headed Python/msedge profile, allows service workers and installs no HTTP/websocket route
filters before or after owner confirmation. No cookie/storage or request/response instrumentation runs
on this path. Older separate diagnostics retain their legacy settings and are not part of this command.

Mutation protection is in FreightDesk's fixed executor/actions. New ReadOnly1752Executor can navigate
the known /loads page, fill one observed searchbox with 1752, open its unique read/view control, and
inspect approved semantic tabs and fields. No generic click/submit/write/model-provided action interface.
Submit/default-form buttons and destructive/untrusted destinations are rejected. Exact detail identity
is checked before other field values; snapshot rereads and policy/pause/expiry/session checks remain.

An existing browser-contract.json is no longer required by the same-process discovery path. Actual
visible field labels/types/presence/attribute-presence and label-selector proposals produce a versioned
AscendFieldContract: provider AscendTMS, source live browser DOM, validation_load 1752, observed_at.
Only unique label/value candidates matching nonconflicting existing history/CarrierView values become
RECONCILED_FOR_1752. Unsupported, duplicate or conflicting mappings remain UNKNOWN. Values are compared
in memory; persisted proposals contain no raw customer values, notes, phones, tokens, HTML or screenshots.
This is a scoped proposal, not a general schema or automatic LIVE_VALIDATED promotion.

No live command was run. Owner executes the prepared owner-same-process-1752-01 command when ready.
Bootstrap -02 stays reserved; cross-process session reuse remains separate. See docs/ASCEND_ACCESS.md.
Offline verification: full suite 342 passed; Ruff and JavaScript/dashboard checks pass, with two existing
dependency warnings. Focused discovery regression covers normal POST/CDN app traffic, search/open,
wrong/duplicate detail identity, destructive/submit control blocking, redaction and reconciliation.
Navigation/detail hydration is bounded by DOM polling only (15/10 seconds), never a second action.

## 2026-09-10 — continuity diagnostics and same-process read implemented OFFLINE ONLY

Latest owner instruction prohibits any additional live Ascend action and reserves load attempt -02.
No production browser/network/storage diagnostic or load attempt was run this turn. Before/after auth
counts do not exist yet; they cannot be reconstructed from prior storage-file presence/DOM counts.
Implemented diagnose-continuity (manual owner login, aggregate before counts, one reopen, aggregate
after counts plus render/resource metadata) and login-validate-1752 (manual owner login then read in
the exact same page/context). The same-process path never closes/replaces the context between login
and verification, does not reload account root, and rejects reserved owner-bootstrap-1752-20260910-02.
It retains the existing strict session, policy/pause, one-use exact-load, contract and write gates.

Login and validation share AveryBrowserSession/chromium.launch_persistent_context, msedge, headed mode,
approved profile and Default subprofile (no override), explicit JavaScript enabled, blocked service
workers, identical application arguments, no explicit proxy override and Playwright default disabled
extensions. No launch-setting divergence found. Material behavior difference: login permits ordinary
networking; validation blocks every non-GET/HEAD or off-origin request and websockets. Startup also
closes restored tabs and opens a blank tab. Resource blocking and tab/process-scoped session loss are
plausible causes; neither is established. No network boundary was relaxed to diagnose them.

The new diagnostic stores only cookie/storage counts and booleans, no names/values/keys/expiry timestamps.
Resource reporting records root HTTP status, sanitized first-party redirect paths, error counts and
failed-resource type/opaque-origin counts, scripts/styles counts. No response bodies/API inspection.
Same-process successful read and cross-process session reuse are separate capabilities; no new
LIVE_VALIDATED claim. The verified live load field contract is still absent/unverified, so discovery
may stop before extraction. Exact future commands and limitations are in docs/ASCEND_ACCESS.md.
Offline verification: 332 tests, Ruff and JavaScript/dashboard checks pass, two existing dependency
warnings. Tests cover aggregate-only redaction, continuity comparison, resource counters, same-context
handoff/closure ordering, reserved attempt rejection and skipping account-root reload with gates intact.

## 2026-09-10 — separate structural session diagnostic completed

Owner explicitly prohibited validate-1752 pending resolution. Added diagnose-session using only the
existing local Python Playwright/AveryBrowserSession/msedge profile and verified https://ascendtms.com.
It navigates root once, waits before inspecting, then polls structural DOM evidence for up to 15 seconds
across ALL frames. No network/API inspection, link following, load grants or shipment reads. Cross-origin
frames can reveal login/incomplete evidence but cannot establish positive account/session authentication.
The diagnostic recommendation is separate from the existing load-reader gate and does not relax it.

Authorized diagnostic completed: final /, title AscendTMS, readyState complete, top-level body children 8,
body text length 23 (text never retained), frames 1, child frames 0, same-origin frame path /; no login
form, no approved nav labels, no dashboard/loads/customer/carrier/locations/accounting route anchors.
All frames inspected; render wait 15.011 seconds; no snapshot timeout. SESSION_AUTHENTICATED remains
unestablished. Tenant is Booking Logistics / OWNER_ATTESTED only. Root cause is unresolved; no inference
of expiry or wrong account. Attempt owner-bootstrap-1752-20260910-02 was not consumed; its claim,
read-grant and result files remain absent. Do not execute it until the diagnostic gap is resolved.
Evidence: runtime ascend/structural-diagnostic-20260910T120152548406Z.json. No raw HTML/text, screenshots,
cookies/tokens, customer data or unrelated URLs/query strings retained. No production writes.
Verification: 322 tests, Ruff and JavaScript/dashboard checks pass; two existing dependency warnings.
Six new tests include delayed rendering, iframe navigation/login, route-only anchors, empty app DOM,
and root-only/no-grant execution. Browser tests intercept synthetic pages; they are not vendor validation.

## 2026-09-10 — owner-attested M4B bootstrap, bounded attempt stopped

Supersedes prior literal-company identity requirement for this Customer Zero bootstrap only.
Origin remains https://ascendtms.com; do not request another hostname or manual login.
Tenant identity is Booking Logistics / OWNER_ATTESTED, never provider-derived verification.
Implemented separate authenticated-session gate: same verified origin, no /login.html or login form,
and Dashboard + Loads + at least two other approved visible navigation controls in one same-origin
frame. Only existing local Python Playwright / Edge msedge profile is used. No alternate context.
Five-field diagnostics contain path, allowlisted title, approved nav markers, login-form presence
and authentication result only. One-use bootstrap attempts stop on uncertainty; exact 1752 must
also match existing history/CarrierView evidence. Field reads still require an observed verified DOM
contract; no fixture selectors are promoted. Provider account hashes are never fabricated from attestation.

Executed owner-bootstrap-1752-20260910-01 at 2026-09-10T11:48:51.125191+00:00. Existing preferences,
cookie database and local storage detected without reading their values. Live diagnostic: path /,
title AscendTMS, approved navigation markers [], login form false, session_authenticated false.
Stopped before /loads; no exact load discovery, field read, reconciliation or production/canonical
write. This does not establish expiry, wrong tenant, or the cause of missing controls. Attempt consumed;
no automatic retry. Runtime ascend/owner-bootstrap-1752-20260910-01-{claim,result,dashboard-diagnostic}.json.
M4B session/load/reconciliation capabilities remain NOT LIVE_VALIDATED; tenant is OWNER_ATTESTED only.
See docs/ASCEND_ACCESS.md for the exact next command and its one-use/review boundary.
Software verification: 316 tests, Ruff and all JavaScript/dashboard checks pass; two existing
dependency deprecation warnings remain. Includes actual Edge with intercepted synthetic navigation
and login forms; these tests do not validate vendor behavior.

## 2026-09-09 — shared Python executor identity-only test

Verified login/read/identity use AveryBrowserSession with channel msedge and exactly
C:\FreightDeskRuntime\Browser\booking-logistics\ascend. Validation now requires an existing profile
and cannot silently create one. No incognito context, storage-state import, cookie copy, Computer Use
or cloud browser is used. Existing preferences, cookie database and local storage were detected
without reading cookie values. Prior troubleshooting's Node driver is not the validation path.

Added strict https://hostname origin validation and identity-only CLI mode. Executed:
`.tools/python/python.exe -m scripts.ascend_browser identity --owner-authorized --origin https://ascendtms.com`.
At 2026-09-09T19:16:53.901184+00:00, the shared local executor reopened the existing profile, but
company/user/dashboard indicators were absent in the same-origin frame. No other frame origins were
observed. Stopped and closed cleanly before load 1752 navigation. Authentication/session survival is
NOT verified; file presence is not proof of authentication. No inferred wrong account or expiry.
Sanitized audit: runtime Data/booking-logistics/ascend/identity-only-result.json. No writes/canonical
mutation or M4B capability promotion. 303 tests, Ruff and all JavaScript checks pass; two prior warnings.

## 2026-09-09 — authorized phase one stopped before load discovery

Owner supplied https://ascendtms.com/ and a screenshot showing BOOKING LOGISTICS LLC after manual
login. The dedicated profile was reopened with same-origin GET/HEAD-only routing. The confirmed
origin loaded, but the automated top-level DOM did not establish the company/user identity shown
in the screenshot. This is an unresolved browser/DOM/session verification gap, not proof that the
owner logged into the wrong account or that the session expired. No load navigation/extraction or
reconciliation occurred. Per the owner identity gate, stopped and set the browser offline.
Sanitized evidence: runtime Data/booking-logistics/ascend/phase1-1752-verification-stop.json.
No operational write, canonical mutation or M4B LIVE_VALIDATED promotion. Browser-driver path
resolution was corrected locally using the verified installed Edge executable; no new dependency
was installed. Earlier manual-login-pending entries below are historical checkpoints.

## 2026-09-09 — M4B phase-one authorization; manual login pending

Owner explicitly selected Booking 1752 and authorized the dedicated browser launch, manual login,
account verification and one bounded read-only reconciliation. All operational mutations remain
forbidden. Dedicated Avery Edge window launched and is waiting for owner login/MFA; no account
identity or shipment fields have been read or validated. No M4B capability is LIVE_VALIDATED yet.
Initial helper startup failed before its login prompt; corrected a last-tab startup race by opening
the replacement blank tab before closing old tabs, while offline. Isolated checks and the full
291-test suite pass, with Ruff and JS checks. No browser error payload or credential was logged.
Continue from the owner's login-complete confirmation; never repeat login or broaden load scope.

## M4B — offline Ascend foundation; stopped at first live boundary

IMPLEMENTED / TESTED: AscendAdapter, deterministic AscendBrowserAdapter, Playwright BrowserExecutor,
dedicated Avery persistent profile, bounded exact-load grant/identity checks, raw/normalized facts,
local per-source reconciliation, isolated read/audit ledger, fixture-only write precondition/claim/
post-verification/UNCERTAIN handling and protected local dashboard panel. 290 tests, Ruff and all
JavaScript checks pass. Real headless Edge tests use intercepted synthetic pages and disposable
runtime profiles; they do not validate Ascend. Two existing dependency warnings remain.

M4B LIVE_VALIDATED: **none**. No Ascend login, navigation, API call, real read or write occurred.
No CarrierView/Outlook networking, canonical mutation, historical import or scheduler action occurred.
Prior capability scopes and Microsoft send guards remain unchanged. Playwright package/docs access
does not establish an Ascend API contract.

Dedicated profile: `C:\FreightDeskRuntime\Browser\booking-logistics\ascend\` (prepared, never launched).
Setup lives under runtime Data/booking-logistics/ascend. Future observation/action/audit storage is
runtime Data/booking-logistics/ascend.sqlite3, separate from historical/canonical/mail stores.
Live origin, account identity and selectors remain unverified. Private browser-contract.json and
one-use read-grant.json intentionally await authorized UI inspection/owner review.
Proposed first read is Booking 1752, pending explicit owner selection; 1753 is not selected.

Exact first-boundary steps: docs/ASCEND_ACCESS.md. Contracts and disabled tender/BOOK IT designs:
docs/ASCEND_CONTRACT.md. Production mutation methods remain blocked independently of policy/approval.
Operation-specific mutation DOM flows and current pricing require separate work/authorization.
The dashboard reads protected local evidence only; no browser starts from HTTP. The running local
server was not restarted or granted new access during this handoff.

## M4A — approved historical commit and intelligence validated

Inspected the actual owner-provided export in the approved runtime inbox. Source SHA-256:
`af7e479a94f44f7f7541e2ecdd725de48e37656f2a0da92085670e16d0886bb0`.
Observed 694 rows, 59 exact columns, 694 unique Load IDs, 19 raw customers, 354 raw carriers and
14 equipment labels. Pickup coverage 2024-09-03–2026-09-04; creation coverage 2024-08-28–2026-09-03.
All financial controls reconcile from staged typed values and independently from source:
income 1,693,484.10; total expenses 1,378,557.00; gross profit 314,927.10; aggregate margin 18.596401%.
All 694 row arithmetic and rounded percentage checks pass. Owner confirmed USD for income,
total expenses and gross profit. Total Expenses is NOT mapped to carrier pay.

One batch / 694 rows are staged and 694 `ascend_history_record` records are now committed in
`C:\FreightDeskRuntime\Data\booking-logistics\history\history.sqlite3`. Owner approval binds source,
mapping, batch, row count, USD and all retention limitations. The pre-commit SQLite backup is private.
Repeated actual commit inserted zero rows and left records AND audit unchanged. SQLite integrity is OK.
Zero canonical/mail/scheduler records were written. No Graph, CarrierView or Ascend networking occurred.
Real historical commit, idempotent re-import, post-commit profiles and internal financial distributions
are now LIVE_VALIDATED for this export only. Changed-version reconciliation has synthetic tests only.

Generated 19 CustomerProfile, 110 LaneProfile, 354 named CarrierProfile, 163 exact endpoint
FacilityProfile and one RateHistorySummary, plus 14 equipment usage groups. Two rows lack carrier
identity and seven lack equipment; their evidence is explicit and remains in all full-sample totals.
Every profile/statistic includes sample size, pickup-date range, source/batch/evidence references,
calculation timestamp and raw-versus-derived designation. Delivery coverage is 2024-09-03–2026-09-08
on 693 populated dates. Internal USD history is not current market pricing.

Review items: 110 exact raw lanes become 109 under proposed trim/casefold grouping (not applied);
one Completed row lacks delivery date; MC has 139 prefix-only `MC`, two blanks and one value with
trailing whitespace; DOT has two blanks and four values with surrounding whitespace. 533 MC
strings have leading-zero numeric portions, preserved. There are 144 rows with identifier warnings;
zero invalid-date/money rows, source duplicates, prior-version conflicts or hard anchor mismatches.
All 15 expected empty columns remain empty. Exchange Rate Date stays raw metadata only.
Pickup/delivery timezones remain unknown; date-only and local date-time evidence are kept distinct.

The proposed Tube Supply identity group covers three raw labels / 326 loads without merging.
All 14 equipment mappings remain proposals, including flatbed-or-step-deck alternatives and Air-Ride.
Bounded per-customer deterministic note review produced 19 candidate topics (first 50 source-order
loads/customer, 4000 characters/field, no model). These may be boilerplate or negated, not approved SOPs.
Private notes are omitted. Full report, profiles, verification and original proposed mapping are under runtime history/reports/
`090676423701034e909dc695d1920546c7c410b4697877c799141aebee0a81d4`.

Artifacts: `historical-intelligence.md`, `historical-intelligence.json`, `commit-verification.json`.
Report calculation timestamp: 2026-09-08T11:43:50.190088+00:00; figures above are derived from
this 694-row batch (raw identities retained), with each subgroup's n/date range/evidence in the report.
The original staging review remains a pre-approval artifact. **252 tests pass**, Ruff and both JS
rendering checks pass; prior two dependency warnings remain. No new vendor or operational capability
is authorized. Alias/equipment approvals and confirmed SOPs remain separate future owner decisions.
Alias/equipment proposals may stay unapproved. See docs/HISTORICAL_INTELLIGENCE.md and LIVE_POC.md.

## M3 — bounded production validation owner-confirmed

Evidence source: the owner's completed bounded-production-run report and manual Outlook
Drafts-folder confirmation. This documentation update made no additional Graph requests and did not
inspect tokens, message bodies or runtime payloads. No timestamp, message IDs, correlation results or
attachment evidence have been invented. No email was sent; no Ascend, CarrierView or canonical
shipment write occurred. Exactly one unsent draft is the only reported provider write.

| M3 capability | LIVE_VALIDATED | Evidence / limit |
|---|---|---|
| Microsoft OAuth authentication | YES | Owner reports successful production authentication |
| Exact mailbox identity verification | YES | /me matched info@bookinglogistic.com |
| Mailbox settings read | YES | Successful production settings read; preferences are not freight timestamp proof |
| Bounded production mail discovery/read | YES | 5 real messages in this bounded sample |
| Real-message ingestion/processing | YES | All 5 processed; does not prove extraction accuracy or shipment matching |
| Unsent draft creation | YES | Exactly 1 created; owner confirmed it in Avery's Drafts folder, unsent |
| Attachment download/classification | NO | 0 stored; attachments were not exercised |
| Delta/incremental sync | NO | Recent-message intake does not exercise delta checkpoints |
| Real shipment correlation | NO | No explicit match evidence supplied |
| Production sending | NO | No email sent; HTTP execution remains blocked |
| Mail.Send OAuth scope | NO | Entra-configured only; excluded from current OAuth request |
| Automatic canonical shipment mutation | NO | No canonical shipment write occurred |
| Owner commands by email | NO | Not exercised |
| Graph webhooks | NO | Not exercised |
| Autonomous communications | NO | Not exercised or authorized |

Entra has User.Read, Mail.ReadWrite, MailboxSettings.Read and Mail.Send configured. Current OAuth
requests only User.Read, Mail.ReadWrite and MailboxSettings.Read (plus MSAL standard session scopes).
ActionPolicy independently allows bounded reads/settings/drafts; customer/carrier/dispatcher sends
remain APPROVAL_REQUIRED and send_message/send_reply/send_forward HTTP execution stays blocked.
Successful OAuth is not evidence that Mail.Send was requested or authorized.

The M3 software foundation remains IMPLEMENTED and TESTED: Graph read/draft adapter, DPAPI cache,
transactional delta, typed events/extraction, review-only proposals, correlation, attachment storage,
owner-command boundaries and protected dashboard. Historical staging/profiles/rates/rule approval
remain fixture-tested only at the M3 checkpoint; the new M4A staging above is separate. Reply/forward draft variants,
search/conversation reads, extraction accuracy and full workflow reliability are not validated by
this sample. The six YES rows above are the complete M3 LIVE_VALIDATED allowlist.

**211 tests pass**, with Ruff and JavaScript checks passing. The two existing dependency deprecation
warnings remain. No application code, execution guards or runtime records were changed by this update.
No additional Graph networking is authorized. A further attachment, delta or correlation validation
requires a separate explicit bounded authorization; do not rerun login/validation helpers automatically.
See [OUTLOOK_ACCESS.md](docs/OUTLOOK_ACCESS.md), [LIVE_POC.md](LIVE_POC.md) and
[HISTORICAL_INTELLIGENCE.md](docs/HISTORICAL_INTELLIGENCE.md).

The earlier M1/M2 evidence below remains unchanged; its test count describes that earlier checkpoint.

**LIVE POC #001 — Historical Production Replay is imported and displayed.**
Owner explicitly reconciled Booking reference 1752 / CarrierView 99616 against the UI and
approved this historical canonical import. No new CarrierView API requests were needed for import.
Load 1753 is a separate owner-reported delivery and has not been read/imported.

## Implemented, tested and live-validated

M1 demo foundation remains implemented/tested: lifecycle, tracking/RC/POD/billing gates,
authorization, policy, approvals, audit/events, scheduler, risk and dashboard.
151 tests pass, Ruff passes, JS syntax/render assertions pass. Actual protected browser view checked.

| Capability | IMPLEMENTED | TESTED | LIVE_VALIDATED |
|---|---|---|---|
| Tenant authentication / Booking Logistics company profile read | Yes | Yes | Yes, tenant |
| Past-load discovery | Yes | Yes | Yes, historical |
| Exact shipment read / identity reconciliation | Yes | Yes | Yes, selected historical shipment |
| Last-position retrieval | Yes | Yes | Yes, retrieval only; numeric time units unverified |
| Position-history retrieval | Yes | Yes | Yes, first page only: 10 of 218 |
| Historical stop timeline / owner UI reconciliation | Yes | Yes | Yes |
| Canonical historical import | Yes | Yes | Yes |
| Protected historical dashboard display | Yes | HTTP/JS/browser | Yes |
| Real-time monitoring | Foundation only | No live monitoring | No |
| Webhook processing | Local quarantined inbox | Fixtures | No |
| Tracking creation/initiation | Create implemented; no separate initiate endpoint | Fixtures | No |
| SMS / chat | Implemented, production blocked | Fixtures/ledger | No |
| Live autonomous execution | Not enabled | Demo simulation only | No |
| POD / signed RC / billing readiness | Canonical gates only; provider document API unknown | Gate tests | No |

LIVE_VALIDATED is capability-specific. The general demo health flag does not claim a live runtime.

## Imported canonical record

Runtime tenant: booking-logistics; record: live-poc-001; demo=false; workflow=historical_production_replay.
Canonical DELIVERED is explicitly a FreightDesk mapping of reconciled provider delivery flags and
owner confirmation. It does not mean CLOSED, POD received, signed RC verified or billing ready.
Provider records, nulls, URLs and source seconds are preserved in private provider metadata.
Customer and driver name remain unknown; no invented customer record. Driver phone stays private
in source metadata and is omitted from the dashboard projection.
Appointment window starts map to canonical Stop.appointment; full windows remain in source/report.
Risk WARNING and arrival assessment are FreightDesk-derived, not CarrierView classifications.
Record is paused/human-owned, stored outside the demo database, with no operational tasks queued.
Owner approval is hash-bound to immutable historical evidence. Repeat import of identical evidence
is idempotent; different evidence cannot overwrite POC #001.
Historical reconciliation does not reuse the real-time import's 15-minute freshness rule.

## Storage and access

Source: C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI.
All operational data stays under owner-authorized C:\FreightDeskRuntime, outside OneDrive.
- Data\booking-logistics\carrierview.sqlite3: canonical POC, provider metadata, scope matrix and audit.
- Data\booking-logistics\historical-1752: private evidence, report and owner-import-confirmation.json.
- Data\booking-logistics\demo.sqlite3: four synthetic DEMO loads, separate controls/scheduler.
- Data\TestRuns\pytest: test databases; Tokens: local demo token; Logs: server logs.
- Data\server.pid: current background server PID; verify executable/command before stopping.
- Secrets: independent encrypted agent/tenant CarrierView DPAPI files; never print their contents.

Loopback dashboard: http://localhost:8787/#live-poc. Protected owner session is open in the app.
To reopen privately from the project:
```powershell
& '.tools/python/python.exe' scripts/open_live_poc.py
```
The launcher issues a one-use, three-minute grant, cleared from the URL before exchange for a
separate eight-hour HttpOnly session. No CarrierView token enters the browser. Demo cookies cannot
unlock this view. There is no public grant-issuance route. General production modes remain disabled.

CarrierView API service credential is explicitly tenant, actor FreightDesk/Avery, with the
owner's manager/admin eligibility reason. Agent real API execution is blocked; no fallback.
All provider POST/PATCH/PUT remain disabled. This turn used no provider networking.

## Remaining scope

GPS history is partial, numeric position timestamp units and app-status acceptance semantics
remain unverified. Documents/POD API is unsupported/unknown. No real-time monitoring, webhooks,
outbound communication, tracking initiation, autonomous operations or billing validation.
Other vendor/model/browser-worker/voice integrations remain interfaces or notes.
The local single-process deployment is not a multi-user production authentication system.
See KNOWN_ISSUES.md and LIVE_POC.md.

No Git commit, branch, remote or deployment was created. Existing source remains untracked for review.
