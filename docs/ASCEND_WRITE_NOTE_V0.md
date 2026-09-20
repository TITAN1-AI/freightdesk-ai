# Ascend write note v0 — private internal note

First FreightDesk **write** on the portable / agent facade. Avery (or any agent) calls HTTP.
The portable Bridge types a **private / internal** note on an authenticated Ascend tab.
The agent never clicks Ascend UI.

**Not LIVE_VALIDATED.** Avery must field-pass before any live claim.
X1 / native host is unchanged. Harvest and agent Bearer reads stay as they were.

| Claim | v0 |
| --- | --- |
| Action | `ASCEND_ADD_INTERNAL_NOTE` (policy). Mint alias `ASCEND_ADD_INTERNAL_NOTE_VIA_SAVE` sets the whole-form flag |
| Policy | **APPROVAL_REQUIRED** (default). Other writes stay unavailable / FORBIDDEN at this facade |
| Auth | Same as the read facade: demo agent Bearer, owner session, or portable device token |
| Actuator | Portable Bridge 0.1.4 on an already-authenticated Ascend tab |
| Evidence | CANDIDATE receipts. `live_validated=false`. `production_writes=false` |
| Note kind | Private / internal only — atlas `textarea#scratch` / Private Load Note. `#notes` (Public Load Note) is blocked |
| Whole-form Save | Allowed only when the approval sets `allow_whole_form_save: true`. Otherwise `NOTE_COMMIT_REQUIRES_OWNER_PATH` |
| Out of scope | Status change, assign, money, New Load, uploads, public notes, send |

## Atlas (Booking Logistics sitemap)

Authoritative for this brokerage’s Ascend. Bridge 0.1.4 binds these selectors:

| Control | Atlas | Bridge |
| --- | --- | --- |
| Private Load Note | textarea id `scratch`, css `#scratch`, section Load Basics, `action_class` OBSERVE_OR_FILL | Only fill target |
| Public Load Note | `#notes` | Never typed. `PUBLIC_NOTE_BLOCKED` if that is the only note |
| Save | overall Save only — “no per-field disc icons observed” (`selectors.json`) | Whole-form commit. Prefer stay-on-load **Save** / **Save Load** over **Save & Exit to Load Board** |

There is **no** note-specific Add/Save Note. Ascend persists `#scratch` by submitting the load form.

**Risk (documented on the receipt as `whole_form_save_risk`):** clicking Save / Save & Exit submits the entire load form, not a note-only control. Status, assign, money, New Load, public `#notes`, and communications stay hard-blocked in the Bridge. Unrelated dirty fields on the form are an owner/operator risk.

## Curl: session → whole-form approval → POST note → receipt

Demo server: `FREIGHTDESK_MODE=demo` (default). Bridge must sit on an Ascend tab for
`VERIFIED`; without it the POST returns `DISPATCHED` and you poll.

```bash
# 1) Agent session (or Tokens/demo-agent-token.txt)
AGENT=$(curl -sS -X POST http://127.0.0.1:8787/v1/agent/session \
  | python -c 'import json,sys; print(json.load(sys.stdin)["agent_token"])')

# 2) Mint a one-use demo approval that acknowledges whole-form Save
#    (also: dashboard checkbox “Allow whole-form Save…” + mint)
#    Alias: "action":"ASCEND_ADD_INTERNAL_NOTE_VIA_SAVE"
APPROVAL=$(curl -sS -X POST http://127.0.0.1:8787/v1/ascend/approvals \
  -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
  -d '{"action":"ASCEND_ADD_INTERNAL_NOTE","load_id":"1763","allow_whole_form_save":true}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["approval_token"])')

# 3) Request the write. Missing/invalid approval → HTTP 403, status PENDING_APPROVAL
#    Approval without allow_whole_form_save → Bridge FAILED NOTE_COMMIT_REQUIRES_OWNER_PATH
curl -sS -X POST http://127.0.0.1:8787/v1/ascend/loads/1763/notes \
  -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
  -d "{\"text\":\"internal ops note\",\"approval_token\":\"$APPROVAL\"}"

# 4) If status is DISPATCHED, poll until VERIFIED or FAILED (no silent success)
# curl -sS http://127.0.0.1:8787/v1/ascend/writes/{write_id} -H "Authorization: Bearer $AGENT"
```

Receipt fields: `write_id`, `status` (`PENDING_APPROVAL` | `DISPATCHED` | `VERIFIED` |
`FAILED`), `evidence_class`, `verified`, `note_present`, `text_digest`, `error_code`,
`stage`, `opener_strategy`, `note_label`, `commit_kind`, `save_variant`,
`allow_whole_form_save`, `whole_form_save_risk`.
Note text is never returned on the agent receipt or audit.

## How demo approval is granted

Default ActionPolicy `ASCEND_ADD_INTERNAL_NOTE = APPROVAL_REQUIRED`. A POST without a
valid unused token is rejected (`403`, `PENDING_APPROVAL`).

Mint a 15-minute, one-use token bound to `load_id` (and optionally the intended text):

