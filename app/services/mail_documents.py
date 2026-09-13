import hashlib

from app.core.runtime import RuntimePaths
from app.models.domain import utcnow


def classify_attachment(content, mime, context):
    signature = ("PDF" if content.startswith(b"%PDF-") else
                 "PNG" if content.startswith(b"\x89PNG\r\n\x1a\n") else
                 "JPEG" if content.startswith(b"\xff\xd8\xff") else "UNKNOWN")
    expected = {"PDF": "application/pdf", "PNG": "image/png", "JPEG": "image/jpeg"}
    if signature == "UNKNOWN" or mime != expected[signature]:
        return {"candidate_kind": "OTHER", "confidence": 0, "review_required": True,
                "reason": "unsupported_or_mismatched_content"}
    lowered = context.casefold()
    kind = "OTHER"
    for words, candidate in [
        (("signed rate confirmation", "signed rc"), "SIGNED_RATE_CONFIRMATION"),
        (("proof of delivery", "pod attached", "attached pod"), "POD"),
        (("bill of lading", "bol attached", "attached bol"), "BOL"),
        (("load tender", "tender attached"), "TENDER"),
        (("loaded photos", "load photos"), "SHIPMENT_PHOTO"),
    ]:
        if any(word in lowered for word in words):
            kind = candidate
            break
    return {"candidate_kind": kind, "confidence": .65 if kind != "OTHER" else .1,
            "review_required": True, "reason": "mime_signature_and_mail_context_only"}


def ingest_attachment(store, message, attachment, content, tenant="booking-logistics", paths=None):
    if len(content) > 10_000_000 or attachment.size > 10_000_000:
        raise ValueError("Attachment size limit exceeded")
    paths = paths or RuntimePaths.from_environment()
    sha = hashlib.sha256(content).hexdigest()
    target = paths.path("Documents", tenant, "mail", sha + ".bin")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as file:
            file.write(content)
    except FileExistsError:
        if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
            raise ValueError("Attachment content-addressed storage conflict")
    classification = classify_attachment(content, attachment.contentType, message.subject + "\n" + message.body.content)
    source = {"message_id": message.id, "attachment_id": attachment.id, "original_name": attachment.name,
              "mailbox": "info@bookinglogistic.com", "received_at": str(message.receivedDateTime)}
    with store.transaction():
        try:
            record = store.get(tenant, "mail_attachment", sha)
        except KeyError:
            record = {"sha256": sha, "storage_ref": str(target), "size": len(content),
                      "stored_at": utcnow().isoformat(), "verified": False, "scan_status": "NOT_SCANNED",
                      "classification": classification, "sources": []}
        if source not in record["sources"]:
            record["sources"].append(source)
        store.put(tenant, "mail_attachment", sha, record)
    return record
