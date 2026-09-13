# LIVE POC #001 — Historical Production Replay

## 2026-09-12: scoped X1 Load 1763 / Load Basics metadata capture — LIVE_VALIDATED

Actual agent-executed bounded iteration 5, corroborated by signed runtime receipts and causal
handshake, proves only the following exact scope. Tenant identity remains OWNER_ATTESTED
Booking Logistics; load identity is provider DOM evidence.

| Capability | Result / evidence boundary |
| --- | --- |
| Session/readiness → capture dispatch → ACK | LIVE_VALIDATED for this exact job, matching tab/document/generation/lease/runtime/process. |
| Provider LOAD/1763 workspace proof | LIVE_VALIDATED before and after this capture. |
| Load Basics metadata-only candidate persistence | LIVE_VALIDATED: exactly one map, version 1, 19 candidate fields, values_included=false, production_writes=false. |
| Job-owned authority cleanup | LIVE_VALIDATED: revoked 16:40:33.946733 UTC, cleanup COMPLETE, no later read receipt for this lease. |
| General Mapping Mode / other loads or sections | NOT LIVE_VALIDATED by this run. |
| AUTO_MAP / navigation controls / operational field meanings or values | NOT LIVE_VALIDATED. |

Map receipt: 2026-09-12 16:40:33.931617 UTC; DOM capture 188 ms. Actual worker/content 0.6.2,
controller 3, content protocol 3, native 1, causal trace 1 and workspace reader 2 were observed.
Coverage: CURRENT_VISIBLE_SECTION_ONLY. Contract activation remains CANDIDATE_ONLY and its
stored live_validated flag remains false: successful metadata capture does not validate field
semantics. No operational values, writes, communications, other vendors or canonical mutations.

All five authorized debugging iterations are used; live execution stopped. OWNER_REVIEW_REQUIRED
is retained for a separate navigation milestone with no active authority. Historical
DOCUMENT_CHANGED did not recur; its exact old cause remains unknown. Sanitized receipts and
agent-causal-debug-20260912-final.json remain under the approved ascend-native runtime directory.
See docs/ASCEND_X1_SESSION_CAUSAL_DEBUG.md. Earlier milestone statements below are historical.

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


## 2026-09-11: bounded persistent-runtime evidence update

LIVE_VALIDATED, limited to observed scope: owner-confirmed durable enrollment/reconnect after
Edge/session restart; local extension/native runtime execution; authenticated Ascend session
reads; automatic binding of one eligible tab in the captured root-path cycle. Session receipts
are provider/browser evidence; Booking Logistics tenant identity remains OWNER_ATTESTED.

NOT LIVE_VALIDATED: independent Active Loads proof in this persistent cycle, scheduled board
read/recurrence/no-op, proposal refresh, content-script recovery/version 0.3.1 compatibility,
operational detail field extraction, or any mutation. Navigation stopped READ_TIMEOUT with zero
board syncs/proposals. Existing owner-reported /loads visibility does not replace view-contract
proof. No live action was executed by this coding task. Earlier implementation-only entries below
are historical. See docs/ASCEND_X1_TAB_LIFECYCLE.md.


## 2026-09-11: persistent X1 runtime implementation is not live evidence

Owner confirms the existing live local installation, exact extension pinning, registration/native
startup/framing, verified pairing and selection of the Ascend /loads tab. Those bounded observations
remain distinct from provider view/detail proof. Source0.3.0 adds offline-tested durable enrollment,
auto-reconnect, read leases, safe routing/navigation, scheduling/proposals and owner dashboard controls.
No real enrollment, persistent lease, restart validation, automatic board cycle or operational detail
extraction was executed in this task. None of those new capabilities is LIVE_VALIDATED.

The earlier consumed -01 session success / ACTIVE_VIEW_UNVERIFIED stop remains unchanged. Actual
view compatibility and field mappings still need provider evidence; fields remain UNKNOWN. Existing
CarrierView/Microsoft/historical validation is unchanged. No write or canonical mutation capability
is added. See [prepared first persistent-read trial](docs/ASCEND_X1_RUNTIME.md).

## 2026-09-11: observed X1 session success; Active Loads stopped before extraction

