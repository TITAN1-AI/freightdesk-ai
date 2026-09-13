> Latest owner milestone: source0.5.0 [workspace Mapping Mode](ASCEND_X1_MAPPING_MODE.md)
> supersedes the proposed per-panel detail -03. First validation cohort is not a permanent ID limit.
> OBSERVE and AUTO_MAP use separate owner lease scopes; normal AUTO_MAP requires reviewed cohort proof. No live execution or
> new capability promotion here. Earlier version/attempt instructions below are historical.

# X1 0.4.3 causal detail-container correction

Local evidence review and offline implementation, 2026-09-11. No live browser/vendor action,
enrollment/transport change, lease mutation, new grant or detail attempt was executed.

## Evidence for owner-x1-detail-20260911-02

A query-only transaction inspected the existing runtime.sqlite3 under
C:\FreightDeskRuntime\Data\booking-logistics\ascend-native. Only approved operation/stage/time,
boolean/count and exact authorized load-ID metadata was printed. No private provider values.

| Fact | Finding |
| --- | --- |
| Attempt | CONSUMED; queued 23:22:24.090593 UTC for 1755 |
| Fresh board prerequisite | Successful receipt 23:22:34.918567 UTC; eight rows; unchanged semantic board hash |
| Exact row | ASCEND_FIND_LOAD succeeded at 23:22:34.975486 UTC, exact_row=true |
| Opener | Successful FIND code path requires a unique safe opener in that row; no separate opener metadata was saved |
| Failure operation | ASCEND_OPEN_LOAD_READONLY, dispatched 23:22:34.999640 UTC |
| Failure | DETAIL_BOUND_CONTAINERS at 23:22:35.034615 UTC; about 35 ms after dispatch |
| Old maximum | 12; used for global container matches, forms within each container, and diff results |
| Exact measured count | NOT RECORDED. More than 12 in the failing check; do not invent a count of exactly 13 |
| Category contributions | NOT RECORDED; dialogs/panels/forms/tabs/changed/referenced counts unavailable |
| Detail identity / mapping | identity_verified=false; no DISCOVER_DETAIL_CONTRACT dispatch or saved contract for this attempt |
| Click stage | Not explicitly recorded. Pre-click snapshot failure is a strong inference from 35 ms versus the code's 100 ms minimum wait before the first post-click diff |
| Existing prerequisite systems | Healthy preceding receipts; no enrollment, host, scheduler, session, view or board-schema diagnosis needed |

The failure is inside WebBridge container discovery invoked by OPEN, not inside operational field
mapping. The generic bound does not establish whether the initial selector match list or a nested
form list exceeded 12. Prior artifacts cannot recover that distinction or prove exactly which
unrelated containers were present.

## Root defect

The old DOMSnapshot called querySelectorAll on dialogs, modal/side-panel containers, tabpanels and
data-load-detail containers across the document, then applied the 12-item bound **before** visibility
or causal relevance. It inspected headings/attributes and descendant forms for every snapshot
container, including unchanged unrelated layout. DOMDiff took another such snapshot before filtering.
Thus unrelated containers could exhaust the same budget needed for the exact clicked detail root.
This is a deterministic design defect; the unrecorded live count/category remains unknown.

## Scoped implementation

The exact row/opener, fixed click executor, board freshness, provider identity and all write gates
remain unchanged. Source 0.4.3 replaces the generic WebBridge container budget with:

| Bound | Maximum |
| --- | --- |
| direct_targets | 4 distinct opener/row target IDs or resolved target elements |
| new_containers | 8 distinct newly created causal roots |
| newly_visible | 8 distinct newly visible causal roots |
| changed_selected | 4 roots with selection changes connected to the target row/opener |
| identity_candidates | 64 identity candidates inside the selected root; existing guard preserved |
| opener_attributes | 24 attributes on the exact opener |

DOMSnapshot keeps a lightweight, ephemeral membership/visibility/selection index of fixed semantic
container types. It does not traverse each container's headings, forms, controls or raw text, nor
recursively enumerate all document nodes. There is no generic 12-container cap on this baseline:
unchanged unrelated elements are excluded before causal bounds, not granted a larger read budget.
Navigation, headers/footers and navigation/banner/contentinfo regions are excluded as page chrome.
Forms are included as possible roots; forms/tabpanels nested in an equally or more strongly related
root are folded into that root before counting. No baseline DOM, selector IDs or raw text is stored.

LocatorGraph and EvidenceScorer rank these provider relationships deterministically:

| Rank | Score | Relationship |
| --- | --- | --- |
| A | 400 | Exact opener/row aria-controls, href fragment, data-target or data-bs-target reference |
| B | 300 | Newly created semantic detail container after the single click |
| C | 200 | Previously hidden container became visible |
| D | 100 | Selected/active state changed and the container is connected by provider identity/labelledby binding to the exact row/opener |

