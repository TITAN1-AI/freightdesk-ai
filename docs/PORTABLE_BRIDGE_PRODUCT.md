# FreightDesk AI — Portable Bridge (product north star)

Status: draft for owner review · 2026-09-15  
Audience: Coder-FreightDesk + Avery + Manuel

## Why this exists
Booking Logistics already has **Ascend X1** (Edge + Windows native host + DPAPI enrollment). That path is strong for *internal* LIVE_VALIDATED reads, but it is a poor shape for a **digital product**: OS lock-in, store friction, enrollment complexity, and “bring your own Windows host” do not scale to other brokerages.

**Product thesis:** FreightDesk is the shipment control plane; browsers and TMS UIs are sensors/actuators. Customers install a **cross-browser extension** (or use a hosted agent session) that talks to **FreightDesk Cloud**, not to a local `.exe`.

## Product layers
1. **FreightDesk Cloud (SaaS)** — tenant, policy, shipment model, leases, audit, billing.
2. **Portable Browser Adapter** — MV3 extension for Chromium (Chrome/Edge) first; Firefox later. Content scripts on approved TMS origins only.
3. **Optional Desktop Worker** — only for customers who need deeper OS automation; *not* required for core Ascend read/map.
4. **Agent face (Avery-class)** — employee UX; same APIs the extension uses.

## Trust model (replace DPAPI/native messaging)
| X1 today | Portable product |
| --- | --- |
| Native host + DPAPI pairing | OAuth / device code to FreightDesk Cloud |
| Host-leased reads on Windows | Cloud-issued **capability lease** (scoped, expiring, revocable) |
| Extension ↔ `FreightDeskAscendHost.exe` | Extension ↔ FreightDesk API (HTTPS) + optional relay |
| Installation ID pinned to Windows SID | Tenant + device enrollment in cloud |

Hard product rules (carry forward from X1):
- Default **read-only / OBSERVE**; writes are capability-gated and audited.
- Ascend maps start **CANDIDATE_ONLY** until identity + receipts pass.
- No Playwright-as-secret-extension; automation is an explicit worker product.
- Evidence classes: FACT / CLAIM / INFERENCE / VERIFIED — never conflate.

## MVP for sale (v0)
**Buyer:** small–mid freight brokerage on AscendTMS (or similar board UI).  
**Job:** “See my loads in FreightDesk and keep them fresh without copy-paste.”

Ship:
1. Chrome Web Store + Edge Add-ons package (same MV3 codebase).
2. Sign-in to FreightDesk tenant.
3. Content script: Active Loads board harvest (VISIBLE_BOARD_ONLY), push to cloud.
4. Dashboard: shipment list, freshness, revoke lease.
5. Admin: origin allowlist, retention, export.

Non-goals for v0: multi-TMS writes, BrokerCarrier booking, Outlook send, autonomous money moves.

## What we keep from X1
- Workspace / board contracts and causal identity lessons.
- Mapping orchestrator concepts (OBSERVE, cohort validation).
- Policy engine patterns (ALLOW / APPROVAL_REQUIRED / FORBIDDEN).
- Demo control plane UX as reference — not the install vehicle.

## What we do *not* ship as the product
- Requiring `C:\FreightDeskRuntime` or `FreightDeskAscendHost.exe`.
- OneDrive-hosted checkouts as the runtime.
- “Load unpacked” as the customer install story.

## Parallel tracks
| Track | Purpose |
| --- | --- |
| **A · Stabilize X1 on TITAN-01** | Keep Booking Logistics live capability; feed contracts into portable v0. |
| **B · Portable product** | New extension + cloud lease API; store-ready packaging. |

## Immediate engineering slices
1. **Lease API sketch** — `POST /v1/leases` (scope, origin, TTL, revoke).
2. **Extension shell** — MV3, no `nativeMessaging`; cloud auth; Ascend board reader ported from X1 content scripts.
3. **Packaging** — single repo folder `extensions/portable-bridge/` + store listing draft.
4. **Threat model one-pager** — token theft, malicious page, lease overreach.

## Success metrics (product)
- Install → first board sync < 15 minutes for a new tenant.
- Works on Chrome *and* Edge without a native installer.
- Revoke lease stops harvest within one poll interval.
- Zero production Ascend writes in v0 (enforced in extension + API).

## Ops vs product boundary (Avery · 2026-09-15)
- **Booking Logistics live ops today** run on Avery hybrid stack (Outlook Graph + CarrierView/Ascend browser) — **not** X1 and **not** the portable cloud lease path.
- **Track A (X1 on TITAN-01)** = BL Ascend MVP only. **Track B (portable)** = commercial product. No cutover claim until Manuel authorizes and harvest is LIVE_VALIDATED.
- Product v0 board harvest does **not** replace ops needs: private notes, driver fields, POD → Ascend Docs, CarrierView client links — those stay Avery/HITL until separately productized.
- Client visibility north star on ops remains **CarrierView live links + accurate ETAs**; portable Ascend board sync *complements* CV, does not replace it.
- Sales/copy must not claim cloud leases on BL production loads before cutover.