Owner-executed owner-x1-identity-1755-20260911-01 has a persisted sanitized session receipt at
17:26:40 UTC: authenticated_app=true, verified extension pairing, one eligible tab at /loads. The
next command at 17:26:58 stopped ACTIVE_VIEW_UNVERIFIED / UNKNOWN. No board counts/reconciliation,
FIND or OPEN were established in this attempt; production_writes=false. This adds the actual bounded
session observation to the earlier fixture-only entry, not provider-derived tenant identity.

| Scope | Evidence status |
|---|---|
| Local pairing transport | Existing LIVE_VALIDATED owner evidence retained; runtime pairing expiry is separate |
| X1 selected-tab routing and authenticated app for this one session | Observed owner-run result plus sanitized local session receipt |
| Independent selected board-view identity | NOT LIVE_VALIDATED; failed first test did not save view candidates |
| X1 8/3 board reconciliation, 1755 row/detail identity | NOT LIVE_VALIDATED; not reached in this test |
| Provider-derived Booking Logistics tenant identity | NOT LIVE_VALIDATED; OWNER_ATTESTED |
| Operational extraction and production writes | BLOCKED / NOT LIVE_VALIDATED |

The 0.2.1 view contract has 117 passing targeted offline tests only. No new view/board/detail promotion,
vendor run or fresh grant. See [current stopped handoff](docs/ASCEND_X1_VIEW_CONTRACT.md), which supersedes
the older pending-first-test execution steps below. Existing historical/Microsoft/CarrierView evidence
remains unchanged.

## 2026-09-11: X1 transport LIVE_VALIDATED; identity controller offline only

Owner reports installed FreightDesk Ascend X1 0.1.2 displayed PAIRED / PAIRING_SUCCESS and explicitly
stated that Ascend reads and writes were disabled. Provenance: OWNER_REPORTED production-local observation,
not a new agent-run browser test. Source 0.2.0 has a prepared identity-only controller; no live read run here.

| Capability | Result | Evidence/source |
|---|---|---|
| Local Edge extension ↔ Native Messaging ↔ FreightDesk host pairing transport | **LIVE_VALIDATED** | Owner's 0.1.2 PAIRED / PAIRING_SUCCESS observation |
| X1 eligible-tab routing and authenticated-session receipt | NOT LIVE_VALIDATED | Implemented; offline API/DOM fixtures only |
| X1 Active Loads exact 8-pickup / 3-delivery reconciliation | NOT LIVE_VALIDATED | Implemented; offline case oracle/board fixtures only |
| X1 exact provider row 1755 discovery | NOT LIVE_VALIDATED | Implemented; offline fixtures only |
| X1 provider-backed detail identity receipt for 1755 | NOT LIVE_VALIDATED | Three allowed strategies tested offline only |
| Booking Logistics provider-derived tenant identity | NOT LIVE_VALIDATED | Tenant remains OWNER_ATTESTED |
| X1 operational detail/stops/assignment extraction | BLOCKED / NOT LIVE_VALIDATED | No current release, including after identity success |
| Ascend writes / autonomous execution | BLOCKED / NOT LIVE_VALIDATED | No authorization or executor route |

This matrix changes only X1 local transport validation; existing scoped historical/Microsoft/board
evidence below remains unchanged. No new CarrierView/Outlook or canonical mutation. Follow
[the prepared owner read-only steps](docs/ASCEND_X1_READONLY.md), stopping before live execution here.
The previous reachability/pairing-pending entries below record earlier state and are superseded.

## X1 local reachability reported; pairing and vendor capabilities unvalidated

Owner reports extension 0.1.1 installed/enabled, ID pinned, registration successful and native host
reachable after restart. Bootstrap import has not reached PAIRED. 0.1.2 diagnostics are offline-tested
only; no real pairing or vendor run occurred here. No new vendor LIVE_VALIDATED capability or grant.

## 2026-09-11: owner-installed extension; no extension vendor validation

Owner reports X1 Offline Prototype 0.1.0 installed/enabled in Edge with no manifest errors, native
host unregistered and production connection disabled. This is OWNER_REPORTED local installation
evidence only. Source 0.1.1 native foundation has offline tests; no real registration/pairing or
Ascend extension interaction occurred here. Native pairing, extension session/board reads, provider
detail identity, operational extraction and writes are all NOT LIVE_VALIDATED. No new attempt/grant.
Prior scoped provider evidence is unchanged; tenant identity remains OWNER_ATTESTED.

