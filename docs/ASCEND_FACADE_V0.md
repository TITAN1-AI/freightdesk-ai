# Ascend facade v0

Read endpoints for product/Avery over **portable UI harvest**, not the X1 native host and not an
Ascend retail API. Demo-gated (`FREIGHTDESK_MODE=demo`). General writes stay out of scope; status /
assign / expenses are **stubs** with receipts. Capability matrix:
[ASCEND_CAPABILITY_MAP_V0.md](ASCEND_CAPABILITY_MAP_V0.md).

| Claim | v0 |
| --- | --- |
| Source | Last accepted `POST /v1/portable/harvest` snapshot |
| Coverage | VISIBLE_BOARD_ONLY |
| Evidence | CANDIDATE / CANDIDATE_ONLY |
| LIVE_VALIDATED | **false** |
| Production writes | **false** — no Save, assign, notes, uploads, New Load |
| Empty harvest | `loads: []` and `harvest_available: false` (HTTP 200, never 500) |
| Revoked lease | Last snapshot remains readable; new harvest posts are rejected |

## Routes

`GET /v1/ascend/status` — lease/harvest/actuator health: lease active/status, harvest count,
last harvest time, extension last seen (last accepted post), row count.

`GET /v1/ascend/loads` — stable board shape: `load_id`, `pick_date`, `drop_date`, plus raw
candidate fields under `fields` (currently sanitized `load_status`).

`GET /v1/ascend/loads/{id}` — last known CANDIDATE fields for one harvested load. Missing harvest
or unknown ID is HTTP 200 with `found: false` and `fields: {}` (never 500). Atlas Load Basics
names are listed without inventing values.

`GET /v1/ascend/capabilities` — READ / WRITE / AUTOMATION map. Writes are not LIVE.

`POST /v1/ascend/loads/{id}/status` — stub. HTTP 501 `NOT_IMPLEMENTED`, intended policy
**APPROVAL_REQUIRED**. No Save Load.

`POST /v1/ascend/loads/{id}/assign` and `.../expenses` — HTTP 403 **FORBIDDEN** stubs.

Auth (any one):

- Demo **agent** Bearer from `POST /v1/agent/session` or `Tokens/demo-agent-token.txt`
  (Avery / agent path; no popup). See [AGENT_ASCEND_API_V0.md](AGENT_ASCEND_API_V0.md).
- Local demo owner session (dashboard cookie or owner `Authorization: Bearer`).
- Portable **device** token from the extension popup (`POST /v1/portable/session`).

These paths are a **facade**. They do not prove Ascend API support, operational field semantics,
or Booking Logistics live cutover. See [PORTABLE_BRIDGE.md](PORTABLE_BRIDGE.md) and
[extensions/portable-bridge/README.md](../extensions/portable-bridge/README.md) for the harvest loop.
