# X1 / WebBridge V2 audit fixes — 2026-09-13

Owner request: implement the audit fixes. The authoritative findings are A01–A10 in
`C:\FreightDeskRuntime\Data\TestRuns\webbridge-audit-20260912\AUDIT.md`.
The earlier 436-test acceptance is historical; it missed the reproduced boundary defects.
This repair is offline source work. No installed extension/host/profile, registry, permissions,
real lease, enrollment, vendor request or operational value collection was changed or executed.

## Repair matrix

| Finding | Implemented correction | Regression evidence |
| --- | --- | --- |
| A01: incoherent legacy map/graph | One mutation fence spans verified shell/section, legacy metadata, V2 projection and final checks. Every field has an indexed node/fingerprint binding; host checks vocabulary meaning and membership in the proved section. | Mutation after legacy completion rejects; valid-but-contradictory legacy field rejects at actual persistence boundary. |
| A02: private neighbor/aggregate reads | Admit bounded static label structures before text access; exclude private/value descendants; arbitrary neighboring spans cannot be label sources. No aggregate textContent reads in workspace mapper. | Actual facade trips on any private input, private neighbor, aggregate text or unbounded query getter; successful metadata capture with zero private reads. |
| A03: remounted nodes reuse IDs | Adapter owns the document/realm WeakMap ledger; observation handles are released independently. New physical nodes get new IDs. Document replacement rotates the binding; bfcache suspension retains identity; disposal closes the adapter. | Actual facade captures a clone, surviving controls, restored document and replacement epoch. |
| A04: modest forms exceed wire budget | Compatibility v3 uses compact positional graph wire v1, reconstructed and strictly checked at host. Fixed node evidence is reconstructed without repeated wire properties. | 12- and 19-field forms accepted within unchanged 32,000 graph / 45,000 combined limits. Larger fixture stops safely. |
| A05: contradictory resolution evidence | Cross-check resolutions, explicit edges, unresolved cardinalities, coverage and owned metadata evidence. Integer literals reject float/bool equivalence. Native wrapping labels remain independently accounted for. | AMBIGUOUS plus a unique edge and no unresolved receipt rejects; floating schema/revision rejects; existing reference corpus passes. |
| A06: caller-selected business domain | Application-owned field-to-domain map plus finite timestamp/scalar/source checks. Missing/invalid observations remain UNKNOWN. | Equipment cannot promote financials; invalid/null/NaN value, invalid timestamp and untrusted source reject. No operational read enabled. |
| A07: bounds only cover standalone core | Workspace queries use streaming iteration with pre-allocation bounds, admitted text traversal and reused verified shell. The entire compatibility capture uses the existing three-second DOM deadline. | Actual facade rejects excessive chrome before an unbounded result allocation; full-facade timings measured. Identity and section checks retained. |
| A08: full-history scans | Additive section/load/load-section/session indexes; bounded latest queries; MAX(id) version allocation; SQL-filtered bounded reports/coordinator reads. | 2,000 prior maps require at most four map JSON decodes; selected session report decodes one map; query planner uses index; all history retained. |
| A09: incomplete acceptance corpus | Audit fixtures now test desired behavior at actual facade/host, plus representative forms and an actual subprocess crash after runtime commit. Existing synthetic full chain remains. | Fresh process recovers committed evidence, creates no duplicate, replays no read and closes job authority. |
| A10: no source baseline/rehearsal | Local audited baseline commit `6d4a781`; versioned source-hash manifest; source-only rollback rehearsal checks all 358 baseline Git blobs under TestRuns. | Project/installed-state targets reject; conflicting rehearsal files reject; V1 remains the baseline manifest default. |

## Measured scope and limits

One offline synthetic run through the actual facade measured:

| Visible fields | Compact graph bytes | Combined map bytes | Capture milliseconds |
| ---: | ---: | ---: | ---: |
| 12 | 10,858 | 20,805 | 177 |
| 19 | 15,298 | 29,802 | 180 |

These timings include legacy metadata, its stabilization delay and V2 projection, not transport,
SQLite or coordinator time. They are not Ascend latency claims. A 32-field fixture exceeds the
combined limit and returns MAPPING_PAYLOAD_BOUND. Field count alone cannot predict byte capacity.
No transport limits were raised: native framing remains 65,536; combined map 45,000; graph wire
32,000. The existing standalone internal graph budget is 262,144, still independently bounded.
Host decoding bounds node/edge array widths/counts before full typed validation.

