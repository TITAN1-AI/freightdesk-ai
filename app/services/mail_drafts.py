import hashlib
import json

from app.models.domain import ActionPolicy, utcnow
from app.security.authorization import authorize
from integrations.outlook.adapter import GraphError
from integrations.outlook.models import Body, DraftPayload, EmailAddress, Recipient


def grounded_draft(recipient, verified_facts=None):
    facts = verified_facts or {}
    if not recipient or "@" not in recipient or any(c in recipient for c in "\r\n"):
        raise ValueError("Verified recipient address required")
    for name, fact in facts.items():
        if name not in {"load_reference", "location", "eta", "status"}:
            raise ValueError("Unsupported draft fact")
        if fact.get("verified") is not True or not fact.get("source_ref") or not fact.get("verified_by"):
            raise PermissionError("Drafts require verified source facts")
        if not isinstance(fact.get("value"), str) or len(fact["value"]) > 200:
            raise ValueError("Invalid bounded draft fact")
    text = "Thank you for your message. We will review the details."
    template = "acknowledgement"
    subject = "FreightDesk acknowledgement"
    if facts:
        labels = {"load_reference": "Booking load", "location": "Verified location",
                  "eta": "Verified ETA", "status": "Verified status"}
        text = "\n".join(labels[key] + ": " + value["value"] for key, value in facts.items())
        subject = "FreightDesk verified shipment update"
        template = "verified_status"
    digest = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
    return DraftPayload(subject=subject, body=Body(contentType="text", content=text),
        toRecipients=[Recipient(emailAddress=EmailAddress(address=recipient))],
        grounding_hash=digest, template=template)


async def create_durable_draft(store, adapter, actor, policy, action_id, payload, kind="new", message_id=None):
    authorize(actor, "booking-logistics", "request_action")
    if policy != ActionPolicy.ALLOW:
        raise PermissionError("Draft creation requires an allowed ActionPolicy")
    if kind not in {"new", "reply", "forward"} or (kind != "new" and not message_id):
        raise ValueError("Draft kind and exact source message required")
    binding = {"mailbox": adapter.config.mailbox, "kind": kind, "message_id": message_id,
               "payload": payload.model_dump(), "grounding_hash": payload.grounding_hash}
    digest = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    with store.transaction():
        try:
            existing = store.get(actor.tenant_id, "mail_draft_action", action_id)
        except KeyError:
            existing = None
        if existing:
            if existing["payload_hash"] != digest:
                raise PermissionError("Draft action identifier was reused with changed content")
            return existing  # Never automatically resubmit an attempted draft.
        record = {"id": action_id, "payload_hash": digest, "state": "IN_FLIGHT", "attempts": 1,
                  "created_at": utcnow().isoformat(), "message_id": None, "kind": kind}
        store.put(actor.tenant_id, "mail_draft_action", action_id, record)
    try:
        if kind == "new":
            result = await adapter.create_draft(payload)
        elif kind == "reply":
            result = await adapter.create_reply_draft(message_id, payload)
        else:
            result = await adapter.create_forward_draft(message_id, payload)
        record.update(state="CREATED", message_id=result.id, completed_at=utcnow().isoformat())
    except GraphError as error:
        record.update(state="UNCERTAIN" if error.uncertain else "FAILED", error_code=error.code)
    except BaseException:
        record.update(state="UNCERTAIN", error_code="draft_result_unknown")
        with store.transaction():
            store.put(actor.tenant_id, "mail_draft_action", action_id, record)
        raise
    with store.transaction():
        store.put(actor.tenant_id, "mail_draft_action", action_id, record)
    return record
