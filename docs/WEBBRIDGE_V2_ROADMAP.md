> Current status (2026-09-13): see [the audit repair handoff](WEBBRIDGE_V2_AUDIT_FIXES.md).
> Earlier acceptance/design statements below are historical. V2 is implemented offline with
> audited repairs; live packaging, operational semantics and Phases 3-7 remain deferred.

# WebBridge V2 implementation roadmap

Status: **PROPOSED — implementation requires owner approval**. This roadmap follows the [source harvest](BROWSER_INTELLIGENCE_CODE_HARVEST.md), [architecture](WEBBRIDGE_V2_ARCHITECTURE.md), [page model](WEBBRIDGE_V2_PAGE_MODEL.md) and [provenance plan](WEBBRIDGE_V2_PROVENANCE.md). No package installation, production implementation or live validation occurred in this research task.

Start with invariants and a frozen synthetic corpus. Replace the generic internals incrementally while preserving X1's existing authenticated boundary and the current Ascend provider acceptance rules. Do not rewrite the coordinator, native transport, enrollment or board-reader architecture as prerequisites.

## Phase 0 — contracts, privacy and evaluation baseline

**Reuse:** existing identity/presence/session/document/lease bindings, safe receipts, fixed write blocks, mapping-store validation and the integrated offline coordinator→host→worker→router→content→synthetic DOM→persistence path. Existing public source research becomes provenance, not a dependency.

**Build/change:** freeze V2 DTOs and policy interfaces; define stage budgets, claim types, cancellation and schema-version negotiation. Separate authorized identity values from forbidden field values. Make missing data, ambiguous data and incomplete coverage distinct. Add immutable observation IDs, accepted-exemplar history and an atomic map/evidence/completion receipt boundary. Preserve cross-database coordinator reconciliation by reference, rather than claiming distributed atomicity.

**Required tests:** getters for operational input/selected values and forbidden private-text subtrees throw if accessed during metadata projection. Separately test the bounded static-label classifier: it may inspect only admitted label sources, must discard unknown text before graph serialization, and may not read aggregate workspace/body text. Malicious/private label and attribute sentinels never reach durable DTOs, selector operands, hashes or logs. Test document/session/lease mismatch, expired/revoked authority, no owner presence, wrong workspace, unknown section, no-page fallback, serialization limits, failed local commit and duplicate completion.

**Migration:** add V2 behind an offline feature switch; retain V1 as the only live implementation. Use synthetic representations of the observed exact section shape and other generic widgets; do not load raw Ascend HTML or infer unobserved selectors. Historical successful X1 receipts describe V1 only.

**Risk/payoff:** medium interface risk; high prevention value. Exit only when a failed stage cannot produce a success receipt, private-value access is test-detectable and contract-version mismatch stops safely. This avoids rebuilding selectors while lifecycle or persistence silently fails.

## Phase 1 — DocumentGraph, NodeLedger and normalization

**Reuse:** Stagehand/Browser Use index architecture, rrweb Mirror identity bookkeeping, selected Playwright visibility/role helpers and evidence-preserving pruning patterns. Record actual copied/adapted units and notices before incorporation.

**Build/change:** one immutable graph per observation epoch, indexed nodes and typed root/frame/shadow/ownership edges. A streaming traversal checks budgets before expansion. Fixed X1 content code supplies sanitized facts; no CDP/debugger permission, alternate session or third-party runner. Keep document generation separate from DOM mutation revision and logical control signature.

**Required tests:** very large irrelevant document around a small approved workspace; max visited/emitted/depth/bytes/time; display:contents; hidden referenced labels; open shadow/slot composition and cycles; unavailable closed roots/frames; DOM replacement mid-capture; duplicate node IDs across document epochs; pruning preserves all evidence handles. Measure end-to-end CPU and serialization in synthetic fixtures, not only pure-function speed.

**Migration:** emit a V1-compatible metadata result from V2 graph in offline comparisons. No live dual-read mode is authorized by this roadmap. Keep `workspace.js` provider proof independent of graph construction.

**Risk/payoff:** high integration/privacy risk; largest shared-code payoff. Exit when normalized graphs are deterministic within an epoch, bounded, value-free and do not broaden capture scope on failure. Full browser accessibility/paint channels unavailable to X1 must remain explicitly unavailable.

