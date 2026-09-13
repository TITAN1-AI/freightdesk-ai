# WebBridge V2 — Phases 0–2 offline acceptance

2026-09-12. Owner authorized implementation after reviewing
`C:\Users\titan\Downloads\CODEX_WEBBRIDGE_V2_PHASES_0_2_REVISED.md`.
No installed extension, browser profile, native host, live authority or vendor was used.

## Baseline and authoritative inputs

Inputs: the revised brief plus the source-harvest, architecture, page-model, provenance and roadmap
documents in this directory. The separately referenced `WEBBRIDGE_V2_IMPLEMENTATION_PLAN_REVISED.md`
was not supplied or found; it is not claimed as reviewed. Exact implementation is traced below.

The existing sanitized `agent-causal-debug-20260912-final.json` under the tenant's ascend-native
runtime directory was inspected by approved keys: iteration 5 SUCCESS, X1 0.6.2, mapper revision 2,
controller/content protocol 3, LOAD/1763, Load Basics, one candidate-only map, 19 metadata candidates,
values=false, writes=false, cleanup COMPLETE. This corroborates the documented V1 baseline; it is
not a new V2 live receipt. Nineteen is not an acceptance constant. The five-iteration authority is closed.

## Four reviewable implementation sets

| Set / phase | Implemented modules | Executable checks |
| --- | --- | --- |
| Contracts/corpus / 0 | `executors/webbridge_v2/contracts.py`, synthetic corpus in `tests/test_webbridge_v2.py` | Strict immutable graph DTOs, identity/epoch/authority bindings, privacy tripwires, incompatible versions, unknown labels, false flags |
| Bounded graph / 1 | `extensions/webbridge-v2/core.js`, `semantics.js` | Streaming scoped traversal, pre-expansion bounds, mutation/cancellation, node ledger, independent visibility, shadow/slot/frame gaps, unrelated page chrome |
| Relationships / 2 | Core section projection; strict `SectionProof` and host relationship recomputation in `runtime_bridge.py` | Direct references, duplicates, multiple targets, cycles without recursive reference traversal, foreign portals, generic sibling-form pattern, competing regions |
| Integrated parity/commit/rollback / 0–2 | `compatibility.js`, `runtime_bridge.py`, small optional hook in existing `runtime.py`; safe optional diagnostic in `mapping_diagnostics.py` | Actual orchestrator/access/native codec/worker/router/content/DOM/map-store chain; observer refresh/replacement, focus, variation, dependency wait, review, revoke, rollback and notification recovery |

These are logical change sets; no commits are fabricated in this currently untracked project baseline.

## Compatibility and partial-stage schema refinements

The JSON wire format uses arrays of nodes/edges and opaque epoch-qualified IDs. Physical DOM handles
and raw IDREF lookup strings remain ephemeral. `DocumentKey` separates document and content-realm
epochs; `ObservationBinding` separates observation ID, authority and session-proof reference.
The compatibility session reference names the authenticated, session-gated dispatch; it is not a
session token. The host reconstructs these references from its pending command/document handshake.

`MetadataName` is only an approved static-vocabulary projection, with provenance references.
`ReferenceResolution` preserves candidate cardinality and ambiguity. When the bounded scope cannot
distinguish missing from inaccessible/out-of-scope, the outcome remains UNRESOLVED; no target is invented.
Layout, accessibility and viewport are separate; unobserved accessibility is UNKNOWN and paint is
UNAVAILABLE. Closed roots and unobserved frames are explicit coverage gaps. Reference cycles are
recorded as edges, never followed as ownership or authority; ownership cycles are rejected.

DocumentGraph is a deliberately partial-stage document representation: graph nodes project controls,
relationships identify section regions, and existing `AscendProviderMap` supplies candidate field
metadata. There is no second generic form/table engine. FIELDS/TABLES/NAVIGATION_ACTIVATION/
OPERATIONAL_VALUES are explicitly deferred, not empty arrays asserting absence.

The offline adapter first uses existing X1 provider proof and safe metadata collection, preserving its
monotonic progress receipts. It then requires a completed V2 graph and section relationship selecting
the same exact region, followed by fresh workspace/section checks. Expected-section input is only a
constraint; it never proves a section. The host validates graph bindings and independently recomputes
the limited section relationship before accepting either representation. Both proofs must pass.

Compatibility version 2 carries the legacy candidate map plus a V2 graph/section supplement. Legacy
fingerprints and history are preserved. This is not approval migration: the offline adapter accepts
OBSERVE only, cannot execute AUTO_MAP, and marks semantic read validation NOT_VALIDATED. Relationships
and navigation candidates cannot authorize clicks or values. Operational optionality remains UNKNOWN;
existing cross-load variation does not waive identity/navigation contradictions or required contracts.

## Runtime ownership, integrity and recovery

Normal RuntimeAccess has no V2 adapter. Explicit test installation is rejected outside Runtime
Data/TestRuns, revalidating path/reparse safety on every persistence. Browser installation additionally
requires the synthetic `chrome.runtime.id=fixture`; none of the V2 modules is included in X1's manifest.
No command, permission, transport or enrollment mechanism was added.

