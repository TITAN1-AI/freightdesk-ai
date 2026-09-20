# Ascend write note v0 — private internal note

First FreightDesk **write** on the portable / agent facade. Avery (or any agent) calls HTTP.
The portable Bridge types a **private / internal** note on an authenticated Ascend tab.
The agent never clicks Ascend UI.

**Not LIVE_VALIDATED.** Avery must field-pass before any live claim.
X1 / native host is unchanged. Harvest and agent Bearer reads stay as they were.

| Claim | v0 |
| --- | --- |
| Action | `ASCEND_ADD_INTERNAL_NOTE` |
| Policy | **APPROVAL_REQUIRED** (default). Other writes stay unavailable / FORBIDDEN at this facade |
| Auth | Same as the read facade: demo agent Bearer, owner session, or portable device token |
| Actuator | Portable Bridge on an already-authenticated Ascend tab |
| Evidence | CANDIDATE receipts. `live_validated=false`. `production_writes=false` |
| Note kind | Private / internal only. Public Notes, Load Posting Notes, customer comms are blocked |
| Out of scope | Status change, assign, money, New Load, uploads, Save Load, send |

## Curl: session → approval → POST note → receipt

Demo server: `FREIGHTDESK_MODE=demo` (default). Bridge must sit on an Ascend tab for
`VERIFIED`; without it the POST returns `DISPATCHED` and you poll.

```bash
# 1) Agent session (or Tokens/demo-agent-token.txt)
AGENT=$(curl -sS -X POST http://127.0.0.1:8787/v1/agent/session \
  | python -c 'import json,sys; print(json.load(sys.stdin)["agent_token"])')

# 2) Mint a one-use demo approval (also: dashboard “Mint demo note approval”)
APPROVAL=$(curl -sS -X POST http://127.0.0.1:8787/v1/ascend/approvals \
  -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
  -d '{"action":"ASCEND_ADD_INTERNAL_NOTE","load_id":"1763"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["approval_token"])')

# 3) Request the write. Missing/invalid approval → HTTP 403, status PENDING_APPROVAL
curl -sS -X POST http://127.0.0.1:8787/v1/ascend/loads/1763/notes \
  -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
  -d "{\"text\":\"internal ops note\",\"approval_token\":\"$APPROVAL\"}"

# 4) If status is DISPATCHED, poll until VERIFIED or FAILED (no silent success)
# curl -sS http://127.0.0.1:8787/v1/ascend/writes/{write_id} -H "Authorization: Bearer $AGENT"
```

Receipt fields: `write_id`, `status` (`PENDING_APPROVAL` | `DISPATCHED` | `VERIFIED` |
`FAILED`), `evidence_class`, `verified`, `note_present`, `text_digest`, `error_code`.
Note text is never returned on the agent receipt or audit.

## How demo approval is granted

Default ActionPolicy `ASCEND_ADD_INTERNAL_NOTE = APPROVAL_REQUIRED`. A POST without a
valid unused token is rejected (`403`, `PENDING_APPROVAL`).

Mint a 15-minute, one-use token bound to `load_id` (and optionally the intended text):

1. **Owner dashboard** — Ascend panel → load ID → **Mint demo note approval**. Uses the
   local owner session (`X-FreightDesk-Local: 1`).
2. **`POST /v1/ascend/approvals`** — same body:
   `{"action":"ASCEND_ADD_INTERNAL_NOTE","load_id":"1763"}`.
   Optional `"text"` binds the digest so a different note cannot reuse the token.

This mint is a **demo grant**, not cloud OAuth and not a production write authority.

## Verify-after-write

`VERIFIED` requires a read-back that the private/internal note is present. A Bridge
completion with `verified=true` and `note_present=false` is stored as `FAILED`
(`verify_without_presence`). Tests use an in-process fixture executor that appends
then reads the same ledger. Live Bridge: type into the unique Private/Internal Notes
control, commit only via an Add/Save Note control, then reread.

## Bridge path

Portable Bridge 0.1.2 polls `GET /v1/portable/writes/pending` with the device token,
opens the exact load row, types **Private Notes** / **Internal Notes** only, and posts
`POST /v1/portable/writes/{id}/complete`. Harvest remains read-only. Content still
rejects `ASCEND_SAVE`, assign, status, rates, New Load, public notes, and send.

Observed UI vocabulary (repo, not an atlas): historical export columns `Notes` /
`Private Notes`; ops discovery looks for textareas labeled `Private Notes` or `Notes`.
v0 writes **only** Private/Internal Notes. A lone public `Notes` control is
`PUBLIC_NOTE_BLOCKED`. A generic **Save Load** / **Submit** is
`NOTE_SAVE_CONTROL_UNVERIFIED` — we do not click it.

## API

| Method | Path | Role |
| --- | --- | --- |
| `POST` | `/v1/ascend/approvals` | Mint demo note approval |
| `POST` | `/v1/ascend/loads/{load_id}/notes` | Queue / execute the write |
| `GET` | `/v1/ascend/writes/{write_id}` | Poll receipt |
| `GET` | `/v1/portable/writes/pending` | Bridge claim (device/agent token) |
| `POST` | `/v1/portable/writes/{write_id}/complete` | Bridge verify result |

Existing `GET /v1/ascend/status`, `GET /v1/ascend/loads`, `/v1/agent/session`, and
`/v1/portable/leases|harvest` are unchanged.

## LIVE field gaps (Avery)

These stay UNKNOWN until a field pass. Do not promote LIVE_VALIDATED from fixtures.

- Exact live Private Notes / Internal Notes control (label, tab, panel vs modal)
- Whether a note-specific **Add Note** exists vs only **Save Load**
- How to open a load from Active Loads without changing status or assignment
- Whether the typed text remains in the textarea or moves to a note list
- SPA settle timing after row activation; tab/section that holds notes
- Multi-tab / missing-tab / stale content behavior beyond `ASCEND_TAB_MISSING`
- Customer-visible vs private distinction on the live form
- Production approval (owner dashboard mint is demo-only)

## What this is not

- Not an Ascend retail API
- Not X1 / native messaging
- Not AUTO_MAP, harvest writes, or operational field semantics
- Not status, assign, rates, New Load, uploads, or outbound comms