## Phase 2 — Control and Relationship views

**Reuse:** Playwright role/IDREF semantics, Crawlee's nested ownership/reference/cycle pattern, and existing FreightDesk direct/new/visible/selected evidence. Study Skyvern target-state distinctions without copying AGPL code.

**Build/change:** typed controls and many-to-many control→target edges; distinguish undeclared, dangling, ambiguous and resolved references. Rank explicit ownership before structural relations. Normalize tabs, menus, accordions and dialogs as candidates without treating them as permitted actions. AscendAdapter supplies known section vocabulary and existing exact identity/acceptance strategies.

**Required tests:** multiple IDREFs, duplicate IDs, missing targets, explicit label/heading disagreement, hidden versus visible panel, sibling region after a heading, nested forms, multiple selected controls, roleless control, modal overlay, unrelated chrome. A portal outside the shell needs fresh exact entity ownership; same document and an ARIA reference alone are insufficient. The expected section parameter never counts as evidence.

**Migration:** route existing section proofs through typed edges one strategy at a time; preserve failed predicates and ambiguity behavior. Do not invent live provider rules to make generic fixtures pass.

**Risk/payoff:** high semantic risk; directly reduces repetitive section predicates. Exit when generic relationship mechanics can express the currently observed proof without embedding Ascend names in core, and ambiguous ownership still stops.

## Phase 3 — Schema view: forms, fields, tables and variation

**Reuse:** Playwright native label/group semantics; standards-based original table occupancy/header algorithms informed by axe-core. Keep current Ascend data-bearing-grid selection and required header acceptance. Crawl4AI's nested-schema concept is a reference, not a runtime dependency.

**Build/change:** Field/Form/Section structures with label evidence, group ownership, optionality and candidate meanings. Separate schema shape, identity/navigation bindings and instance observations. Implement HTML logical table topology separately from ARIA row/column indexing; preserve physical DOM versus logical versus visible column positions. Bound spans/indices/slot allocation before building matrices. Report unknown virtualized or paginated coverage rather than synthesizing missing rows.

**Required tests:** explicit and implicit labels, multiple agreeing/conflicting labels, fieldsets, custom controls, absent optional fields, unknown units/timezones, changed ordering, conditional sections, cross-load variation versus identity/navigation drift. Tables: multilevel headers, colspan/rowspan including row-group `rowspan=0`, nested tables, fixed header clone plus data grid, multiple real grids, hidden columns, ARIA gaps/indices, huge malicious spans, busy initialization, incomplete page-size/next-page evidence. Never pad/truncate malformed provider rows.

**Migration:** compare V2 candidate schemas with V1 metadata without changing activation. Preserve append-only original V1 maps and provenance; schema version 2 does not imply a stronger evidence maturity. Existing operational board reads remain behind their separate authority and VISIBLE_BOARD_ONLY constraint.

**Risk/payoff:** high edge-case risk; high reduction in bespoke schema traversal. Exit on fixture parity plus explicit handling of variation, topology ambiguity and incomplete coverage. Metadata-only field proposals do not qualify operational value reads.

## Phase 4 — LocatorEngine portfolio and adaptive candidates

**Reuse:** Playwright candidate ranking/uniqueness patterns, Finder's compact CSS search and Scrapling's signatures. Healenium path/node separation is an algorithm reference; do not import Java/Selenium/backend or unreviewed artifact classes.

**Build/change:** exact verified semantic locators first; alternative typed locator portfolio second; bounded same-scope similarity proposals third. Search is lazy/best-first with hard limits on expansion, ancestry, queries, bytes and optimization. Expose evidence contributions and candidate separation; missing information cannot increase certainty. Verified exemplars are immutable; candidate remaps have separate history and cannot overwrite them.

**Required tests:** reordered siblings, wrapper changes, disappearing stable IDs, duplicate logical controls in different loads/sections, stale selector still matching the wrong element, duplicate unique-looking attributes, CSS escaping, private selector operands, semantic conflict despite high similarity, tied scores, high branching before timeout, geometry-only similarity. Every accepted locator must resolve uniquely to the observed target under fresh identity and action classification.

