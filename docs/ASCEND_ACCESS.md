# M4B — first owner handoff, offline foundation

LATEST: completed owner-table-schema-001 evidence has been applied to the ops parser offline. Next owner
command is login-discover-ops / owner-live-ops-002 with 2026-09-11 and US format; see ASCEND_ALL_LOADS_TABLE.md.
It reads board rows only, keeps the same local session and normal networking, and does not open details.
Older diagnostic-next statements below are superseded. No live run or new attempt consumption here.

Current next command is login-diagnose-table, not login-discover-ops: see ASCEND_ALL_LOADS_TABLE.md.
owner-live-ops-001 is consumed with a header-schema stop after authenticated board navigation.
New owner-table-schema-001 is prepared but not run. Older unexecuted statements below are historical.

## ACTIVE: POC #002 owner operating board

Tomorrow operations supersede historical 1752 validation. Use the new dated owner-executed command in
docs/POC_002_LIVE_OPERATIONS.md: login-discover-ops, attempt owner-live-ops-001. It prompts for calendar
date and board date format, keeps the same normal-network headed Python/msedge session after manual
login/Enter, reads only recognized date-matching board/detail identities, and stores private operations
facts/derived queues separately from canonical state. Bounds/unknown coverage are explicit. Do not run
1752 or consume bootstrap -02 for this task. No live read was performed during this implementation.

## Current prepared run — normal app networking, fixed read actions, live field discovery

This supersedes the older same-process network restrictions and missing-contract prerequisites below.
The owner must execute the live run; only offline tests have been run during this update.

```powershell
Set-Location 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
.\.tools\python\python.exe -m scripts.ascend_browser login-validate-1752 --owner-authorized --owner-attested-booking-logistics --origin https://ascendtms.com --attempt-id owner-same-process-1752-01
```

Existing persistent profile C:\FreightDeskRuntime\Browser\booking-logistics\ascend; local Python
Playwright / headed Edge msedge only. Owner logs in manually, confirms Booking Logistics and presses
Enter. The exact page/context remains open. This path installs no same-origin/method or websocket filters
and allows service workers. App POST/session refresh/background/CDN traffic is not treated as a requested
FreightDesk mutation. No network bodies/headers/cookies/tokens are inspected or recorded by this command.
It does not call the separate continuity/storage/resource diagnostics. Other commands' older network
policies are unchanged and do not govern this new same-process flow.

After deterministic session verification, the one-use read checks local 1752 history/CV evidence and
policy/pause/expiry. ReadOnly1752Executor navigates only to the established /loads, finds unique exact
1752 (optionally fills one observed searchbox, never submits it), then opens only a recognized read/view
control bound to that row. Missing/ambiguous controls stop; no write action is a fallback. It verifies
the detail's load identity before reading other fields and repeats snapshots to detect changing values.
It may inspect up to eight approved semantic tabs; submit/default-form buttons and destructive/external
destinations are blocked. It never calls Save/Submit/Create/Delete/Assign/Update/Send/Upload or changes
financials/status/notes/canonical state. No model or page content can extend its fixed operation surface.

Field discovery uses actual labels, control types, value-presence and attribute-presence metadata.
Unknown labels are redacted; notes/phones/password/hidden values are not retained. Approved candidate
values are compared privately in memory to independent history/CV evidence. A unique observed label/value
with one nonconflicting reference value becomes RECONCILED_FOR_1752; otherwise it is UNKNOWN. Comparison
is exact/explicitly normalized, with no time/currency/expense semantic guessing. Duplicate fields across
sections are not silently merged. The result is a versioned AscendFieldContract proposal with provider,
source live browser DOM, validation_load 1752 and observed_at. No preexisting selector file is required.
Proposals save under runtime ascend/<attempt-id>-field-contract.json; no raw field values are logged or
persisted. Accepted mappings are scoped to this load, not automatically a reusable provider schema.
The result reports reconciled/unknown counts, not customer-sensitive data. It closes on completion or
failure and does not retry. Bootstrap -02 remains reserved. Session reuse is independent. No capability
is automatically marked LIVE_VALIDATED; review the actual scoped evidence after the owner-run test.

## Latest handoff — OFFLINE ONLY: continuity and same-process validation

Owner prohibits another live action this turn and reserves owner-bootstrap-1752-20260910-02. Commands
below are implemented/testable entry points, NOT executed or newly authorized live operations.
Before/after auth metadata is unavailable: no pre-closure aggregate baseline was collected previously.
Existing browser storage files do not establish their contents or authentication persistence.

### Login versus validation launch comparison

