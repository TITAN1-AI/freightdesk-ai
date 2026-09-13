# X1 session and mapping causal debugging — completed 2026-09-12

The exact authorized task succeeded on iteration 5 of 5: one provider-verified Load 1763 /
Load Basics metadata map persisted. All live debugging has stopped. Job-owned temporary read
authority is REVOKED, cleanup COMPLETE. Do not start a sixth iteration or continue navigation.
No enrollment, extension pin, browser permission, registry or unrelated authority was changed.

## Actual success evidence

The final signed runtime receipt and private content handshake prove extension/worker/content
0.6.2, controller revision 3, content protocol 3, native protocol 1, causal diagnostic revision 1
and actual workspace reader revision 2. Source-file version alone was not used as proof.

| Phase | Actual live result |
| --- | --- |
| A — fresh session/readiness, dispatch, ACK | PASSED. Matching tab, document, generation, mapping lease, host runtime instance and process. ACK 16.401 ms after dispatch. |
| B — exact workspace | PASSED. Provider LOAD/1763 identity verified before section work and revalidated after capture. Tenant Booking Logistics remains OWNER_ATTESTED. |
| C — Load Basics map | PASSED. Exactly one map, provider-map version 1, 19 field metadata proposals, CANDIDATE_ONLY, values_included=false, writes_allowed=false, production_writes=false. |

UTC receipts on 2026-09-12: mapping-lease session proof 16:40:33.640906; ACK 16:40:33.726224;
map persisted receipt 16:40:33.931617; authority revoked 16:40:33.946733. DOM capture measured
188 ms. The job has one completed capture, last stage MAP_PERSISTED and cleanup COMPLETE.
Its final UI stage is OWNER_REVIEW_REQUIRED because navigation approval is a separate milestone;
no review or automatic traversal was performed. No further owner action is needed for this task.

The final causal trace has 40 events. Its mapping lease produced only ASCEND_GET_SESSION_STATE /
ASCEND_MAP_WORKSPACE receipt operations. No read receipt followed its revocation. No operational
values, provider writes, other loads/sections, other vendors or canonical mutation were executed.
Coverage is CURRENT_VISIBLE_SECTION_ONLY. Field semantics, general OBSERVE across real loads,
AUTO_MAP and operational extraction remain unvalidated. The candidate contract retains
live_validated=false; observing its metadata does not validate its field mappings.

## Existing owner-run DOCUMENT_CHANGED evidence

The earlier owner job at 15:10:53.945579–15:10:56.909202 UTC received probe-lease session proof at
15:10:56.747204, enabled a mapping lease at .765603, queued capture at .775205, then received a
fresh successful session under that new lease at .838342. Worker routing CONTROL reported
DOCUMENT_CHANGED at .888768. Coordinator reporting replaced it with SESSION_UNVERIFIED at
.903264 and closed access. There was no capture dispatch, ACK, workspace observation or map.

Both provider session receipts used the same tab/document generation 1. This was not demonstrated
to be a failed login or reuse of an old-lease proof. The exact router branch was not persisted.
DOCUMENT_CHANGED did not recur in the instrumented agent runs; its historical branch remains
UNKNOWN. Successful new runs do not retrospectively establish that missing cause.

## Five bounded iterations

1. Local reconnect preflight, conservatively counted: native audit reached RESUME_SUCCESS,
   then X1 reported PAIRING_ACK_INVALID. No new job, grant or provider read. The new causal-trace
   ACK omitted protocol/tenant/actor/paired-state bindings required by the worker. Corrected
   the host response, preserving every existing verification gate.
2. Fresh session/readiness, dispatch/ACK and exact LOAD/1763 passed. Browser tab selection left
   keyboard focus in chrome; the helper requested page focus and X1 independently proved it.
   Section stopped WORKSPACE_SECTION_UNVERIFIED / UNIQUE_CANDIDATE_COUNT_ZERO: 12 recognized
   controls, 4 selected candidates, no verified target or supported heading root.
3. Structural diagnostics without changed acceptance rules found one selected recognized Load
   Basics anchor resolving to current origin/path without query/fragment, plus one visible H1
   Load Basics with no supported semantic root. Other active controls were unclassified.
