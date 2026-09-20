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
| Actuator | Portable Bridge 0.1.10 on an already-authenticated Ascend tab |
| Evidence | CANDIDATE receipts. `live_validated=false`. `production_writes=false` |
| Note kind | Private / internal only — atlas `textarea#scratch` / Private Load Note. `#notes` (Public Load Note) is blocked |
| Whole-form Save | Allowed only when the approval sets `allow_whole_form_save: true`. Otherwise `NOTE_COMMIT_REQUIRES_OWNER_PATH` |
| Out of scope | Status change, assign, money, New Load, uploads, public notes, send |

## Atlas (Booking Logistics sitemap)

Authoritative for this brokerage’s Ascend. Bridge 0.1.10 binds these selectors:

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
`allow_whole_form_save`, `whole_form_save_risk`, `claimed_at`, `claim_deadline_at`,
`tab_hint`.
Unclaimed `DISPATCHED` writes fail `BRIDGE_CLAIM_TIMEOUT` after 90s; claimed but
unfinished writes use 180s. Note text is never returned on the agent receipt or audit.

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
2. Click unique stay-on-load **Save** if a Save control exists (even if less
   prominent). Only then **Save & Exit to Load Board**
3. If Save & Exit left the workspace, wait for the board and re-open 1763
   (unique row, search+Enter, or `/loads/{id}`), then read `#scratch` again
4. Receipt `VERIFIED` when the text is present on `#scratch` (this tab or another)

Without the flag: do not type or click; `NOTE_COMMIT_REQUIRES_OWNER_PATH`.

## Bridge path

Portable Bridge **0.1.10** claims `GET /v1/portable/writes/pending` (sets `claimed_at`;
includes `allow_whole_form_save`). Wake sources: 1-minute write alarm, one-shot
`WRITE_SOON` (+1s / +4s), popup `POLL_WRITES` every 4s, tab complete / activate.
The same principal may reclaim an incomplete dispatch. Complete ignores extra body
fields (0.1.4’s `allow_whole_form_save` extra caused HTTP 422 / `[object Object]`
and left the API `DISPATCHED`). Popup `error_code` is stringified — never
`[object Object]`. It does **not** require harvest `ACTIVE_VIEW_UNVERIFIED`
to be cleared. Opening a load is independent of the Active Loads view contract:

1. **Already-open workspace** — `#scratch` via `getElementById` (including same-origin
   iframes) or unique Private Load Note. **Do not** fall through to
   `LOAD_OPENER_UNVERIFIED` when that field is present. The worker prefers the
   Ascend tab that probes `scratch=true`. **Scan every Ascend tab first.** Prefer
   the tab that already has `#scratch` / Private Load Note, focus it, and run the
   write there. Do **not** run `unique_searchbox` on the board tab if any tab
   already has `#scratch`. Receipt `tab_hint` records which tab was chosen and
   which were skipped.
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

0.1.4: atlas `#scratch` + explicit whole-form approval. Field fail: writes
`8a7dcacb` / `a433ed36` stayed `DISPATCHED` with public `claimed_at` omitted;
complete 422’d on extra `allow_whole_form_save` (`[object Object]`); Save-as-link
was `MISSING` instead of `NOTE_COMMIT_REQUIRES_OWNER_PATH`.

0.1.5: public `claimed_at` / `claim_deadline_at`, reclaim, `BRIDGE_CLAIM_TIMEOUT`,
faster wake, complete extra-ignore, popup stringify, Save `<a>` / `input value`.
Field pass: claim + no-whole-form `NOTE_COMMIT_REQUIRES_OWNER_PATH`. Field fail:
whole-form writes `c5275de` / `12eaed94` / `6cef42f0` claimed then
`LOAD_OPENER_UNVERIFIED`; `#scratch` showed B2 text but `note_present=false`
and Save never clicked.

