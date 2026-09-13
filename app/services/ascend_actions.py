"""Controlled write foundation. Production transport execution is independently disabled."""
from datetime import timedelta

from pydantic import Field

from app.models.domain import ActionPolicy, AuditEvent, AuthorizedIdentity, Model, Role, utcnow
from app.services.mail_sync import digest
from integrations.ascend.models import OPERATIONS, POLICY_ACTIONS, AscendError

TENANT = 'booking-logistics'
PAYLOAD_FIELDS = {
    'create_load': {'customer', 'customer_reference', 'origin', 'destination', 'pickup_appointment',
                    'delivery_appointment', 'equipment', 'commodity', 'weight'},
    'update_load': {'customer_reference', 'equipment', 'commodity', 'weight'},
    'assign_carrier': {'carrier', 'carrier_mc', 'carrier_dot'},
    'update_driver_info': {'dispatcher', 'driver', 'driver_phone'},
    'update_truck_trailer': {'truck', 'trailer'}, 'update_pickup_eta': {'pickup_eta'},
    'update_delivery_eta': {'delivery_eta'}, 'update_status': {'status'},
    'update_rates': {'customer_revenue', 'total_expenses'}, 'add_note': {'note'},
    'upload_document': {'document_reference', 'document_hash'},
}


class WriteIntent(Model):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')
    load_number: str = Field(pattern=r'^\d{1,20}$')
    operation: str
    expected_version: str
    payload: dict[str, str] = Field(repr=False)


