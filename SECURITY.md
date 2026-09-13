# Security

## X1 0.5.0 OBSERVE / AUTO_MAP action scopes

Mapping leases are separate from board leases. OBSERVE permits session verification/current-workspace
metadata capture. AUTO_MAP additionally permits only host-planned transitions through owner-reviewed,
provider-fingerprinted READ_ONLY_NAVIGATION contracts, within one exact current load and back to start.
Policy read_ascend, owner lease, enrollment, pause, expiry/revoke and receipt-time checks remain. No
arbitrary selectors/scripts, submit/action controls, other-load navigation, writes or crawler exist.
Each transition independently verifies current session, load, starting/target section and control.
The 3-5 ID cohort is validation-only; normal modes have no required ID list and support optional tighter
scope. Normal AUTO_MAP requires reviewed navigation plus an owner-confirmed successful cohort, not
just OBSERVE evidence. Foreground ownership and time/workspace/section/field/read-attempt limits apply.
Field values are excluded; unknown labels are redacted. Initial field maps remain CANDIDATE_ONLY;
navigation review never activates operational facts or writes. Fixed structural hints on the existing
private port grant no authority and stop on expiry/disconnect. No new permissions, network inspection,
API calls or credentials. A future bulk audit worker requires a distinct ActionPolicy scope.

## X1 0.3.0 persistent read-only enrollment and lease boundary

Persistent enrollment is protected under runtime DPAPI and binds the exact pinned extension ID,
Windows user/device, host installation, tenant, actor and compatible protocol. Native allowed_origins
is exactly chrome-extension://opckmnldaebecjphbmdmelfflikinpif/. Browser storage holds an opaque handle
only; bootstrap secrets, HMAC session keys and proofs are never persisted there. Each native reconnect
uses a fresh short challenge/connection key through the pinned local pipe. Same-user local process
trust remains the security boundary; this is not a new independent remote credential system.

Enrollment does not enable reads. Only explicit local owner lease controls enable the fixed read
vocabulary; grants default to8h and are checked with policy/pause/enrollment on dispatch and receipt.
Revoke/reset or security mismatch persistently closes existing lease authority, including before a
replacement host handshake completes. Restoring old configuration cannot silently reactivate it.
No native/page/model command can create a lease, supply JS/selector/URL actions, mutate vendors or
apply canonical proposals. Provider session, view, exact-row/detail binding and freshness stay mandatory.

The dashboard uses dedicated live-owner proof, loopback/origin boundaries and a custom-header CSRF
gate for explicit controls. Demo bootstrap never authorizes X1 reads. Status validation reads owner
session evidence without opening/writing canonical provider records. Re-pair only revokes and directs
owner-local setup; it never prepares a bootstrap through HTTP. Append-only leases, requests, safe
receipts and unapplied proposals live in ascend-native/runtime.sqlite3; historical grants remain.
No real enrollment/lease was created here. See docs/ASCEND_X1_RUNTIME.md for scopes and limitations.

## X1 0.2.1 independent provider-view gate

The reader must prove ACTIVE_LOADS from selected provider controls/title/board relationships before
accessing operational board rows. The host independently resolves a strict allowlisted view contract;
path/IDs/counts cannot override unknown/other view evidence. Conflicts and in-command view changes
stop execution. Candidate diagnostics contain canonical view labels, safe CSS enums, counts and
booleans only; no raw attributes/private DOM content. They travel in existing signed receipts, with
no transport, permission or pairing protocol change. Current failure cancels selected-tab binding.

Consumed first read authorization remains immutable. Only a future explicit owner CLI may append the
single named successor to this exact reviewed ACTIVE_VIEW_UNVERIFIED stop. No automatic renewal,
third attempt or loosened policy/expiry/read/write/identity gate. No actual successor or pairing was
created in this task. See docs/ASCEND_X1_VIEW_CONTRACT.md for the stopped current handoff.

## X1 0.2.0 identity-only release boundary

PAIRED transport never grants Ascend reads. The separate local owner CLI may prepare one ten-minute
four-command test, bound to installation, tenant/actor, explicit service date/oracle and target 1755.
The native host checks ActionPolicy ALLOW and pause/takeover before dispatch and receipt, consumes
requests/test durably, binds tab/document and board hash, validates strict evidence schemas and persists
only safe receipts. Signed READ_DISPATCH travels through the existing HMAC native channel; heartbeat
and read messages serialize outgoing sequence allocation. DPAPI, exact extension ID, Windows/runtime
binding, one-use pairing and replay rules remain unchanged. No added browser permission or native command
can prepare/retry a grant or execute operational fields, JS, selectors, arbitrary URLs, shell or writes.

