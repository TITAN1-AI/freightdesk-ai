# Store packaging v0 — Chrome Web Store + Edge Add-ons

Status: **documented, not submitted**. Track **B** (portable Bridge). Parallel to open
[PR #11](https://github.com/TITAN1-AI/freightdesk-ai/pull/11) note-capture; this slice
does **not** rewrite harvest/write paths and does **not** bump Bridge 0.1.12.

Audience: Owner + Avery + next engineer. Machine-readable copy:
[config/store-packaging-v0.json](../config/store-packaging-v0.json). Builder:
`app/services/store_packaging.py`.

The first sellable digital product is the **AscendTMS back-ops agent**: harness + Avery +
portable Chromium Bridge under policy. Customers install Bridge from the stores and bind
to FreightDesk Cloud. There is **no** Windows native host and **no** TITAN-01 requirement.

## Product map — demo-only vs store-path

| Surface | Demo (unpacked today) | Store-path (this packaging) |
| --- | --- | --- |
| Install | Load unpacked `extensions/portable-bridge/` | Chrome Web Store + Edge Add-ons |
| Native host / X1 | Untouched, not used | Untouched, not shipped |
| API origin | `http://127.0.0.1:8787` host permission + CSP | Pinned **HTTPS** FreightDesk Cloud origin only |
| Sign-in | Popup **Demo sign-in** `auth_kind=PLACEHOLDER` | OAuth / device-code lease ([CLOUD_LEASE_OAUTH_V0.md](CLOUD_LEASE_OAUTH_V0.md)) |
| Avery API auth | `DEMO_AGENT` Bearer | Tenant OAuth later; not this slice |
| Harvest | `VISIBLE_BOARD_ONLY` CANDIDATE | Same contract, Cloud-issued lease |
| Private note / status writes | APPROVAL_REQUIRED; narrow FIELD LIVE_VALIDATED | Do **not** claim LIVE in store copy |
| Assign / money / New Load | FORBIDDEN | FORBIDDEN |
| TITAN-01 | Internal ops machine | Not a customer install vehicle |
| Submission | n/a | **NOT_STARTED** — blockers below must be empty |

Keep demo sign-in working. Localhost stays on the **unpacked** manifest until a store zip
is built from `store_manifest_candidate(cloud_origin)`. Never upload the unpacked folder.

## Do not submit the unpacked manifest

`store_blockers()` on current `extensions/portable-bridge/manifest.json` is **non-empty**:

1. `http://127.0.0.1/*` and `http://localhost/*` host permissions
2. CSP `connect-src` allows those loopback origins
3. No `icons`
4. `cloud_api_origin` is `UNSET`
5. `privacy_policy_url` is `UNSET`

Chrome and Edge review will reject loopback as a customer network permission. The demo
API also binds `TrustedHostMiddleware` to localhost — that is a **demo control plane**,
not the Cloud origin.

## Chrome Web Store checklist

Account and listing

- [ ] Chrome Web Store developer account (one-time registration). Owner holds the publisher.
- [ ] Item name **FreightDesk Bridge** (matches manifest `name`).
- [ ] Short summary ≤ 132 characters. Do not say LIVE_VALIDATED, Booking Logistics cutover,
      or “we log into Ascend for you”.
- [ ] Detailed description: single purpose — sync the **visible Active Loads board** the
      user already opened into FreightDesk, plus owner-approved private-note / status
      actions already gated in-product. Assign and money stay blocked.
- [ ] Category: Productivity / Workflow (confirm at submit time).
- [ ] Language: English.
- [ ] Support URL + homepage URL (both `UNSET` until Owner pins them).
- [ ] Privacy policy **HTTPS URL** (required because the extension handles user data from
      a third-party site). In-repo draft is not a substitute.
- [ ] Visibility: unlisted first, then public. Do not ship to all regions until Cloud IdP
      exists.

Package

- [ ] Manifest V3 only. `manifest_version: 3` already.
- [ ] Zip the extension **root** (manifest at zip root), produced from
      `store_manifest_candidate`, not from a dirty working tree with localhost.
- [ ] No `nativeMessaging`. No `.exe`. No X1 files in the zip.
- [ ] No remote hosted code (no CDN scripts, no `eval`, no string `executeScript`).
- [ ] Source in this repo is the reviewable copy. Do not minify/obfuscate for store.
- [ ] Version: keep 0.1.12 on **main** until PR #11 (0.1.13) merges or Owner bumps.
      Store version must be unique per upload.

Permissions (minimal, already on unpacked)

| Permission | Keep? | Justification for the review form |
| --- | --- | --- |
| `storage` | yes | Opaque device/lease handles on this device. Not Ascend passwords. |
| `alarms` | yes | Bounded harvest poll (one minute). |
| `scripting` | yes | Reinject **packaged** isolated files on an allowlisted Ascend tab that was open before install. Never arbitrary URL/code. |
| `nativeMessaging` | **no** | Product rule. |
| `identity` | **no** for v0 | Device-code does not need it. Adding it expands review. |
| `tabs`, `cookies`, `webRequest`, `<all_urls>`, `debugger` | **no** | Over-broad; fail closed. |

Host permissions

| Host | Unpacked demo | Store zip |
| --- | --- | --- |
| `https://ascendtms.com/*` | required | required — content script + harvest/write on the TMS the user opened |
| `http://127.0.0.1/*`, `http://localhost/*` | demo only | **strip** |
| FreightDesk Cloud `https://…` | absent | **required** once Owner pins origin |

Content script: `matches: ["https://ascendtms.com/*"]`, `world: ISOLATED`,
`all_frames: false`. Do not add extra TMS hosts in this slice.

Privacy practices form (Chrome)

- Single purpose: board harvest into the user’s FreightDesk tenant.
- Data: load id, pick/drop dates, sanitized load status (current **main** harvest).
  Notes, customer names, driver/carrier strings, and finance are **not** in the main
  harvest contract. If PR #11 merges broader Active Loads cells, **update this form
  before submit** — do not silently expand disclosed data.
- Remote destination: FreightDesk Cloud only (after origin is pinned). Not sold.
- User is already signed into Ascend; the extension does not collect Ascend passwords.
- Evidence class remains CANDIDATE until a separate validation program.

Assets

- [ ] Icons: 16, 32, 48, 128 PNG. 128 is mandatory. Folder:
      [extensions/portable-bridge/store](../extensions/portable-bridge/store).
- [ ] At least one screenshot 1280×800 or 640×400. Show popup + Active Loads **without**
      private customer/driver/finance text (synthetic board or redacted).
- [ ] Small promo tile 440×280 (optional but recommended).
- [ ] Marquee 1400×560 (optional).
- [ ] Store icon 128×128 consistent with extension icon.

Review gotchas for the Ascend host permission

1. **Third-party site automation.** Reviewers treat `host_permissions` on someone else’s
   product as high risk. Copy must say: the user is already on Ascend; Bridge reads the
   visible board and, only with FreightDesk policy, types an approved private note or
   status. It does not scrape the rest of the web.
2. **Do not claim we operate AscendTMS.** FreightDesk is the control plane; Ascend is the
   customer’s TMS.
3. **Loopback looks unfinished or malicious.** Strip it.
4. **`scripting` + host permission** looks like a generic injector. Justify: packaged
   files, isolated world, exact origin, no remote code.
5. **Alarms every minute** are fine if the description says bounded harvest, not hidden
   tracking of unrelated sites.
6. **Permission creep after listing** (adding `<all_urls>` or extra hosts) triggers
   re-review and user disable prompts. Keep the allowlist frozen.
7. **Remote code / WASM from Cloud** is forbidden in MV3. Cloud is an HTTPS API, not a
   script source. CSP `script-src 'self'` stays.
8. **Unlisted vs public.** Ship unlisted until Cloud IdP + privacy URL + icons exist.
9. **LIVE / “reads all loads” overclaim** is a policy problem and a product lie. Store
   copy stays CANDIDATE / visible board only.
10. **PR #11 merge.** Note-capture may add `read-notes.js` and extra harvest cells. Rebuild
    the store candidate from whatever manifest is on the integration branch; do not freeze
    a second copy of `content_scripts` in this PR.

## Edge Add-ons checklist

- [ ] Microsoft Partner Center product for Edge Add-ons.
- [ ] Same MV3 zip as Chrome after localhost strip. Edge accepts Chromium MV3.
- [ ] Listing name, description, and privacy URL aligned with Chrome (no LIVE claims).
- [ ] Store logos: Partner Center still asks for 300×200 promo and a 1:1 logo; keep 128 PNG.
- [ ] Host permission justification is the same Ascend paragraph.
- [ ] Optional: import from Chrome Web Store after the Chrome item exists — only if Owner
      wants one listing pipeline. Do not assume automatic mirroring.
- [ ] Edge enterprise policy is out of scope; do not require sideload for customers.

Firefox is **not** in v0 (no `browser_specific_settings`, no AMO listing).

## Privacy draft (host this at `privacy_policy_url` before submit)

FreightDesk Bridge is a browser extension that helps a signed-in AscendTMS user sync the
visible Active Loads board into that user’s FreightDesk tenant.

- **Data collected from Ascend:** load identifiers and board dates/status already shown on
  the Active Loads grid. Harvest is CANDIDATE evidence, not a claim of complete account
  coverage.
- **Not collected (v0 store copy on main):** customer names, driver or carrier contact
  strings, finance, private note bodies, cookies, passwords.
- **Where it goes:** only the FreightDesk Cloud API origin pinned at package time.
- **Auth:** device-code / OAuth to FreightDesk (store-path) or a local demo placeholder
  (developer unpacked). Ascend login stays on Ascend.
- **Retention / revoke:** the user can revoke the capability lease; further harvest posts
  stop. Cloud retention follows the tenant’s FreightDesk settings (unset until Cloud).
- **Native host:** none.
- **Contact:** unset until Owner pins support URL.

This draft is not legal advice and not a live policy URL.

## Capability / policy (unchanged by packaging)

Assign and money stay **FORBIDDEN**. Writes stay **APPROVAL_REQUIRED** or blocked. X1
(`extensions/ascend-x1/` + `FreightDeskAscendHost.exe`) is not in the zip. No live Ascend
UI automation is added in this PR.

## Next engineering steps (Owner / Avery / eng)

1. Pin `cloud_api_origin` and `privacy_policy_url` in `config/store-packaging-v0.json`.
2. Add 16/32/48/128 icons under `extensions/portable-bridge/store/` (Owner brand).
3. Produce redacted screenshots from a synthetic or owner-approved board.
4. Implement Cloud IdP so device-code poll can mint `auth_kind=OAUTH_DEVICE` — see
   [CLOUD_LEASE_OAUTH_V0.md](CLOUD_LEASE_OAUTH_V0.md). Do not replace PLACEHOLDER until then.
5. Point the demo API (or a real Cloud API) at HTTPS; relax localhost `TrustedHost` only
   on that Cloud deployment, never in the unpacked developer path.
6. After PR #11 merges (or is declined), regenerate the store candidate and refresh the
   privacy form if harvest cells expanded.
7. Upload an **unlisted** CWS item, then Edge. Do not merge this packaging PR as
   “submitted”.
8. Keep assign/money FORBIDDEN in store copy and in code.

## Merge conflict risk with PR #11

PR #11 (`cursor/ascend-note-readback-ops-harvest-1fb7`) edits portable-bridge JS, atlas,
`portable_leases.py` harvest rows, and Bridge version **0.1.13**. This slice avoids those
files. If both merge, rebuild the store overlay from the resulting `manifest.json`; do not
hand-merge `content_scripts`.

See [PORTABLE_BRIDGE.md](PORTABLE_BRIDGE.md), [PORTABLE_BRIDGE_PRODUCT.md](PORTABLE_BRIDGE_PRODUCT.md),
and [CLOUD_LEASE_OAUTH_V0.md](CLOUD_LEASE_OAUTH_V0.md).
