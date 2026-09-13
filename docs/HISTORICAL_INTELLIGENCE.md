# Historical freight intelligence foundation

M4A actual source is committed under the owner's source/mapping/USD approval. Schema inspection,
staging, Decimal reconciliation, historical commit, idempotent re-import and provenance-backed
customer/lane/carrier/facility profiles and internal financial distributions are validated for this CSV.
No Ascend API, browser scrape, model training, live shipment update or Graph networking occurred.

## Actual Ascend CSV — original proposed mapping, now approved for historical commit

File: `ascend_loads_export_8XAPybttM7vDrSQpdiVYVF_20260908044312.csv` in the approved inbox.
SHA-256: `af7e479a94f44f7f7541e2ecdd725de48e37656f2a0da92085670e16d0886bb0`.
694 rows, 59 columns, 694 unique Load IDs. Pickup dates: 2024-09-03–2026-09-04;
created dates: 2024-08-28–2026-09-03. 19 raw customers, 354 carriers, 14 equipment labels.
110 raw city/state lanes; proposed trim/casefold grouping gives 109, without rewriting raw values.

Run `python -m scripts.stage_ascend_history <filename>` only for authorized local staging.
It reads actual headers before constructing an `AscendSchemaMapping` with PROPOSED status bound to
the source hash. The command has no commit flag or commit implementation. Use this M4A workflow
for the real export, not the older generic fixture mapping described later in this document.

| Observed source | Proposed historical evidence |
|---|---|
| Load ID | source_load_id string, original reference retained |
| Customer / Carrier | Exact raw identities; no destructive normalization |
| Carrier MC Number / Carrier USDOT Number | Exact strings, including prefixes/leading zeros/whitespace; quality flags separate |
| First Pick / Last Drop location columns | Structured name/address/city/state/postal/country and source date/time |
| Pickups / Deliveries / All Stops & Actions | Full private raw multi-stop evidence; first/final endpoints do not replace intermediate stops |
| Equipment / commodity / weight / mileage | Raw equipment and typed optional numeric evidence; no inferred weight unit |
| Drivers / Power Unit / Trailer / References / Notes / Private Notes / Status / Branch | Typed private source evidence, not canonical operational updates |
| Load Created Date | Aware ISO source timestamp; not a substitute pickup/delivery time |
| Total Income / Total Expenses | historical_total_income / historical_total_expenses; carrier pay remains unknown |
| Gross Profit/Loss / Gross Profit/Loss % | Separate source Decimal values; verify income minus expenses and two-decimal percentage |
| Exchange Rate Date | Raw source metadata only; no financial/event/payment/FX-effective semantics |
| Other / empty columns | Preserved in raw_source; no invented values |

Financial totals from staged values and an independent CSV pass both reconcile to income
1,693,484.10, total expenses 1,378,557.00 and gross profit 314,927.10. All 694 row checks pass.
Exported margin percentage matches `gross / income * 100` rounded to two decimals, ROUND_HALF_UP.
Aggregate margin is `sum(gross) / sum(income) * 100` = 18.596401%, not a mean of percentages.
The source uses dollar symbols. Owner confirmed USD at commit; this is separate owner provenance.
Original staged currency remains null; each committed wrapper records USD and its approval hash.

## Source limitations retained

One Completed row lacks a delivery date. Pickup fields have 671 local date-times and 23 date-only
values; delivery has 670 local date-times, 23 date-only values and one missing. No local timezone
or midnight event is invented. Delivery coverage is 2024-09-03–2026-09-08. All 15 expected empty
columns are empty; Exchange Rate Date is populated throughout without corroborating FX fields.
MC has 553 numeric-prefixed strings (533 leading-zero portions), 139 prefix-only placeholders and
two empty values. One MC and four DOT values include whitespace; DOT has two empty values.
There are 144 rows with identifier review warnings, zero invalid dates/money fields and no duplicates.

RawCustomerIdentity / ProposedCustomerAliasGroup / ApprovedCustomerIdentity are distinct models.
The proposed Tube Supply group has three raw labels totaling 326 loads (295 + 26 + 5); none merged.
Equipment proposals retain all 14 raw labels and propose family, length and Air-Ride features.
Flatbed/Step Deck remains an alternative, not a forced single equipment class. Unknown length stays unknown.

A bounded deterministic review of the first 50 Tube Supply loads, at most 4000 characters per
Notes/Private Notes field, found QuickPay keyword evidence on 49 distinct loads. Source offsets,
load IDs and hashes support private review. This is a proposed topic, possibly boilerplate/negated,
not a verified commercial term or approved SOP. No notes were sent to a model or printed.

## Stage storage and approval

Only `C:\FreightDeskRuntime\Data\booking-logistics\history\history.sqlite3` is opened by the stager.
`ascend_stage_batch` and `ascend_stage_row` hold one batch / 694 rows. Repeating the identical CSV
does not duplicate evidence; changed source evidence creates a separate REVIEW_REQUIRED version.
Source/hash/mapping provenance is retained, and all original raw columns remain private. The stager
never commits history. The separate approved committer wrote 694 ascend_history_record records only;
neither path writes generic history_record, canonical shipment, mail proposal or scheduler records.
Structural/financial/control failures yield rejection/quarantine; no commit path bypasses that result.

