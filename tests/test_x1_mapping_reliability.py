"""Reliability regressions use synthetic receipts and local fixture stores only."""
import asyncio
import json
from uuid import uuid4

import pytest

from app.api import ascend_mapping
from executors.ascend_extension.bridge_build import BUILD
from executors.ascend_extension.mapping_orchestrator import MappingIntent
from executors.ascend_extension.mapping_store import persist_map
from scripts.review_x1_mapping_state import check_cross_load_variation, check_read_job_wait, synthetic_map
from tests.test_ascend_mapping_orchestrator import orchestrated as orchestrated, session_step, starting_capture
from tests.test_ascend_x1_controller import repo as repo, session
from tests.test_ascend_x1_runtime import runtime as runtime, result, wake
from tests.test_x1_document_lifecycle import proof
from tests.test_x1_section_diagnostics import section_diagnostic
from tests.test_x1_workspace_mapping import approval, provider_map


def test_review_reproductions_now_assert_correct_behavior():
    assert check_read_job_wait()['passed']
    assert check_cross_load_variation()['passed']


def test_no_capture_deadline_before_foreground_readiness(orchestrated):
    o, access, controller, now = orchestrated
    first = o.start(owner_authorized=True)
    assert first['stage'] == 'WAITING_FOR_OWNER_WORKSPACE'
    sequence = access.mapping_wake_sequence()
    assert sequence == 1
    now[0] += 45
    absent = wake(controller, build=BUILD, handshake=proof(), owner_present=False)
    assert 'command' not in absent
    status = o.tick()
    assert status['stage'] == 'WAITING_FOR_OWNER_WORKSPACE'
    assert status['safe_stop_code'] is None and status['capture_requested_at'] is None
    assert access.status()['mapping_capture_count'] == 0
    assert access.mapping_wake_sequence() == sequence
    dispatch = wake(controller, build=BUILD, handshake=proof(), owner_present=True)
    assert dispatch['command']['operation'] == 'ASCEND_GET_SESSION_STATE'
    controller.finish(result(dispatch, session()))
    ready = o.tick()
    assert ready['capture_dispatch_state'] == 'QUEUED'
    assert ready['capture_requested_at'] == now[0]
    assert access.mapping_wake_sequence() == sequence + 1


def test_unrelated_dependency_finishes_without_revocation_or_new_job(orchestrated):
    o, access, controller, _ = orchestrated
    access.enable(owner_authorized=True)
    unrelated = access.check()['generation']
    controller.status()
    status = o.start(owner_authorized=True)
    job_id = o.status(advanced=True)['advanced']['job_id']
    assert status['stage'] == 'WAITING_FOR_READ_JOB'
    assert access.check()['generation'] == unrelated and access.status()['read_access'] == 'ENABLED'
    assert o.tick()['stage'] == 'WAITING_FOR_READ_JOB'
    access.disable(owner_authorized=True)
    resumed = o.tick()
    assert resumed['stage'] == 'WAITING_FOR_OWNER_WORKSPACE'
    assert o.status(advanced=True)['advanced']['job_id'] == job_id
    assert len(o.status(advanced=True)['advanced']['session_ids']) == 1


def test_paused_job_resume_waits_for_new_unrelated_authority(orchestrated):
    o, access, controller, _ = orchestrated
    o.start(owner_authorized=True)
    o.control('pause', owner_authorized=True)
    access.enable(owner_authorized=True)
    generation = access.check()['generation']
    controller.status()
    before = len(o.status(advanced=True)['advanced']['session_ids'])
    response = o.control('resume', owner_authorized=True)
    assert response['stage'] == 'WAITING_FOR_READ_JOB'
    assert access.check()['generation'] == generation
    assert len(o.status(advanced=True)['advanced']['session_ids']) == before
    access.disable(owner_authorized=True)
    resumed = o.tick()
    assert resumed['stage'] == 'WAITING_FOR_OWNER_WORKSPACE'
    assert access.check()['mapping']['session_only'] is True