**Migration:** retain exact current matching as the first stage; initially report alternatives only in offline candidate receipts. No automatic activation, click or live healing is authorized. Do not adopt upstream fixed thresholds as calibrated probabilities.

**Risk/payoff:** high wrong-target risk; strong long-term resilience and code reuse. Exit after false-match adversarial cases are rejected and all candidates have scope/provenance. Numeric score alone never passes identity or policy.

## Phase 5 — StateDiff, causal evidence and ApplicationStateGraph

**Reuse:** rrweb added/moved/dropped bookkeeping and ordering; existing FreightDesk causal relevance categories. Independently implement scoped deferred-visibility sweeps inspired by Skyvern. No recorder, raw mutation payloads or DOM stamping.

**Build/change:** metadata-only MutationJournal plus bounded visible/selected-state resampling. Match stable handles within a document; represent remounts as candidate correspondence rather than inheriting identity. Fence before/action/after by sequence and epoch. State keys include verified entity and section, not just URL. Navigation edges carry typed action, prerequisites, provider bindings, postconditions and competing-event evidence.

**Required tests:** unchanged document session refresh retains observer; replacement document cancels and requires fresh proof; background refresh coinciding with click; newly visible panel without second mutation; concurrent owner navigation; node move/remove/reinsert; virtualized row reuse; same route different load; event overflow/gaps; delayed stale ACK. Distinguish provider-bound causality, observed correlation and unbound change.

**Migration:** preserve current A/B/C/D signals as explicit evidence, replacing only their storage/matching mechanics. OBSERVE records owner navigation; a future authorized AUTO_MAP uses already reviewed read-only edges. Building the graph does not authorize automatic exploration.

**Risk/payoff:** highest causal correctness risk; major reduction in repeated whole-workspace scans. Exit when unrelated events cannot produce a verified transition and a missing event produces a coverage gap, not invented causal certainty.

## Phase 6 — Recovery and end-to-end integration

**Reuse:** Playwright context cancellation/re-resolution, Stagehand module-capability registry ideas, Crawlee lifecycle ownership and FreightDesk's existing reliable coordinator/read-job wake/cleanup behavior.

**Build/change:** RecoveryPlanner emits only fixed typed proposals: repeat a safe observation within its remaining budget, resolve a fresh same-scope locator, request fresh document proof, wait for owner readiness, propose new structure, or stop. Preserve terminal revoke and safe durable failure receipts. No retry of an uncertain navigation/action and no recovery by changing tab/profile/authentication automatically.

**Required tests:** actual offline coordinator→RuntimeAccess→native host→worker→router→content→synthetic DOM→mapping persistence→result path. Cover first capture, unchanged-session refresh, observer persistence, foreground/presence waiting before deadlines, correct section, second owner-opened load, optional variation, unrelated read completion, navigation review, revoke, no post-revoke dispatch/read acceptance, crash between map commit and coordinator result, reconnect and complete job-owned cleanup. A stale or malformed receipt cannot satisfy any stage.

**Migration:** after offline acceptance, prepare a separately approved rollout with exact source/runtime revision handshakes and one metadata-only capture. Retain V1 rollback data and protocol compatibility while a job is outstanding; never hot-swap an in-flight observation's semantics. Rollback revokes only job-owned authority and leaves evidence/history intact.

**Risk/payoff:** medium implementation risk but high safety consequence; fewer opaque stalls. Exit only when all integrated boundaries are exercised with failure injection and surfaced stop codes are precise. Live success is a later owner-authorized milestone, not implied by offline completion.

## Phase 7 — semantic/agent fallback, then separately scoped visual research

**Reuse:** bounded proposal/validate/feedback loops from Crawl4AI and observe/extract/history concepts from Stagehand, Browser Use and Skyvern, subject to provenance decisions. Use original typed implementations; do not adopt any agent executor.

**Build/change:** model input is a frozen sanitized graph subset. Model output is candidate relationships/semantic interpretations referencing existing nodes and approved tokens, never JavaScript, free-form selectors or permissions. Deterministic checks validate cardinality, identity, scope, policy and every required fixture. Exhaustion returns UNKNOWN. Visual fallback remains a separate design/authorization because screenshots can contain private values and exceed this metadata-only boundary.

