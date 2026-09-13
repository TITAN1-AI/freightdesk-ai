> Latest owner milestone: source0.5.0 [workspace Mapping Mode](ASCEND_X1_MAPPING_MODE.md)
> supersedes the proposed per-panel detail -03. First validation cohort is not a permanent ID limit.
> OBSERVE and AUTO_MAP use separate owner lease scopes; normal AUTO_MAP requires reviewed cohort proof. No live execution or
> new capability promotion here. Earlier version/attempt instructions below are historical.

> Source0.4.1 supersedes older content refresh instructions. See
> [content lifecycle correction](ASCEND_X1_CONTENT_LIFECYCLE.md). Do not refresh/re-pair or run
> a detail attempt to diagnose lifecycle failure. Owner reload is required; no live execution here.

> Source 0.4.0 adds an offline-prepared metadata-only detail discovery path. See
> [X1 detail contract v1](ASCEND_X1_DETAIL_CONTRACT.md) for the separate one-load owner-run plan.
> Do not reuse prior retry instructions as authorization. Read access remains revoked.

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

---

Historical implementation/diagnosis follows. Earlier retry commands are not current authorization.

> 2026-09-11 update: owner-tested enrollment/reconnect and local session receipts are now recorded.
> Source 0.3.1 fixes tab lifecycle/status. See [tab lifecycle diagnosis](ASCEND_X1_TAB_LIFECYCLE.md)
> before retrying; the inspected lease expired. Older 0.3.0 preparation statements below are historical.

# X1 0.3.0 persistent read-only runtime

Implementation and fixtures only, 2026-09-11. No real enrollment, bootstrap, lease, extension reload,
host execution, Ascend request, registry change or vendor write was performed for this implementation.
The first real read lease must be explicitly enabled by the owner. Earlier consumed test grants and
pairing audits remain unchanged. The one-shot `-02` preparation is no longer the normal operating model.

## Architecture

The existing Edge extension and Native Messaging host remain the transport. Three independent checks
govern operation: durable owner enrollment, a time-limited read lease, and current provider evidence.
None grants permission to write to Ascend, another vendor or canonical shipment state.

| Layer | Responsibility |
|---|---|
| Windows local enrollment | DPAPI-protected binding to exact extension ID, Windows user/device, host installation, protocol, Booking Logistics and FreightDesk/Avery |
| Edge service worker | Store an opaque enrollment handle; reconnect, route one eligible tab, execute only typed host dispatches |
| FreightDesk native runtime | Own cadence, lease/policy/pause checks, bounded command sequence, replay protection, provenance receipts and unapplied proposals |
| Provider DOM reader | Prove authenticated session, Active Loads view, board schema, exact row and deterministic detail identity before appropriate reads |
| Protected local dashboard | Show fresh connection/read state and accept explicit owner lease, pause, rebind and enrollment-recovery controls |

The native manifest remains pinned to exactly
`chrome-extension://opckmnldaebecjphbmdmelfflikinpif/`. No wildcard or additional vendor origin is added.
The extension adds only `storage` and `alarms` permissions to existing `nativeMessaging`; its host
permission remains `https://ascendtms.com/*`. Browser alarms wake the local runtime; FreightDesk owns
the actual read schedule. Codex is not a scheduler or a required running participant.

Booking Logistics tenant identity remains **OWNER_ATTESTED**. Reconnect proves the enrolled local
extension/installation and fresh app session; a reliable provider-derived account identifier has
not been established. The owner must use the enrolled Booking Logistics Ascend account when signing in.

Initial enrollment uses an explicitly prepared ten-minute bootstrap once. Verified acknowledgement
commits durable enrollment and returns its opaque handle. Reconnect checks the protected record and
uses a fresh thirty-second challenge and connection-only HMAC key. Keys, challenges, proofs and
bootstrap JSON never enter browser persistent storage or logs. Ten-minute connection sessions renew
automatically; they do not require fresh enrollment. Enrollment has no daily expiry.

Reconnect trust is the pinned native origin plus the protected local Windows enrollment and host
installation. The session key is delivered through that local native pipe; it is not an independent
credential against code already controlling the enrolled Windows user. Identity, manifest, protocol,
device or security mismatches invalidate enrollment/read authority rather than silently replacing it.

## Read lease and loop

Default lease: **eight hours**. Default board interval: **five minutes**. The owner CLI can choose
one minute to twenty-four hours and a polling interval of one to sixty minutes. Dashboard Enable
uses eight hours. Expiry, explicit Disable, enrollment revoke or security mismatch closes read
authority. Pause is independent; enabling a lease does not implicitly resume paused Avery reads.