| Setting | Both paths |
|---|---|
| Implementation | AveryBrowserSession -> Python Playwright chromium.launch_persistent_context |
| Engine/channel | Edge, msedge |
| user_data_dir | C:\FreightDeskRuntime\Browser\booking-logistics\ascend |
| Subprofile | Default; no --profile-directory override (Default files previously detected) |
| Headed/headless | Headed (headless=False) |
| Explicit executable args | --disable-background-networking, --no-first-run |
| JavaScript | Enabled; now explicit java_script_enabled=True |
| Service workers | block |
| Proxy | No explicit override; inherited/system policy not inspected or logged |
| Extensions | Playwright Chromium default --disable-extensions; no custom extension loading |
| Initial state | Offline, replace restored tabs with one blank tab before networking |

Installed Playwright coreBundle.js confirms its default --disable-extensions flag. No differing executable
path, incognito context, copied cookie/storage state, cloud browser or Computer Use is involved.
There IS a post-launch difference: login sets offline=False without route restrictions; validation
enforces same-origin GET/HEAD only and blocks websockets. Do not silently weaken that boundary. This
could block resources/startup requests; the new failure counts can test that hypothesis in a later
authorized run. Closing/restoring/replacing tabs can also lose sessionStorage or session-only cookies.
Neither cause has production evidence yet; both may contribute.

### Prepared same-process command (requires future explicit owner authorization)

```powershell
Set-Location 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
.\.tools\python\python.exe -m scripts.ascend_browser login-validate-1752 --owner-authorized --owner-attested-booking-logistics --origin https://ascendtms.com --attempt-id owner-same-process-1752-01
```

The command opens the existing headed profile. Owner logs in manually at the fixed origin, visually
confirms Booking Logistics, leaves exactly one Ascend dashboard/loads tab open and presses Enter in
PowerShell. The browser stays open. The helper installs the existing read-only network boundary,
collects aggregate metadata, verifies the existing deterministic session gate, and passes the exact
page/context to the one-use 1752 workflow. Grant expiry starts after manual confirmation, not while
waiting for login. Tenant remains OWNER_ATTESTED; no provider-derived account hash is fabricated.
It navigates /loads, rejects a login redirect/ambiguity, locates only 1752, and uses a verified runtime
browser-contract.json for extraction/reconciliation. The contract is still unverified/unavailable;
the command must stop before unmapped field reads. It cannot promise a full read until live selectors
are established. No fixture selector is treated as observed. The context closes only after completion
or a failed gate. Reconciliation is against local history/CV evidence; no canonical mutation.
Read success does not require or imply persistent cross-process session reuse. No auto-retry; -02 is
explicitly rejected by this entry point. No Save/Submit, operational mutation, upload or communication.

### Prepared continuity diagnostic (separate future authorization)

```powershell
.\.tools\python\python.exe -m scripts.ascend_browser diagnose-continuity --owner-authorized --origin https://ascendtms.com
```

After the same owner login/confirmation, record cookie counts (first-party/session/persistent/future-expiry
boolean), localStorage/sessionStorage entry counts, service-worker registration count, sanitized current
path, body text length and approved nav-marker count. Cookie API records are reduced in memory and
discarded; no cookie names/values, storage keys/values, expiry timestamps, tokens or raw HTML are saved.
Require the existing session gate before closing. Save the aggregate baseline before closure; reopen
once with the same profile/settings/read guard, navigate root only, poll rendering, and collect identical
after counts. Report count deltas with causality_established=false. Storage access failures are null,
not fabricated zero. This diagnostic never consumes a load grant or opens a load.

Reopened render metadata: document HTTP status, first-party sanitized redirect path chain, console
error/pageerror counts, requestfailed counts by resource type and opaque origin bucket, script/stylesheet
counts. Foreign origins use stable per-run other-origin-N buckets; no unrelated URLs/query strings or
authentication material is logged. No response bodies, API contracts, request payloads or error text are
inspected. Reports stay under runtime Data/booking-logistics/ascend as continuity-before/result files.
Same-process runs keep separate same-process-result and existing sanitized bounded-read evidence files.

## Structural diagnostic — current command and stop boundary

Owner explicitly says DO NOT execute validate-1752 or consume owner-bootstrap-1752-20260910-02 until
the diagnostic gap is resolved. The separately authorized command executed once was:

```powershell
.\.tools\python\python.exe -m scripts.ascend_browser diagnose-session --owner-authorized --origin https://ascendtms.com
```

