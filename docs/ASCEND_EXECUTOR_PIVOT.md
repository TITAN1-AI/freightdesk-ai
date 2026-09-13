# Ascend X1: executor pivot assessment and offline prototype

Current: owner reports LIVE_VALIDATED 0.1.2 local pairing transport. Source 0.2.0 implements the
offline-tested identity-only controller; see [current owner handoff](ASCEND_X1_READONLY.md).
No extension Ascend read is LIVE_VALIDATED yet. The Playwright identity closure below is unchanged.

Latest 2026-09-11: owner reports 0.1.0 installed/enabled in Edge. Source 0.1.1 adds the offline native
host, explicit local ID capture, registration and pairing foundation. See
[Ascend Native Messaging handoff](ASCEND_NATIVE_MESSAGING.md) for current commands and limits.
No real registry change/pairing or extension Ascend read occurred here. Production read release stays
closed. The original prototype assessment below remains background; its missing-pairing statements
are superseded by the newer offline foundation, not by production validation.

## Decision and evidence

Prefer an authenticated browser extension bridge as the Customer Zero interactive executor candidate.
Retain Playwright for the proven board workflow and future unattended jobs only where deterministic
behavior is established. Do not delete it or label unattended execution/session reuse LIVE_VALIDATED.
Playwright load-detail identity experiments are CLOSED. No new attempt, bound increase or grant reset.

Local read-only ledger inspection confirms final attempt owner-ascend-final-identity-1755-20260911-01
is consumed: TARGETED_BOUND_EXCEEDED / targeted_causal_bound_exceeded, board_tables measured 9 versus
maximum 8, pivot_required=true, production_writes=false. It saved no opener record or identity contract.
The final run did not test the resulting panel's identity; it stopped during exact-row preparation.
The accumulated board/session evidence and earlier owner-observed opener behavior remain useful,
but none establish a reusable provider row-to-panel identity contract.

| Option | Evidence and benefit | Remaining limitation | Decision |
|---|---|---|---|
| Extension bridge | Runs in the owner's selected authenticated tab; can observe actual selection events and retain DOM object references before/after an interaction | Same provider DOM; isolated content scripts do not gain framework internals or a reliable identity field automatically | Primary interactive prototype; production proof pending |
| Provider-evidence-supported row-bound reads | Exact Load ID column, data row and opener association are supported by prior board evidence | Selection alone does not rule out stale panels, delayed rendering, unrelated modals, reassignment or changed board state | Accept board-row facts only; do not attribute detail values without a provider binding |
| Existing Playwright | Authenticated-session/Active Loads and exact 11-load, 8/3 reconciliation evidence | Detail identity never established; final experiment exhausted | Preserve code and proven board capabilities; no further detail-identity experiments |

Option B cannot currently meet the unchanged detail identity standard. It must never authorize writes
on this evidence. Any future write still requires independent owner approval, policy, tenant/actor,
fresh shipment/version checks, a provider-bound detail context, idempotency and post-action verification.
The bridge has no write commands or write-dispatch path in X1.

Content scripts share the DOM while running in an isolated JavaScript world; that separation is useful
for a fixed executor but does not reveal the application's private JavaScript state. This is a design
inference from the [Chrome content-script model](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts),
not new Ascend evidence. No architecture blocker was found; identity observation, private pairing,
deployment and live DOM contracts remain prerequisites to production connection.

## Architecture and authority

The existing executors.interfaces.BrowserExecutor is a DOM-primitive protocol. X1 adds an optional
TypedBrowserReadExecutor capability and AscendExtensionExecutor with execute_read(ReadCommand).
It retains the protocol's navigate/read/wait_ready surface, but rejects generic navigation and selector
reads; only session_state is mapped. This is intentionally not a transparent replacement for a legacy
selector-based adapter. Existing Playwright BrowserExecutor consumers remain unchanged.

```text
FreightDesk policy / grants / tenant / actor / canonical versions / audit
    -> typed read command authority
        -> AscendExtensionExecutor -> authenticated native pipe -> MV3 worker -> isolated content reader
        -> existing Playwright BrowserExecutor -> established bounded board adapter
        -> future OpenClaw / ComputerUse adapters (not implemented or enabled)
```