The fixed operation vocabulary is:

- `ASCEND_GET_SESSION_STATE`
- `ASCEND_NAVIGATE_ACTIVE_LOADS`
- `ASCEND_GET_ACTIVE_LOADS`
- `ASCEND_FIND_LOAD`
- `ASCEND_OPEN_LOAD_READONLY`
- `ASCEND_READ_LOAD`
- `ASCEND_READ_STOPS`
- `ASCEND_READ_ASSIGNMENT`

No command accepts a selector, script, arbitrary URL, form action, write operation or model-defined
action. Normal Ascend-generated application traffic is permitted; the typed executor is the write
safety boundary. No password or MFA automation is implemented.

An enabled cycle verifies the current enrollment, lease, tenant/actor, policy and pause state. It
resolves an authenticated tab, verifies its current document, navigates using a known provider Loads
or Active Loads control where needed, and independently verifies `AscendLoadBoardViewContract`.
It then reads the bounded visible board and calculates a semantic hash. An unchanged hash produces
no new proposal; changed evidence appends an **UNAPPLIED** proposal with provider facts, view proof,
observation time and separate derived hash/count. Returning to an earlier board state is a new
observation, not an overwrite of an old proposal.

The current hash covers **load ID, pickup date and drop date only**. It cannot detect changes to
assignment, rates or other unread fields. Coverage remains **VISIBLE_BOARD_ONLY**, at most 100 rows;
there is no pagination or whole-account absence/deletion inference. An empty board is accepted only
with explicit provider empty-state evidence and an otherwise verified schema. No recurring 8/3 or
eleven-load oracle is applied; that belongs to the historical one-shot test.

The trusted local workflow can request an exact load present in a fresh manifest using the active
lease. It repeats session/view/board proof, exact FIND and deterministic OPEN identity before the
three detail read operations. No per-load pairing or authorization phrase is needed. However, real
assignment, stop and appointment field contracts have not yet been established: these reads return
**mapping_state=UNKNOWN, fields=[]**. This release does not claim operational field extraction works
against production, and does not infer values from unverified labels or positions.

## Lifecycle and owner states

| Condition | State/action |
|---|---|
| No durable enrollment | `NOT_ENROLLED`; complete initial owner enrollment |
| Host unavailable | `HOST_UNAVAILABLE`; bounded backoff and later alarm reconnect |
| Invalid/revoked/incompatible enrollment | `PAIRING_STALE`; owner reviews/re-enrolls, no automatic replacement |
| Valid connection, no enabled lease | `PAIRED` / read access disabled; owner enables a lease |
| No eligible tab | `WAITING_FOR_ASCEND`; open Ascend normally |
| One authenticated eligible tab | Automatically bind after provider session proof |
| Multiple authenticated tabs | Keep a currently verified binding; otherwise request owner selection |
| Logged-out provider session | `ASCEND_REAUTH_REQUIRED`; “Sign into Ascend.”; no password/MFA automation |
| Valid lease, view and completed board cycle | `READ_ONLY_READY`; idle until the host schedule is due |
| Expired/revoked lease or pause | Stop reads; explicit Enable or Resume is required as appropriate |
| DOM/view/identity ambiguity, drift or uncertain detail operation | `STOPPED`/`ERROR`; concise safe result, no blind retry |

Opaque binding hints support lifecycle recovery only. A tab/document hint is never authentication:
after reload, close, navigation, worker/host/browser or Windows restart, current origin/document and
provider session checks still apply. A fresh native session alone cannot resume an uncertain detail
click. Safe session/board recovery may resume under the still-valid lease; unsafe uncertainty stops.

The dashboard reports Extension, Native host, Pairing, Session, Read access, Bound tab, View, last
board sync, semantic board hash, load count and lease expiry. Connection labels are freshness-bound;
old receipts do not establish current connectivity. The dashboard polls local status only. Its
existing dedicated owner session is required; the demo bootstrap cannot enable X1 reads. Mutating
local controls also require the same-origin local request header. Re-pair revokes access and directs
the owner to local enrollment setup; it never generates a bootstrap silently.

## Runtime files and migration

All live files remain under `C:\FreightDeskRuntime`, using checked paths that reject reparse points:

- `Secrets\ascend-x1-enrollment.dpapi`: durable protected enrollment binding.
- `Secrets\ascend-x1-enrollment-pending.dpapi` and
  `Data\booking-logistics\ascend-native\enrollment-bootstrap.json`: initial enrollment only, removed after success.
- Existing `Data\booking-logistics\ascend-native\bridge.sqlite3`: historical native/pairing/grant
  records plus append-only enrollment events. Existing consumed entries are retained.