The owner must select an eligible exact-origin tab. No default/all-sites routing. Its top-frame isolated
content script reads nothing on load/selection. Native dispatch activates one fixed command through a
document-bound private port. Close/navigation/reload and pairing loss invalidate the port and short lease;
no successful late result after loss. Same-page opener rejects submit/reset/default form buttons, URL
navigation, downloads/form actions/new-window targets. Actual row/opener references plus narrow provider
identity evidence are mandatory. Identity success closes the read sequence; no operational extraction.

Only load IDs/date prefixes cross the pipe for board reconciliation, then are projected to sanitized
counts/IDs/hash in runtime audit. No customer, assignment/contact, stop, financial, note, cookie, token,
header, HTML or screenshot data is logged or persisted. Tenant identity is OWNER_ATTESTED separately
from provider session/detail evidence. Fixture tests do not establish vendor capabilities.
See docs/ASCEND_X1_READONLY.md for the exact one-test scope and consumed-uncertainty behavior.

## Ascend extension X1 boundary

Native startup patch preserves byte-only stdio with explicit incremental flush; module import noise
is suppressed and native stdout contains frames only. Startup launcher/Python JSONL use fixed stages,
codes, exception categories and observed stage flags; no raw stderr, proof or payload. Owner-only
RebuildLauncher changes only the executable/source at the existing checked runtime path, no registry
or pairing reset. --self-test is a process argument unavailable to browser command payloads; it checks
the pinned Windows/runtime installation and allows one synthetic ping without DPAPI key or grant access.
Normal native sessions reject this ping. Tests use isolated runtime fixtures, not the installed host.

0.1.2 pairing diagnostics use only fixed result codes/remediation, stage names and nullable check
booleans. The new pairing_attempts table has timestamp, extension-ID match, expired, consumed, stage
and result only. NULL is unmeasured. No pairing material, actual IDs, filenames or raw errors. The same
native pipe accepts bounded pre-pair diagnostics from the exact pinned extension, without redeeming
pairing or dispatching reads. A success diagnostic requires the host's authenticated connection.
Only the exact packaged popup URL can initiate controls, including that same page in a persistent tab;
provider tabs/other frames remain rejected. No new extension permission or raw-page bridge. First signed
ACK must bind installation/generation/protocol/principal/session; PAIRING_REQUIRED persists until then.
Runtime/audit failures are visible and never authorize reads. No READ_ONLY_READY in 0.1.2.

0.1.1 adds an owner-run native registration/pairing foundation; actual installation/pairing is not
performed here. See docs/ASCEND_NATIVE_MESSAGING.md. Runtime-only host manifest pins the locally entered
ID exactly; no wildcard. Host checks caller origin, current Windows user/runtime installation, protocol,
tenant and actor. CurrentUser DPAPI protects the at-rest key; restricted runtime ACLs protect the one-use
ten-minute bootstrap. Browser key is nonextractable WebCrypto in worker memory only, no storage API.
HMAC challenge/session/direction/sequence, durable UUID consumption, strict 64-KiB framing, bounded
timeouts and append-only sanitized audit fail closed. Reset/re-pair preserve ledger history.
Unsigned fixed launcher uses binary stdio only, no shell/TCP; stderr is discarded and replies sanitized.
Only the packaged popup can explicitly initiate a host connection. Installation never connects itself.
Pairing/status do not authorize reads: valid read commands return read_release_required. Registry/ACL
deployment and real Edge handshake remain unverified. Same-user malware/OS compromise is outside this
local boundary. Reset removes any leftover expired bootstrap; expiration already prevents its reuse.

MV3 host access only https://ascendtms.com/*; no cookies/history/all-sites/debugger/webRequest permissions.
Packaged isolated-world code and seven exact read operations; no model-supplied JS/selectors, window
message bridge or write operation. Native transport interface is disconnected; worker/content switches
are false. Installation initiates no reads/clicks/networking. No actual native registration or pairing
secrets were created. Runtime pairing/registration helpers are offline-tested; real deployment is pending.
Fixture-tested origin pinning, HMAC challenge/session/sequence/direction and bounded frame parsing are
components of the proposed native bridge. FreightDesk retains policy, principal/load/version checks,
audit, retries and canonical authority. No row-bound detail fallback. See ASCEND_EXECUTOR_PIVOT.md.

