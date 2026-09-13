"""Real mapping execution chain; only Chrome API, provider page and local credentials are synthetic.

No installed host/profile or vendor access. Every browser request is fulfilled in memory.
All SQLite/enrollment fixtures live beneath pytest's explicitly selected Runtime TestRuns path.
"""
import asyncio
import copy
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from executors.ascend_extension.mapping_orchestrator import MappingIntent, MappingOrchestrator
from executors.ascend_extension.native import decode_message, encode_message
from executors.ascend_extension.runtime import RuntimeAccess, RuntimeController
from tests.test_ascend_x1_enrollment import enrollment as enrollment, enroll

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / 'extensions' / 'ascend-x1'


def provider_dom(number='900101', *, optional=True, section='Load Basics', linked=True):
    nav = '<nav>' + ''.join(f'<a>{label}</a>' for label in ['Dashboard', 'Loads', 'Customers', 'Carriers']) + '</nav>'
    controls = ''.join(f'<button type="button" role="tab" id="tab{i}" aria-selected="{str(label == section).lower()}" '
        f'aria-controls="panel{i}">{label}</button>' for i, label in enumerate(['Load Basics', 'Customer Info']))
    fields = '<label for="equipment">Equipment</label><input id="equipment" value="PRIVATE_NEVER_READ">'
    if optional:
        fields += '<label for="carrier">Carrier</label><input id="carrier" value="PRIVATE_NEVER_READ">'
    panels = ''.join(f'<section id="panel{i}" role="tabpanel" {"hidden" if label != section else ""}>'
        f'<h2>{label}</h2>{fields}<button type="button">Save</button></section>'
        for i, label in enumerate(['Load Basics', 'Customer Info']))
    body = nav + f'<main data-load-workspace data-load-id="{number}"><h1>Load #{number}</h1><div role="tablist">{controls}</div>{panels}</main>'
    if not linked:
        body = body.replace('aria-selected="true"', 'aria-selected="false"').replace('<h2>Load Basics</h2>', '<p>Unknown fixture section</p>')
    return body


@pytest.mark.parametrize('v2,sibling_first_capture,commit_failure', [
    (False, False, False), (False, True, False), (True, False, False), (True, True, False), (True, False, True), (True, False, 'GRAPH')])