Direct references resolve exact escaped IDs, including duplicate matches; they cannot target body,
document root or page chrome. A direct div/section target need not use a guessed modal CSS class.
Arbitrary script text or selectors are never accepted from a command. Unconnected selection changes
and unchanged page layout contribute zero causal candidates.

AdaptiveLocator selects only the unique strongest root. Equal highest scores, including duplicate
provider target IDs, stop as DETAIL_IDENTITY_AMBIGUOUS. A relevance score only selects a place to
verify identity; it is not identity proof. Existing provider field/opener/selected-row identity
strategies remain mandatory. Field mapping follows successful identity and uses the unchanged
metadata-only field contract. Generic structural/heading changes alone no longer admit a root.

Bound failures now use exact codes such as DETAIL_BOUND_NEW_CONTAINERS and
DETAIL_BOUND_DIRECT_TARGETS. Structural diagnostics retain stage, click_dispatched, row/opener
verification flags, baseline/ignored counts, category counts, rank/reasons, selected level, and
failed category/measured/maximum. BEFORE_CLICK, AFTER_CLICK, DOM_DIFF, IDENTITY and FIELD_MAPPING
are distinguished. No raw values, attribute values, customer data, phones, addresses, notes, HTML,
screenshots, network data or secrets are persisted.

Content results carry this typed metadata to attempt-linked runtime receipts, audit and status.
Attempt reports read the matching persisted failure, not a later global runtime error. Legacy
view-only receipts are matched within the queue-to-next-queue interval and retain UNKNOWN diagnostics.
Nested null fields are preserved for strict validation. Successful identity/contract receipts retain
the ranked container proof; reports expose that metadata with the exact validated load ID.

Build is 0.4.3 across manifest, worker, content and host; existing protocol versions, permissions,
enrollment, Native Messaging architecture and board schema are unchanged. Reload is needed to adopt
the packaged reader changes. No field capability or 0.4.3 compatibility is LIVE_VALIDATED.

## Prepared owner retry — not executed

Proposed unused ID: **owner-x1-detail-20260911-03**, checked absent from the local attempt ledger.
It is not reserved, queued or consumed. Attempt -02 remains consumed and unchanged.

1. Disable the previous stopped read lease, then reload the existing pinned X1 extension to 0.4.3.
   Retain the authenticated Ascend tab and enrollment; no re-pair, manual page refresh or repair.

   ```powershell
   Set-Location 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime disable --owner-executed
   ```

2. When ready for a live owner-executed retry, use the existing bounded lease flow:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime enable --owner-executed --hours 0.1 --interval-seconds 60
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime status --owner-executed
   ```

   Wait for READ_ONLY_READY / AUTHENTICATED / ACTIVE_LOADS / CURRENT_VERIFIED_BOARD with a fresh
   board sync and 1755 present. These are unchanged queue gates, not a new prerequisite investigation.
   Do not use retained evidence to queue. If 1755 is absent, stop without substituting a load.
3. Queue exactly one discovery:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_detail queue --owner-executed --attempt-id owner-x1-detail-20260911-03 --load-id 1755
   ```

   Do not click other rows/tabs or queue another load while it runs. The executor clicks once.
4. After its automatic stop, read the attempt-specific report and disable the lease:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_detail report --owner-executed --attempt-id owner-x1-detail-20260911-03
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime disable --owner-executed
   ```

Expected success is conditional: DETAIL_DISCOVERY_COMPLETE, validated load1755 and provider-backed
identity, selected causal level/counts, versioned CANDIDATE_ONLY contract, per-field presence/mapping
levels, values_included=false, production_writes=false, live_validated=false. Unknown/ambiguous
field mappings stay UNKNOWN. Successful discovery is not automatic activation or live validation.

Stop on an exceeded category bound, equal top-ranked containers, missing/conflicting provider
identity, changed row/opener/document/board, unsafe opener, lease/policy failure, invalid metadata
or persistence failure. Save the sanitized report; do not retry automatically or queue a fourth
attempt. No CarrierView, Outlook, operational values, writes, canonical mutation or communication.

## Offline verification

153 targeted tests passed across causal DOM fixtures, existing WebBridge mapping, exact identity,
one-attempt lifecycle, runtime/controller, content transport, build handshakes and attempt reports.
The tests include many unchanged visible containers/forms, page chrome, new/hidden/direct roots,
strong-versus-weak relationships, duplicate target IDs, equal-rank ambiguity, every new bound code,
identity-before-value-access, consumed/revoked attempts, strict diagnostic validation and no-write
commands. The old failure's exact DOM/count is unavailable and is not claimed as a fixture.
Existing Starlette/httpx and AnyIO deprecation warnings remain. All browser requests were fulfilled
locally in isolated test profiles under C:\FreightDeskRuntime\Data\TestRuns; no live execution.
The final attempt-report subset passed41/41; Ruff and JavaScript syntax passed. Sanitized local
review: C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\detail-container-review-20260911-02.json.
This review file is an analysis artifact, not a provider observation or new authorization.
