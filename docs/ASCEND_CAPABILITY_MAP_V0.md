# Ascend capability map v0

Closed-loop map of the **de facto AscendTMS surface** that Avery/agents call over HTTP, with
FreightDesk Bridge as the hands on an authenticated Ascend tab. Demo-gated. Not a retail Ascend
API. **Not LIVE_VALIDATED.**

Source of truth for routes/policy/status: [config/ascend-bridge-capabilities.json](../config/ascend-bridge-capabilities.json).
Atlas selectors: [extensions/portable-bridge/atlas.json](../extensions/portable-bridge/atlas.json)
(`textarea#scratch` private note, `#notes` public note, Load Basics labels). Machine-readable
copy: `GET /v1/ascend/capabilities`.

| Claim | v0 |
| --- | --- |
| Actuator | Portable Bridge on an authenticated Ascend session |
| Agent API | HTTP + demo Bearer (`DEMO_AGENT`) |
| Evidence | CANDIDATE / CANDIDATE_ONLY unless noted |
| Writes | Receipts only; no silent Save Load |
| Next LIVE field after private-note **VERIFIED** | **status change** (`POST /v1/ascend/loads/{id}/status`, APPROVAL_REQUIRED) — **IMPLEMENTED / TESTED**, not LIVE_VALIDATED |
| Out of scope | X1 native host, Playwright secret path, money/assign LIVE |

Private-note write (`#scratch` + `WHOLE_FORM_SAVE`) is FIELD LIVE_VALIDATED for the
1763 SAVE_STAY already_open path only (PR #8). Status write is IMPLEMENTED on this
slice and is not LIVE_VALIDATED.

## READ

| Capability | Route | Policy | Status | Evidence |
| --- | --- | --- | --- | --- |
| Active Loads board | `GET /v1/ascend/loads` | ALLOW | **IMPLEMENTED / TESTED** | CANDIDATE, VISIBLE_BOARD_ONLY |
| Load Basics fields (atlas / harvest cache) | `GET /v1/ascend/loads/{id}` | ALLOW | **IMPLEMENTED / TESTED** | Last known CANDIDATE board fields; empty-safe if missing |
| Status facade | `GET /v1/ascend/status` | ALLOW | **IMPLEMENTED / TESTED** | Lease/harvest health, CANDIDATE |
| Capability catalog | `GET /v1/ascend/capabilities` | ALLOW | **IMPLEMENTED / TESTED** | This matrix |

`GET /v1/ascend/loads/{id}` returns harvested `load_id` / `pick_date` / `drop_date` /
`fields.load_status` when that ID is in the last accepted harvest. Unknown or unharvested IDs
return HTTP 200 with `found: false` and `fields: {}` (never 500). Atlas field names are listed
without inventing values. Load Basics selectors stay CANDIDATE until a later detail harvest.

## WRITE

| Capability | Route | Policy default | Status | Notes |
| --- | --- | --- | --- | --- |
| Private / internal note | `POST /v1/ascend/loads/{id}/notes` | **APPROVAL_REQUIRED** | **IMPLEMENTED** | Atlas `textarea#scratch`. FIELD LIVE_VALIDATED for 1763 SAVE_STAY already_open only. |
| Public note | none | **FORBIDDEN** | **FORBIDDEN** | Atlas `#notes`. Never typed. |
| Status change | `POST /v1/ascend/loads/{id}/status` | **APPROVAL_REQUIRED** | **IMPLEMENTED** | Catalog statuses except UNKNOWN. WHOLE_FORM_SAVE with explicit flag. Not LIVE_VALIDATED until Avery VERIFIED. |
| Assign carrier | `POST /v1/ascend/loads/{id}/assign` | **FORBIDDEN** | **FORBIDDEN** | HTTP **403** stub. Money/assign stay forbidden. |
| Expenses / rates | `POST /v1/ascend/loads/{id}/expenses` | **FORBIDDEN** | **FORBIDDEN** | HTTP **403** stub. |
| Documents upload | none | **FORBIDDEN** | **NOT_STARTED** | No LIVE route. |
| Communications | none | **FORBIDDEN** | **NOT_STARTED** | No LIVE route. |

Write receipts always include `silent_save_forbidden: true`, `live_validated: false`, and
`production_writes: false`. An approval token on assign/expenses stubs does not execute Save,
assign, or money moves. Status is IMPLEMENTED under **APPROVAL_REQUIRED** and is not LIVE.

## AUTOMATION

| Capability | Entry | Policy | Status |
| --- | --- | --- | --- |
| Harvest poll | Extension alarm → `POST /v1/portable/harvest` | ALLOW (lease-scoped) | **IMPLEMENTED / TESTED** |
| Lease revoke | `POST /v1/portable/leases/{id}/revoke` | ALLOW | **IMPLEMENTED / TESTED** — last snapshot stays readable |
| Scheduled board sync | none beyond harvest alarm | ALLOW (read) | **NOT_STARTED** — no server-owned schedule |
| Verify-after-write | `GET /v1/ascend/writes/{id}` | APPROVAL_REQUIRED | **IMPLEMENTED** for notes and status. Status not LIVE. |

## Closed-loop rules

1. One capability at a time.
2. Writes are **APPROVAL_REQUIRED** or **FORBIDDEN**. There is no silent Save Load.
3. Every write attempt emits a receipt (`FORBIDDEN`, `NOT_IMPLEMENTED`, or a later VERIFIED/FAILED).
4. Harvest / agent Bearer / PR #8 note write stay independent. This slice is additive on `main`.
5. Demo-gated. No X1 changes. No Playwright-as-secret-extension.

## Agent curl

```bash
AGENT=$(curl -sS -X POST http://127.0.0.1:8787/v1/agent/session \
  | python -c 'import json,sys; print(json.load(sys.stdin)["agent_token"])')

curl -sS http://127.0.0.1:8787/v1/ascend/capabilities -H "Authorization: Bearer $AGENT"
curl -sS http://127.0.0.1:8787/v1/ascend/loads/1763 -H "Authorization: Bearer $AGENT"
curl -sS -X POST http://127.0.0.1:8787/v1/ascend/loads/1763/status \
  -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
  -d '{"status":"Dispatched"}'
# → 403 PENDING_APPROVAL without a one-use token
```

See [ASCEND_WRITE_STATUS_V0.md](ASCEND_WRITE_STATUS_V0.md) for mint → approve → VERIFIED.

See [ASCEND_FACADE_V0.md](ASCEND_FACADE_V0.md), [AGENT_ASCEND_API_V0.md](AGENT_ASCEND_API_V0.md),
and [PORTABLE_BRIDGE.md](PORTABLE_BRIDGE.md).
