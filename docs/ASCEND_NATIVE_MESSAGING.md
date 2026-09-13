# Ascend X1 native foundation - owner handoff

**Current handoff:** [X1 0.2.0 identity-only controller](ASCEND_X1_READONLY.md). The owner has now
LIVE_VALIDATED local 0.1.2 pairing transport (OWNER_REPORTED PAIRED / PAIRING_SUCCESS). The startup/
pairing-pending steps below are historical. No new Ascend capability is validated. Reload/fresh pairing
and a separate owner-executed read grant are prepared, never executed automatically. Existing registration
and launcher remain; no rebuild/registry changes are required by the controller patch.

Earlier: [native startup diagnosis and owner self-test](ASCEND_NATIVE_STARTUP.md) superseded the pairing
retry steps below. The registered launcher has a reproduced incremental relay buffering defect. Source
is fixed; owner must rebuild at the existing manifest path, run the synthetic self-test, then STOP.
No new bootstrap/pairing yet. Registry and extension 0.1.2 remain unchanged.

## 0.1.2 pairing import diagnostics - 2026-09-11

Owner reports 0.1.1 installed, exact ID pinned, registration successful, and host reachability after
Edge restart/reload. Check local host returns PAIRING_REQUIRED. Bootstrap import has not produced
PAIRED. These are OWNER_REPORTED local results; no Ascend capability is promoted.

Confirmed implementation defects in 0.1.1: popup file/JSON exceptions were swallowed; worker schema,
expiry and host errors were collapsed; polling could overwrite a popup-local error; and a synchronous
connectNative exception after connect advanced the epoch could be mistaken for an obsolete import.
The prior real import failure cannot be attributed to one of these or a particular host gate from
the old output. No private bootstrap, DPAPI data, installed ID, runtime session or old ledger was
inspected in this task. File-picker focus loss is a lifecycle possibility covered by the new panel,
not a claimed observation from the owner's failed import.

0.1.2 adds a persistent packaged pairing panel, explicit Import selected file button, unconditional
file-input reset after an attempt, stage-specific safe diagnostics and verified-acknowledgement gating.
Selection shows PAIRING_FILE_SELECTED; import explicitly starts validation. Import reads .files directly
even if change was not delivered. A missing file shows PAIRING_FILE_NOT_SELECTED. Re-selecting the same
file is supported; it does not bypass one-time consumption. State stays PAIRING_REQUIRED until a signed
host acknowledgement matches session, protocol, tenant, actor, installation and generation. Only then
PAIRED / PAIRING_SUCCESS. READ_ONLY_READY is neither displayed nor reachable.

### Trace and audit

| Stage | Check/result |
|---|---|
| FILE_INPUT / FILE_READ | Explicit button reads selected File, 4096-byte cap; missing/read errors shown |
| JSON_PARSE | Parse only in popup memory; malformed data becomes PAIRING_SCHEMA_INVALID |
| SCHEMA_VALIDATION | Worker validates exact bootstrap shape/version/principal fields |
| EXTENSION_ID_VALIDATION | Bootstrap ID must equal actual runtime extension ID |
| EXPIRY_VALIDATION | Reject expired/future-invalid package locally |
| NATIVE_CONNECT | Existing exact native host; no replacement transport |
| DPAPI_VALIDATION | Host validates its protected current pairing and installation |
| ONE_TIME_VALIDATION | Durable consumed-generation lookup before issuing a challenge |
| PROOF_VALIDATION | Verify HMAC challenge proof; rejection remains unpaired |
| PAIRING_PERSIST | Consume generation, remove bootstrap, persist safe checkpoint before acknowledgement |
| ACK_VERIFICATION | Worker verifies signed acknowledgement and reports safe success; no operational read |

Frontend failure metadata uses the same native pipe via a strictly bounded PAIRING_DIAGNOSTIC control
message. This control has no read or pairing-redemption path. Only the exact packaged popup URL is
allowed, including that same page opened as a persistent extension tab; no new permission, vendor-page
message handler or arbitrary payload is introduced. No automatic pairing retry or host reconnect loop.
If the host/runtime is unavailable, audit persistence cannot be promised; PAIRING_PERSIST_FAILED is
shown when a diagnostic cannot be saved. Popup errors stay visible across status polling.

New append-only `pairing_attempts` table in:
`C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\bridge.sqlite3`.
It contains exactly timestamp, extension_id_match, bootstrap_expired, bootstrap_consumed, handshake_stage
and result_code. Boolean columns use SQLite 1/0; NULL means not checked, never an invented false.
Frontend stages record local client observations; host stages record host checks. ACK_VERIFICATION with
PAIRING_SUCCESS records the worker's verified acknowledgement, while the preceding host checkpoint
only says PAIRING_HANDSHAKE_PENDING. The host rejects unauthenticated success claims.
No actual IDs, file names, payload, secret, nonce, DPAPI blob or exception text is in this table.
Existing consumption/security audit history remains intact. No real audit database migration occurred
here; table creation happens on the next owner-executed native connection.

