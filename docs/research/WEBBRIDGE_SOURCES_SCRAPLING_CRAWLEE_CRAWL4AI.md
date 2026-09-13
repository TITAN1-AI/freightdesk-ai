# WebBridge V2 source study: Scrapling, Crawlee and Crawl4AI

Research date: 2026-09-12. This is source analysis and a design proposal, not an implementation or vendor validation. No dependency was installed, framework/demo executed, browser opened, Ascend read performed, or production source/runtime changed for this study. Public source was fetched with shallow, blob-filtered Git snapshots; only selected source directories and root files were materialized.

## Revisions and license evidence

| Project | Exact revision examined | Source snapshot | License observed | Direct-reuse disposition |
|---|---|---|---|---|
| Scrapling | `48da61d1ee85cea7bbbdff013d98c90602e1d93f` (2026-09-12) | `C:/FreightDeskRuntime/Data/Research/WebBridgeV2/Scrapling` | [BSD 3-Clause](https://github.com/D4Vinci/Scrapling/blob/48da61d1ee85cea7bbbdff013d98c90602e1d93f/LICENSE), copyright Karim Shoair | `SAFE_TO_ADAPT_WITH_NOTICE` for selected original parser algorithms; preserve copyright, conditions and disclaimer, reproduce them with binary distribution, no endorsement implication. |
| Crawlee (TypeScript repository) | `0b2ac45323d7be8d9d3d146d4873cec1cafdc095` (2026-09-11) | `C:/FreightDeskRuntime/Data/Research/WebBridgeV2/Crawlee` | [Apache 2.0](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/LICENSE.md), copyright Apify Technologies | `SAFE_TO_ADAPT_WITH_NOTICE` for selected original utilities, subject to Apache license/retained notices/changed-file notices. No separate NOTICE was present in the examined tree. |
| Crawl4AI | `862f6bccb9c063f49b9d42701baa0eea17a4993f` (2026-08-31) | `C:/FreightDeskRuntime/Data/Research/WebBridgeV2/Crawl4AI` | [LICENSE](https://github.com/unclecode/crawl4ai/blob/862f6bccb9c063f49b9d42701baa0eea17a4993f/LICENSE) contains Apache 2.0 **plus an appended attribution requirement**, including prominent credit for public use/web applications/CLI | `PREFER_CLEAN_REIMPLEMENTATION` of general engineering concepts; `REFERENCE_ONLY` for source snippets until the additional terms and upstream provenance are reviewed. Do not record this as unqualified Apache-2.0 clearance. |

The Crawl4AI addendum calls for UncleCode/Crawl4AI credit and names About/Credits and CLI help among display locations. Its legal interaction with Apache 2.0 needs review before code incorporation; this note does not decide enforceability. Root license labels are not a dependency license audit. No code from any of the three repositories has been copied into FreightDesk by this study. Git tree searches found root licenses, Scrapling's separately located agent-skill license, and no separate root NOTICE files; only selected implementation modules were reviewed. Vendored modules such as Crawl4AI's `html2text` have not been cleared for reuse merely because the repository root has a license.

## Source-backed capability decisions

“Best” below is restricted to these three repositories and the named capability, not an assertion about the entire ecosystem.

| Capability | Strongest relevant source among these three | Current FreightDesk equivalent | Decision | Why |
|---|---|---|---|---|
| Historical element relocation | Scrapling `Selector.relocate`, similarity scorer, element signature | `AdaptiveLocator.propose`/`proposeMapping` compare a few exact semantic fields | ADAPT | Add bounded feature-based candidate ranking and explicit competing candidates; omit raw values, whole-tree scanning and automatic acceptance. |
| Repeated sibling structure | Scrapling `find_similar` | No general repeated-structure recognizer; provider-specific board parser | REIMPLEMENT | Useful typed structural clustering primitive, but equal depth/parent assumptions are too rigid and its default threshold is not an identity proof. |
| Selector generation | Scrapling `SelectorsGeneration` | Integer child-index relative paths plus reviewed navigation fingerprints | REFERENCE | Short ID/ancestor paths are useful candidates; implementation lacks uniqueness validation, escaping and ARIA-first ranking required here. |
| Durable recovery lifecycle | Crawlee `RecoverableState` | RuntimeAccess, orchestrator ledger, signed causal receipts | ADAPT | Borrow initialize/teardown ownership and restore validation patterns; keep FreightDesk's authority and SQLite boundaries. |
| Staged extraction attempts | Crawlee `StorageTransaction`, adaptive per-attempt transaction handling | `persist_map` and candidate-only append-only maps | REIMPLEMENT | Stage competing extraction results before committing one accepted observation. Do not import at-least-once external storage delivery or automatic retry. |
| Explicit semantic nesting/references | Crawlee microdata traversal | `navigationTarget`, label association, section inheritance | ADAPT | Scoped recursive ownership, tokenized references and cycle guards are transferable; schema.org values themselves are irrelevant to Ascend mapping unless actually present. |
| Composed tree handling | Crawl4AI shadow serializer, Crawlee shadow/iframe expansion | Light-DOM scoped queries; no general composed DocumentGraph | REIMPLEMENT | Traverse open shadows and slots read-only while preserving roots. Neither flattened HTML format is a safe canonical graph. |
| Content pruning | Crawl4AI `PruningContentFilter` | Bounded, verified workspace and causal-root selection | REFERENCE | Weighted features are useful; article-content defaults remove the forms/navigation the mapper needs. |
| Deterministic extraction schema DSL | Crawl4AI `JsonElementExtractionStrategy` | AscendProviderMap plus approved field candidate vocabulary | REIMPLEMENT | Keep relative nested schema and validation feedback; replace arbitrary selectors/default values/functions with typed graph references and explicit unknowns. |
| Generated schema recovery | Crawl4AI `agenerate_schema` + `_validate_schema` | No model-generated extraction selector activation | REIMPLEMENT | Bounded proposal/validate/refine loop is useful after sanitization; provider identity and acceptance remain deterministic. |
| Table candidate ranking | Crawl4AI `DefaultTableExtraction.is_data_table` | `reader.js:grid` semantic required headers/data-bearing grid/clone rejection | REFERENCE | Useful weak structural features only. Not a substitute for exact board semantics. |
| Table cell alignment | None is sufficient | Ascend's observed 33-column schema and strict mismatches | IGNORE upstream default alignment | Crawl4AI's default path silently duplicates/truncates/pads and does not implement its advertised rowspan handling. |
| Causal control→region relationship | None of the three implements the required proof graph | `containerGraph`, bounded direct/new/visible/selected relationships, section proof | KEEP/REFACTOR FreightDesk; REFERENCE upstream primitives | URL adaptation/content extraction is not control causality. Retain the action-bound evidence boundary and expand its representation. |
| Authenticated session executor | No applicable replacement | X1 native/worker/router/content proof and ActionPolicy | IGNORE framework executors | Launching independent contexts, cookie pools, retries, page mutation or HTTP fallback violates the required deployment boundary. |

## Scrapling: what actually makes relocation work

### Signature, ranking and recovery history

Sources: [`_StorageTools.element_to_dict`](https://github.com/D4Vinci/Scrapling/blob/48da61d1ee85cea7bbbdff013d98c90602e1d93f/scrapling/core/utils/_utils.py#L76), [`Selector.relocate`](https://github.com/D4Vinci/Scrapling/blob/48da61d1ee85cea7bbbdff013d98c90602e1d93f/scrapling/parser.py#L530), [`__calculate_similarity_score`](https://github.com/D4Vinci/Scrapling/blob/48da61d1ee85cea7bbbdff013d98c90602e1d93f/scrapling/parser.py#L822), [`xpath`](https://github.com/D4Vinci/Scrapling/blob/48da61d1ee85cea7bbbdff013d98c90602e1d93f/scrapling/parser.py#L639), [`SQLiteStorageSystem`](https://github.com/D4Vinci/Scrapling/blob/48da61d1ee85cea7bbbdff013d98c90602e1d93f/scrapling/core/storage.py#L74).

The saved signature is a dictionary: element tag, all nonempty attributes, immediate element text, tag-only ancestor path, parent tag/attributes/immediate text, sibling tag sequence, and child tag sequence. This is not an accessibility snapshot or browser-layout model. The stored child sequence is not used by the relocation scorer examined here.

For every descendant candidate in the current lxml subtree, the scorer adds individual checks and divides by the number of checks:

- Exact element tag contributes 0 or 1.
- Immediate text uses Python `difflib.SequenceMatcher` if the original had text.
- Attributes use half the sequence similarity of ordered keys plus half the sequence similarity of ordered values.
- Original `class`, `id`, `href` and `src`, when present, receive additional independent value comparisons, effectively giving these attributes extra influence.
- Tag-only ancestor path, parent name/attributes/text, and sibling tag sequence add further comparisons.
- The result is rounded to two decimal places and multiplied by 100. It is a normalized similarity score, not a calibrated probability.

`relocate` scores the entire current parsed subtree, groups candidates by numeric score, and returns **all** candidates tied at the maximum if it exceeds the default 40 threshold. It deliberately does not stop at the first perfect match. The ordinary CSS/XPath path remains first; adaptive relocation happens only after the selector produces no result and a prior signature exists. A selector that still matches the wrong element does not trigger this fallback. `auto_save` stores the first selected/relocated element, and SQLite uses `INSERT OR REPLACE` on `(base domain, identifier)`. This is a latest-signature cache, not append-only selector history or evidence review. Debug logging can print candidate representations.

Dependencies for these paths: lxml elements/XPath, cssselect CSS conversion, `difflib`, orjson, SQLite/RLock, and `tld` for storage domain grouping. The parser dependencies are separate from optional Playwright/Patchright/curl/browser-fingerprint fetchers, which FreightDesk should not import.

Failure modes: repeated controls with equal structure, dynamic classes/IDs, insertion changing tag paths, attributes with order changes, original/candidate asymmetric parent information, stale selectors that match the wrong control, and low similarity passing without runner-up separation. The signature reads raw text/attributes, including potentially sensitive attribute values. Grouping by registered domain cannot substitute for tenant/workspace/document separation. There is no field semantic verification, visibility/geometry/ARIA computation, authenticated document proof, or write-policy decision in this scorer.

**FreightDesk integration decision: ADAPT, license `SAFE_TO_ADAPT_WITH_NOTICE`.** Introduce a bounded `LocatorSignature` over already-sanitized X1 graph features, with explicit per-feature contributions, omitted-feature reasons, candidate count, top score, next-best score, and a separation threshold. Hard identity/session/workspace/action-class predicates run before ranking and cannot be compensated by similarity. Use append-only provider-contract versions and permit only candidate remaps until independently verified. Do not persist raw DOM text/values/URLs or reuse the SQLite storage implementation unchanged. Cross-load optional-field differences must not retrain a control into a different identity.

FreightDesk's current `AdaptiveLocator` is much smaller: [`webbridge.js`](../../extensions/ascend-x1/webbridge.js) `remap`/`proposeMapping` require exact equality of semantic tuples and emit candidate-only proposals. Scrapling is stronger at ranking structural changes, while FreightDesk is stronger at authority/identity separation. Preserve both strengths rather than replacing the gate with a percentage.

Reviewed upstream tests: [`test_adaptive.py`](https://github.com/D4Vinci/Scrapling/blob/48da61d1ee85cea7bbbdff013d98c90602e1d93f/tests/parser/test_adaptive.py) includes moved element recovery and the empty-result/auto-save threshold regression. These tests were read, not executed; they are not proof against multiple identical load workspaces.

### Repeated-element recognition and selector generation

[`find_similar` and `__are_alike`](https://github.com/D4Vinci/Scrapling/blob/48da61d1ee85cea7bbbdff013d98c90602e1d93f/scrapling/parser.py#L987) first restrict candidates to equal depth and the same element/parent/grandparent tag path. Attribute value similarities are divided by the larger original/candidate attribute count; `href` and `src` are ignored by default and text matching is optional. The default 0.2 threshold targets repeated extraction items rather than reliable element identity. It can seed groups of similarly structured fields/rows, but wrapper insertion breaks its depth assumptions, and similar items are deliberately different entities. **REIMPLEMENT** bounded structural grouping; never convert the result into “same load.”

[`SelectorsGeneration._general_selection`](https://github.com/D4Vinci/Scrapling/blob/48da61d1ee85cea7bbbdff013d98c90602e1d93f/scrapling/core/mixins.py#L15) climbs toward ancestors, stops early at an ID, or adds tag and `nth-of-type` positions. It emits CSS/XPath/full-path variants. In the examined code it does not validate uniqueness, escape arbitrary ID syntax, rank multiple locators, or prefer role/name/test-id. It notes Firefox inspiration in a comment. **REFERENCE** only: use it as a baseline fixture expectation, not the selected V2 locator implementation. A more rigorous selector generator from the wider study should win.

## Crawlee: robust execution primitives, not load-detail intelligence

### “Adaptive” is rendering selection

Sources: [`RenderingTypePredictor`](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/packages/playwright-crawler/src/internals/utils/rendering-type-prediction.ts#L129), [`AdaptivePlaywrightCrawler.runRequestHandler`](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/packages/playwright-crawler/src/internals/adaptive-playwright-crawler.ts#L682).

The predictor stores rendering observations by request label and URL components. Hosts must match; pathname segments are compared with Jaro-Winkler and binarized at 0.8. Two features are mean similarity to previously static and client-only URLs. `ml-logistic-regression`/`ml-matrix` train on these features. No model means browser mode plus detection recommendation 1. A narrow classifier score margin raises verification frequency. This is not semantic DOM control matching, session proof, or an application-state graph.

The crawler executes a restricted handler in HTTP or browser mode, stages its storage writes, falls back to a browser if HTTP fails/checks fail, and optionally runs a second result-comparison detection. Default comparison checks dataset item equality; a custom comparator can return inconclusive. A predictor can be injected, and only owned predictors are initialized/torn down by the crawler. Dependencies include Cheerio, Playwright, Crawlee pipelines/storage, Zod, logistic regression/matrix/string-comparison packages.

**IGNORE** its rendering/session execution for X1. Ascend's multiple states at `/loads` are exactly the case where URL similarity provides no selected-section proof. **REFERENCE** explicit inconclusive results and owned-versus-injected lifecycle contracts. Repeated handler execution and extra HTTP requests must not become FreightDesk automatic recovery actions.

### Persistence and proposal transactions

[`RecoverableState`](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/packages/core/src/recoverable_state.ts#L130) separates initialization, first record restore, active periodic persistence subscription, teardown, in-memory reset, and persisted-record reset. It accepts serialization/deserialization functions or Standard Schema validation. Reinitialization after teardown reopens persistence without reloading over surviving in-memory state. Clearing storage while a periodic writer is active is rejected. Storage operations have their own deadline. Periodic/teardown persistence errors warn rather than throw, while direct persistence can reject.

**ADAPT** lifecycle invariants and validate-on-restore for a V2 contract/graph repository. Keep RuntimePaths, SQLite atomic writes, sanitized errors and FreightDesk cleanup/authority receipts. A warning-only teardown is insufficient if an authority revocation receipt must be durable. This source is more general and explicit about resource lifecycle, but does not replace the current signed worker/document handshake.

[`StorageTransaction`](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/packages/core/src/storages/transaction.ts#L166) uses an ordered journal, state `open → committing → committed/failed` or `rolledBack`, async-local transaction context, per-storage write policy, and explicit disposal. Per-attempt adaptive extraction commits only the accepted handler result; the losing detection transaction is discarded. Commit groups key-value/request-queue changes before dataset changes. The implementation explicitly has at-least-once delivery; partial commit may already have applied writes, and operations after closing a transaction can pass through to the backend. It is not a universal atomic rollback boundary.

**REIMPLEMENT** a smaller `ObservationTransaction`: stage graph/schema candidates, compare validation results, atomically append one accepted local proposal with its proof receipt, then close. FreightDesk already does strict local validation and append-only maps in [`mapping_store.py:persist_map`](../../executors/ascend_extension/mapping_store.py); do not replace it with external dataset writes. Reuse tests about discarded candidate output and cleanup, not the crawler retry semantics. Both Crawlee modules are `SAFE_TO_ADAPT_WITH_NOTICE` as original Apache-licensed source, but there is no reason to bring in Crawlee storage dependencies for this small role.

### Semantic references and composed DOM

[`extract-microdata.ts`](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/packages/utils/src/internals/extract-microdata.ts#L36) implements nested item ownership, `itemprop` multi-token grouping, `itemref` lookup through a lazy ID index, repeated properties as arrays, and ancestor-set cycle protection. Traversal stops at a nested `itemscope` so its descendants belong to that child. This is a useful reference-graph pattern. It assumes schema.org microdata and extracts content/URLs, not general form labels. **ADAPT** ownership/reference/cycle mechanics over X1 graph node handles, with duplicate-ID ambiguity recorded instead of silently using the first ID match for an identity decision. `SAFE_TO_ADAPT_WITH_NOTICE`.

[`expandShadowRoots`](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/packages/utils/src/internals/general.ts#L41) recursively scans shadow hosts and appends serialized shadow content to `el.innerHTML`. **It mutates the live page.** [`parseWithCheerio`](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/packages/playwright-crawler/src/internals/utils/playwright-utils.ts#L580) uses it by default, serializes page HTML, and replaces iframe nodes in the parsed HTML with iframe contents by index. It warns on live/snapshot iframe count mismatch. This loses root/document boundaries and is sensitive to changes between snapshots. **IGNORE these implementations for the live sensor.** Reimplement a read-only composed graph with explicit shadow-host/slot/frame edges and same-origin/document proof, borrowing stronger primitives from the Playwright/accessibility study.

[`ErrorSnapshotter.captureSnapshot`](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/packages/basic-crawler/src/internals/crawlers/error_snapshotter.ts#L36) stores screenshots/HTML and may create public storage URLs. **IGNORE** for FreightDesk diagnostics. The existing bounded, fixed-vocabulary stage/bound receipts are the correct privacy model. [`Session`](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/packages/basic-crawler/src/internals/session_pool/session.ts) uses expiry, usage limits, error score and terminal retirement, but also stores cookies/fingerprints and drives session pools. **REFERENCE** terminal retirement as a recovery invariant; do not import authentication/session storage or rotation.

## Crawl4AI: separate schema execution from schema inference

### Deterministic extraction DSL

[`JsonElementExtractionStrategy`](https://github.com/unclecode/crawl4ai/blob/862f6bccb9c063f49b9d42701baa0eea17a4993f/crawl4ai/extraction_strategy.py#L1043) parses HTML, finds `baseSelector`, applies base fields and relative child fields, and recurses through `nested`, `list`, and `nested_list` schemas. Scalar steps extract text, attributes, HTML or regex groups; transforms include case conversion/strip. CSS/BeautifulSoup, optimized lxml/CSS, and XPath subclasses supply selection primitives. Source-relative lookup can reach parent/previous/next siblings. Scalar selection uses the first match; missing/error cases can return a configured default. Computed string expressions are explicitly disabled in this revision; user-supplied Python callables remain possible. This is a declarative extraction executor, not automatic deterministic field-label discovery.

**REIMPLEMENT** the typed nested-schema idea behind X1. Use graph node references and approved locator alternatives, require explicit cardinality, and represent `ABSENT`, `UNVERIFIED`, `AMBIGUOUS`, `BOUND_EXCEEDED` separately. Do not copy first-match/default swallowing, raw HTML output, arbitrary function hooks or selector execution into Mapping Mode. FreightDesk [`workspace.js:fields`](../../extensions/ascend-x1/workspace.js) already associates native labels, ARIA labels/labelledby, approved provider attributes and a conservative neighbor fallback; that actual association logic is stronger for metadata capture than “HTML + existing selector → value.” Generalize it into Field/Form ownership rather than replace it with this DSL.

### Bounded generated-schema feedback: useful loop, unsuitable acceptance rule

Sources: [`_validate_schema`](https://github.com/unclecode/crawl4ai/blob/862f6bccb9c063f49b9d42701baa0eea17a4993f/crawl4ai/extraction_strategy.py#L1366), [`agenerate_schema`](https://github.com/unclecode/crawl4ai/blob/862f6bccb9c063f49b9d42701baa0eea17a4993f/crawl4ai/extraction_strategy.py#L1764).

The generator preprocesses HTML, calls an LLM for a CSS/XPath schema, parses JSON, runs it against original HTML, and returns structured feedback for up to `1 + max_refinements` attempts (default four). It detects repeated schemas and can require expected field names. This is stronger than trusting syntactically valid JSON alone.

However, validation collects sample raw HTML (up to 2,000 characters) and sample field values (up to 120 characters). Fuzzy success requires only one populated field; expected-field mode requires expected fields to be populated, not proof they are semantically correct. Across multiple HTML samples, **success on at least one sample** is enough. The final failed refinement still returns the best-effort schema without turning it into a typed unverified result. URL input can launch its own AsyncWebCrawler. The source signature defaults `validate=True`, while part of its docstring still describes a false default; trust the implementation, not prose.

**REIMPLEMENT** only proposal → bounded execution against sanitized frozen graph → precise validation feedback → revised proposal. Unknown interface interpretation may use a model, but generated selectors cannot execute in the authenticated page. Resolve proposed graph relationships through deterministic known primitives; independent load identity, read-only classification, section/cardinality constraints and every required cohort fixture must pass. After exhausted refinements return `UNVERIFIED`, never activate a best-effort contract. No raw examples leave X1 in Mapping Mode.

### Content pruning is aimed at documents, not application controls

[`PruningContentFilter`](https://github.com/unclecode/crawl4ai/blob/862f6bccb9c063f49b9d42701baa0eea17a4993f/crawl4ai/content_filter_strategy.py#L541) parses HTML with BeautifulSoup/lxml and recursively scores nodes. Its weighted composite combines text/markup density (0.4), inverse link density (0.2), tag weight (0.2), class/ID weight (0.1), and log text length (0.1). Dynamic thresholds lower removal pressure for semantically important/text-heavy nodes and raise it for link-heavy nodes. Low-score ancestors are decomposed before recursion; whitelisted nodes bypass pruning. The base excluded tag set includes `form`, `nav`, `iframe`, header/footer and aside. The class/ID contribution clamps negative scores to zero in the composite; this is not a trained relevance probability.

**REFERENCE**, not an app DocumentGraph implementation. Preserve ownership anchors, labels, controls, target relationships, identity and safe hidden referenced regions before any reduction. Compute compact metadata/features without reading values or destroying the provider DOM. A low-text toolbar, form, or accordion can be operationally important despite looking like boilerplate. The method lacks browser geometry, computed visibility, shadow/frame identity and interaction-state evidence.

[`flatten_shadow_dom.js`](https://github.com/unclecode/crawl4ai/blob/862f6bccb9c063f49b9d42701baa0eea17a4993f/crawl4ai/js_snippet/flatten_shadow_dom.js) is more appropriate conceptually than Crawlee's mutating expander: it recursively serializes open shadow roots and resolves slots with `assignedNodes({flatten:true})`, falling back to slot children. Nevertheless it returns raw text/attributes as HTML, loses graph ownership, has no bounds, cannot read closed roots, and text nodes are emitted without HTML escaping. **REIMPLEMENT** only read-only composed traversal, produce typed bounded nodes rather than HTML strings, and preserve unavailable-root evidence. Do not copy this serializer into X1.

### Table claims checked against code

[`DefaultTableExtraction`](https://github.com/unclecode/crawl4ai/blob/862f6bccb9c063f49b9d42701baa0eea17a4993f/crawl4ai/table_extraction.py#L65) ranks actual HTML `<table>` elements using thead/tbody/th, column-count variance, caption/summary, data attribute count, size and text density. Nested tables and presentation/none roles reduce the score. These are reasonable **weak candidate-ranking features** for SchemaGraph; most require only counts/tags, but its text-density path reads all cell text.

Its default extraction is not a robust merged-cell algorithm despite the class description. `extract_table_data` reads only the first thead row, duplicates text according to colspan, extracts td rows, and aligns by truncating/padding to header width. It does not create a rowspan occupancy matrix or preserve all multi-row headers. Descendant XPath can mix nested-table rows/cells. Missing headers can be invented as `Column N`; malformed spans can cause an exception, which the caller logs and skips. It does not handle ARIA grids, virtualized row windows, sticky clones, hidden-column alignment, or pagination proof. `LLMTableExtraction` asks a model to interpret difficult tables, which cannot become deterministic operational evidence.

**REFERENCE** the table/layout candidate features; **IGNORE** default cell alignment and LLM table execution. FreightDesk [`reader.js:grid`](../../extensions/ascend-x1/reader.js) already independently proves Active Loads, rejects header-only competition, uses semantic Load ID/Pick Date/Drop Date mapping, validates the observed header contract and reports bounds/predicates. Preserve these protections. V2 should separately normalize a physical-cell occupancy grid with source-node evidence, expose multi-level column paths, and distinguish rendered rows from unknown total coverage. Do not replace fail-closed mismatch with padding/truncation.

## Current FreightDesk: keep, refactor and replace

Source inspected: [`webbridge.js`](../../extensions/ascend-x1/webbridge.js), [`workspace.js`](../../extensions/ascend-x1/workspace.js), [`reader.js`](../../extensions/ascend-x1/reader.js), [`mapping_store.py`](../../executors/ascend_extension/mapping_store.py), and [`mapping_orchestrator.py`](../../executors/ascend_extension/mapping_orchestrator.py).

| Current component | Decision from this study | V2 target |
|---|---|---|
| BrowserSensor | KEEP boundary; REFACTOR implementation | X1 emits bounded, sanitization-tagged node/relationship facts from its verified document. No external browser runner. |
| DOMSnapshot | REPLACE limited representation | DocumentGraph with per-document node handles, explicit frame/shadow roots, visibility/selection facts and bounded feature signatures. Existing snapshot is an ephemeral Map of selected semantic containers, not a general normalized DOM. |
| DOMDiff | REFACTOR | StateDiff matching stable nodes where possible; explicit added/removed/visibility/selected/identity changes, causally linked to an authorized action or owner transition. Current graph compares element-object presence and visible/selected state, not semantic tree edit distance. |
| LocatorGraph | REFACTOR/MERGE | Separate ownership/reference graph from field inference and candidate locators. Preserve direct-reference → newly-created → newly-visible → connected-selection evidence and ambiguity stops. |
| AdaptiveLocator | REPLACE internals | Feature ranker/history plus hard constraints; candidate-only relocation. No numeric score may prove tenant, load identity, authorization or write safety. |
| ProviderContract | KEEP/REFACTOR | Versioned semantic vocabulary and reviewed rules over generic graphs; append-only source provenance, coverage and identity strategy remain. |
| EvidenceScorer | REFACTOR | Return evidence vector, contradictions and candidate separation. Ordinal A/B/C/D strength and PROPOSED/UNKNOWN are not probabilities. |

Important privacy distinction: legacy `webbridge.js:graph` computes `value_present` by reading `e.value` or `textContent` for recognized fields, while its output says `values_included=false`. That means “values not exported,” not “values never read.” The currently used `workspace.js:capture/fields` path is metadata-only and was the path validated for exact 1763/Load Basics. Do not collapse these into one privacy claim. V2 needs an explicit data-class policy distinguishing never-read, ephemeral-value-access, exported metadata and separately authorized operational extraction. This research has not changed either path.

## Recommended harvest sequence for these sources

1. Write graph contracts and hard evidence constraints first. Keep authenticated document/identity/presence authority in X1; upstream parsers only inform pure algorithms.
2. Build read-only composed-tree and ownership/reference normalization. Use explicit root boundaries and semantic control edges; do not flatten into HTML or prune forms/navigation.
3. Generalize field/form and physical table schemas over the graph. Retain provenance for every field association and every occupied table coordinate. Treat optional fields separately from navigation/identity drift.
4. Add a Scrapling-inspired bounded locator signature/ranker, historical validated signatures and negative fixtures. Never auto-save the first fuzzy result as verified history.
5. Add staged observation transactions and explicit recovery lifecycle inspired by Crawlee. Atomic local proposal persistence and closure must remain separate from provider actions.
6. Only then introduce the Crawl4AI-inspired bounded schema proposal/validation feedback loop on sanitized frozen graphs. Cross-fixture generalization, cardinality, ambiguous controls and privacy checks are mandatory; failures remain unknown.

Necessary tests include duplicate IDs, duplicate logical controls in different workspaces, changed wrapper depth, attribute ordering, lost labels, missing originals, wrong-selector-still-matches, tied fuzzy scores, hidden referenced targets, shadow slots and unavailable closed roots, iframe document replacement, multiple form branches, multi-row/rowspan/colspan headers, sticky clones, virtualization gaps, discarded extraction attempts, failed local commit, owner revoke during recovery, and zero raw-value access/export. No live provider assumptions should enter these fixtures.

## Provenance entries to prepare if implementation is authorized

These are recommendations, not claims that upstream code has been incorporated:

```yaml
components:
  - component: locator_signature_ranker
    source_project: Scrapling
    repository: https://github.com/D4Vinci/Scrapling
    source_file: scrapling/parser.py
    source_symbols: [Selector.relocate, Selector.__calculate_similarity_score]
    source_commit: 48da61d1ee85cea7bbbdff013d98c90602e1d93f
    license: BSD-3-Clause
    decision: ADAPT
    license_classification: SAFE_TO_ADAPT_WITH_NOTICE
    incorporation_status: PROPOSED_ONLY
    adaptation_notes: Bounded sanitized features; hard identity gates; ambiguity margin; append-only approved history.
    freightdesk_module: proposed/webbridge/locator_engine
  - component: observation_transaction_lifecycle
    source_project: Crawlee
    repository: https://github.com/apify/crawlee
    source_file: packages/core/src/storages/transaction.ts
    source_symbols: [StorageTransaction]
    source_commit: 0b2ac45323d7be8d9d3d146d4873cec1cafdc095
    license: Apache-2.0
    decision: REIMPLEMENT
    license_classification: SAFE_TO_ADAPT_WITH_NOTICE
    incorporation_status: PROPOSED_ONLY
    adaptation_notes: Conceptual staged evidence journal; native SQLite atomic persistence; no backend pass-through or provider retry.
    freightdesk_module: proposed/webbridge/evidence_store
  - component: schema_proposal_feedback
    source_project: Crawl4AI
    repository: https://github.com/unclecode/crawl4ai
    source_file: crawl4ai/extraction_strategy.py
    source_symbols: [JsonElementExtractionStrategy.agenerate_schema, JsonElementExtractionStrategy._validate_schema]
    source_commit: 862f6bccb9c063f49b9d42701baa0eea17a4993f
    license: Apache-2.0-text-plus-additional-attribution-requirement
    decision: REIMPLEMENT
    license_classification: PREFER_CLEAN_REIMPLEMENTATION
    incorporation_status: PROPOSED_ONLY
    adaptation_notes: Original typed graph proposal/validate loop; no upstream code, raw examples, runner, arbitrary selectors or best-effort activation.
    freightdesk_module: proposed/webbridge/schema_proposal
```

An implementation review must record which original functions or excerpts were actually adapted, their preserved licenses/notices, changed-file notices, dependency licenses, tests and patch revision. A research link is not a substitute for that incorporation audit. Neither legal clearance nor vendor validation is implied by this document.
