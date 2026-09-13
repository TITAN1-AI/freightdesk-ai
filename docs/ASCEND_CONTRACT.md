# AscendTMS adapter contract — M4B offline

LATEST: observed owner-table-schema-001 v1 contract is now used by ops_board.py/ops_board.js.
Full named 33-column schema is validated; unsupported indexes 19/23 stay unused. Load ID=0,
Load Status=1, Pick Date=5, Drop Date=7. Unique visible data grid required, zero-row clones rejected.
Only requested same-row fields are extracted for date matches. Board-only queues do not require or
prove detail fields. See ASCEND_ALL_LOADS_TABLE.md; earlier unobserved-contract claims are historical.

AscendAllLoadsTableContract v1 is implemented as a separate observed schema proposal; see
ASCEND_ALL_LOADS_TABLE.md. It does not activate/replace the existing ops parser. Actual live headers
remain unobserved; same-process board access succeeded but owner-live-ops-001 stopped on schema.

## POC002 date-scoped identity grant

The read executor can bind an exact target only from a discovered/authorized identity set; it cannot
substitute arbitrary references. A one-use OpsReadGrant binds owner operating date, explicit ISO/US board
format and 500-row/30-candidate bounds. Initial coverage is visible board only, not a complete account
search. Exact detail and list dates must reconcile. The reader may inspect approved sections, but never
edit forms. Company/driver/contact facts remain private; notes are presence only. Numbered verified
stop groups plus explicit stop count preserve sequence/completeness; no timezone conversion inferred.
POC002 provider facts/queues/proposals are in a separate runtime operations store, never canonical state.

## Current action boundary and observed contract bootstrap

For the owner-executed same-process run, normal application networking/service workers are allowed.
The write boundary is FreightDesk's executor/action surface, not HTTP verbs/origins of app requests.
ReadOnly1752Executor exposes bounded navigation, fixed exact-load search/open, section inspection and
DOM reads only. It has no generic action dispatcher or caller-provided scripts/clicks/submits. URLs,
buttons and semantic tabs are checked before intentional actions; unknown/ambiguous targets stop.
Production mutation interfaces remain blocked independently. Model output and page content are data.

AscendFieldContract records provider=AscendTMS, source=live browser DOM, validation_load=1752, observed_at,
version, observed field metadata/selector proposals and per-candidate reconciliation. It is distinct
from the older verified BrowserContract and is not auto-promoted to it. New same-process reads do not
require the old file. Candidates originate from observed exact field labels; values are read only after
the opened detail's load-number gate, then compared in memory with known history/CV values. Reconciled
label/value mappings are scoped RECONCILED_FOR_1752, not universal semantic proof. Conflicting/missing
evidence, duplicate candidates and unknown labels remain UNKNOWN. No timezone or financial assumptions.
Raw candidate values never appear in the persisted contract; unknown labels and identifier values are
not leaked. Metadata includes control type, presence booleans and unique observed label selectors.
Read failures never authorize a write/retry; incomplete discovery must not be called full field coverage.

## Same-process interactive read / continuity separation

login-validate-1752 launches the existing headed session, awaits owner login and tenant confirmation,
then verifies the same deterministic session gate in that exact page/context. The read service accepts
an explicitly paired existing_browser/existing_page, rejects mismatched contexts and never launches or
closes the supplied context. Its outer owner-interactive wrapper closes after the bounded outcome.
Adapter use_current_session skips the account-root navigation but still verifies account/session before
target navigation and after extraction. No identity gate is weakened. One-use grants, pause/policy,
expiry, exact 1752, verified field contract and snapshot rereads remain mandatory. -02 is reserved.

Cross-process persistence is not a prerequisite for this read. Same-process reports explicitly leave
persistent_cross_process_session_reuse false even on a complete read/reconciliation. No provider account
identity is derived from owner attestation. Actual live field selectors are still pending; no synthetic
write/session/read test is provider evidence. Same-process orchestration does not invent missing selectors.

diagnose-continuity is separate: manual authenticated baseline -> close -> one reopen -> aggregate
comparison plus passive resource/error counts. It cannot consume read grants or open 1752. It keeps
cookie/storage names/values, HTML, error text, response bodies and API payloads out of persisted data.
Count changes are observations, not causal proof. A diagnostic cannot relax read-only routing.

## Structural diagnostic contract

