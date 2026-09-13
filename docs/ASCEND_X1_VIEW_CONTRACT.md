# X1 0.2.1: independent load-board view identity

> 2026-09-11: The provider-view contract remains required in X1 0.3.0. The later owner request replaces
> the one-shot operating model with persistent enrollment plus a read lease. Current setup/first-live
> instructions are in [ASCEND_X1_RUNTIME.md](ASCEND_X1_RUNTIME.md). Do not create the old proposed -02
> grant as part of normal runtime migration. This document retains the original stop diagnosis.

Prepared offline on 2026-09-11. STOP before live execution. No Ascend interaction, re-pairing, new
bootstrap/read authorization, registry change or Native Messaging transport change occurred in this
task. The source update requires a future extension Reload; it has not been installed by this task.

## Failed first test: what the local evidence establishes

The existing sanitized `x1_read_events` and consumption ledger were inspected read-only under
`C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\bridge.sqlite3`.

| Event, UTC on 2026-09-11 | Sanitized result |
|---|---|
| 17:26:40 | `ASCEND_GET_SESSION_STATE` returned `READ_ONLY_READY`; authenticated app and verified extension pairing, one eligible tab, path `/loads` |
| 17:26:58 | `ASCEND_GET_ACTIVE_LOADS` returned `STOPPED / ACTIVE_VIEW_UNVERIFIED / UNKNOWN` |
| Entire attempt | `owner-x1-identity-1755-20260911-01` durably consumed; `production_writes=false`; no FIND or OPEN operation |

The old X1 check required exactly one visible control with literal Active Loads text and an active
attribute on that same element. It omitted direct parent `li.active` and `aria-current="true"`, both
already supported by the older board normalizer. This is a confirmed implementation gap, not proof
that either particular marker was present on the live page. Version 0.2.0 did not persist candidate
view evidence: the actual selected view, candidate count and specific missing/conflicting marker
cannot be recovered from this stop. The gate failed before operational board extraction; row counts
and 8/3 reconciliation are not established by this attempt.

The STOPPED response cancels the selected-tab content port/binding. A previous successful selection
therefore cannot be reused. This does not establish loss of the owner's Ascend login.

At the read-only audit check at 17:47:02 UTC, the last verified pairing (17:24:30 UTC) was beyond its
unchanged maximum ten-minute lifetime. The latest persisted pairing-attempt result at 17:28:38 UTC
was `PAIRING_ALREADY_CONSUMED`. The view failure itself does not unpair transport; nevertheless a
currently usable pairing cannot be claimed. No pairing material was opened or regenerated. A future
Reload also discards extension in-memory pairing. Renewal requires later owner authorization.

## Provider DOM contract

`AscendLoadBoardViewContract`, version 1, records `provider=AscendTMS`, `source=provider DOM`, resolved
view, confidence and safe candidate metadata. This is an implemented observation contract, not a
claim that the real page's selector/marker has now been observed. Version 0.2.1 needs one separately
authorized production observation before compatibility can be reported as LIVE_VALIDATED.

The extension recognizes these independent signals, outside operational tables, forms and dialogs:

- A known view control selected by `aria-selected`, `aria-pressed`, `aria-current` (`page` or `true`),
  allowlisted active CSS, or a direct active list/presentation parent with exactly one named control.
- A known, visible primary heading outside navigation, or a visible explicitly identified board
  container with a structural table/grid. Its private content text is not read for view identity.
- A known control with an unambiguous direct relationship to a uniquely visible provider tab panel.
  Bare links and shared panel references are insufficient.

Canonical labels are Active Loads, All Loads and Ready for Accounting. An unknown selected member
of a recognized board tab group, or an explicit unknown board identifier, is projected as `OTHER`;
its raw label/value is never persisted. Explicit contradictory labels, data identifiers, headings or
selection states yield UNKNOWN. Multiple selected controls also yield UNKNOWN.

Safe CSS identifiers are limited to `active`, `selected`, `is-active`, `ui-tabs-active` and
`ui-state-active`. Diagnostic candidates contain only kind, canonical label/view, visibility,
selection/relationship booleans, nullable aria booleans, allowlisted CSS and an approved data-view
enum. No raw data attributes, IDs, URLs, customer values, notes, HTML, cookies or tokens are retained.
The bound is 32 candidates; the 33rd records the exceeded category/count and stops.