## Final identity pivot — no detail capability validated

Local final ledger confirms consumed owner-ascend-final-identity-1755-20260911-01 stopped at
TARGETED_BOUND_EXCEEDED / targeted_causal_bound_exceeded: board_tables measured 9, maximum 8.
Pivot required; no production writes, opener record or identity contract. Playwright detail-identity
experiments are closed. Extension X1 is an offline prototype only: all extension vendor capabilities
remain NOT LIVE_VALIDATED. Prior board/session and CarrierView/Microsoft/history evidence stays scoped
and unchanged. Tenant identity remains OWNER_ATTESTED. See docs/ASCEND_EXECUTOR_PIVOT.md.

## Latest causal diagnostic stop

Consumed owner-ascend-causal-identity-1755-20260911-01 reached BOARD_RECONCILED, then stopped with
causal_scan_bound in pre-click preparation. No opener metadata or bound measurement was persisted.
No detail click or identity contract followed. Exact failing bound is unknown; existing session/board
success is not reclassified as failure. No identity/operational LIVE_VALIDATED promotion. Targeted
refactor is offline-only and live execution is disabled; see docs/ASCEND_TARGETED_IDENTITY.md.

## Latest 1755 identity diagnostic evidence

Owner-executed owner-ascend-detail-identity-1755-20260911-01 reconciled the exact approved Active Loads
scope, opened the selected control and stopped at detail_identity_missing with zero candidate identity
fields. Local ledger confirms consumption and no identity contract. A modal/panel mechanism remains
unproven. Provider detail identity and operational extraction are not LIVE_VALIDATED. Booking Logistics
tenant identity remains OWNER_ATTESTED. No production write occurred. New causal diagnostic is prepared
offline only; no capability is promoted from its fixtures. See docs/ASCEND_CAUSAL_IDENTITY.md.

## Active next milestone: POC #002 — LIVE OPERATIONS

Owner-reported workload: 1760 delivered, ~8 pickups and ~3 deliveries tomorrow. Actual identities/date
and queues are pending owner-executed live discovery. No numbers or provider status are invented.

| POC002 capability | IMPLEMENTED / TESTED | LIVE_VALIDATED |
|---|---|---|
| Same-process dated Ascend board/detail discovery | Yes, bounded partial-coverage reader | No |
| Pickup tracking / delivery watch manifests | Yes, explicit unknown/discrepancy states | No |
| Selected CarrierView tenant GET reconciliation | Yes, bounded and no negative-existence assumption | No new operations proof |
| Payload hashes and durable proposal ledger | Yes, no dispatch/canonical mutation | No |
| One tracking creation pilot and batch release | Approval/readback plan only; execution blocked | No |

Software: 352 offline tests plus lint/JS checks pass; two existing warnings. Existing POC001/M3/M4A live
evidence is unchanged. See docs/POC_002_LIVE_OPERATIONS.md for next command and write boundary.

## Latest M4B offline update — observed field-contract discovery

Normal-network same-process orchestration and fixed-action 1752 discovery are implemented, not live-run.
Observed AscendFieldContract proposals will separate provider DOM metadata from FreightDesk-derived
mapping/reconciliation. UNKNOWN remains explicit; accepted mappings are scoped to 1752. No field values
or reusable schema are invented. Authenticated interactive session, exact read, field reconciliation
and persistent cross-process reuse all remain NOT LIVE_VALIDATED until their respective real evidence.
Booking Logistics remains OWNER_ATTESTED. Existing CarrierView/M3/M4A validation is unchanged.

## M4B interactive session versus persistence — offline update

New same-process owner login + read orchestration and metadata continuity diagnostics are IMPLEMENTED,
not production-run. No additional M4B capability is LIVE_VALIDATED. Track these independently:

| Capability | Current LIVE_VALIDATED state |
|---|---|
| Authenticated interactive Ascend session | No |
| Booking Logistics tenant identity | OWNER_ATTESTED only, not provider verification |
| Exact 1752 discovery/read | No |
| Field extraction/reconciliation | No |
| Persistent cross-process session reuse | No; not a prerequisite for the first three provider capabilities |
| Production mutations | No; independently blocked |

