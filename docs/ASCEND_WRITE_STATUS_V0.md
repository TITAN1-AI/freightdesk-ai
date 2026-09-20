# Ascend write status v0 — load status change

Second FreightDesk **write** on the portable / agent facade. Avery (or any agent) calls HTTP.
Portable Bridge **0.1.12** sets **Load Status** on an authenticated Ascend Load Basics tab.
The agent never clicks Ascend UI.

**Not LIVE_VALIDATED.** Avery must field-pass before any live claim.
X1 / native host is unchanged. Harvest, agent Bearer, and the private-note write stay as they were.

| Claim | v0 |
| --- | --- |
| Action | `ASCEND_CHANGE_LOAD_STATUS` (policy). Mint alias `ASCEND_CHANGE_LOAD_STATUS_VIA_SAVE` sets the whole-form flag |
| Policy | **APPROVAL_REQUIRED** (default). No silent status flips. Assign / money stay FORBIDDEN |
| Auth | Same as the read facade: demo agent Bearer, owner session, or portable device token |
| Actuator | Portable Bridge 0.1.12 on an already-authenticated Ascend tab |
| Evidence | CANDIDATE receipts. `live_validated=false`. `production_writes=false` |
| Control | Atlas Load Basics labels `Load Status` / `Status`. Prefer a unique `<select>` / combobox |
| Whole-form Save | Allowed only when the approval sets `allow_whole_form_save: true`. Prefer stay-on-load **Save**. Otherwise `STATUS_COMMIT_REQUIRES_OWNER_PATH` |
| Allowed statuses | Atlas `status_catalog`: `Active`, `Available`, `Assigned`, `Booked`, `Dispatched`, `In Transit`, `Delivered`, `Completed`, **`To Be Billed`**, `Driver Assigned` |
| Out of scope | UNKNOWN (harvest-only), assign, money, New Load, public notes, send, from→to graph invention |

## Atlas catalog (harvest + field evidence)

`extensions/portable-bridge/atlas.json` `status_catalog` is the source of truth.
Python `WRITE_STATUSES`, harvest `STATUSES`, Bridge `WRITE_STATUSES`, capability
`allowed_statuses`, and the dashboard select are derived from or checked against it.

The catalog is **not** a hard-coded short “ops board” list. It comes from:

- the original Active Loads harvest labels
- historical M4A export distribution (`Completed`, **`To Be Billed`**, `Delivered`, `Driver Assigned`)
- field load **1763** UI status **To Be Billed** (Avery correctly refused `Dispatched` on that load)

Any other UI value stays **UNKNOWN** and harvest-only. FreightDesk does **not** invent
a from→to transition graph. Any catalog status except `UNKNOWN` may be requested.
Ascend UI may reject some transitions; `VERIFIED` requires read-back of the
requested status. Whole-form Save can submit unrelated dirty fields — documented
on the receipt as `whole_form_save_risk`.

Status is a labeled Load Basics control (`kind: select`, `read: select`). There is
**no** per-field status save — atlas `write_default` remains `WHOLE_FORM_SAVE`.

## Curl: session → whole-form approval → POST status → receipt

Use an **Active or Available** load for the first 0.1.12 smoke (reversible catalog
change). Do **not** use 1763 until the later To Be Billed round-trip.

```bash
AGENT=$(curl -sS -X POST http://127.0.0.1:8787/v1/agent/session \
  | python -c 'import json,sys; print(json.load(sys.stdin)["agent_token"])')

# A) No approval → HTTP 403 PENDING_APPROVAL
curl -sS -X POST http://127.0.0.1:8787/v1/ascend/loads/{ACTIVE_LOAD}/status \
  -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
  -d '{"status":"Available"}'

# B) Mint + approved change (stay-on-load Save acknowledged)
APPROVAL=$(curl -sS -X POST http://127.0.0.1:8787/v1/ascend/approvals \
  -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
  -d '{"action":"ASCEND_CHANGE_LOAD_STATUS","load_id":"{ACTIVE_LOAD}","status":"Available","allow_whole_form_save":true}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["approval_token"])')

curl -sS -X POST http://127.0.0.1:8787/v1/ascend/loads/{ACTIVE_LOAD}/status \
  -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
  -d "{\"status\":\"Available\",\"approval_token\":\"$APPROVAL\"}"

# Poll until VERIFIED or FAILED (no silent success)
# curl -sS http://127.0.0.1:8787/v1/ascend/writes/{write_id} -H "Authorization: Bearer $AGENT"
```

