# X1 Mapping Reliability Fix Pack — 0.6.2

Implemented and tested offline against findings 1–7 in
[ASCEND_WORKFLOW_REVIEW.md](ASCEND_WORKFLOW_REVIEW.md). No live Ascend execution, new real job,
lease, pairing, registry change, provider write or canonical mutation was performed. Browser
permissions and origin scope are unchanged. Operational fields remain UNKNOWN and maps remain
CANDIDATE_ONLY. This handoff supersedes the 0.6.1 retry instructions.

## Corrections

| Review finding | Implemented behavior |
| --- | --- |
| Section identity diagnostics | A rejected section carries typed counts, canonical labels, approved state markers, relationship kinds, visible targets, heading roots, unique candidates and the exact failed predicate. The last completed DOM stage is preserved. |
| OBSERVE lifecycle | An unchanged provider document reuses its private port and observer. Owner navigation hints survive routing/session proof; a replacement document is captured only after fresh proof, then observation is restored. Loading documents wait without probing stale content. |
| Unrelated read dependency | WAITING_FOR_READ_JOB resumes its saved continuation when the other lease ends, including pause/resume and navigation review. Grant, queue and cleanup checks are transactional so concurrent authority changes cannot replace, capture under or revoke an unrelated lease. |
| Optional fields across loads | CROSS_LOAD_VARIATION is stored as candidate variation. Same-load structural drift and identity/navigation topology changes remain fail-closed. |
| Owner readiness | WAITING_FOR_OWNER_WORKSPACE uses a fresh private, document-bound visibility/focus receipt. Session/capture deadlines do not start while the owner is still in PowerShell or the dashboard. Every dispatch rechecks readiness. |
| Immediate job wake | A committed local job/queue/cleanup change appends a wake hint. The already-connected native host observes it during its existing stdin wait and emits a signed notification on the same pipe. Idle polling is bounded at 100 ms; heartbeat/alarm cadence is no longer the only job-start trigger. |
| Reporting and unexpected failures | Normal UI/CLI status exposes safe_stop_code, last_completed_dom_stage, failed_predicate, one owner action and cleanup_state. Unexpected coordinator failures append a sanitized failure receipt and notify after cleanup commits. Expired navigation review persists STOPPED and sends its cleanup wake before returning. |

The outbox is not authorization. It contains only a sequence and timestamp, and cannot specify a
provider operation, URL, selector or script. Notifications are authenticated, deduplicated, coalesced
while the worker is busy, and cause the existing policy/lease checks to run. Protected enrollment
binding is rechecked before a notification is signed. No new socket, server or transport was added.

The integrated test also exposed an existing cross-language MAC defect: Python's `1.0` and
JavaScript's `1` had different signed representations for whole-number timestamps. Canonical MAC
encoding now normalizes finite integral floats in JavaScript's safe integer range, without rounding
fractional timestamps. Raw framing preserves scalar types so strict protocol validation remains
effective. There is no alternative-signature fallback. Tampering, replay and nonfinite-number tests
remain fail-closed. This correction covers the timestamp/count domain used here; it does not claim
a general ECMAScript canonicalizer for arbitrary exponent-form numbers.

Packaged versions: extension/service worker/content script **0.6.2**, controller revision **3**,
content protocol **3**, native protocol **1**. Enrollment and host installation identities are unchanged.

## Section-failure contract

`MappingSectionDiagnostic` contains only:

- `schema_version`, `selected_candidate_count`, `recognized_section_labels`
- `approved_state_markers`, `target_relationship_kinds`
- `visible_target_count`, `heading_root_count`, `unique_candidate_count`
- `failed_predicate`

Predicates distinguish zero candidates, multiple candidates, selected-control/target/heading bounds,
and a section that incorrectly contains workspace identity. Unknown labels are `UNCLASSIFIED`;
attribute values, private text, HTML, notes, phones and screenshots are excluded. Invalid diagnostic
payloads are discarded instead of being logged. Expected load/section input never supplies provider
proof. No live selector was guessed or activated.

## Integrated offline execution

`tests/test_x1_mapping_integrated_path.py` joins the real MappingOrchestrator, RuntimeAccess,
HostSession framing/HMAC/replay handling, worker, router, content script, DOM reader, schema checks,
map store and final orchestrator report. Chrome APIs and the provider DOM are synthetic; every
browser request is fulfilled in memory, and all fixture state is under Runtime TestRuns. No
installed native host or persistent Ascend profile is used.

The path checks:

1. Start while the owner is outside Ascend; wait longer than the old 30-second deadline without
   consuming a capture. A focus event resumes through the signed wake/readiness path.
2. First map reaches DISPATCHED → ACKNOWLEDGED → COMPLETED → MAP_PERSISTED, then closes its
   lease for navigation review. Review remains separate from general AUTO_MAP qualification.
3. A routine session refresh keeps the same port and active observer; it creates no duplicate map.
4. Foreground absence suspends work. A second owner-opened load with an optional field absent
   persists CROSS_LOAD_VARIATION without weakening identity or navigation checks.
5. Document replacement requires fresh routing/session/workspace proof and restores observation.
6. Owner revoke closes authority. Subsequent DOM changes cause neither additional reads nor maps.
7. An unrelated read job retains its authority, then mapping resumes when that job is finished.
8. A section with no valid provider relationship stops with UNIQUE_CANDIDATE_COUNT_ZERO,
   retains WORKSPACE_IDENTITY_VERIFIED, persists zero private values and reports completed cleanup.