A later same-process success may validate only the provider capabilities actually evidenced by that
run, while cross-process reuse remains NOT LIVE_VALIDATED. No success or persistence is inferred from
offline tests. Owner-bootstrap-1752-20260910-02 is reserved and unconsumed.

## Latest M4B structural diagnostic (2026-09-10)

Separate root-only diagnostic inspected all frames after up to 15 seconds of rendering. It observed
complete document, 8 body children, text length 23, one frame and zero approved navigation/route markers;
no login form. This is diagnostic browser evidence only and does not establish an authenticated session.
Booking Logistics remains OWNER_ATTESTED; provider tenant verification, exact-load read and reconciliation
remain NOT LIVE_VALIDATED. No load validation attempt was consumed; -02 is prohibited pending resolution.
No production writes. Existing CarrierView/M3/M4A validation is unchanged.

## M4B current evidence distinction — 2026-09-10

| Capability / identity claim | LIVE_VALIDATED | Evidence source / outcome |
|---|---|---|
| Ascend authenticated session | No | Local Python/Edge observed /, AscendTMS title, no login form, zero approved nav markers; positive gate failed |
| Booking Logistics tenant identity | OWNER_ATTESTED only | Explicit owner attestation bound to existing dedicated profile; not provider verification |
| Provider-derived Booking Logistics tenant identity | No | No reliable provider account identifier established |
| Exact load 1752 discovery/read | No | Stopped before /loads |
| Ascend field reconciliation | No | No new Ascend fields read; existing history/CarrierView evidence unchanged |
| Production mutations / autonomous execution | No | Independently blocked; none performed |

Attempt owner-bootstrap-1752-20260910-01 at 2026-09-10T11:48:51.125191+00:00 is consumed, not retried.
Runtime evidence is restricted to the five-field diagnostic and separate sanitized attestation/audit.
Owner attestation does not establish provider authentication by itself. Software/synthetic tests are
not vendor evidence. The existing CarrierView historical POC, M3 and M4A matrices below are unchanged.

## Status: owner-reconciled, canonically imported, protected dashboard verified

Owner selected Booking reference 1752 / CarrierView 99616 and explicitly confirmed both
pickup/delivery appointment windows and arrival/departure times against CarrierView UI.
Owner approved historical canonical import. Raw/source evidence and detailed timestamps remain
under C:\FreightDeskRuntime\Data\booking-logistics\historical-1752.

Canonical local record live-poc-001 is historical-only, paused/human-owned and excluded from the
demo scheduler. Provider delivery flags and original timestamps are preserved. FreightDesk-derived
DELIVERED/arrival/risk classifications are separately labeled. No fabricated customer or documents.
Load 1753 is distinct, owner-reported delivered today, and not read/imported.

## Resulting LIVE_VALIDATED matrix

| Capability | LIVE_VALIDATED | Evidence / boundary |
|---|---|---|
| Tenant authentication and company profile | Yes | Successful profile, Booking Logistics LLC match |
| Past-load discovery | Yes | Successful past-filter GET |
| Exact shipment retrieval / identity reconciliation | Yes | Unique selected reference/provider; list/detail identity checks |
| Last-position retrieval | Yes | Exact endpoint success; numeric timestamp units unverified |
| Position-history retrieval | Yes | Page 1 only, 10 of 218 reported positions |
| Historical stop timeline / UI reconciliation | Yes | Owner confirmed appointment, arrival and departure times |
| Canonical historical import | Yes | Hash-bound owner approval, source-preserving import and audit |
| Protected historical dashboard | Yes | Actual imported record rendered; separate session and scoped matrix |
| Real-time monitoring | No | Historical snapshot only |
| Webhook processing | No | Local fixture inbox remains quarantined |
| Tracking creation/initiation | No | Production writes disabled |
| SMS / chat | No | Production sends disabled |
| Live autonomous execution | No | No operational work queued |
| POD | No | No verified POD or established document API |
| Signed RC | No | No verified signed RC |
| Billing readiness | No | Remains unverified |

## Evidence and limitations

- Earlier agent profile attempts returned user_not_found twice. Owner explicitly selected tenant
  as the API service identity; no silent fallback occurred.
- Historical discovery used profile then past list; selected-shipment replay used exactly
  one detail GET, one last-position GET and one positions-history GET.