The optional adapter persists the existing candidate map and `runtime_v2_observations` graph/evidence/
completion in the SAME runtime.sqlite3 connection and existing savepoint. It never opens a second
database or calls executescript inside that transaction. The accepted-payload digest covers both the
legacy map and V2 supplement. Identical observation ID/digest is idempotent; changed digest rejects.
Normal native replay rejection still applies before this store boundary.

Coordinator recovery uses the committed runtime receipt; no cross-database atomicity is claimed.
The integrated fixture suppresses the post-commit coordinator notification, then demonstrates recovery
without another provider map. An injected failure after legacy map insertion rolls back map, graph and
completion together. Cleanup revokes only job-owned temporary authority. TestRuns graph-only utility
receipts say GRAPH_PERSISTED; only the real compatibility pipeline can claim MAP_PERSISTED.

## Privacy, budgets and diagnostic boundaries

The generic projector does not read input values, selected values, arbitrary table text, aggregate
workspace text, raw HTML or private subtrees. Synthetic throwing getters check access, not just output.
The integrated test also traps the legacy value-reading LocatorGraph.build path. Existing safe field
metadata collection is deliberately reused; operational mappings are not validated by these tests.

Core maximums: 1,024 visited nodes; 512 emitted; depth 32; 32 attributes/node; 256 bytes/attribute;
1,024 relationships; 16 references/attribute; 32 label nodes, label depth 4, 128 label bytes;
1,024 geometry reads; frontier 128; batch 32; 1,500 ms; 262,144 standalone graph bytes.
The compatibility graph budget is LOWER, 32,000 bytes, and combined map/supplement must remain within
the existing 45,000-byte map limit and 65,536-byte native frame limit. Existing 3-second capture and
12-second host deadlines are unchanged. These are stop bounds, not a full-context latency promise.

Core failures retain exact stage, predicate and category measurement. The optional fixed-vocabulary
V2 structural diagnostic travels inside the existing safe section-diagnostic receipt. Existing V1
section diagnostics are preserved; V2 failures do not trigger a broader scan or alternate execution.

## Incorporated source and obligations

Only a narrow Playwright subset is adapted: reviewed native/explicit roles, IDREF token/dedup,
parent/shadow-host and Chromium visibility primitives. Exact pin, source hashes/symbol ranges,
modifications, dependency closure, exclusions, destination hash and tests are in
`third_party/webbridge-v2-implementation.json`. Apache LICENSE and applicable NOTICE are included under
`third_party/licenses/playwright/`; adapted source is attributed. It is not called original code.

The graph/ledger, compatibility and host modules are FreightDesk implementations. Stagehand,
Browser Use and rrweb remain architectural inputs only. No flagged Skyvern/Crawl4AI/axe-core/Healenium
code or framework runtime is incorporated. Finder/Scrapling and roadmap Phases 3–7 remain deferred.

## Validation status and next boundary

Final verification: 428 broader relevant tests passed in 133.36s, plus seven separate boundary tests
and one added integrated graph-bound failure case: 436 distinct passing tests. The 73 focused and
36 final diagnostic/coordinator runs overlap these sets; do not add them together. Changed Python
Ruff and all three V2 JavaScript syntax checks passed. Two existing dependency deprecations remain.
The integrated graph-bound failure proves the precise payload category reaches persisted diagnostics
and owner-facing failed_predicate, with no map and completed temporary-authority cleanup.

One synthetic sample (graph acquisition only, not complete capture/transport/persistence latency):

| Fixture | Visited / emitted | Edges | Geometry reads | Frontier | Graph bytes | Elapsed ms |
| --- | --- | --- | --- | --- | --- | --- |
| Direct target | 14 / 13 | 17 | 14 | 2 | 10,433 | 0.4 |
| Sibling region | 14 / 14 | 15 | 15 | 3 | 10,537 | 0.4 |
| Non-Ascend sibling | 14 / 14 | 14 | 15 | 3 | 10,328 | 0.7 |
| Direct target + 5,000 unrelated chrome elements | 14 / 13 | 17 | 14 | 2 | 10,433 | 0.3 |

Measurements are saved beneath Runtime Data/TestRuns/v2-acceptance in the fixture measurements.json.
They are one machine/sample, not a benchmark or speedup claim. Synthetic results do not validate Ascend.

V1 remains the ordinary runtime and rollback path. A future migration must explicitly package and
version-pin the V2 worker/content compatibility contract and remove neither proof nor write gates.
No installed-extension reload or live command is part of this offline package.

Proposed ONE consolidated live validation, requiring fresh separate owner authorization: review and
package the pinned migration; use the existing authenticated X1 session, a job-owned bounded OBSERVE
lease and current LOAD/1763 Load Basics only; verify actual worker/content revisions; obtain matching
identity/document/lease/ACK, V1 and V2 section proofs; persist one metadata-only CANDIDATE_ONLY result;
verify receipt/digest and close temporary authority. Stop on any ambiguity/bound/mismatch, with no
automatic retry, navigation traversal, field values or other-vendor action. Do not reuse closed grants.

Verified operational context still requires separately authorized field-semantic validation, section
coverage and provider facts. Avery's shipment actions additionally require their own ActionPolicy,
readiness and write approval milestones. This package does not authorize them.
