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
| Writes | Blocked | Blocked in extension and API |
| LIVE_VALIDATED | Narrow historical X1 reads only | **No** — this track is not live-validated |

v0 harvest never clicks Save, assign, notes, uploads, or wizard New Load. Maps/harvest are
evidence-only. Booking Logistics live ops stay on the Avery stack until a separate cutover.

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

The popup shows distinct states for not signed in, missing lease, allowlist/origin failures,
and an unreachable API. Harvest posts only to `http://127.0.0.1` / `http://localhost` in this
package.

## Tests

From a full Windows checkout (same suite as CI):

```powershell
.\scripts\test.ps1
```

Focused:

```powershell
.\.tools\python\python.exe -m pytest tests/test_portable_leases.py tests/test_portable_bridge_extension.py --basetemp=C:\FreightDeskRuntime\Data\TestRuns\portable-bridge
```

An existing Python 3.12+ environment can run the same pytest modules. The extension test also
runs `node --check` on packaged JS.

## Remaining gaps (not in v0)

- Real FreightDesk Cloud auth (OAuth / device code) and tenant billing
- Chrome Web Store / Edge Add-ons listing, icons, privacy disclosure, review
- HTTPS cloud API origin in `host_permissions` (replace localhost stub)
- Firefox
- Operational field values, AUTO_MAP, writes, and any LIVE_VALIDATED claim
- Dashboard shipment list / freshness UI bound to portable harvest
- Token storage stronger than `chrome.storage.local`