- A list/detail stop-shape mismatch triggered a guard. Offline IANA-zone mapping resolved UTC
  versus local appointment representation; cached detail was reused without another GET.
- Owner confirmed stop times; no additional CarrierView request was made for canonical import.
- SQL audit records tenant credential class and FreightDesk/Avery for provider operations,
  owner approval/import and protected dashboard verification.
- Both arrivals were within appointment windows. This derived historical assessment does not
  prove real-time tracking health, complete GPS history, document readiness or billing readiness.
- 151 automated tests, Ruff, JS checks and actual protected browser rendering passed.
- No production write, message, webhook registration, tracking creation or autonomous action.
- Real operational labor saved, full workflow reliability and live monitoring latency are not measured.

## POC #002

Planned BOOK IT -> onboarding -> tracking/RC -> pickup/documents -> delivery/POD -> billing.
No validation of that full workflow yet.
# M3 — owner-confirmed bounded production validation

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

Scope: six validated capabilities only. Existing Booking 1752 / CarrierView 99616 historical
capabilities above remain unchanged. This run neither updates that shipment nor validates live
tracking, document gates, billing readiness or autonomous operation. Classification/extraction
accuracy is not established by a processed-message count. An unsent draft does not prove sending,
reply/forward draft variants, or Mail.Send consent. No further Graph networking is authorized.

# M4B — first live boundary; no production validation

Latest 2026-09-09 same-profile test: local Python/msedge/existing approved profile verified, stored
browser files present, but account identity not established. No load read. All six M4B production
capabilities remain NO. 303 software tests pass; profile-file presence is not authenticated reuse.


2026-09-09 live attempt: owner reported login and supplied the official origin/dashboard screenshot.
Controlled account-page navigation occurred, but account identity was not established by the reader.
Stopped before exact-load discovery/read; no reconciliation or writes. All M4B entries below remain
NO. The original offline-only description below is the earlier handoff, not the latest attempt.


Offline implementation and 290-test suite pass, including real headless Edge against synthetic
intercepted pages only. No actual Ascend login/navigation/read/API/write occurred. Dedicated profile
prepared at C:\FreightDeskRuntime\Browser\booking-logistics\ascend; never launched.

| M4B capability | IMPLEMENTED / TESTED | LIVE_VALIDATED |
|---|---|---|
| Account/session identity | Independent company/account checks; mismatch/expiry/redirect tests | NO |
| Exact-load discovery | One-load grant and exact display-number check | NO |
| Live load read | Bounded read foundation and one-use ledger | NO |
| Field extraction | Raw/normalized/section/time evidence; missing/DOM/fallback tests | NO |
| Read-only reconciliation | MATCH / DIFFERENT / UNKNOWN / STALE / UNAVAILABLE tests | NO |
| Browser session reuse | Synthetic persistent-cookie round trip only | NO |
| Creation/edit/assignment/driver/status/rate/document writes | Interfaces blocked in production; fixture ledger tests | NO |
| Customer communication / autonomous browser execution | Disabled | NO |

Only an authorized real run meeting docs/ASCEND_ACCESS.md criteria can change this matrix. A first
read cannot prove session reuse. Existing M2/M3 and M4A capability evidence remains unchanged.

# M4A — owner-approved historical import and intelligence

Source: owner-provided CSV in runtime history inbox, SHA-256
`af7e479a94f44f7f7541e2ecdd725de48e37656f2a0da92085670e16d0886bb0`.
Observed 694 rows / 59 columns / 694 unique Load IDs. Staged typed and independent CSV financial
totals both reconcile: 1,693,484.10 income, 1,378,557.00 total expenses, 314,927.10 gross profit.
All 694 gross-profit and margin-percentage row checks pass; aggregate margin 18.596401%.
No source duplicates or prior conflicts. Owner approved the mapping and USD with all source limitations.
The historical database contains one staged batch / 694 staged rows plus 694 committed
ascend_history_record records. Actual re-import inserted zero rows; record and audit hashes unchanged.
SQLite integrity passed. Generic history_record and canonical/mail/task counts remain zero there.
Batch: `090676423701034e909dc695d1920546c7c410b4697877c799141aebee0a81d4`.
Evidence: private `historical-intelligence.json` and `commit-verification.json` in its runtime report folder.
Calculation timestamp: 2026-09-08T11:43:50.190088+00:00. Counts/financial summaries are derived from
the 694-row source; full pickup coverage 2024-09-03–2026-09-04. Subgroup samples/dates are explicit in JSON.