Review artifacts are under runtime history/reports/
`090676423701034e909dc695d1920546c7c410b4697877c799141aebee0a81d4`:
`staging-report.md`, `staging-report.json`, `proposed-mapping.json`.
The report includes all 59 columns, completeness, counts, validation, aliases and equipment proposals.
Private notes/driver contacts/addresses/raw record payloads are excluded from the owner-facing Markdown.

Owner approved the hash-bound mapping, USD, neutral expense semantics, unknown dates/identifiers/raw
metadata retention and all 694 rows for historical-only commit. AscendHistoricalCommitter re-reads and
compares source/mapping/row evidence against staging and commits atomically. Changed source versions
require separate owner reconciliation and are never silently overwritten. Exact re-import creates no
record or audit change. SQLite backup and approval receipt stay in private history storage.

Post-commit output includes 19 CustomerProfile, 110 LaneProfile, 354 named CarrierProfile, 163 exact
endpoint FacilityProfile, one RateHistorySummary and 14 equipment usage groups. Two missing carrier
and seven missing equipment rows have separate evidence contexts. Every group contains sample size,
pickup-date coverage, calculation timestamp, raw/derived designation and source-row/hash references.
Facility identity uses exact raw name/address/city/state/postal/country; addresses are omitted from
the report, identity hashes distinguish colliding display names. Intermediate stops are not inferred.

Financial distributions use Decimal min/P25/median/P75/max/mean, with linear interpolated quantiles.
Source row margins are percentage points; aggregate margin is a ratio of sums. No carrier-pay mapping,
market-rate claim or quote automation exists. All named customer distributions are shown in Markdown;
full carrier/lane profiles and evidence sets are in JSON. Bounded per-customer keyword topics remain
unverified candidates, possibly boilerplate or negated. No customer SOP is approved or applied.

New report artifacts in the same batch folder: historical-intelligence.md, historical-intelligence.json,
commit-verification.json. Original staging artifacts remain the pre-approval record. The approved command
was `.tools/python/python.exe -m scripts.commit_ascend_history ascend_loads_export_8XAPybttM7vDrSQpdiVYVF_20260908044312.csv m4a-owner-694-usd.json`.
Do not reuse the approval for a different export or expand it to operational/vendor work.

252 tests pass, with Ruff and JavaScript checks passing; synthetic coverage includes malformed values,
financial controls, source-to-stage mismatches, mixed date precision, idempotence/conflicts, private report
redaction, identifier preservation, separate identity proposals and bounded note review. Additional tests
cover approval/hash tampering, atomic commit rollback, immutable re-import, version rejection, private
backup and evidence-backed profile/distribution generation. Changed real-export behavior is unvalidated.

## Earlier generic fixture foundation

Owner-provided CSV/XLSX exports belong in
`C:\FreightDeskRuntime\Data\booking-logistics\history\inbox`.
`AscendHistoricalImporter.read_export` inspects actual headers and hashes the file. The next step
requires an explicit `SchemaMapping` identifying real columns, date formats, currency and reviewer.
No Ascend column names are assumed. CSV input is bounded to 20 MB/20,000 rows/100 columns;
XLSX is one worksheet, bounded expanded size, no formulas, macros or external links. No content executes.

`stage` normalizes typed optional freight fields and quarantines invalid rows. Missing values stay
missing. Dates need ISO or a reviewed explicit format; rates use finite Decimal values and known
currency. Conflicting stated margin is invalid. `commit` requires an owner identity and writes only
the separate historical store: `...\history\history.sqlite3`. Never point this importer at a live store.
Each record retains source system, source identifier/load ID, hash, version, import timestamp and
normalization status. Available source dates remain in the data; original_timestamp is nullable,
not invented. Changed versions of the same source load remain REVIEW_REQUIRED; they do not overwrite
prior evidence. Exact duplicate rows are not counted twice. Import counts are audited.

`HistoricalIntelligence.query` supports structured customer, lane endpoints, equipment, carrier,
MC/DOT, facility, reference and pickup-date filters. `profile` produces typed CustomerProfile,
LaneProfile, CarrierProfile or FacilityProfile records with sample size, covered dates, source IDs,
calculation timestamp, field frequencies and rate summaries. Customer revenue, carrier pay and
gross margin have currency-separated min/median/average/max and per-metric sample counts.
Derived margin is explicitly computed from available revenue/cost; it is not a provider assertion.
Empty evidence yields unknown statistics. These are internal historical observations, not current
market quotes, customer commitments or proof of carrier reliability/seasonal patterns.

Customer note phrases require evidence from at least three distinct loads before becoming a
ProposedCustomerRule. Owner approval creates a separate ApprovedCustomerRule with provenance.
There is no automatic SOP activation, policy change, scheduling or pricing action.

No fine-tuning or full-database model context. Retrieval is deterministic and scoped; embeddings,
semantic retrieval, retention policy automation and production schema mappings are future work.
The real-source workflow above supersedes the old next-step request to obtain an export. Do not
manufacture history from the single CarrierView POC or reuse generic carrier-pay assumptions for Total Expenses.