def test_mapping_orchestrator_native_worker_dom_persistence(enrollment, tmp_path, sibling_first_capture, v2, commit_failure):
    async def exercise():
        from playwright.async_api import async_playwright

        offset = [0.0]
        def clock():
            return time.time() + offset[0]
        enrollment.test_clock[0] = time.time()
        host, _, package = enroll(enrollment)
        host.clock = clock
        kwargs = dict(clock=clock, enrollment_guard=enrollment.load, gate=lambda _: None)
        access, controller = RuntimeAccess(enrollment.repo, **kwargs), RuntimeController(enrollment.repo, **kwargs)
        host.runtime = controller
        if v2:
            from executors.webbridge_v2.runtime_bridge import install_offline
            adapter = install_offline(controller.access)
            accepted = []
            real_persist = adapter.persist
            def remember(db, state, lease, pending, raw, now):
                result = real_persist(db, state, lease, pending, raw, now)
                accepted.append(copy.deepcopy((state, lease, pending, raw, now)))
                return result
            adapter.persist = remember
            if commit_failure is True:
                def fail_commit():
                    raise RuntimeError('PRIVATE_DATABASE_FAILURE')
                adapter.before_completion = fail_commit
        controller.status()  # Existing authenticated fixture channel is connected; no lease.
        orchestrator = MappingOrchestrator(access)
        frames = []
        lost_notification = []

        async def host_wire(message):
            # Exercise actual native framing, HMAC/replay handling, host dispatch and receipt hooks.
            request = decode_message(encode_message(message))
            frames.append(request['envelope']['body']['kind'])
            body = request['envelope']['body']
            if v2 and not commit_failure and not lost_notification and body['kind'] == 'RUNTIME_RESULT' and body.get('evidence', {}).get('webbridge_v2'):
                # Model process loss after the runtime commit, before coordinator notification.
                # No receipt is mocked; the real host/controller/SQLite completion still executes.
                with patch.object(MappingOrchestrator, 'tick', return_value=None):
                    response = decode_message(encode_message(host.handle(request)))
                with access.database(readonly=True) as db:
                    assert db.execute('SELECT count(*) FROM runtime_v2_observations').fetchone()[0] == 1
                lost_notification.append(True)
            else:
                response = decode_message(encode_message(host.handle(request)))
            return response

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel='msedge', headless=True,
                env={**os.environ, 'TEMP': str(tmp_path), 'TMP': str(tmp_path)})
            context = await browser.new_context(service_workers='block')
            requests = []

            async def offline(route):
                requests.append('INTERCEPTED_FIXTURE_REQUEST')
                await route.fulfill(content_type='text/html', body='<title>Offline synthetic provider</title>')

            await context.route('**/*', offline)
            page = await context.new_page()
            await page.expose_function('fixtureHostWire', host_wire)
            try:
                await page.goto('https://ascendtms.com/loads')
                for name in ['build.js', 'contract.js', 'pairing.js', 'read-errors.js', 'load-board-view.js',
                             'detail-scope.js', 'webbridge.js', 'mapping-scope.js', 'workspace.js', 'reader.js', 'tab-router.js', 'runtime.js']:
                    await page.add_script_tag(path=str(EXT / name))
                await page.add_script_tag(path=str(ROOT / 'tests/fixtures/x1_mapping_chain.js'))
                if v2:
                    for name in ['semantics.js', 'core.js', 'compatibility.js']:
                        await page.add_script_tag(path=str(ROOT / 'extensions/webbridge-v2' / name))
                    await page.evaluate("()=>FreightDeskV2Compatibility.install({mode:'OFFLINE'})")
                    await page.evaluate("""()=>{
                      for(const prototype of [HTMLInputElement.prototype,HTMLSelectElement.prototype,HTMLTextAreaElement.prototype])
                        for(const name of ['value','selectedOptions','checked'])Object.defineProperty(prototype,name,{get(){throw Error('PRIVATE_ACCESS');}});
                      const W=FreightDeskWebBridge;
                      globalThis.FreightDeskWebBridge=Object.freeze({...W,LocatorGraph:{...W.LocatorGraph,build(){throw Error('LEGACY_VALUE_GRAPH_FORBIDDEN');}}});
                    }""")
                await page.add_script_tag(path=str(EXT / 'content.js'))
                await page.evaluate('a=>x1Chain.init(a)', dict(key=package['key'], session=host.auth.session_id,
                    incoming=host.auth._outgoing, expires=int(clock()+590)))
                sibling_dom = '<nav>'+''.join('<a>'+label+'</a>' for label in ['Dashboard', 'Loads', 'Customers', 'Carriers'])+'</nav>' \
                    '<main><h1>Load #900101</h1><div><div><h1>Load Basics</h1></div>' \
                    '<ul><li class="active"><a href="/loads">Load Basics</a></li><li><a href="/fixture-other">Customer Info</a></li></ul>' \
                    '<div><form><legend>Private fixture legend</legend><label for="fixture-field">Equipment</label>' \
                    '<input id="fixture-field" value="PRIVATE_NEVER_READ"><button>Save</button></form></div></div></main>'
                await page.evaluate('body=>document.body.innerHTML=body', sibling_dom if sibling_first_capture else provider_dom())
                if commit_failure == 'GRAPH':
                    # Legitimate V1 workspace, but V2's SMALLER wire budget must fail closed.
                    await page.evaluate("()=>document.querySelector('main').insertAdjacentHTML('beforeend','<div></div>'.repeat(80))")

                async def flush():
                    for _ in range(12):
                        await page.evaluate('()=>x1Chain.flush()')
                        assert (await page.evaluate('()=>x1Chain.summary()'))['errors'] == []
                        orchestrator.tick()
                        notification = host.poll_mapping_notification()
                        if notification is None:
                            break
                        await page.evaluate('m=>x1Chain.receive(m)', notification)

                async def notify():
                    message = host.poll_mapping_notification()
                    assert message and message['envelope']['body']['kind'] == 'RUNTIME_JOB_WAKE_NOTIFICATION'
                    await page.evaluate('m=>x1Chain.receive(m)', message)
                    await flush()

                async def focus(value):
                    await page.evaluate('v=>x1Chain.focus(v)', value)
                    await flush()

                def maps():
                    with access.database(readonly=True) as db:
                        return [json.loads(r[0]) for r in db.execute('SELECT body FROM runtime_provider_maps ORDER BY id')]

                # Owner starts from the dashboard/PowerShell. No capture deadline until foreground proof.
                state = orchestrator.start(MappingIntent(expected_load_id='900101', starting_section='Load Basics', causal_trace=True), owner_authorized=True)
                assert state['stage'] == 'WAITING_FOR_OWNER_WORKSPACE'
                await notify()  # No manually invoked worker wake for job start.
                offset[0] += 40
                await page.evaluate('()=>x1Chain.advance(40)')
                assert orchestrator.tick()['stage'] == 'WAITING_FOR_OWNER_WORKSPACE'
                assert access.status()['mapping_capture_count'] == 0 and not maps()
                await focus(True)
                await flush()
                state = orchestrator.tick()
                if commit_failure:
                    assert state['stage'] == 'STOPPED' and state['cleanup_complete']
                    if commit_failure == 'GRAPH':
                        assert state['safe_stop_code'] == 'WORKSPACE_SECTION_UNVERIFIED', state
                        assert state['failed_predicate'] == 'V2_BOUND_EXCEEDED', state
                        with access.database(readonly=True) as db:
                            diagnostics = [json.loads(row[0]) for row in db.execute('SELECT body FROM runtime_mapping_diagnostics')]
                        assert any(((r['diagnostic'].get('section_diagnostic') or {}).get('v2_diagnostic') or {}).get('bound_category') == 'payloadBytes' for r in diagnostics)
                    assert maps() == []
                    with access.database(readonly=True) as db:
                        assert not db.execute("SELECT name FROM sqlite_master WHERE name='runtime_v2_observations'").fetchone()
                        assert not any('webbridge_v2' in row[0] for row in db.execute('SELECT body FROM runtime_receipts'))
                    assert access.status()['read_access'] == 'REVOKED'
                    return
                assert state['stage'] == 'OWNER_REVIEW_REQUIRED', json.dumps(state)
                assert len(maps()) == 1 and state['last_completed_dom_stage'] == 'MAP_PERSISTED'
                assert state['capture_dispatch_state'] == 'COMPLETED'
                assert state['cleanup_complete'] and access.status()['read_access'] == 'REVOKED'
                if v2:
                    with access.database(readonly=True) as db:
                        rows = db.execute('SELECT body,completion FROM runtime_v2_observations').fetchall()
                    assert len(rows) == 1
                    assert json.loads(rows[0][1])['status'] == 'MAP_PERSISTED'
                    assert json.loads(rows[0][0])['graph']['binding']['entity_id'] == '900101'
                    assert 'PRIVATE_NEVER_READ' not in str(rows)
                    assert lost_notification == [True]  # tick recovered the committed evidence.
                    saved = accepted[0]
                    with access.database() as db:
                        assert real_persist(db, *copy.deepcopy(saved)) is None
                        changed = copy.deepcopy(saved)
                        changed[3]['webbridge_v2']['graph']['nodes'][0]['visibility']['viewport'] = 'UNKNOWN'
                        with pytest.raises(PermissionError, match='MAPPING_CONTRACT_INVALID'):
                            real_persist(db, *changed)
                        assert db.execute('SELECT count(*) FROM runtime_provider_maps').fetchone()[0] == 1
                if sibling_first_capture:
                    # A separate fixture history avoids pretending changed navigation is optional drift.
                    sibling_map = maps()[0]['map']
                    assert sibling_map['workspace']['load_id'] == '900101'
                    assert sibling_map['workspace']['navigation_candidates'] == []
                    assert sibling_map['section']['section_signal'] == 'SELECTED_ROUTE_AND_VISIBLE_HEADING'
                    assert sibling_map['section']['coverage'] == 'CURRENT_VISIBLE_SECTION_ONLY'
                    assert sibling_map['activation'] == 'CANDIDATE_ONLY' and not sibling_map['values_included']
                    assert state['safe_stop_code'] is None and state['production_writes'] is False
                    with access.database(readonly=True) as db:
                        receipts = [json.loads(row[0]) for row in db.execute('SELECT body FROM runtime_mapping_diagnostics')]
                        evidence = '\n'.join(row[0] for table in ['runtime_mapping_diagnostics', 'runtime_provider_maps', 'runtime_receipts']
                            for row in db.execute('SELECT body FROM '+table))
                    relationships = [row['diagnostic']['section_diagnostic']['route_heading_diagnostic'] for row in receipts
                        if row['diagnostic'].get('section_diagnostic') and row['diagnostic']['section_diagnostic'].get('route_heading_diagnostic')]
                    assert any(row['root_relationship'] == 'SIBLING_FORM_REGION' and row['sibling_form_diagnostic']['failed_predicate'] is None
                        for row in relationships)
                    assert 'PRIVATE_NEVER_READ' not in evidence
                    assert 'RUNTIME_CAPTURE_ACK' in frames and 'RUNTIME_MAPPING_PROGRESS' in frames
                    assert set((await page.evaluate('()=>x1Chain.summary()'))['operations']) <= {'ASCEND_GET_SESSION_STATE', 'ASCEND_MAP_WORKSPACE'}
                    assert requests and all(x == 'INTERCEPTED_FIXTURE_REQUEST' for x in requests)
                    return
                review = orchestrator.review(['Load Basics', 'Customer Info'], owner_authorized=True)
                assert review['stage'] == 'COMPLETE' and review['maturity'] == 'REVIEWED_NAVIGATION'
                assert review['live_validated'] is False

                # Passive session: first capture -> idle session proof -> same observer remains armed.
                orchestrator.start(MappingIntent(scope='OWNER_NAVIGATION_OBSERVE'), owner_authorized=True)
                await notify()
                baseline = await page.evaluate('()=>x1Chain.summary()')
                assert baseline['active_observers'] == 1
                prior_count = len(maps())
                offset[0] += 61
                await page.evaluate('()=>{x1Chain.advance(61);x1Chain.wake();}')
                await flush()
                refreshed = await page.evaluate('()=>x1Chain.summary()')
                assert refreshed['active_observers'] == 1 and refreshed['connections'] == baseline['connections']
                assert len(maps()) == prior_count

                # Owner leaves Ascend, opens a second workspace while unfocused, then returns.
                await focus(False)
                assert orchestrator.tick()['stage'] == 'WAITING_FOR_OWNER_WORKSPACE'
                await page.evaluate('body=>document.body.innerHTML=body', provider_dom('900102', optional=False))
                assert len(maps()) == prior_count
                await focus(True)
                await page.wait_for_timeout(2200)  # Actual bounded observer debounce, entirely offline.
                await flush()
                state = orchestrator.tick()
                assert state['stage'] != 'STOPPED', state
                assert maps()[-1]['change_kind'] == 'CROSS_LOAD_VARIATION'
                assert maps()[-1]['structural_drift'] is False
                assert maps()[-1]['map']['workspace']['load_id'] == '900102'

                # True document lifecycle replacement: rebind, fresh proof, capture, restored observer.
                await page.evaluate('()=>x1Chain.replaceDocument()')
                await page.evaluate('body=>document.body.innerHTML=body', provider_dom('900103', optional=False))
                await page.add_script_tag(path=str(EXT / 'content.js'))
                await page.evaluate('()=>x1Chain.documentReady()')
                await flush()
                assert orchestrator.tick()['stage'] != 'STOPPED'
                assert maps()[-1]['map']['workspace']['load_id'] == '900103'
                assert (await page.evaluate('()=>x1Chain.summary()'))['active_observers'] == 1

                # Revoke closes owned authority; later DOM changes cannot persist maps.
                access.disable(owner_authorized=True)
                stopped = orchestrator.tick()
                assert stopped['stage'] == 'STOPPED' and stopped['cleanup_complete']
                count_at_revoke = len(maps())
                operations_at_revoke = len((await page.evaluate('()=>x1Chain.summary()'))['operations'])
                await page.evaluate('()=>x1Chain.wake()')
                await flush()
                await page.evaluate('body=>document.body.innerHTML=body', provider_dom('900104'))
                await focus(True)
                assert len(maps()) == count_at_revoke
                assert len((await page.evaluate('()=>x1Chain.summary()'))['operations']) == operations_at_revoke

                # Dependency wait recovers without taking away another read job's authority.
                old = access.enable(owner_authorized=True)
                old_expiry = old['lease_expires_at']
                state = orchestrator.start(MappingIntent(scope='OWNER_NAVIGATION_OBSERVE'), owner_authorized=True)
                assert state['stage'] == 'WAITING_FOR_READ_JOB'
                assert access.status()['read_access'] == 'ENABLED' and access.status()['lease_expires_at'] == old_expiry
                access.disable(owner_authorized=True)  # Simulated owner finishes the other job.
                orchestrator.tick()
                await notify()
                assert orchestrator.tick()['stage'] != 'STOPPED'
                assert maps()[-1]['map']['workspace']['load_id'] == '900104'
                orchestrator.control('cancel', owner_authorized=True)

                # Current section rejection persists its precise safe predicate through every layer.
                await page.evaluate('body=>document.body.innerHTML=body', provider_dom('900105', linked=False))
                orchestrator.start(MappingIntent(expected_load_id='900105', starting_section='Load Basics'), owner_authorized=True)
                await notify()
                state = orchestrator.tick()
                assert state['safe_stop_code'] == 'WORKSPACE_SECTION_UNVERIFIED', state
                assert state['failed_predicate'] == 'ROUTE_ANCHOR_COUNT_ZERO'
                assert state['last_completed_dom_stage'] == 'WORKSPACE_IDENTITY_VERIFIED'
                assert state['cleanup_complete'] and state['production_writes'] is False

                with access.database(readonly=True) as db:
                    evidence = '\n'.join(row[0] for table in ['runtime_mapping_diagnostics', 'runtime_provider_maps', 'runtime_receipts']
                        for row in db.execute('SELECT body FROM '+table))
                assert 'PRIVATE_NEVER_READ' not in evidence
                assert set((await page.evaluate('()=>x1Chain.summary()'))['operations']) <= {'ASCEND_GET_SESSION_STATE', 'ASCEND_MAP_WORKSPACE'}
                assert 'RUNTIME_CAPTURE_ACK' in frames and 'RUNTIME_MAPPING_PROGRESS' in frames
                assert requests and all(x == 'INTERCEPTED_FIXTURE_REQUEST' for x in requests)
            finally:
                await page.evaluate('()=>x1Chain.close()')
                await context.close()
                await browser.close()
    asyncio.run(exercise())
