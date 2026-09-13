> Latest owner milestone: source0.5.0 [workspace Mapping Mode](ASCEND_X1_MAPPING_MODE.md)
> supersedes the proposed per-panel detail -03. First validation cohort is not a permanent ID limit.
> OBSERVE and AUTO_MAP use separate owner lease scopes; normal AUTO_MAP requires reviewed cohort proof. No live execution or
> new capability promotion here. Earlier version/attempt instructions below are historical.

> Source0.4.3 supersedes the generic container bound and first-attempt commands below. Read
> [causal container correction](ASCEND_X1_CAUSAL_CONTAINERS.md) for consumed -02 evidence and
> the proposed owner-only -03. No live execution here. Older sections describe the initial design.
>
> Source0.4.1 supersedes older content refresh instructions. See
> [content lifecycle correction](ASCEND_X1_CONTENT_LIFECYCLE.md). Do not refresh/re-pair or run
> a detail attempt to diagnose lifecycle failure. Owner reload is required; no live execution here.

# X1 operational detail contract v1 - offline preparation

Status: IMPLEMENTED / OFFLINE TESTED; not live executed or LIVE_VALIDATED. Read access remains revoked.
The separately proven X1 Active Loads board runtime remains LIVE_VALIDATED within VISIBLE_BOARD_ONLY.
Source extension version is 0.4.0. No new transport, browser profile, registry change, enrollment,
bootstrap, lease or vendor request was created during this milestone.

## Architecture and trust boundaries

The existing X1 content script is the first BrowserSensor/executor. `webbridge.js` is a bounded
DOM-only module, loaded in the isolated extension world. It has no network/messaging, click, write,
or model primitive. Provider vocabulary is in detail-scope.json and its matching JS module; these
are proposed label aliases, never claims of observed Ascend selectors.

Components: BrowserSensor produces metadata; DOMSnapshot fingerprints likely detail containers;
DOMDiff finds new/newly-visible/structurally-changed/directly-referenced containers; LocatorGraph
combines section, label relationships, role/type, approved attribute names and relative element
path; EvidenceScorer assigns deterministic levels; AdaptiveLocator proposes equivalent semantic
read remappings; ProviderContract fingerprints structure. This is Ascend-sized infrastructure, not
a generic scraper. No model/visual inference is implemented.

The existing exact-row FIND and single OPEN_READONLY executor remains the only opener. Discovery
requires the same provider-backed identity receipt (expected ID equals observed ID), board revision,
document binding, current host lease and independent Active Loads proof before and after sampling.
Unknown/conflicting identity stops before reading operational controls. Accepted strategies remain
PROVIDER_DETAIL_FIELD, PROVIDER_OPENER_IDENTITY and PROVIDER_SELECTED_ROW_BINDING. Operational
similarities cannot establish identity. Tenant identity remains OWNER_ATTESTED.

Discovery is a new fixed operation ASCEND_DISCOVER_DETAIL_CONTRACT, inaccessible through arbitrary
selectors, scripts or URLs. Only the local owner queue can attach a one-use detail attempt to an
existing unexpired lease and fresh observed board. The ID must be in that exact visible board.
The queued board hash is pinned; changed-board or changed-document evidence stops rather than
reselecting or substituting another load. No all-load batch and no workflow-triggered discovery.

## Proposed field inventory

| Section | Contract fields |
| --- | --- |
| Identity | load_id |
| Assignment | carrier, driver_name, driver_contact, dispatcher_contact, power_unit, trailer, equipment |
| Status | load_status, truck_status, last_contact_tracking |
| Pickup | pickup_facility, pickup_address, pickup_window, pickup_reference |
| Delivery | delivery_facility, delivery_address, delivery_window, delivery_reference |

Driver contact covers a provider-labeled driver phone/contact field. Appointment window fields
require an explicit provider-labeled window/appointment control. Separate date/start/end controls
are not guessed or silently combined. Multiple stops with duplicate field labels remain UNKNOWN;
no stop order, timezone, timestamp conversion or appointment interpretation is invented. Labels
outside the proposed vocabulary or unsupported static/custom widgets remain UNKNOWN pending
observation and a new candidate contract. Hidden sections are not opened by this milestone.

