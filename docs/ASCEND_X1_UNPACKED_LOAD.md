# Load unpacked Ascend X1 (0.6.2)

This is the current offline handoff for making the V1 MV3 package load in Edge or Chrome.
It does not authorize live Ascend reads, a new lease, native-host registration, or any write.

V1 remains the packaged default. WebBridge V2 stays out of `extensions/ascend-x1/manifest.json`
(TestRuns/fixture gated, OBSERVE-only). Field maps remain CANDIDATE_ONLY. Wizard New Load and
production CarrierView writes stay unavailable.

## Load unpacked in Edge or Chrome

1. Open `edge://extensions` or `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked**.
4. Select the folder `extensions/ascend-x1` that contains `manifest.json`.
5. Confirm the toolbar popup shows version **0.6.2**, production connection disabled, and
   CANDIDATE_ONLY / Windows-only native-host copy. There must be no manifest or icon error.

Keep using this same folder path if you already have a pinned install. Moving the folder can
change the unpacked ID. Branded Chrome 137+ no longer honors `--load-extension` on the command
line; use the extensions page (or Chrome for Testing / Chromium if you need automation).

Do not copy a browser profile, enrollment handle, pairing file, or runtime database into the
extension directory.

## What works after a clean unpacked load

- MV3 service worker, popup, and isolated content scripts load.
- Content scripts inject only on `https://ascendtms.com/*`, top frame, isolated world.
- The popup and worker stay dormant: `PRODUCTION_CONNECTION_ENABLED=false`.
- On non-Windows browsers the worker reports `HOST_NOT_REGISTERED` /
  `NATIVE_HOST_WINDOWS_ONLY` and does not call `connectNative`.
- On Windows without a registered host, **Check local host** reports `HOST_NOT_REGISTERED`.

No vendor page is opened by loading the extension.

## Native host (Windows-only)

Authenticated pairing, enrollment, and Ascend reads need the local native messaging host:

| Item | Value |
| --- | --- |
| Host name | `com.freightdesk.ascend_x1` |
| Executable | `FreightDeskAscendHost.exe` |
| Typical registration | `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.freightdesk.ascend_x1` |
| Historical pinned unpacked ID | `opckmnldaebecjphbmdmelfflikinpif` |

The host is Windows + DPAPI + a host-side allow-list of that exact extension origin. Linux and
macOS can load the unpacked package for source review; they cannot complete enrollment or reads.
This repository does not include a public `key` field, so a fresh unpacked load generally gets a
new ID. Native messaging then requires the host manifest `allowed_origins` to match that ID, or
the existing pinned Edge install must be reloaded in place.

Do not register the host, rebuild the launcher, or enable a read lease from ordinary coding work.
See [ASCEND_NATIVE_MESSAGING.md](ASCEND_NATIVE_MESSAGING.md) and
[ASCEND_NATIVE_STARTUP.md](ASCEND_NATIVE_STARTUP.md) for the Windows owner path.

## Remaining Windows-only gaps

- Native host binary, registry registration, and DPAPI enrollment are not available here.
- A new unpacked ID will not match a previously pinned host allow-list.
- Edge vs Chrome use separate native-messaging registry views; the historical pin is Edge.
- Alarms, tab routing, and mapping leases still expect the Windows FreightDesk host.
- Installed-extension lifecycle, real Ascend DOM, and V2 live packaging remain out of scope.

## Offline checks

```text
node scripts/check-ascend-x1-package.js
node scripts/check-ascend-extension.js
node scripts/check-ascend-native.js
```

These checks do not launch a browser, register a host, or contact Ascend.
