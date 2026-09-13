# POC002 bounded CarrierView read handoff

Owner reconciled manifest owner-active-loads-20260911-02 for 2026-09-11: 12 Active Loads rows,
8 pickups (1755,1756,1757,1758,1759,1762,1768,1769), 3 deliveries (1761,1766,1767).
The local manifest agrees. Coverage remains VISIBLE_BOARD_ONLY as recorded; owner reconciliation
does not change pagination evidence. It is the approved board for this read, not a fresh write grant.

## Owner command

From the FreightDesk AI project:

```powershell
.\scripts\with-carrierview-token.ps1 -CredentialClass tenant -ScriptPath .\scripts\reconcile_live_ops.py
```

At the manifest prompt enter: `owner-active-loads-20260911-02`.
No secrets are requested in chat or printed. Actor FreightDesk/Avery, credential class tenant,
existing manager/admin eligibility reason and pre-dispatch audit are retained. No credential fallback.

## Bounded plan and stops

1. Local preflight validates the exact manifest/date/queue IDs/candidates, then claims the one-use
   manifest-bound CarrierView read grant. No Ascend refresh or browser action.
2. GET /api/profile; require Booking Logistics company identity.
3. GET /api/loads?filter=active and GET /api/loads?filter=past, at most 2,000 rows each.
4. Match only the 11 approved Booking load_id values. GET /api/loads/{id} once for each uniquely
   matched provider identity; require exact Booking/provider detail identity. Maximum 14 GETs total.

No undocumented future filter/search parameter; future-record coverage remains unknown. Lists may
contain unrelated entries in memory, but they are discarded, not persisted or individually requested.
No retries, redirects, pagination traversal or writes. Each response max 2MB and timeout 15 seconds.
Stop on preflight mismatch, consumed grant, credential/audit failure, company mismatch, permission/auth
failure, rate limiting, redirect, timeout, provider failure, malformed/oversized response, list bound,
or exact-detail mismatch. Duplicate provider matches are reported NEEDS_REVIEW with no detail read or
creation for that load; a miss is NOT_FOUND_IN_BOUNDED_SEARCH, never absence proof.

## Report and remaining unknowns

Sanitized report goes to runtime operations/<manifest-id>-carrierview-reconciliation.json and the
isolated ops_carrierview_reconciliation record. Ascend manifest/evidence timestamps are not overwritten.
Reports include exact IDs, existence, list membership, known native carrier_view type, raw boolean
arrival/departure flags, position presence/timestamp age, required-data gaps and conservative next actions.
Unknown external integration types stay UNKNOWN; no opaque provider strings/phones/URLs are printed.
List membership is not verified operational state. Unverified tracking semantics stay UNKNOWN, not
ALREADY_TRACKING/DELIVERED/POD_PENDING. Timestamp age alone is not proof of healthy tracking.

No pilot can currently be proposed: verified absence and complete fresh phone/ordered stop/company/
address/time-window facts are not established. Report pilot=null and gaps; no dispatch/proposed write
ledger is invoked. A future single-native-shipment creation requires separate owner approval after all
facts, absence, stop-company wire mapping and creation communication effects are reconciled.

Implemented offline; 15 targeted tests and Ruff passed, two existing dependency warnings. No CarrierView
networking or read-grant consumption occurred during preparation. Actual per-load results await owner run.
