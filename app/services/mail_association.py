"""Owner-reviewed conversation bindings; unverified facts are durable proposals only."""
from app.models.domain import AuditEvent, Role, utcnow


def approve_conversation_binding(store, actor, mailbox, conversation_id, shipment_id, known_shipments):
    if actor.role != Role.OWNER or actor.tenant_id != 'booking-logistics':
        raise PermissionError('Owner review required for conversation binding')
    if not conversation_id or not any(s.id == shipment_id and s.tenant_id == actor.tenant_id for s in known_shipments):
        raise ValueError('Exact known shipment and conversation required')
    from app.services.mail_sync import digest
    with store.transaction():
        store.put(actor.tenant_id, 'mail_conversation_binding', digest([mailbox, conversation_id]), {
            'mailbox': mailbox, 'conversation_id': conversation_id, 'shipment_id': shipment_id,
            'approved_by': actor.id, 'approved_at': utcnow().isoformat()})
        store.audit(AuditEvent(tenant_id=actor.tenant_id, actor_id=actor.id, source='mail_review',
            event='MAIL_CONVERSATION_BOUND', explanation='Owner reconciled thread to an exact canonical shipment'))


def bindings(store, tenant, mailbox):
    return {row['conversation_id']: row['shipment_id'] for row in store.all(tenant, 'mail_conversation_binding')
            if row['mailbox'] == mailbox}


def store_proposal(store, event):
    fields = event.extracted.model_dump(mode='json', exclude_none=True, exclude={'ambiguities', 'evidence'})
    if not fields:
        return
    store.put(event.tenant_id, 'mail_update_proposal', event.id, {
        'event_id': event.id, 'shipment_id': event.shipment_id, 'source_message_id': event.message.id,
        'fields': fields, 'evidence': [e.model_dump(mode='json') for e in event.extracted.evidence],
        'ambiguities': event.extracted.ambiguities, 'status': 'REVIEW_REQUIRED',
        'verified': False, 'applied': False})
