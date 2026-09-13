# X1 0.6.3 release preparation — Windows execution blocked

Owner authorized the daily-operations validation plan on 2026-09-13. Preparation remains at the
installed-release gate. No new Ascend read, mapping grant, extension reload or installed native-host
replacement has occurred. The code on disk advertises 0.6.3; the inspected loaded extension card
still showed 0.6.2. Do not treat these as a coherent deployed release.

## Actual inspection and blocker

The pinned extension and Native Messaging manifest bindings match the existing installation.
The latest local lease is revoked/expired, no pending read or active mapping job was found, and
historical evidence was preserved. Browser-chrome maintenance opened the Extensions manager in
the existing Edge window and verified the pinned 0.6.2 card. It did not inspect Ascend DOM.

Three newly compiled **synthetic test launchers** were denied before process startup. One surfaced
Windows error 4551; two were hidden by the self-test's generic HOST_UNAVAILABLE response. Local
CodeIntegrity events match all three fixture paths: event 3077, policy VerifiedAndReputableDesktop,
status 0xc0e90002. The policy-state value is 1. These are enforced Windows execution denials, not
failed Ascend authentication, mapping or Native Messaging protocol evidence. No blocked file was
retried after the denial was identified.

The safe local receipt is `application-control-block.json` under
`C:\FreightDeskRuntime\Data\Development\X1Releases\x1-0.6.3-20260913`.
It records only fixed policy/error metadata, timestamps and synthetic fixture identifiers.
Raw Windows events, browser state, enrollment material and provider values are not copied to Git.

Microsoft identifies 3077 as an enforced-policy block. Smart App Control has no per-application
override. The proposed deployment solution is a trusted RSA code-signing certificate/service,
followed by Windows signature validation and a separately reviewed signed-artifact manifest.
No signing account, paid service, trust-store exception or machine security change was created.
[Windows event definitions](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/operations/event-id-explanations),
[Smart App Control FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions),
[supported code signing](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control).

## Implemented release safeguards

- Extension, worker, content and Python build identity now agree on source version 0.6.3;
  controller/content revision 3 and native protocol 1 remain unchanged. V2 is absent from the
  manifest. Exact Ascend host scope and extension permissions are unchanged.
- `scripts.x1_release prepare` compiles/hashes a candidate without executing it. The manifest
  identifies executable source files, project Python, prior/candidate native files and build tuple.
  A clean committed source tree and unchanged existing installation/backup are required.
- `verify` checks artifact integrity only. It does not establish executable trust, successful
  startup, installed version, extension handshake or provider behavior.
- `check-candidate --owner-authorized` is a separate synthetic process boundary. It reserves a
  one-time receipt before dispatch; a denial, failure or crash cannot silently retry. Installation
  requires an exact candidate-hash-bound successful synthetic receipt.
- Host replacement checks unrelated jobs/leases without changing them, rejects unexpected file
  changes and uses a same-directory atomic replacement. A locked executable causes recovery of
  only this updater's launcher-source change. Receipt-write uncertainty has an explicit safe code
  requiring installed-hash inspection.
- `rollback-host` covers the two native files only. It is **not** a full extension/Python release
  rollback. The pre-update source snapshot is preserved, but was not a live-qualified release.
  Do not restore databases or old authority, or advertise full installed rollback qualification.
- Native self-test now returns `SELF_TEST_APPLICATION_CONTROL_BLOCKED` for error 4551, without
  raw exception text. Other OS errors remain generic and are not mislabeled as policy denials.
- Browser maintenance can open only the fixed local Extensions manager and validate an explicit
  expected card version. Reload/focus use existing pinned browser-chrome controls; provider reads
  remain exclusively inside X1. No browser profile is created or copied.

## Verification

The initial targeted run returned 72 passed / 3 failed. All three failures were matched to Windows
policy blocks; this run is not represented as passing. The native-launcher suite was not repeated
locally. Later source-only release/orchestrator/causal-trace/integrated tests passed 72 cases,
including 19 release tests, before the final receipt-write regression was added. Final results are
recorded in CURRENT_STATE.md. Full repository Ruff and X1 controller/runtime Node checks passed.
Two existing Starlette/AnyIO deprecation warnings remain.

The existing GitHub offline workflow may validate synthetic native binaries in its disposable
Windows runner. That never authorizes execution on this PC or resolves its local Windows policy.
No runtime artifacts or credentials are uploaded. Prior 967-test CI success belongs to the earlier
commit and cannot qualify this release.

## Resume procedure and remaining gates

1. Establish a supported signing/trust path for the native host. Do not disable Windows protection,
   rename/repackage a denied binary to evade policy, or execute it indirectly. The unsigned staged
   candidate is review material, not a deployable signed release. Signing changes its hash: prepare
   a reviewed final manifest for the signed bytes before any execution or installation.
2. Confirm no unrelated authority is active; verify source/native artifact hashes. Run one recorded
   synthetic candidate check only after the Windows prerequisite is resolved. If denied, stop and
   preserve the consumed receipt.
3. Review coherent extension/Python rollback and controlled native replacement. After replacement,
   reload the existing pinned extension and prove actual worker/content/build/protocol handshakes
   and local transport while provider reads remain disabled. A card version alone is insufficient.
4. Only then start a fresh exact LOAD 1763 / Load Basics metadata job through the existing
   MappingOrchestrator. Fresh session, foreground presence, tab/document/lease/runtime bindings and
   provider identity must agree. Stop on ambiguity, record one CANDIDATE_ONLY map with values=false,
   and complete job-owned cleanup. Do not revive any closed attempt or infer current load identity.
5. Continue the [daily-operations plan](ASCEND_DAILY_OPERATIONS_VALIDATION_PLAN.md) only as its gates
   are proved. General Mapping Mode/AUTO_MAP, operational values, other views and daily reliability
   remain unvalidated. All provider mutations, communications and canonical writes stay disabled.

Read-only local package inspection after staging:

```powershell
.\.tools\python\python.exe -B -m scripts.x1_release verify
```

This command is not a live validation. Do not run install-host/check-candidate or enable a mapping
lease merely because artifact verification passes.