Receipt fields: `write_id`, `action`, `requested_status`, `observed_status`,
`status_matched`, `status` (`PENDING_APPROVAL` | `DISPATCHED` | `VERIFIED` | `FAILED`),
`evidence_class`, `verified`, `error_code`, `stage`, `opener_strategy`, `commit_kind`,
`save_variant`, `allow_whole_form_save`, `whole_form_save_risk`, `claimed_at`,
`claim_deadline_at`, `tab_hint`, `reopen_attempts`, `verify_reason`, `bridge_version`.

Optional mint `"status"` binds the token so a different catalog value cannot reuse it.
Alias `"action":"ASCEND_CHANGE_LOAD_STATUS_VIA_SAVE"` forces `allow_whole_form_save`.

## Avery field script (Bridge 0.1.12 only)

Reload unpacked Bridge **0.1.12** (single-build) and **restart the demo API**.
Demo-sign-in and **keep the popup open**. Sit on an **Active or Available** Load
Basics tab (leave the Active Loads board tab open on purpose). Use **one**
unpacked 0.1.12 build — do not mix 0.1.11 content.

**Do not smoke B on 1763.** 1763 is **To Be Billed**. The first 0.1.12 pass is a
reversible catalog change on a different Active/Available load. The 1763
To Be Billed round-trip is a later field after this catalog smoke.

1. **A — no approval.** `POST /v1/ascend/loads/{ACTIVE_LOAD}/status` with a
   catalog value (for example `Available` or `Active`). Expect HTTP **403** /
   `PENDING_APPROVAL` / `approval_required`. Ascend status must not change.
2. **B — approved reversible change.** Mint with `allow_whole_form_save: true`
   (or VIA_SAVE) bound to that Active/Available load and the intended catalog
   status. POST the same status. Expect claim, then
   `GET /v1/ascend/writes/{id}` → **`VERIFIED`**, `status_matched=true`,
   `observed_status` equals the request, `tab_hint` set, `bridge_version=0.1.12`,
   `verify_reason` present. Prefer `save_variant=SAVE_STAY` if Save exists.
3. Do **not** click Save yourself. Do **not** merge until this receipt is VERIFIED.
4. Assign / expenses still 403. Note write still works on its own approval.
5. **Later:** 1763 To Be Billed → another catalog status (or the reverse) after
   B passes on an Active/Available load.

## Demo sign-in / revoked harvest lease

Avery saw `device_session_bound` with harvest `lease_status=REVOKED` (stale
2026-09-19) and a write stuck `DISPATCHED` / `awaiting_bridge`. That is **not**
a status-write lease bug in this slice.

- Harvest **revoke** stops further harvest posts. The last snapshot stays
  readable. Writes **claim via the device token**, not the harvest lease.
- `device_session_bound` is the demo cap of **8 ACTIVE device sessions**
  (8h TTL). Demo sign-in mints a new device row; Sign out only clears the
  extension token and does **not** free a server slot. Sessions live in
  demo SQLite, so restarting the API does **not** wipe them.
- To rebind: wait for the oldest device sessions to expire (8h), or start a
  fresh demo store / TestRuns DB if you control that path. Then Demo sign-in
  on **0.1.12**, keep the popup open, and mint a **new** harvest lease if you
  still need board reads.
- A write left `DISPATCHED` / `awaiting_bridge` after a failed sign-in is
  waiting for Bridge to claim. Rebind, keep the popup open, and retry. Do not
  treat a revoked harvest lease as proof the write queue is broken.

## Bridge path

Portable Bridge **0.1.12** force-reinjects write content before every write (same
0.1.10 lesson). It claims `GET /v1/portable/writes/pending` (note and status share
the queue; oldest DISPATCHED wins). For `CHANGE_LOAD_STATUS`:

1. Prefer the already-open Load Basics / `#scratch` / Load Status tab
2. Set the unique Load Status select/input to the requested catalog option
3. Click stay-on-load Save when the approval allows whole-form commit
4. Read the status back. Matching catalog value → `VERIFIED`

Without `allow_whole_form_save`, Bridge does not change the control and does not
click Save (`STATUS_COMMIT_REQUIRES_OWNER_PATH`).

## What this is not

- Not LIVE_VALIDATED until Avery’s VERIFIED receipt
- Not an Ascend retail API
- Not X1 / native messaging
- Not assign, rates, New Load, uploads, public notes, or send
- Not a silent status flip
- Not a proven from→to workflow (catalog gate only)
