# CarrierView contract record

Source: owner's supplied CarrierView contract, 2026-09-07 continuation request.
This record distinguishes supplied facts from engineering fixtures and unresolved fields.
No vendor network verification has occurred.

## Supplied facts

Authentication: Authorization: Bearer {API_TOKEN}; Content-Type: application/json.
Inspect strict boolean success for every response; HTTP 200 alone is insufficient.
On success=false retain error_code/errors in the typed error, but never print raw errors.

| Method | Documented path | Adapter |
|---|---|---|
| GET | /api/profile | get_profile |
| GET | /api/loads/integration-types | get_integration_types |
| GET | /api/loads?filter=active | search_loads |
| GET | /api/loads/{id} | get_load |
| GET | /api/loads/{id}/last-position | get_last_position |
| GET | /api/loads/{id}/positions-history | get_positions_history |
| POST | /api/loads | create_tracking_load |
| PATCH | /api/loads/{id} | edit_load |
| PATCH | /api/loads/{id}/disable | disable_load |
| POST | /api/loads/{id}/chat-message | send_driver_chat_message |
| POST | /api/loads/{id}/text-message | send_driver_text_message |
| PUT | /api/webhook/new-position-sent | configure_webhooks |
| PUT | /api/webhook/chat-message-created-by-driver | configure_webhooks |
| PUT | /api/webhook/load-status-changed | configure_webhooks |

Known errors: user_not_found, company_not_found, company_disabled, load_not_found,
permission_denied, required_fields_errors, creation_error, driver_opted_out,
sms_provider_failed, internal_error. Unknown error codes fail safely.
Permission failures raise scope/elevation, never change credential class automatically.

Native creation uses integration_type=carrier_view, driver_phone, load_id, locations containing
pickup and destination; optional starts_active, emails, dispatchers. Returned provider ID is
separate from Booking load_id; tracking_number_url/client_url are retained in provider metadata.
Creation may initiate tracking; no separate initiation endpoint is established.

SMS message_type: welcome, assigned_load, one_time_ping_request, installation_guide, custom.
Custom requires message of at most 480 characters. Maximum 5 requests/minute; 429 is rate limiting.
SMS is non-idempotent. Any ambiguous outcome becomes UNCERTAIN; no automatic resend.

Tracking preserves integration_type, load_id, driver_phone, route_started,
track_driver.app_status/last_request_time_utc, driver_is_late, time_left_sec,
distance_left_meters, delivery_arrived/departed, statuses, locations, last_position,
tracking_number_url and client_url. Unknown fields, explicit nulls and raw timestamps survive mapping.
Documents/POD API is unsupported/unknown.

## Still unverified

- Exact HTTPS base origin and complete response envelopes. ResponseContract selectors must
  come from official reference; fixture data nesting is not evidence.
- Profile user/company key semantics; position field names and numeric timestamp units;
  stop address/type/appointment sub-shapes and timezone rules; app/status meanings.
- List pagination and history ordering/query filters. Current implementation requests only
  the documented active filter and bounds bytes/count locally.
- Exact chat body key, webhook URL body key, dispatcher object structure, edit/null behavior
  and location subfields. The current typed request models are provisional where omitted.
- Provider webhook wire format, authentication/signatures, delivery retry/order/replay behavior.
  Local normalized schemas and ingress key are an internal staging contract only.

Write methods are fixture-tested but all real write networking is disabled.
Read networking requires owner confirmation, verified origin and verified response contract.
Status labels must never conflate IMPLEMENTED, TESTED and LIVE_VALIDATED.
