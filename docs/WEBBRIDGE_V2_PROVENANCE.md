# WebBridge V2 provenance and license-handling proposal

Implementation update: the reviewed Playwright subset is now adapted in offline `semantics.js`.
See `third_party/webbridge-v2-implementation.json` for exact pin, hashes, modifications and included
Apache LICENSE/NOTICE. The research descriptions below remain the original audit snapshot and do not
override this narrowly scoped implementation record.

The [proposed registry](../third_party/provenance.yaml) records 24 components: 23 source units covering all 11 studied repositories and one separately pinned Healenium dependency source artifact. **Every component is `incorporated: false`.** No third-party implementation or license file was copied into FreightDesk by this audit. Target module names are design destinations, not implemented files. This document grants no browser, vendor, runtime or production execution authority.

The registry complements the [code-harvest assessment](BROWSER_INTELLIGENCE_CODE_HARVEST.md) and its four source studies:

- [Stagehand and Browser Use](research/WEBBRIDGE_SOURCES_STAGEHAND_BROWSER_USE.md)
- [Scrapling, Crawlee and Crawl4AI](research/WEBBRIDGE_SOURCES_SCRAPLING_CRAWLEE_CRAWL4AI.md)
- [Skyvern, Healenium and Finder](research/WEBBRIDGE_SOURCES_SKYVERN_HEALENIUM_FINDER.md)
- [Playwright, rrweb and axe-core](research/WEBBRIDGE_SOURCES_PLAYWRIGHT_RRWEB_AXE.md)

The studies provide exact functions, algorithms, limitations and commit-pinned source links. Public source snapshots remain in `C:\FreightDeskRuntime\Data\Research\WebBridgeV2`; they are research inputs, not vendored runtime dependencies. Existing installed development tools used to read or validate these documents are separate from the proposed new harvest.

## What the registry means

Each component has a source project, repository, source path, source commit, observed license, engineering decision, commercial reuse category, adaptation notes and proposed FreightDesk destination. YAML source anchors inherit the repeated provenance fields; each component explicitly repeats `incorporated: false`. Parse with YAML merge-key support to resolve the anchors. `source_lines` locates reviewed symbols; it does not authorize copying every line between separately named functions. The source studies remain the detailed evidence.

| Decision | Meaning at this design stage |
| --- | --- |
| COPY | A future narrowly copied helper could be appropriate; none is presently selected for unmodified copying. |
| ADAPT | A reviewed isolated algorithm or helper is a candidate for an attributed, modified implementation after incorporation review. |
| REIMPLEMENT | Write an original implementation from documented requirements/algorithms, without translating upstream implementation text. |
| REFERENCE | Retain comparison and design evidence; do not incorporate its implementation. |
| IGNORE | The implementation is unsuitable for the proposed use, even if its license could otherwise permit reuse. |

Engineering decisions and license categories are independent. A permissive implementation may still be inappropriate because it records values, mutates DOM, silently chooses a target, creates another browser context, or imports an entire execution stack.

| Commercial reuse category | Meaning and limit |
| --- | --- |
| `SAFE_TO_COPY_WITH_NOTICE` | Reviewed permissive source is a possible copy candidate after exact file/dependency and notice review. This category is defined but unused by the current component choices. |
| `SAFE_TO_ADAPT_WITH_NOTICE` | Selected permissive source is a possible adaptation candidate under the recorded notice conditions. No completed-product legal clearance is implied. |
| `PREFER_CLEAN_REIMPLEMENTATION` | An original implementation is preferred because of architecture, privacy, copyleft/additional terms, or incomplete attribution provenance. This does not certify a formal clean-room process. |
| `REFERENCE_ONLY` | Study concepts and compare behavior; direct copying or translation is not approved. |
| `DO_NOT_USE` | Do not incorporate the named implementation for this design. This is a suitability restriction, not a claim that commercial use of the entire project is unlawful. |

## License boundaries by repository

