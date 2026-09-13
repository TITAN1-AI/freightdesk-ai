import re

from app.models.mail import Classification, FactEvidence, FreightFacts, MailIntent
from model_providers.interfaces.provider import LanguageRequest

LOAD = re.compile(r"\b(?:booking\s+(?:load|ref(?:erence)?)|load(?:\s*(?:number|no\.?))?)\s*[#:]?\s*([A-Za-z0-9-]{2,30})\b", re.I)

RULES = [
    ("EXCEPTION_REPORT", r"\b(accident|breakdown|cargo damage|missed appointment)\b"),
    ("ACCESSORIAL_REQUEST", r"\b(detention|layover|lumper)\b.*\b(request|charge|approval)\b"),
    ("SIGNED_RATE_CONFIRMATION", r"\bsigned\s+(?:rate confirmation|rate con|rc)\b"),
    ("POD", r"\b(?:proof of delivery|pod attached|attached pod)\b"),
    ("BOL", r"\b(?:bill of lading|bol attached|attached bol)\b"),
    ("SHIPMENT_PHOTO", r"\b(?:loaded photos|load photos|shipment photos)\b"),
    ("CUSTOMER_LOAD_TENDER", r"\b(?:load tender|shipment tender|tender attached)\b"),
    ("CUSTOMER_QUOTE_REQUEST", r"\b(?:quote request|request a quote|please quote|rate request)\b"),
    ("CUSTOMER_STATUS_REQUEST", r"\b(?:status update request|where is the truck|load status\?)"),
    ("CARRIER_SETUP_REQUEST", r"\b(?:carrier setup|carrier packet|onboarding request)\b"),
    ("DRIVER_INFO", r"\bdriver\s+(?:is|name[: ])"),
    ("ETA_UPDATE", r"\beta\b"),
    ("TRACKING_RESPONSE", r"\b(?:tracking link|tracking accepted|tracking invitation)\b"),
    ("CARRIER_BOOKING_INFO", r"\b(?:booking confirmation|carrier booked)\b"),
    ("DISPATCHER_UPDATE", r"\bdispatcher update\b"),
    ("DRIVER_UPDATE", r"\bdriver update\b"),
    ("CARRIER_UPDATE", r"\bcarrier update\b"),
    ("OTHER_LOAD_DOCUMENT", r"\bload document\b"),
]


def classify_text(text):
    if re.fullmatch(r"\s*(?:status\s+\d+|show deliveries tomorrow|which loads are at risk\??|follow up on load\s+\d+)\s*", text, re.I):
        return Classification(intent=MailIntent.OWNER_COMMAND, confidence=.95, review_required=True)
    for intent, pattern in RULES:
        if re.search(pattern, text, re.I | re.S):
            return Classification(intent=MailIntent(intent), confidence=.85, review_required=True)
    return Classification()


def extract_facts(message):
    text = message.subject + "\n" + message.body.content
    facts = FreightFacts()
    def capture(field, pattern, flags=re.I, transform=lambda value: value.strip()):
        match = re.search(pattern, text, flags)
        if not match:
            return
        value = transform(match.group(1))
        setattr(facts, field, value)
        facts.evidence.append(FactEvidence(field=field, source_message_id=message.id,
            source_text=match.group(1), start=match.start(1), end=match.end(1),
            confidence=.9, observed_at=message.receivedDateTime))
    refs = list(dict.fromkeys(LOAD.findall(text)))
    if len(refs) == 1:
        capture("load_reference", LOAD.pattern)
    elif refs:
        facts.ambiguities.append("multiple_load_references")
    capture("driver_name", r"\bdriver\s+(?:is|name\s*[:=]?)\s*([A-Za-z][A-Za-z .'-]{1,70}?)(?=,|\n|\s+\+?\d)")
    capture("driver_phone", r"\bdriver(?:\s+phone)?\s*[:=]?\s*(\+?\d[\d ()-]{7,20}\d)")
    if facts.driver_name and not facts.driver_phone:
        capture("driver_phone", r"\bdriver\s+(?:is|name\s*[:=]?)\s*[A-Za-z .'-]+,\s*(\+?\d[\d ()-]{7,20}\d)")
    for field, label in [("truck_number", "truck"), ("trailer_number", "trailer"),
                         ("mc", "MC"), ("dot", "DOT")]:
        capture(field, r"\b" + label + r"\s*(?:number|no\.?|#|:)?\s*([A-Za-z0-9-]{1,25})\b")
    capture("current_location", r"\bempty in\s+([A-Za-z .]+?)(?=\s+and\b|[,.\n]|$)")
    capture("truck_status", r"\b(empty)\b", transform=lambda _: "EMPTY")
    if re.search(r"\b(?:heading to|en route to) pickup\b", text, re.I):
        capture("movement", r"\b((?:heading to|en route to) pickup)\b", transform=lambda _: "EN_ROUTE_PICKUP")
    capture("eta_text", r"\bETA\s*[:=]?\s*(\d{1,2}:\d{2}(?:\s*[ap]m)?)")
    if facts.eta_text:
        facts.ambiguities.append("eta_date_timezone_and_possibly_am_pm_unverified")
    from decimal import Decimal
    for field, label in (("customer_rate", "customer (?:rate|price)"), ("carrier_rate", "carrier (?:rate|pay)")):
        capture(field, r"\b" + label + r"\s*[:=]?\s*\$?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)\b",
                transform=lambda value: Decimal(value.replace(",", "")))
    return facts


