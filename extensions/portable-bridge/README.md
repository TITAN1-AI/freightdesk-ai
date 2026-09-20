# FreightDesk Bridge (portable)

Unpacked MV3 adapter for **Track B** (sellable product). It talks to a FreightDesk lease API over
HTTPS/HTTP. It does **not** use Windows native messaging and does not replace
[Ascend X1](../ascend-x1/).

Product north star: [docs/PORTABLE_BRIDGE_PRODUCT.md](../../docs/PORTABLE_BRIDGE_PRODUCT.md).
Engineering handoff: [docs/PORTABLE_BRIDGE.md](../../docs/PORTABLE_BRIDGE.md).

## How this differs from X1

| | X1 (Track A) | Portable Bridge (Track B) |
| --- | --- | --- |
| Install | Edge + `FreightDeskAscendHost.exe` | Load unpacked now; Chrome/Edge stores later |
| Permission | `nativeMessaging` | **none** — no native host |
| Auth | DPAPI enrollment / pairing | Demo placeholder device session (cloud OAuth later) |
| Lease | Host-owned Windows read lease | Cloud/demo capability lease, revocable |
| Harvest | Host-leased identity/map jobs | VISIBLE_BOARD_ONLY board snapshot, **CANDIDATE** |
| Writes | Blocked | Harvest blocked; approved **private internal note** only ([write note v0](../../docs/ASCEND_WRITE_NOTE_V0.md)) |
| LIVE_VALIDATED | Narrow historical X1 reads only | **No** — this track is not live-validated |

v0 harvest never clicks Save, assign, notes, uploads, or wizard New Load. Maps/harvest are
evidence-only. A separately approved private/internal note can be typed by the Bridge; other
writes stay blocked. Booking Logistics live ops stay on the Avery stack until a separate cutover.

## Load unpacked (Chrome or Edge)

1. Start the FreightDesk demo API (same path as the dashboard):

   ```powershell
   .\scripts\start.ps1
   ```

   Linux/macOS with an existing Python environment:

   ```bash
   FREIGHTDESK_MODE=demo python run.py
   ```

   The stub listens on `http://127.0.0.1:8787`. `FREIGHTDESK_MODE` must remain `demo`.

2. Chrome: `chrome://extensions` → Developer mode → **Load unpacked** →
   `extensions/portable-bridge/`.
   Edge: `edge://extensions` → Developer mode → **Load unpacked** → same folder.
3. Open `https://ascendtms.com` to Active Loads. Sign in to Ascend yourself.
4. Open the **FreightDesk Bridge** popup:
   - Demo sign-in (placeholder device session)
   - Create lease
   - Start harvest
   - Revoke to stop further posts within one alarm interval (1 minute)