**Required tests:** hostile provider text and prompt injection; invented node IDs/labels; attempts to request writes or expand scope; best-effort schema after failed validation; one passing sample among several failing samples; correlated unsupported claims; malformed responses; hard iteration/payload budgets; no raw values in prompts/traces; no executor reference accessible to a model.

**Migration:** advisory offline proposals first, human/provider-contract review second; no direct deployment into navigation or value extraction. Deterministic → adaptive → semantic → agentic → visual is an escalation hierarchy, not permission to run all layers automatically.

**Risk/payoff:** high uncertainty; potential assistance on unknown interfaces after the deterministic core works. Defer it rather than using an LLM to hide missing graph evidence.

## Validation and migration decision gates

The first implementation approval should cover **Phases 0–2 offline**, not all future provider actions. Review source-derived units and license notices before merging them. Freeze fixture and integration results before preparing a live plan. Normal project checks apply to changed production code when that future implementation happens; no such tests were run for this documentation-only research.

Subsequent live validation needs separate owner authorization and actual current provider proof. A conservative first case remains one owner-opened verified load/section, metadata-only, with exact worker/content revisions, bounded capture, a candidate map and job-owned cleanup. Cross-load validation follows only after that capture passes; use a small representative cohort to test generalization, not a permanent normal-mode allowlist. Navigation and AUTO_MAP require their own reviewed control contracts. Do not resume the closed five-attempt causal-debugging authorization.

No V2 phase can inherit a LIVE_VALIDATED claim solely from V1, library popularity, fixture success or matching field count. Current V1 exact 1763/Load Basics success remains intact; V2 behavior, other sections, field meanings and traversal are separate claims.

## Estimated engineering reduction

This is an explicit planning model, **not measured productivity data or an implementation quote**. It estimates browser-intelligence work only; security, product workflows, FreightDesk business rules and provider validation are largely retained work.

| Hypothetical new browser-intelligence work | Share of 100 planning units | Gross avoided reinvention from studied primitives |
| --- | --- | --- |
| Representation, semantics and normalization | 25 | 10–13 |
| Controls, relationships and schema topology | 20 | 5–8 |
| Selector generation and adaptive retrieval | 20 | 10–13 |
| Diffing and lifecycle/recovery mechanics | 15 | 5–8 |
| Evidence, business identity, policy and acceptance integration | 20 | 3–5 |
| **Total** | **100** | **33–47** |

Budget roughly 10–15 units for adapting privacy/scope/bounds, provenance and X1 integration. Subtracting the ranges yields about 18–37 units net; round conservatively to a **20–35% planning estimate**. No speedup from blindly adopting AGPL/custom-license code or entire frameworks is assumed. Re-estimate after Phases 1–2 by comparing delivered generic behaviors, integration effort and rejected false matches. Do not extrapolate this percentage to all FreightDesk development or promise a calendar completion date from it.

The 5–10 second product goal for known read-only sections is a future measured target, not demonstrated by source review. Existing one-section timing does not predict a multi-section run. Profile provider render time, content capture, transport, verification and persistence separately before choosing concurrency or budgets.

## Recommended implementation model and remaining risk

Use **GPT-6 Astra — Ultra in this Codex app** for the initial graph contracts, privacy boundary and integrated migration review, matching the owner's requested setting. Astra is described in the [official model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra) as suited to complex coding and research; choosing Ultra here is an engineering recommendation, not a benchmark finding. The app's supported effort label is separate from the public API's documented effort names. Once interfaces stabilize, bounded fixture and helper work can use Astra at Medium/High with final architectural review.

The largest unresolved problem is deterministic **business ownership and read-only effect** in imperfect SPA markup during concurrent updates. The inspected libraries improve evidence acquisition and relocation but do not prove that an apparently similar panel still belongs to the same load or that an arbitrary button is harmless. V2 must preserve UNKNOWN and stop on conflicting ownership; it must never make that uncertainty disappear through broader scanning, a model guess or automatic healing.

Recommended sequence: **invariants → document graph → control relationships → schema topology → locator portfolio → state/causal graph → integrated recovery → advisory semantic fallback**. Implementation remains unstarted and requires owner approval.