## POC002 operational proposals

Private driver/contact/stop facts and proposed payloads stay in the nonsynced operations runtime store;
owner reports/audits exclude phones/private notes and signed tracking URLs. Source facts and derived
classifications are separate. The operations proposal ledger has no dispatch/approve interface and
cannot mutate canonical state. Native creation messages/welcome effects and missing company wire mapping
must be resolved/disclosed before a separately authorized one-load pilot. No automatic batch release,
duplicate creation, uncertain retry, Ascend/pricing mutation or outbound communication is authorized.
Calendar date and numeric date locale require explicit owner input; unknown stop timezones stay unknown.

## Same-process Ascend application traffic and action safety

Owner-authorized same-process validation now allows normal app traffic/service workers. No blanket
same-origin/GET/HEAD/websocket filter is installed. Application session/CDN/read POST traffic is not
an authorized FreightDesk mutation; protection resides in fixed executor/actions. The command performs
only bounded exact-1752 search/open/navigation/tab/read/reconciliation actions. There is no generic
model/page-supplied click, submit, script, upload, communications or mutation entry point. Risky form
buttons/URLs and ambiguous targets stop. Existing production adapter write methods remain blocked.
No cookie/storage inspection or traffic-body/header logging is attached to this read command. Approved
field candidates are transient in-memory data; saved contract proposals exclude raw values/private
notes/phones/customer text/HTML. Owner attestation is not provider tenant identity. Prior restrictive
network text below is historical for this path or still applies only to separate legacy diagnostics.

## Auth continuity metadata and owner-interactive boundary

Future authorized continuity diagnostics may retrieve cookie records through Playwright only to reduce
first-party counts/expiry booleans in memory, then discard them. Never persist/log cookie names/values,
storage keys/values, raw HTML, console/pageerror text, request/response bodies or authentication material.
Resource observations are counts and sanitized root status/redirect paths; foreign origin buckets are
opaque. Storage access failures remain unknown/null. Do not infer causal authentication loss from counts.
Same-process validation begins automated reads only after the owner's local Enter confirmation, on the
same existing profile/page/context, after reinstalling independent read-only routing. No write guards or
session identity requirements are loosened. Manual login and same-process validation use headed Edge.

## M4B owner-attested identity boundary

Customer Zero explicitly binds Booking Logistics ownership to the approved existing local Ascend profile.
This attestation is OWNER_ATTESTED, never a provider account identifier or provider-derived tenant proof.
An independent positive authenticated-navigation check is mandatory before /loads. No login form plus a
page title alone is insufficient. Bootstrap is confined to https://ascendtms.com and exact 1752, with
one-use attempt claims, policy/pause/expiry checks, verified field contracts and independent write blocks.
Diagnostics retain only allowlisted path/title, approved nav marker names, login presence and session
result. Shipment values are not diagnostic output; bootstrap persists only reconciliation/provenance
metadata. No alternate profiles, cookie copying, screenshots, HTML or raw browser errors. No automatic retry.

This is a local demo foundation, not an approved production deployment.

## Credentials and files

Never commit .env, credentials, cookies, browser profiles, customer documents, shipment databases,
raw provider logs, HARs or sensitive screenshots. .gitignore excludes runtime directories and
common secret/database extensions. Environment examples contain placeholders only.
Owner-authorized CarrierView reads used DPAPI credentials through the private launcher.
Only historical POC capabilities are live-validated; provider writes and autonomous execution remain disabled.

CarrierView capture uses explicitly user-run hidden prompts and Windows DPAPI encrypted
storage under C:\FreightDeskRuntime\Secrets. The child process receives only the selected
CARRIERVIEW_AGENT_API_TOKEN or CARRIERVIEW_TENANT_API_TOKEN temporarily;
Python config uses SecretStr. Tokens are not command arguments or printed.
DPAPI does not protect against malicious code under the same Windows user or process-memory
access. Production needs a managed secret store.

Microsoft 365 must use OAuth/Graph with least privilege and encrypted refresh-token storage.
Never store the mailbox password. Vendor auth must follow official documentation.
Manual login/MFA belongs to the owner; never bypass platform controls.

## OneDrive