Rates, income, expenses, profit, private notes, documents, communications and all mutations are
outside the schema. Unknown/excluded fields do not have their values sampled. Approved fields
produce only PRESENT/EMPTY/UNKNOWN metadata; no actual values are persisted even though protected
value storage could be separately implemented later. Native receipts cannot accept raw value keys.

## Evidence levels and activation

| Level | Meaning | This implementation |
| --- | --- | --- |
| LEVEL_1 | Exact provider identifier / explicit binding | Identity proof; exact scoped data-field binding |
| LEVEL_2 | Stable labeled provider DOM field | Unique label-control / aria-label / aria-labelledby in approved section |
| LEVEL_3 | Structural relationship | Neighbor label / table-header relationship; PROPOSED only |
| LEVEL_4 | Semantic inference | Not produced or accepted for automation |
| LEVEL_5 | Model/visual inference | Not implemented |

Identity requires LEVEL_1-equivalent provider proof. A unique non-conflicting LEVEL_1/2 operational
mapping can have confidence VERIFIED for that observation. That is **not** activation or vendor
LIVE_VALIDATED status: every artifact has activation=CANDIDATE_ONLY, writes_allowed=false,
values_included=false, and host live_validated=false. There is no API to activate a candidate.
LEVEL_3 stays PROPOSED; conflicting/duplicate signals yield UNKNOWN. Host validation recomputes
confidence and the structural fingerprint instead of trusting a submitted confidence label.

A locator records canonical approved label, section, strategy, tag, control type, role, nearby
approved labels, approved attribute names, and numeric path relative to the verified detail root.
Arbitrary id/name/data-* values and arbitrary text never enter diagnostics. Provider, view,
observed_at, validation load ID, contract fingerprint and provenance apply to every field through
the immutable parent contract. Stable label/section/type/role can propose a remapping if a path
changes; proposals cannot activate themselves, execute writes or replace old observations.

## DOM differential and bounds

Snapshot queries only likely detail containers: dialogs, known modal/side-panel containers,
tabpanels and data-load-detail containers. It does not enumerate every page node or input.
Before click it retains structural state in ephemeral memory. After click it narrows to relevant
visible containers, then requires a unique provider-bound detail panel. New visibility, selected/
expanded/active state, approved heading changes, form structure and provider binding attributes
participate in differential comparison. Direct opener references are retained independently.
Unrelated page changes do not authorize field scanning. Multiple candidate detail roots stop.

Bounds: 12 candidate containers, 24 attributes per inspected element, 64 candidate controls per
detail root, 32 headings, 8 candidates per field, and 10 relative-path levels. Exceeding a category
returns DETAIL_BOUND_CONTAINERS / ATTRIBUTES / CONTROLS / HEADINGS / CANDIDATES / DEPTH. No broad
page-wide fallback or automatic increase. Only approved field labels/section names are emitted;
private values, HTML, arbitrary scripts, screenshots and network payloads are not recorded.

## Persistence and one-load lifecycle

Existing runtime.sqlite3 under C:\FreightDeskRuntime\Data\booking-logistics\ascend-native gains
append-only runtime_detail_attempts and runtime_detail_contracts on a future authorized host run.
No actual runtime schema was migrated by this coding task. Attempt ID is consumed atomically with
queue acceptance; preflight rejection does not consume it. Attempts bind load, lease and board hash.
No retry of a consumed attempt. Schema v1 and candidate contract_version are distinct. A first
observation is version1; changed structural fingerprint creates the next candidate version;
unchanged fingerprints append another observation without replacing old evidence. Artifact and
receipt acceptance are atomic. Local audit contains only fixed safe codes/counts/operation/time.