### Exact owner retry - prepared only

1. Reload the existing unpacked extension in Edge; confirm version 0.1.2. Keep the existing ID and native
   registration. The launcher loads the updated Python module on the next native connection; no registry
   or launcher rebuild is needed for this patch.
2. Open the popup, then **Open persistent pairing panel**. Use this panel for file selection; no DevTools.
   Check local host if needed. Expired/consumed codes indicate a reachable host requiring a fresh package.
3. Prepare one fresh bootstrap locally, because the prior package's age/consumption is uncertain:

```powershell
Set-Location -LiteralPath 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
powershell.exe -NoProfile -File .\scripts\ascend-native.ps1 -Action Pair -OwnerExecuted
```

4. Select `C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\pairing-bootstrap.json`, then
   click **Import selected file**. Do not open/copy the file contents. Allow up to ten seconds.
5. Success is exactly PAIRED + PAIRING_SUCCESS. Otherwise retain only the displayed safe code/remediation
   for diagnosis and stop; do not repeatedly regenerate/retry. An acknowledged package is one-use.
6. Stop at local pairing. Ascend/vendor reads, writes, READ_ONLY_READY and new live attempts remain closed.

Offline validation: 53 targeted extension/native tests passed; browser fixture and unrelated Windows
crypto primitive test excluded. Popup fixtures include valid/malformed/expired/wrong-ID files, same-file
reselection, missing change callback, cancel/no-file, read failure, input reset, popup loss/reopen,
worker loss mid-handshake, synchronous launch failure and incomplete acknowledgement. Host fixtures
cover consumed packages, DPAPI/proof/persistence failures and strict append-only safe metadata. Node
protocol/isolation fixtures, JS syntax and scoped Ruff pass. Two existing dependency warnings remain.
No browser/vendor execution, registry operation or real Pair bootstrap generation occurred.

Extension changes: manifest.json (0.1.2), background.js, pairing.js, popup.html, popup.js, new diagnostics.js.
Host changes: host.py, pairing.py, new diagnostics.py. Tests: test_ascend_native_host.py,
check-ascend-native.js, new check-ascend-pairing-popup.js. Current-state/security documents updated.

## Earlier 0.1.1 foundation handoff (historical)

Status: IMPLEMENTED and OFFLINE TESTED. Source version 0.1.1 awaits owner reload; the owner reported
successful manual installation/enabling of 0.1.0 with no manifest errors. No actual extension ID was
read, guessed or stored in this task. No registry change, real pairing, browser launch, vendor request
or new live attempt occurred. All extension vendor capabilities remain NOT LIVE_VALIDATED.

This foundation implements local Native Messaging pairing/status only. Host, worker, content script
and FreightDesk executor independently keep production reads closed. A valid typed read gets
`read_release_required`; pairing is not an action grant. READ_ONLY_READY cannot occur in this build.
The previous Playwright detail-identity experiment remains permanently closed.

## Local installation capture and registration - prepared, not executed

Run these commands manually from Windows PowerShell in the project directory. None runs Ascend.
Use the existing unpacked extension location; moving it may change its ID. In Edge, manually reload
the extension after the reviewed 0.1.1 source update. Confirm the same restricted permissions.
Copy the actual installed ID from `edge://extensions` or the extension popup. Enter it only at the
local prompt of CaptureId; do not put it or any bootstrap content into chat, command arguments or logs.

```powershell
Set-Location -LiteralPath 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
powershell.exe -NoProfile -File .\scripts\ascend-native.ps1 -Action CaptureId -OwnerExecuted
```

CaptureId accepts exactly 32 lowercase a-p characters and refuses an existing installation. It
creates a runtime installation ID bound to the current Windows user SID, protocol 1, tenant
booking-logistics, actor FreightDesk/Avery and C:\FreightDeskRuntime. It prepares the manifest with
one exact `chrome-extension://<locally entered ID>/` allowed origin; no wildcard or guessed ID.
The runtime directory ACL allows the current Windows user and SYSTEM only.

Manual registration command, after capture:

```powershell
powershell.exe -NoProfile -File .\scripts\ascend-native.ps1 -Action Register -Browser Edge -OwnerExecuted
```

The helper uses Windows PowerShell 5.1 and the installed .NET Framework C# compiler. It compiles a
fixed executable launcher under runtime, targeting this checkout's local Python and source path,
then registers only the per-user 32-bit registry-view key:
`HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.freightdesk.ascend_x1`.
The default value is the absolute runtime host-manifest.json path. It refuses a different installation
at that key or an existing host entry in the other per-user registry view. It does not edit HKLM.
The exact caller origin is checked again by Python against installation.json.