Workspace discovery allows at most 4,096 visited elements per semantic iterator and 1,024 matches;
label text allows 32 nodes, four levels and 128 characters. Existing narrower identity, field,
attribute and section bounds remain. Extremely large unrelated chrome may stop with WORKSPACE_BOUND;
this is bounded failure, not a claim that every large provider DOM can be mapped. The repair does
not implement the deferred generic field/table engine or eliminate every repeated proof scan.

Reports select only relevant sessions and stop rather than truncate above 4,096 rows per collection.
Current mapping session limits are much smaller. Lifetime history remains append-only. Index creation
is additive at a future runtime database open; no live runtime DB was opened or migrated by this task.

## Release and maturity

| Component | Source/validation state | Live state |
| --- | --- | --- |
| V1 X1 | Default manifest; shared collector privacy and bounded history fixes in source | Prior exact LOAD/1763 metadata success remains historical evidence; these new fixes are not live-tested |
| V2 Phases 0–2 | Compatibility 3 / graph 2 / wire 1; fixture and TestRuns gates; OBSERVE only | Not installed, not LIVE_VALIDATED |
| Candidate field mappings | Graph-bound structural candidates; semantic_read_validation=NOT_VALIDATED | Operational meanings remain UNKNOWN |
| Board runtime | Existing source and independent policy/view gates retained | Historical VISIBLE_BOARD_ONLY promotion preserved; no new board read |
| General OBSERVE / AUTO_MAP | Existing scope/qualification policy retained; V2 AUTO_MAP prohibited | No generalization or traversal promotion |
| Phases 3–7 | Deferred | No claim |

The immutable source manifest identifies the exact offline source independently of the unchanged
installed X1 version string. It is not a deployable V2 extension package or a production upgrade
command. The baseline is the audited pre-repair source, **not** a claim that its defects are safe to
restore into production. Rollback rehearsal extracts only into TestRuns and never resets the project.
No prior navigation approval is migrated into compatibility v3.

Offline verification commands:

```powershell
.\scripts\test.ps1
.\.tools\python\python.exe -m scripts.webbridge_v2_release
```

The second command emits an immutable source manifest plus a baseline rehearsal under
`C:\FreightDeskRuntime\Data\TestRuns\webbridge-v2-offline-release\<source hash>\`.
It cannot install, reload, enable a lease, contact a vendor or modify a browser profile.

## Remaining live unknowns and next boundary

Actual provider DOM size, conditional fields, iframe/closed-root coverage, installed MV3 isolated-world
lifecycle, host startup and realistic cross-section performance remain unverified for V2. The new
tests use real source modules and local synthetic DOM with intercepted networking, not an installed
production extension. The separately referenced revised implementation-plan document remains
unavailable; it was not silently substituted or claimed reviewed.

A future live migration requires a separately reviewed package/version handshake and explicit fresh
owner authorization for one exact current workspace, metadata only, with dispatch/ACK/proof/map and
cleanup receipts. No executable live command is prepared by this repair, and closed grants must not
be reused. A new live retry is not a substitute for packaging review or these offline acceptance tests.

## Verification completed

`scripts/test.ps1`: 960 passed in 375.61s, full Ruff and all scripted dashboard checks passed.
Final audit/release rerun: 18 passed; final integrated chain rerun: 7 passed; final release tests:
4 passed. Counts overlap; the full suite plus five distinct new cases cover 965 tests. Node syntax
checks passed. The two existing Starlette/AnyIO dependency deprecation warnings remain.

The additional 19-field full-chain case reaches host validation, atomic map/graph/completion storage,
coordinator result and cleanup. Its synthetic focus-to-cleanup measurement was 1.056 seconds,
including an independent subprocess crash/recovery probe. This is fixture evidence, not a provider SLA.
The actual provider DOM and installed V2 package still require separate authorization and validation.

The source-release command requires a clean committed working tree. Its manifest records the repair
commit and all source file hashes; it refuses to overwrite a conflicting artifact or reset the project.
