# X1 0.4.1 content lifecycle correction - offline diagnosis

## Evidence: what failed and what is unknown

Local read-only inspection of runtime.sqlite3 at 2026-09-11 22:11:52 UTC found the fifth lease
issued at 22:04:34 UTC, scheduled to expire at 22:19:34 UTC, not revoked at inspection.
The owner reported repeated tab refresh/logout/login with one eligible tab and persistent
CONTENT_SCRIPT_STALE / REFRESH_ASCEND_TAB. The ledger corroborates:

- 22:04:35.812117 and 22:04:35.849878: verified session receipts.
- 22:04:35.892166: verified independent Active Loads view receipt.
- 22:04:35.948096: fresh board receipt, 8 visible rows, matching retained board hash.
- 22:04:40.034613: CONTROL / REFRESH_ASCEND_TAB, one eligible tab.
- No subsequent read receipts in the inspected lease; scheduler wakes continued through 22:11:37.

Thus the count was **fresh before the failure**, then became **retained evidence** while current
session/view/binding were UNKNOWN. It was not evidence of a successful read in the stale state.
Earlier 9/49-row receipts belong to prior leases and are not substituted for this cycle.

Deterministic local defect: runtime.js enabled() rejected the persisted REFRESH_ASCEND_TAB code.
Every wake exited before tab enumeration/handshake, including wakes caused by manual refresh or
login. The owner could not clear that condition by refreshing. The old recovery budget also lived
in a tab-ID Set without resetting on document replacement. These are implementation defects.

The **initial** handshake/reconnect failure at 22:04:40 was collapsed into one generic safe code.
Installed manifest/worker/content versions, controller revision, document generation, handshake
revision and original failure category were not persisted. Missing registration, old injected
script, stale port/generation, invalidated extension context, cache or build mismatch therefore
cannot be distinguished retrospectively. Checked source 0.4.0 manifest/reader expectations agree;
that is not proof of the installed or injected build. No evidence establishes authentication failure.
No raw browser state, cookies, session values, HTML or traffic was inspected.

## Implemented build handshake

Packaged build.js and host BridgeBuild agree on extension 0.4.1, controller_revision=2,
content_protocol=2 and native_protocol=1. Manifest vs worker and manifest vs content are checked.
Native Messaging framing/enrollment protocol remains1; no transport or re-enrollment change.
Signed native runtime WAKE and RESULT messages require the current build. Successful document
handshakes also include service_worker_version, content_script_version, document_generation,
tab_id and document_id. Host matches proof to route before dispatch and persists the sanitized
handshake with receipts/status. A stale ID or wrong build cannot acquire provider verification.
These IDs are local document bindings, not cookies, pairing secrets or authentication tokens.

Current source differentiates CONTENT_SCRIPT_MISSING, CONTENT_SCRIPT_OLD_VERSION,
CONTENT_SCRIPT_PORT_STALE, DOCUMENT_CHANGED and PROTOCOL_VERSION_MISMATCH. Failed injection has
CONTENT_SCRIPT_INJECTION_BLOCKED; a failed bounded recovery has CONTENT_SCRIPT_RECOVERY_FAILED.
No generic REFRESH_ASCEND_TAB loop. Old stored REFRESH_ASCEND_TAB can re-enter **handshake only**
under a valid lease; it never bypasses version/session/view/identity checks or replays detail opens.
Protocol rejection preserves enrollment and read-lease identity; it invalidates current proof.

## Automatic recovery and permission boundary

An eligible tab is pinged through the existing document port. Missing/old/disconnected content
permits one bounded recovery per tab document under a freshly checked unexpired, unpaused host
lease. Only the fixed packaged build/contract/error/view/scope/sensor/reader/content files are
injected into frame0, ISOLATED world, on the existing ascendtms.com tab. No arbitrary JavaScript,
file list, URL, navigation, new profile, content-script read or write action can be supplied by a
model, webpage or owner command. Reinjection itself registers the sensor; no DOM read happens
until the existing signed fixed read dispatch.

