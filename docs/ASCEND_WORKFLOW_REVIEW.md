# Ascend workflow review — 2026-09-12

**Implementation follow-up:** the owner-authorized
[X1 0.6.2 reliability pack](ASCEND_X1_MAPPING_RELIABILITY.md) addresses this defect list offline.
The descriptions below preserve the reviewed pre-fix behavior and original live evidence. The
two reproduction scripts now assert desired behavior, rather than asserting the original defects.

The current blocker is section recognition in FreightDesk. The latest local run successfully
dispatched a capture, received its acknowledgement, verified the Ascend session and passed the
workspace identity gate. It stopped with `WORKSPACE_SECTION_UNVERIFIED` before mapping fields.
This is different from the previous job's owner-presence rejection and expiry.

Several additional coordination bugs were reproduced offline. Fixing only the current section
error would leave later OBSERVE and cohort steps capable of stalling. No live execution, production
code correction, new job, lease, pairing, provider request or capability promotion occurred in this review.

## Evidence inspected

Read-only, whitelisted projections of these existing owner-authorized databases:

- `C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\mapping-orchestrator.sqlite3`
- `C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\runtime.sqlite3`

Only job stages, timestamps, sanitized error codes, structural counts and evidence counts were
printed. No raw provider payloads, private field values, browser state or secrets were inspected.
Source review covered owner CLI/dashboard/API, orchestrator, runtime authority, native-host hooks,
extension scheduling, worker, router, content lifecycle, workspace/section capture, map storage,
and their fixture tests. Historical handoffs were used to distinguish resolved and current issues.

### Latest observed job

| Event | UTC, 2026-09-12 |
| --- | --- |
| Owner job started | 13:55:37.733016 |
| Capture requested | 13:55:39.827000 |
| Capture dispatched | 13:55:39.937540 |
| Capture acknowledged | 13:55:39.952710 |
| Failed capture receipt | 13:55:40.021475 |
| Job stopped; cleanup complete | 13:55:40.036478 |

Queue-to-dispatch was approximately 111 ms; dispatch-to-ACK was 15 ms. The whole job stopped in
approximately 2.30 seconds. This run did not wait for the read deadline or lease expiry.

The final structural diagnostic was:

```text
last_completed_stage = WORKSPACE_IDENTITY_VERIFIED
candidate_workspace_count = 1
identity_signal_count = 1
section_control_count = 12
elapsed_ms_at_last_completed_DOM_stage = 10
stop_code = WORKSPACE_SECTION_UNVERIFIED
provider_maps_persisted = 0
auto_map_cycles_persisted = 0
cleanup_complete = true
production_writes = false
```

The entity-discovery stage counted 14 recognized controls; workspace proof reduced these to 12
distinct recognized section names. These are navigation-control counts, not resolved section-root
counts. Ten milliseconds describes the last completed DOM stage, not the total capture duration.
The requested target and starting section were configured; section recognition failed before a
starting-section match or field capture could complete. A diagnostic stage is not a complete
provider-map artifact or an operational field validation.

The preceding job started at 03:22:49 UTC, dispatched at 03:23:15 and received
`MAPPING_OWNER_NOT_PRESENT`; its final report was `READ_LEASE_EXPIRED` at 03:32:49. Source 0.6.1
addressed that handoff/error-suppression defect. The newest receipts show that the immediate capture
path advanced further. The cause of the older missing foreground presence was not persisted.

## Findings and minimum corrections

### 1. Current section gate provides insufficient failure evidence — live-proven stop

`extensions/ascend-x1/workspace.js:56–79` recognizes a section through a selected control with a
same-document target relationship, or a recognized visible heading inside a limited set of root
elements. The exact failing predicate at line 77 is `unique.length !== 1`.

Zero matches and multiple competing matches produce the same error. Neither the candidate count
nor the failed relationship is persisted. The present audit cannot establish which case occurred,
which selected marker Ascend used, or whether a valid control lacked one of the supported target
relationships. It would be incorrect to name a particular missing selector or rendering defect.