The selected project is inside OneDrive. Git ignore does not prevent cloud sync.
The owner authorized C:\FreightDeskRuntime for all operational data; OneDrive settings were not changed.
Runtime paths reject other roots, escapes, symlinks and junctions. Demo DB/logs/token were migrated;
new test databases also use runtime. Never introduce live files into source, including ignored folders.
The generated local demo bearer lives under runtime Tokens and grants only loopback demo access.

## HTTP and identity

run.py binds 127.0.0.1:8787. Trusted Host, Origin and Fetch-Metadata checks block common
DNS-rebinding/drive-by requests. Writes require bearer auth or a Strict SameSite HttpOnly
cookie and a custom header. No CORS. CSP blocks external assets, inline scripts and framing;
values are escaped. Access logging is disabled.

Any process on this workstation can bootstrap a demo owner session. This is an explicit local
trust boundary, NOT production identity. Do not expose the server through a proxy/tunnel.
All general live modes fail at startup. A separate 32+ character FREIGHTDESK_LIVE_VIEW_TOKEN can
unlock a local read projection of an explicitly reconciled POC. The private local launcher can instead
issue a one-use three-minute grant exchanged for an eight-hour HttpOnly/Strict session. The grant
is removed from the URL before exchange, never placed in provider logs; only hashes persist.
There is no HTTP grant-issuance route. Demo cookies never grant that access.
It is not multi-user production identity. Real login, TLS, revocation, rate/request limits and
field-level tenant/participant authorization must precede remote or broader production use.

## Untrusted data and execution

Models cannot create identities, grant roles, override policy or invoke tools through text.
Only the server resolves the owner identity. Driver/dispatcher/customer membership is checked
in core logic; production participant API projections do not yet exist.
Historical read requests occurred under explicit owner authorization. CarrierView GET networking requires verified origin/response contract
and explicit owner read authorization. All production writes are categorically blocked. Redirects and
environment proxy inheritance are disabled; timeout/bytes are bounded. Provider documents are unsupported.
The separate local normalized webhook inbox authenticates with a local key and quarantines events;
this is not vendor signature validation. No public ingress is exposed.

Approvals are single-use, expiring and bound to shipment version. Current policy, pause and risk
must be rechecked before simulation. The CarrierView ledger adds immutable payload/contact
bindings, exact resource identity and UNCERTAIN recovery. Independent result reconciliation and
production dispatcher enablement remain future. No attempted side effect automatically retries.

## Audit and recovery

Only application-authored explanations/error codes are logged. No raw commands, secret-bearing
provider responses or raw exception strings. Database triggers reject audit update/delete;
database owners could bypass them. Audits are not cryptographically tamper-evident.
The dashboard shows recent entries; SQLite retains history. Production retention, backup/restore,
key rotation and migration tooling are pending.
# M3 security additions — 2026-09-07

Microsoft uses delegated public-client OAuth; no password or client secret. Tenant-specific authority,
exact mailbox checks, explicit network gate, fixed Graph origin/resource, disabled redirects and bounded
responses prevent credential forwarding. DPAPI-encrypted MSAL cache lives only in approved runtime Tokens.
No Mail.Send in the requested OAuth scopes; all send interfaces fail closed regardless of policy. Drafts require explicit runtime
authorization and durable single-attempt intent. Tenant and AuthorizedIdentity bind owner command proof
to message/content; untrusted mail/model output cannot grant authority. Mail views reuse dedicated
HttpOnly owner sessions and reject demo credentials. Provider errors/cursors/content/tokens are not logged.
Files are hashed, stored as private .bin, never executed, and remain NOT_SCANNED/unverified. Historic
imports reject formulas/macros/external links and never write canonical shipments. SQLite/documents
are not encrypted by DPAPI; OS account/ACL/disk encryption remain deployment responsibilities.

## Entra provisioning versus authorization — owner update

Configured in Entra (owner-reported): User.Read, Mail.ReadWrite, MailboxSettings.Read, Mail.Send.
Requested by current interactive/silent OAuth code: User.Read, Mail.ReadWrite, MailboxSettings.Read
only, plus MSAL's standard session scopes. Never request .default or derive scopes from provisioning.
ActionPolicy separately allows reads/settings/drafts; customer/carrier/dispatcher sending stays
APPROVAL_REQUIRED. Send/reply/forward HTTP execution remains blocked regardless of token scopes,
provisioning or future policy changes. LIVE_VALIDATED is limited to the six owner-confirmed bounded
capabilities in LIVE_POC.md; this does not authorize any further networking or expand execution rights.

