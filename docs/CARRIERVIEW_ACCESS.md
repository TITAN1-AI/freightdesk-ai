# CarrierView access — current handoff

LATEST prepared multi-system run uses owner-supplied active/future list scope, NOT past, at 14 GET max.
See POC_002_MULTI_SYSTEM.md for exact staged commands. Future scope is offline implemented, not yet
LIVE_VALIDATED. No new vendor read is automatic; all creation/communication guards remain blocked.

POC #002 live operations are now priority. A separate owner-executed reconcile_live_ops.py helper is
prepared through the tenant DPAPI launcher after the Ascend manifest exists. It reads profile, bounded
active/past lists and at most one exact read for each unique discovered matching identity (max 33 GETs).
Unmatched records are not persisted; no credentials/phones/raw payloads are printed. It has no writes,
fallback or retry. A bounded list miss is not verified absence because pagination is unresolved. Existing
provider write guards remain; see docs/POC_002_LIVE_OPERATIONS.md for negative-existence, company-wire and
creation-communication blockers. No new CarrierView networking was performed during implementation.

CarrierView API service identity is explicitly the Booking Logistics tenant credential.
Avery's employee token is unavailable for real API execution; no fallback is permitted.
Owner-provided reason: "CarrierView API requires manager/admin credential; Avery employee token
is not API-eligible." Provider audit actor is FreightDesk/Avery, credential class tenant.

Verified origin: https://carrierview.com. Both DPAPI files were privately stored by the owner:
C:\FreightDeskRuntime\Secrets\carrierview-agent-token.dpapi and carrierview-tenant-token.dpapi.
Never read them into terminal/chat output. The private launcher defaults to tenant, temporarily
sets only the selected token environment variable, and restores process state afterward.
Agent launches are blocked. No automatic .env loading.

The historical POC is imported and already visible in the protected app browser.
To reopen it privately, from the project:

```powershell
& '.tools/python/python.exe' scripts/open_live_poc.py
```

This does not read CarrierView credentials or contact CarrierView. It issues a one-use local
three-minute launch grant, clears the URL fragment and establishes an eight-hour HttpOnly
historical-view cookie. The optional dedicated FREIGHTDESK_LIVE_VIEW_TOKEN bearer still works;
do not put a CarrierView API token in that field. Demo cookies never unlock this view.

The approved import used saved evidence and owner UI reconciliation, with no additional provider GET.
Canonical record is in runtime Data\booking-logistics\carrierview.sqlite3. Detailed evidence/report
and hash-bound owner approval are under runtime Data\booking-logistics\historical-1752.
Source seconds/nulls/provider metadata survive; sensitive raw fields are excluded from the view.

All provider POST/PATCH/PUT, SMS/chat, webhook registration and operational polling remain disabled.
GET authorization is task-specific; do not rerun historical/discovery scripts without a current reason.
The past-list and selected shipment's detail/position/first history page were proven; other methods
or payload mappings are not thereby validated. See LIVE_POC.md and KNOWN_ISSUES.md.

Historical approval has no real-time freshness implication. General snapshot import still requires
its own identity/freshness checks. Load 1753 is separate and has not been read/imported.
Local dashboard: http://localhost:8787. No public ingress, tunnel or production webhook receiver.
