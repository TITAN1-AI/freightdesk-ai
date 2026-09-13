import hashlib
import json

from app.models.domain import AuditEvent, utcnow
from app.models.mail import MailExternalEvent
from app.services.mail_intelligence import classify_message, correlate, extract_message
from app.services.mail_association import bindings, store_proposal
from integrations.outlook.models import Message


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class MailSynchronizer:
    def __init__(self, store, mailbox="info@bookinglogistic.com", tenant="booking-logistics", model_provider=None):
        self.store, self.mailbox, self.tenant, self.model_provider = store, mailbox, tenant, model_provider

    async def sync(self, adapter, shipments=(), folder="inbox", max_pages=2):
        if not 1 <= max_pages <= 10:
            raise ValueError("Sync must be bounded")
        await adapter.get_mailbox_profile()
        key = digest([self.mailbox, folder])
        try:
            checkpoint = self.store.get(self.tenant, "mail_checkpoint", key)
        except KeyError:
            checkpoint = {"cursor": None, "version": 0}
        processed = 0
        for _ in range(max_pages):
            page = await adapter.delta_page(folder, checkpoint["cursor"])
            events, memberships = [], []
            for row in page.value:
                if not isinstance(row.get("id"), str):
                    raise ValueError("Delta message identity required")
                message_key = digest([self.mailbox, row["id"]])
                removed = "@removed" in row
                memberships.append((digest([folder, message_key]), {"message_key": message_key,
                                    "folder": folder, "present": not removed}))
                if removed:
                    continue  # Folder tombstone is not evidence of global deletion; retain provenance.
                try:
                    prior = self.store.get(self.tenant, "mail_message", message_key)
                    previous = self.store.get(self.tenant, "mail_event", prior["event_id"])["message"]
                    message = Message.model_validate({**previous, **row})
                except KeyError:
                    message = Message.model_validate(row)
                    if not {"subject", "body", "receivedDateTime"} <= row.keys():
                        message = await adapter.get_message(row["id"])
                # Exclude read-state/changeKey churn from processing fingerprint.
                content = message.model_dump(mode="json", exclude={
                    "changeKey", "lastModifiedDateTime", "isRead", "parentFolderId"})
                event_key = digest([self.mailbox, message.id, content])
                if self.store.db.execute("SELECT 1 FROM receipts WHERE tenant=? AND source=? AND id=?",
                        (self.tenant, "microsoft_graph", event_key)).fetchone():
                    continue
                classification = await classify_message(message, self.tenant, self.model_provider,
                                                         self._model_audit)
                facts = await extract_message(message, self.tenant, self.model_provider, self._model_audit)
                match = correlate(message, facts, shipments, bindings(self.store, self.tenant, self.mailbox))
                event = MailExternalEvent(id=event_key, tenant_id=self.tenant, mailbox=self.mailbox,
                    message=message, shipment_id=match["shipment_id"], classification=classification,
                    extracted=facts, match_confidence=match["confidence"],
                    processing_state="REVIEW_REQUIRED" if match["review_required"] or facts.ambiguities else "PROCESSED",
                    action_taken="PROPOSED_UPDATE_ONLY" if match["shipment_id"] else "REVIEW_REQUIRED")
                events.append((message_key, event))
            next_checkpoint = {"cursor": page.next_link or page.delta_link,
                               "version": checkpoint["version"] + 1, "round_complete": bool(page.delta_link),
                               "last_successful_sync": utcnow().isoformat()}
            # Event records, dedup receipts and cursor advance atomically; concurrent stale workers fail.
            with self.store.transaction():
                current = self.store.all(self.tenant, "mail_checkpoint")
                actual = self.store.get(self.tenant, "mail_checkpoint", key) if any(
                    value.get("mailbox_folder_key") == key for value in current) else {"version": 0}
                if actual["version"] != checkpoint["version"]:
                    raise ValueError("Concurrent sync checkpoint changed")
                for membership_key, membership in memberships:
                    self.store.put(self.tenant, "mail_membership", membership_key, membership)
                for message_key, event in events:
                    inserted = self.store.db.execute("INSERT OR IGNORE INTO receipts VALUES (?,?,?,?)",
                        (self.tenant, "microsoft_graph", event.id, event.id)).rowcount
                    if not inserted:
                        continue
                    self.store.put(self.tenant, "mail_event", event.id, event)
                    store_proposal(self.store, event)
                    self.store.put(self.tenant, "mail_message", message_key, {
                        "message_id": event.message.id, "event_id": event.id, "mailbox": self.mailbox})
                    self.store.audit(AuditEvent(tenant_id=self.tenant, source="microsoft_graph",
                        actor_id="FreightDesk/Avery", event="MAIL_DISCOVERED",
                        explanation="Message normalized; extracted claims are proposals, not verified facts",
                        facts={"intent": event.classification.intent, "matched": event.shipment_id is not None}))
                    processed += 1
                next_checkpoint["mailbox_folder_key"] = key
                self.store.put(self.tenant, "mail_checkpoint", key, next_checkpoint)
            checkpoint = next_checkpoint
            if page.delta_link:
                break
        return {"processed": processed, "round_complete": checkpoint.get("round_complete", False)}

    async def ingest_recent(self, messages, shipments=()):
        count = 0
        for message in messages:
            content = message.model_dump(mode="json", exclude={
                "changeKey", "lastModifiedDateTime", "isRead", "parentFolderId"})
            event_key = digest([self.mailbox, message.id, content])
            if self.store.db.execute("SELECT 1 FROM receipts WHERE tenant=? AND source=? AND id=?",
                    (self.tenant, "microsoft_graph", event_key)).fetchone():
                continue
            classification = await classify_message(message, self.tenant, self.model_provider, self._model_audit)
            facts = await extract_message(message, self.tenant, self.model_provider, self._model_audit)
            match = correlate(message, facts, shipments, bindings(self.store, self.tenant, self.mailbox))
            event = MailExternalEvent(id=event_key, tenant_id=self.tenant, mailbox=self.mailbox, message=message,
                shipment_id=match["shipment_id"], classification=classification, extracted=facts,
                match_confidence=match["confidence"], processing_state="REVIEW_REQUIRED",
                action_taken="PROPOSED_UPDATE_ONLY" if match["shipment_id"] else "REVIEW_REQUIRED")
            with self.store.transaction():
                if not self.store.db.execute("INSERT OR IGNORE INTO receipts VALUES (?,?,?,?)",
                        (self.tenant, "microsoft_graph", event_key, event_key)).rowcount:
                    continue
                self.store.put(self.tenant, "mail_event", event_key, event)
                store_proposal(self.store, event)
                self.store.put(self.tenant, "mail_message", digest([self.mailbox, message.id]),
                               {"message_id": message.id, "event_id": event_key, "mailbox": self.mailbox})
                self.store.audit(AuditEvent(tenant_id=self.tenant, source="microsoft_graph",
                    actor_id="FreightDesk/Avery", event="MAIL_DISCOVERED",
                    explanation="Bounded intake; extracted claims remain unverified proposals",
                    facts={"intent": classification.intent, "matched": match["shipment_id"] is not None}))
                count += 1
        return count

    def _model_audit(self, entry):
        with self.store.transaction():
            self.store.audit(AuditEvent(tenant_id=self.tenant, source="model", actor_id="FreightDesk/Avery",
                event=entry["event"], explanation="Minimal untrusted mail context supplied for structured classification",
                facts={"characters": entry.get("characters", 0)}))