This follows the documented [Microsoft Edge Native Messaging registration and stdio model](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging).
`-Browser Chrome` targets the analogous Google\Chrome key only when the same captured ID is actually
installed in Chrome; it is never a fallback. Registration neither pairs nor dispatches a read.

## Explicit local pairing

After registration, the popup's **Check local host** should show PAIRING_REQUIRED. Prepare a bootstrap:

```powershell
powershell.exe -NoProfile -File .\scripts\ascend-native.ps1 -Action Pair -OwnerExecuted
```

In the extension popup, choose **Import runtime-local pairing bootstrap** and select:
`C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\pairing-bootstrap.json`.
Do not open/copy its contents. It contains a short-lived secret and must remain in that restricted
runtime directory. It expires after ten minutes, is usable for one connection, and is removed after
successful host redemption. Expiration invalidates it even if a crash leaves the file behind; Reset
removes it, and Pair replaces it. It is not a reusable configuration backup.

The host key at rest is protected by CurrentUser Windows DPAPI in
`C:\FreightDeskRuntime\Secrets\ascend-native-pairing.dpapi`. No secret is stored in extension storage,
page DOM, source, process arguments or audit. The popup imports the key into worker memory only as a
nonextractable WebCrypto key. Challenge proof and signed messages bind the fresh connection, exact
extension origin, tenant/actor, local installation generation and protocol. Pairing should end at
**PAIRED**, with production reads still disabled.

Every new Pair rotates the generation and revokes the previous connection on its next message.
Session lifetime is ten minutes maximum, with authenticated status checks every 20 seconds.
Handshake/heartbeat response timeout is ten seconds; host frame input timeout is 30 seconds.
Browser restart, extension reload, a discarded worker or host crash requires explicit Pair/import
again. There is no automatic reconnect, replay or persistent browser key. Native ports can keep a
worker alive, but this implementation does not rely on indefinite worker lifetime; see the
[Chrome extension service-worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle).

## Uninstall, reset and re-pair - prepared, not executed

Disconnect in the popup first. Revoke pairing while retaining installation/registration:

```powershell
powershell.exe -NoProfile -File .\scripts\ascend-native.ps1 -Action Reset -OwnerExecuted
```

To re-pair, run the Pair command above and import the new bootstrap. To unregister the exact owned
Edge host and revoke pairing:

```powershell
powershell.exe -NoProfile -File .\scripts\ascend-native.ps1 -Action Uninstall -Browser Edge -OwnerExecuted
```

Uninstall removes only the exact owned registry key. It retains the executable, manifest, installation,
append-only audit and consumed-request ledger. It does not remove the Edge extension. No recursive
deletion occurs. Re-register with Register if needed. Reset/Uninstall never clear consumed requests
or reset any Playwright/vendor grant. A different extension ID requires an explicit installation
migration; these helpers will not silently rebind it. Relocating Python/source requires launcher rebuild.

## Host and state contract

Native stdio uses a four-byte little-endian byte length followed by UTF-8 JSON, capped at 64 KiB
in either direction. It handles fragmented frames, rejects duplicate JSON keys and malformed/versioned
messages, caps each connection at 64 messages, and terminates after an error without retrying.
No TCP listener, browser launch, shell invocation or vendor client exists in the host.
The fixed C# launcher relays binary stdio to Python and discards stderr; only framed safe replies reach
native stdout. Safe audits contain operation/outcome, timestamp, tenant and actor, never payloads,
pairing material, provider values or browser/session identifiers. UUID request and pairing consumption
is durable in bridge.sqlite3. SQLite triggers reject UPDATE/DELETE of audit and consumption records.

The strict seven-command read contract remains GET_SESSION_STATE, GET_ACTIVE_LOADS, FIND_LOAD,
OPEN_LOAD_READONLY, READ_LOAD, READ_STOPS and READ_ASSIGNMENT, each prefixed ASCEND_. All writes,
unknown commands, JS/eval/script/shell, arbitrary selectors/URLs, wrong tenant/actor/version and
unbound load requests fail closed. No live command dispatch is implemented in this foundation.
Only the packaged popup may initiate pairing; content scripts, page messages and other extensions
cannot connect or authorize commands. Restriction remains https://ascendtms.com/* with nativeMessaging
only, no cookies/history/all-sites permissions and no raw HTML export.

