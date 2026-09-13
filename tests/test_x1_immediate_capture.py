"""Offline immediate capture dispatch, acknowledgement and stage-deadline fixtures."""
import subprocess
from uuid import uuid4
import pytest
from tests.test_ascend_x1_controller import repo as repo
from tests.test_ascend_x1_runtime import runtime as runtime, wake, result
from tests.test_ascend_mapping_orchestrator import orchestrated as orchestrated, session_step
from tests.test_x1_document_lifecycle import proof
from executors.ascend_extension.bridge_build import BUILD
from executors.ascend_extension.mapping_orchestrator import CAPTURE_DISPATCH_SECONDS, CAPTURE_ACK_SECONDS, CAPTURE_COMPLETE_SECONDS


def test_worker_open_before_start_needs_no_navigation_event():
    r=subprocess.run(['node','scripts/check-x1-immediate-capture.js'],capture_output=True,text=True,timeout=20)
    assert r.returncode==0,r.stdout+r.stderr


def ack(controller,d):
    controller.capture_ack(dict(kind='RUNTIME_CAPTURE_ACK',request_id=uuid4().hex,command_request_id=d['command']['request_id'],route=d['route']))


@pytest.mark.parametrize('failure',['dispatch','ack','complete','session'])
def test_short_stage_deadlines_cleanup(orchestrated,failure):
    o,access,controller,now=orchestrated
    o.start(owner_authorized=True)
    if failure=='session':
        wake(controller, build=BUILD, handshake=proof(), owner_present=True)
        o.tick()  # Readiness starts the session deadline; command receipt is withheld.
        now[0]+=31
        response=o.tick()
        expected='SESSION_PROOF_TIMEOUT'
    else:
        response=session_step(o,controller)
        assert response['stage']=='CAPTURE_CURRENT_WORKSPACE_NOW'
        assert response['capture_dispatch_state']=='QUEUED'
        if failure=='dispatch':
            now[0]+=CAPTURE_DISPATCH_SECONDS
            expected='CURRENT_LOAD_CAPTURE_NOT_DISPATCHED'
        else:
            session_step(o,controller)
            d=wake(controller,build=BUILD,handshake=proof())
            assert d['command']['operation']=='ASCEND_MAP_WORKSPACE'
            if failure=='ack':
                now[0]+=CAPTURE_ACK_SECONDS
                expected='CAPTURE_ACKNOWLEDGEMENT_TIMEOUT'
            else:
                ack(controller,d)
                now[0]+=CAPTURE_COMPLETE_SECONDS
                expected='WORKSPACE_CAPTURE_TIMEOUT'
        response=o.tick()
    assert response['stage']=='STOPPED'
    assert o.status(advanced=True)['advanced']['stop_code']==expected
    assert response['cleanup_complete'] and access.status()['read_access']=='REVOKED'


def test_dispatch_ack_completion_are_distinct(orchestrated):
    from tests.test_x1_auto_map import mapped
    o,_,controller,_=orchestrated
    o.start(owner_authorized=True)
    session_step(o,controller)
    session_step(o,controller)
    d=wake(controller,build=BUILD,handshake=proof())
    response=o.tick()
    assert response['capture_dispatch_state']=='DISPATCHED'
    assert response['capture_acknowledged_at'] is None
    ack(controller,d)
    assert o.tick()['capture_dispatch_state']=='ACKNOWLEDGED'
    with pytest.raises(PermissionError):
        ack(controller,d)
    controller.finish(result(d,mapped()))
    response=o.tick()
    assert response['capture_dispatch_state']=='COMPLETED'
    assert response['capture_completed_at'] is not None
    assert response['production_writes'] is False


@pytest.mark.parametrize('code,expected',[('MAPPING_OWNER_NOT_PRESENT','NO_FOREGROUND_ASCEND_WORKSPACE'),('EXPECTED_LOAD_NOT_OPEN','EXPECTED_LOAD_NOT_OPEN'),('STARTING_SECTION_MISMATCH','STARTING_SECTION_MISMATCH')])
def test_real_foreground_and_target_failures_never_become_passive_wait(orchestrated,code,expected):
    o,access,controller,_=orchestrated
    o.start(owner_authorized=True)
    session_step(o,controller)
    session_step(o,controller)
    d=wake(controller,build=BUILD,handshake=proof())
    controller.finish(result(d,None,code))
    response=o.tick()
    assert response['stage']=='STOPPED'
    assert o.status(advanced=True)['advanced']['stop_code']==expected
    assert access.status()['read_access']=='REVOKED'
