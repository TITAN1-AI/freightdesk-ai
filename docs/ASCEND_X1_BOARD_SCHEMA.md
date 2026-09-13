# X1 0.4.2 board schema diagnosis and correction

2026-09-11. Local evidence review and offline implementation only. No Ascend/vendor execution,
installed native-host invocation, lease enable, registry change, re-pair or detail attempt.

## What the failed live run actually recorded

Read-only SQLite review of
`C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\runtime.sqlite3`
at 22:33:23 UTC used a query-only transaction. The owner reports successful 0.4.1 lifecycle
recovery; local session/view receipts and 0.4.1 document handshakes support that observation.
This is separate from successful board-schema validation or proof of every recovery scenario.

The latest lease was issued at 22:28:38 UTC. Authenticated-session receipts at 22:29:36.211932
and 22:29:36.248979 precede an independently verified Active Loads view at 22:29:36.289838.
The board operation dispatched at 22:29:36.311619 and failed at 22:29:36.337089.
Its receipt timestamp is 22:29:36.336982, with `BOARD_SCHEMA_INVALID`.

**The failure evidence contains only the verified view contract. No grid/header/row diagnostic
or underlying schema predicate was persisted. The exact live defect cannot be reconstructed.**
Do not treat a synthetic reproduction as the missing live DOM snapshot.

| Requested fact | Evidence available for this failed read |
| --- | --- |
| Exact failed predicate | UNKNOWN; only BOARD_SCHEMA_INVALID retained |
| Header count | Not recorded |
| Data-row cell count | Not recorded |
| Required headers found/missing | Not recorded |
| Wrong grid selected | Not established |
| Fixed/header clone and data grid | Not recorded for this read |
| Hidden/responsive alignment change | Not recorded |
| Changed column labels | Not recorded |
| Incomplete initialization | Not recorded; short dispatch-to-failure time alone does not prove it |
| Material difference from earlier observed contract | Cannot determine without structural evidence |
| Selected provider view | ACTIVE_LOADS / VERIFIED |
| Pagination/page size | Not recorded |

Earlier `owner-table-schema-001` evidence, documented in ASCEND_ALL_LOADS_TABLE.md, observed
9 candidates, one 48-row data-bearing grid with 33 headers/cells, a header clone without data,
and page size 100. That is comparison evidence, not the current schema measurement.
The established schema has 31 named headers and two unsupported reserved columns. The old
snapshot's Load ID/Pick Date/Drop Date indexes were 0/5/7, not permanent semantic definitions.

Owner revoke is recorded at 22:31:43.150449 UTC. The lease is revoked, state STOPPED,
READ_LEASE_REVOKED, with the tab unbound. There is no successful board receipt in this lease.
The retained eight-row count/hash has last_board_sync 22:04:35.948090 from a prior lease and
remains LAST_KNOWN_BOARD_EVIDENCE. It is not a current observation.

## Deterministic local weaknesses and scoped correction

The previous runtime called the reader with empty boards allowed. The selector accepted an
empty tbody/header clone as a qualifying grid even when an actual data-bearing grid was present.
Both then competed, producing `data_grid_ambiguous`, which collapsed to BOARD_SCHEMA_INVALID.
Fixed positional and case-sensitive header comparison also differed from the older observed
contract's whitespace/case normalization. These defects are reproduced offline; neither is
asserted to have caused this particular live failure.

Source 0.4.2:

- Selects the unique visible, relevant data-bearing grid before considering an empty board.
  Header-only clones never compete with it. Multiple relevant data-bearing grids still stop.
- Maps all 31 named fields by normalized header meaning. Only whitespace/case normalization is
  accepted, not synonyms. All 33 headers/cells, unique required labels, span checks and explicit
  aria-column alignment checks remain enforced. ID/pick/drop reads use their semantic mappings.
- An empty tbody alone is not an empty-board proof. A unique schema-valid grid requires an exact
  provider-style DataTables empty marker. Those marker cases are fixture-tested, not newly live
  observed. Real unknown empty states remain stopped.
- Waits at most three seconds for two consistent structural samples, checking the lease and
  independent Active Loads view throughout. Persistent incomplete or conflicting schemas stop
  with the measured predicate; this is one bounded read, not a new lease or automatic retry.
