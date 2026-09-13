# Roadmap

Current implementation/release matrix: [X1 / V2 audit repairs](docs/WEBBRIDGE_V2_AUDIT_FIXES.md).
V2 Phases 0-2 repaired offline; V1 remains default. No live V2 migration or capability promotion.


| Phase | Scope | State |
|---|---|---|
| M1 | Core state/gates, policy/roles, events/audit, approvals/scheduler/risk, interfaces, dashboard | Local demo foundation implemented/tested |
| M2 | CarrierView official contract, secure read-only connection, mappings, create/initiate if supported | Adapter foundation tested; scoped historical reads/import/display live-validated |
| POC #001 | Historical Production Replay | Owner-reconciled and imported; operational/document capabilities excluded |
| M3 | Graph OAuth, mail/settings and unsent drafts; historical intelligence | Six bounded capabilities live-validated; broader workflow remains pending |
| M4 | Ascend supported API verification or deterministic browser reconciliation | Planned |
| M4A | Real Ascend historical CSV intelligence | Approved 694-row historical commit, re-import and provenance-backed profiles/distributions validated |
| M4B | Ascend integration and X1 runtime | Scoped persistent Active Loads board runtime live validated; X1 0.5.0 OBSERVE + AUTO_MAP workspace/context interface implemented offline; controlled mapping cohort and verified operational reads next |
| M5 | Quo SMS, conversations, signed inbound events, scoped identity | Planned |
| M6 | BrokerCarrier profile/vetting/setup/docs and BOOK IT | Planned |
| POC #002 | BOOK IT -> tracking gate -> RC -> pickup/BOL/photos -> delivery/POD | Planned |
| Later | Tender extraction/load creation, DAT/Truckstop, Morning Ops, owner email/SMS | Planned |
| Autonomous production | Live validation, configured ALLOW, durable outbox, recovery and observability | Planned |
| Commercial | Real identity, isolated secrets/profiles/storage, customer deployments | Planned |
| Voice | Future legal review and bounded calling | Contract only |

Validation is capability-specific; see LIVE_POC.md for actual historical and local/provider evidence.
Offline tests do not promote provider capabilities. The scoped prior live board evidence remains in
[ASCEND_X1_RUNTIME.md](docs/ASCEND_X1_RUNTIME.md). Next: OBSERVE unknown structure, reviewed navigation, controlled AUTO_MAP cohort,
normal automatic section mapping, then verified context reads and 5-10-second latency validation. See [Mapping Mode](docs/ASCEND_X1_MAPPING_MODE.md).
Planning/Active/Accounting lifecycle semantics remain an owner-attested hypothesis. Bulk audit workers
and structured-network observation require separate future authorization and are not implemented.
# M3 checkpoint — owner-confirmed bounded validation complete

Completed: OAuth, exact mailbox verification, settings read, 5-message production discovery/read,
real-message ingestion/processing and exactly 1 unsent draft, manually verified in Outlook.
211 tests and checks pass. No attachments exercised, no explicit shipment matching evidence and no
incremental delta validation. Production sending, Mail.Send scope, canonical mutation, owner commands,
webhooks and autonomous communications remain unvalidated/blocked as applicable.

Next: obtain separate bounded authorization before any further Graph networking. A useful next
validation is one known freight attachment with explicit shipment reconciliation, followed separately
by bounded delta/restart/dedup validation. No such action is authorized by this roadmap.
The owner-provided Ascend export is now committed to the isolated history store; see M4A below.
Later: owner-reviewed canonical application, verified sender gateway, scanning/retention, explicit
polling schedule, minimal notification ingress and real Ascend adapter. No automatic communication.

## M4A next step

M4B first handoff is ready in docs/ASCEND_ACCESS.md. Next is separately authorized manual login,
identity/DOM inspection and owner selection of one load (1752 proposed), then a bounded read and
reconciliation. A later separate session is needed for reuse validation. No real write, autonomous
tender/BOOK IT workflow or current pricing is enabled by this foundation.

Completed: owner-approved source/mapping/USD commit of all 694 rows, successful financial controls,
idempotent re-import and provenance-backed customer/lane/carrier/facility profiles and internal
income/total-expense/gross/margin distributions. 252 tests and checks pass. Next potential work is
owner review of bounded candidate topics and separate alias/equipment decisions; none is automatically
approved by this milestone. Changed-source version handling still lacks a changed real export.
No Ascend browser/API work or current-state writes are authorized by this historical milestone.
# Active priority: POC #002 — LIVE OPERATIONS

Owner's tomorrow board now precedes additional historical browser proof. Execute the owner-controlled
same-process dated discovery, reconcile selected references with bounded CarrierView tenant GETs,
produce pickup tracking/delivery watch queues and resolve missing data/coverage/negative-existence
evidence. Prepare hashed creation proposals; disclose unresolved company mapping/communication effects.
Only after separate exact-payload owner authorization, one creation/readback pilot; stop for batch approval.
No live execution occurred in implementation. See docs/POC_002_LIVE_OPERATIONS.md; older roadmap follows.

## 2026-09-11: Mapping Orchestrator V1 / X1 0.6.0 (offline)

Read docs/ASCEND_MAPPING_ORCHESTRATOR.md. A single protected-owner Map Ascend action or
scripts.ascend_mapping_orchestrator start manages durable stages, IDs, session-only preflight,
bounded mapping authority, automatic starting capture, navigation review, qualified AUTO_MAP,
reports and cleanup. A repeated click preserves the active job. Interrupted capture never retries.
The existing extension/native transport, provider workspace contracts and WebBridge sensors are reused.
Planning/accounting operations scope is still unverified and fails closed; Active Loads remains
VISIBLE_BOARD_ONLY. Representative cohort loads are owner-opened; reviewed sections traverse automatically.
General AUTO_MAP still requires controlled cohort return receipts. Read/write field mappings remain
unvalidated. No new LIVE_VALIDATED promotion and no live job/lease/attempt was created this turn.
The old manual -02 ID and all prior audit remain intact. The orchestrator supersedes manual per-step
lease/session/capture/report commands as the normal owner workflow; advanced diagnostics retain IDs.
Owner first reloads existing X1 to 0.6.0, opens 1763 / Load Basics, then runs the single documented start
command. No re-pair, Computer Use, Playwright live run, vendor request or production write here.

Next: one controlled orchestrated workspace capture, reviewed cohort section returns, then separate read-field validation feeding AscendLoadContextAssembler. ShipmentOrchestrator follows those proofs.
