# POC002 multi-system owner handoff — offline preparation

LATEST STOP: owner-multi-system-20260911-01 Ascend grant is consumed. Do NOT rerun the commands below
under this run or advance later phases without successful Ascend evidence. No new run is prepared.
The old generic terminal failure saved no root/stage/per-load evidence; exact cause is unrecoverable.
Future instrumentation now appends sanitized multi_progress/multi_failure records under the operations
DB: phase, execution_stage, safe error_code/reason, affected_load_id, completed_load_count and observed
initial_board_reconciled/board_changed booleans. Unknown observations remain null. No private facts or
exception payloads are included. Complete per-load counts do not promote uncommitted phase evidence.
The earlier handoff below is historical and not an instruction to retry a consumed grant.

Run ID: owner-multi-system-20260911-01. Source manifest: owner-active-loads-20260911-02.
Scope: the eight approved Sept 11 pickup IDs and three delivery IDs in that manifest. It is a
target allowlist, not proof of current assignments, contacts, stops or CarrierView coverage.
Owner's 7 covered / 1 uncovered / 3 delivery records oracle is compared only after independent
classification. No per-load answer from the owner's examples is used as operational evidence.

## Owner commands, in order

From C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI:

```powershell
.\.tools\python\python.exe -m scripts.multi_system_ops ascend --owner-authorized
.\scripts\with-carrierview-token.ps1 -CredentialClass tenant -ScriptPath .\scripts\multi_system_carrierview.py
.\.tools\python\python.exe -m scripts.multi_system_ops outlook --owner-authorized
.\.tools\python\python.exe -m scripts.multi_system_ops report --owner-authorized
```

Run the next command only after BOUNDED_READ_COMPLETE. Each vendor phase has a separate one-use
grant; failures do not retry automatically. These commands have NOT been executed during preparation.
The report command is local only and may be repeated; it re-evaluates evidence age without refreshing it.

## Ascend read boundary

Same local Python Playwright, headed Edge msedge and existing persistent profile:
C:\FreightDeskRuntime\Browser\booking-logistics\ascend. Normal application networking; no
Computer Use/cloud/alternate profile, private network-body instrumentation or cookie inspection.
Owner confirms login and presses Enter; keep that same page/context. Navigate /loads then select the
unique semantic Active Loads control. Validate the observed 33-column data grid and exact queue set.
Only the 11 discovered/approved load IDs may be opened; each is opened once from Active Loads.
Inspect supported General/Details/Stops/Pickup/Delivery/Carrier tabs, not Financials; bounded label
reads and rereads preserve unknown/unmapped/conflicting facts. At most 11 detail opens, up to 7
approved section controls per detail, 500 board rows, 250 controls per field scan, 100 stop groups,
and 30 minutes after confirmation. DOM hydration polling is bounded; no action retries.
Reread Active Loads at the end and reject board changes. No stale All Loads facts enter decisions.

Approved fields include identity/status/dates, carrier/MC/assignment indicator, driver/contact,
truck/trailer/status, references and stop company/address/windows. No notes text or financial values
are extracted in this phase. Stop sequence/count/timezones must be explicit; no inferred conversions.
Unknown detail identity stops. Unknown noncritical mappings remain UNKNOWN. Missing fields do not
justify guessed assignments or detail selectors. Local detail evidence stays in runtime operations DB.

## CarrierView budget

Tenant only, FreightDesk/Avery actor and recorded manager/admin eligibility reason. Exact 11 IDs
must match the fresh Ascend detail set (maximum four hours old). GET /api/profile, require Booking
Logistics; GET /api/loads?filter=active; GET /api/loads?filter=future; up to 11 exact /api/loads/{id}
GETs for unique approved matches. **14 GET maximum**, no past query, extra pagination, retries,
redirects, creation, SMS, chat or webhooks. Future filter is owner-supplied contract for this new
prepared scope, not yet LIVE_VALIDATED. Lists max 2,000 records; response max 2MB; timeout 15 seconds.
Unmatched entries are discarded. Duplicate identities require review without exact-detail/creation.
Misses are NOT_FOUND_IN_BOUNDED_SEARCH, not absolute nonexistence. Active/future list membership is
reported as provider evidence, not automatically mapped to route/app semantics. Native carrier_view
is recognized; unknown external types/state mappings stay UNKNOWN. No POD endpoint is invented.

