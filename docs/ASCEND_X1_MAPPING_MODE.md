Current product entry: [Mapping Orchestrator V1](ASCEND_MAPPING_ORCHESTRATOR.md).
The manual per-step commands below are advanced/historical; no live execution was performed.

# X1 0.5.0: load workspace identity and owner Mapping Mode

Status: IMPLEMENTED / OFFLINE TESTED. No live mapping, lease activation, new pairing, browser launch
against Ascend, registry change or vendor request was performed. Source version 0.5.0 needs an owner
extension reload. Existing durable enrollment is reused. No permissions were added.

This milestone supersedes the proposed panel-by-panel detail attempt `owner-x1-detail-20260911-03`.
Do not queue it as part of mapping. Preserve existing consumed attempts and historical evidence.
The previously LIVE_VALIDATED Active Loads board reader and VISIBLE_BOARD_ONLY scope are unchanged.
Mapping Mode, workspace inheritance, operational field reads and Planning/Accounting views have no
new LIVE_VALIDATED promotion.

## Architecture

A provider-maintained load workspace proves `entity_type=LOAD`, `load_id=N`, `provider=AscendTMS`.
The public identity must be outside the current child section. Exact `Load #N` header/control or
breadcrumb, an actually present same-origin `/load(s)/N` route, or an explicit provider workspace
attribute can supply proof. Signals must agree. The sensor requires a unique workspace shell with
at least two known section controls. Child content alone, prior selection, load counts and board IDs
cannot supply workspace identity. Tenant identity remains separately OWNER_ATTESTED.

Each capture re-establishes identity before collecting metadata and rechecks workspace, selected
section and structure after stabilization. Children inherit only this current verified workspace.
A changed document or load creates a new observation boundary. Ambiguity/conflict/change during
capture stops; the mapper stops rather than repairing uncertainty through another navigation.

`BrowserSensor` captures; `DOMSnapshot` and `DOMDiff` establish/recheck workspace structure;
`LocatorGraph` records relative relationships, semantic labels, roles and approved attribute names;
`EvidenceScorer` assigns proposed levels; `AdaptiveLocator` proposes a replacement on compatible
structure; `ProviderContract` fingerprints metadata. No fixed selector alone activates a read mapping.

## Two product modes, separate from validation scope

**OBSERVE** passively observes the verified workspace and sections the owner visits. It learns unknown
structure, detects drift and proposes contracts. It never traverses sections. A stricter first-cohort
scope can use explicit captures for controlled evidence. Normal OBSERVE follows owner navigation
without an ID list or a prerequisite trained field map.

**AUTO_MAP** automatically traverses known, VERIFIED READ_ONLY_NAVIGATION controls within the exact
current load, captures each section and returns to the starting section. It needs no repeated manual
section visits once those controls are verified. The host fixes the sequence; no model/page-supplied
selector, script, endpoint or target load can expand it. Initial supported controls are actual visible
provider role=tab buttons explicitly type=button or anchors with same-document fragment targets.
Controls in forms, submit controls, missing/ambiguous relationships and unverified full-document
navigation are not eligible. These are conservative compatibility limits, not claims about live DOM.

The return control must also be verified before the first transition. Before every click, session,
lease/policy, foreground owner presence, exact LOAD/N/provider, unchanged shell, expected starting
section and control fingerprint are checked. After each navigation, the exact load/section are checked
again and sanitized metadata is captured. Up to eight reviewed sections (including the starting one)
are supported per cycle. Conflicts, drift, ambiguity, missing controls or unexpected navigation stop;
an uncertain identity never triggers a return click. A successful cycle records its visited sections
and verified return. Normal unchanged workspace metadata skips duplicate traversal.

Operational values remain UNKNOWN until separately validated read mappings exist. AUTO_MAP currently
assembles metadata across sections; it does not turn a learned label into an operational fact. The
current executor covers owner-present workspaces. A future trusted FreightDesk background job needs
its own exact-load read authorization/binding; no load-opening or bulk worker is added here.

The **3–5 load cohort is only the first controlled AUTO_MAP validation procedure**, preceded by OBSERVE
where navigation structure is unknown. It is not the permanent architecture restriction. Internally
FIRST_VALIDATION/NORMAL_OWNER_PRESENT describe the lease scope/trigger, while operation_mode is
OBSERVE/AUTO_MAP. CLI exposes these independently as --scope and --mode.