Sequence after owner queue: fresh session -> Active Loads -> recheck pinned board -> FIND ->
OPEN_READONLY -> provider identity -> DISCOVER_DETAIL_CONTRACT -> STOPPED / DETAIL_DISCOVERY_COMPLETE.
Legacy READ_LOAD/STOPS/ASSIGNMENT still return UNKNOWN; this operation does not activate them.
Any discovery failure is latched stopped, with no automatic retry. The owner then disables the
lease. Pause/revoke/expiry/security gates remain independent. Enrollment is never reset.

## Prepared first live validation (owner execution only; not executed)

Proposed unused attempt ID: **owner-x1-detail-20260911-01**. Checked absent from the local runtime
attempt ledger; this is a proposed ID, not a generated grant. No load ID is predetermined.

1. Reload the existing pinned X1 extension to source 0.4.0. Do not reinstall/re-pair. Keep the
   authenticated Ascend tab; existing bounded content-version recovery applies. Confirm the local
   enrolled connection resumes. Stop if enrollment/session recovery fails.
2. In the project PowerShell directory, explicitly enable a six-minute owner read lease:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime enable --owner-executed --hours 0.1 --interval-seconds 60
   ```

   This starts real reads; do not execute as an offline check. Leave Edge open. Check status:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime status --owner-executed
   ```

3. Require READ_ONLY_READY, AUTHENTICATED, ACTIVE_LOADS, one bound eligible tab and a new board sync
   from this lease. Owner selects exactly one ID currently visible on that verified Active Loads
   board. 1755 is allowed only if actually present. Do not infer IDs from historical fixtures.
4. Queue that one load (do not paste sensitive data):

   ```powershell
   $detailLoadId = Read-Host 'Exact Load ID on the freshly verified Active Loads board'
   .\.tools\python\python.exe -B -m scripts.ascend_x1_detail queue --owner-executed --attempt-id owner-x1-detail-20260911-01 --load-id $detailLoadId
   ```

   The host rejects absent/stale IDs and in-flight ambiguity. After accepted queue, do not click
   tabs/rows, start another command, or queue another load. Allow the fixed bounded sequence to
   complete; it stops automatically. If it fails, do not retry the opener or consume another ID.
5. Read the metadata-only report, then revoke the lease:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_detail report --owner-executed --attempt-id owner-x1-detail-20260911-01
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime disable --owner-executed
   ```

   Also disable if preparation/queue/discovery fails. No additional detail attempt without review.

Expected output is conditional, never preclaimed: DETAIL_DISCOVERY_COMPLETE, contract_version,
CANDIDATE_ONLY, live_validated=false, production_writes=false, and per-field presence/mapping/level.
For example a unique explicit carrier label may yield PRESENT / VERIFIED / LEVEL_2, while unavailable
or ambiguous windows remain UNKNOWN. No raw phone, address, customer value or note is printed.

Stop on lease/policy/session/view failure, missing/nonunique row, board drift, unsafe opener,
unknown/conflicting identity, ambiguous container, bound excess, invalid contract or persistence
failure. Individual field ambiguity remains UNKNOWN and cannot be operationally accepted; a report
can still document that gap. No CarrierView/Outlook calls, pricing, communication, write, canonical
mutation, automatic contract activation or detail LIVE_VALIDATED promotion.

## Offline validation completed

244 targeted tests passed across new DOM/contract/attempt tests and existing X1 runtime, controller,
identity/view, enrollment/native host/startup and protected API/dashboard suites. Ruff, JS syntax
and runtime Node fixtures passed. Fixture DOM cases cover labeled/ARIA fields, conflicts, duplicate
labels, hidden/aria-hidden controls, scoped pickup/delivery, LEVEL_1/2/3, changed selectors, unchanged
values/fingerprints, DOM differential changes, bounded scans and poisoning of excluded value getters.
Host cases cover one-use attempts, fresh board, changed board, identity stop, revoke, append-only
versions, atomic persistence failure, raw-value rejection and impossible write/other-vendor commands.
Existing two Starlette/httpx and AnyIO deprecation warnings remain. Headless DOM fixtures intercepted
all requests; no live profile, installed host, Ascend, CarrierView or Outlook networking occurred.