The mapper therefore needs a structural diagnostic at this specific gate: selected candidate count,
recognized section labels, approved state markers, target relationship kinds, visible target counts,
heading-root counts, unique candidate count, and a precise failed predicate. Capture this only
inside the verified workspace and only as sanitized metadata. Keep field extraction blocked until
one provider-backed section is established. Do not use the owner's expected section as proof.

### 2. Routine session refresh removes passive observation — reproduced integration bug

`extensions/ascend-x1/runtime.js:75–90` probes owner-present tabs by selecting them again.
`tab-router.js:26–27` disconnects the current content port during selection. `content.js:23,32`
removes the mapping observer on disconnect; only successful mapping reinstalls it at lines 59–64.
A session-only probe does not restore it.

The real worker/router/content reproduction produced:

| State | After first map | After idle refresh |
| --- | ---: | ---: |
| Content connections | 1 | 2 |
| Active mapping observers | 1 | 0 |
| Successful maps | 1 | 1 |
| Successful session proofs | 1 | 2 |

The coordinator can then wait for a change hint that no component can emit. Full navigation or
switching eligible tabs has a related gap: routing is invalidated, but a durable mapping-change
hint is not established for the new document. Authentication can remain healthy throughout.

Preserve the port when the approved document is unchanged. On actual replacement, explicitly
restore observation and record a lease-bound owner-navigation hint. Fresh session, workspace and
section proof must still precede every capture. This is a later-stage defect, not the cause of
today's zero-map section stop.

### 3. Waiting for another read job is a dead end — reproduced state-machine bug

`mapping_orchestrator.py:394–396` enters `OWNER_REVIEW_REQUIRED / READ_JOB_ACTIVE` when a healthy
board lease owns access. When that lease ends, `tick()` still leaves the review state inert
at lines 374–375. Repeated Start returns the same unfinished job; Resume only handles paused jobs.
The dashboard also disables Start while review is pending.

The in-memory reproduction revoked the unrelated lease, then called Tick, Start and Resume.
All remained `OWNER_REVIEW_REQUIRED`. The requested owner action cannot resolve the wait.

Reevaluate this specific dependency wait and resume preflight within the original authorization
deadline when the other job ends. Do not revoke unrelated authority or restart an uncertain capture.

### 4. Optional fields across loads become fatal drift — reproduced cohort bug

`mapping_store.py:33–44` compares each section with the latest same-named section across all loads.
Any fingerprint difference becomes `structural_drift`. `mapping_orchestrator.py:276` treats that
flag as terminal `WORKSPACE_CHANGED`.

A synthetic first load with an optional field followed by another load without it produced
`structural_drift=true` and stopped the orchestrator. This contradicts the representative cohort's
purpose of learning optional and conditional structure. The lower-level optional-field test passes
because it does not run the orchestrator's fatal-drift decision.

Separate cross-load variation from changes to verified identity/navigation and from unexplained
changes within the same workspace. Store variation as a candidate observation; keep ambiguous
identity, unsafe navigation and unverified operational fields blocked.

### 5. Safe failure details remain hidden in normal owner reporting — code-proven

`mapping_orchestrator.py:584–597` omits the sanitized stop code and last DOM stage from normal
status. They are available through advanced status, while CLI/dashboard use the normal projection.
`WORKSPACE_SECTION_UNVERIFIED` also lacks a specific owner-facing message. Thus useful internal
evidence again becomes a generic stopped message.

Additionally, `app/api/ascend_mapping.py:62–67` silently discards unexpected loop exceptions.
Deadline cleanup is a safety fallback, not adequate reporting for a failed coordinator step.

Expose the safe code, last completed stage, failed predicate and appropriate next action in the
ordinary result. Persist a sanitized coordinator-failure receipt for unexpected exceptions; never
log exception text or provider payloads. Distinguish waiting, command rejection, capture failure
and successful persistence in the normal UI.

### 6. Owner startup and foreground readiness are not coordinated — workflow gap

Dashboard Start leaves the dashboard selected; CLI Start leaves PowerShell focused. The worker
requires the eligible active tab, and `reader.js:294` additionally requires `document.hasFocus()`.
There is no explicit armed/waiting-for-owner-workspace handoff before capture. Quickly switching
focus can work, but the owner must win a timing race. The earlier live owner-presence rejection is
consistent with this gap; its exact focus state was not recorded, so causation remains unproven.