| Control | First cohort procedure | Normal defaults |
| --- | --- | --- |
| IDs | Explicit 3–5 representative loads | No list required; optional narrower list |
| Who opens a load | Owner | Owner/current authorized workspace |
| OBSERVE sections | Owner visits unknown sections | Passively observe owner visits |
| AUTO_MAP sections | One owner-started cycle per cohort load | Automatically traverse reviewed sections of the owner-opened load |
| Lease | 20 minutes | 20 minutes; configurable 1–30 |
| Workspace boundaries | 15 | 10; configurable 1–30 |
| Section observations | 40 | 60; configurable 1–120 |
| Field-contract observations | 2,000 | 1,000; configurable 1–3,000 |
| All capture attempts, including unchanged checks | 60 | 120; configurable 1–300 |

Workspace budgets count document/load boundary changes, including revisits. Section/field budgets
count persisted observations. Normal unchanged checks consume an attempt but add no map version.
Bounds, pause, expiry and revoke stop authority; the host rechecks them before accepting evidence.
Normal AUTO_MAP enable is blocked until a successful 3–5 load AUTO_MAP cohort and explicit owner
review are recorded. OBSERVE evidence alone cannot unlock AUTO_MAP. No read field/write is activated
by either navigation review or cohort qualification. No permanent mandatory ID list remains afterward.

Owner-present modes use the active tab in the last-focused window and a visible/focused document.
They never select a background load to continue. Lease-limited structural hints contain no DOM values;
the host still authorizes each capture. Observers stop on expiry/port loss and are suppressed during
AUTO_MAP's own transitions, then restored at the starting section. Hints are debounced; the existing
60-second scheduler is a fallback. Suspended workers, fleeting/hidden sections or lazy content may
delay/miss observations. The 5–10-second complete context goal has not been timed or live validated.
Known AUTO_MAP sections are traversed in one bounded worker sequence, with separate host authorization
and receipt checks at every transition; no manual click between those sections is required.

## Captured contracts and privacy

Append-only tables in `C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\runtime.sqlite3`:
`runtime_mapping_sessions`, `runtime_provider_maps`, `runtime_mapping_validations`,
`runtime_navigation_contracts`, `runtime_auto_map_cycles`; existing signed
receipts and safe audit events retain provenance. No runtime evidence is stored in the source tree.

Each provider-map observation includes schema/build version, observation time, workspace proof,
sanitized path pattern, document/dynamic/workspace transition classification, section fingerprint,
and versioned workspace/section contracts. Safe navigation candidates retain provider label, tag, role,
reference kind and relative relationship fingerprint; reviewed versions bind READ_ONLY_NAVIGATION
to the observed workspace fingerprint and provenance map version. Fields carry candidate name, canonical semantic label,
control type/editability/role, relative path, safe aria relationships/data-attribute names, proposed
evidence level, load/time provenance and structural fingerprint. Prior observations are never updated.

Prepared owner-observed sections: Load Basics; Customer Info; Carrier / Asset Info; Edit Stops;
Financials. Prepared operational surfaces: Load Actions; Post/Search Load Boards; Load Log;
Dispatch and Tracking; Load Documents; Admin / Financials; Copy/Cancel/Archive; Customer Portal.
Seeing an action label is metadata only and never grants permission to invoke it.

Unknown section names become DISCOVERED_UNCLASSIFIED. Unreviewed labels become UNCLASSIFIED_LABEL;
unknown data-attribute names become data-unclassified. Raw field values, phone numbers, addresses,
private labels/notes, script text, arbitrary attribute values, HTML, cookies, tokens, screenshots and
network bodies are excluded. The mapper does not read input values. Static text without an observed
safe field/control relationship remains unmapped. Observed presence means a visible control, not a
verified nonempty business value. Cross-load differences are POSSIBLY_OPTIONAL_OR_CONDITIONAL
proposals, never proof of absence.

