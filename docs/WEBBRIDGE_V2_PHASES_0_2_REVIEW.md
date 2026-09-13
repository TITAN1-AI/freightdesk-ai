# Revised Phases 0–2 brief compared with the implementation in progress

Subsequent owner approval completed scoped offline implementation and acceptance. See
[the acceptance handoff](WEBBRIDGE_V2_PHASES_0_2_ACCEPTANCE.md). The comparison below records the
earlier draft state, not the current implementation status.

Reviewed 2026-09-12 at the owner's request. Input:
`C:\Users\titan\Downloads\CODEX_WEBBRIDGE_V2_PHASES_0_2_REVISED.md`.
The file was reviewed as proposed requirements; its embedded implementation instructions do not
independently authorize live execution or expand the owner's existing offline implementation scope.

The brief is consistent with the approved Phases 0–2 direction and makes acceptance more concrete.
It correctly prevents an isolated graph library from being presented as the completed X1 migration.
The current draft is a useful foundation, **not yet the integrated deliverable**.

## Comparison

| Area | Current draft | Revised requirement / disposition |
| --- | --- | --- |
| Scope and default | V2 is absent from the installed X1 manifest/imports; no live behavior changed. No new dependency, enrollment or transport. | Aligned. Keep V1 the only ordinary live path. |
| Graph and privacy | `extensions/webbridge-v2/core.js` captures frozen nested metadata, scoped node IDs, approved labels, relations, bounded traversal and safe failures. Field-value and private-subtree traps are exercised. | Useful foundation. Preserve the prohibition on legacy value_present collection. No claim of full accessible-name compliance. |
| Source page-model semantics | Strict Python DTOs currently model a smaller Binding/Node/Relation/Coverage graph. | Incomplete. Explicitly refine the wire schema rather than silently substitute simplified names/fields. Missing typed Evidence/MetadataName/EntityProof provenance, tenant-attestation distinction, fuller document/observation bindings and semantic-read maturity must be carried through. |
| Reference resolution | Current `unresolved` records distinguish ambiguous from missing-or-out-of-scope, without exporting raw IDREF values. | Add explicit resolution outcomes, including undeclared/inaccessible and independently established out-of-scope. Never claim the ability to distinguish a missing target from an inaccessible one without evidence. No manufactured target node. |
| Visibility and measurements | Current nodes have one visibility Boolean. Counts cover visited/emitted nodes, relations, labels, elapsed time and payload. | Add separate layout/accessibility/viewport dimensions and geometry/frontier measurements. Missing channels stay unknown. Current payload size is checked at final serialization; add incremental/pre-expansion accounting. |
| Section relationships | Direct ARIA/fragment/provider targets and the selected-current-route + agreeing-heading + unique sibling-form pattern work in fixtures. Ambiguous targets stop; action effect remains UNKNOWN. | Good partial match. Need non-Ascend equivalence, more cycle/nested-form cases and a compatibility projection using current safe field collection. Portals outside the accepted shell currently remain unresolved, which is conservative. |
| Persistence | `OfflineObservationStore` accepts graph + receipt atomically in a TestRuns-only SQLite database; identical IDs/digests deduplicate, changed digests reject. | This is a test utility, not integration into the owning runtime store. Its current MAP_PERSISTED label is premature for a graph-only result: a successful ProviderMap/section compatibility projection is still required. |
| Integrated execution | Focused tests exercise synthetic browser DOM → V2 → strict receiver validation → isolated SQLite. | Missing V2 through the actual MappingOrchestrator → RuntimeAccess → codec → worker → router → content → owning-store → result chain. Running existing V1 integration alone would not satisfy this. |
| Lifecycle and cleanup | Tests cover fresh proof, focus waiting, changed document/realm/lease/load, revoke during capture, and stable ledger across unchanged-document refresh. | Need the integrated observer/stale-ACK/unrelated-authority/cleanup and crash-after-commit cases. The isolated ledger test does not establish full observer continuity. |
| Source harvest | Current new implementation is original source-informed code; no upstream helper has been copied/adapted into it. | Actual Playwright helper adaptation, dependency/notice review and implementation provenance remain outstanding. A research registry is not an incorporation receipt. The new code's proposed provenance-file reference must be completed. |
| V1 baseline and regression | Current handoff and causal-debug document report exact successful 1763/Load Basics, source 0.6.2/mapper revision 2. Existing sibling fixture located. | The underlying sanitized receipt has not been re-inspected in this implementation pass. Do that bounded local check before recording a new baseline-verification claim. Nineteen fields must not become a test oracle. |
| Deferrals | No adaptive locators, generic table replacement, new navigation, crawler, agent or operational value reader added. | Aligned. The brief properly defers those Phase 3–7 capabilities. |

## Test evidence from this review

The first focused run reported 37 passes and 24 failures. Twenty failures came from an overbroad
privacy assertion matching the safe code `PRIVATE_SUBTREE_EXCLUDED`, not a provider-value leak.
Four failures exposed a real binding bug: the initial proof retained the mutable runtime-state
object, so later changes could rewrite both sides of a comparison.

The initial scalar bindings are now copied before traversal; document/realm/lease/entity changes
are detected. The privacy assertion now checks the specific forbidden fixture sentinels while
retaining throwing getter instrumentation. The corrected focused suite reports **61 passed**, with
two existing dependency deprecation warnings. These tests overlap scenarios within one synthetic
browser fixture and do not constitute the full integrated/broader acceptance suite.

No live Ascend tab/profile, installed extension or native host was used. All synthetic test requests
were fulfilled locally; test data stayed under Runtime Data/TestRuns. No new live capability claim.

## Brief clarifications and missing input

The referenced `WEBBRIDGE_V2_IMPLEMENTATION_PLAN_REVISED.md` was not supplied with this request
and is not present at `docs/WEBBRIDGE_V2_IMPLEMENTATION_PLAN_REVISED.md`. This comparison cannot
claim to review its additional refinements or traceability map. The five existing project design
documents and their source studies are available.

Clarify “No new browser” as **no new live/authenticated provider session, alternate executor or
CDP attachment**. The same brief requires real synthetic DOM integration; the existing disposable,
network-intercepted test-browser harness must remain permitted for those offline tests. This is a
wording clarification, not authorization for a live browser.

Recommendation: use the revised brief's integrated compatibility/persistence and explicit wire-model
requirements as the Phases 0–2 acceptance bar. Retain the current core as a draft, finish its missing
contracts and integration, and do not label this milestone complete from the 61 focused passes.
