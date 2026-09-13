# Native host startup diagnosis - 2026-09-11

Historical diagnosis below. The owner subsequently reported 0.1.2 PAIRED / PAIRING_SUCCESS, validating
local transport only. Current prepared work is [X1 read-only controller 0.2.0](ASCEND_X1_READONLY.md).
Do not repeat registry/rebuild/startup diagnosis as a prerequisite to that handoff.

Scope: local registration/manifest/launcher inspection, sanitized existing audit and isolated native
fixture tests only. No installed launcher execution, registry edit, bootstrap generation, pairing retry,
Edge launch or Ascend/vendor operation occurred. Installed extension remains 0.1.2; no extension files changed.

## Findings

Both HKCU Registry32 and Registry64 entries for com.freightdesk.ascend_x1 exist and point to the same:
`C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\host-manifest.json`.
The manifest exists, parses as JSON, names the expected stdio host and contains exactly the owner-provided
Edge extension origin, with no wildcard. The expected executable exists at:
`C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\FreightDeskAscendHost.exe`.
No registration change is needed. The older Register helper rejects a second registry-view entry;
do not rerun Register merely to rebuild this executable.

The runtime launcher source matches the pre-fix source template. Its executable contains the expected
project Python and working-directory strings. The project path with spaces and Python both exist;
ProcessStartInfo uses a separate executable path, fixed arguments and explicit working directory,
UseShellExecute=false, fixed runtime root and runtime TEMP/TMP. Required native-host imports succeeded
locally with zero stdout bytes, zero stderr bytes and zero warnings. No moved paths or missing-module
defect was found. Test-runner dependency warnings are separate from native-host startup output.

The actual pairing_attempts audit's latest HELLO sequence at 2026-09-11T16:05:28Z reached:
NATIVE_CONNECT -> DPAPI_VALIDATION -> ONE_TIME_VALIDATION, with extension_id_match=true,
bootstrap_expired=false and bootstrap_consumed=false. The generic audit recorded PAIRING_REQUIRED.
No proof-validation or pairing-persistence stage is recorded in the examined diagnostic history.
The durable consumed-pairing count is zero. Thus the host did start, read requests, and pass these gates;
the failure was not established as missing registration, startup failure or rejected pairing proof.

## Deterministic relay defect and evidence limits

The existing C# launcher used CopyTo on redirected streams without flushing incremental writes.
A controlled compiled fixture could not receive a small response while stdin remained open. The same
fixture, Python, paths and two-message protocol work when each relay write is explicitly flushed.
The regression test retains the old CopyTo behavior and demonstrates the timeout without pipe EOF.
The fix is a small binary relay loop with Flush after each write in both directions.

This is a reproduced local defect consistent with HELLO processing at connection teardown and no
follow-on proof. The installed launcher has not been rebuilt or retested here. Old audit did not record
frame receipt/output checkpoints, so it cannot independently prove the exact failure point in Edge's
particular attempt. Classification: F for the unobserved response/proof transfer, with positive evidence
that the host started and accepted HELLO. Do not label A/B/C/D/E as proven from the old generic popup.

## Startup diagnostics

The updated launcher writes startup-launcher.jsonl and the Python entry point writes startup-python.jsonl
under the existing ascend-native runtime directory. Each row has only timestamp plus startup_stage,
safe_error_code, exception_type, launcher_started, python_started, host_initialized and
first_message_received. Codes/stages and exception categories are fixed, never raw exception text.
Launcher checkpoints report the stages it directly observes; its host/read flags remain false until
those stages are observed by the Python recorder. They do not negate later Python checkpoints.

Python records entry, binary stdio, imports, host initialization, first message, generated/flushed
response and safe failure/EOF. Import-time stdout/stderr/warnings are suppressed, with a safe marker if
noise occurred. Neither banners, warnings nor tracebacks enter native stdout. C# keeps binary protocol
stdout separate and discards raw child stderr. If the runtime cannot accept a startup record, only the
fixed STARTUP_DIAGNOSTIC_UNAVAILABLE marker goes to stderr; persistence cannot be promised when storage
itself is unavailable. No proof, secret, token, blob, frame, cookie or provider data is recorded.

## Owner-run rebuild and local self-test - prepared, not executed

Keep the existing ID, manifest and registry. Disconnect/close the pairing panel so the executable is
not in use, then run:

```powershell
Set-Location -LiteralPath 'C:\Users\titan\OneDrive\Documents\ChatGPT\FreightDesk AI'
powershell.exe -NoProfile -File .\scripts\ascend-native.ps1 -Action RebuildLauncher -OwnerExecuted
.\.tools\python\python.exe -B -m scripts.ascend_native_selftest --owner-executed
```

RebuildLauncher validates the existing manifest/paths and compiles to the existing executable path;
it exits before registry access and never resets pairing. The existing Register/Uninstall behavior
is unchanged. No extension Reload is required for this host-only patch. A native connection restarted
after rebuild uses the new executable/Python module.

The self-test launches the registered-path executable with an owner-only --self-test process flag.
It validates current Windows/runtime installation and exact extension binding, then permits exactly
one synthetic SELF_TEST_PING -> SELF_TEST_PONG exchange. It does not read the bootstrap/DPAPI key,
claim pairing, consume any grant, call Edge, open a socket or invoke a vendor. The normal native
connection does not accept SELF_TEST_PING. Native commands cannot activate the process flag.

The parent keeps stdin open until it receives a valid response so closing the pipe cannot hide the
old buffering problem. It checks framing, exact safe response, process exit and trailing stdout.
Success is status=PASS, safe_error_code=SELF_TEST_OK, framing/stdout checks true and production reads/
writes false. Failure is a fixed SELF_TEST_* code, never raw frames or stderr. On timeout it cleans up
only the launched test process. Startup audit distinguishes missing process, import failure, no first
message, rejected request and response generation/flush.

After running the self-test, STOP and report its sanitized result. Do not generate another bootstrap
or retry pairing yet. A later controlled pairing retry should use a fresh bootstrap after self-test
success and owner release; zero consumption in the old audit does not extend the ten-minute expiry.
READ_ONLY_READY, Ascend reads/writes and operational extraction remain blocked.

## Offline checks

46 targeted native-host tests passed; three unrelated browser/crypto tests excluded. Covers original
relay timeout versus flushed interactive frames, executable/working paths with spaces, the compiled
launcher plus actual Python entry point with injected fixture identity, exact-origin rejection,
synthetic ping, early exit, malformed/contaminated stdout, import failure/noise suppression, stderr
isolation, safe startup fields and unchanged pairing/read denial. Tests use only TestRuns fixture
executables and injected repositories, never the installed host or a real pairing package.
Scoped Ruff and PowerShell syntax passed. Two existing test dependency warnings remain.

Changed: scripts/native_host_launcher.cs, scripts/ascend_native_host.py, scripts/ascend-native.ps1,
executors/ascend_extension/host.py. Added: executors/ascend_extension/startup.py,
scripts/ascend_native_selftest.py, tests/test_ascend_native_startup.py and this handoff.