| M4A capability | IMPLEMENTED / TESTED | LIVE_VALIDATED |
|---|---|---|
| Ascend CSV schema inspection | Actual 59-column source inspected | YES — offline owner export |
| Real historical staging | 694 raw + typed evidence rows | YES — staging only |
| Real financial reconciliation | Decimal source/staged controls and 694 row checks | YES |
| Identical-export staging deduplication | Same source repeated; one batch / 694 rows retained | YES — staged scope only |
| Changed-source version/conflict handling | Synthetic tests | NO — no conflicting real export exercised |
| Real historical commit | 694 source/mapping/owner-bound records; historical store only | YES |
| Identical committed-export re-import | 0 inserts; records and audit unchanged | YES |
| Real CustomerProfile / LaneProfile | 19 exact customers / 110 raw lanes; evidence-backed samples | YES |
| Real CarrierProfile / FacilityProfile | 354 named carriers / 163 exact first/final endpoint identities | YES — raw identities only |
| Real internal RateHistorySummary / financial distributions | USD income, total expenses, gross and margin; per-group provenance | YES — internal history only |
| Raw equipment usage | 14 named labels; 7 missing rows separately scoped | YES — no mapping approval |
| Candidate customer note-topic extraction | 19 bounded deterministic candidates with source offsets/hashes | YES — candidate generation only |
| Approved SOPs / merged aliases / confirmed equipment mappings | Proposals only; none applied | NO |
| Ascend API / browser automation / live reads / writes | Not performed | NO |
| Current market pricing / automatic quoting | Not authorized or inferred | NO |
| Automatic canonical shipment updates | No writes | NO |

This is real exported-data validation, not a live Ascend connection. All statistics carry sample size,
date range, calculation timestamp, source provenance and raw/derived designation. Two missing carrier
identities and seven missing equipment values remain explicit. Unknown zones, one missing delivery
date, raw MC/DOT irregularities and raw-only Exchange Rate Date remain intact. Expenses are not carrier
pay. No vendor writes, quote automation or live canonical mutation. 252 tests, Ruff and JS checks pass.
Prior M2/M3 scope and Microsoft send guards remain unchanged.
# 2026-09-10 POC002 evidence update

Owner reports authenticated All Loads view reached. Local ledger confirms owner-live-ops-001 consumed;
sanitized result STOPPED_OPS_DISCOVERY / ops_board_headers_missing_or_ambiguous is consistent with
passage through session/navigation gates. Booking Logistics identity remains OWNER_ATTESTED.
No table-contract, dated manifest, detail-field or session-reuse validation follows from this result.
New table diagnostic is implemented offline, not live-executed; no additional capability is promoted.
# 2026-09-10 existing production table evidence applied offline

owner-table-schema-001 saved TABLE_STRUCTURE_OBSERVED: 9 candidates; data grid 48 rows/33 headers/33
cells; zero-row header clone; page size 100. Owner supplied column contract identifies Load ID at 0,
Pick Date at 5 and Drop Date at 7. Existing diagnostic has 13 date-matching rows/16 occurrences but null
load IDs. Corrected parser is offline-tested only; no new queue/field/reconciliation LIVE_VALIDATED
claim and no new vendor activity. Booking Logistics tenant identity remains OWNER_ATTESTED.
# 2026-09-11 owner-reconciled Active Loads evidence

Local manifest owner-active-loads-20260911-02 reports OPS_BOARD_RECONCILED, service date 2026-09-11,
12 board rows, 8 pickups and 3 deliveries, matching the owner's independent confirmation. Pickup IDs:
1755,1756,1757,1758,1759,1762,1768,1769. Delivery IDs:1761,1766,1767. No production/canonical writes.
This proves the scoped Active Loads discovery/date-queue reconciliation; pagination completeness,
phone/stop readiness and CarrierView operational states are not promoted. Tenant stays OWNER_ATTESTED.
CarrierView exact-eleven reconciliation is offline-prepared only; no new provider evidence yet.
