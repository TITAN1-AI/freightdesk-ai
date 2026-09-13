> Source0.4.1 supersedes older content refresh instructions. See
> [content lifecycle correction](ASCEND_X1_CONTENT_LIFECYCLE.md). Do not refresh/re-pair or run
> a detail attempt to diagnose lifecycle failure. Owner reload is required; no live execution here.

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

# X1 0.3.1 tab lifecycle diagnosis — 2026-09-11

## Local evidence and limits

Inspected only sanitized fields in the existing runtime database and receipt/audit records under
`C:\FreightDeskRuntime\Data\booking-logistics\ascend-native`. No browser, installed host, vendor
request, read lease, enrollment, registry or live runtime file was changed by this task.

| Owner question | Persisted observation |
| --- | --- |
| Tab enumeration after enable? | Yes: eligible_tab_count=1 in the dispatched route. |
| Candidate origin/path? | https://ascendtms.com, path `/` (dashboard root). The owner's later visible `/loads` is a separate observation. |
| Worker received lease/wake? | Yes: session probe, bound session read and navigation dispatched. |
| Extension knew access enabled? | Yes: those host-leased dispatches executed after enable. |
| Content script active? | Yes: two verified session receipts, authenticated_app=true, all eight approved navigation markers. |
| Tab created/refreshed relative to extension reload? | UNKNOWN; not persisted. |
| Injection/reconnection failure? | Not shown for these successful session reads. Later lifecycle/version state UNKNOWN. |
| Host permissions/site access? | Declared Ascend origin and effective access sufficient for two session reads; exact browser site-access settings not persisted. |
| Authentication failed before binding? | No. Provider/browser session proof succeeded. Tenant remains OWNER_ATTESTED. |
| Binding reached? | Yes. Active Loads navigation followed binding; no view proof or board receipt completed. |
| Why STOPPED? | ASCEND_NAVIGATE_ACTIVE_LOADS reached its 12-second deadline. |
| Safe error persisted? | READ_TIMEOUT. Underlying renderer/port/navigation cause was not retained. |

UTC timeline on 2026-09-11:
- 18:54:30.599655: read lease enabled (15 minutes, 60-second cadence).
- 18:54:46.095772: session probe dispatched; 18:54:46.111729 verified.
- 18:54:46.133284: bound session dispatched; 18:54:46.148394 verified.
- 18:54:46.168184: ASCEND_NAVIGATE_ACTIVE_LOADS dispatched.
- 18:54:58.179341: READ_TIMEOUT receipt; stopped, production_writes=false.
- 19:09:30: lease expired, not revoked. Confirmed expired at inspection 19:17:26 UTC.

Two session receipts, zero board syncs and zero proposals were persisted. Binding did not fail in
this captured cycle. UNKNOWN/UNBOUND in a later projection are freshness labels, not evidence that
binding never occurred. Source 0.3.0 also incorrectly used WAITING_FOR_ASCEND before enumeration.
The root cause of the navigation timeout cannot be narrowed further from existing evidence.

## Scoped corrections

- Initial enable/resume/rebind uses DISCOVERING_ASCEND. WAITING_FOR_ASCEND is emitted only after
  enumeration proves zero tabs. Discovery failure, stale content, reauthentication, bound session,
  unverified view, stopped execution and scheduler inactivity have distinct states.
- Current content-script version handshake is 0.3.1. Existing compatible tabs reconnect automatically.
  A stale/missing receiver permits one refresh per tab per worker lifetime, only with a freshly
  checked unexpired/unpaused host lease, exact origin, `/` or `/loads`, and no query/fragment.
  No new permission, script reinjection alongside old listeners, profile, or transport is introduced.
  Unsupported/blocked/unsuccessful recovery returns CONTENT_SCRIPT_STALE / REFRESH_ASCEND_TAB.
  That error stops automatic reads/recovery rather than repeatedly refreshing.
- Reuse the successfully proved port when possible. Do not unnecessarily disconnect/reconnect it
  between the single-tab probe and bound-session verification.
- Do not scan for board view on the dashboard root. After the fixed provider Loads navigation click,
  report NAVIGATION_STARTED and verify a fresh session/document before requiring independent
  Active Loads view proof. This fixes an old-document lifecycle assumption, not a proven vendor cause.
  Timeouts remain stopped; no speculative retry of a timed-out operation.
- Status includes safe execution stage, eligible tab count, safe error, last scheduler wake and
  scheduler freshness. Successful receipts retain sanitized origin/path/count. No raw DOM, URL query,
  document/tab IDs, private values or network contents are added to diagnostics.

## Scheduler ownership

The extension service worker registers the named `x1-runtime-wake` Chrome/Edge alarm every minute,
re-registers on worker load, and resumes enrollment on wake/startup. Native connection heartbeats also
provide wake opportunities; the host owns the lease, cadence, policy and fixed read sequence.
The enable CLI persists authorization then exits; it is not the scheduler. Neither Codex nor the
dashboard must stay running. Edge with the extension must remain capable of running. A valid lease
with no runtime wake for more than 150 seconds projects SCHEDULER_NOT_RUNNING, distinct from a
native heartbeat. This is an observed-wake timeout, not proof of why Edge stopped waking.

The captured dispatches establish that scheduling executed once. They do not validate recurring
board cycles, sleep recovery or unchanged-board no-ops in production.

## Owner retry (not executed here)

1. Reload the existing unpacked FreightDesk Ascend X1 extension in Edge; verify version 0.3.1 and
   the same pinned extension ID. Keep the existing authenticated Ascend tab. Do not remove/reinstall,
   reset enrollment, import another bootstrap, or manually bind/select a single tab.
2. The recorded read lease is expired. From the project PowerShell directory, explicitly enable a
   fresh bounded read lease when ready for the runtime to start automatically:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime enable --owner-executed --hours 0.25 --interval-seconds 60
   ```

3. Leave Edge open and allow up to one alarm interval. X1 should auto-discover the single eligible
   tab, recover its content script if needed, prove session, bind, then independently verify Active
   Loads before a board read. No manual refresh is normally needed. If REFRESH_ASCEND_TAB is shown,
   refresh the existing Ascend tab once and retain the safe result for review; do not reset/re-pair
   or repeatedly renew access to bypass a stopped gate. A stopped recovery may require an explicit
   owner control after local review; do not assume a page refresh clears a latched safety stop.
4. Inspect the safe status without running another browser command:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime status --owner-executed
   ```

   Stop on any further safe error and report it. To end the bounded read lease:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime disable --owner-executed
   ```

No CarrierView, Outlook, operational mutation, communication, canonical mutation or field-contract
promotion is authorized by these changes. Unknown operational detail mappings remain UNKNOWN.

## Validation

Targeted offline fixture coverage includes existing tabs across reload, stale/missing receivers,
one bounded refresh, blocked/unsafe-path recovery, disabled lease, alarm registration and wake,
worker/enrollment resume, one/zero/multiple tabs, proof before view, persisted timeout stage,
CLI-independent persisted leases, scheduler inactivity, and protected dashboard controls.
Offline tests do not establish live browser compatibility of 0.3.1.

Targeted validation for this correction: **215 tests passed** across the extension DOM/router,
runtime/controller, native enrollment/host/startup and protected runtime API/dashboard suites.
Ruff and JavaScript syntax checks passed. Existing two Starlette/httpx and AnyIO deprecation
warnings remain. Tests used isolated fixtures under C:\FreightDeskRuntime\Data\TestRuns;
no installed browser profile, installed native host or vendor was executed.