Selected mailbox preferences are read-only and privately stored with source/time. No automatic-reply
text is retained, no raw settings/IDs are logged, and no settings write permission is requested.
Mailbox timezone/locale cannot override explicit shipment timezone or resolve an ambiguous ETA.
Tenant/client IDs are hidden in model repr and accepted only through non-echoing local setup prompts;
if hidden input is unavailable, configuration fails rather than echoing. No identifiers or credentials
are requested in chat. OAuth and bounded validation are now owner-confirmed complete; STOP before
any further Graph networking remains the current owner instruction. No send or shipment mutation occurred.

## M4A historical staging and approved commit boundary

The owner-authorized CSV is read only from the validated runtime history inbox. Its complete raw
59-column evidence, including private notes/driver information, stays in the nonsynced historical
SQLite store and original CSV. Source data is never code, formulas are not executed, and no notes
corpus or record payload is sent to a model. Bounded per-customer note review uses local regexes
with source offsets/hashes and returns unverified topics only. Reports omit notes, driver contacts,
addresses and raw record payloads. Only aggregate/proposed-label review material is exposed.

AscendRealStager opens only runtime history/history.sqlite3; it has no historical commit, vendor,
canonical, mail proposal or scheduler execution path. Stage identity binds source hash and proposed
schema. Repeats do not duplicate records; changed evidence creates a separate review-required version.
Malformed source schema, rows, dates, money, arithmetic or exact control mismatches fail closed into
rejection/quarantine and cannot become committed history. Owner approval is required before commit.
Raw customer identities, MC/DOT strings and multi-stop evidence remain intact; no proposed alias,
equipment classification, pattern or financial label grants operational authority.

Owner approved the exact 694-row source/mapping and USD with all raw-data limitations. The separate
AscendHistoricalCommitter re-reads source and compares hash, mapping, staged raw/typed rows and row
count before one transaction in history.sqlite3. The approval and commit receipt are source-bound.
Changed source versions fail closed for reconciliation; committed evidence is never silently replaced.
SQLite backup precedes commit; rollback and missing/tampered approval/evidence are tested. An identical
re-import performs no record or audit mutation. No operational stores or vendor adapters are called.
Post-commit reports contain aggregate/raw-label evidence plus source-row/hash pointers, not private
notes, driver contacts, full addresses or raw payloads. All real data and approval/report artifacts remain
under C:\FreightDeskRuntime. This authorization does not extend to additional exports or vendor activity.

## M4B browser boundary

The dedicated Avery Ascend profile is runtime Browser/booking-logistics/ascend, never the owner's
general profile. No cookies are copied. Only the owner performs login/MFA in a separately authorized
blank browser window. Private contracts/read grants and separate ascend.sqlite3 remain nonsynced.
Browsers start offline and discard restored tabs before installing the read network boundary.
Read mode permits same-origin GET/HEAD only and blocks WebSockets, other methods/origins and downloads.
Unexpected dependency on a blocked request requires review, not silent policy widening.

No screenshot, HAR, trace, raw HTML, browser exception text, notes or driver contact is logged.
Notes/contacts remain private source evidence; protected dashboard projections redact them. Required
independent company/account selectors and exact load number gates precede shipment extraction.
One-load grants bind contract hash/load/tenant/expiry and are consumed even on failure. Reauthentication
and browser recovery never silently retry. Existing historical/canonical/mail stores are read-only inputs.

Action intents are tenant-scoped and bind exact payload/version to owner approval and expiry. Policy,
pause/takeover, account/load identity and reread checks precede a single durable claim. Unknown outcomes
remain UNCERTAIN without replay. Only synthetic transports execute this foundation; every production
mutation interface is independently blocked. Pricing remains human-controlled. No model output,
historical rate or email candidate can approve an action or cause canonical/vendor mutation.

The new dashboard endpoint reuses the dedicated owner boundary, never demo bootstrap, and performs
local reads only. No HTTP route launches Ascend. Offline setup/tests do not grant live permission.

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

Orchestrator jobs are owner-authorized local actions; the provider cannot start/review them. Session-probe leases cannot dispatch mapping. One probe renewal stays inside the original job deadline; uncertain capture execution never replays. Cleanup targets only job-bound leases. Read/write mappings and communication authority remain separate.