def test_reviewed_auto_continuation_waits_for_unrelated_authority(orchestrated):
    o, access, controller, _ = orchestrated
    o.start(MappingIntent(scope='VALIDATION_COHORT', load_ids=['1755', '900001', '900002']), owner_authorized=True)
    starting_capture(o, controller)
    access.enable(owner_authorized=True)
    generation = access.check()['generation']
    controller.status()
    reviewed = o.review(['Load Basics', 'Customer Info'], owner_authorized=True)
    assert reviewed['stage'] == 'WAITING_FOR_READ_JOB'
    assert reviewed['maturity'] == 'REVIEWED_NAVIGATION'
    assert access.check()['generation'] == generation
    access.disable(owner_authorized=True)
    resumed = o.tick()
    assert resumed['stage'] == 'WAITING_FOR_OWNER_WORKSPACE'
    lease = access.check()
    assert lease['mapping']['operation_mode'] == 'AUTO_MAP'
    assert lease['mapping']['session_only'] is False
    session_step(o, controller)
    assert o.status()['stage'] == 'AUTO_MAP'
    assert o.status()['capture_dispatch_state'] == 'QUEUED'


def test_lease_acquisition_race_is_atomic_dependency_wait(orchestrated):
    o, access, _, _ = orchestrated
    original = access.enable
    raced = []
    def enable(**kwargs):
        if kwargs.get('mapping') and not raced:
            original(owner_authorized=True)
            raced.append(access.check()['generation'])
        return original(**kwargs)
    access.enable = enable
    result = o.start(owner_authorized=True)
    assert result['stage'] == 'WAITING_FOR_READ_JOB'
    assert access.check()['generation'] == raced[0]
    with access.database(readonly=True) as db:
        assert db.execute('SELECT COUNT(*) FROM runtime_mapping_sessions').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM runtime_leases').fetchone()[0] == 1


def test_cleanup_cannot_revoke_concurrently_replaced_authority(orchestrated):
    o, access, _, _ = orchestrated
    o.start(owner_authorized=True)
    original_status, original_enable = access.status, access.enable
    replaced = []
    def status():
        old = original_status()
        if old['mapping_mode'] and not replaced:
            # Replacement occurs after _lease_matches observes the old mapping authority.
            replaced.append(True)
            original_enable(owner_authorized=True)
        return old
    access.status = status
    result = o.control('cancel', owner_authorized=True)
    assert result['cleanup_state'] == 'COMPLETE'
    assert original_status()['read_access'] == 'ENABLED'
    assert original_status()['mapping_mode'] is False


def test_capture_queue_rejects_a_different_mapping_session(runtime):
    access, _, _, *_ = runtime
    first = approval()
    access.enable(mapping=first, owner_authorized=True)
    other = first.model_copy(update={'session_id': 'owner-x1-mapping-unrelated-race'})
    access.enable(mapping=other, owner_authorized=True)
    with pytest.raises(PermissionError, match='READ_LEASE_REVOKED'):
        access.request_mapping_capture(owner_authorized=True, expected_mapping_session_id=first.session_id)
    assert access.status()['read_access'] == 'ENABLED'
    assert access.status()['mapping_session_id'] == other.session_id
    assert access.status()['mapping_capture_requested'] is False


def test_direct_coordinator_failure_commits_and_notifies_without_another_tick(orchestrated):
    o, access, _, _ = orchestrated
    o.start(owner_authorized=True)
    previous = access.mapping_wake_sequence()
    status = o.coordinator_failed()
    assert status['safe_stop_code'] == 'COORDINATOR_FAILED'
    assert status['cleanup_state'] == 'COMPLETE'
    assert o.status()['stage'] == 'STOPPED'
    assert access.mapping_wake_sequence() == previous + 1


def test_expired_navigation_review_persists_stop_and_cleanup_notification(orchestrated):
    o, access, controller, now = orchestrated
    o.start(owner_authorized=True)
    starting_capture(o, controller)
    previous = access.mapping_wake_sequence()
    now[0] += 601
    status = o.review(['Load Basics'], owner_authorized=True)
    assert status['safe_stop_code'] == 'READ_LEASE_EXPIRED'
    assert status['cleanup_state'] == 'COMPLETE'
    assert o.status()['stage'] == 'STOPPED'
    assert o.status()['safe_stop_code'] == 'READ_LEASE_EXPIRED'
    assert access.mapping_wake_sequence() == previous + 1
    assert o.status()['maturity'] == 'OBSERVED'