FreightDesk owns action decisions, trusted principal binding, allowed load scope, pause/takeover,
approvals, version freshness, audit, retries and verification. The extension receives no model-generated
JavaScript, URL, selector, arbitrary method or free-form action. Provider page text is data, not policy.
Results remain reviewable provider observations/proposals and never mutate canonical shipments.

## Transport comparison

| Transport | Authentication and local boundary | Costs/risks | X1 recommendation |
|---|---|---|---|
| Native Messaging | Browser launches a pinned registered local host; exact extension allowlist; add private pairing challenge, HMAC-bound session and ordered messages | Installer/host packaging, per-browser extension ID binding and private pairing lifecycle required | Prefer for Customer Zero: no listening socket, origin/CORS service or public endpoint |
| Authenticated loopback HTTP/WebSocket | Bind loopback only; exact extension Origin; private pairing and authenticated per-message session; reject Host/DNS rebinding, browser cross-origin requests and replays | Browser-accessible listener, port conflicts, Origin/CORS configuration, session/CSRF and local process threat management | Viable alternative if native deployment proves impractical; no listener implemented |

Native Messaging uses a registered local application and browser-managed stdio; the host manifest
allows exact extension origins. See [Chrome Native Messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)
and [Microsoft Edge Native Messaging](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging).
Windows framing uses length-prefixed binary messages. The prototype enforces a smaller 64 KiB message
limit and rejects malformed framing. No registry changes, native host process or network listener was created.

The Python authentication component is fixture-tested: exact caller origin, fresh challenge, private
pairing-key proof, session ID, sequence numbers, HMAC integrity and direction separation. Replay,
reflection and wrong-principal messages fail. Browser allowlisting/argv alone are not sufficient app-level
authentication. Same-user malware or a compromised browser/OS is outside the protection of this design.

The subsequent 0.1.1 foundation implements explicit runtime-only provisioning/DPAPI, a fixed native
launcher, owner-run registration/reset helpers and in-memory browser pairing. No real pairing or host
registration has been executed. Pairing cannot change any production connection switch. Policy-bound
controller routing, tab lifecycle and identity-only receipts remain separate release prerequisites.
No cookie permission is needed. See ASCEND_NATIVE_MESSAGING.md for current local procedures.

## X1 prototype behavior

Unpacked MV3 manifest: host permission and content match ONLY https://ascendtms.com/*; nativeMessaging
is the only API permission. No history, tabs permission, all-sites, cookie, password, debugger, webRequest,
externally_connectable or exposed page resources. CSP permits only packaged extension code; no eval or
outbound fetch/WebSocket connection. Content bootstrap runs in an isolated top-frame world and installs
only a runtime-message listener. Both worker and content production switches are false; installation
does not read Ascend, send native messages, attach selection listeners, navigate or click anything.

Seven exact typed operations are implemented in the fixture reader and Python contract:

| Command | Bounded behavior |
|---|---|
| ASCEND_GET_SESSION_STATE | Approved navigation markers, login-presence boolean and safe path only |
| ASCEND_GET_ACTIVE_LOADS | One visible data-bearing 33-column grid; ignores header-only clones and decorative tables; at most 100 rows |
| ASCEND_FIND_LOAD | Exact unique row ID plus matching board revision |
| ASCEND_OPEN_LOAD_READONLY | Exact same-row read opener, fixed destination/control checks, retain row/control/before-panel references; reports identity_verified=false |
| ASCEND_READ_LOAD | Require unchanged board revision and deterministic detail identity; return bounded board facts and detail identity/section metadata |
| ASCEND_READ_STOPS | Identity-gated section presence; actual stops/appointments remain null, mapping UNKNOWN |
| ASCEND_READ_ASSIGNMENT | Identity-gated presence flags sourced explicitly from the board, never driver/contact values |

Fixed future write names (SET_DRIVER, UPDATE_STATUS, ADD_NOTE, UPLOAD_DOCUMENT, SAVE_LOAD) are absent
from both allowlists. Unknown command keys, scripts, selectors, tenant/actor overrides and unbound load
reads fail. An OPEN acknowledgement is not identity proof. No production tab selection/dispatch or
unattended command poller is wired up. The fixture-only reader is not callable from the provider's page
in the installed isolated world. Bootstrap does not accept window.postMessage or other extensions.