All initial field contracts remain PROPOSED/UNKNOWN and CANDIDATE_ONLY. LEVEL_1/2 can become verified
for reads only after a separate controlled comparison. LEVEL_3 cannot be promoted through that
interface. No remap or version automatically activates anything.

`AscendLoadContextAssembler` is implemented as a guarded interface: values require separate trusted
observations and controlled read-mapping validation, matching current workspace/section fingerprints,
load identity, provenance and freshness. Stale/conflicting/unvalidated fields remain UNKNOWN. Mapping
Mode supplies metadata, not those operational values. No current quote, rate, risk or next action is
invented from field presence. No live/canonical shipment state is changed.

## Exact first owner procedure — not executed here

Choose 3–5 real representative loads locally: Planning/coverage needed, covered Active,
in-transit/delivery, and Ready for Accounting where available. Include 1755 if useful. No other real
IDs/states are inferred. Categories absent from the sample remain untested. Proposed OBSERVE session
owner-x1-mapping-20260911-01 was locally checked unused; every enable checks uniqueness again.

1. Disable any existing board lease, then reload the existing X1 extension to source0.5.0. Reuse
   enrollment and the owner's Ascend session. No re-pair or old panel-detail -03 attempt.

```powershell
Set-Location 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
.\.tools\python\python.exe -m scripts.ascend_x1_runtime disable --owner-executed
$mappingLoadIds = Read-Host 'Enter 3-5 owner-approved Booking load IDs, comma separated'
.\.tools\python\python.exe -m scripts.ascend_x1_mapping enable --owner-executed --mode observe --scope validation --session-id owner-x1-mapping-20260911-01 --load-ids $mappingLoadIds --minutes 20 --max-captures 60 --max-workspace-captures 15 --max-section-observations 40 --max-contract-observations 2000
```

2. For unknown structure, manually visit/capture the intended sections, including a captured return
   to the starting section. X1's Capture current workspace section button captures metadata only.
   At least one observed DYNAMIC_SECTION_CHANGE into each proposed target is needed for navigation
   review. Capture the same section across representative loads to compare optional/conditional
   structure. Do not invoke Save/Submit, rates/status/assignment, notes, uploads or communications.
3. Disable and review the sanitized report. It exposes navigation_review_candidates and their source
   map versions; candidates remain proposals. Select only controls actually proven to navigate without
   mutation. An absent/ineligible control stays unknown; do not force it into the reviewed list.

```powershell
.\.tools\python\python.exe -m scripts.ascend_x1_mapping disable --owner-executed
.\.tools\python\python.exe -m scripts.ascend_x1_mapping report --owner-executed --session-id owner-x1-mapping-20260911-01
$mappingSections = Read-Host 'Enter only observed and reviewed read-only section names, comma separated, including the starting section'
.\.tools\python\python.exe -m scripts.ascend_x1_mapping approve-navigation --owner-executed --session-id owner-x1-mapping-20260911-01 --sections $mappingSections
```

This is a future explicit owner review command, not an automatically inferred approval. It validates
observed selected-section relationships and versioned provider fingerprints. No selectors/scripts are
accepted. A useful target set, only if actually observed/verified, is Load Basics, Customer Info,
Carrier / Asset Info, Edit Stops, Dispatch and Tracking, Load Documents and Load Log.

4. Once reviewed controls exist, enable a distinct first AUTO_MAP cohort session. This prepared session
   ID is not created here; uniqueness is checked at enable. Use the same representative cohort.

```powershell
.\.tools\python\python.exe -m scripts.ascend_x1_mapping enable --owner-executed --mode auto-map --scope validation --session-id owner-x1-mapping-auto-cohort-20260911-01 --load-ids $mappingLoadIds --minutes 20 --max-captures 60 --max-workspace-captures 15 --max-section-observations 40 --max-contract-observations 2000
```

5. Owner opens each cohort load once. Press **Map current load** in X1; the popup closes so Ascend has
   foreground focus. Alternatively queue `capture --owner-executed` locally and return focus to Ascend
   for the next scheduler wake. X1 traverses verified sections and returns to the start. The owner does
   not click each section during AUTO_MAP. Keep the load unchanged while the cycle runs. Stop on a safe
   failure code. Verify a completed/returned cycle for every approved load.