@pytest.mark.parametrize('route_detail, expected_predicate', [
    (None, 'UNIQUE_CANDIDATE_COUNT_ZERO'),
    (dict(strategy='SELECTED_CURRENT_ROUTE_AND_MATCHING_HEADING', route_anchor_candidate_count=1,
        matching_heading_count=1, ancestor_count=0, eligible_root_count=0, ancestor_candidates=[],
        failed_predicate='NO_ELIGIBLE_ROOT'), 'NO_ELIGIBLE_ROOT'),
    (dict(strategy='SELECTED_CURRENT_ROUTE_AND_MATCHING_HEADING', route_anchor_candidate_count=1,
        matching_heading_count=1, ancestor_count=0, eligible_root_count=0, ancestor_candidates=[],
        failed_predicate='NO_ELIGIBLE_ROOT', sibling_form_diagnostic=dict(
            strategy='NEAREST_HEADING_CONTEXT_UNIQUE_LATER_FORM_REGION', context_count=1,
            context_candidates=[dict(ancestor_depth=1, direct_child_count=3, visible_form_count=2,
                heading_child_count=1, form_bearing_child_count=2, predicate='FORM_CHILD_NOT_UNIQUE')],
            failed_predicate='FORM_CHILD_NOT_UNIQUE')), 'FORM_CHILD_NOT_UNIQUE'),
])
def test_normal_failure_report_has_precise_section_receipt(orchestrated, route_detail, expected_predicate):
    o, access, controller, _ = orchestrated
    o.start(owner_authorized=True)
    session_step(o, controller)
    session_step(o, controller)
    dispatch = wake(controller, build=BUILD, handshake=proof())
    for elapsed, stage in enumerate(['SESSION_VERIFIED', 'ENTITY_DISCOVERY', 'LOAD_WORKSPACE_CANDIDATE_FOUND', 'WORKSPACE_IDENTITY_VERIFIED'], 1):
        controller.mapping_progress(dict(kind='RUNTIME_MAPPING_PROGRESS', request_id=uuid4().hex,
            command_request_id=dispatch['command']['request_id'], route=dispatch['route'],
            diagnostic=dict(stage=stage, candidate_workspace_count=1, identity_signal_count=2,
                section_control_count=12, elapsed_ms=elapsed)))
    detail = section_diagnostic(route_heading_diagnostic=route_detail)
    controller.finish(result(dispatch, {'section_diagnostic': detail}, 'WORKSPACE_SECTION_UNVERIFIED'))
    status = o.tick()
    assert status['safe_stop_code'] == 'WORKSPACE_SECTION_UNVERIFIED'
    assert status['last_completed_dom_stage'] == 'WORKSPACE_IDENTITY_VERIFIED'
    assert status['failed_predicate'] == expected_predicate
    assert status['owner_action'] == 'REVIEW_CAPTURE_FAILURE' and status['owner_action_text']
    assert status['cleanup_state'] == 'COMPLETE'
    assert access.status()['read_access'] == 'REVOKED'
    with o.database(readonly=True) as db:
        events = [json.loads(row[0]) for row in db.execute('SELECT body FROM events')]
        other_gate = dict(o._load(db), stop_code='WORKSPACE_BOUND')
    receipt = next(event for event in reversed(events) if event.get('safe_stop_code'))
    assert receipt['safe_stop_code'] == 'WORKSPACE_SECTION_UNVERIFIED'
    assert receipt['failed_predicate'] == expected_predicate
    assert receipt['last_completed_dom_stage'] == 'WORKSPACE_IDENTITY_VERIFIED'
    assert o._public(other_gate)['failed_predicate'] == 'UNIQUE_CANDIDATE_COUNT_ZERO'


@pytest.mark.parametrize('cleanup_fails', [False, True])
def test_unexpected_coordinator_failure_is_persisted_and_sanitized(orchestrated, cleanup_fails):
    o, access, _, _ = orchestrated
    o.start(owner_authorized=True)
    def fail(*args, **kwargs):
        raise RuntimeError('PRIVATE_EXCEPTION_VALUE')
    o._advance = fail
    if cleanup_fails:
        access.disable = fail
    status = o.tick()
    assert status['safe_stop_code'] == 'COORDINATOR_FAILED'
    assert status['cleanup_state'] == ('INCOMPLETE' if cleanup_fails else 'COMPLETE')
    advanced = o.status(advanced=True)
    assert any(e.get('safe_stop_code') == 'COORDINATOR_FAILED' for e in advanced['advanced']['events'])
    assert 'PRIVATE' not in json.dumps(advanced)
    before = len(advanced['advanced']['session_ids'])
    o.tick()
    assert len(o.status(advanced=True)['advanced']['session_ids']) == before


