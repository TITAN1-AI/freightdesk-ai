# Agent Ascend API v0

How Avery (or any local agent) authenticates to the Ascend **facade** without the
FreightDesk Bridge popup “Demo sign-in”. Demo-gated (`FREIGHTDESK_MODE=demo`).
Not cloud OAuth. **Not LIVE_VALIDATED** beyond the existing portable harvest.

The extension remains the hands on an authenticated Ascend tab. Agent Bearer only
skips UI for **API auth**. Harvest still requires Bridge on Active Loads.

| Claim | v0 |
| --- | --- |
| Auth | Demo agent token, `Authorization: Bearer` |
| Label | `auth_kind=DEMO_AGENT` — not tenant OAuth |
| Reads | `GET /v1/ascend/status`, `GET /v1/ascend/loads`, `GET /v1/ascend/loads/{id}`, `GET /v1/ascend/loads/{id}/notes`, `GET /v1/ascend/capabilities` |
| Optional | `POST /v1/portable/leases` and revoke, with the same Bearer |
| Harvest | Still `POST /v1/portable/harvest` with a **lease token**, from the Bridge |
| Note capture | `POST /v1/ascend/loads/{id}/notes/capture` (ALLOW). See [ASCEND_READ_NOTES_V0.md](ASCEND_READ_NOTES_V0.md). |
| Writes | Private internal note and load-status change after approval. See [ASCEND_WRITE_NOTE_V0.md](ASCEND_WRITE_NOTE_V0.md) and [ASCEND_WRITE_STATUS_V0.md](ASCEND_WRITE_STATUS_V0.md). Assign and expenses FORBIDDEN. Save, money, New Load stay blocked. |
| LIVE_VALIDATED | **false** |

## Get a token

Mint (idempotent if a bootstrap file or `FREIGHTDESK_AGENT_TOKEN` already exists):

```bash
AGENT=$(curl -sS -X POST http://127.0.0.1:8787/v1/agent/session \
  | python -c 'import json,sys; print(json.load(sys.stdin)["agent_token"])')
```

Or read the runtime bootstrap file after the first mint (Windows owner runtime):

```text
C:\FreightDeskRuntime\Tokens\demo-agent-token.txt
```

Documented relative path: `Tokens/demo-agent-token.txt`. Optional env:
`FREIGHTDESK_AGENT_TOKEN` (minimum 32 characters). TTL is 30 days; `POST` reuses
an unexpired bootstrap/env token. The secret is hashed at rest in the demo store.

```bash
curl -sS http://127.0.0.1:8787/v1/agent/status
# {"signed_in":false,"auth_kind":"DEMO_AGENT","bootstrap_path":"Tokens/demo-agent-token.txt",...}
```

Humans keep using the popup: `POST /v1/portable/session` + `X-FreightDesk-Portable: 1`.
That path is unchanged.

## Read the facade

Lease/harvest is required only if you need a **fresh** board snapshot. If Bridge
already harvested, the agent can read immediately:

```bash
curl -sS http://127.0.0.1:8787/v1/ascend/status -H "Authorization: Bearer $AGENT"
curl -sS http://127.0.0.1:8787/v1/ascend/loads -H "Authorization: Bearer $AGENT"
curl -sS http://127.0.0.1:8787/v1/ascend/loads/1763 -H "Authorization: Bearer $AGENT"
curl -sS http://127.0.0.1:8787/v1/ascend/capabilities -H "Authorization: Bearer $AGENT"
curl -sS http://127.0.0.1:8787/v1/ascend/loads/1763/notes -H "Authorization: Bearer $AGENT"
# Queue Load Basics #scratch / #notes capture (ALLOW, no approval)
curl -sS -X POST http://127.0.0.1:8787/v1/ascend/loads/1763/notes/capture \
  -H "Authorization: Bearer $AGENT"
```

Empty harvest is HTTP 200 with `loads: []` and `harvest_available: false`.
Unknown load IDs are HTTP 200 with `found: false`. See
[ASCEND_CAPABILITY_MAP_V0.md](ASCEND_CAPABILITY_MAP_V0.md).

Private-internal-note writes (APPROVAL_REQUIRED) use the same Bearer after
`POST /v1/ascend/approvals`. See [ASCEND_WRITE_NOTE_V0.md](ASCEND_WRITE_NOTE_V0.md).

## Optional: create a lease

A lease is still required for the Bridge to **post** harvest. The agent can create
one without the popup. The extension on an Ascend tab must still capture the board
(using its own popup lease, or a lease token the operator supplies). Creating a
lease from curl does not harvest.

```bash
curl -sS -X POST http://127.0.0.1:8787/v1/portable/leases \
  -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
  -d '{"origin":"https://ascendtms.com","scope":"VISIBLE_BOARD_ONLY","ttl_seconds":900}'
```

Harvest posts use the returned `lease_token`, not the agent token:

```bash
# Bridge does this on the tab. Agents do not scrape Ascend.
# POST /v1/portable/harvest  Authorization: Bearer $LEASE_TOKEN
```

## What this is not

- Not a retail Ascend API.
- Not FreightDesk Cloud OAuth / device-code / multi-tenant identity.
- Not a substitute for an authenticated Ascend browser session.
- Not Playwright-as-secret-extension.
- Not X1 / native host.
- Not LIVE_VALIDATED operational field semantics or writes.

See [ASCEND_FACADE_V0.md](ASCEND_FACADE_V0.md) and [PORTABLE_BRIDGE.md](PORTABLE_BRIDGE.md).