| Popup state | Meaning |
|---|---|
| OFFLINE_PROTOTYPE | Fresh worker; no connection attempted |
| HOST_NOT_REGISTERED | Browser reports missing native host |
| PAIRING_REQUIRED | No usable bootstrap, explicit disconnect, expired/consumed pairing, or missing local setup |
| PAIRED | Local authenticated pipe only; production reads remain disabled |
| HOST_UNAVAILABLE | Host exits, cannot start, or response deadline expires; no automatic reconnect |
| READ_ONLY_READY | Reserved for a separately approved and tested read release; unreachable in 0.1.1 |
| ERROR | Invalid host message, identity/protocol/MAC/replay failure or other closed gate |

## First live read-only validation plan - not an executable grant

Before a live release, finish and offline-test policy-bound controller dispatch, explicit owner-tab
binding, navigation/reload invalidation, bounded post-open stabilization and an identity-only receipt.
The current OPEN fixture acknowledgement explicitly says identity_verified=false; do not call
READ_LOAD simply to bypass that gap, and do not flip production switches to simulate readiness.

After those gates and separate owner authorization:

1. Owner opens Ascend normally in Edge and logs into Booking Logistics. Tenant identity remains
   OWNER_ATTESTED unless a reliable provider account identifier is actually observed.
2. Confirm the explicitly selected tab's exact https://ascendtms.com origin and authenticated context;
   use the registered, paired Native Messaging connection, never Playwright substitution.
3. FreightDesk requests ASCEND_GET_SESSION_STATE, then ASCEND_GET_ACTIVE_LOADS.
4. Require a fresh board for the explicitly approved operating date to reconcile exactly eight pickups
   and three deliveries. Do not force counts or reuse the old 2026-09-11 hash as current evidence.
   Stop on a mismatch, incomplete scope or uncertain grid identity.
5. Owner approves exactly load 1755. Bind its exact unique row and current board revision, request
   ASCEND_FIND_LOAD, then ASCEND_OPEN_LOAD_READONLY once from that row's approved opener.
6. Observe only identity evidence in the resulting same-page UI after bounded stabilization. Require
   a deterministic provider-backed row/opener/detail relationship; a click or owner assumption is
   insufficient. Save only sanitized identity evidence under runtime.
7. Stop on success or uncertainty. No READ_LOAD/READ_STOPS/READ_ASSIGNMENT, operational extraction,
   other loads, notes, Save, Submit, communications, other vendors or canonical mutation in this test.

No live run ID or grant is created here. If the board no longer matches the owner's 8/3 scope, obtain
fresh scope rather than improvising another test. The closed Playwright identity gate remains closed.

## Offline verification and remaining deployment risk

Final results: 45 targeted Python tests passed; one existing browser fixture intentionally excluded.
Both Node fixture scripts, JavaScript syntax, scoped Ruff, PowerShell syntax and Windows .NET Framework
launcher compilation passed. No compiled host execution. Two existing dependency warnings remain.

```powershell
.\.tools\python\python.exe -m pytest tests/test_ascend_native_host.py tests/test_ascend_extension.py -k 'not dom_fixtures' --basetemp=C:\FreightDeskRuntime\Data\TestRuns\native-host-scoped-complete
node scripts/check-ascend-extension.js
node scripts/check-ascend-native.js
```

Targeted Python host/extension tests exclude the browser fixture test. Node VM tests use mocked Chrome
ports/timers only and cover restart/reload, missing/crashed host, expiry, wrong binding, protocol/MAC/
replay, oversize, missing runtime and disabled read release. Python-to-WebCrypto vectors verify actual
framing/authentication conventions, including Unicode canonicalization. Windows SID/DPAPI are checked
with public fixture bytes in memory only. The C# launcher compiles under TestRuns but is not launched.
PowerShell helpers are syntax-checked only; registry and ACL changes are not deployment-validated.

Remaining risks: actual Edge-to-host startup/pairing has not been observed; launcher is unsigned and
depends on the current source/Python installation; enterprise policy or antivirus may block it.
Unpacked ID changes, worker loss and host crashes require deliberate recovery. Same-user malware or
compromised OS/browser can defeat local process/file controls. Real Ascend detail identity, production
tab routing, controller transport and operational field semantics remain unverified/unreleased.

## Files added or changed in this foundation

Added:

- executors/ascend_extension/host.py and pairing.py
- scripts/ascend_native_host.py, ascend_native_setup.py, ascend-native.ps1 and native_host_launcher.cs
- extensions/ascend-x1/pairing.js and popup.js
- tests/test_ascend_native_host.py and scripts/check-ascend-native.js
- docs/ASCEND_NATIVE_MESSAGING.md

Changed:

- executors/ascend_extension/native.py and contracts.py
- extensions/ascend-x1/manifest.json, background.js, contract.js and popup.html
- scripts/check-ascend-extension.js
- CURRENT_STATE.md, KNOWN_ISSUES.md, DECISIONS.md, SECURITY.md, AGENTS.md and LIVE_POC.md
- docs/ASCEND_EXECUTOR_PIVOT.md