0.1.6: `#scratch` already-open + tab probe. Field win: whole-form B2 text
persisted on Ascend. Receipt fail: `86373c6a` `SAVE_AND_EXIT` then
`stage=reopen` `LOAD_OPENER_UNVERIFIED`; first whole-form `aadfc9ab` also
opener-failed. Note is on the load; Bridge did not verify.

0.1.7: reopen after Save & Exit. Field fail: B/B2/B3 `c640c880` / `53c4e9fd` /
`34514137` were `LOAD_OPENER_UNVERIFIED` `unique_searchbox` while Load Basics
`#scratch` was open on another tab. A `37897c52` still hit `already_open`.

0.1.8: probe **all** Ascend tabs (content `PROBE_NOTE_WORKSPACE` plus a DOM
`#scratch` / Private Load Note fallback), prefer/focus the `#scratch` tab, never
run `unique_searchbox` when any tab already has `#scratch`. Receipt `tab_hint`
shows `scratch:<id>;skip=board:<id>`. Field pass: tab prefer. Field fail:
`07a344d3` `SAVE_AND_EXIT` then `stage=reopen` `LOAD_OPENER_UNVERIFIED` `none`.
Curl receipts showed `tab_hint` null.

0.1.9: after Save & Exit, wait for the board, then reopen 1763 via unique row,
search+Enter, or `https://ascendtms.com/loads/{id}` (3 retries, backoff). If a
Save control exists (even less prominent / not strictly visible), never choose
Save & Exit. If reopen fails but `#scratch` anywhere still has the note,
`VERIFIED`. `GET /v1/ascend/writes/{id}` always includes `tab_hint`.
Field fail `6e63295e`: `SAVE_AND_EXIT` `stage=reopen` `none` ~1s after claim;
`tab_hint` null. PING-ready tabs skipped reinject, so 0.1.9 helpers did not run.

0.1.10: force-reinject write content before every write. Background owns reopen
with 1s/2s/3s backoff: `#scratch` scan → `REOPEN_AND_VERIFY` (row / search+Enter)
→ `https://ascendtms.com/loads/{id}`. Receipts include `tab_hint` (or `missing`),
`reopen_attempts`, `verify_reason`, `bridge_version`. Save / SAVE / Save Changes
wins over Save & Exit.

## Avery re-test checklist (load 1763)

Reload unpacked Bridge **0.1.10** and **restart the demo API**. Demo-sign-in and
**keep the popup open**.
**Leave the Active Loads board tab open on purpose**, and sit on **1763 Load
Basics** with `#scratch` / Private Load Note visible (prior note text may remain).

1. POST without approval → `403` / `PENDING_APPROVAL`
2. Mint **without** `allow_whole_form_save` + POST → `claimed_at` set, then
   `FAILED` / `NOTE_COMMIT_REQUIRES_OWNER_PATH` / `already_open`. Textarea untyped.
   **Do not click Save**
3. Stay on 1763 Load Basics. Mint **with** `allow_whole_form_save: true` + POST
4. Expect `already_open` / non-null `tab_hint` / `bridge_version=0.1.10` on
   `GET /v1/ascend/writes/{id}`. Type `#scratch` only. If **Save** exists
   (any casing), Bridge must click it — **not** Save & Exit
5. If only Save & Exit exists: worker waits seconds, reopens 1763 (row /
   search+Enter / `/loads/1763`) or VERIFIED via `#scratch` scan. Poll →
   **`VERIFIED`** + `note_present=true`. Receipt `reopen_attempts` ≥ 1 if
   Save & Exit ran — not a ~1s `none` reopen
6. Popup **Last write** shows the write code, `tab_hint`, and reopen count,
   not harvest `ACTIVE_VIEW_UNVERIFIED`
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

These stay UNKNOWN until a 0.1.10 **VERIFIED receipt**. The 0.1.6 UI note is not
a receipt. Do not promote LIVE_VALIDATED from fixtures.

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