async def classify_message(message, tenant, model_provider=None, audit=lambda _: None):
    text = (message.subject + "\n" + message.body.content)[:4000]
    result = classify_text(text)
    if result.intent != MailIntent.UNKNOWN or model_provider is None:
        return result
    audit({"event": "MODEL_MAIL_CONTEXT_ACCESS", "characters": len(text), "source_message_id": message.id})
    request = LanguageRequest(tenant_id=tenant, purpose="classification", verified_facts={},
        untrusted_text=text, output_schema=Classification.model_json_schema(), max_output_tokens=300)
    try:
        response = await model_provider.generate(request)
        result = Classification.model_validate(response.structured_output)
        result.source = "model"
        result.review_required = True
        return result
    except Exception:
        audit({"event": "MODEL_CLASSIFICATION_FAILED"})
        return Classification(source="unavailable")


async def extract_message(message, tenant, model_provider=None, audit=lambda _: None):
    facts = extract_facts(message)
    if model_provider is None:
        return facts
    text = (message.subject + "\n" + message.body.content)[:4000]
    audit({"event": "MODEL_MAIL_EXTRACTION_ACCESS", "characters": len(text)})
    try:
        result = await model_provider.generate(LanguageRequest(tenant_id=tenant, purpose="extraction",
            verified_facts={}, untrusted_text=text, output_schema=FreightFacts.model_json_schema(),
            max_output_tokens=1000))
        proposed = FreightFacts.model_validate(result.structured_output)
        for evidence in proposed.evidence:
            if evidence.field not in FreightFacts.model_fields or evidence.field in {"evidence", "ambiguities"}:
                continue
            value = getattr(proposed, evidence.field)
            if (evidence.source_message_id != message.id or text[evidence.start:evidence.end] != evidence.source_text
                    or value is None or str(value).casefold() not in evidence.source_text.casefold()):
                continue
            if getattr(facts, evidence.field) is None:
                setattr(facts, evidence.field, value)
                evidence.verification = "UNVERIFIED"
                facts.evidence.append(evidence)
        facts.ambiguities = list(dict.fromkeys(facts.ambiguities + proposed.ambiguities))
    except Exception:
        audit({"event": "MODEL_EXTRACTION_FAILED"})
        facts.ambiguities.append("model_extraction_failed")
    return facts


def correlate(message, facts, shipments, conversation_bindings=None):
    bindings = conversation_bindings or {}
    if "multiple_load_references" in facts.ambiguities:
        return {"shipment_id": None, "confidence": 0, "review_required": True, "reason": "multiple_references"}
    candidates = []
    for shipment in shipments:
        explicit = facts.load_reference is not None and facts.load_reference in {
            shipment.booking_load_id, shipment.customer_reference, shipment.id}
        conversation = bindings.get(message.conversationId) == shipment.id if message.conversationId else False
        sender = message.from_.emailAddress.address.casefold() if message.from_ else ""
        participant = bool(shipment.dispatcher and shipment.dispatcher.email
                           and shipment.dispatcher.email.casefold() == sender)
        carrier = bool(shipment.carrier and (
            (facts.mc and facts.mc == shipment.carrier.mc) or
            (facts.dot and facts.dot == shipment.carrier.dot) or
            (facts.carrier and facts.carrier.casefold() == shipment.carrier.name.casefold())))
        driver = bool(shipment.driver and facts.driver_phone and
            re.sub(r"\D", "", facts.driver_phone) == re.sub(r"\D", "", shipment.driver.phone))
        recipients = {r.emailAddress.address.casefold() for r in message.toRecipients + message.ccRecipients}
        known_recipient = bool(shipment.dispatcher and shipment.dispatcher.email and
                               shipment.dispatcher.email.casefold() in recipients)
        if explicit or conversation or participant or carrier or driver or known_recipient:
            # Weak identity signals never suffice alone to bind a shipment.
            weak = min(.7, .35 * participant + .25 * carrier + .25 * driver + .1 * known_recipient)
            score = min(.99, (.92 if explicit else .85 if conversation else weak) +
                        (.06 if participant and (explicit or conversation) else 0))
            candidates.append((score, shipment.id))
    candidates.sort(reverse=True)
    if not candidates or (len(candidates) > 1 and candidates[0][0] - candidates[1][0] < .15):
        return {"shipment_id": None, "confidence": 0, "review_required": True, "reason": "ambiguous_or_unmatched"}
    score, shipment_id = candidates[0]
    return {"shipment_id": shipment_id if score >= .85 else None, "confidence": score,
            "review_required": score < .95, "reason": "explicit_signals"}