Uses only local Python Playwright/AveryBrowserSession, Edge msedge, existing persistent
C:\FreightDeskRuntime\Browser\booking-logistics\ascend. No alternate/new production profile or browser.
It navigates root once and waits before inspecting; polls up to 15 seconds, without reloads or following
links. It examines ALL frames for readyState, body child/text-length counts, login-form presence, approved
navigation labels and same-origin anchor route categories. No network/API traffic is inspected. Foreign
frames may block authentication through login/incomplete evidence but cannot supply positive identity.
Root anchors alone do not prove authentication; icon-only links may supply structural route evidence.
The recommendation needs two consecutive positive snapshots; the command never changes the load gate.
Path/title output is allowlisted; unknown paths/titles are redacted. URLs/queries, HTML, text, cookies,
tokens, notes, customer values and screenshots are not retained. No operational controls are activated.

Result: root /, AscendTMS title, document complete, body children 8, body text length 23, frame count 1,
child frames 0, same-origin frame path /, login false, all nav/route counts zero. All frames inspected,
15.011-second render wait, no snapshot timeout. Authentication cannot be established. Booking Logistics
stays OWNER_ATTESTED, not provider-verified. Runtime structural-diagnostic-20260910T120152548406Z.json.
No load read/write; -02 claim/read-grant/result files remain absent. Earlier next-load commands below
are prepared examples only and are currently prohibited by the owner's latest instruction.

## Current owner-attested bootstrap — 2026-09-10

This section supersedes older origin/login/literal-company requirements below for Customer Zero.
Verified origin is https://ascendtms.com; login /login.html, dashboard /, loads /loads are owner-established.
Do not request another hostname or login. Use only local Python Playwright, AveryBrowserSession,
Edge channel msedge, existing C:\FreightDeskRuntime\Browser\booking-logistics\ascend profile. Login and
validation share that executor/profile; require_existing prevents silent creation. No Computer Use,
cloud/alternate context, incognito, cookie import/export or storage-state copying.

The owner has attested Booking Logistics ownership of this profile. OWNER_ATTESTED tenant identity
is independent of SESSION_AUTHENTICATED. Session evidence requires the exact origin, no login path/form,
and Dashboard + Loads + two additional approved visible navigation controls in one same-origin frame.
Markers: Dashboard, Loads, Customers, Carriers, Locations, Reporting, Accounting, Settings. Titles and
browser storage presence alone never prove authentication. Unknown titles/paths are redacted in diagnostics.

The authorized attempt `owner-bootstrap-1752-20260910-01` is consumed. It stopped at the session gate:
path /; title AscendTMS; nav markers []; login form false; session_authenticated false. Browser closed.
No /loads navigation, load read, reconciliation, production write or M4B LIVE_VALIDATED promotion.
Owner attestation is retained without claiming provider-derived tenant identity. No retry was performed.

Exact next command, prepared for a separately authorized attempt after reviewing this stop (not run):

```powershell
Set-Location 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
.\.tools\python\python.exe -m scripts.ascend_browser validate-1752 --owner-authorized --owner-attested-booking-logistics --origin https://ascendtms.com --attempt-id owner-bootstrap-1752-20260910-02
```

Each ID is exclusive/one-use, consumed before launch even on failure. Do not reuse -01 or automatically
increment IDs to retry. The command navigates /loads only after session, policy, attestation and local
1752 history/CarrierView checks pass. Discovery reads only exact 1752; missing/ambiguous matches stop.
Extraction then requires runtime browser-contract.json with owner-attested provenance and verified live
field selectors. No such production field contract is currently verified; discovery alone cannot count
as a full field read. An available verified contract is read through the same context/adapter and values
are reconciled in memory. Only provenance/comparison metadata is retained by bootstrap, not field values.

Diagnostics under runtime Data/booking-logistics/ascend contain exactly five keys: current_path,
page_title, authenticated_nav_markers, login_form_present, session_authenticated. Separate claim/result
audit records the explicit owner attestation and outcomes. No HTML, screenshots, cookies/tokens, notes,
customer values or raw browser errors are saved. Independent production write and send guards remain.
Verification: 316 tests plus Ruff and JavaScript/dashboard checks pass, with two existing deprecation
warnings. Synthetic Edge tests exercise navigation/login predicates without vendor networking.

## Current update — shared-executor identity-only check, 2026-09-09

Owner authorized testing exactly the existing persistent local profile. Login and validation share
AveryBrowserSession / local Python Playwright / msedge, with no cookie import/export or incognito
context. Validation refuses to create a missing profile. Browser-state files are present but do not
prove surviving authentication. The identity-only command validates a bare owner-provided HTTPS
origin (no path/query/token), checks exact expected account indicators in same-origin frames only,
and cannot navigate to a shipment. No Computer Use/cloud/alternate driver is a permitted substitute.

