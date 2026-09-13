"""Offline session handoff cause preservation; no vendor or live profile execution."""
import json
from uuid import uuid4

import pytest

from executors.ascend_extension.bridge_build import BUILD
from executors.ascend_extension.mapping_orchestrator import MappingIntent
from tests.test_ascend_mapping_orchestrator import orchestrated as orchestrated, session_step
from tests.test_ascend_x1_controller import repo as repo
from tests.test_ascend_x1_runtime import runtime as runtime


@pytest.mark.parametrize('underlying,predicate', [
    ('DOCUMENT_CHANGED', 'DOCUMENT_BINDING_CHANGED_BEFORE_CAPTURE_DISPATCH'),
    ('TAB_STATE_CHANGED', 'TAB_BINDING_CHANGED_BEFORE_CAPTURE_DISPATCH'),
    ('CONTENT_SCRIPT_PORT_STALE', 'CONTENT_CONNECTION_LOST_BEFORE_CAPTURE_DISPATCH'),
    ('CONTENT_SCRIPT_MISSING', 'CONTENT_CONNECTION_MISSING_BEFORE_CAPTURE_DISPATCH'),
])
def test_proved_new_lease_then_routing_failure_preserves_exact_cause(orchestrated, underlying, predicate):
    o, access, controller, _ = orchestrated
    o.start(MappingIntent(causal_trace=True), owner_authorized=True)
    session_step(o, controller)  # First verified session -> replacement mapping lease and queued capture.
    assert o.status()['capture_dispatch_state'] == 'QUEUED'
    session_step(o, controller)  # The replacement lease's own session proof succeeds.
    assert access.status()['session'] == 'AUTHENTICATED'
    controller.wake(dict(kind='RUNTIME_WAKE', request_id=uuid4().hex, build=BUILD,
        route=None, routing_state='TAB_DISCOVERY_FAILED', eligible_tab_count=1, routing_error=underlying))
    stopped = o.tick()
    assert stopped['stage'] == 'STOPPED'
    assert stopped['safe_stop_code'] == underlying
    assert stopped['failed_predicate'] == predicate
    assert stopped['last_completed_dom_stage'] is None
    assert stopped['capture_dispatch_state'] == 'QUEUED'
    assert stopped['capture_dispatched_at'] is None and stopped['capture_acknowledged_at'] is None
    assert stopped['cleanup_state'] == 'COMPLETE' and not stopped['retry_safe']
    with access.database(readonly=True) as db:
        assert db.execute('SELECT COUNT(*) FROM runtime_capture_events').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM runtime_provider_maps').fetchone()[0] == 0
    with o.database(readonly=True) as db:
        events = [json.loads(row[0]) for row in db.execute('SELECT body FROM events')]
    failure = next(event for event in reversed(events) if event.get('safe_stop_code'))
    assert failure['safe_stop_code'] == underlying and failure['failed_predicate'] == predicate
    o.tick()
    assert access.status()['read_access'] == 'REVOKED'  # No reproof or retry of a changed document.


def test_expected_lease_reset_without_error_waits_for_fresh_proof(orchestrated):
    o, access, controller, _ = orchestrated
    o.start(owner_authorized=True)
    session_step(o, controller)
    assert access.status()['session'] == 'UNKNOWN'
    state = o.tick()
    assert state['stage'] == 'VERIFY_SESSION'
    assert state['safe_stop_code'] is None and state['failed_predicate'] is None
    assert state['capture_dispatch_state'] == 'QUEUED'
    session_step(o, controller)
    assert access.status()['session'] == 'AUTHENTICATED'


def test_job_and_queue_trace_follow_durable_commits(orchestrated, monkeypatch):
    o, access, controller, _ = orchestrated
    events = []
    causal, notify = access.causal_event, access.notify_mapping_job
    def record(event, **kwargs):
        with o.database(readonly=True) as db:
            assert o._load(db)['owner_authorized'] is True
        lease = access.check()
        assert lease['mapping']['orchestrated'] is True
        events.append(event)
        return causal(event, **kwargs)
    def wake():
        response = notify()
        events.append('WAKE_WRITTEN')
        return response
    monkeypatch.setattr(access, 'causal_event', record)
    monkeypatch.setattr(access, 'notify_mapping_job', wake)
    o.start(MappingIntent(causal_trace=True), owner_authorized=True)
    assert events[:2] == ['JOB_COMMITTED', 'WAKE_WRITTEN']
    session_step(o, controller)
    assert events.count('JOB_COMMITTED') == 1
    assert events.index('CAPTURE_QUEUED') < len(events) - 1
    assert events[-1] == 'WAKE_WRITTEN'


def test_unrelated_read_does_not_receive_job_trace(orchestrated, monkeypatch):
    o, access, _, _ = orchestrated
    access.enable(owner_authorized=True)
    events = []
    monkeypatch.setattr(access, 'causal_event', lambda event, **kwargs: events.append(event))
    assert o.start(MappingIntent(causal_trace=True), owner_authorized=True)['stage'] == 'WAITING_FOR_READ_JOB'
    assert events == []
    access.disable(owner_authorized=True)
    o.tick()
    assert events == ['JOB_COMMITTED']


def test_trace_bound_preserves_safe_stop_at_outer_commit_boundary(orchestrated, monkeypatch):
    o, access, _, _ = orchestrated
    def bounded(event, **kwargs):
        raise PermissionError('CAUSAL_TRACE_BOUND')
    monkeypatch.setattr(access, 'causal_event', bounded)
    stopped = o.start(MappingIntent(causal_trace=True), owner_authorized=True)
    assert stopped['safe_stop_code'] == 'CAUSAL_TRACE_BOUND'
    assert stopped['stage'] == 'STOPPED' and stopped['cleanup_state'] == 'COMPLETE'
    assert access.status()['read_access'] == 'REVOKED'


def test_normal_and_legacy_intents_do_not_enable_causal_diagnostics(orchestrated, monkeypatch):
    o, access, controller, _ = orchestrated
    events = []
    monkeypatch.setattr(access, 'causal_event', lambda event, **kwargs: events.append(event))
    o.start(owner_authorized=True)
    assert access.check()['mapping']['causal_trace'] is False
    with o.database() as db:
        job = o._load(db)
        job['intent'].pop('causal_trace')  # Existing persisted jobs predate the opt-in flag.
        o._save(db, job)
    session_step(o, controller)
    assert access.check()['mapping']['causal_trace'] is False
    assert events == []