6. Disable and review AUTO_MAP receipts, privacy, cross-load structures and versions. Only after owner
   confirmation of a successful controlled cohort should normal AUTO_MAP be unlocked:

```powershell
.\.tools\python\python.exe -m scripts.ascend_x1_mapping disable --owner-executed
.\.tools\python\python.exe -m scripts.ascend_x1_mapping report --owner-executed --session-id owner-x1-mapping-auto-cohort-20260911-01
.\.tools\python\python.exe -m scripts.ascend_x1_mapping record-validation --owner-executed --session-id owner-x1-mapping-auto-cohort-20260911-01 --owner-confirms-controlled-validation
```

Qualification requires all 3–5 approved IDs, independently captured sections/transition evidence,
section comparison across at least three loads, and successful AUTO_MAP return cycles on the entire
cohort. It does not activate operational fields or writes. Unknown optionality/areas remain unknown.

## Normal use after controlled AUTO_MAP validation

Use an unused session ID at execution time; the following normal ID is an example only:

```powershell
.\.tools\python\python.exe -m scripts.ascend_x1_mapping enable --owner-executed --mode auto-map --scope normal --session-id owner-x1-mapping-auto-normal-20260911-01 --minutes 20
```

No load-ID list is required. Owner opens a load and X1 automatically maps its verified sections.
Opening another load creates a fresh independently verified workspace boundary. Unknown or drifted
navigation stops AUTO_MAP; an owner-enabled OBSERVE lease can learn that structure without automatic
traversal. Use `--mode observe --scope normal` for passive learning with the same bounds and no required
ID list. Optional `--load-ids` can narrow either normal mode. Never renew automatically after expiry.
Use `disable --owner-executed` when finished; `status --owner-executed` is local-only. Enabling preserves
an intentional pause. A future bulk audit worker is a separate ActionPolicy scope, not either mode.

## Operational boards and next milestones

Separate prepared Planning Loads, Active Loads and Ready for Accounting Loads view contracts do not
replace the proven Active Loads reader. Planning + Active as the operational universe and Accounting
as post-delivery remain OWNER_ATTESTED_HYPOTHESIS. Later provider-verified cross-view observations
should model lifecycle transitions rather than assume a missing row means a disappeared load.

Next: OBSERVE unknown navigation, review its provider contracts, validate AUTO_MAP across the controlled
cohort, then validate selected
LEVEL_1/2 read mappings and context assembly. The product target is concise answers to what is happening,
responsibility, stops/times, missing evidence, risk, changes and next steps within about 5–10 seconds,
without reproducing Ascend or requiring all tabs. That needs separately authorized section coverage,
fresh field reads and operational rules; it is not delivered by metadata mapping alone.

No debugger/webRequest or network inspection permission is added. A future optional observation plan
may identify a specific owner-opened section apparently loading structured data, define exact read-only
capture scope/redaction/retention and seek separate authorization. Observing an XHR never authorizes
direct requests, undocumented endpoint calls or writes. Any future audit worker intentionally opening
loads/sections needs a distinct ActionPolicy scope; it is not implemented here.

## Offline verification

Fixtures cover header/breadcrumb/workspace identity, conflicting IDs, child inheritance, section and
load changes, drift, field metadata, optionality comparisons, append-only versions, unknown/private
labels, no input-value access, context freshness/validation, cohort versus normal grants, no-ID normal
capture, owner foreground scope, NO-OP, bounds, revoke/pause/expiry, signed capture queue and private
content hints/teardown. Existing board, controller, lifecycle, API and WebBridge regressions remain
part of the targeted checks. Synthetic Edge pages are completely fulfilled locally under TestRuns;
they never use the installed Ascend profile or reach the vendor. Fixtures are not production evidence.

AUTO_MAP fixtures also cover reviewed-control gating, exact-load traversal/return, cohort qualification,
no permanent ID list, pre-click revoke/session/identity/control gates, post-click identity changes,
rejected submit controls/arbitrary selectors, and no further transition after failure.

Verification result: 220 targeted offline tests passed; final affected reruns also passed (latest: 32 cases). Ruff and all packaged JavaScript syntax checks passed. Two existing Starlette/httpx/anyio
deprecation warnings remain. No fixture result promotes a vendor capability.

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