```powershell
.tools/python/python.exe -m scripts.ascend_browser identity --owner-authorized --origin https://ascendtms.com
```

The authorized run stopped because identity was not established; no load 1752 read or production
write occurred. Report: C:\FreightDeskRuntime\Data\booking-logistics\ascend\identity-only-result.json.
303 tests and checks pass. No M4B LIVE_VALIDATED promotion. Earlier handoff status below is historical.

IMPLEMENTED / TESTED: isolated Playwright browser primitives, typed AscendBrowserAdapter, one-load
read ledger, reconciliation, protected local dashboard and controlled write state machine.
LIVE_VALIDATED: **none of M4B**. M4A exported-history validation remains unchanged.
No Ascend login, navigation, API call, production read or write has occurred in this milestone.
Only Playwright documentation/package infrastructure was accessed; browser tests use intercepted synthetic pages.

## Completed implementation and tests

AscendAdapter is the replaceable provider boundary. No general Ascend customer CRUD API is established
and no Ascend endpoint or live selector is invented. The browser contract must be filled from observed
UI evidence and owner-verified before a real load read. Accessible roles, labels, stable selectors,
explicit waits, exact URL/account/load checks and post-read comparisons replace visual coordinate actions.
Visual/agent browser control remains a separately supervised fallback, not an automatic retry path.

290 tests pass, including all M1–M4A tests. Ruff, existing JavaScript checks and new Ascend rendering
checks pass. The real Edge/Playwright test runs headless in a temporary runtime profile, fulfills every
request with synthetic HTML and proves only offline selector extraction and synthetic cookie reuse.
No test uses the dedicated production profile or claims Ascend compatibility. Two existing dependency
deprecation warnings remain. Tests cover identity, isolation, exact lookup, missing fields, DOM changes,
fallback selectors, raw/normalized evidence, all reconciliation states, policy/approval/version/pause
guards, post-verification, uncertain/crashed actions, one-use grants and network method/origin blocking.

## Browser and storage

* Dedicated Avery profile: `C:\FreightDeskRuntime\Browser\booking-logistics\ascend\`
* Browser temporary artifacts: `C:\FreightDeskRuntime\Browser\booking-logistics\ascend-temp\`
* Private setup/contract/read grants: `C:\FreightDeskRuntime\Data\booking-logistics\ascend\`
* Separate observations, approval ledger and audit: `C:\FreightDeskRuntime\Data\booking-logistics\ascend.sqlite3`

The profile is created locally but has not been launched. No general owner Chrome/Edge profile is
used or copied. Passwords are never requested by the helper. Session cookies remain inside this
profile. Screenshots, HAR, traces and automatic downloads are disabled; no raw HTML is retained.
RuntimePaths validates every configurable filename/root and rejects path traversal and reparse points.
Production writes do not touch the historical database, live canonical state or mail proposals.

## Exact manual login steps — only after separate owner authorization

Run commands from `C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI`.

Offline preparation (already performed; does not launch a browser):

```powershell
.tools/python/python.exe -m scripts.ascend_browser prepare
```

After the owner authorizes the live login boundary:

```powershell
.tools/python/python.exe -m scripts.ascend_browser login --owner-authorized
```

1. The helper opens a **blank, dedicated Avery Edge window**, with no automatic Ascend URL navigation.
2. The owner enters the known, verified Ascend login URL directly in that window. No URL is guessed
   or supplied as an invented integration endpoint.
3. Complete Ascend login/MFA manually. Do not import another profile, copy cookies or save the password.
4. Confirm the Booking Logistics company and account identifier in the account area, using independent
   account-level evidence rather than a load's customer name. Ambiguity means stop.
5. Press Enter in the helper to close the browser cleanly, preserving only this dedicated session.

Do not send password, cookie, session token, tenant/account secrets or private HTML in chat.

## Proposed first read and remaining contract work

Propose **Booking load 1752**, subject to the owner's explicit selection. It already has owner-reconciled
CarrierView 99616 / canonical historical POC evidence and can be compared with exact historical Ascend
evidence if the source identity matches. Load 1753 is not included or selected automatically.

After authorized login/inspection, capture only the account identifiers and DOM selectors needed to
construct private `browser-contract.json`. Use BrowserContract in integrations/ascend/models.py:
verified origin, account page URL, exact-load URL, independent company/account selectors and values,
required ready/load-number anchors, per-field selectors and section labels, version, owner/time proof.
No fixture selectors may be relabeled as production-verified. Missing optional selectors yield UNAVAILABLE.

Then create private `read-grant.json`: tenant booking-logistics, exact selected load_number, contract_hash
(digest of validated contract model JSON), owner_authorized=true, short expires_at, max_reads=1 and a
unique grant id. The grant is consumed before launch; an expired/failed/used grant cannot be retried.
These files must be prepared/reviewed after actual observation; the read command is intentionally blocked
until they exist and validate. No owner data or credentials are needed in chat for offline preparation.

Future bounded command, **not executed now**:

```powershell
.tools/python/python.exe -m scripts.ascend_browser read --owner-authorized --contract browser-contract.json --grant read-grant.json
```

The browser starts offline, clears restored tabs, installs the same-origin GET/HEAD-only guard, then goes
online. POST/PATCH/PUT/DELETE, cross-origin requests and WebSockets are blocked. Login/authentication is
a separate manual mode; reads never attempt automatic reauthentication. If Ascend needs a POST for a
read or an external asset origin, stop for contract/network review; do not silently broaden the guard.

## Fields and comparison

Read, where present: load number, customer/reference/status, origin/destination, pickup/delivery
facilities and appointments, equipment, commodity, weight, carrier/MC/DOT, dispatcher, driver/phone,
truck/trailer, customer revenue, total expenses, gross profit/margin, notes/private notes and tracking
status. Each fact retains raw text, normalized comparison value, source page/section and observation
time. Money uses Decimal; live currency and units require evidence. Appointment text retains unknown
local zones without conversions. Total expenses never becomes carrier pay.

Account identity is verified before any shipment field and again on the exact-load page and after reads.
The exact load number must match before other fields are read. All mapped fields are reread to reject
an inconsistent snapshot; this is a content fingerprint, not an invented provider revision/ETag.

Local comparison reads existing stores read-only and only the exact requested identity. Cached canonical,
owner-reconciled CarrierView stop evidence and exact Ascend history are compared where mapped. Outlook
remains UNAVAILABLE without explicit shipment correlation; no unrelated messages or vendor requests are
used. Unmapped fields remain unknown/unavailable. Conflicting or ambiguous identity mappings never merge.

Per field/source: MATCH, DIFFERENT, UNKNOWN, STALE or UNAVAILABLE. Comparisons are explicitly derived;
literal appointment/text differences are not timezone reconciliation. Historical evidence is always
STALE for current-state proof; other evidence older than 24 hours is stale. This conservative threshold
is visible in each comparison and does not authorize an update. Private notes and phones are retained
privately for comparison but redacted from dashboard/log output.

The dashboard at `http://localhost:8787/#ascend` shows local session/executor status, last verified company,
last successful read, separate provider/reconciliation evidence, pending approvals and audit. The
existing dedicated live owner session protects data; demo bootstrap does not. Refresh never launches
a browser. The existing server must load the updated code to expose the new summary route; no live
server restart, login grant or canonical write was performed in this handoff.

