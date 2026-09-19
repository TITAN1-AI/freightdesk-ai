# FreightDesk AI

Private collaboration repository: [TITAN1-AI/freightdesk-ai](https://github.com/TITAN1-AI/freightdesk-ai).

FreightDesk is the freight operations control plane above existing logistics systems.
Avery, Booking Logistics' AI Operations Assistant, will execute bounded operational work
through replaceable adapters and workers. FreightDesk owns shipment facts, workflow,
authorization, policy, scheduling and audit history.

**Current work:** Track B portable browser bridge v0 is the product-foundation slice beside X1.
X1 / WebBridge V2 audit repairs remain the Track A baseline. V1 remains default; V2 remains
fixture/TestRuns-gated and OBSERVE-only. Read [CURRENT_STATE.md](CURRENT_STATE.md),
[the portable handoff](docs/PORTABLE_BRIDGE.md) and [the repair handoff](docs/WEBBRIDGE_V2_AUDIT_FIXES.md)
before starting a task. Opening the demo dashboard or a pull request does not authorize live vendor activity.

**Collaborative development:** see [CONTRIBUTING.md](CONTRIBUTING.md) for branches, agent handoffs,
Windows setup, offline checks and source/runtime boundaries. Live validation is capability-specific.
Synthetic DEMO-1847 through DEMO-1850 are not LIVE POC #001.

## Run locally

A portable Python 3.13.7 runtime is installed under .tools/python inside this project.
No system Python installation or PATH change was made.

```powershell
.\scripts\start.ps1
```

Open http://localhost:8787. The browser establishes a demo-only owner session on this
workstation. There is no production login or live credential in this release.
Ctrl+C stops a foreground server.

For a fresh clone, run scripts/bootstrap.ps1 first. It downloads Python from python.org,
pip from bootstrap.pypa.io and exact dependencies from requirements.lock.
If local PowerShell execution policy prevents running scripts, use the existing Python
runtime directly; do not weaken machine security policy.

```powershell
& '.tools/python/python.exe' run.py
.\scripts\test.ps1
```

An existing Python 3.12+ environment can install requirements.lock and run run.py.
Never run multiple server workers against this single-process foundation.

## Dashboard

- Avery active/paused/error state, heartbeat, queued work and approvals
- Loads, deterministic risk explanations, tracking freshness, ETA/appointment comparison
- Load details, participants, documents, reconciliation placeholders and activity
- Approval/rejection, pause/resume, human takeover and demo customer update preparation
- Editable action policies; ALLOW simulates routine updates without a human click
- Connections, upcoming reviews, model/worker usage placeholders

Commands: status 1847, review 1847, pause 1847, resume 1847, takeover 1847,
at risk, missing pod, deliveries today, pickups tomorrow.
These are deterministic authorized commands, not a general chatbot.

## Operating modes and persistence

FREIGHTDESK_MODE=demo is the only enabled mode. Other modes fail at startup.
Live read-only, supervised and autonomous execution are planned; ActionPolicy already
supports ALLOW, APPROVAL_REQUIRED and FORBIDDEN independently of mode.

C:\FreightDeskRuntime\Data\booking-logistics\demo.sqlite3 stores persistent demo state and append-only audit.
Restarting preserves controls, policies, approvals and task due dates.
Demo timestamps intentionally age; the demo does not fake fresh GPS pings.

Configuration uses process environment; see .env.example. No .env auto-loading.
The local demo bearer is generated in C:\FreightDeskRuntime\Tokens\demo-owner-token.txt and never printed.
The dashboard uses an HttpOnly SameSite session cookie rather than the bearer token in JavaScript.
All operational runtime paths use owner-authorized C:\FreightDeskRuntime, outside OneDrive.
See SECURITY.md and docs/CARRIERVIEW_ACCESS.md for two-class private DPAPI setup.
The CarrierView panel displays the imported historical POC through a separate protected session.
Open privately with .tools/python/python.exe scripts/open_live_poc.py; no CarrierView token enters the browser.
All production CarrierView writes remain blocked. Current validation results and scoped capability
claims are recorded in CURRENT_STATE.md and LIVE_POC.md.

## Structure

```text
app/
  api/          FastAPI routes and local security boundary, including /v1/portable demo leases
  core/         settings, state machine, tracking gates, risk
  models/       typed canonical records
  services/     transactional control plane, SQLite, demo fixtures
  dashboard/    HTML/CSS/JavaScript
  security/     roles, tenant and shipment authorization
  policies/     policy evaluation
  events/       event bus contract
  scheduler/    bounded scheduled review worker
  workers/      future bounded worker integration
integrations/   logical interfaces and vendor capability notes
executors/      BrowserExecutor, ComputerExecutor, AgentWorker
model_providers/ provider contracts and deterministic routing
voice_providers/ future voice contract only
config/         default action policies
scripts/        bootstrap, start, test, encrypted token helpers
tests/          core, control-plane and HTTP tests
docs/           access handoff and verification evidence
extensions/     Ascend X1 (Track A) and portable-bridge (Track B; no native host)
workflows/      incremental workflow specification
```

See CURRENT_STATE.md, KNOWN_ISSUES.md and docs/CARRIERVIEW_ACCESS.md for the handoff.
