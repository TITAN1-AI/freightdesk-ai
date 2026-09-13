# Verification evidence — 2026-09-07

## Current milestone verification

151 tests passed, Ruff passed, JS syntax and legacy/historical renderer assertions passed.
Import tests cover evidence hash, UI time/identity mismatch, approval, fixture rejection, idempotence,
unknown fact preservation, no task enqueue and classification/source separation.
Access tests cover one-use grant replay rejection, tenant isolation, HttpOnly/Strict cookie and
demo-cookie denial. Historical evidence is owner-approved, not subject to current-snapshot freshness.
Actual browser displayed the imported production replay, source facts, derived assessments,
source seconds, 10/218 GPS limitation and scoped YES/NO matrix. No CarrierView request was made.
The source/previous-milestone notes below are historical; current scoped LIVE_VALIDATED is in LIVE_POC.md.

Latest historical replay: 142 tests, Ruff and JS renderer pass. Exact-resource guards, identity
short-circuit, UTC/list versus local/detail appointment reconciliation and historical arrival
assessment are covered. Three real GETs for owner-selected reference 1752 succeeded; independent
UI validation/import not performed. GPS history is partial; no undocumented pagination requested.

Latest: 138 tests, Ruff and JS rendering passed. New fixture checks cover tenant audit, exact-company
gate, conditional past-list query, conflicting/missing company rejection and disabled agent networking.
Real tenant profile and past-list reads succeeded; company matched Booking Logistics LLC, 32 records
returned. Two GETs only in this run. No import/replay/write; shipment reconciliation remains pending.

## Latest discovery verification

133 tests passed, Ruff and JS renderer passed after adding two-GET discovery with explicit
scope guards, denial short-circuiting and allowlisted candidate output. Synthetic DPAPI
trailing-newline regression and updated launcher parser passed.
Live agent GET /api/profile returned HTTP 200 / success=false / user_not_found.
Active loads were not requested, tenant credential unused, no import or production writes.
This failed application-level read does not mark a capability LIVE_VALIDATED.
Earlier no-network statements below describe the pre-authentication verification snapshot.

Windows; project-local Python 3.13.7, FastAPI 0.141.1, Pydantic 2.13.5, Uvicorn 0.52.4.
requirements.lock pins dependencies. This is engineering verification, not vendor live validation.

## Final automated checks

- scripts/test.ps1: **129 passed**. All 61 M1 cases retained; credential expectations updated
  for the explicit two-class contract. New tests use MockTransport only.
- Ruff: **All checks passed**.
- Node live-view rendering assertions: passed for unknown/null, zero/false and HTML escaping.
- JavaScript syntax: app.js and live.js passed.
- All PowerShell scripts parsed successfully.
- Windows DPAPI synthetic in-memory encrypt/decrypt round-trip passed; no real credential file accessed.
- Test DBs now use C:\FreightDeskRuntime\Data\TestRuns\pytest.
- Two upstream deprecation warnings: Starlette httpx TestClient backend and anyio BlockingPortal alias.

## Coverage

M1: lifecycle/transitions/exception recovery, tracking/RC/signed-RC/POD/billing gates,
risk/freshness/ETA, role and tenant authorization, model routing, demo-only mode,
event idempotency/concurrency/rollback, approvals/policies/version/pause/takeover,
ALLOW simulation, scheduler persistence/bounded retries, safe audit/errors and HTTP boundaries.

CarrierView: all six reads, documented write methods through fixture transport, strict success
envelope and ten known error codes, redirects, auth/scope, 429, network authorization gates,
separate credentials/no fallback, provider ID validation and safe audit.
Native creation validates stops and persists returned provider ID and tracking/client URLs.
SMS validates message type/custom length. Ledger tests exercise immutable action bindings,
one concurrent dispatch, approvals/pause/current state, payload tampering, attempt budget,
timeouts/UNCERTAIN, no automatic resend and abandoned-claim recovery.

Mapping: raw/null preservation, separate provider/Booking identity, exact stops/appointments,
aware timestamps, no inferred acceptance/ETA, no stale position fallback and no demo-to-live mapping.
POC: bounded read sequence, account mismatch stops early, staging without live validation,
fixture import refusal and separate live-view authorization.
Webhook inbox: three typed normalized events, local auth, account/load association, dedup/conflict,
timestamps, body limits, remote rejection, sanitized errors and no canonical mutation.
Runtime paths: exact root, allowed areas and path traversal rejection.

## Runtime/browser evidence

- SQLite backup migrated the existing synthetic database into the nonsynced runtime.
  Old synthetic DB/logs/PID/inactive demo token were then archived there, without overwriting.
- Restarted loopback server using runtime database/token/log paths; /healthz returned
  status=ok, mode=demo, live_validated=false.
- Browser dashboard and desktop screenshot inspected: four DEMO loads, existing controls,
  CarrierView IMPLEMENTED=yes / TESTED=yes / LIVE_VALIDATED=no, and separate locked live panel.
- Live-panel submission without configured owner access was rejected with the expected locked message.
- No live record is displayed. Node renderer uses synthetic fields only.
- Earlier M1 browser interactions remain audited: pause/resume, prepare/approve simulated
  customer update, reject seeded approval, scheduled reviews and restart persistence.
  Avery active, no paused loads or pending approvals. Synthetic tracking timestamps age naturally.

## Not verified

No real CarrierView token, API origin/response mapping, authenticated GET, production write,
SMS/chat, webhook delivery/registration, UI reconciliation or real freight POC.
No other vendor, model/browser worker, voice or multi-user production deployment was exercised.
Full mobile/accessibility/cross-browser and supply-chain/backup/recovery audits remain future.
