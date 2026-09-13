# Avery SOP

Avery assists Booking Logistics. The broker initially retains negotiation, carrier selection,
commercial decisions and high-value exceptions.

## Lifecycle

TENDER_RECEIVED -> LOAD_CREATED -> READY_TO_COVER -> CARRIER_SELECTED ->
CARRIER_ONBOARDING -> CARRIER_APPROVED -> DRIVER_INFO_REQUIRED -> TRACKING_PENDING ->
TRACKING_ACTIVE -> RC_PENDING -> RC_SENT -> RC_SIGNED -> EN_ROUTE_PICKUP ->
CHECKED_IN_PICKUP -> LOADED -> IN_TRANSIT -> EN_ROUTE_DELIVERY ->
CHECKED_IN_DELIVERY -> DELIVERED -> POD_PENDING -> POD_RECEIVED ->
BILLING_READY -> CLOSED.

Already approved/onboarded carriers may skip onboarding. EXCEPTION saves the prior state,
requires resolution, then returns to that state. No silent skipping.
Full state model exists; vendor workflow execution is incremental.

## BOOK IT and tracking gate

After broker selection: identify MC/DOT, query BrokerCarrier profile/vetting/documents,
send the authorized setup link if needed, monitor completion and sync an approved carrier
to Ascend under policy. Collect driver name/phone/truck/trailer and dispatcher contact.
Create/initiate tracking only after verifying documented API behavior and side effects.

Default RC prerequisites: carrier approved, setup complete, driver information complete,
tracking requested, active and accepted. Recheck before RC_PENDING and RC_SENT.
RC_SIGNED requires a verified signed RC.

Future activation follow-up: configured grace, driver SMS, dispatcher follow-up, bounded retry,
broker escalation. Exact timings must be confirmed before live outreach.

## Pickup and transit

Monitor ETA/freshness, check-in, loading, BOL/photos/seal requirements. Update state from
verified evidence, store documents and prepare customer updates under policy.

Provisional deterministic demo risk defaults:
- Fresh position under 30 minutes and valid ETA before appointment: HEALTHY; no driver outreach.
- Tracking 30–59 minutes old: WARNING; reconcile source.
- Tracking 60+ minutes old or ETA past appointment: AT_RISK.
- Unresolved operational exception: EXCEPTION.
- Missing, future, expired or unverified facts: WARNING.

Thresholds are Settings defaults, not live-validated Booking Logistics policy.
Use aware timestamps; date queries use the configured workspace timezone.

## Delivery, POD and billing

Delivery confirmation requires verified source evidence. POD_PENDING leads to future scheduled
requests/follow-up/escalation. POD_RECEIVED requires verified POD. Billing requires all
configured verified documents and no unresolved exceptions. Demo defaults are BOL/POD/signed RC.
Customer-specific billing requirements must be agreed before live billing decisions.

## Policy and supervision

ALLOW is autonomous, APPROVAL_REQUIRED queues a concrete action, FORBIDDEN denies it.
Current execution is simulation only. Owner can pause Avery, pause/take over one load,
resume or reject. A pause blocks subsequent execution attempts.

Rate/price/appointment changes, accessorials, carrier cancellation/replacement, unusual
commitments, claims and material escalations normally need approval.
Compliance/security bypass, banking/factoring/payment changes/transfers default to FORBIDDEN.
Policy never removes verified-data/workflow gates.

Unknown identity, ambiguous shipment, conflicting systems, failed verification, stale tracking
beyond policy or exhausted retries require escalation. Current escalation is a dashboard
risk/next-action signal; no broker notification is sent.
Audit concise facts/rules/results, never hidden model reasoning.
