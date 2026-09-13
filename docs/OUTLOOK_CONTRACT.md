# Outlook contract and boundaries

Official Graph v1.0 origin: `https://graph.microsoft.com`. Tenant-specific Entra authority.
Public-client MSAL OAuth; no app secret/password or Outlook UI automation. Adapter creation alone
does not authorize networking. Exact `/me.mail` verification precedes every mailbox session.

## Permission-state contract

1. **CONFIGURED IN ENTRA:** owner confirms delegated User.Read, Mail.ReadWrite,
   MailboxSettings.Read and Mail.Send, all displayed as not inherently requiring admin consent.
   `ENTRA_CONFIGURED_PERMISSIONS` is owner-reported metadata only, never an OAuth input.
2. **REQUESTED BY OAUTH:** `SCOPES` explicitly contains User.Read, Mail.ReadWrite and
   MailboxSettings.Read. Both interactive and silent MSAL calls use it. No Mail.Send, `.default`
   or extra consent scopes. The owner confirms successful OAuth; no Mail.Send request/use is claimed.
3. **AUTHORIZED BY ACTIONPOLICY:** read_mail/read_attachment/read_mailbox_settings and
   create_draft are ALLOW eligibility; explicit network/draft/identity gates remain. Customer,
   carrier and dispatcher sends remain APPROVAL_REQUIRED. All send HTTP paths are independently
   blocked even if policy were changed or a token included Mail.Send.
4. **LIVE_VALIDATED:** only the owner-confirmed OAuth, exact mailbox identity, settings read,
   bounded discovery/read of 5 messages, ingestion/processing and 1 manually verified unsent draft.
   Attachments (0 exercised), delta, real correlation, send, canonical mutation, owner commands,
   webhooks and autonomous communications remain unvalidated. See LIVE_POC.md. No further Graph
   networking is authorized. Registration and offline tests alone are not live evidence.

| Adapter operation | Graph contract |
|---|---|
| Profile | GET `/v1.0/me` with selected identity fields |
| Mailbox preferences | GET `/v1.0/me/mailboxSettings?$select=timeZone,language,dateFormat,timeFormat`; requires MailboxSettings.Read |
| Folders | GET `/v1.0/me/mailFolders`, first 50 |
| Message / recent / search / conversation | GET `/v1.0/me/messages[/id]`, bounded select/top and documented filter/search |
| Attachments | GET `/v1.0/me/messages/{id}/attachments`, first 50 metadata entries |
| File bytes | GET `/v1.0/me/messages/{id}/attachments/{id}/$value`; fileAttachment only, <=10 MB |
| Delta | GET `/v1.0/me/mailFolders/{folder}/messages/delta`; immutable IDs, selected fields, page size preference 25 |
| New draft | POST `/v1.0/me/messages`; must return isDraft=true |
| Reply / forward draft | POST `/v1.0/me/messages/{id}/createReply` or `/createForward` |
| Send / send reply / send forward | Interfaces raise APPROVAL_REQUIRED; no HTTP execution |

MailboxSettings uses typed nullable strings and locale metadata; extra response fields such as
automatic-reply text are discarded. A failed read does not replace prior observations. Successful
reads store only selected preferences, mailbox/source/observation time and fixture/live provenance
under `mail_settings/microsoft` in the private runtime mail database, never in logs. Fixture results
cannot set live_validated. The owner-run login and bounded-validation helpers include this read.
Timezone is retained exactly as Microsoft returns it (Windows or IANA); missing/unknown zones stay
unresolved. Mailbox locale/date/time formats are context, not evidence of a driver's timezone,
appointment zone, AM/PM or date. No automatic timezone conversion, UTC offset, DST assumption or
shipment update is introduced. No settings PATCH/PUT, MailboxSettings.ReadWrite scope or send route.
See Microsoft's [mailbox settings read contract](https://learn.microsoft.com/en-us/graph/api/user-get-mailboxsettings?view=graph-rest-1.0).