**After Load unpacked (or the chrome://extensions Reload button):** already-open Ascend tabs
do not receive the new content script automatically. The bridge first tries a safe isolated
reinject (`chrome.scripting.executeScript` of the packaged files, main frame only). On
install/update it may reload only `https://ascendtms.com/` or `https://ascendtms.com/loads`
with no query or fragment. It does **not** reload detail/other paths.

If harvest stays **running** with 0 rows, `extension_last_seen` null, or no snapshot:

1. Reload the Ascend **Active Loads** tab now (F5 or the browser reload button).
2. Press **Start harvest** again.

The popup banner repeats that action. A full manual reload is still required when the browser
blocks programmatic injection (policy, discarded tab, or a path the extension will not reload).

The popup shows distinct states for not signed in, missing lease, allowlist/origin failures,
and an unreachable API. **Last write** is separate from harvest: a harvest
`ACTIVE_VIEW_UNVERIFIED` banner does not describe a note-write failure. Keep the
popup open during a note write so 0.1.10 can claim within seconds (`claimed_at`);
leave the board tab open and sit on 1763 Load Basics with `#scratch` visible.
Bridge must pick the scratch tab (`already_open`, `tab_hint`), not the board
`unique_searchbox`. Prefer stay-on-load Save. After Save & Exit the Bridge waits
for the board and reopens 1763 (row / search+Enter / `/loads/1763`) then reads
`#scratch`. Unclaimed
dispatches fail `BRIDGE_CLAIM_TIMEOUT`. Harvest posts only
to `http://127.0.0.1` / `http://localhost` in this package.

## Facade curl (demo)

After the demo server is up, product/Avery can read the last harvest through the Ascend **facade**
(`GET /v1/ascend/loads`). That is UI-harvest evidence, not an Ascend retail API. Agents should
use [docs/AGENT_ASCEND_API_V0.md](../../docs/AGENT_ASCEND_API_V0.md) (Bearer, no popup).
Humans keep Demo sign-in in this popup. See [docs/ASCEND_FACADE_V0.md](../../docs/ASCEND_FACADE_V0.md).

```bash
# Agent path (no X-FreightDesk-Portable, no popup)
AGENT=$(curl -sS -X POST http://127.0.0.1:8787/v1/agent/session \
  | python -c 'import json,sys; print(json.load(sys.stdin)["agent_token"])')
# Or: C:\FreightDeskRuntime\Tokens\demo-agent-token.txt

# Optional lease — harvest still needs Bridge on an Ascend tab
curl -sS -X POST http://127.0.0.1:8787/v1/portable/leases \
  -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
  -d '{"origin":"https://ascendtms.com","scope":"VISIBLE_BOARD_ONLY","ttl_seconds":900}'

# Read the facade after Bridge has posted harvest (or when harvest is empty)
curl -sS http://127.0.0.1:8787/v1/ascend/status -H "Authorization: Bearer $AGENT"
curl -sS http://127.0.0.1:8787/v1/ascend/loads -H "Authorization: Bearer $AGENT"

# Optional: approved private internal note (not LIVE_VALIDATED)
# APPROVAL=$(curl -sS -X POST http://127.0.0.1:8787/v1/ascend/approvals \
#   -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
#   -d '{"action":"ASCEND_ADD_INTERNAL_NOTE","load_id":"1763"}' \
#   | python -c 'import json,sys; print(json.load(sys.stdin)["approval_token"])')
# curl -sS -X POST http://127.0.0.1:8787/v1/ascend/loads/1763/notes \
#   -H "Authorization: Bearer $AGENT" -H 'Content-Type: application/json' \
#   -d "{\"text\":\"internal ops note\",\"approval_token\":\"$APPROVAL\"}"
```
See [ASCEND_WRITE_NOTE_V0.md](../../docs/ASCEND_WRITE_NOTE_V0.md) for approval, receipts, and LIVE gaps.

Extension/device path (popup Demo sign-in) is unchanged: `POST /v1/portable/session` with
`X-FreightDesk-Portable: 1`, then the same lease/harvest/facade routes using the device token.

Empty harvest returns `loads: []` and `harvest_available: false` (HTTP 200). A revoked lease keeps
the last snapshot readable and rejects further harvest posts.

## Tests

From a full Windows checkout (same suite as CI):

```powershell
.\scripts\test.ps1
```

Focused:

```powershell
.\.tools\python\python.exe -m pytest tests/test_portable_leases.py tests/test_portable_bridge_extension.py tests/test_ascend_facade.py tests/test_ascend_notes.py --basetemp=C:\FreightDeskRuntime\Data\TestRuns\portable-bridge
```

An existing Python 3.12+ environment can run the same pytest modules. The extension test also
runs `node --check` on packaged JS and checks the inject-first / manual-reload copy.

Field smoke (owner-manual, after Load unpacked on an already-open Active Loads tab):

- Prefer: Start harvest without a manual reload and see a CANDIDATE snapshot / facade rows.
- Fallback: banner says to reload Active Loads (F5) then Start harvest; after that reload,
  harvest_count > 0. No Ascend writes. Demo mode only.

## Remaining gaps (not in v0)

- Real FreightDesk Cloud auth (OAuth / device code) and tenant billing
- Chrome Web Store / Edge Add-ons listing, icons, privacy disclosure, review
- HTTPS cloud API origin in `host_permissions` (replace localhost stub)
- Firefox
- Operational field values, AUTO_MAP, general writes, and any LIVE_VALIDATED claim
  (private-note write is CANDIDATE / not field-passed)
- Dashboard shipment list / freshness UI bound to portable harvest
- Token storage stronger than `chrome.storage.local`
