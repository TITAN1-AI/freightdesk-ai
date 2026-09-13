# POC #002 — LIVE OPERATIONS

## Current operational-source decision — Active Loads only

For service date 2026-09-11, **Active Loads** is the sole operational population. The owner has
attested 8 pickup events and 3 delivery events for the next validation run. The reader records
`observed_at`, source view, visible board row count, service date and an immutable evidence hash.
Only an exact 8/3 Active Loads result is `OPS_BOARD_RECONCILED`; any different result is
`OPS_BOARD_MISMATCH` and stops before CarrierView, tracking, communications or canonical mutation.
The queues count Pick Date and Drop Date independently, so a same-day load occurs once in each relevant
queue. A repeated load within either queue fails closed. `All Loads` is optional read-only audit only:
its extra service-date records are reported as `NON_ACTIVE_SERVICE_DATE_RECORDS` and never join the
operational manifest. A later action must compare a fresh reread's evidence hash before proceeding.

This is the active priority over historical 1752 browser validation. Owner reports load 1760 delivered,
approximately eight pickups and three deliveries tomorrow. Those are OWNER_ATTESTED workload expectations,
not discovered provider facts. No load numbers beyond the owner's 1760 report are invented. No live read
or write was performed while implementing this plan; the operating date and real queues remain pending.

## First live boundary — owner executes the same-process command

```powershell
Set-Location 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
.\.tools\python\python.exe -m scripts.ascend_browser login-discover-ops --owner-authorized --owner-attested-booking-logistics --origin https://ascendtms.com --service-date 2026-09-11 --board-date-format US --attempt-id owner-active-loads-20260911-01
```

The command asks for an explicit YYYY-MM-DD operating date and owner-confirmed board date format
(ISO for YYYY-MM-DD or US for MM/DD/YYYY). Unconfirmed numeric-date locale is not inferred. Do not use the old 1752 command for this
workload. If an old helper is still waiting for Enter, stop that old helper instead of continuing its
historical read. The new command opens the existing local Python Playwright/headed Edge msedge profile
at C:\FreightDeskRuntime\Browser\booking-logistics\ascend. Owner logs in, confirms Booking Logistics and
presses Enter. Normal app networking/service workers remain allowed. The exact page/context stays open
through bounded discovery. No Computer Use/cloud/alternate profile or cookie/network-body inspection.

The dated grant is one-use, maximum 500 visible board rows and 30 selected identities, with a 15-minute
read period after owner confirmation. It reads recognized visible load/date columns, selects only exact
date matches, and opens only those observed load numbers using fixed read controls. No default historical
load is selected. Unparsed dates are counted and reported; duplicate/conflicting identities stop.
The initial implementation reports VISIBLE_BOARD_ONLY coverage. Pagination, hidden filters and unseen
loads are not assumed complete: a count matching 8/3 is not proof of full board coverage. Report discrepancies
and review the owner board if scope is incomplete. There is no arbitrary page/API crawling or guessed filter.

Detail identity must match the selected Booking reference. Recognized fields/approved read-only tabs are
read and reread; duplicate/conflicting field mappings remain unverified. Facts include available customer,
status, origin/destination, appointments, equipment, carrier, dispatcher, driver/phone, truck/trailer and
tracking/truck-status fields. Notes are presence-only. Complete stop data requires explicit provider stop
count and company/address/windows; preserve ordered verified additional-stop groups. Unknown zones remain
unknown; the owner operating date never supplies a stop timezone. Unobserved phone is NEEDS_REVIEW, not a
claim that the provider has no driver phone. No Save/Submit/assignment/status/rate/note/document/email action.

## Manifest and private evidence

Runtime root: C:\FreightDeskRuntime\Data\booking-logistics\operations.

- operations.sqlite3: separate provider candidates, read grants, tracking evidence, derived manifests and
  proposal-only action ledger. No canonical shipment records are created or changed.
- owner-live-ops-001-manifest.json: sanitized PICKUP_TRACKING_QUEUE and DELIVERY_WATCH_QUEUE.
- owner-live-ops-001-owner-report.md: owner-readable queue/watch tables, timestamps, missing data and next actions.
- Planning record poc-002-plan.json has pending/null queues, not fabricated operational rows.

