# Store assets — FreightDesk Bridge

Icons, screenshots, and promo tiles for Chrome Web Store / Edge Add-ons belong here.

**None are checked in yet.** Do not submit without 16/32/48/128 PNG icons and at least
one 1280×800 or 640×400 screenshot that contains no private customer, driver, finance,
or token data.

Handoff: [docs/STORE_PACKAGING_V0.md](../../docs/STORE_PACKAGING_V0.md).
Trust model: [docs/CLOUD_LEASE_OAUTH_V0.md](../../docs/CLOUD_LEASE_OAUTH_V0.md).

The store zip is built in memory by `store_manifest_candidate(cloud_origin)` from the
unpacked `manifest.json`. It strips localhost. It does not use this folder as a second
manifest (that would drift from PR #11 harvest/write edits).
