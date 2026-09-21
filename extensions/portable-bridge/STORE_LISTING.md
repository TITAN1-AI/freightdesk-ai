# Store listing draft — FreightDesk Bridge

Status: **draft only**. Not submitted to Chrome Web Store or Edge Add-ons.

Name: FreightDesk Bridge  
Summary: Ascend Active Loads harvest into FreightDesk plus approved private internal notes. No native host. Other writes blocked.

Permission justification (draft):

- `https://ascendtms.com/*` — content script reads the visible Active Loads board the user already opened.
- `storage` — device/session placeholder and lease state.
- `alarms` — bounded harvest poll.
- `scripting` — recover the isolated content script on the allowlisted origin if the tab was open first.
- Localhost host permissions exist only for the developer lease stub and must be removed or replaced
  with the FreightDesk Cloud origin before store submission.

Privacy (draft): harvest is identity metadata (load id, pick/drop dates, sanitized status). Notes,
customer names, finance and driver/carrier strings are not collected. Evidence is CANDIDATE until a
separate validation program. Single purpose: sync the visible board the user is looking at.

Do not claim LIVE_VALIDATED Ascend or Booking Logistics production cutover in store copy.

Full Chrome Web Store + Edge Add-ons checklist, privacy draft, and demo-vs-store product
map: [docs/STORE_PACKAGING_V0.md](../../docs/STORE_PACKAGING_V0.md). Cloud lease trust
model: [docs/CLOUD_LEASE_OAUTH_V0.md](../../docs/CLOUD_LEASE_OAUTH_V0.md). This listing
draft is still **not submitted**.
