# WebBridge V2 source study: Stagehand and Browser Use

Research date: 2026-09-12. This is a source/design assessment, not an implementation or live-provider validation. No third-party package was installed, no project demo or test was run, no browser was launched, and no operational runtime state was changed. Only shallow official source snapshots were downloaded to the authorized research directory. All descriptions below are original analysis rather than copied implementation text.

## Revision and license ledger

| Project | Exact examined revision | Revision date and source version | Local source snapshot | Source license |
|---|---|---|---|---|
| Stagehand | `b771930d2b4d858e5bd9670203c66260b385a8fa` | 2026-09-11; workspace 4.0.0; private extension package 1.0.2 | `C:\FreightDeskRuntime\Data\Research\WebBridgeV2\stagehand` | [MIT, Browserbase Inc.](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/LICENSE#L1) |
| Browser Use | `50f205533fe10ba35b553d2a3689c77b87bd5d0a` | 2026-09-09; Python project 0.13.10 | `C:\FreightDeskRuntime\Data\Research\WebBridgeV2\browser-use` | [MIT, Gregor Zunic](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/LICENSE#L1) |

Both snapshots use depth-one, blob-filtered sparse clones. The Stagehand checkout materializes its extension and TypeScript SDK implementation; Browser Use materializes `browser_use`. Full Git tree inventories were searched for LICENSE, NOTICE and COPYING: only the root LICENSE was present in each examined revision. This is not a dependency license audit. No source was copied into FreightDesk production modules.

The MIT licenses permit commercial use, modification and distribution subject to preserving the copyright and permission notice with copies or substantial portions. Source-level classifications below assume those notices will be retained. Dependencies, generated assets, hosted service terms, trademarks and any separately attributed upstream material still require a component-specific check before actual incorporation. In particular, do not treat a root MIT file as a blanket approval for every package transitively installed by an SDK.

The practical default is **ADAPT / SAFE_TO_ADAPT_WITH_NOTICE** for small isolated implementation modules, or **REIMPLEMENT / PREFER_CLEAN_REIMPLEMENTATION** where importing the implementation would pull in a browser-control stack or incompatible data handling. Those are engineering reuse classifications, not a legal opinion about the completed commercial product.

## Findings that change the architecture decision

1. **Document indexing is worth borrowing; these agent runtimes are not replacements for X1.** Both projects build richer reusable DOM representations than FreightDesk's current repeated selectors. Stagehand now implements much of its runtime in an extension, but its [manifest](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/manifest.json#L1) requests debugger/offscreen/tabs access and all-URL, all-frame content access. FreightDesk's existing exact-origin, isolated top-frame sensor and host authority remain the boundary. Studying Stagehand's extension does not authorize adopting those permissions.
2. **Neither reviewed implementation supplies a verified freight workspace or section graph.** Their useful primitive is a document/interaction graph. The reviewed snapshot and serializer modules do not establish LOAD/N identity, a verified tab-to-section contract, or a read/write classification from provider evidence. Those responsibilities remain FreightDesk-native.
3. **Self-healing is not identity verification.** Stagehand re-infers a selector after failure; Browser Use tries progressively weaker element matches. Both can help generate candidates. Their automatic target choice cannot directly replace X1's uniqueness, workspace and action-policy gates.
4. **DOM/AX collection is not metadata-only by default.** Browser Use explicitly restores live field values into its node model. Stagehand's AX structures carry names, descriptions, values and URLs, and its cache client can transmit raw AX nodes. FreightDesk must strip disallowed values before creating a graph, logging, serializing or asking a model.
5. **The most useful differentiation is three-layer evidence:** document identity and lifecycle; structural identity and relationships; semantic interpretation. These projects often combine those concerns to get an action done. FreightDesk should retain them separately so an adaptive match cannot silently become provider truth.

## Stagehand: exact implementation findings

### S1. Hybrid DOM/accessibility representation and frame indexing

**Sources:** [`captureHybridSnapshot`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/a11y/snapshot/capture.ts#L59), [`buildSessionDomIndex`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/a11y/snapshot/domTree.ts#L233), and [`HybridSnapshot` / `SessionDomIndex`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/types/private/snapshot.ts#L31).

The capture pipeline snapshots frame topology first, obtains a DOM index once per unique CDP session, slices that index into per-frame maps, obtains AX outlines, computes iframe-host path prefixes and combines the results. A scoped-locator fast path can avoid building all frame outputs. The node index stores backend ID to absolute XPath, tag, scrollability, document-root membership and DFS entry/exit positions. The resulting hybrid structure keeps an AX text outline plus maps from frame-encoded backend IDs to paths and URLs; it does not discard the DOM-to-AX join after textual serialization.

The important reusable design is **one immutable snapshot index, multiple derived views**. FreightDesk currently builds separate sets/maps in `workspace.js`, `webbridge.js` and board-reading code. A DocumentGraph can compute containment, labels and target edges once within the verified workspace, retaining node references privately and exposing only sanitized handles. Session/frame/node IDs must be namespaced; backend IDs are not cross-document business identifiers.

Dependencies are TypeScript, Chrome CDP, `devtools-protocol` types and Stagehand's Page/Frame/CDP abstractions. Directly importing the collector would introduce a different sensor interface and broader permissions. Its iterative index/data model is a better fit for **REIMPLEMENT / PREFER_CLEAN_REIMPLEMENTATION** behind X1's existing DOM sensor. Pure indexing helpers are possible **ADAPT / SAFE_TO_ADAPT_WITH_NOTICE** candidates after attribution review.

Limitations: the normal pipeline collects broad document trees; mutation can occur between DOM and AX responses; accessibility may omit or flatten application structure. A snapshot should therefore carry document generation, capture interval, scope and missing-channel flags. The upstream combined outline does not itself prove a provider account, exact entity or complete board coverage.

### S2. Subtree exclusion through DFS intervals

**Sources:** [`buildFrameExclusionIntervals`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/a11y/snapshot/capture.ts#L534) and [`makeIsIgnoredBackendNode`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/a11y/snapshot/capture.ts#L644).

The implementation records each node's DFS entry/exit interval. Ignoring a node excludes its full interval, and excluding an iframe host recursively excludes the corresponding child-frame subtree. Overlapping intervals are merged after sorting; membership uses binary search instead of repeated ancestor walks. This is a concrete, reusable algorithm, not an LLM feature.

FreightDesk should **ADAPT / SAFE_TO_ADAPT_WITH_NOTICE** the interval/index idea for repeated containment checks, authorized region membership and metadata exclusions. An index makes both explicit exclusion and positive allowed-subtree checks cheap. Important modification: build the allowed workspace snapshot first, rather than collect a broad page and rely only on later redaction. Invalid or missing scope membership must be UNKNOWN/denied rather than treated as outside an exclusion list and therefore allowed. Rebuild intervals after generation or structural revision changes.

### S3. AX pruning and semantic role enrichment

**Sources:** [`a11yForFrame`, `decorateRoles`, `buildHierarchicalTree`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/a11y/snapshot/a11yTree.ts#L15) and [`treeFormatUtils`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/a11y/snapshot/treeFormatUtils.ts#L8).

AX nodes are indexed and joined by parent/child IDs. Empty structural leaves are pruned; unhelpful structural wrappers with one useful child collapse; redundant static text is removed. DOM tag information corrects cases such as a file input exposed as a generic button and a native select exposed as combobox. Selected/checked state remains explicit. That combination offers a substantially better *interpretation view* than FreightDesk's small tag/role selector vocabulary.

FreightDesk should maintain the original structural graph alongside any pruned AX projection. Collapsing a wrapper is acceptable for a model prompt but can destroy the evidence needed to associate a heading with a later form sibling, exactly the layout encountered in Ascend. Store a `collapsed_from` relationship or let pruning operate on a separate view. Keep accessible names only when they are approved schema labels; arbitrary names/descriptions/values may contain customer data. **ADAPT / SAFE_TO_ADAPT_WITH_NOTICE** for the pruning/enrichment concepts, not the value-bearing formatter wholesale.

**Scope trap:** in `a11yForFrame` lines 42–79, a locator that cannot resolve to a backend AX node, or a caught scoping error, can return the unscoped node set. A failed frame-scoped AX call can also retry without the frame parameter. `scopeApplied` is reported, but a caller must enforce it. FreightDesk must never broaden its read scope this way: unresolved requested root is an explicit stop. This is a key difference between a useful general browser tool and an authorized sensor.

### S4. Bounded recovery from deep CDP trees

**Source:** [`getDomTreeWithFallback`, `hydrateDomTree`, `shouldExpandNode`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/a11y/snapshot/domTree.ts#L6).

On a specific CDP CBOR stack-limit failure, Stagehand retries DOM retrieval with progressively shallower depths. It identifies truncated branches by comparing declared child count with materialized children, hydrates only those branches via `DOM.describeNode`, and uses visited ID sets to avoid repeated expansion. Nonmatching error types propagate. This distinguishes **representation truncation** from a genuinely empty DOM.

This is **REFERENCE ONLY** for X1 today because X1 does not use CDP snapshots. The transferable idea is explicit completeness flags and targeted expansion, with category and elapsed-time budgets. Do not port the initial unbounded full-depth request or use hydration to defeat FreightDesk's capture limits. A future separately approved CDP sensor would need a total node/request budget in addition to depth attempts.

### S5. Selector discovery, resolution and cache

**Sources:** [`observe`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/services/observeService.ts#L76), [`FrameSelectorResolver`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/selectorResolver.ts#L20), [`buildChildXPathSegments`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/a11y/snapshot/xpathUtils.ts#L86), [`withCache`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/services/cacheService.ts#L200), and [`CacheClient`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/clients/cacheClient.ts#L4).

`observe` supplies the AX outline to inference, receives element IDs, resolves those IDs through the snapshot's XPath map, and returns action objects. This grounds model references in captured nodes, but action selection is still model interpretation. The resolver parses CSS/text/XPath and resolves an indexed match within a frame. XPath generation records same-tag sibling positions and shadow/frame hops. It is not a learned stable-selector ranker. The text resolver performs broad text matching and chooses innermost matches; it is not safe as a unique identity primitive.

The cache wrapper collects raw AX trees and URL, asks a cache client for a result, and on a miss or replay failure executes the inference path. It records hit count, age and miss reason. **The actual cache key/tree-matching implementation is not in the examined repository:** the client references a separate server module. Do not claim to have harvested an open-source structural similarity algorithm from this client. Its threshold is an observation/hit-count threshold in the wire contract, not a calibrated identity confidence score.

FreightDesk should **REIMPLEMENT** a local, metadata-only, document-and-provider-contract-scoped cache. A hit proposes a locator whose uniqueness, role/label, entity scope and current target relationship are rechecked. Do not copy the external cache transport, raw AX payload, arbitrary selector input or automatic action replay. The element-handle-to-generated-locator pattern is useful; upstream model output never becomes an unrestricted selector in X1.

### S6. Diffing and self-healing

**Sources:** [`diffCombinedTrees`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/a11y/snapshot/treeFormatUtils.ts#L76), [`runActPipeline`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/services/actService.ts#L140), and [`takeDeterministicAction` / `selfHealAction`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/services/actService.ts#L304).

The diff is set subtraction of trimmed outline lines: retain lines newly present in the later snapshot and normalize indentation. A two-step action can feed those new lines, or the entire next tree if the diff is empty, into a second inference. This is useful prompt compression, but it does not report removals, reparenting, visibility transitions, multiplicity changes or an action-to-region causal edge. FreightDesk's existing causal container graph is stronger for its specific question and should not be replaced with this string diff.

With self-heal enabled, an execution failure causes a fresh unscoped snapshot and model inference based on the prior action description; the selected replacement is executed with the original method and arguments. Cached sequences likewise fall back to fresh inference when replay fails. This is **REFERENCE ONLY** for agent fallback and **DO_NOT_USE** as X1's automatic execution recovery. A failure after an uncertain side effect cannot authorize a retry. A new selector also cannot inherit exact LOAD/N or read-only control proof from the old selector.

### S7. Execution-world lifecycle and module capability checks

**Source:** [`ExecutionContextRegistry`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/understudy/executionContextRegistry.ts#L23).

The registry has forward/reverse maps keyed by CDP session and frame for main, extension and fallback execution contexts. It listens for context creation/destruction/clearing, removes reverse bindings when contexts disappear and probes candidate worlds for a fixed package/version/capability marker. Pending fallback creation is coalesced per frame. The registry distinguishes an extension world with closed-shadow capability from a fallback world without it.

This supports **ADAPT / SAFE_TO_ADAPT_WITH_NOTICE** at the lifecycle-state-machine level. FreightDesk already has a private READY handshake, document generation, actual mapper revision and stale-content reinjection. Keep those gates; factor their state into an explicit DocumentRegistry with single-flight recovery and capability receipts. Do not import Stagehand's CDP fallback worlds, arbitrary source evaluation or all-frame access. The fixed health-check concept is especially relevant to the stale same-build mapper problem we just solved; source version alone is insufficient proof of the installed executing module.

### S8. Structured extraction

**Source:** [`extract`](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/packages/extension/services/extractService.ts#L88).

The service converts caller JSON Schema to Zod, wraps nonobject schemas, substitutes DOM element IDs for URL-valued fields before model extraction, then reinserts actual URLs from the captured map. Screenshot extraction explicitly bypasses the DOM-only cache. The ID substitution is a useful anti-hallucination pattern for values that must come from a captured reference map.

This is still **snapshot/optional image + LLM → structured output**, not deterministic field-schema discovery. Valid JSON or a `completed` inference flag does not prove each field's provider origin. FreightDesk should **ADAPT** the handle substitution idea for proposed mappings: the model returns approved node IDs, relation IDs and canonical-label candidates, then deterministic code validates all references. Never expose signed URLs or arbitrary field values to the model during mapping. Do not adopt the extraction service as the canonical fact verifier.

## Browser Use: exact implementation findings

### B1. Fused document graph with geometry and accessibility

**Sources:** [`DomService._get_all_trees`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/service.py#L403), [`_construct_enhanced_node`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/service.py#L759), and [`EnhancedDOMTreeNode`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/views.py#L379).

The collector obtains DOM, AX, DOMSnapshot layout/paint data and device-pixel ratio concurrently, then joins them by backend node ID. Enhanced nodes retain parent/child/shadow/frame links, attributes, AX role/name/properties, layout rectangles, visibility, scrollability, session/target IDs and listener flags. Iframe offsets and scroll corrections are accumulated when constructing absolute positions. This is the strongest broad **data-model** example among these two projects.

The pending CDP tasks have a 10-second first wait and 2-second retry wait. AX failure may degrade to an empty AX channel, while required DOM/layout failures stop. That is a useful distinction: missing optional evidence need not discard a usable graph, but it must lower capability/coverage. The collection is not atomic; arbitrary SPAs can mutate between channels. FreightDesk should add a generation/revision bracket and reject mixed-document joins.

**REIMPLEMENT / PREFER_CLEAN_REIMPLEMENTATION** as a compact, value-free graph behind X1. CDP, `cdp-use`, the BrowserSession and event bus are not necessary dependencies for the graph concept. The inspected Python package has numerous SDK/cloud/file/telemetry dependencies in [pyproject.toml](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/pyproject.toml#L15), making wholesale adoption disproportionate. Current X1 cannot obtain full CDP AX/paint data with its existing permissions; represent those channels as unavailable rather than broadening access during this design task.

### B2. Linear snapshot lookup and privacy limitation

**Source:** [`build_snapshot_lookup`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/enhanced_snapshot.py#L70).

The code converts flattened CDP arrays into backend-ID maps, preindexes the layout rows, converts rare-boolean index arrays to sets and looks up per-node computed styles/geometry directly. This avoids repeatedly searching array indices for every DOM node. **ADAPT / SAFE_TO_ADAPT_WITH_NOTICE** for the indexing implementation or independently reimplement it in the sensor's language. Do not copy the reported performance numbers from code comments as benchmark results for FreightDesk; none were reproduced here.

The same function intentionally reads live input/text values from the CDP snapshot, excluding selected sensitive input/autocomplete categories. [`_construct_enhanced_node` lines 814–826](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/service.py#L814) writes those values into the enhanced attribute map. Password/payment filtering does not make ordinary driver/customer/contact fields safe for FreightDesk mapping. Strip **all operational values** at collection, not only known secret classes.

### B3. Interactive-control discovery

**Source:** [`ClickableElementDetector.is_interactive`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/serializer/clickable_elements.py#L4).

The detector combines semantic tags, ARIA/AX roles and state properties, event-handler/listener presence, tabindex and component wrappers. Labels with `for` are treated differently from labels/spans wrapping a form control; descendant inspection is limited to two levels. It recognizes more controls than X1's current anchor/button/tab set and can supply ControlGraph **candidate reasons**.

However, it also accepts broad search-related class/ID/data substrings, some row/cell roles and eventability before later disabled/hidden checks. The result is a heuristic boolean, not a calibrated score despite the docstring wording. Search-class text can match unrelated components. A clickable element may be a destructive action; hidden or disabled state must be assessed separately and conservatively. **ADAPT** the semantic candidate rules and wrapper handling, but **REIMPLEMENT** the result as a reasoned classification with three states: candidate, noncandidate, unknown. Do not adopt it as a READ_ONLY_NAVIGATION classifier.

[`_get_all_trees` lines 456–566](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/service.py#L456) optionally discovers JavaScript listeners through DevTools command-line APIs, bounds total DOM size/listener count and limits resolution concurrency. This is not available to ordinary X1 content JavaScript and still begins with a page-wide element query. **REFERENCE ONLY**; do not add debugger permissions or inspect listener script bodies.

### B4. Pruned model representation and session-scoped indexing

**Sources:** [`DOMTreeSerializer.serialize_accessible_elements`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/serializer/serializer.py#L114), [`_create_simplified_tree`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/serializer/serializer.py#L455), and [`_allocate_selector_index` / `_assign_interactive_indices_and_mark_new_nodes`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/serializer/serializer.py#L637).

The serializer builds a simplified tree, applies paint-order filtering, optimizes structure, applies bounding-box filtering, then indexes interactive nodes. It retains shadow fragments and iframe content. A cache key includes CDP session plus node ID; previous interactive-node identity uses session plus backend ID. Model indices prefer backend IDs, allocating collision-free synthetic indices when different frames reuse the same number. This is a concrete warning against a global integer node ID namespace.

FreightDesk should **ADAPT** separate original/pruned graphs and collision-safe handle allocation, using `document_generation + frame + local_node_id`. Newness is useful evidence for StateDiff but not causality: a background refresh can create a node without the owner action. Replacement documents must start a new identity epoch even if a browser target/session survives.

Do not copy visibility overrides: the serializer can retain hidden file inputs and treat validation-related attributes as visibility hints. Preserve those as separately flagged structural metadata if ever needed; they cannot become current-visible evidence. The model-facing exclusion attributes are also not FreightDesk authorization rules.

### B5. Paint order and occlusion

**Sources:** [`RectUnionPure`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/serializer/paint_order.py#L35) and [`PaintOrderRemover.calculate_paint_order`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/serializer/paint_order.py#L146).

Nodes are grouped by paint order and processed front-to-back. A rectangle union tracks covered area per session/frame document; fully covered lower nodes are marked ignored. Transparent or low-opacity covering rectangles are not added to the occlusion union. This is better than treating `getClientRects().length > 0` as sufficient visibility and can help reject background workspaces behind dialogs.

The implementation uses an opacity threshold and rectangles, so clipped/rounded/transformed/partially transparent geometry can be imperfect. Treat occlusion as an evidence channel, not sole proof. **ADAPT / SAFE_TO_ADAPT_WITH_NOTICE** the small rectangle-union routine if a future authorized sensor supplies geometry. Do not import CDP solely to obtain it; current X1 can start with bounded DOM geometry and explicit modal/hidden/aria state, marking absent paint evidence UNKNOWN.

### B6. Compound fields and select-option structure

**Sources:** [`_add_compound_components`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/serializer/serializer.py#L167) and [`_extract_select_options`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/serializer/serializer.py#L352).

The serializer describes native compound widgets, preserves numeric bounds, recursively groups options/optgroups and exposes option count and a short representation. Some format hints are inferred from a handful of option strings. The useful idea is distinguishing a logical field from its rendered subcontrols. This avoids mapping a numeric field's increment/decrement buttons as unrelated business fields.

FreightDesk should **REIMPLEMENT** a metadata-only Field/Form model with native type, required/readonly/disabled state, label edges and group membership. Do not import option values, selected values or inferred financial/date semantics. A field's `type=date` does not establish timezone or appointment meaning. These functions do not solve general field-label association or section identity; current FreightDesk's explicit label/control/ARIA relationships should remain.

### B7. Historical locator matching and selector generation

**Sources:** [`EnhancedDOMTreeNode.compute_stable_hash`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/views.py#L834), [`filter_dynamic_classes`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/views.py#L138), [`Agent._update_action_indices`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/agent/service.py#L3529), and [`generate_css_selector_for_element`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/utils.py#L8).

The replay ladder tries exact structural/attribute hash, a hash with transient class names removed, XPath, accessible name plus tag, then identifying attributes. Stable hashes combine ancestor tag path, a static-attribute set and AX name, using truncated SHA-256. The CSS generator prefers ID, otherwise composes tag/classes and an attribute set; it may fall back to the tag alone. It does not validate uniqueness by querying the current DOM in this function.

The ladder is useful **REFERENCE / REIMPLEMENT** material for LocatorEngine, but it is not a safe drop-in repair algorithm. Source inspection shows that each replay level takes the first match; even the documented unique-attribute fallback does not count all candidates. The old frame is preferred rather than enforced. Equal-looking siblings and duplicate accessible names can therefore silently select a different control. Removing classes by substring can erase semantic identifiers containing words such as `active`; it must not erase state evidence needed to prove selected view/section.

FreightDesk's improved version should generate a candidate set for each strategy, enforce document/frame/workspace scope, retain all supporting and contradictory signals, require unique identity plus a sufficient score margin, and reverify the target control before any action. Separate **identity fingerprint**, **structure fingerprint**, and **current state**. Adaptive matches remain CANDIDATE_ONLY until their evidence meets the unchanged provider/action contract. Never treat hash equality as a security proof or persist private accessible names in fingerprints without a data policy.

### B8. DOM cache, target recovery and action-sequence invalidation

**Sources:** [`DOMWatchdog.on_BrowserStateRequestEvent`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/browser/watchdogs/dom_watchdog.py#L244), [`_build_dom_tree_without_highlights` / `clear_cache`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/browser/watchdogs/dom_watchdog.py#L551), [`SessionManager._handle_target_detached`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/browser/session_manager.py#L530), [`_recover_agent_focus`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/browser/session_manager.py#L636), and [`Agent.multi_act`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/agent/service.py#L2730).

The DOM watchdog coordinates snapshot tasks, stores a selector map and keeps the DOM service while clearing cached trees. SessionManager owns target/session forward and reverse maps, clears stale focus on detach and coalesces recovery with a lock/event. Multi-action execution stops its remaining queue after an action declared to terminate a sequence or after URL/focus-target change. These are useful coordination patterns and **ADAPT** candidates.

Do not adopt their recovery scope. `_recover_agent_focus` can switch to the most recent other page or create an emergency blank tab. A health watchdog can navigate browser new-tab pages. X1 must rebind only an owner-authorized eligible workspace and establish fresh proof. Also, URL/focus guards alone cannot detect an Ascend same-route section or load change. Keep FreightDesk's exact load, expected section, document-generation and pre/post capture checks. A cached selector map being present is not a freshness receipt.

### B9. Structured extraction, tables and agent fallback

**Sources:** [`extract` tool](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/tools/service.py#L1072), [`chunk_markdown_by_structure`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/markdown_extractor.py#L410), [`detect_pagination_buttons`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/dom/service.py#L1168), and [`Agent.step` / `_prepare_context`](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/browser_use/agent/service.py#L1035).

The extraction tool creates cleaned Markdown, splits by structural blocks, supplies one chunk and a query/schema to an LLM, and returns structured data with partial/source metadata. Invalid requested schemas can fall back to free text. The chunker groups code fences, lists, headings and tables; it prefers heading boundaries and carries table headers into continuation chunks. That chunking algorithm is an **ADAPT / SAFE_TO_ADAPT_WITH_NOTICE** candidate for future authorized document/model presentation. Its chunk size is soft for a single oversized block, so FreightDesk needs an independent hard payload bound.

This is not robust table-schema discovery. Pagination detection is multilingual text/ARIA/class pattern matching over clickable nodes; it does not prove total row coverage, handle Ascend sticky clones or map hidden columns. Keep the existing verified semantic board reader while designing a generic TableGraph. A retained table header in Markdown cannot validate a data grid.

The agent step obtains browser state, produces model actions, executes, postprocesses and finalizes; context gathering requests screenshots even when the model's vision setting is disabled. A judge result is advisory and does not replace the agent's self-reported success. This path is **REFERENCE ONLY**. FreightDesk's fallback must return bounded mapping proposals from approved metadata, with no direct browser executor access, screenshots, automatic page switching, schema-to-free-text relaxation or action retries.

## Comparison with current FreightDesk

This comparison uses the current local files, including mapper revision2. It does not claim new Ascend behavior from these source studies.

| Current component | Existing mechanism | External improvement worth taking | Recommended disposition |
|---|---|---|---|
| BrowserSensor | `webbridge.js` forwards discovery and workspace capture; X1 executes fixed commands under signed host authority | Separate sensor output from immutable indexed graph and projections | KEEP security boundary; REFACTOR sensor output |
| DOMSnapshot | `webbridge.js` indexes likely containers; `workspace.js` repeatedly queries a verified shell | Stagehand reusable per-document index; Browser Use fused node record with optional channels | REPLACE internals with bounded DocumentGraph; retain capture gates |
| DOMDiff | Same-document Element identity/visibility/selection changes; explicit causal ranking | Session-scoped node matching, separate identity/structure/state; retained source graph | REFACTOR into StateDiff; do not replace with Stagehand line subtraction |
| LocatorGraph | Labels, ARIA references, relative child paths and causal container reasons | Indexed relationship graph and multiple independently evaluated locator candidates | REFACTOR; current name overstates a mostly per-field record |
| AdaptiveLocator | Semantic equality proposes read remaps; ties/ambiguity stop | Browser Use match ladder as candidate generation, with strict uniqueness and scope added | REPLACE candidate engine; KEEP proposal-only activation |
| ProviderContract | Canonical SHA-256 fingerprints, candidate activation and owner review | Separate stable structure from transient state and cross-load optionality | KEEP contract authority; REFACTOR version/evidence model |
| EvidenceScorer | Hand-authored ordinal levels; 400/300/200/100 container ranking | Explicit evidence vector and contradiction vetoes; later calibration on fixtures/live-reviewed corpus | KEEP veto/unknown behavior; REFACTOR scores, never label them probabilities |
| `workspace.js` section resolver | Selected target references, heading roots, constrained route/heading ancestor/sibling proofs | Generic graph edges for contains, labels, controls, selected, later-sibling and visible-form coverage | MERGE reusable relationship machinery into ControlGraph/SchemaGraph; KEEP Ascend identity adapter |
| `tab-router.js` | Origin/tab/document/version checks; same-document port reuse; fresh owner presence and fixed reinjection | Stagehand context registry; Browser Use single-flight lifecycle coordination | KEEP and factor a DocumentRegistry; no external transport |

Local evidence locations: `extensions/ascend-x1/webbridge.js` lines 38–118, 125–182 and 208–217; `workspace.js` lines 19–54, 112–289, 292–345 and 348–391; `tab-router.js` lines 16–26, 34–109, 113–137 and 139–191. In particular, WebBridge's causal relationship levels and workspace identity constraints are more suitable for FreightDesk than either project's automatic first-match fallback.

## What neither project solves for FreightDesk

- A deterministic LOAD/N identity contract independent of the requested target and independent of a successful click.
- A selected-board or workspace-state graph that remains valid when `/loads` is unchanged.
- A generic, evidence-backed control-to-target edge with uniqueness, contradiction and read/write classification. AX roles and new-node flags are useful inputs, not the completed relationship proof.
- Metadata-only capture whose privacy restriction is enforced before snapshot construction and model input.
- Verified Ascend sticky/header-clone, hidden-column, virtualized-row and pagination semantics.
- Canonical facts with per-field provenance, domain semantics, timezone uncertainty and reconciliation against independent historical evidence.
- A recovery policy that distinguishes safe rereads from uncertain writes while preserving owner/tenant authority.

These gaps are the primary FreightDesk-native work. They should not be disguised as missing selector libraries. Mature open-source projects reduce the generic DOM engineering needed; they do not remove domain identity or authorize inferred actions.

## Suggested first harvest sequence from these two repositories

| Priority | Borrowed idea | Integration point | Source-level decision | Validation needed before incorporation |
|---|---|---|---|---|
| 1 | One indexed immutable snapshot with scoped handles | DocumentGraph | REIMPLEMENT; source architecture reference | Same-document updates, replacement generations, duplicate IDs, privacy traps |
| 2 | DFS interval membership and exclusion | DocumentGraph / ScopeIndex | ADAPT with MIT notice | Nested exclusions, missing roots, mutation invalidation, strict subtree scope |
| 3 | Original graph plus compact AX/semantic projection | DocumentGraph / EvidenceView | ADAPT concepts | Wrapper preservation, label relations, omitted AX data, output budgets |
| 4 | Semantic control candidate reasons and native compound controls | ControlGraph / FieldGraph | ADAPT selected pure rules | Disabled/hidden precedence, wrapper ambiguity, destructive-control classification |
| 5 | Multi-strategy historical relocation | LocatorEngine | REIMPLEMENT safely | All-candidate enumeration, equal-score rejection, same-load/frame scope, stale paths |
| 6 | Separate stable structure and transient state fingerprints | ProviderContract / StateDiff | REIMPLEMENT | Optional cross-load fields, selected-state changes, identity drift, key collisions |
| 7 | Execution-context registry and single-flight recovery | DocumentRegistry / RecoveryEngine | ADAPT state-machine concepts | Late disconnects, refresh, actual module revision, revoke during recovery |
| 8 | Geometric occlusion channel | EvidenceEngine | ADAPT rectangle logic if sensor approved | Overlay/dialogs, transparency, clipping, frame coordinate boundaries |
| 9 | Model output references snapshot handles, never arbitrary selectors | SemanticProposalEngine | REIMPLEMENT from Stagehand grounding pattern | Unknown IDs, out-of-scope IDs, stale observation, malicious text |
| 10 | Structure-aware chunking with table-header carry | EvidenceView | ADAPT with notice; lower immediate priority | Hard bounds, duplicated table headers, provenance-preserving offsets |

No numerical estimate of custom-code reduction is supported by this source-only study. The likely savings concentrate in graph construction, indexing, representation, lifecycle bookkeeping and locator candidate generation. The highest-risk unsolved piece remains **causal section/workspace identity inside a changing same-route application**, which must combine provider relationships, domain identity and action-policy evidence.

## Proposed provenance entry fields

For any future copied/adapted module, record: component; repository URL; exact commit; source path and function; source license file hash; copyright holder; COPY/ADAPT/REIMPLEMENT decision; notice destination; local module; modifications and removed behaviors; retained algorithm assumptions; approved sensor capabilities; test fixture references; reviewer and review date. For clean reimplementations, explicitly mark `copied_code: false` and preserve the algorithm/source references without claiming a legal clean-room process that was not performed.

For these snapshots, public source code remains in the nonsynced research directory. Only these original notes are added to FreightDesk. A future implementation should copy the relevant MIT notice into its third-party attribution bundle when incorporating source, and examine the exact file/dependency chain again at the commit actually used.