The native host independently resolves the projected contract and rejects inconsistent confidence,
view, counts, version, unknown fields or private values. Existing signed native messages carry the
contract; the transport, pairing protocol, DPAPI and extension permissions are unchanged. Safe
contracts persist in the existing runtime read event on both success and failure.

| Provider result | Read behavior |
|---|---|
| `ACTIVE_LOADS / VERIFIED` | May proceed to the existing board/schema/oracle gates |
| `ALL_LOADS`, `READY_FOR_ACCOUNTING` or `OTHER / VERIFIED` | Report that actual view; stop with `ACTIVE_VIEW_NOT_ACTIVE_LOADS` |
| `UNKNOWN / UNKNOWN` | Stop with `ACTIVE_VIEW_UNVERIFIED` and a fixed diagnostic reason |
| View changes during a command | Stop with `ACTIVE_VIEW_CHANGED`, including a transient switch away and back |

Path `/loads`, load IDs, board membership and 8/3 counts cannot establish the view. Verification
precedes row access and is checked around asynchronous work and before a detail opener. A bounded
observer watches provider view controls/groups/relationships, not operational cell contents. The
existing policy, one-use release, document, board hash, exact-row and detail identity gates remain.
Successful identity still ends with operational extraction blocked. Tenant remains OWNER_ATTESTED.

## Authorization and next owner steps

There is no authorized live retry in this task. Do not run the historical 0.2.0 instructions or reset
the consumed ledger. Review this patch first. Before any future retry:

1. Obtain a separate owner release for the next test and any required pairing renewal. This handoff
   does not authorize a bootstrap, re-pair, browser interaction or Ascend request.
2. Once authorized, Reload the existing extension to 0.2.1 with the same pinned ID, refresh the intended
   existing Ascend tab, and explicitly select Active Loads. Reload means new in-memory pairing and a
   fresh selected-tab binding are necessary; do not re-register or rebuild the transport.
3. Confirm a verified pairing acknowledgement and explicitly select that eligible tab. The service
   date `2026-09-11`, US board date format and previously approved 8/3 membership must still apply;
   otherwise STOP and reconcile the scope rather than changing the oracle to force a match.
4. Only on that future owner execution, use the prepared local-only successor command below. It
   requires the local confirmation phrase and creates a new ten-minute grant, not a resumed grant.
5. Load that authorization, verify session once, then request Active Loads once. Review the persisted
   view contract and safe result before any further step. Stop on any error; no automatic retry or
   detail extraction. Do not advance to 1755 identity without the applicable owner release.

Proposed unused ID: `owner-x1-identity-1755-20260911-02`. No record with this ID was created. The
prepared successor path requires an explicitly named consumed `-01` whose last event is exactly the
reviewed `ASCEND_GET_ACTIVE_LOADS / STOPPED / ACTIVE_VIEW_UNVERIFIED` failure. It preserves all old
events/consumption, refuses implicit replacement and does not enable a third attempt.

Future command only; do not execute under this task's authorization:

```powershell
Set-Location -LiteralPath 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
.\.tools\python\python.exe -B -m scripts.ascend_x1_readonly prepare --owner-executed --attempt-id owner-x1-identity-1755-20260911-02 --service-date 2026-09-11 --supersedes-attempt owner-x1-identity-1755-20260911-01
```

## Offline verification

117 targeted tests passed across view, controller, DOM, extension and native-host suites. View
fixtures cover all ten requested cases, plus parent CSS/current-state restoration, accessible labels,
accounting/OTHER views, explicit data identity, panel relationships, conflicts, hidden titles, bounds,
privacy projection, host-forged proofs and append-only successor authorization. Forbidden board-cell
getters verify that an unverified/wrong view stops before manifest reads. Both persistent and transient
view changes fail closed. The synthetic pages are intercepted in isolated TestRuns profiles; the
owner's live profile is not opened. Two existing dependency deprecation warnings remain.

Ruff, changed JavaScript syntax, bootstrap isolation, popup pairing fixtures and signed X1
controller/tab-routing fixtures also pass. These checks do not run the installed extension or host.

No new view, board, detail or operational capability is LIVE_VALIDATED by these fixtures.
