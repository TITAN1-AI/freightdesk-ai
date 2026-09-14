# X1 0.6.4 Stops release preparation

Source preparation only until runtime receipts say otherwise. No LIVE_VALIDATED claim.
Version 0.6.4 binds extension/worker/content/host expectations to the candidate Stops metadata
schema. Protocol revisions and permissions are unchanged. The one-use release directory is
x1-0.6.4-20260914; never reuse 0.6.3 candidate execution or installation receipts.

The exact owner entry now accepts Edit Stops as well as Load Basics, with an expected load ID
required for either. It does not authorize section navigation. Existing session, identity,
presence, lease and cleanup gates apply. The intended first live capture is exactly the
owner-opened LOAD/1763 / Edit Stops, metadata only. Operational values remain excluded.

Before deployment require green current-source offline checks, idle authority, verified candidate
artifacts and successful candidate self-test. Use existing x1_release and browser maintenance
helpers; stop on policy denial, ambiguous browser/workspace or unrelated authority. No policy
bypass, re-enrollment or historical receipt reset.

Prepared bounded command (not a receipt of execution):

```powershell
.\.tools\python\python.exe -B -m scripts.ascend_mapping_orchestrator start --scope CURRENT_LOAD --expected-load-id 1763 --starting-section "Edit Stops" --minutes 3
```

Initial release tests: 92 passed (Stops/release/orchestrator/causal trace). Current CI and local
release status must be checked separately; tests do not establish installed/provider readiness.