Chrome/Edge requires the **scripting API permission**, which 0.4.0 did not declare. Source0.4.1
adds that capability explicitly. Host permissions remain exactly https://ascendtms.com/*; no new
site access, activeTab, remote code, eval, MAIN-world injection or runtime permission-request flow.
If Edge policy disallows injection, the operation stops precisely; it never requests repeated
page refresh. Adding this API capability is not described as already available in 0.4.0.

Current registration disposes its previous listener/port and increments document generation.
Physical document replacement creates a fresh document identity. New V2 dispatch/result kinds
prevent surviving pre-0.4.1 listeners from executing duplicate reads: old code rejects the new
kind before reader execution; old READY/results cannot satisfy the new handshake. The same port
transport is retained. Stale ports, navigation/root-to-loads, refresh, logout/login, worker/browser
restart require fresh proof without revoking durable enrollment. Recovery budget resets on a new
document; policy/protocol failures stop rather than automatically reinjecting indefinitely.

## Current versus retained board evidence

CLI/dashboard/popup expose board_evidence_status:
- CURRENT_VERIFIED_BOARD only with enabled/unpaused access, fresh authenticated session, bound tab,
  ACTIVE_LOADS, completed READ_ONLY_READY cycle and fresh board timestamp.
- LAST_KNOWN_BOARD_EVIDENCE when prior hash/count exist but any current proof is absent or revoked.
- NO_BOARD_EVIDENCE when no board receipt exists.

Retained hash/count/time are preserved without asserting current truth. Local port invalidation
also removes the popup's current-proof claim while the host catches up. No additional LIVE_VALIDATED
promotion follows from this offline lifecycle fix. Detail mappings remain UNKNOWN/CANDIDATE_ONLY,
coverage VISIBLE_BOARD_ONLY, tenant OWNER_ATTESTED, and all writes unavailable.

## Owner retry - historical, superseded by 0.4.2 board-schema handoff

Owner subsequently validated 0.4.1 lifecycle recovery. The next board read stopped with
BOARD_SCHEMA_INVALID and the owner revoked the lease. Use ASCEND_X1_BOARD_SCHEMA.md for the
current 0.4.2 correction and retry; the commands below document the earlier lifecycle milestone.

1. Reload the existing pinned unpacked X1 extension and verify version0.4.1. If Edge requires review
   of the added scripting capability, allow it only for the existing Ascend host scope. Do not
   uninstall/re-pair/re-enroll or refresh the Ascend page. Keep the existing authenticated tab open.
   Reload can resume authorized reads automatically if the existing lease is still valid.
2. Inspect status from the project PowerShell directory:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime status --owner-executed
   ```

   An enabled, unexpired, unpaused lease remains usable after this source update; no re-creation
   is required merely for document recovery. If it expired, owner may explicitly enable a short
   board-only retry when ready:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime enable --owner-executed --hours 0.1 --interval-seconds 60
   ```

3. Allow one scheduler interval. Expect automatic document handshake, provider session, tab binding,
   Active Loads proof and a fresh board receipt labeled CURRENT_VERIFIED_BOARD. Do not queue detail
   discovery or reuse its proposed attempt in this lifecycle retry.
4. On injection/policy/protocol/recovery failure, retain the safe status and stop; no page refresh
   or repeated enable attempts. Disable after success or failure:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime disable --owner-executed
   ```

No live browser/Ascend/native-host execution, lease change, registry change, re-pair, CarrierView,
Outlook or production write was performed by this coding task.

## Verification and final lease check

260 targeted offline tests passed across document/build handshake, fixed injection fixtures,
content/router, retained evidence, runtime/controller, enrollment/native host/startup, detail
contracts and protected dashboard/API. Ruff and JavaScript syntax checks passed. Existing two
Starlette/httpx and AnyIO deprecation warnings remain. All browser fixtures used isolated profiles
and intercepted requests under C:\FreightDeskRuntime\Data\TestRuns; no live execution.

At final read-only check 2026-09-11 22:24:20 UTC, the same lease had expired at 22:19:34 UTC,
not been revoked. No detail attempt was queued. Therefore this owner's next retry needs a fresh
short lease after adopting 0.4.1; that requirement is due to elapsed time, not enrollment loss or
protocol migration. The enable command above has not been executed by this task.
