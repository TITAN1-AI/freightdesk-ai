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
| Actuator | Portable Bridge 0.1.3 on an already-authenticated Ascend tab |
| Evidence | CANDIDATE receipts. `live_validated=false`. `production_writes=false` |
| Note kind | Private / internal only. Public Notes, Load Posting Notes, customer comms are blocked |
| Out of scope | Status change, assign, money, New Load, uploads, Save Load, Save & Exit, send |

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
`FAILED`), `evidence_class`, `verified`, `note_present`, `text_digest`, `error_code`,
`stage`, `opener_strategy`, `note_label`, `commit_kind`.
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
then reads the same ledger. Live Bridge: type into the unique Private Load Note /
Private Notes / Internal Notes control, commit only via an Add/Save Note control,
then reread. If the only visible commit is **Save Load** or **Save & Exit to Load
Board**, the Bridge does **not** type or click; receipt is `FAILED` /
`NOTE_COMMIT_REQUIRES_OWNER_PATH`.

## Bridge path

Portable Bridge **0.1.3** polls `GET /v1/portable/writes/pending` with the device token.
It does **not** require harvest `ACTIVE_VIEW_UNVERIFIED` to be cleared. Opening a load
is independent of the Active Loads view contract:

1. **Already-open workspace** — unique **Private Load Note** (or Private/Internal Notes)
   and either a matching load identity (heading, Load Number, URL/title) or no conflicting
   other load IDs. This is the 1763 field case (Load Basics + Private Load Note, no board).
2. **Unique row opener** — exact load-id cell plus unique View / Details / Open / id
   control. Harvest board verification is not consulted.
3. **Unique searchbox** — fill the load id, **no Enter / submit**, then the same row
   opener. Historical Playwright 1752 gesture, reused here only as a bounded fill.

If none of those work: `LOAD_OPENER_UNVERIFIED` with `stage` / `opener_strategy` on the
receipt. A private note on the wrong load identity is `LOAD_IDENTITY_UNVERIFIED`.

The Bridge then types **only** if a note-specific **Add/Save Note** exists. It still
rejects `ASCEND_SAVE`, assign, status, rates, New Load, public notes, and send.

Popup **Last write** is separate from harvest. `ACTIVE_VIEW_UNVERIFIED` on harvest does
not mean the note write failed that way.

## Field report — Avery / load 1763 (safe stop)

PASS:

- `403` without approval (`PENDING_APPROVAL`)
- mint + POST → `DISPATCHED` then `FAILED`
- Avery did **not** click **Save Load**

FAIL (Bridge 0.1.2):

- Receipt `FAILED` `LOAD_OPENER_UNVERIFIED` (write_id `4f9959bd…`); note never appeared
- Popup banner showed harvest `ACTIVE_VIEW_UNVERIFIED` (“Active Loads is not verified
  in the current tab.”) — harvest, not the write
- Ascend: **Private Load Note** found
- No note-specific Add/Save Note — only generic **Save & Exit to Load Board**
- Avery correctly treated that as unverified and stopped

0.1.3 changes from that report:

- Opener no longer requires a verified Active Loads grid
- **Private Load Note** is a recognized private control
- **Save & Exit to Load Board** / **Save Load** → `NOTE_COMMIT_REQUIRES_OWNER_PATH`
  (not a silent whole-form save). We cannot prove those buttons commit only the
  private note, so they stay owner-gated and unclicked
- Receipts carry `stage`, `opener_strategy`, `note_label`, `commit_kind`
- Popup **Last write** is distinct from harvest

## Avery re-test checklist (load 1763)

Reload unpacked Bridge **0.1.3**. Keep harvest optional. Sit on an authenticated
Ascend tab — **Active Loads does not need to be the verified view**. Preferred start:
already on load 1763 with **Private Load Note** visible. Then:

1. POST without approval → `403` / `PENDING_APPROVAL` (unchanged)
2. Mint approval + POST → `DISPATCHED`, then poll `GET /v1/ascend/writes/{id}`
3. If a note-specific Add/Save Note exists: expect `VERIFIED` + `note_present=true`
   and the text on the private note. Confirm Avery did not press Save Load
4. If Ascend still only shows **Save & Exit to Load Board**: expect `FAILED` /
   `NOTE_COMMIT_REQUIRES_OWNER_PATH`, `opener_strategy=already_open`,
   `commit_kind=WHOLE_FORM_SAVE`. The textarea must stay untyped. **Do not click
   Save Load / Save & Exit** unless a later owner path is explicitly documented
5. Popup **Last write** should show the write code, not harvest
   `ACTIVE_VIEW_UNVERIFIED`
6. From Active Loads (view unverified is fine): unique row or unique searchbox
   (fill 1763, no Enter) should open the workspace instead of
   `LOAD_OPENER_UNVERIFIED`
7. Still no status / assign / money / New Load

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

- Whether a note-specific **Add Note** exists anywhere besides Save & Exit (1763
  field pass saw none)
- Whether Save & Exit to Load Board commits only the private note (unproven; not
  auto-clicked)
- How typed text is stored after a real note-specific commit (textarea vs list)
- SPA settle timing after row / searchbox open
- Multi-tab / missing-tab / stale content beyond `ASCEND_TAB_MISSING`
- Customer-visible vs private distinction beyond the Private Load Note label
- Production approval (owner dashboard mint is demo-only)

## What this is not

- Not an Ascend retail API
- Not X1 / native messaging
- Not AUTO_MAP, harvest writes, or operational field semantics
- Not status, assign, rates, New Load, uploads, Save Load, Save & Exit, or outbound comms
- Not a LIVE_VALIDATED write