- `Data\booking-logistics\ascend-native\runtime.sqlite3`: separate read leases, durable request
  replay ledger, safe events, provenance receipts/proposals and recoverable scheduler checkpoint.

There is no need to clear old consumed grants. A legacy successful pairing does not silently enroll
the extension or grant a read lease. The owner migrates by completing the new enrollment once and
explicitly enabling read access. Existing Reset/Revoke also invalidates persistent enrollment and
leases while preserving historical audit records. No registration or launcher rebuild is part of
this migration when the existing installed host points to the current local Python source.

## Prepared owner setup — do not execute in this implementation task

1. Reload the existing unpacked X1 extension to **0.3.0**, retaining its exact pinned extension ID.
   Refresh the existing Ascend tab so its content script is current. Do not create a new profile.
2. Prepare the initial enrollment locally:

   ```powershell
   Set-Location -LiteralPath 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
   .\.tools\python\python.exe -B -m scripts.ascend_x1_enrollment prepare --owner-executed
   ```

   Type `ENROLL X1 READ ONLY` locally once. Import
   `C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\enrollment-bootstrap.json`
   through the extension panel and wait for its verified acknowledgement. Never paste its contents.
3. Open the existing private owner dashboard when controls/status are needed:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.open_live_poc
   ```

   This launcher opens the local dashboard without printing its private access grant. The local
   FreightDesk dashboard server must already be running. The native host itself is launched by Edge.
4. The first real read lease is a separate explicit owner action. For normal operation, click
   **Enable read-only access**, or use:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime enable --owner-executed --hours 8 --interval-seconds 300
   ```

   Enabling permits the runtime to begin its bounded reads automatically; do not run it as a setup
   or status check. No real lease has been granted by this coding task.

During an enabled lease, the normal workflow is to open/log into Ascend. Enrollment and reconnect do
not need daily bootstrap files, phrases or buttons. Lease renewal after expiry, provider login/MFA,
multiple-tab ambiguity, deliberate pause/resume, security invalidation and unresolved provider DOM
drift still require owner action. The dashboard's protected session may need its private launcher
again when that session expires; this does not interrupt an otherwise valid native read lease.

## First live validation plan — owner authorization still required

After successful enrollment, first observe automatic reconnect with **read access disabled** across
popup close, worker wake, Edge restart and host restart. Confirm no board or detail requests occurred.
Then, in a separately authorized bounded test, enable a short lease:

```powershell
.\.tools\python\python.exe -B -m scripts.ascend_x1_runtime enable --owner-executed --hours 0.25 --interval-seconds 60
```

Use one authenticated Ascend tab. Verify independent Active Loads view proof and one board receipt;
on a second unchanged cycle, verify a no-op rather than a duplicate proposal. Check zero-tab and
logout/re-login recovery, and explicitly test multiple-tab selection before relying on it. Do not
change vendor data to force a board change; a naturally changed board can verify refresh later.
End by disabling read access and verifying no further reads:

```powershell
.\.tools\python\python.exe -B -m scripts.ascend_x1_runtime disable --owner-executed
```

Stop on a provider contract/identity mismatch; never weaken view or identity requirements to finish
the trial. Actual detail values remain a later field-contract milestone. No CarrierView, Outlook,
Ascend mutation, communication, document action or canonical shipment mutation belongs to this plan.

No new persistent-runtime capability is LIVE_VALIDATED until the owner-run evidence proves its
specific scope. Restart and provider fixtures validate implementation, not production compatibility.

## Verification completed

**232 targeted tests passed**, covering persistent enrollment, native framing/startup, reconnect and
restart abstractions, exact identity/manifest pinning, replay/revocation, zero/one/multiple tabs,
binding recovery, logout/reauth, typed navigation, view changes, lease lifecycle, policy/pause gates,
board no-op/refresh/provenance, unknown detail contracts, safe diagnostics and protected dashboard
controls. Owner disable/pause/rebind/expiry racing an in-flight receipt rejects the evidence while
retaining a valid pairing; security mismatches still revoke it. Legacy one-shot regressions passed.

Ruff, JavaScript syntax and Node bootstrap/popup/controller/runtime/dashboard checks passed. The
dashboard was exercised at desktop and narrow-screen sizes with synthetic data and intercepted
requests. Native launcher tests used a compiled isolated fixture, not the installed host. All test
artifacts are under `C:\FreightDeskRuntime\Data\TestRuns`. Two existing Starlette/httpx and AnyIO
deprecation warnings remain. No claim of production compatibility follows from these tests.