diagnose-session is an independent root-only DOM observer, not a read grant or replacement load reader.
It waits 0.5 seconds before inspecting, polls at bounded intervals for up to 15 seconds, and examines
all Playwright frames. It returns structural booleans/counts and allowlisted paths/titles only. Unreadable
frames or login forms in any frame prevent a positive recommendation. Positive evidence requires
approved navigation in a same-origin frame (Dashboard + Loads + two other labels), or a /loads anchor
plus three customer/carrier/locations/accounting route categories. This route classification is structural
evidence only: no matching link is followed and no guessed route becomes a navigable provider contract.
Two consecutive positive samples are required; root anchors alone never qualify. Foreign/inherited
frame document origin is evaluated structurally without logging URLs. No traffic/HTML/text is retained.
The recommendation does not automatically weaken the established exact-load session gate or promote
LIVE_VALIDATED. No attempt ID is accepted and no load validation ledger is opened by this command.

## Customer Zero owner-attested exception — 2026-09-10

The owner explicitly authorizes tenant_identity=Booking Logistics, tenant_identity_source=OWNER_ATTESTED
for only the existing local msedge profile and exact load 1752 at https://ascendtms.com. This is not
provider-derived account verification. BrowserContract retains PROVIDER_DOM as its default strict branch;
the explicit OWNER_ATTESTED branch requires owner_attested_booking_logistics=true, expected_company
Booking Logistics and an empty expected_account. Company/account selectors may be absent in this branch.
It independently checks authenticated navigation before/after reads, and never fabricates an account hash
or proves provider account/session reuse by comparing an owner-attested name. Observations carry separate
tenant_identity_source, tenant_identity, session_authenticated and provider_tenant_identity_verified.

Authentication requires verified same origin, no login path/form and four approved visible nav controls,
including Dashboard and Loads, in one same-origin frame. No literal company text is required. Unrelated
frames cannot supply the missing navigation controls. The title/absence of login alone cannot pass.
The five-field diagnostic is allowlisted and separate from tenant attestation and shipment observations.
The bootstrap consumes one attempt before launch, checks policy/pause and existing exact historical/CV
identity evidence, then may navigate only to the owner-established /loads. Unknown load selectors remain
unverified. The downstream verified field contract, exact-load checks, grant expiry, snapshot rereads,
source/derived reconciliation and independent mutation blocks still apply. This exception does not grant
production writes or widen tenant/load scope. Older strict provider-account language below describes the
PROVIDER_DOM branch; it must not be imposed on the expressly authorized bootstrap branch.

Ascend is replaceable. Canonical state, identity, policy, approval, scheduling and audit remain owned
by FreightDesk. Integration preference is an official supported operation-specific API if independently
verified, otherwise deterministic DOM automation, otherwise separately supervised visual fallback.
No supported general customer CRUD API or production DOM contract was established during this phase.

## Separation of responsibilities

* `integrations/ascend/models.py`: typed contract, exact-load grant, source facts and observation.
* `integrations/ascend/adapter.py`: AscendAdapter interface and deterministic AscendBrowserAdapter;
  all Ascend field/identity/operation semantics live here. Read observations are not Shipments.
* `executors/playwright/browser.py`: DOM primitives and isolated persistent session lifecycle.
* `app/services/ascend_live.py`: consume one-load grant, isolated read/audit store, local evidence
  loading and sanitized protected projection. No scheduler job or canonical mutation is created.
* `app/services/ascend_reconciliation.py`: explicit derived per-field/source comparisons only.
* `app/services/ascend_actions.py`: policy, bound owner approval, content/version checks, durable
  single-attempt claim and post-verification foundation. Only a fixture transport can execute.

Selectors must come from authorized UI observation: accessible role/name, label, stable test ID or
reviewed CSS. A locator must be unique; an ambiguous primary selector fails rather than silently
trying a different element. Fallback alternatives are bounded to three. Required account/ready/load
anchors fail closed; optional/unmapped fields stay missing/unavailable. No coordinate clicking, blanket
DOM scrape, screenshot-driven control, credentials in contracts or unreviewed DOM-derived instructions.
Live contracts must independently bind account-level company and account identity, origin and exact
load URL. A customer name inside a load is not account identity evidence.

## Read semantics

Raw source text remains private and unchanged. Normalized text trims only for comparison; numeric
parsing is Decimal and rejects unexplained units/format. MC/DOT remain strings. Appointments keep raw
local text and unknown timezone; no conversion or appointment window is fabricated. Currency is not
inferred from historical confirmation or a dollar sign. Expenses are not carrier pay. All fields have
source page (without query/fragment), section, observation timestamp and availability state.

