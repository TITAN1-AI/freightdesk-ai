"""All evidence is synthetic. No live browser, host, enrollment or vendor execution."""
import json
import sqlite3

import pytest

from executors.ascend_extension.mapping_orchestrator import MappingIntent, MappingOrchestrator
from executors.ascend_extension.bridge_build import BUILD
from tests.test_ascend_x1_controller import repo as repo, session
from tests.test_ascend_x1_runtime import runtime as runtime, wake, result
from tests.test_x1_document_lifecycle import proof
from tests.test_x1_auto_map import mapped
from tests.test_x1_workspace_mapping import approval


@pytest.fixture
def orchestrated(runtime):
    access, controller, now, *_ = runtime
    controller.status()  # Synthetic paired host heartbeat, not real enrollment.
    return MappingOrchestrator(access), access, controller, now


def session_step(o, controller):
    d = wake(controller, build=BUILD, handshake=proof())
    assert d['command']['operation'] == 'ASCEND_GET_SESSION_STATE', d
    controller.finish(result(d, session()))
    return o.tick()


def starting_capture(o, controller, number='1755'):
    session_step(o, controller)  # probe-only grant -> mapping grant
    session_step(o, controller)  # new lease needs fresh session proof
    d = wake(controller, build=BUILD, handshake=proof())
    assert d['command']['operation'] == 'ASCEND_MAP_WORKSPACE', d
    controller.finish(result(d, mapped(number, at=o.clock())))
    return o.tick()


def test_one_click_preflight_ids_probe_scope_and_audit(orchestrated):
    o, access, controller, _ = orchestrated
    before = o.status()
    assert before['status'] == 'IDLE'
    with pytest.raises(PermissionError):
        o.start()
    state = o.start(owner_authorized=True)
    assert state['stage'] == 'WAITING_FOR_OWNER_WORKSPACE', state
    assert access.check()['allowed_operations'] == ['ASCEND_GET_SESSION_STATE']
    with pytest.raises(PermissionError):
        access.request_mapping_capture(owner_authorized=True)
    ids = o.status(advanced=True)['advanced']['session_ids']
    assert len(ids) == 1 and ids[0].startswith('owner-x1-mapping-orch-')
    o.start(owner_authorized=True)
    assert o.status(advanced=True)['advanced']['session_ids'] == ids
    stopped = starting_capture(o, controller)
    assert stopped['stage'] == 'OWNER_REVIEW_REQUIRED', stopped
    assert stopped['workspaces_observed'] == 1
    assert stopped['review_sections'] == ['Load Basics', 'Customer Info']
    assert stopped['cleanup_complete'] is True
    assert access.status()['read_access'] == 'REVOKED'
    assert 'session_id' not in json.dumps(o.status())
    assert 'session_id' not in json.dumps(o.report())
    with o.database() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('DELETE FROM events')


def test_current_load_review_finishes_without_qualifying_auto(orchestrated):
    o, access, controller, _ = orchestrated
    o.start(owner_authorized=True)
    starting_capture(o, controller)
    response = o.review(['Load Basics', 'Customer Info'], owner_authorized=True)
    assert response['stage'] == 'COMPLETE', response
    assert response['maturity'] == 'REVIEWED_NAVIGATION'
    assert response['contracts_validated'] == 0
    assert response['production_writes'] is False and response['live_validated'] is False
    assert access.status()['read_access'] == 'REVOKED'
    assert o.report()['contracts'][0]['activation'] == 'CANDIDATE_ONLY'


def test_stale_mapping_cleanup_and_unrelated_access(orchestrated):
    o, access, controller, _ = orchestrated
    access.enable(mapping=approval(), owner_authorized=True)
    old = access.check()['mapping']['session_id']
    controller.status()
    o.start(owner_authorized=True)
    assert o.status()['stage'] == 'WAITING_FOR_READ_JOB'
    assert access.status()['mapping_session_id'] == old
    with access.database(readonly=True) as db:
        assert db.execute('SELECT 1 FROM runtime_mapping_sessions WHERE id=?',(old,)).fetchone()
    access.disable(owner_authorized=True)  # The unrelated owner read job ends independently.
    assert o.tick()['stage'] == 'WAITING_FOR_OWNER_WORKSPACE'
    assert access.status()['mapping_session_id'] != old
    o.control('cancel', owner_authorized=True)
    access.enable(owner_authorized=True)
    controller.status()
    response = o.start(owner_authorized=True)
    assert response['owner_action'] == 'READ_JOB_ACTIVE'
    assert access.status()['read_access'] == 'ENABLED'


