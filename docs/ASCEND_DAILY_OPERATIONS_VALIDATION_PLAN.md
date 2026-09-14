# Ascend daily operations: proposed release and validation plan

Execution update 2026-09-13: owner explicitly authorized proceeding. Release preparation and the
first bounded installed X1 metadata validation are now in progress. Keep later gates dependent on
their actual evidence; no production write permission or V2 activation is granted by this update.
Execution initially stopped at the Windows native-executable trust gate. The owner then manually
disabled Smart App Control: candidate startup, guarded native installation, pinned0.6.3 reload and
local reconnect now succeed. Fresh content/workspace proof remains pending; no new lease/read yet.
See [the X1 0.6.3 release handoff](ASCEND_X1_RELEASE_063.md); installation is not provider acceptance.

Originally prepared 2026-09-13 in response to the owner's readiness question before execution approval.
At that planning stage no installation, browser, host, lease or vendor action was performed.
The closed five-iteration authorization remains closed. Numerical acceptance targets
below are proposed pilot criteria, not measured reliability or an owner-approved service level.

## First useful product

A read-only Ascend operations desk showing verified pickup/delivery work, selected load context,
missing/stale information and items requiring owner review. Each item shows its source, observation
time and coverage. The owner continues performing operational changes in Ascend.

Initially scope this to independently verified Active Loads and the visible board. Planning and
accounting views must be qualified separately before claiming coverage of all current operations.
The operating date and timezone policy must be explicit; historical 8/3 counts and old load cohorts
are not current business expectations. Missing timezone evidence remains unknown.

Use the existing X1/V1 executor as the controlled baseline. V2 qualification is a separate, explicit
release decision using the same acceptance cases; it cannot inherit V1 live evidence. V2 remains
absent from the live manifest and fixture/TestRuns-gated until an approved migration is prepared.

## Actual starting point

- Prior live evidence proves local transport, bounded repeated board reads/no-op/revoke, and one
  exact Load 1763 / Load Basics metadata capture. It does not prove today's session is ready.
- The repaired source passed 967 tests plus lint/dashboard checks in GitHub run 34773561853.
  These are automated tests, not new provider validation. The installed native host was not updated.
- `scripts/webbridge_v2_release.py` creates an offline source manifest and source-only rollback
  rehearsal. It is not an installer. Its audited pre-repair baseline is not a safe production fallback.
- `MappingOrchestrator` explicitly waits at `REVIEW_OPERATIONS_SCOPE` for `CURRENT_OPERATIONS`.
  Removing that wait would not supply verified view contracts or operational data.
- `VerifiedAscendLoadContextAssembler` accepts separately validated observations. Metadata maps do
  not supply those values. Its current flat field grouping is not a completed per-stop data model:
  repeated appointment fields cannot establish a correctly ordered multi-stop itinerary.
- General OBSERVE, reviewed AUTO_MAP, operational field meaning and all-load coverage remain unproven.

Evidence: [current repair handoff](WEBBRIDGE_V2_AUDIT_FIXES.md),
[exact live capture](ASCEND_X1_SESSION_CAUSAL_DEBUG.md),
[board runtime](ASCEND_X1_RUNTIME.md), and [capability matrix](../LIVE_POC.md).
Older commands and version numbers in historical handoffs are not the next execution procedure.

## Ordered gates

| Gate | Engineering/preparation | Required evidence to advance |
| --- | --- | --- |
| 1. Reproducible installed release | Prepare a new identified candidate covering extension, worker, content, Python host and compiled launcher. Include source hashes, protocol compatibility, update instructions and a tested rollback procedure. | Installed components prove the expected revisions and compatible bindings; local transport works with provider reads disabled. |
| 2. One exact workspace | After fresh bounded authorization, use the existing pinned extension/session for one currently available, owner-confirmed load and section. Load 1763 / Load Basics is a reference case, not assumed current. | Session/readiness, dispatch/ACK, exact provider load identity before/after capture, one candidate metadata map, complete job-owned cleanup. |
| 3. Representative structure and navigation | Observe 3–5 owner-approved loads spanning available operational states; include conditional fields and multiple stops where available. Review actual provider navigation relationships, then run controlled AUTO_MAP cycles. | Every cohort load independently identified; every traversed section proved; return to start recorded; optional variation distinguished from identity/navigation drift; zero value capture during mapping. |
| 4. Operational read contracts | Implement the bounded value-reader/validation path for the chosen field subset and connect it to the protected dashboard. Add per-stop identity/order, appointments and provenance rather than flattening repeated fields. | Compare every released critical field with the owner-visible provider source. Disagreement blocks that field; missing, stale, conflicting or unsupported values remain explicit. |
| 5. Useful operations view | Implement the reviewed view/coverage policy behind the operations scope. Start with Active Loads; qualify other needed views separately. Derive date-based worklists only from verified dates and known timezone rules. | Owner reconciles the visible worklist and its stated coverage. No partial board is represented as account-wide completeness. Every derived item links to source facts. |
| 6. Supervised daily pilot | Run during normal owner work, exercise recovery deliberately within approved scope, and review discrepancies daily. | Meet the pilot criteria below before relying on the released capabilities for everyday read-only assistance. |

No gate promotes writes. A passed transport test cannot satisfy workspace identity; a metadata map
cannot satisfy value correctness; an AUTO_MAP qualification cannot authorize a new field reader.

## Release preparation details

Inventory the installed versions and pending jobs through an explicitly authorized, sanitized local
preflight. Do not hot-swap components while a job owns an observation. Wait for unrelated jobs or
coordinate a maintenance window; never revoke unrelated authority or erase consumed history.