Whole mapped snapshots are reread to detect changes. Content fingerprints are not provider ETags and
cannot prove database-level atomicity. Before any future write, an operation-specific provider state
check and verified DOM/postcondition contract are still required. Raw text comparison can report a
difference without proving a semantic or timezone discrepancy. Disagreements are never auto-resolved.

Audit names provider AscendTMS, actor FreightDesk/Avery and session class Avery operational browser
session. Raw HTML, driver phone, notes, cookies, passwords, tokens and browser error text are excluded
from logs. No automatic screenshot, tracing, download or browser recovery occurs. Failed reads consume
their grant and require a newly authorized attempt; failed writes remain UNCERTAIN when side effects
cannot be excluded. A reload is not a safe write retry.

## Logical write surface and policy

| Interface | Policy key | Initial policy |
|---|---|---|
| read_load | read_ascend | ALLOW, plus bounded owner execution grant |
| create_load | create_load | APPROVAL_REQUIRED |
| update_load | update_load | APPROVAL_REQUIRED |
| assign_carrier | assign_carrier | APPROVAL_REQUIRED |
| update_driver_info / update_truck_trailer | update_driver | APPROVAL_REQUIRED |
| update_pickup_eta / update_delivery_eta / add_note | update_load | APPROVAL_REQUIRED |
| update_status | update_status | APPROVAL_REQUIRED |
| update_rates | update_rates | APPROVAL_REQUIRED; owner-controlled even under ALLOW override |
| upload_document | upload_document | APPROVAL_REQUIRED |

Initial rates and creation are intentionally separate: create payload cannot contain pricing. Ordinary
load updates cannot smuggle rates or arbitrary fields. Document intents reference reviewed stored
evidence/hash, never arbitrary browser filesystem commands. Any real upload execution still requires
a verified document resolver/scanner and screen-specific contract. Assignment never establishes carrier
vetting by itself. Per-action approval binds ID/load/version/payload digest, owner identity and expiry.
Fixture ALLOW requires no click except rates; no policy can lift the independent production write block.

Write sequence: trusted tenant/account -> exact load (or verified absence/idempotency reference for
future create) -> reread -> expected state -> policy -> pause/takeover -> payload -> durable claim ->
one mutation -> reread -> exact intended postcondition -> audit. Production create absence checks,
operation-specific screens and provider idempotency are NOT implemented/verified. All real write
methods stay blocked until a separately authorized operation can satisfy the entire sequence.

## Future Outlook tender workflow — disabled

```mermaid
flowchart LR
  Email[Outlook customer email] --> Candidate[CUSTOMER_LOAD_TENDER candidate]
  Candidate --> Facts[Structured facts with source evidence]
  Facts --> Review[Identity, evidence and owner review gates]
  Review --> Tender[FreightDesk canonical tender]
  Tender --> Policy[ActionPolicy and bound approval]
  Policy --> Ascend[Ascend create_load adapter]
  Ascend --> Verify[Reread provider and verify identity/result]
  Verify --> Created[LOAD_CREATED]
  Created --> Ready[READY_TO_COVER]
```

Candidate fields are untrusted proposals. Owner review reconciles sender/customer, reference, stops,
appointment zones, equipment, commodity, weight and current pricing. Historical customer/lane/facility/
equipment/rate context is read-only advisory evidence; it cannot populate or approve current pricing.
Only a verified create result with provider binding can emit LOAD_CREATED; uncertain results enter
reconciliation and cannot emit READY_TO_COVER. No Outlook event, parser output or historical profile
currently triggers canonical tender creation, Ascend writes or mail sends. M3 send guards remain intact.

## Future BOOK IT workflow — disabled

BOOK IT -> selected carrier -> BrokerCarrier adapter verification -> FreightDesk carrier approval
gate -> Ascend assign_carrier -> gather verified dispatcher/driver information -> Ascend driver/truck/
trailer update -> CarrierView adapter create/initiate -> verified tracking gate -> RC workflow.

Ascend never embeds BrokerCarrier or Quo logic. Each vendor keeps its own adapter, explicit operation
authorization, evidence, uncertain-action ledger and failure semantics. RC and tracking readiness are
FreightDesk gates, not side effects inferred from an Ascend assignment. No future workflow is scheduled
or autonomously enabled by this foundation.

See ASCEND_ACCESS.md for exact first-boundary commands and capability-specific live criteria.