@pytest.mark.parametrize('stop', ['cancel', 'pause', 'failure', 'session_loss', 'policy', 'timeout'])
def test_cleanup_and_no_blind_retry(orchestrated, stop):
    o, access, controller, now = orchestrated
    o.start(owner_authorized=True)
    session_step(o, controller)
    session_step(o, controller)
    d = wake(controller, build=BUILD, handshake=proof())
    if stop in {'cancel','pause'}:
        response = o.control(stop, owner_authorized=True)
    elif stop == 'policy':
        access.gate = lambda _: (_ for _ in ()).throw(PermissionError('READ_POLICY_BLOCKED'))
        response = o.tick()
    elif stop == 'timeout':
        now[0] += 601
        response = o.tick()
    else:
        controller.finish(result(d, None, 'SESSION_UNVERIFIED' if stop=='session_loss' else 'READ_TIMEOUT'))
        response = o.tick()
    assert response['stage'] in {'STOPPED', 'OWNER_REVIEW_REQUIRED'}
    assert response['cleanup_complete']
    assert response['retry_safe'] is False
    assert access.status()['read_access'] == 'REVOKED'
    count = len(o.status(advanced=True)['advanced']['session_ids'])
    o.tick()
    assert len(o.status(advanced=True)['advanced']['session_ids']) == count


def test_browser_restart_pre_capture_keeps_same_job(orchestrated):
    o, access, controller, now = orchestrated
    o.start(MappingIntent(scope='OWNER_NAVIGATION_OBSERVE'), owner_authorized=True)
    identifier = o.status(advanced=True)['advanced']['job_id']
    now[0] += 121
    state = MappingOrchestrator(access).tick()
    assert state['stage'] == 'VERIFY_SESSION'
    assert o.status(advanced=True)['advanced']['job_id'] == identifier
    # One bounded renewal of session-probe authority; no capture attempt is replayed.
    assert len(o.status(advanced=True)['advanced']['session_ids']) == 2
    controller.status()
    response = session_step(o, controller)
    assert response['stage'] == 'RESOLVE_WORKSPACE'


def test_operations_scope_is_not_guessed(orchestrated):
    o, _, controller, _ = orchestrated
    o.start(MappingIntent(scope='CURRENT_OPERATIONS'), owner_authorized=True)
    response = session_step(o, controller)
    assert response['owner_action'] == 'REVIEW_OPERATIONS_SCOPE'
    assert response['cleanup_complete']
    assert o.report()['operations_views']['PLANNING_LOADS']['contract'] == 'UNKNOWN'
    assert o.report()['contracts'] == []


def test_validation_cohort_review_auto_return_and_wait_for_owner(orchestrated):
    o, access, controller, _ = orchestrated
    o.start(MappingIntent(scope='VALIDATION_COHORT', load_ids=['1755','900001','900002']), owner_authorized=True)
    starting_capture(o, controller)
    response = o.review(['Load Basics','Customer Info'], owner_authorized=True)
    assert response['stage'] == 'AUTO_MAP', response
    session_step(o, controller)
    d = wake(controller, build=BUILD, handshake=proof())
    assert d['command']['operation'] == 'ASCEND_MAP_WORKSPACE'
    controller.finish(result(d, mapped()))
    o.tick()
    for section in ['Customer Info','Load Basics']:
        d = wake(controller, build=BUILD, handshake=proof())
        assert d['command']['operation'] == 'ASCEND_MAP_NAVIGATE_SECTION', d
        assert d['command']['load_id'] == '1755'
        controller.finish(result(d, mapped(section=section)))
        response = o.tick()
    assert response['stage'] == 'RESOLVE_WORKSPACE'
    assert response['owner_action'] == 'OPEN_APPROVED_LOAD'
    # No automatic load opener or further capture while owner remains on this workspace.
    assert 'command' not in wake(controller, build=BUILD, handshake=proof())
    with access.database(readonly=True) as db:
        assert db.execute('SELECT COUNT(*) FROM runtime_auto_map_cycles').fetchone()[0] == 1


