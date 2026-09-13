# Targeted identity diagnostic — live execution stopped

## Current authorization: final attempt prepared, not executed

Attempt ID: `owner-ascend-final-identity-1755-20260911-01` (unused; no runtime grant created here).
From the FreightDesk AI project in PowerShell:

```powershell
.\.tools\python\python.exe -m scripts.ascend_causal_identity --owner-authorized --attempt-id owner-ascend-final-identity-1755-20260911-01
```

Uses the existing persistent local msedge profile and same-process owner confirmation. CLI preparation
is enabled only for this fixed ID. Existing consumed causal_grant records remain unchanged; any
final_causal_grant blocks another execution. No automatic execution or retry. The targeted scan,
category-specific bounds and identity/write gates are unchanged.

Success records sanitized opener-first evidence, targeted container fingerprints/identity relationships
and AscendLoadDetailIdentityContract v1, provider AscendTMS, target 1755, timestamp and confidence VERIFIED.
Contract remains observation-scoped with automatic_reader_activation=false and write_activation=false.
Failure after consuming this final grant (including initialization, bounds, unknown/conflicting/ambiguous
identity or cleanup failure) mandates pivot_required and permanently ends these Playwright identity
experiments. Prepare an engineering assessment of an in-session browser-extension bridge versus
row-bound identity supported by actual provider evidence; no automatic implementation or relaxed gate.

No CarrierView/Outlook call, operational extraction or Ascend production mutation is performed.
The earlier disabled/no-new-attempt paragraphs below describe the previous handoff, now superseded
only by this explicit owner authorization for preparation. This command has not been run live.

No new attempt ID or command is prepared. The prior causal attempt
owner-ascend-causal-identity-1755-20260911-01 is consumed. The CLI now stops at local preflight before
opening a runtime store or browser. Do not rerun the prior command or reset its grant.

## Saved failure and limits of the evidence

Read-only inspection of causal-identity-diagnostics.sqlite3 confirms BOARD_RECONCILED,
STOPPED_CAUSAL_IDENTITY_DIAGNOSTIC and causal_scan_bound. Zero OPENER_STRUCTURE checkpoints and zero
bound measurements were saved. No detail click occurred: the exception arose in the pre-click prepare
callback, after the existing executor resolved one exact-text target and one opener locator.
Full Load ID-column/row binding was not persisted, so it is not established by this artifact.

The old shared code represented: more than eight same-origin frames, opener frame absent from that
set, more than 80 container candidates, OR more than 2,000 descendants in any candidate container.
The exact trigger and measured count cannot be reconstructed. Do not assert a measured overrun or
choose the most plausible branch as fact. Authentication and board reconciliation did not fail.

The design did query broad page-wide candidates (including every ID-bearing element) and enumerate
every descendant of each candidate, including forms. It attempted that scan before persisting opener
metadata. These are confirmed code problems; which branch caused this particular stop remains unknown.

## Offline refactor

TargetedReadExecutor searches only table Load ID headers/cells for exact 1755, without page-text search
or search-box filling. The original action/session/write gates still control the opener click. Opener
metadata is evaluated and persisted separately before any container fingerprint. Only the opener's
same-origin frame participates in the causal scan.

Before click, query specific likely container selectors and fingerprint visible dialogs, modal/panels,
forms, headings and load-detail sections, plus direct opener references. Read attributes, direct child
counts and visibility only; no descendant walks or input reads. Hidden likely-container existence is
remembered as an observer-only weak reference to distinguish newly visible from newly created nodes.

After click, inspect identity only in new/newly visible containers and directly referenced containers.
Resolve row/opener selection and reference bindings locally. Unrelated unchanged forms/panels are not
searched for identity. Within the narrowed scope query identity labels, named/hidden/readonly controls,
load-specific attributes and semantic headings; never enumerate all descendants or all page inputs.
Structural change comparison excludes the addition of diagnostic identity metadata itself.

Explicit bounds (each reports category, measured count, maximum and scan phase before stopping):

| Category | Maximum |
|---|---:|
| Board tables per searched frame | 8 |
| Load-ID table headers | 64 |
| Board rows per candidate table | 100 |
| Opener/container/identity-element attributes | 32 |
| Class tokens | 20 |
| Opener reference targets | 8 |
| Visible candidate containers | 24 |
| Combined candidate containers | 32 |
| Identity candidates per narrowed container | 64 |

Frame evaluations retain a three-second timeout; post-click stabilization retains its ten-second
total budget. These are execution deadlines, not DOM-node measurements. No broad bound was raised.
No raw private values, HTML, query strings, cookies or script bodies are persisted.

## One final test and mandatory pivot

The targeted design warrants considering one final owner-authorized live attempt, but none is prepared
or authorized to run now. A future preparation must explicitly bind that final grant; never reuse the
consumed ID. Any unsuccessful final live diagnostic must stop further Playwright identity experiments.
The runner records pivot_required on a failed live session, preserving the error/stage/measurement.
Assess an owner-approved browser-extension bridge, or an owner-approved row-bound model only if actual
provider DOM evidence supports it. Neither alternative is implemented or authorized by this refactor.
No operational identity gate, write permission or automatic contract activation changes.

## Tests

Targeted offline tests cover identity/conflict/ambiguity behavior, a 5,000-input unrelated background
whose value access throws, exact categorized bound counts, early opener persistence, redaction,
no operational extraction, one-use grants and the disabled live entry point. Synthetic browsers use
intercepted requests and test-only profiles under C:\FreightDeskRuntime\Data\TestRuns.

Results: five targeted tests passed (17 browser scenarios and four measured bound cases included).
Final two-test runner/live-entry rerun passed after adding the mandatory-pivot assertion. Ruff and CLI
help passed; two existing dependency deprecation warnings remain. No live run or new grant was created.
