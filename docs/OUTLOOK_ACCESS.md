# Microsoft 365 access — M3 owner handoff

LATEST prepared POC002 gap-only owner command is documented in POC_002_MULTI_SYSTEM.md. No networking
was performed here. After exact Ascend/CV phases, at most 8 load-specific searches/10 messages each plus
one /me check; no attachment/draft/send/scope expansion. Silent auth only, stop for manual login.
Correlated mail findings remain review-required proposals and never mutate canonical/verified facts.

Status: the owner confirms Microsoft bounded live validation completed successfully: OAuth,
exact mailbox identity, settings read, 5 messages discovered/processed, and 1 unsent draft. The owner
manually confirmed that draft exists in Avery's Drafts folder and was not sent. Attachments were not
exercised (0 stored). See CURRENT_STATE.md and LIVE_POC.md for the six-capability allowlist.
No additional Graph networking is authorized. The commands below are reference procedures, not
instructions to rerun the completed validation. No credentials or payloads were inspected for this update.

## Four independent permission states

| Capability / Graph permission | CONFIGURED IN ENTRA (owner-reported) | REQUESTED BY CURRENT OAUTH CODE | FREIGHTDESK ACTIONPOLICY / execution | LIVE_VALIDATED |
|---|---|---|---|---|
| Identity / User.Read | Yes | Yes | Bounded profile verification prerequisite; explicit owner execution | Yes: exact identity |
| Mail reads and unsent drafts / Mail.ReadWrite | Yes | Yes | read_mail/read_attachment/create_draft = ALLOW; network and draft gates still apply | Yes: 5-message read/intake and 1 new unsent draft only; attachments excluded |
| Mailbox preferences / MailboxSettings.Read | Yes | Yes | read_mailbox_settings = ALLOW; network and exact mailbox gates still apply | Yes: settings read only |
| Send / Mail.Send | Yes, provisioned for later | **No** | send_customer/carrier/dispatcher_email = APPROVAL_REQUIRED; all send HTTP execution independently disabled | **No** |

“Requested” describes the explicit scope set used by the current OAuth code. The owner reports successful
authentication; token contents were not inspected and no Mail.Send consent/use is claimed.
Configured permissions are metadata, not runtime scopes, approval or live evidence. The code uses
an explicit three-scope allowlist for interactive and silent acquisition, never `.default`, the
Entra permission list or extra_scopes_to_consent. MSAL's standard openid/profile/offline_access
session scopes are separate. Provisioning Mail.Send does not authorize FreightDesk to request or use it.
Existing tenant grants can affect Microsoft's consent UI/token issuance; this code does not infer
the contents of an issued token from registration. Sending stays blocked even with a broader token.

## Registration reference — already completed by owner

1. Sign in to the Microsoft Entra admin center in Booking Logistics' organizational tenant.
   Open **Identity → Applications → App registrations → New registration**.
2. Name: **FreightDesk AI — Avery Desktop**. Supported accounts: **Accounts in this
   organizational directory only (Single tenant)**. Register.
3. Open **Authentication → Add a platform → Mobile and desktop applications**.
   Add the custom redirect URI **http://localhost**, then save. This is MSAL's temporary
   loopback callback, not the dashboard URL or port 8787. Use the system browser.
   Do not add a Web/SPA platform, implicit grants or a client secret. This implementation
   uses interactive authorization code + PKCE, not device-code, password or client-credentials flow.
   The separate “Allow public client flows” fallback switch is not needed for this flow;
   the mobile/desktop redirect registration identifies the public client.
4. **API permissions → Add a permission → Microsoft Graph → Delegated permissions**:
   configured: **User.Read**, **Mail.ReadWrite**, **MailboxSettings.Read**, **Mail.Send**.
   Current OAuth requests only the first three. MailboxSettings.Read is for timezone/locale/date/time
   preferences; Mail.Send is provisioned for later and must remain unused. Do not remove the owner's
   provisioned Mail.Send or request application permissions, `.Shared` or directory-wide access.
5. The owner reports all four delegated permissions show **Admin consent required: No**.
   Booking Logistics' user-consent policy or Conditional Access may still require an administrator
   to approve the app. Use that tenant's normal approval process; do not weaken its security policy.
6. Keep **Directory (tenant) ID** and **Application (client) ID** private to the local configuration
   helper. Do not provide either identifier, password, authorization code or token in chat/log output.

