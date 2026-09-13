import re

from app.models.domain import AuditEvent


def sanitized(text):
    value = re.sub(r"[\w.+-]+@[\w.-]+", "[email]", text or "")
    value = re.sub(r"(?<!\w)\+?\d[\d ()-]{7,}\d", "[phone]", value)
    value = re.sub(r"https?://\S+", "[link]", value)
    value = re.sub(r"\$\s*[\d,.]+", "[amount]", value)
    return value[:120]


def mail_summary(store, tenant="booking-logistics", shipment_id=None):
    connections = store.all(tenant, "mail_connection")
    connection = connections[0] if connections else {"status": "NOT_AUTHENTICATED"}
    latest = store.all(tenant, "mail_message")
    events = [store.get(tenant, "mail_event", row["event_id"]) for row in latest]
    if shipment_id:
        events = [event for event in events if event.get("shipment_id") == shipment_id]
    rows = []
    for event in sorted(events, key=lambda e: e["message"].get("receivedDateTime") or "", reverse=True)[:20]:
        message = event["message"]
        address = ((message.get("from_") or message.get("from") or {}).get("emailAddress") or {}).get("address", "")
        rows.append({"time": message.get("receivedDateTime"), "sender_company": address.rpartition("@")[2],
            "subject": sanitized(message.get("subject")), "intent": event["classification"]["intent"],
            "matched_load": event.get("shipment_id"), "confidence": event["match_confidence"],
            "status": event["processing_state"], "action": event["action_taken"]})
    message_ids = {event["message"]["id"] for event in events}
    attachments = [record for record in store.all(tenant, "mail_attachment") if not shipment_id or
                   any(source["message_id"] in message_ids for source in record["sources"])]
    drafts = store.all(tenant, "mail_draft_action")
    checkpoints = store.all(tenant, "mail_checkpoint")
    return {"messages_discovered": len(events),
        "messages_processed": sum(e["processing_state"] in {"PROCESSED", "REVIEW_REQUIRED"} for e in events),
        "unmatched_messages": sum(e.get("shipment_id") is None for e in events),
        "classification_failures": sum(e["classification"]["source"] == "unavailable" for e in events),
        "attachment_count": len(attachments), "drafts_created": sum(d["state"] == "CREATED" for d in drafts),
        "errors": sum(bool(e.get("error_code")) for e in store.timeline(tenant)),
        "last_successful_sync": max((p["last_successful_sync"] for p in checkpoints), default=None),
        "recent": rows, "documents": [{"kind": a["classification"]["candidate_kind"],
            "verified": a["verified"], "scan_status": a["scan_status"], "size": a["size"]} for a in attachments],
        "connection": connection, "live_validated": False}


def graph_audit(store, tenant="booking-logistics"):
    def callback(entry):
        with store.transaction():
            store.audit(AuditEvent(tenant_id=tenant, actor_id="FreightDesk/Avery", source="microsoft_graph",
                event=entry["event"], explanation="Delegated Graph operation; sensitive content omitted",
                error_code=entry.get("error_code"),
                facts={k: entry[k] for k in ("operation", "fixture", "status", "credential_class") if k in entry}))
    return callback