Read methods return pagination links for an explicit next bounded job; they do not drain the mailbox.
Delta validates exact HTTPS origin and folder path on returned cursors, stores entire opaque links,
and never prints them. Immutable IDs are requested on all calls. Folder removals retain source
provenance and mark membership absent, rather than deleting a global message on a folder move.
Continuation cursor, normalized ExternalEvents, proposals and dedup receipts commit atomically;
stale concurrent checkpoint writers fail. Read-state/changeKey churn does not rerun classification.
Partial updates merge with prior records; an incomplete newly discovered item is fetched by exact ID.
401/403/410/429 stop with safe codes. Retry-After is exposed as bounded metadata, not an automatic retry.

MailExternalEvent retains message/conversation IDs, sender/recipients, timestamps, subject/body,
supplied attachment metadata, classification, evidence, processing state, confidence and action.
Attachment enumeration/download adds provenance records separately; it does not claim full
attachment enumeration from hasAttachments alone. Bodies and provider payloads are never logged.

Deterministic intent rules precede optional injected ModelProvider structured output. Only minimal
bounded message text enters that interface, with audited access. No remote model is configured or
called in M3. Model facts must have matching literal evidence spans and always remain UNVERIFIED.
The typed schema supports freight entities/locations/appointments/rates; handwritten extractors
cover explicit load/MC/DOT, driver/truck/trailer, empty location/movement, raw ETA and labeled rates.
Unknown dates/timezones and AM/PM are not invented: “ETA 2:30” remains eta_text plus ambiguity.

Correlation uses explicit load/customer references, owner-approved conversation bindings and
weaker dispatcher/recipient/carrier/MC/DOT/driver-phone signals. Weak signals alone never bind.
Ambiguous candidates remain unmatched/review-required. Extracted changes are stored as
`mail_update_proposal`, never applied automatically to canonical loads or external systems.
Owner command execution requires trusted verification bound to message ID, content hash, sender,
tenant and AuthorizedIdentity. From/display name or Graph transport alone is not sender proof.
Supported verified commands are read-only; all other command texts become review requests.

Drafts use verified source-labeled facts or a claim-free acknowledgement. Graph draft POSTs have
a durable local intent before execution. IN_FLIGHT/UNCERTAIN/FAILED records never auto-resubmit;
owner reconciliation is required after unknown results. No automated recovery search is enabled.
Production sending is blocked independently of policy configuration, and Mail.Send is not requested.

Attachments use content hashes, private .bin storage, MIME/signature checks and context. Classification
is a candidate only; NOT_SCANNED and verified=false. No execution, OCR, automatic POD/BOL acceptance,
signed-RC verification or billing-gate advancement. Malware scanning is not implemented.

## Future notification ingress (architecture only)

Graph → dedicated minimal public HTTPS ingress → durable tenant-scoped notification queue →
private worker → authenticated Graph delta reconciliation → existing MailSynchronizer.
The ingress must independently handle Graph validation challenges, bind subscription/clientState
to tenant/resource, validate notification authenticity, limit payload/rate, deduplicate deliveries,
acknowledge after durable enqueue and renew subscriptions. Notifications are hints, not shipment
facts: the worker re-reads Graph with its own identity. Keep the dashboard and owner endpoints private.
No subscription creation, public endpoint, tunnel or webhook acceptance is implemented/deployed here.

Sources checked 2026-09-07:
[delta](https://learn.microsoft.com/en-us/graph/api/message-delta?view=graph-rest-1.0),
[immutable IDs](https://learn.microsoft.com/en-us/graph/outlook-immutable-id),
[draft creation](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0),
[reply draft](https://learn.microsoft.com/en-us/graph/api/message-createreply?view=graph-rest-1.0),
[forward draft](https://learn.microsoft.com/en-us/graph/api/message-createforward?view=graph-rest-1.0),
[attachment reads](https://learn.microsoft.com/en-us/graph/api/attachment-get?view=graph-rest-1.0).