Pickup classifications: READY_FOR_TRACKING, ALREADY_TRACKING, MISSING_DRIVER_PHONE,
MISSING_REQUIRED_STOP_DATA or NEEDS_REVIEW. Readiness requires exact identity, recent verified Ascend
facts, usable E.164 phone, complete verified ordered stops/windows and fresh verified tracking absence.
Existing or duplicate CarrierView loads always block creation. Malformed/unknown phones are review items.

Delivery classifications use only established, fresh provider semantics. Unverified semantics or old
snapshots remain UNKNOWN; expose raw Ascend status and known provider flags separately. Do not invent ETA,
EN_ROUTE_DELIVERY, POD_PENDING or a healthy NO ACTION conclusion from missing data. Delivered state does
not establish POD absence. The stale threshold is a FreightDesk rule (60 minutes), not a provider fact.
No monitoring scheduler or outbound communication is activated by the watch list.

## Subsequent bounded CarrierView tenant reconciliation

After inspecting the actual Ascend manifest, the prepared owner-executed read helper is:

```powershell
.\scripts\with-carrierview-token.ps1 -ScriptPath '.\scripts\reconcile_live_ops.py' -CredentialClass tenant
```

Enter the exact manifest ID locally. This uses Booking Logistics' tenant service credential, never agent
fallback, actor FreightDesk/Avery and the recorded manager/admin eligibility reason. Exactly one profile
GET, one active-list GET, one past-list GET, then at most one exact-load GET per unique discovered matching
provider ID (maximum 33 GETs). No per-load request for unrelated list records. Bound response bytes/count;
identity/scope/rate/network failure stops without retry. No raw list, phones, URLs or tokens are printed.
No POST/PATCH/PUT, position polling loop or vendor write is enabled.

The list pagination/negative-existence contract remains unverified. A miss is NOT_FOUND_IN_BOUNDED_READ,
not ABSENT_VERIFIED. Therefore it cannot alone make a pickup READY_FOR_TRACKING. Duplicates, old snapshots
and missing semantics are review items. Raw Boolean route/delivery flags and timestamp availability are
stored separately from any operational classification. Historical replay does not validate every live
status interpretation. Do not force pilot selection if evidence is insufficient.

## Tracking proposal and first-write approval plan

For genuinely READY_FOR_TRACKING candidates, prepare the typed native CarrierView payload and durable
payload hash. Preserve all verified stops. No emails/dispatchers communication fields are added. The
proposal ledger has no dispatch method; proposals are AWAITING_OWNER_REVIEW with attempts=0. Repeated
identical proposals are idempotent; changed payloads require reconciliation. Prefer a unique complete
two-stop shipment as the pilot; if none qualifies, proposed_pilot remains null.

Two contract issues still require review before an actionable authorization request: stop-company wire
mapping is not established by the existing CreateLocation schema, and load-creation SMS/welcome/tracking
effects are not documented/verified here. Never guess a company JSON key or assume creation is silent.
The proposed payload contains only existing schema fields; required company facts remain in private stop
evidence with an explicit unresolved mapping. pilot_authorization_ready remains false until resolved.

Return the actual two queues, discrepancies/missing facts, provider-ID/existence reconciliation, one
candidate (if any), exact private payload and payload hash, company mapping and documented side effects
to the owner. The exact future action needing separate authorization is ONE POST /api/loads for that
named load and unchanged hash, including explicit approval of any unavoidable communication effect.
Current production transport remains independently blocked; no generic write permission is granted.

After a separately authorized implementation/execution: claim once durably, send once, then GET/read back
and verify Booking load ID, driver, every stop/window, provider/tracking identity and no duplicate. Keep
signed tracking URLs private. Ambiguous network outcome is UNCERTAIN; never resend. Read back/reconcile
before reporting success. Stop after the pilot and obtain separate owner approval for the remaining
READY_FOR_TRACKING batch. No Ascend/pricing/canonical/communication mutation is implied by this plan.

## Capability status

IMPLEMENTED/TESTED are software states. Actual tomorrow discovery, operational classifications,
tracking-creation payloads and pilot creation are not LIVE_VALIDATED until separately observed.
Existing historical POC #001 and M3/M4A evidence remain unchanged. Bootstrap -02 remains reserved.
Offline validation: full suite 352 passed, Ruff/JavaScript/dashboard checks pass, with two existing
dependency warnings. Focused date/operations regressions also pass; fixtures are not live vendor proof.