def test_drift_preserves_evidence_and_stops(orchestrated):
    o, access, controller, _ = orchestrated
    o.start(owner_authorized=True)
    session_step(o, controller)
    session_step(o, controller)
    d = wake(controller, build=BUILD, handshake=proof())
    controller.finish(result(d, mapped()))
    # Fixture simulates prior contract comparison reporting drift, without changing raw values.
    original = o._records
    def drift(job):
        records, cycles = original(job)
        records[0]['structural_drift'] = True
        return records, cycles
    o._records = drift
    response = o.tick()
    assert response['stage'] == 'STOPPED' and response['drift_detected']
    assert response['cleanup_complete'] and o.report()['contracts']


def test_full_cohort_generalizes_then_current_auto_is_available(orchestrated):
    o, access, controller, now = orchestrated
    cohort = ['1755','900001','900002']
    o.start(MappingIntent(scope='VALIDATION_COHORT', load_ids=cohort), owner_authorized=True)
    starting_capture(o, controller)
    o.review(['Load Basics','Customer Info'], owner_authorized=True)
    for index, number in enumerate(cohort):
        if index:
            now[0] += 1
            wake(controller, build=BUILD, handshake=proof(), mapping_hint=True)
            o.tick()
        session_step(o, controller)
        d = wake(controller, build=BUILD, handshake=proof())
        controller.finish(result(d, mapped(number, at=now[0])))
        o.tick()
        for section in ['Customer Info','Load Basics']:
            d = wake(controller, build=BUILD, handshake=proof())
            controller.finish(result(d, mapped(number, section, at=now[0])))
            response = o.tick()
    assert response['stage'] == 'COMPLETE', response
    assert response['maturity'] == 'AUTO_MAP_VALIDATED'
    assert response['workspaces_observed'] == 3 and response['contracts_validated'] == 0
    assert access.status()['read_access'] == 'REVOKED'
    controller.status()
    o.start(owner_authorized=True)
    response = starting_capture(o, controller)
    assert response['stage'] == 'AUTO_MAP', response


def test_context_handoff_does_not_activate_values(orchestrated):
    from integrations.ascend.context_assembler import VerifiedAscendLoadContextAssembler
    o, _, controller, now = orchestrated
    o.start(owner_authorized=True)
    starting_capture(o, controller)
    context = o.provider_maps().assemble('1755', VerifiedAscendLoadContextAssembler(), now=now[0])
    assert context['identity']['value'] == '1755'
    assert all(v['value'] is None for k,v in context.items() if k != 'identity')


def test_crash_after_grant_adopts_audit_and_never_replays(orchestrated):
    o, access, _, _ = orchestrated
    o.start(owner_authorized=True)
    sid = access.status()['mapping_session_id']
    with o.database() as db:
        job = o._load(db)
        job['session_ids'] = []  # Synthetic coordinator checkpoint older than committed runtime grant.
        job['lease_session'] = None
        o._save(db, job)
    response = MappingOrchestrator(access).tick()
    assert response['stage'] == 'STOPPED' and response['cleanup_complete']
    assert o.status(advanced=True)['advanced']['session_ids'] == [sid]
    assert access.status()['read_access'] == 'REVOKED'


def test_observe_unchanged_capture_does_not_block_next_workspace(orchestrated):
    o, _, controller, now = orchestrated
    o.start(MappingIntent(scope='OWNER_NAVIGATION_OBSERVE'), owner_authorized=True)
    response = starting_capture(o, controller)
    assert response['workspaces_observed'] == 1
    for number in ['1755','900001']:
        now[0] += 1
        wake(controller, build=BUILD, handshake=proof(), mapping_hint=True)
        o.tick()
        session_step(o, controller)
        d = wake(controller, build=BUILD, handshake=proof())
        controller.finish(result(d, mapped(number, at=now[0])))
        response = o.tick()
    assert response['workspaces_observed'] == 2
    assert response['stage'] == 'RESOLVE_WORKSPACE'
    assert len(o.report()['contracts']) == 2