class AscendActionLedger:
    def __init__(self, store, policies, controls):
        self.store, self.policies, self.controls = store, policies, controls

    def actor(self, actor, owner=False):
        if not isinstance(actor, AuthorizedIdentity) or actor.tenant_id != TENANT or actor.role not in (
                {Role.OWNER} if owner else {Role.OWNER, Role.OPERATIONS_USER, Role.SYSTEM}):
            raise AscendError('ascend_actor_not_authorized')

    def audit(self, action, event):
        self.store.audit(AuditEvent(tenant_id=TENANT, actor_id='FreightDesk/Avery', source='AscendTMS',
            event=event, explanation='Historical-free bounded Ascend action; payload omitted',
            facts={'session_class':'Avery operational browser session', 'action_id':action['id'],
                   'operation':action['operation'], 'state':action['state'], 'attempts':action['attempts']}))

    def enqueue(self, actor, intent: WriteIntent):
        self.actor(actor)
        if intent.operation not in OPERATIONS:
            raise AscendError('ascend_operation_unsupported')
        if not intent.payload or set(intent.payload)-PAYLOAD_FIELDS[intent.operation] or any(
                not v.strip() or len(v) > 8000 for v in intent.payload.values()):
            raise AscendError('ascend_payload_invalid')
        action_name = POLICY_ACTIONS.get(intent.operation, intent.operation)
        policy = self.policies.evaluate(action_name)
        if policy == ActionPolicy.FORBIDDEN:
            raise AscendError('ascend_policy_forbidden')
        body = intent.model_dump(mode='json')
        fingerprint = digest(body)
        with self.store.transaction():
            try:
                prior = self.store.get(TENANT, 'ascend_action', intent.id)
            except KeyError:
                prior = None
            if prior:
                if prior['intent_hash'] != fingerprint:
                    raise AscendError('ascend_action_id_conflict')
                return prior
            action = {**body, 'policy_action':action_name, 'intent_hash':fingerprint,
                'state':'QUEUED' if policy == ActionPolicy.ALLOW and intent.operation != 'update_rates' else
                        'AWAITING_APPROVAL',
                'attempts':0, 'approved_by':None, 'approval_expires_at':None}
            self.store.put(TENANT, 'ascend_action', intent.id, action)
            self.audit(action, 'ASCEND_ACTION_PROPOSED')
            return action

    def approve(self, actor, action_id, reviewed_intent_hash):
        self.actor(actor, owner=True)
        with self.store.transaction():
            action = self.store.get(TENANT, 'ascend_action', action_id)
            if action['state'] != 'AWAITING_APPROVAL' or action['intent_hash'] != reviewed_intent_hash:
                raise AscendError('ascend_approval_binding_invalid')
            action.update(state='APPROVED', approved_by=actor.id,
                approval_expires_at=(utcnow()+timedelta(minutes=15)).isoformat())
            self.store.put(TENANT, 'ascend_action', action_id, action)
            self.audit(action, 'ASCEND_ACTION_APPROVED_EXECUTION_STILL_BLOCKED')
            return action

    async def execute_fixture(self, actor, action_id, transport):
        """Exercises the complete state machine with a fixture transport; never enables live writes."""
        self.actor(actor)
        if getattr(transport, 'fixture_only', False) is not True:
            raise AscendError('ascend_production_mutation_disabled')
        from datetime import datetime
        with self.store.transaction():
            action = self.store.get(TENANT, 'ascend_action', action_id)
            if action['attempts']:
                if action['state'] == 'EXECUTING':
                    action['state'] = 'UNCERTAIN'
                    self.store.put(TENANT, 'ascend_action', action_id, action)
                    self.audit(action, 'ASCEND_RECOVERY_REQUIRES_RECONCILIATION')
                return action
            policy = self.policies.evaluate(action['policy_action'])
            requires_approval = policy != ActionPolicy.ALLOW or action['operation'] == 'update_rates'
            if (policy == ActionPolicy.FORBIDDEN or action['state'] not in {'APPROVED','QUEUED'} or
                    (requires_approval and (not action['approved_by'] or
                     datetime.fromisoformat(action['approval_expires_at']) <= utcnow()))):
                raise AscendError('ascend_action_approval_or_policy_blocked')
        if not self.controls(action['load_number']):
            raise AscendError('ascend_paused_or_takeover')
        await transport.verify_account()
        before = await transport.read_current(action['load_number'])
        if before['load_number'] != action['load_number'] or before['version'] != action['expected_version']:
            raise AscendError('ascend_expected_state_changed')
        # Claim durably immediately before the single mutation. Recheck all application gates.
        with self.store.transaction():
            latest = self.store.get(TENANT, 'ascend_action', action_id)
            if latest['attempts']:
                raise AscendError('ascend_already_claimed')
            original = {k:latest[k] for k in ['id','load_number','operation','expected_version','payload']}
            if digest(original) != latest['intent_hash'] or latest['intent_hash'] != action['intent_hash']:
                raise AscendError('ascend_payload_changed')
            current_policy = self.policies.evaluate(action['policy_action'])
            needs_approval = current_policy != ActionPolicy.ALLOW or action['operation'] == 'update_rates'
            if (not self.controls(action['load_number']) or current_policy == ActionPolicy.FORBIDDEN or
                    latest['state'] not in {'APPROVED','QUEUED'} or (needs_approval and
                    (not latest['approved_by'] or datetime.fromisoformat(latest['approval_expires_at']) <= utcnow()))):
                raise AscendError('ascend_authority_changed')
            action.update(state='EXECUTING', attempts=1)
            self.store.put(TENANT, 'ascend_action', action_id, action)
            self.audit(action, 'ASCEND_FIXTURE_MUTATION_CLAIMED')
        try:
            await transport.mutate(action['operation'], action['load_number'], action['payload'])
            await transport.verify_account()
            after = await transport.read_current(action['load_number'])
            verified = (after['load_number'] == action['load_number'] and
                        all(after['fields'].get(k) == v for k, v in action['payload'].items()))
            action['state'] = 'VERIFIED_FIXTURE' if verified else 'UNCERTAIN'
        except Exception:
            action['state'] = 'UNCERTAIN'
        with self.store.transaction():
            self.store.put(TENANT, 'ascend_action', action_id, action)
            self.audit(action, 'ASCEND_FIXTURE_RESULT_RECORDED')
        return action
