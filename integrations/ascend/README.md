# ascend adapter

IMPLEMENTED: AscendAdapter, typed DOM/source contracts, deterministic AscendBrowserAdapter,
exact account/load read gates and separately blocked production write interfaces.
TESTED: offline synthetic DOM, real headless browser fixtures, policy/ledger/reconciliation/dashboard.
LIVE_VALIDATED: NO for M4B. M4A historical-export validation is a separate capability.

Supported customer API access is unverified. Prefer official API if confirmed; otherwise use bounded deterministic DOM reads and verified writes. Manual login belongs to the owner.

No real selectors or API URLs are invented. See docs/ASCEND_ACCESS.md for first-boundary owner steps
and docs/ASCEND_CONTRACT.md for private schema/operation contracts. Production writes cannot execute.