def test_background_loop_records_an_unexpected_boundary_failure(orchestrated, monkeypatch):
    o, access, _, _ = orchestrated
    o.start(owner_authorized=True)
    def fail():
        raise RuntimeError('PRIVATE_EXCEPTION_VALUE')
    o.tick = fail
    monkeypatch.setattr(ascend_mapping, 'mapping_orchestrator', lambda: o)
    status = asyncio.run(ascend_mapping.mapping_loop_step())
    assert status['safe_stop_code'] == 'COORDINATOR_FAILED'
    assert access.status()['read_access'] == 'REVOKED'
    assert 'PRIVATE' not in json.dumps(o.status(advanced=True))


def test_passive_owner_absence_waits_without_consuming_capture(orchestrated):
    o, access, controller, now = orchestrated
    o.start(MappingIntent(scope='OWNER_NAVIGATION_OBSERVE'), owner_authorized=True)
    starting_capture(o, controller)
    before = access.status()['mapping_capture_count']
    now[0] += 1
    assert 'command' not in wake(controller, build=BUILD, handshake=proof(), owner_present=False)
    waiting = o.tick()
    assert waiting['stage'] == 'WAITING_FOR_OWNER_WORKSPACE'
    assert access.status()['read_access'] == 'ENABLED'
    assert access.status()['mapping_capture_count'] == before
    d = wake(controller, build=BUILD, handshake=proof(), owner_present=True)
    controller.finish(result(d, session()))
    assert o.tick()['stage'] == 'RESOLVE_WORKSPACE'


@pytest.mark.parametrize('change', ['same_load_fields', 'navigation', 'identity_topology'])
def test_true_safety_or_same_workspace_drift_still_fails_closed(runtime, change):
    from executors.ascend_extension.workspace_contracts import fingerprint
    access, _, _, *_ = runtime
    access.enable(mapping=approval(), owner_authorized=True)
    state, pending = {}, {'deadline': 1012.0, 'route': {'document_id': 'f'*32}}
    first = provider_map(extra=True)
    second = provider_map(number='1755' if change == 'same_load_fields' else '900001')
    if change == 'navigation':
        second['workspace']['section_controls'].append('Edit Stops')
    if change == 'identity_topology':
        second['workspace']['signals'].append(dict(kind='BREADCRUMB', load_id='900001', outside_child_section=True))
    second['workspace']['shell_fingerprint'] = fingerprint(dict(
        signals=sorted({s['kind'] for s in second['workspace']['signals']}), sections=second['workspace']['section_controls']))
    with access.database() as db:
        lease = {'mapping': approval().model_dump()}
        persist_map(db, state, lease, pending, first, 1000.0)
        observed = persist_map(db, state, lease, pending, second, 1000.0)
    assert observed['structural_drift'] and observed['change_kind'] == 'STRUCTURAL_DRIFT'
    assert not observed['cross_load_variation']


def test_cross_load_variation_preserves_candidate_evidence_and_coordinator_continues(orchestrated):
    o, access, controller, now = orchestrated
    o.start(MappingIntent(scope='OWNER_NAVIGATION_OBSERVE'), owner_authorized=True)
    session_step(o, controller)
    session_step(o, controller)
    dispatch = wake(controller, build=BUILD, handshake=proof())
    controller.finish(result(dispatch, synthetic_map('900101', optional_field=True)))
    assert o.tick()['workspaces_observed'] == 1
    now[0] += 1
    wake(controller, build=BUILD, handshake=proof(), mapping_hint=True)
    o.tick()
    session_step(o, controller)
    dispatch = wake(controller, build=BUILD, handshake=proof())
    second = synthetic_map('900102')
    second['workspace']['observed_at'] = now[0]
    for field in second['section']['fields']:
        field['observed_at'] = now[0]
    controller.finish(result(dispatch, second))
    response = o.tick()
    assert response['workspaces_observed'] == 2 and response['stage'] == 'RESOLVE_WORKSPACE'
    assert not response['drift_detected']
    with access.database(readonly=True) as db:
        records = [json.loads(row[0]) for row in db.execute('SELECT body FROM runtime_provider_maps')]
    assert records[-1]['change_kind'] == 'CROSS_LOAD_VARIATION'
    assert records[-1]['map']['activation'] == 'CANDIDATE_ONLY'
    o.control('cancel', owner_authorized=True)
    assert access.status()['read_access'] == 'REVOKED'