- Records candidate counts, visible/data-bearing flags, canonical header labels, header visibility,
  header and row-width counts, complete required-header mapping, spans/alignment flags, busy/empty
  markers, render sample count and available page-size/next/previous control state.
  Unknown labels are UNKNOWN_LABEL, blank labels EMPTY_LABEL; no raw header strings or cell values.
- Uses explicit predicates such as AMBIGUOUS_DATA_GRIDS, HEADER_COUNT_MISMATCH,
  REQUIRED_HEADERS_MISSING, DUPLICATE_REQUIRED_HEADERS, ROW_CELL_COUNT_MISMATCH,
  ARIA_COLUMN_ALIGNMENT and INITIALIZATION_BUSY. Host duplicate-ID/hash failures have separate
  HOST_DUPLICATE_LOAD_ID / HOST_BOARD_HASH_MISMATCH predicates.
- Carries typed sanitized metadata through content result, host receipt, local status and audit.
  CLI, dashboard and popup expose schema_predicate. Missing older metadata is not backfilled.
  Strict allowlists reject arbitrary strings/extra fields. Oversized structural summaries omit
  candidates explicitly with metadata_truncated=true, retaining the selected candidate, measured
  total candidate count and failed predicate within the existing Native Messaging size limit.

No private row values are read for diagnostic metadata. Board execution still reads only its
existing ID/pick/drop fields. VISIBLE_BOARD_ONLY, independent view proof, proposal-only persistence,
provider versus OWNER_ATTESTED tenant distinction, enrollment and all write gates are unchanged.
No canonical mutation, operational detail extraction, pagination click or new field mapping.
The source build is 0.4.2 across manifest/worker/content/host; controller/content protocols remain
2/2 and Native Messaging protocol 1. No new permissions or transport architecture.

## Owner retry, prepared but not executed

The inspected lease is revoked; a fresh lease is required. No new detail attempt ID or read-plan
bootstrap is required for a board-only runtime lease. Leave the detail queue untouched.

1. From the project PowerShell directory inspect local status:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime status --owner-executed
   ```

   Expect revoked/disabled access. If an unrelated newer lease has been enabled, disable it
   before reloading/starting this bounded retry. Reload can resume an already enabled lease.
2. Reload the existing pinned unpacked X1 extension in Edge and verify version 0.4.2. Retain
   enrollment and the existing authenticated Ascend tab; do not re-pair or refresh the tab.
3. When ready for the owner-executed live boundary, enable a six-minute maximum board lease:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime enable --owner-executed --hours 0.1 --interval-seconds 60
   ```

4. After the first result, inspect status with the status command above. Success must include a
   **new** last_board_sync and CURRENT_VERIFIED_BOARD. If it stops, preserve error_code,
   schema_predicate and board_schema_diagnostic. No repeated enable or diagnostic attempt.
5. Disable after that result, successful or failed:

   ```powershell
   .\.tools\python\python.exe -B -m scripts.ascend_x1_runtime disable --owner-executed
   ```

Do not queue operational detail discovery during this board correction check. The earlier board
runtime LIVE_VALIDATED scope remains historical evidence; 0.4.2 compatibility is not live validated.
Operational detail mappings remain UNKNOWN / NOT LIVE_VALIDATED.

## Offline verification

Targeted fixtures cover empty header clones before/after the data grid, competing real grids,
reordered/case-normalized headers with identical semantic hash, mapped opener identity, hidden
columns, missing/duplicate labels, header/row spans, aria mismatch, missing cells, invalid/duplicate
IDs, explicit versus unverified empty boards, delayed initialization, persistent failure, pagination,
bounded structural output, private-cell read traps, content transport, popup predicate rendering,
strict host validation, receipt/audit/status persistence and retained-evidence separation.

The exact live mismatch has no fixture because its structural facts were never recorded. These
tests prove the correction's defined behavior, not compatibility with the currently open Ascend DOM.

The 254-test targeted regression set initially returned 253 passes and one stale pre-0.4.1
permission assertion. That assertion was corrected to the already-declared exact permission list;
the affected 22-test set then passed, including all new schema cases after the final diagnostic
size-bound adjustment. Thus all 254 targeted cases have passing results with the correction.
Ruff and JavaScript syntax checks passed. Existing Starlette/httpx and AnyIO deprecation warnings
remain. No full project suite or live vendor test was run. Browser/host fixtures used isolated
test directories and fulfilled requests under C:\FreightDeskRuntime\Data\TestRuns.
