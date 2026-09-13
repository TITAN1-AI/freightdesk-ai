"""Typed extension reads under FreightDesk policy; no generic selectors, JS, writes or retries."""
import re
from uuid import uuid4

from app.models.domain import ActionPolicy, utcnow
from executors.ascend_extension.contracts import ReadCommand
from executors.ascend_extension.native import NativeBridgeInterface, canonical

BOOLS = {'session_authenticated','login_form_present','carrier_presence','driver_presence','power_unit_presence',
    'trailer_presence','exact_row','opener_located','identity_verified','stop_section_presence','appointment_section_presence',
    'opener_belongs_to_row','unique_panel','detail_field_match','selection_transition'}
IDS = {'load_id','expected_load_id','provider_observed_load_id','row_load_id'}
ENUMS = {
    'tenant_identity_source': {'OWNER_ATTESTED'}, 'path': {'/','/loads','/login.html','UNKNOWN'},
    'source_view': {'ACTIVE_LOADS'}, 'coverage': {'VISIBLE_BOARD_ONLY'}, 'scope': {'OBSERVATION_ONLY'},
    'strategy': {'PROVIDER_DETAIL_FIELD','PROVIDER_OPENER_BINDING','PROVIDER_SELECTED_ROW_BINDING'},
    'source': {'ACTIVE_LOADS_BOARD','BOARD_FACTS_AND_DETAIL_IDENTITY'}, 'mapping': {'UNKNOWN'},
    'relationship_attribute': {'aria-controls','data-target','data-bs-target','href'},
    'load_status': {'Active','Available','Assigned','Booked','Dispatched','In Transit','Delivered','Completed','UNKNOWN'},
    'truck_status': {'Active','Available','Assigned','Booked','Dispatched','In Transit','Delivered','Completed','UNKNOWN'},
}


def safe_result(value: dict) -> dict:
    """Reject unknown/private fields, rather than trusting an extension/native host response."""
    def visit(data):
        if not isinstance(data, dict):
            raise ValueError('bridge_result_shape_invalid')
        for key, val in data.items():
            if key in BOOLS:
                valid = type(val) is bool
            elif key in IDS:
                valid = isinstance(val, str) and re.fullmatch(r'\d{1,20}', val)
            elif key in ENUMS:
                valid = isinstance(val, str) and val in ENUMS[key] or key == 'relationship_attribute' and val is None
            elif key in {'pick_date', 'drop_date'}:
                valid = val is None or isinstance(val, str) and re.fullmatch(r'\d{2}/\d{2}/\d{4}', val)
            elif key == 'revision':
                valid = isinstance(val, str) and re.fullmatch('[a-f0-9]{64}', val)
            elif key in {'row_dom_path', 'opener_dom_path', 'panel_dom_path'}:
                valid = isinstance(val, str) and len(val) <= 2048 and re.fullmatch(
                    r'[a-z]+:nth-child\([1-9]\d*\)( > [a-z]+:nth-child\([1-9]\d*\))*', val)
            elif key in {'identity', 'evidence'}:
                visit(val)
                valid = True
            elif key == 'rows':
                valid = isinstance(val, list) and len(val) <= 100
                if valid:
                    for row in val:
                        visit(row)
            elif key == 'nav_markers':
                valid = isinstance(val, list) and len(val) <= 8 and all(v in
                    ('Dashboard','Loads','Customers','Carriers','Locations','Reporting','Accounting','Settings') for v in val)
            elif key in {'stops', 'appointments'}:
                valid = val is None  # No fabricated complete stops/appointment semantics in X1.
            else:
                valid = False
            if not valid:
                raise ValueError('bridge_result_field_invalid')
    if len(canonical(value)) > 65536:
        raise ValueError('bridge_result_bound')
    visit(value)
    return value


class AscendExtensionExecutor:
    """Satisfies BrowserExecutor's surface with blocked generic navigation/selector paths.

    New consumers use execute_read; legacy adapters cannot silently pass selector/code payloads through.
    """
    url = 'https://ascendtms.com'
    status = 'OFFLINE_X1'

    def __init__(self, policy, running, audit, *, transport=None, approved_loads=(), live_enabled=False):
        self.policy, self.running, self.audit = policy, running, audit
        self.transport = transport or NativeBridgeInterface()
        self.approved_loads = frozenset(approved_loads)
        self.live_enabled = live_enabled
        self.used = set()

    async def execute_read(self, command: ReadCommand) -> dict:
        # Validate again at this boundary even if the caller uses an untrusted model_construct result.
        command = ReadCommand.model_validate(command.model_dump())
        event = {'executor':'AscendExtensionExecutor', 'request_id': command.request_id,
            'operation':command.operation, 'tenant_id':command.tenant_id, 'actor':command.actor, 'load_id':command.load_id,
            'observed_at':utcnow().isoformat()}
        try:
            if not self.live_enabled:
                raise PermissionError('production_extension_bridge_disabled')
            if not self.running() or self.policy.evaluate('read_ascend') != ActionPolicy.ALLOW:
                raise PermissionError('read_policy_denied')
            if command.load_id is not None and command.load_id not in self.approved_loads:
                raise PermissionError('load_scope_denied')
            if command.request_id in self.used:
                raise PermissionError('request_consumed_no_retry')
            self.used.add(command.request_id)
            self.audit(dict(event, outcome='AUTHORIZED_READ'))
            result = safe_result(await self.transport.exchange(command.model_dump()))
            if not self.running() or self.policy.evaluate('read_ascend') != ActionPolicy.ALLOW:
                raise PermissionError('read_policy_changed')
            if command.operation in {'ASCEND_READ_LOAD','ASCEND_READ_STOPS','ASCEND_READ_ASSIGNMENT'}:
                identity = result.get('identity', {})
                if (result.get('load_id') != command.load_id or identity.get('expected_load_id') != command.load_id or
                    identity.get('provider_observed_load_id') != command.load_id or not identity.get('strategy')):
                    raise PermissionError('provider_identity_unverified')
            self.audit(dict(event, outcome='READ_OBSERVED_UNVERIFIED_PROPOSAL', identity=result.get('identity')))
            return result
        except Exception:
            self.audit(dict(event, outcome='READ_STOPPED'))
            raise PermissionError('bounded_extension_read_stopped') from None

    async def navigate(self, url):
        raise PermissionError('generic_extension_navigation_disabled')

    async def read(self, field):
        if field != 'session_state':
            raise PermissionError('generic_extension_selector_disabled')
        return await self.execute_read(ReadCommand(request_id=uuid4().hex, operation='ASCEND_GET_SESSION_STATE'))

    async def wait_ready(self, field):
        if field != 'session_state' or not (await self.read(field)).get('session_authenticated'):
            raise PermissionError('extension_session_unverified')
