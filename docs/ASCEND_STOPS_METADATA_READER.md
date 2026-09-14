# Candidate Stops metadata reader

Implemented and connected in source to existing ASCEND_MAP_WORKSPACE capture. The source manifest
and packaged reinjection list load stops-metadata.js; installed files have not been updated.
There is no new command, grant, permission, value extraction or live deployment. No LIVE_VALIDATED
promotion. The existing section contract now accepts optional strict, fingerprint-bound Stops metadata.

The adapter consumes an exact-load ASCEND_MAP_WORKSPACE target for Edit Stops. It requires
the caller's existing synchronous authority guard, checks owner presence and a three-second
deadline, and reuses FreightDeskWorkspace.observeWorkspace/observeSection before and after
capture. Session/lease/enrollment verification remains the responsibility of the existing
authenticated command boundary; this module is not a substitute for it. The mapping capture calls the sensor after that boundary. Host validation rejects unknown/private
keys, wrong sections, invalid row references, bounds and fingerprint mismatches before the existing
append-only runtime_provider_maps store accepts the result.

Header labels determine column positions, not fixed indices. One visible candidate table,
eleven unique known headers and rectangular stop cells are required. Header clones, hidden rows,
unsupported action structures, ambiguous actual surfaces and wrong-cell containment fail closed.
One-cell details/summary rows are counted separately. Layout-visible off-viewport rows are included.
Limits: eight candidate tables, twenty body rows and twenty controls per row.

The output contains static column labels, action categories, counts, scheduled surface presence
and candidate Arrival/Departure class bindings. It does not read aggregate cell text, dates, notes,
addresses, control values, href values or provider row identifiers. Scheduled subtype stays UNKNOWN.
Rows have capture-local references, never stable provider identity; repeated pickups remain distinct.
Before/after physical node bindings and metadata must match. No DOM interaction is implemented.

External UI observations informed these candidate structures; no raw provider artifacts are in Git.
The fixture uses synthetic identities and private-value sentinels. External observations are not
extension receipts and do not prove general provider compatibility. Other action types, alternate
table layouts, localization and appointment semantics remain unsupported/unknown.

Validation: targeted synthetic Edge DOM tests plus existing workspace mapping and diagnostics tests.
All fixture networking is intercepted in a disposable context; no authenticated profile is used.
Initial standalone result: 53 tests passed. Integration adds actual synthetic browser capture
through runtime dispatch/result validation into the private test database, plus host tampering cases. The Stops adapter rejects the general mapper's heading-only fallback: selected
control or selected-route-and-heading proof is required.

Integrated verification: 66 tests passed across Stops, workspace mapping, diagnostics and the
existing integrated mapping path. After removing generic action-text scans for Stops, all 26 Stops
cases passed again with datetime-anchor text-access tripwires. Ruff, Node syntax and the persistent
runtime/lease/reinjection script passed. No installed component or real authority was changed.