1. **Owner dashboard** — Ascend panel → load ID → optional **Allow whole-form Save /
   Save & Exit for Private Load Note (#scratch)** → **Mint demo note approval**.
2. **`POST /v1/ascend/approvals`** — `{"action":"ASCEND_ADD_INTERNAL_NOTE","load_id":"1763","allow_whole_form_save":true}`.
   Or `"action":"ASCEND_ADD_INTERNAL_NOTE_VIA_SAVE"` (same policy, flag forced on).
   Optional `"text"` binds the digest so a different note cannot reuse the token.

Without `allow_whole_form_save`, the Bridge will **not** click Save. This mint is a
**demo grant**, not cloud OAuth and not a production write authority.

## Verify-after-write

`VERIFIED` requires a read-back that `#scratch` / Private Load Note contains the text.
A Bridge completion with `verified=true` and `note_present=false` is stored as `FAILED`
(`verify_without_presence`).

Live Bridge with a whole-form approval:

1. Type only `#scratch` / Private Load Note
2. Click unique stay-on-load **Save** if present; otherwise **Save & Exit to Load Board**
3. If Save & Exit left the workspace, re-open the load and read `#scratch` again
4. Receipt `VERIFIED` only when the text is present

Without the flag: do not type or click; `NOTE_COMMIT_REQUIRES_OWNER_PATH`.

## Bridge path

Portable Bridge **0.1.4** polls `GET /v1/portable/writes/pending` (claim includes
`allow_whole_form_save`). It does **not** require harvest `ACTIVE_VIEW_UNVERIFIED`
to be cleared. Opening a load is independent of the Active Loads view contract:

1. **Already-open workspace** — unique `#scratch` / Private Load Note
2. **Unique row opener** — exact load-id cell plus View / Details / Open / id
3. **Unique searchbox** — fill the load id, **no Enter / submit**, then the same row opener

Then commit:

- Note-specific Add/Save Note if one exists (none in the atlas)
- Else whole-form Save only with `allow_whole_form_save`
- Else `NOTE_COMMIT_REQUIRES_OWNER_PATH`

Still rejects `ASCEND_SAVE` as a generic action, assign, status, rates, New Load,
public `#notes`, and send.

Popup **Last write** is separate from harvest.

## Field report — Avery / load 1763

0.1.2: `LOAD_OPENER_UNVERIFIED`; harvest banner `ACTIVE_VIEW_UNVERIFIED`; Private Load
Note found; only Save & Exit; Avery did not click Save Load.

0.1.3: opener no longer needs Active Loads; Save & Exit failed closed as
`NOTE_COMMIT_REQUIRES_OWNER_PATH`.

0.1.4: atlas `#scratch` + explicit whole-form approval. Same safe fail without the flag.

## Avery re-test checklist (load 1763)

Reload unpacked Bridge **0.1.4**. Sit on authenticated Ascend — Active Loads does
**not** need to be the verified view. Preferred: already on 1763 Load Basics with
`#scratch` / Private Load Note visible.

1. POST without approval → `403` / `PENDING_APPROVAL`
2. Mint **without** `allow_whole_form_save` + POST → `DISPATCHED` then `FAILED` /
   `NOTE_COMMIT_REQUIRES_OWNER_PATH`. Textarea untyped. **Do not click Save**
3. Mint **with** `allow_whole_form_save: true` (dashboard checkbox or curl above) + POST
4. Expect Bridge to type `#scratch` only (never `#notes`), click **Save** if present,
   else **Save & Exit**, then re-read `#scratch`
5. Poll `GET /v1/ascend/writes/{id}` → `VERIFIED` + `note_present=true` +
   `commit_kind=WHOLE_FORM_SAVE` + `whole_form_save_risk` set. Or `FAILED` with a
   clear `error_code` / `stage` — not silent success
6. Popup **Last write** shows the write code, not harvest `ACTIVE_VIEW_UNVERIFIED`
7. Still no status / assign / money / New Load / public note / communications

## API

| Method | Path | Role |
| --- | --- | --- |
| `POST` | `/v1/ascend/approvals` | Mint demo note approval (`allow_whole_form_save` optional) |
| `POST` | `/v1/ascend/loads/{load_id}/notes` | Queue / execute the write |
| `GET` | `/v1/ascend/writes/{write_id}` | Poll receipt |
| `GET` | `/v1/portable/writes/pending` | Bridge claim (includes `allow_whole_form_save`) |
| `POST` | `/v1/portable/writes/{write_id}/complete` | Bridge verify result |

Existing `GET /v1/ascend/status`, `GET /v1/ascend/loads`, `/v1/agent/session`, and
`/v1/portable/leases|harvest` are unchanged.

## LIVE field gaps (Avery)

These stay UNKNOWN until a 0.1.4 field pass. Do not promote LIVE_VALIDATED from fixtures.

- Whether stay-on-load **Save** is distinguishable from **Save & Exit** on 1763
- Whether `#scratch` retains the text after Save / after Save & Exit + re-open
- SPA settle timing after whole-form Save
- Dirty-form side effects of whole-form Save (unrelated fields)
- Multi-tab / missing-tab / stale content beyond `ASCEND_TAB_MISSING`
- Production approval (owner dashboard mint is demo-only)

## What this is not

- Not an Ascend retail API
- Not X1 / native messaging
- Not AUTO_MAP, harvest writes, or operational field semantics
- Not status, assign, rates, New Load, uploads, public notes, or outbound comms
- Not a silent whole-form Save (the approval flag is the acknowledgment)
- Not a LIVE_VALIDATED write