MSAL automatically includes the standard sign-in/session scopes `openid`, `profile` and
`offline_access`. The code requests the three current Graph scopes above; offline access enables silent
token renewal when Microsoft permits it. Revocation/MFA/consent errors require manual reauthentication.

Microsoft references, checked 2026-09-07:
[desktop client configuration](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/client-applications),
[interactive token acquisition](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens),
[Graph permission definitions](https://learn.microsoft.com/en-us/graph/permissions-reference),
[app registration](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).

## Owner's manual steps — completed; reference only

Run from the existing FreightDesk project in PowerShell:

```powershell
$env:FREIGHTDESK_RUNTIME_ROOT = 'C:\FreightDeskRuntime'
$env:PYTHONDONTWRITEBYTECODE = '1'
.tools/python/python.exe -m scripts.configure_microsoft
```

Enter the Directory ID and Application ID only in the helper's hidden local prompts (not chat).
If configuration already exists, skip this helper; the scope update is in code and needs no ID rewrite.
This writes private local configuration
to `C:\FreightDeskRuntime\Data\booking-logistics\microsoft-config.json`; networking/drafts default off.
When ready to authenticate, the owner runs:

```powershell
.tools/python/python.exe -m scripts.microsoft_login
```

The browser opens Microsoft's sign-in page. Select **info@bookinglogistic.com**, complete MFA and
consent, and return to PowerShell. FreightDesk receives the OAuth result directly and stores it
encrypted; it prints only a success/failure message. It then checks `/me` and requires the returned
`mail` address to match exactly, then reads selected `/me/mailboxSettings` preferences and stores
them with observation time/source in the private mail database. No settings values or IDs are printed.
The helper does not read messages, create a draft, change settings or send mail.

**Mailbox prerequisite:** this implementation expects info@bookinglogistic.com to be a dedicated
organizational user mailbox with interactive sign-in, and its account username to match that address.
If it is a shared mailbox or an alias of a different sign-in identity, stop and reconcile that design.
Do not enable a shared-mailbox password or silently use another account. Shared delegated access
needs a separately reviewed principal, scopes and `/users/{mailbox}` contract.

## Bounded validation procedure — completed once; do not rerun without authorization

The owner has completed this procedure and confirmed its result. A future invocation requires
separate authorization; preserve the existing draft ledger and never reset it to recreate the draft:

```powershell
.tools/python/python.exe -m scripts.microsoft_bounded_validation --create-unsent-draft
```

This verifies `/me`, reads selected mailbox settings, reads at most **5 recent messages**, classifies/extracts/correlates locally,
examines the first attachment-bearing message and downloads at most **one** eligible file (10 MB),
then creates **one unsent acknowledgement draft addressed to the mailbox itself**. It does not
send, change an existing message, update Ascend/CarrierView or apply unverified canonical facts.
The durable action ID prevents automatic draft resubmission, including after ambiguous failure.
Inspect the unsent draft and sanitized results before marking specific capabilities LIVE_VALIDATED.
Read-only validation can omit `--create-unsent-draft`.

After separate authorization for incremental intake, `python -m scripts.microsoft_sync` processes
at most two inbox delta pages per invocation and retains the checkpoint. It is not scheduled.
Do not run this before the initial bounded validation. A 410/reset, 429 or authentication failure
stops without silently restarting the whole mailbox or retrying requests.

## Runtime and audit

* OAuth cache: `C:\FreightDeskRuntime\Tokens\Microsoft\msal-cache.bin` plus encrypted-cache lock file.
  MSAL Extensions uses Windows DPAPI bound to the current Windows user. No plaintext fallback.
* Mail records, events, draft ledger, proposals and redacted audit:
  `C:\FreightDeskRuntime\Data\booking-logistics\mail.sqlite3`.
* Files: `C:\FreightDeskRuntime\Documents\booking-logistics\mail\{sha256}.bin`.
* Historical exports/store: `C:\FreightDeskRuntime\Data\booking-logistics\history\...`.

DPAPI protects the token cache, not all SQLite/document contents. Runtime ACLs, Windows account
security and disk encryption remain deployment responsibilities. Raw mail is private runtime data.
Do not copy it into source, OneDrive, logs, screenshots or model prompts unnecessarily.

Dashboard records require the dedicated eight-hour HttpOnly owner session, distinct from demo access.
Run `python -m scripts.open_live_poc` to open it privately. The cookie is scoped to `/api` so it also
protects mail records; older sessions may need a fresh owner launch. No auth-grant URL is logged.
