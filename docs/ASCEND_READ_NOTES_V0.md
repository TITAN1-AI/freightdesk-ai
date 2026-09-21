# Ascend read notes v0 — private/public note read-back + board ops harvest

Tight **read** bundle for the portable / agent facade. Avery calls HTTP. Portable
Bridge **0.1.13** reads atlas `textarea#scratch` (Private Load Note) and `#notes`
(Public Load Note) on an authenticated Load Basics tab, and harvests already-named
Active Loads ops columns. **No Save. No typing.** X1 / native host is unchanged.

**Not LIVE_VALIDATED** until Avery VERIFIED. Receipts stay CANDIDATE
(`live_validated=false`).

| Claim | v0 |
| --- | --- |
| Action | `ASCEND_READ_LOAD_NOTES` |
| Policy | **ALLOW** (default). Writes stay APPROVAL_REQUIRED / FORBIDDEN |
| Auth | Demo agent Bearer, owner session, or portable device token |
| Actuator | Portable Bridge 0.1.13 on an already-authenticated Ascend tab |
| Private note | Atlas `textarea#scratch`. Read-only capture |
| Public note | Atlas `#notes` plus board column **Public Load Notes**. Never typed |
| Board ops | Observed 33-column headers already in harvest.js: Last Contact/Tracking, customer, picks/drops, carrier, driver, equipment, power unit, trailer, weight, reference, truck status, load posting notes, public notes |
| Out of scope | Assign, money, New Load, public-note **write**, appointment/stop **write**, documents, GPS API |

Appointment / stop-time / POD-received writes stay deferred: the portable atlas
has no Edit Stops selector, and X1 `mapping-scope.json` labels are vocabulary
only. Board **Picks** / **Drops** are city summaries, not appointments.

## Curl: session → capture → receipt → GET notes

```bash
AGENT=$(curl -sS -X POST http://127.0.0.1:8787/v1/agent/session \
  | python -c 'import json,sys; print(json.load(sys.stdin)["agent_token"])')

# Board ops fields after Bridge harvest on Active Loads (no approval)
curl -sS http://127.0.0.1:8787/v1/ascend/loads/1763 -H "Authorization: Bearer $AGENT"

# Empty-safe last capture
curl -sS http://127.0.0.1:8787/v1/ascend/loads/1763/notes -H "Authorization: Bearer $AGENT"

# Queue a Load Basics note read-back (ALLOW — no approval token)
CAPTURE=$(curl -sS -X POST http://127.0.0.1:8787/v1/ascend/loads/1763/notes/capture \
  -H "Authorization: Bearer $AGENT" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["write_id"])')

# Poll until VERIFIED or FAILED (no silent success)
curl -sS http://127.0.0.1:8787/v1/ascend/writes/$CAPTURE -H "Authorization: Bearer $AGENT"
curl -sS http://127.0.0.1:8787/v1/ascend/loads/1763/notes -H "Authorization: Bearer $AGENT"
```

Receipt fields: `write_id`, `action=ASCEND_READ_LOAD_NOTES`, `status`
(`DISPATCHED` | `VERIFIED` | `FAILED`), `private_note`, `public_note`,
`private_note_present`, `public_note_present`, `commit_kind=READ_ONLY`,
`save_variant=NONE`, `silent_save_forbidden=true`, `tab_hint`, `bridge_version`,
`verify_reason`, `opener_strategy`. Empty `#scratch` with the control found is
still VERIFIED (`private_note=""`).

## Avery field script (owner-manual, do not merge)

Single unpacked Bridge **0.1.13**. Restart the demo API so it serves the new
routes. Prefer load **1763** if Load Basics / `#scratch` is already open
(same already_open path as the note write). 1777 is also owner-safe. Do **not**
touch 1778–1780. **Read-only — no restore.**

1. Load unpacked `extensions/portable-bridge/` (0.1.13 only). Keep one build.
2. Active Loads tab: Demo sign-in, lease, Start harvest. Then:
   `GET /v1/ascend/loads/{id}` should include CANDIDATE `last_contact_tracking`,
   `public_notes`, `customer`, `picks`/`drops` when those board cells are
   non-empty. Income/expenses stay off the harvest.
3. Sit on **1763 Load Basics** with `#scratch` visible. Keep the popup open.
4. **A — capture without Save.** `POST /v1/ascend/loads/1763/notes/capture`
   with the agent Bearer (no approval). PASS if the receipt reaches **VERIFIED**,
   `commit_kind=READ_ONLY`, `save_variant=NONE`, `tab_hint` set,
   `bridge_version=0.1.13`, and `GET .../notes` returns the same `#scratch`
   text Avery sees (empty string is OK if the field is empty).
5. Confirm `#notes` is captured when present. Confirm Save was **not** clicked.
6. Private-note **write** and status **write** still require approval. Assign /
   expenses still 403.

Do not merge until this receipt is VERIFIED. Do not claim LIVE_VALIDATED from
offline tests.

## Bridge path

0.1.13 force-reinjects packaged content before every job (same 0.1.10 lesson).
Note read shares the mint/claim/complete queue with note and status writes
(oldest DISPATCHED wins). For `READ_LOAD_NOTES`:

1. Prefer the already-open Load Basics / `#scratch` tab
2. Read `#scratch` and `#notes` (same-origin frames included)
3. Never type, never click Save / Save & Exit
4. Matching controls → `VERIFIED`

Harvest on Active Loads still requires a verified Active Loads view. Note
capture does not.

## What this is not

- Not LIVE_VALIDATED note or board-ops reads
- Not an Ascend retail API
- Not X1 / native messaging
- Not a public-note write, assign, money, New Load, appointment write, or POD flag
- Not GPS last-position (board **Last Contact/Tracking** is cell text only)
