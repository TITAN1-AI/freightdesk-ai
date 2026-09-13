# playwright executor

BrowserExecutor implements the deterministic DOM protocol in executors/interfaces.py.
IMPLEMENTED / TESTED: accessible selectors, bounded fallbacks, waits, safe errors, dedicated persistent
session lifecycle and strict read network routing. Real headless Edge tests use synthetic intercepted
HTML only. No production Ascend profile/navigation has been exercised. LIVE_VALIDATED: NO.
FreightDesk owns state, policy and audit. Verify exact identity, expected state, authorization
and deadline; writes must be reread and verified. Never store browser state in Git.

No automatic browser startup from the dashboard. RuntimePaths protects Avery's dedicated profile.
The optional broad BrowserJobExecutor/ComputerExecutor interfaces remain future orchestration;
M4B uses adapter-owned bounded reads rather than arbitrary browser jobs or visual coordinate control.