Combined verification: **361 relevant tests passed** in 96.11 seconds, including the integrated
execution path. Final review then added five authority-conflict/race regressions and transactional
guards. After those corrections, **128 affected tests passed** in 24.66 seconds and the **integrated
path passed again** in 6.54 seconds. Two final regressions cover direct failure notifications and
expired-review stop persistence; **39 coordinator/API/integrated tests passed** afterward in 11.45
seconds. These follow-up counts overlap the combined suite. Scoped Ruff and syntax checks passed
for the changed Python and 13 packaged/fixture JavaScript files.

The former defect reproduction scripts now assert desired behavior. Other targeted tests cover
ambiguous section selection, privacy rejection, true drift, notification authenticity/coalescing,
readiness timeouts, exceptional cleanup, AUTO_MAP gates and the protected dashboard status UI.
Two existing FastAPI/Starlette dependency deprecation warnings remain; they are not test failures.

## Files changed

| Area | Files |
| --- | --- |
| Coordinator and store | `executors/ascend_extension/mapping_orchestrator.py`, `mapping_store.py` |
| Host, authority and wire contracts | `executors/ascend_extension/host.py`, `runtime.py`, `runtime_contracts.py`, `mapping_diagnostics.py`, `native.py`, `bridge_build.py` |
| Packaged extension | `extensions/ascend-x1/runtime.js`, `tab-router.js`, `content.js`, `workspace.js`, `reader.js`, `build.js`, `manifest.json` |
| Owner surfaces | `app/api/ascend_mapping.py`, `app/dashboard/ascend-mapping.js`, `scripts/ascend_mapping_orchestrator.py` |
| New regression coverage | `tests/test_x1_mapping_integrated_path.py`, `tests/fixtures/x1_mapping_chain.js`, `test_x1_mapping_reliability.py`, `test_x1_mapping_lifecycle_regression.py`, `test_x1_section_diagnostics.py`, `test_x1_mapping_notifications.py`, `test_ascend_native_numeric_canonical.py` |
| Updated fixtures | Existing orchestrator/immediate-capture/runtime tests and controller/runtime/mapping-mode Node fixtures; both review reproduction scripts now check corrected behavior. |
| Handoff | This document, CURRENT_STATE, KNOWN_ISSUES, DECISIONS, AGENTS, the workflow review and mapping-orchestrator handoff. |

## Next owner-executed live validation

Do not run this procedure automatically.

If a FreightDesk dashboard server was already running before this update, let its existing jobs
finish, then stop it with Ctrl+C in its server terminal. Leave it stopped for this CLI-only check:
that process has the old Python coordinator loaded and could otherwise tick the same durable job.
The updated CLI and reconnected native host provide all coordination needed for this validation.
This does not require closing Ascend or changing its authentication.

1. Reload the existing **FreightDesk Ascend X1** extension to **0.6.2**. The existing lifecycle
   recovery adopts the packaged content script under the mapping lease and requires fresh proof.
   No manual Ascend page refresh, re-pair, registration or bootstrap is needed.
2. Open the previously approved **Load 1763 → Load Basics** in that same authenticated Ascend tab.
3. From the FreightDesk repository, run this single command:

```powershell
.\.tools\python\python.exe -m scripts.ascend_mapping_orchestrator start --expected-load-id 1763 --starting-section "Load Basics"
```

4. Return focus to the intended Ascend tab. The job displays WAITING_FOR_OWNER_WORKSPACE until
   readiness is proved; there is no need to race a capture deadline or press a separate Capture button.
   If another read job owns access, finish it normally; the mapping job waits and resumes preflight.
5. Let this one starting-section capture finish. Do not review new navigation, start AUTO_MAP,
   or visit the rest of the cohort during this first verification.

Success evidence: the requested LOAD/1763 and Load Basics are provider-verified; one metadata map
is persisted with MAP_PERSISTED, COMPLETED capture lifecycle and CANDIDATE_ONLY activation. The
job may pause at OWNER_REVIEW_REQUIRED with authority closed, or complete if that starting-section
review already exists. No operational field-read or general AUTO_MAP promotion follows automatically.

On failure, the ordinary result must contain the safe code, last completed DOM stage, exact section
predicate when applicable, owner action and cleanup state. Stop at that receipt. Do not retry,
re-pair, loosen selection criteria or substitute expected-section input for provider evidence.
The independent job deadline still bounds owner waiting; leaving Ascend during an in-flight capture
can still stop that capture. A dispatched NOT_A_LOAD_WORKSPACE remains an explicit stop, not an
automatic retry or an invitation to inspect unrelated page content.

Another controlled owner attempt is justified by the integrated offline evidence and precise failure
instrumentation. It is not justified by an assumption that the real Ascend section layout now matches:
the actual selected-state/target relationship that failed previously is still UNKNOWN. A successful
provider map is still required before claiming live workspace mapping or operational field validation.

If the runtime database itself is unavailable, a receipt cannot be persisted there. The fallback
reports a fixed coordinator failure/storage code and UNKNOWN cleanup instead of claiming success;
independent host lease/policy gates still apply.
