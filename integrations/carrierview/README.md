# CarrierView adapter

IMPLEMENTED: six documented GET methods; native create, edit, disable, chat, SMS and three
webhook registration methods; typed source-preserving mapping and explicit response selectors.
TESTED: MockTransport and durable ledger/identity/error/credential tests.
LIVE_VALIDATED: tenant profile, past list, selected historical detail, last-position retrieval and
first history page only, plus owner-reconciled historical import/display. See LIVE_POC.md.

All production writes are blocked. Read networking additionally requires verified HTTPS origin,
official ResponseContract mapping and owner authorization. Tenant is the explicitly configured service identity with the owner's reason, distinct audit and
no fallback. Agent real API execution is blocked.

The owner-supplied summary establishes routes/auth/success/errors but omits response envelopes
and several nested field/write-body shapes. Fixture payloads are synthetic engineering examples.
See docs/CARRIERVIEW_CONTRACT.md, docs/CARRIERVIEW_ACCESS.md and KNOWN_ISSUES.md.

CarrierView documents/POD API is unsupported/unknown. Local webhook receiver is a separate
normalized quarantined inbox, not a verified vendor wire/signature implementation.