## Outlook gap-only bound

Only pickup loads with positive assignment evidence and missing driver/contact/truck/trailer fields
are eligible. No reads for uncovered/unknown-assignment loads. Use existing delegated session silently;
stop if manual authentication is needed. Verify exact /me mailbox identity first. Current OAuth scopes
remain User.Read + Mail.ReadWrite + MailboxSettings.Read; no Mail.Send or drafts/sends.
One subject:<exact Booking load ID> search per eligible load, maximum eight searches, $top=10, one page,
no conversation expansion/attachments/delta. **Maximum nine Graph GETs / 80 messages**; silent token
refresh may add identity-provider traffic, not Graph/mail reads. No interactive login automatically.
Return only exact labeled Booking/load references with no competing reference, known Ascend dispatcher
email match and received timestamp within 14 days. Missing dispatcher identity prevents acceptance.
Persist only narrow extracted claims with message/conversation IDs and timestamps privately; no raw
body, subject or contact values in the report. Sender match does not prove claim accuracy: claims remain
REVIEW_REQUIRED, never silently replace verified Ascend facts or enable a pilot. If evidence cannot
establish the missing fact safely, queue owner reconciliation instead of expanding mailbox searches.

## Decision and execution boundary

Carrier name alone never proves covered. Positive assignment indicator or carrier MC plus nonempty
carrier/driver/truck/trailer is required by the conservative coverage rule. Explicit unassigned or
verified empty carrier+driver establishes UNCOVERED; missing/ambiguous fields remain UNKNOWN or
ASSIGNMENT_INCOMPLETE. Placeholder values or unrecognized semantics require review, not inference.
Missing contact/stops are distinct from uncovered. Verified Ascend fact age must be <=4 hours;
tracking classification/pilot eligibility requires fresh <=15-minute CarrierView evidence.

READY_FOR_TRACKING means pilot-review eligibility under the owner's bounded-search criterion, NOT
absolute absence or execution authorization. Require exact identity, covered assignment, E164 phone,
complete ordered company/address/aware-window stops and no ambiguity. Existing/duplicate records block
pilot creation. Choose one eligible two-stop load deterministically only after evidence assessment;
otherwise pilot=null. Store any complete payload privately, with per-fact/stop provenance. Production
creation remains disabled pending exact owner approval, explicit bounded-search duplicate risk,
company-field wire mapping and creation communication-side-effect reconciliation. No action dispatcher,
approval bypass, canonical mutation or outbound communication is implemented by this workflow.

After independent states are fixed, compare aggregate counts to the owner oracle. Report
POC_002_MULTI_SYSTEM_RECONCILED only on agreement, else POC_002_RECONCILIATION_MISMATCH. Per-load
unknowns/missing delivery records are identified. A count-only oracle cannot identify which otherwise
evidence-supported load should change; all per-load states remain visible without forced corrections.

## Stop conditions and sanitized schema

Stop the phase on consumed grant, policy/pause/takeover, expiry, scope/date/identity mismatch, wrong
mailbox/company, ambiguous view/grid, schema drift, changing board, unknown detail identity, unauthorized
control, auth failure, timeout, rate limit, malformed/oversized response or provider identity conflict.
No retry or credential fallback. STOPPED_MULTI_SYSTEM includes fixed error_code, phase and safe reason.

Runtime report: Data\booking-logistics\operations\owner-multi-system-20260911-01-report.json.
Fields: run_id, status, calculated_at, observed counts, owner_validation_oracle, loads[], pilot_load_id,
pilot_summary/provenance, pilot_missing_facts, approval_required, creation_execution_enabled=false.
Each load: load_id, queue, operational_state, carrier_coverage, fact_presence, missing_required_facts,
missing_fact_sources, carrierview_result/provider_ids/list_filters/integration_kind/provider_flags,
last_position_available/age, sources, next_action, action_authorized=false, action_state,
email_claims_pending_review, pod_state. Read phases completed are listed separately from queued actions.
No phone, secret, signed URL, raw message/body/customer/driver/financial values are printed.

Actual classifications and a pilot remain unknown until owner execution. No new live evidence or
LIVE_VALIDATED claim is produced by offline implementation/tests.
Verification: 104 targeted tests passed, then 375 full-project tests plus Ruff/dashboard checks passed.
Two existing dependency deprecation warnings remain. CLI help was checked without launching a phase.
