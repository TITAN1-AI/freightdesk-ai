# Architecture

## Ascend interactive executor pivot (offline X1)

Existing BrowserExecutor DOM primitive protocol is retained. TypedBrowserReadExecutor adds execute_read
for bounded provider operations; AscendExtensionExecutor blocks generic navigation/selector reads and
uses policy/tenant/actor/load/version gates with an injected disconnected transport. Existing Playwright
executor is preserved. OpenClaw/ComputerUse remain future adapters, not enabled paths. Native Messaging
is preferred for the extension; identity/approvals/canonical state/audit remain in FreightDesk.
See docs/ASCEND_EXECUTOR_PIVOT.md for transport and row-bound identity assessments.

## Ownership and flow

FreightDesk owns orchestration and canonical workflow. Ascend remains the external operational
TMS system of record; differences require explicit reconciliation. Canonical records hold
verified facts and source references. Models and browser harnesses cannot declare facts authoritative.

```text
Dashboard / trusted normalized event / scheduler
 -> server-resolved identity and tenant
 -> authorization and pause checks
 -> deterministic state/risk/gates
 -> ActionPolicy
    ALLOW -> bounded execution
    APPROVAL_REQUIRED -> version-bound approval -> recheck -> bounded execution
    FORBIDDEN -> audited denial
 -> reread / verify
 -> canonical state + audit
```

Current execution is only a simulated customer update; nothing is sent.
Policy is independent of mode, enabling future autonomous routine work without redesign.

## Persistence and events

SQLite schema version 1 uses tenant/kind/id record keys and unique tenant/source/event-id
receipts. Reusing an event ID with changed content fails. Event application, receipt and audit
commit atomically; invalid transitions roll back. An in-process lock plus BEGIN IMMEDIATE
serializes one control-plane instance. WAL enabled; one server process only.

Audit triggers reject update/delete. This is append-only, not tamper-proof against a database
owner. Audits contain concise facts/rules/results, never hidden model chain-of-thought.
No public webhook endpoint exists. /api/events accepts authenticated local dashboard input.
A separate loopback:8788 typed normalized CarrierView inbox validates local ingress identity,
account/load association and deduplication. It persists PENDING_VERIFICATION events without canonical
mutation until actual vendor wire/auth/signature semantics are verified.

## State and risk engines

The entire TENDER_RECEIVED -> CLOSED lifecycle plus EXCEPTION is modeled. Adjacent
transitions only, with an already-onboarded-carrier shortcut. Exception recovery returns
to the previous state after explicit resolution. Carrier approval/setup, tracking acceptance,
RC prerequisites, signed RC, verified POD and required billing documents are enforced.
TrackingGate is configurable in code; future customer settings can supply it.

Aware timestamps, provenance, freshness and ETA vs appointment drive deterministic risk.
Unknown/future/expired/inactive tracking is never healthy. Post-delivery reviews prioritize
missing documents rather than contacting drivers about tracking.

## Scheduler

A 30-second asynchronous wakeup examines persistent due dates. Reviews are five minutes apart,
not every tick. Paused or human-owned loads are skipped. Failed reviews back off exponentially
and stop after three attempts. Audit holds outcome history; the current task row holds the next
review. Network I/O must never be introduced into a SQLite transaction.

The separate durable ActionLedger claims an immutable side effect once, outside-network transactions,
with tenant, actor, policy, approval, pause, agent state, shipment version, provider/contact and payload
bindings. Attempted records cannot auto-resend; abandoned or ambiguous claims become UNCERTAIN.
SMS budget is shared across credential classes. All production write transport remains blocked.
Distributed leases, production dispatcher, operational reconciliation and dead-letter tooling remain future.

## Adapters and workers

Logical methods are not vendor endpoint promises. Prefer API, official events, deterministic
DOM, bounded harness worker, visual fallback, then human escalation. Verify account contracts first.

BrowserExecutor / ComputerExecutor / AgentWorker jobs carry tenant, shipment, exact external ID,
expected/intended state, authorization reference and deadline. Future workers verify identity,
prepare, check authorization, execute, reread and verify. Harnesses never own shipment state,
policy, customer database, scheduling or audit. Playwright/OpenClaw/Hermes/DeepSeek Harness
are planned replaceable implementations only.

## Models and voice

ModelProvider takes purpose, untrusted text, verified facts, output schema and output budget.
ModelInvocation records model/provider, tokens, cost/duration and escalation reason when known.
Routing bypasses LLMs for deterministic tasks. The requested gpt-5.6-sol label is configurable;
API availability is unverified and no inference provider is implemented.
Models draft/classify/extract, never authorize actions or mutate verified facts.
VoiceProvider is design-only; no telephony runtime exists.

## Dashboard and security boundaries

Vanilla static assets call authenticated local FastAPI endpoints. Loopback, trusted-host,
Origin and Fetch-Metadata checks protect demo workstation sessions. Local bootstrap grants
owner access only because all non-demo modes are rejected.

Core authorization defines tenant and shipment-scoped roles. Participant API projections remain
disabled pending field-level data access design. A distinct owner-bearer endpoint reads only a reconciled runtime POC; demo cookies cannot unlock it.
CarrierView reads stage exact account/load evidence, then require recent hash-bound UI reconciliation
before import. Fixture evidence is rejected. New runtime storage is C:\FreightDeskRuntime.
Commercial deployment needs real identities,
tenant-isolated credentials/browser profiles/storage, scoped adapters, TLS and operational recovery.