Use the existing pinned extension ID and approved Edge profile. Keep enrollment, permissions and
host registration unchanged unless an actual deployment prerequisite is separately reviewed.
The existing `RebuildLauncher` helper is relevant to the compiled-host repair, but currently builds
directly into the registered binary path. Prepare staging, replacement/recovery and rollback checks
before treating it as a reliable release installer. Do not run it merely to inspect status.

Record the known installed artifact state before an approved update. Test candidate artifacts and
rollback using isolated fixtures first. Any runtime database backup/migration must preserve audit,
pairing and lease history; never restore old authority to make an old build appear healthy.

The final reviewed execution sheet must specify the exact release, approved workspace, allowed
operations, budgets, receipts, stop conditions and cleanup. Generate a fresh internal job ID only
when that authorized execution begins. Do not reuse historical attempt IDs.

Microsoft documents that Edge does not install/manage the native application host with the
extension. Therefore an extension reload alone does not deploy the compiled-host fix.
[Microsoft Edge native messaging](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging).

## First operational field set

Proposed minimum: provider load ID/status/reference, customer, ordered pickup/delivery stops,
appointment windows with raw timezone evidence, carrier and equipment. Add driver/contact/assets
only when needed and separately authorized for private value reads. Documents, financials, private
notes, billing readiness and communications are outside the first release.

Verify status and appointment meanings as well as selector identity. Preserve raw provider facts
separately from FreightDesk classifications. A field's presence is not a nonempty business value.
Use the historical export/CarrierView replay only where identity and time context genuinely match;
they cannot prove current assignments, current rates or today's tracking state.

Metadata diagnostics remain value-free. Authorized operational values belong only in protected local
runtime storage/UI under C:\FreightDeskRuntime. They never enter GitHub, general logs or screenshots.
The repo is public; defect fixtures must be synthetic and diagnostic receipts sanitized.

## Proposed pilot acceptance

Use three normal business days and at least 50 eligible capture cycles across at least ten
owner-opened loads. If normal work provides fewer, extend the observation period instead of crawling
other loads. Count all failures and field mismatches, including fixed failures; do not discard them
to improve the result. A new build requires requalification of the affected acceptance cases.

- Zero incorrect workspace identities, cross-load field contamination, unauthorized actions or
  private values in metadata diagnostics. Any occurrence stops the affected capability immediately.
- All sampled critical fields accepted as verified match the provider comparison; unresolved fields
  remain unknown and the load is marked partial. Partial captures do not count as complete context.
- At least 95% of eligible captures finish without engineering intervention. Track owner absence,
  expired leases and login waits separately; they must be visible and never masquerade as success.
- Proposed performance goal: 95th-percentile complete-context acquisition within ten seconds for
  the released, known sections after foreground/session readiness. Measure readiness waiting too.
  This is not yet an achieved timing claim or a promise for unsupported sections.
- Exercise popup close, worker suspension/reconnect, host restart, same-document refresh, document
  replacement, focus loss, competing reads, network loss, session expiry, lease expiry and revoke.
  Recovery must reprove its bindings and remain within existing authority; uncertain navigation is
  not automatically retried.
- Unchanged board cycles produce no duplicate proposals. New observations retain provenance and
  remain unapplied. Revoke produces no later read/dispatch and clears only job-owned authority.
- Every stop supplies a safe code, last completed stage, failed predicate, owner action and cleanup
  state. The operator can distinguish CURRENT, STALE, PARTIAL, WAITING and STOPPED evidence.

This small pilot is an initial release gate, not statistical proof of long-term reliability. Continue
monitoring failures, coverage and field correctness after release. Controlled rollouts with explicit
readiness and rollback criteria follow the general practice described in
[Google SRE: reliable product launches](https://sre.google/sre-book/reliable-product-launches/).

## Intended owner routine after qualification

1. Open the existing Ascend session; complete login/MFA when required. Check the intended workspace
   and FreightDesk's build/session/lease/freshness status in the protected dashboard.
2. Explicitly enable the approved board-read lease. Existing defaults are eight hours and five-minute
   polling; use a shorter bounded lease for initial validation. Enabling is an execution action.
3. Open a load and select Map Ascend. The orchestrator handles IDs, proof, capture, reviewed section
   navigation, reporting and cleanup. Normal operation has no permanent 3–5 load allowlist.
4. Owner-present detail mapping retains its short lease and foreground requirements. The board
   lease does not confer all-day background detail reads. Unknown structures return to OBSERVE/review.
5. Work from the scoped pickup/delivery list and review missing/stale/conflicting information. The
   owner makes operational changes in Ascend. Pause/revoke when finished or when evidence is suspect.

Initial structure review is temporary learning work, not a requirement to click every known section
forever. Qualified AUTO_MAP should visit known read-only controls within the exact current load and
return to the starting section. It does not crawl or open other loads.

CarrierView live tracking reconciliation and narrowly scoped Outlook freight evidence follow separate
read-only milestones after Ascend context is dependable. Existing historical/Microsoft validations do
not authorize new networking. Email/SMS, tracking creation, Ascend changes and canonical mutation need
separate policy, validation and explicit authorization.

## Immediate next engineering deliverable

Prepare the versioned X1 release candidate and reviewed installation/rollback procedure, plus one
exact-workspace acceptance job. Keep the first live test metadata-only. Do not activate V2, run
CURRENT_OPERATIONS, collect operational values or consume a grant as part of preparing this plan.