## What remains blocked

All production mutations: creation/editing, assignments, driver/truck/trailer updates, ETAs/status,
rates, notes, documents and communications. Logical interfaces exist, but actual mutation DOM flows
remain unverified and every production method raises a fixed blocked error independently of policy.
The fixture-only action coordinator checks actor/tenant, exact load, fresh current state/version,
policy, pause/takeover, payload hash and approval, claims once, mutates once and rereads. Unknown result
or crash becomes UNCERTAIN with no automatic retry. Approval is bound to exact payload/version and
expires after 15 minutes. ALLOW runs fixture operations without a click; rates remain owner-controlled.
None of this enables production execution. No customer quotes or current prices derive from M4A history.

## Exact LIVE_VALIDATED criteria

| Capability | Required production evidence | Current status |
|---|---|---|
| Account/session identity | Owner-reconciled company AND account-level identifier match before load fields | NOT LIVE_VALIDATED |
| Exact-load discovery | Only selected load resolves and its displayed load number matches exactly | NOT LIVE_VALIDATED |
| Live load read | One bounded authorized read completes with identity checks and no mutation | NOT LIVE_VALIDATED |
| Field extraction | Present fields reconciled with actual UI, raw/normalized/section/time evidence; absent fields excluded | NOT LIVE_VALIDATED |
| Read-only reconciliation | Per-source/field results reviewed, mismatches and unknowns retained, no canonical write | NOT LIVE_VALIDATED |
| Browser session reuse | Separate authorized process reopens the same dedicated session and verifies identity without login/MFA | NOT LIVE_VALIDATED |

A first successful read cannot alone validate session reuse; that requires another separately authorized
bounded session. No load creation/edit/assignment/status/rate/document/communication/autonomous execution
capability may be marked LIVE_VALIDATED from phase 1.

Implementation uses documented [Playwright persistent contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
and [context network routing](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-route).
These documents establish browser mechanics only, not an Ascend contract.
