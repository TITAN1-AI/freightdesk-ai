# X1 0.6.3 installed — workspace validation pending

Owner authorized the daily-operations validation plan on 2026-09-13. After the initial policy block,
the owner manually disabled Smart App Control and confirmed "off". Local policy state0 was verified;
the agent did not change Windows security policy. The staged candidate passed its one-time synthetic
check, the native host was installed, and the existing pinned extension reloaded0.6.3. Fresh worker
wakes and local pairing/reconnect work with reads REVOKED. No new Ascend read or mapping grant yet.

Staging completed from source commit `5031e49`: 201 source/config hashes verified, signature NotSigned.
Candidate execution is PASS / SELF_TEST_OK, including Python startup and native framing. Its receipt
is consumed: do not rerun check-candidate. Installed native SHA256 is
`5043d3e63395c8c944ae54927b6127e3da9989d138e4cb5e13f7be552f8646db`.
Private candidate-selftest.json and installed.json receipts exist under the release directory.
No executable artifact or runtime evidence was published to GitHub.

The first replacement returned RELEASE_FAILED while the old idle installed host was running.
Both files were verified restored to their prior hashes, with no pending files or install receipt.
After rechecking unrelated authority idle and stopping only that exact installed host process,
the unchanged guarded install succeeded. This is consistent with an executable lock; the first
generic error did not retain the OS exception and is not claimed to prove an exact WinError.

The approved browser-chrome helper reloaded the pinned0.6.3 card. Compatible worker wake validation
and transport freshness succeeded; the saved content handshake is still historical0.6.2. The router
establishes fresh content proof only within scoped read authority, before mapping dispatch. Do not
misrepresent the host's build projection or an extension card as a fresh content receipt.
FocusAscend stopped LOCAL_BROWSER_TAB_AMBIGUOUS:9 tab controls,0 Ascend-labelled candidates and
1 Extensions manager. Unrelated titles/URLs were not printed. Owner was asked to foreground exact
1763 / Load Basics. No job or lease was created. This is an availability/selection gate, not evidence
of failed Ascend authentication. No provider selectors or safety gates were changed.

## Historical inspection and policy blocker

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

Post-policy-change targeted run:27 release/integrated cases passed, including every V1/V2 synthetic
chain variant. The separate reproduction of the failed CI V2 case also passed. Candidate native
execution passed independently on this PC. A27-file source recovery rehearsal under TestRuns
restored the saved extension/Python build0.6.2 hashes and both native files without touching any
installed files or authority. This is source/native recovery evidence, not live rollback qualification.

CI run34776663983 at192fcf9 returned986passed/1failed. The failure was the V2 synthetic integrated
path at the second mapping-session notification: NATIVE_RECEIPT_FAILED. Its exact cause is not
persisted and remains UNKNOWN. The production native serve loop serializes responses/notifications;
the test uses an asynchronous fixture bridge, but a fixture-ordering cause has not been proved.
Do not call this CI run passing or silently attribute it to provider behavior. V2 remains disabled.

Earlier verification:

The initial targeted run returned 72 passed / 3 failed. All three failures were matched to Windows
policy blocks; this run is not represented as passing. The native-launcher suite was not repeated
locally. Later source-only release/orchestrator/causal-trace/integrated tests passed 72 cases,
including 19 release tests, before the final receipt-write regression was added. Final results are
recorded in CURRENT_STATE.md: 73 distinct cases across the integrated run and final 20-test release
run. Full repository Ruff and X1 controller/runtime Node checks passed.
Two existing Starlette/AnyIO deprecation warnings remain.

The existing GitHub offline workflow may validate synthetic native binaries in its disposable
Windows runner. That never authorizes execution on this PC or resolves its local Windows policy.
No runtime artifacts or credentials are uploaded. Prior 967-test CI success belongs to the earlier
commit and cannot qualify this release.

## Resume procedure and remaining gates

1. Do not repeat completed candidate execution or installation. Preserve their receipts and the
   historical denied fixture attempts. Signing remains a separate future release decision; changed
   executable bytes require a new reviewed artifact manifest. No indirect policy evasion is allowed.
2. Resolve the exact foreground workspace with the owner. Verify source/installed hashes and no
   unrelated authority. Keep existing enrollment/profile and permissions unchanged.
3. Local transport is connected; a fresh content/worker document handshake must still be established
   by the normal router preflight under the bounded job lease, before any metadata capture. Never
   reuse the retained0.6.2 document receipt as current proof.
4. Start a fresh exact LOAD 1763 / Load Basics metadata job through the existing
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