Identity strategies: explicit matching detail field; load-specific opener identity plus direct provider
reference to one resulting panel; or a provider selected/expanded transition plus that unique binding.
Conflict, multiple panels, absent binding, unknown session and stale revisions fail. A mere click never
qualifies. Evidence includes exact row ID, observed positional row/opener/panel paths, relationship
attribute, strategy and observation-only scope. Python audit hooks preserve this sanitized relationship
with request ID, FreightDesk timestamp and bound tenant/actor. Positional paths are observation evidence,
not a promised stable general selector contract.

Real user selection observation has a separate trusted-event helper; it cannot itself grant a read.
Until the controller binds a fresh board revision, that selected context is deliberately unreadable.
Production wiring must add authorized before-selection capture, bounded stabilization, navigation/frame
lifecycle invalidation and version-bound receipts. This prototype does not claim those live behaviors.

Presence booleans are derived structural observations, not verified assignment completeness. Dates are
rendered date prefixes; no timezone inference/conversion. Known status text is preserved; unknown status
vocabulary remains UNKNOWN. Board coverage remains VISIBLE_BOARD_ONLY. No carrier/driver identity text,
phone, financial value, notes, raw HTML, cookies, session token or authentication header is returned.
Actual stops, appointments and non-fixture detail mapping remain unknown.

## Manual installation — offline prototype only

1. Do not run any Playwright identity command. The final grant remains consumed and the entry point is disabled.
2. In Edge, manually open edge://extensions (Chrome: chrome://extensions). Enable Developer mode.
3. Choose Load unpacked and select the project folder `extensions/ascend-x1` containing manifest.json.
4. Inspect permissions: only Ascend host access plus Native Messaging. The toolbar popup must report
   “Offline prototype. Production connection is disabled.” Do not enable a native host or connection.
5. Keep Ascend live validation stopped. Loading the extension is not authorization to begin a new test.

Use source files only; no browser profile, runtime evidence or credentials belong in the extension
directory. A future packaged deployment should copy reviewed assets to the nonsynced FreightDesk runtime
installation directory and pin the resulting extension ID locally. Unpacked ID/location consistency,
host signing/registration and owner-approved private pairing need separate deployment verification.

## First read-only live validation plan — not authorized/executed here

1. Finish/review private pairing, host packaging, response receipts and lifecycle/stabilization gates
   offline. Confirm exact extension host permissions, principal binding, mutation denial and audit storage.
2. Obtain owner approval for one bounded X1 session in the already-authenticated dedicated Ascend tab.
   Pin tenant identity as OWNER_ATTESTED unless a provider account identifier is actually observed.
3. Grant session-state and Active Loads reads only. Reconcile current owner-approved operating date,
   IDs and counts afresh; the historical 2026-09-11 manifest is not perpetual authorization.
4. Owner selects one exact approved load while the bridge captures the before-selection relationship.
   Capture sanitized opener and stable resulting container evidence. Require provider-backed identity.
5. Only after exact identity succeeds, separately enable bounded read-load/section-presence operations.
   Compare a small permitted field set against the owner UI. Unknown fields remain unknown.
6. Stop on uncertainty or missing provider binding; do not silently adopt row-bound detail identity.
   Produce an owner-reviewed observation report, close the grant and disconnect. No writes or other vendors.

No new extension live attempt ID/grant is created by this plan. No LIVE_VALIDATED promotion from mocks.

## Offline validation and files

`extensions/ascend-x1`: manifest, popup, command contract, fixed DOM reader, dormant worker/content bootstrap.
`executors/ascend_extension`: typed Python contract, policy-gated executor, safe result projection,
audit hooks, native framing/authentication and disconnected transport interface.
`executors/interfaces.py`: optional typed-read protocol; original interfaces retained.
`tests/test_ascend_extension.py`, `scripts/check-ascend-extension.js`: auth, scope, injection, DOM fixture,
identity/conflict/freshness, privacy, bootstrap isolation and no-connection checks.

No native host registered, unpacked extension installed, vendor browser opened or production request
performed during implementation. Tests use synthetic intercepted fixtures and runtime test profiles only.

Results: 19 scoped regression tests passed (extension + retained causal fixtures); final extension suite
14 passed. The additional unchanged-panel regression passed in the nine-scenario DOM fixture test.
Native bootstrap isolation checks, JS syntax and scoped Ruff checks passed. Two existing dependency
deprecation warnings remain. These are IMPLEMENTED/TESTED results, not vendor LIVE_VALIDATED evidence.
