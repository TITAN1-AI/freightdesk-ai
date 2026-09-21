# Portable Bridge v0 — engineering handoff

Track **B** product foundation. Parallel to X1; it does not replace Booking Logistics live ops
or the Windows native host. Product north star: [PORTABLE_BRIDGE_PRODUCT.md](PORTABLE_BRIDGE_PRODUCT.md).
Load and test steps: [extensions/portable-bridge/README.md](../extensions/portable-bridge/README.md).

## What shipped

- MV3 extension `extensions/portable-bridge/` named **FreightDesk Bridge**. No `nativeMessaging`.
- Demo lease API under `/v1/portable/*` (session, leases, revoke, harvest, status).
- Demo **agent** Bearer under `/v1/agent/session` for Avery/API callers (no popup).
  See [AGENT_ASCEND_API_V0.md](AGENT_ASCEND_API_V0.md).
- Ascend **facade** `GET /v1/ascend/loads`, `GET /v1/ascend/loads/{id}`, and
  `GET /v1/ascend/status` over stored harvest. Capability map:
  [ASCEND_CAPABILITY_MAP_V0.md](ASCEND_CAPABILITY_MAP_V0.md).
  See [ASCEND_FACADE_V0.md](ASCEND_FACADE_V0.md).
- Note **read-back** `GET /v1/ascend/loads/{id}/notes` and
  `POST /v1/ascend/loads/{id}/notes/capture` (ALLOW, not LIVE).
  See [ASCEND_READ_NOTES_V0.md](ASCEND_READ_NOTES_V0.md).
- First write: APPROVAL_REQUIRED private internal note
  (`POST /v1/ascend/loads/{id}/notes`). See [ASCEND_WRITE_NOTE_V0.md](ASCEND_WRITE_NOTE_V0.md).
- Second write: APPROVAL_REQUIRED load-status change
  (`POST /v1/ascend/loads/{id}/status`). See [ASCEND_WRITE_STATUS_V0.md](ASCEND_WRITE_STATUS_V0.md).
  FIELD LIVE_VALIDATED for Avery 1777 SAVE_STAY In Transit↔Dispatched only.
- Atlas bindings in [extensions/portable-bridge/atlas.json](../extensions/portable-bridge/atlas.json)
  (`textarea#scratch`, `#notes`, Load Basics labels) for read/write paths.
- VISIBLE_BOARD_ONLY Active Loads harvest, stored as **CANDIDATE** evidence.
- CORS for `chrome-extension://` origins on the portable prefix only. Other demo routes stay same-origin.
- After Load unpacked, the service worker tries isolated-world reinject on open Ascend tabs
  (and a conservative `/` or `/loads` reload on install/update only). If that is blocked, the
  popup/README tell the owner to reload Active Loads and press Start harvest again.

## What this is not

- Not LIVE_VALIDATED Ascend.
- Not cloud OAuth / tenant billing / store listing.
- Not a general write path. Status is FIELD LIVE_VALIDATED for Avery 1777 SAVE_STAY
  In Transit↔Dispatched only. Assign, expenses, public-note writes, uploads and New Load
  remain FORBIDDEN or out of the capture. Private-note write is FIELD LIVE_VALIDATED for
  Avery 0.1.10 / load 1763 / SAVE_STAY / already_open only. Note read-back and board ops
  harvest are IMPLEMENTED, not LIVE. See [ASCEND_READ_NOTES_V0.md](ASCEND_READ_NOTES_V0.md),
  [ASCEND_WRITE_NOTE_V0.md](ASCEND_WRITE_NOTE_V0.md) and
  [ASCEND_WRITE_STATUS_V0.md](ASCEND_WRITE_STATUS_V0.md).
- Not a cutover of BL operations onto portable leases.

## Threat model (v0)

| Risk | v0 handling | Remaining gap |
| --- | --- | --- |
| Token theft from `chrome.storage` | Localhost-only API, hashed tokens at rest, short TTL, revoke | Real cloud tokens need device-bound storage and rotation |
| Malicious page | Isolated world, origin allowlist, content script never holds the lease token | Store listing must keep host permissions narrow |
| Lease overreach | Scope is VISIBLE_BOARD_ONLY; writes flags rejected; named ops board cells only (no income/expenses, no #scratch) | Cloud policy engine must remain the source of capability |
| Provider origin calling the API | `https://ascendtms.com` is denied as a CORS origin | Cloud must keep the same deny |
| Demo session minting | Local process + `X-FreightDesk-Portable: 1` | Replace with OAuth / device code |
| Agent API auth | Demo Bearer (`DEMO_AGENT`) or bootstrap file | Cloud OAuth, multi-tenant, rotation |

X1 (`extensions/ascend-x1/` + `FreightDeskAscendHost.exe`) is unchanged Track A.
