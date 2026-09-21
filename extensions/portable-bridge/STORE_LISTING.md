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

Privacy (draft): harvest is CANDIDATE board cells the operator already has on Active Loads:
load id, pick/drop dates, sanitized status, last-contact/tracking, customer, assignment
names, public/posting notes, and other named ops columns. Private `#scratch` is collected
only by an explicit note-capture job, not by board harvest. Finance columns are not
harvested. Evidence is CANDIDATE until a separate validation program.

Do not claim LIVE_VALIDATED Ascend or Booking Logistics production cutover in store copy.