Use an explicit bounded readiness wait before consuming a capture. After the owner returns to the
authorized Ascend workspace, verify presence and start the short dispatch/ACK/completion deadlines.
Do not weaken the presence or identity gates and do not retry a rejected capture silently.

The fail-fast presence handling also applies to every orchestrated scope, including passive
`OWNER_NAVIGATION_OBSERVE`. That scope should suspend observations when the owner leaves an
eligible workspace; a queued exact CURRENT_LOAD capture has different failure semantics.

### 7. Start latency depends on incidental scheduling — code-proven latency, conditional risk

The local Start action writes a job but does not itself notify the extension. The background alarm
is 60 seconds, but ordinary enrolled Native Messaging STATUS acknowledgements also wake the runtime
every 20 seconds. The latter was verified with actual background code and synthetic timers/ACKs.

Therefore a blanket claim that the 60-second alarm necessarily defeats the 30-second session
deadline is incorrect. Healthy heartbeat traffic usually leaves time for proof. There can still be
approximately 20 seconds of startup delay, and delayed heartbeat/recovery is an untested deadline
interaction. This is not the latest live stop and the current code does not meet a general
5–10-second startup/context-assembly guarantee.

Provide an explicit job-readiness notification through the existing local channel, or make polling
latency and readiness deadlines agree. Test actual scheduling and wake behavior together. No new
transport architecture is required to establish the correct contract.

## Why the existing checks did not prevent this

- `tests/test_ascend_mapping_orchestrator.py:23–36` supplies successful session and map receipts
  directly. It does not verify how the extension produces them.
- `scripts/check-x1-immediate-capture.js:9–13,36` mocks the router and calls worker wake directly.
  It proves the same-wake lease transition but bypasses real focus, scheduler and port lifecycle.
- `tests/test_ascend_mapping_api.py:43–76` substitutes a successful API progression. It does not
  join dashboard Start to extension execution.
- Most reader fixtures use synthetic DOM that already has the expected role/fragment relationships.
  They prove handling of those layouts, not that live Ascend exposes them.
- Owner-navigation tests inject change hints rather than testing their browser-event producer.
- Optional-field storage tests and orchestrator drift tests do not exercise the same multi-load path.

These checks remain useful component tests. Their combined passing count is not an end-to-end
execution test or provider compatibility evidence. Repeated owner attempts have been discovering
integration and diagnostic gaps that should have been exposed offline first.

## Recommended completion order before another live attempt

1. Make normal status and section-gate failure evidence precise and safe.
2. Repair observer lifecycle, dependency-wait recovery, and cross-load variation handling.
3. Add explicit owner-foreground readiness and test the real scheduling handoff.
4. Run one integrated offline path through actual coordinator/host dispatch/worker/router/content
   boundaries, with synthetic provider DOM, clock and transport. Cover first capture, idle refresh,
   second owner-opened load, optional fields, external lease completion, review, revoke and cleanup.
5. Only after those changes and checks, prepare a separately owner-executed structural validation
   at the unresolved section boundary. Do not guess live selectors or revisit healthy enrollment,
   Native Messaging, board identity or the closed Playwright identity approach.

Retain the distinction between metadata discovery and operational facts. No provider maps or
AUTO_MAP cycles are persisted in the inspected live runtime. Operational detail mappings remain
UNKNOWN; existing Active Loads validation remains VISIBLE_BOARD_ONLY. Sending, provider writes,
canonical mutations and automatic traversal of unverified controls remain blocked.

## Reproducible offline review diagnostics

```powershell
node scripts/check-x1-observe-lifecycle-review.js
.\.tools\python\python.exe -B -m scripts.review_x1_mapping_state
```

These diagnostics assert and label the current defects. Exit zero means the defect was reproduced,
not that the product passed validation. They use synthetic data and in-memory state; no browser,
installed host, vendor networking, real lease or runtime-file mutation. Convert them into desired-
behavior regression tests when implementing the corrections. Production code was not changed here.