| Project and pinned revision | Reviewed terms | Proposed handling |
| --- | --- | --- |
| Stagehand `b771930d2b4d858e5bd9670203c66260b385a8fa` | [MIT](https://github.com/browserbase/stagehand/blob/b771930d2b4d858e5bd9670203c66260b385a8fa/LICENSE) | Selected index, projection and lifecycle concepts; preserve Browserbase copyright/permission notice for source adaptation. The separately referenced cache server was not available for code harvest. |
| Browser Use `50f205533fe10ba35b553d2a3689c77b87bd5d0a` | [MIT](https://github.com/browser-use/browser-use/blob/50f205533fe10ba35b553d2a3689c77b87bd5d0a/LICENSE) | Selected graph/geometry algorithms; preserve applicable MIT notice. Exclude its agent, session switching and raw-value collection paths. |
| Scrapling `48da61d1ee85cea7bbbdff013d98c90602e1d93f` | [BSD-3-Clause](https://github.com/D4Vinci/Scrapling/blob/48da61d1ee85cea7bbbdff013d98c90602e1d93f/LICENSE) | Preserve copyright, conditions and disclaimer in source and required binary materials; no endorsement implication. The separately licensed agent-skill package is excluded. |
| Crawlee `0b2ac45323d7be8d9d3d146d4873cec1cafdc095` | [Apache-2.0](https://github.com/apify/crawlee/blob/0b2ac45323d7be8d9d3d146d4873cec1cafdc095/LICENSE.md) | Retain Apache license/applicable notices and mark modifications. No separate NOTICE was found in the examined tree. Crawler, session pool and page-mutating helpers are excluded. |
| Crawl4AI `862f6bccb9c063f49b9d42701baa0eea17a4993f` | [Apache text plus appended attribution requirement](https://github.com/unclecode/crawl4ai/blob/862f6bccb9c063f49b9d42701baa0eea17a4993f/LICENSE) | Record custom `LicenseRef`, not unqualified Apache clearance. Prefer original schema-proposal concepts; direct source remains unapproved pending added-term review. |
| Skyvern `35cfb314f4777ad77130dae087b26aa3ef99c489` | [AGPL-3.0](https://github.com/Skyvern-AI/skyvern/blob/35cfb314f4777ad77130dae087b26aa3ef99c489/LICENSE) | Reference/original concepts only. Direct source use requires review of applicable copyleft/source obligations or a suitable separate agreement. No permissive exception for examined core was found. |
| Playwright `d1ead3ecca23182f2d06d761c28e3d4edafb6595` | [Apache-2.0](https://github.com/microsoft/playwright/blob/d1ead3ecca23182f2d06d761c28e3d4edafb6595/LICENSE), [NOTICE](https://github.com/microsoft/playwright/blob/d1ead3ecca23182f2d06d761c28e3d4edafb6595/NOTICE) | Selected injected helpers only; audit dependent helpers, preserve applicable NOTICE material and mark modifications. No new Playwright executor is proposed. |
| rrweb `32ed9fe5387e088cfc023c71a39672c30c516da7` | [MIT](https://github.com/rrweb-io/rrweb/blob/32ed9fe5387e088cfc023c71a39672c30c516da7/LICENSE) | Node mirror and original mutation-ordering concepts; preserve MIT notice where source is adapted. Recorder/replay, prototype patching and input capture are excluded. |
| axe-core `4d306cbb7c456849c6f964444a6a7174d2be502a` | [MPL-2.0](https://github.com/dequelabs/axe-core/blob/4d306cbb7c456849c6f964444a6a7174d2be502a/LICENSE), [third-party notices](https://github.com/dequelabs/axe-core/blob/4d306cbb7c456849c6f964444a6a7174d2be502a/LICENSE-3RD-PARTY.txt) | Reference table/label behavior; implement the standards model independently. Direct covered-file inclusion is not cleared by preserving a notice alone. |
| Healenium Web `c1e4f83d8995c2928ea1e09e721a7ac9f421bd69` | [Apache-2.0](https://github.com/healenium/healenium-web/blob/c1e4f83d8995c2928ea1e09e721a7ac9f421bd69/LICENSE), [EPAM header](https://github.com/healenium/healenium-web/blob/c1e4f83d8995c2928ea1e09e721a7ac9f421bd69/HEADER) | Candidate-history concepts only; retain applicable Apache/EPAM notices on adaptation. The transitive scoring library has a separate provenance record below. |
| Finder `a8d83110d3d035e029c571b94965b629a10a469f` | [MIT](https://github.com/antonmedv/finder/blob/a8d83110d3d035e029c571b94965b629a10a469f/LICENSE), source attribution in `finder.ts` | Small adaptation candidate after hard search bounds and exact-target validation; retain Anton Medvedev copyright/permission text. Website fixtures and dev dependencies are excluded. |

Crawl4AI's root addendum calls for prominent UncleCode/Crawl4AI attribution for public use, including web About/Credits and CLI help examples. Its interaction with the Apache text has not been resolved by this engineering review. Vendored `html2text` and other dependencies were not cleared by that root license. The custom terms belong to Crawl4AI; **MPL here refers to axe-core, and AGPL here refers to Skyvern**. No claim is made that Crawl4AI itself is MPL- or AGPL-licensed.

MPL allows commercial larger works while retaining duties for covered files, including relevant source availability on distribution; it is not a blanket ban on proprietary software. AGPL also permits commercial activity, with applicable modified-work and network-source obligations. Neither is equivalent to MIT/Apache notice-only treatment. No commercial exception was verified for the inspected Skyvern modules, and a hosted service subscription is not evidence of source relicensing. These distinctions are supported by the linked licenses; final incorporation still needs review of actual packaging and use.

## Healenium artifact provenance gap

Healenium Web pins `com.epam.healenium:tree-comparing:0.4.14`. The [published POM](https://repo.maven.apache.org/maven2/com/epam/healenium/tree-comparing/0.4.14/tree-comparing-0.4.14.pom) declares Apache-2.0. The exact [source JAR](https://repo.maven.apache.org/maven2/com/epam/healenium/tree-comparing/0.4.14/tree-comparing-0.4.14-sources.jar) was inspected and has SHA-256:

```text
1b785629b9f8b76268009227f3503562296f90959749797e4dc4d63c3b974187
```

Its declared GitHub repository returned 404 during the audit. A Git revision could not be verified, and the archive contained no LICENSE/NOTICE/per-file attribution header. Accordingly the registry preserves `source_commit: null`, the exact artifact identity/hash and `VERIFIED_SOURCE_ARTIFACT_HASH_GIT_COMMIT_UNKNOWN`. Version `0.4.14` is not substituted for a commit. This is an additional artifact entry attached to the Healenium study, not a twelfth independently verified repository. The POM's license declaration is evidence, but it does not close the attribution/redistribution provenance gap. Direct class copying remains unapproved.

## Future incorporation and NOTICE handling

The following is a proposed process for a later authorized implementation. None of its copy/publish steps has been executed here.

1. Select the exact source unit and pin the revision actually used. Record symbols, ranges, source-file SHA-256, applicable license/NOTICE hashes, upstream attribution and dependent helpers. Recheck per-file headers, submodules, vendored code, generated assets and dependency terms; do not inherit a root license blindly.
2. Resolve extra terms and provenance gaps before direct source reuse. MPL/AGPL/additional-attribution material needs use-specific review; ambiguous material remains reference only. Source-informed original design does not justify calling a line-by-line translation a clean implementation.
3. Before merging a copied/adapted unit, prepare the required license and applicable notice material in a future `third_party/licenses/<project>/` bundle and a future `THIRD_PARTY_NOTICES.md`. Preserve copyright/permission text, applicable Apache NOTICE contents and changed-file notices. These paths are a plan; no files or fulfilled-attribution claim are created now.
4. Record the real FreightDesk file/commit, changes and removed behavior, dependency closure, reviewer, approval reference, tests, copied-versus-original status and notice destinations. Split mixed-license units into separate entries. Only then can an actually incorporated component change to `incorporated: true`.
5. Validate the result against the existing X1 boundary: approved document scope; no raw values in metadata capture; no broader permissions or transport; exact entity/control proof; bounded all-candidate evaluation; contradictory evidence stops; unknown coverage stays unknown; no write execution. License permission never expands ActionPolicy.
6. Include required attribution/source availability in the actual distribution or service workflow if the selected terms require it. A repository markdown file alone may be insufficient. On upstream updates, compare license/NOTICE and algorithm changes before changing the pin.

No browser intelligence algorithm supplies FreightDesk's tenant/load identity, action authorization, private-data boundary, canonical truth or operational reconciliation. Those remain FreightDesk responsibilities even for permissively licensed helpers.

## Registry validation

The local Python environment does not contain PyYAML. The existing Playwright driver bundle exports a YAML parser, so validation used that already-installed utility without installing or running a browser. Validation loads the proposed registry with merge keys enabled and duplicate keys rejected, checks all required component fields, allowed decisions/categories, 11 pinned repository defaults, the single explicit artifact commit gap, unique component names, and `incorporated: false` for every component. No studied browser collector/executor, provider fixture or operational runtime database was executed for this check.

Validation completed on 2026-09-12: **PASS**, 24 components, 11 repository pins, one explicit artifact commit gap, no parser warnings, and all components unincorporated. Source pins also matched their referenced research notes. No dependency was installed.