4. Tested bounded selected-route/heading ancestor rule; actual mapper revision 1 proved. A/B
   passed. Section stopped NO_ELIGIBLE_ROOT: four ancestors, first without form fields and
   remaining three containing section navigation. No map; authority revoked. New evidence
   supported a unique sibling form region rather than allowing navigation in the captured root.
5. Actual mapper revision 2 proved. A/B/C passed. Nearest form-bearing heading context: depth 2,
   four direct children, three forms of which one was visible, one heading branch and one later
   form branch containing all visible forms. Its selected region had 19 visible eligible fields.
   Identity/navigation were outside that region. One map persisted, authority closed. Stop on
   both success and the five-iteration limit.

## Narrow corrections and proof rules

The ACK correction adds required authenticated response bindings; it never resets pairing or
relaxes authentication. Local Windows UI Automation operates browser chrome only for pinned
Reload and verified Ascend focus. The helper requests page focus using F6 from the verified
address bar; X1 still independently requires visibility/focus. Provider reads remain in X1.

Section proof combines an independently selected provider current-route control and matching
unique visible heading. The requested section name is only a final scope check. Existing semantic
target proof remains first. The fallback examines bounded heading ancestors, then the nearest
form-bearing context with exactly one later DIV branch containing all visible forms. Competing
branches, identity in that context, navigation/identity/other section headings in the selected
region, ambiguous selection and mismatched headings stop. Bounds: 8 ancestors, 24 direct children,
16 candidate forms, 256 form-control candidates, then the unchanged 64 visible mapped-field limit.
No class/ID selector was guessed, bound raised or navigation control automatically approved.

Sanitized diagnostics retain structural counts, approved labels/state markers, relationship kinds
and precise predicates. Normal status and durable failure receipts prefer the innermost recorded
predicate. No private values, HTML, arbitrary attributes, notes or script text are retained.

Opt-in --causal-trace uses the existing authenticated pipe, at most 256 events per job. Ordinary
jobs do not trace. Diagnostic exhaustion cannot block revocation. Actual content trace and mapper
revisions are handshaken; stale modules trigger fixed packaged reinjection.

## Evidence and verification

Evidence stays under C:\FreightDeskRuntime\Data\booking-logistics\ascend-native:

- agent-causal-debug-20260912.jsonl: append-only five-iteration summary.
- agent-causal-debug-20260912-final.json: sanitized binding/map/cleanup summary.
- runtime.sqlite3: causal stream, signed receipts, diagnostics and candidate map.
- mapping-orchestrator.sqlite3: preserved job history/result/cleanup.
- bridge.sqlite3: preserved local enrollment/pairing audit.

Final frozen relevant suite: 411 passed across 30 X1/native/mapping/workspace/WebBridge files.
Scoped Ruff and Node syntax/fixtures passed. Two existing Starlette/httpx and AnyIO deprecation
warnings remain. Artifacts: Runtime Data/TestRuns/x1_final_frozen_20260912_43e786f2.
Synthetic full integration covers coordinator → RuntimeAccess → native host → worker → router →
content → provider DOM fixture → persistence → orchestrator result. Regressions cover sibling/
ancestor proofs, ambiguity, measured bounds, expected-name mismatch, stale-module recovery,
ACK binding, private-value/write traps, observer/presence/revoke and cleanup. Broader tests ran
only after live Phase A passed. Synthetic fixtures are not vendor evidence.

## Files changed

- executors/ascend_extension: causal_trace.py, host.py, runtime.py, mapping_orchestrator.py,
  workspace_contracts.py, mapping_diagnostics.py.
- extensions/ascend-x1: runtime.js, tab-router.js, content.js, workspace.js.
- scripts: ascend_mapping_orchestrator.py, x1_browser_maintenance.ps1, check-x1-causal-ack.js,
  and affected existing synthetic worker/controller/lifecycle fixtures.
- tests: causal trace, session handoff, mapping reliability, section diagnostics, route-heading,
  sibling-form and integrated-path regressions.
- This handoff, CURRENT_STATE.md, KNOWN_ISSUES.md, DECISIONS.md, AGENTS.md and LIVE_POC.md.

The prepared causal-trace CURRENT_LOAD command was executed by the agent. It is not a retry
instruction. Future reads/navigation require a new separately scoped authorization.
