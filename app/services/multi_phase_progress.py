"""Sanitized append-only phase observations; never persist exception payloads."""
from uuid import uuid4

from app.models.domain import utcnow
from app.services.live_ops_carrierview import PICKUPS, DELIVERIES

SAFE_CODES = {
    'one_use_phase_consumed_no_retry','read_policy_not_allow','paused_or_human_takeover',
    'fresh_ascend_detail_evidence_required','owner_reconciled_exact_eleven_load_scope_required',
    'active_board_changed_during_details','ops_board_bound_exceeded','ops_board_headers_missing_or_ambiguous',
    'board_load_identity_unrecognized','board_duplicate_identity_conflict','ops_candidate_bound_exceeded',
    'active_loads_view_ambiguous_or_missing','active_loads_view_not_read_only',
    'discovery_policy_pause_or_expiry','discovery_session_not_authenticated',
    'exact_load_discovery_ambiguous_or_missing','exact_load_read_control_unknown','exact_load_read_control_ambiguous',
    'non_read_load_control_blocked','non_read_load_destination_blocked','detail_load_identity_unverified',
    'field_discovery_bound_exceeded','ops_detail_changed_or_exceeded_bound','ops_detail_load_mismatch',
    'ops_list_detail_date_conflict','owner_login_page_ambiguous','continuity_profile_or_channel_mismatch',
    'active_view_selection_not_confirmed','board_render_not_settled','board_presentation_wrapper_unknown',
    'board_presentation_control_ambiguous','board_presentation_control_not_safe','board_page_size_option_unverified',
    'board_filter_requires_observed_reset_contract','normalized_board_scope_mismatch',
    'detail_identity_origin_mismatch','detail_identity_scan_bound',
}
STAGES = {'preflight','phase_grant','browser_launch_owner_confirmation','active_loads_refresh',
    'active_loads_view_selection','data_grid_detection','board_reconciliation','load_detail_open',
    'detail_identity_verification','field_contract_extraction','stop_appointment_extraction',
    'driver_contact_extraction','per_load_reconciliation','final_board_freshness_check','persistence',
    'carrierview_read','outlook_read','local_report','complete','browser_close'}


def safe_failure(error):
    # Compare only single string arguments to fixed application-authored codes. No str(error)/tracebacks.
    code=error.args[0] if len(error.args)==1 and isinstance(error.args[0],str) else None
    if code in SAFE_CODES:
        return code,'A bounded read gate stopped the phase; inspect the recorded stage and code.'
    if isinstance(error,KeyError):
        return 'local_evidence_or_contract_key_missing','A required local record or contract field was missing.'
    if isinstance(error,AttributeError):
        return 'internal_attribute_error','An internal attribute lookup failed.'
    if isinstance(error,TimeoutError) or type(error).__name__=='TimeoutError':
        return 'bounded_read_timeout','The bounded read timed out.'
    return 'unexpected_phase_execution_error','An unexpected execution failure occurred; private details omitted.'


class PhaseProgress:
    def __init__(self,store,run_id,phase):
        self.store=store
        self.data={'run_id':run_id,'phase':phase,'execution_stage':'preflight',
            'affected_load_id':None,'completed_load_count':0,'initial_board_reconciled':None,
            'board_changed':None,'production_writes':False}

    def save(self,kind):
        self.store.put('booking-logistics',kind,self.data['run_id']+':'+uuid4().hex,
                       dict(self.data,observed_at=utcnow().isoformat()))

    def stage(self,name):
        if name not in STAGES:
            raise ValueError('invalid_progress_stage')
        self.data['execution_stage']=name
        self.save('multi_progress')

    def load(self,number):
        if number not in PICKUPS|DELIVERIES:
            raise ValueError('invalid_progress_load')
        self.data['affected_load_id']=number

    def completed(self):
        self.data['completed_load_count']+=1
        self.save('multi_progress')

    def failed(self,error):
        code,reason=safe_failure(error)
        self.data.update(status='STOPPED_MULTI_SYSTEM',error_code=code,reason=reason)
        self.save('multi_failure')
        return dict(self.data)
