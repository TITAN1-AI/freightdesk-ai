"""Audit repros converted to desired behavior, through the actual compatibility facade.

Synthetic DOM only; every browser request is intercepted. Runtime data stays in TestRuns.
"""
import asyncio
import copy
import json
import os
import sqlite3
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from executors.ascend_extension.mapping_store import ensure_map_indexes, persist_map, report_maps
from executors.ascend_extension.workspace_contracts import AscendProviderMap, MappingSessionApproval, SCOPE
from executors.webbridge_v2.contracts import Binding, validate_graph
from executors.webbridge_v2.wire import expand_graph
from integrations.ascend.context_assembler import ReadMappingValidation, VerifiedAscendLoadContextAssembler, VerifiedProviderObservation
from tests.test_x1_workspace_mapping import provider_map

ROOT = Path(__file__).resolve().parents[1]
BASE = r'''count=>{
 document.body.innerHTML='<main data-load-workspace data-load-id="900101"><h1>Load #900101</h1><div role="tablist">'+
 '<button type="button" role="tab" aria-selected="true" aria-controls="p1">Load Basics</button>'+
 '<button type="button" role="tab" aria-selected="false" aria-controls="p2">Customer Info</button></div>'+
 '<section id="p1" role="tabpanel"><h2>Load Basics</h2><form>'+Array.from({length:count},(_,i)=>
 '<div><label for="f'+i+'">Equipment</label><input id="f'+i+'" value="PRIVATE_AUDIT_FIXTURE"></div>').join('')+
 '<button type="button">Save</button></form></section><section id="p2" role="tabpanel" hidden><h2>Customer Info</h2></section></main>';
 globalThis.chrome={runtime:{id:'fixture'}};globalThis.__freightdeskX1Document={id:'a'.repeat(32),generation:1};document.hasFocus=()=>true;
}'''
CALL = r'''async id=>{const started=performance.now();try{
 const value=await FreightDeskWebBridge.BrowserSensor.mapWorkspace(document,['900101'],()=>{},()=>{},performance.now(),
 {request_id:id.repeat(32),lease_expires_at:Math.trunc(Date.now()/1000)+600,capture_load_id:'900101',capture_section:'Load Basics'});
 return {ok:true,value,elapsed_ms:Math.ceil(performance.now()-started)};
}catch(e){return {ok:false,error:e.message,diagnostic:e.section_diagnostic?.v2_diagnostic||null};}}'''


def valid_graph(wire):
    graph = expand_graph(wire)
    vocabulary = frozenset(SCOPE['sections'] + list(SCOPE['fields']) + SCOPE['actions'])
    return validate_graph(graph, expected_binding=Binding.model_validate(graph['binding']), vocabulary=vocabulary)


@pytest.mark.parametrize('scenario,count', [('capacity', 12), ('capacity', 19), ('capacity', 32),
    ('private', 1), ('between_phases', 1), ('node_replaced', 1), ('unbounded_chrome', 1)])
def test_actual_facade_audit_regressions(tmp_path, scenario, count):
    async def exercise():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel='msedge', headless=True,
                env={**os.environ, 'TEMP': str(tmp_path), 'TMP': str(tmp_path)})
            context = await browser.new_context(service_workers='block')
            await context.route('**/*', lambda route: route.fulfill(content_type='text/html', body='<title>Offline synthetic fixture</title>'))
            page = await context.new_page()
            try:
                await page.goto('https://ascendtms.com/loads')
                for name in ['build', 'contract', 'detail-scope', 'webbridge', 'mapping-scope', 'workspace']:
                    await page.add_script_tag(path=str(ROOT / f'extensions/ascend-x1/{name}.js'))
                for name in ['semantics', 'core', 'compatibility']:
                    await page.add_script_tag(path=str(ROOT / f'extensions/webbridge-v2/{name}.js'))
                await page.evaluate(BASE, count)
                if scenario == 'between_phases':
                    await page.evaluate('''()=>{const W=FreightDeskWorkspace;globalThis.FreightDeskWorkspace=Object.freeze({...W,
                      capture:async(...args)=>{const result=await W.capture(...args);document.querySelector('label').textContent='Carrier';return result;}});}''')
                if scenario == 'unbounded_chrome':
                    await page.evaluate("()=>document.body.insertAdjacentHTML('afterbegin','<div></div>'.repeat(5000))")
                if scenario == 'private':
                    await page.evaluate('''()=>{const e=document.createElement('span');e.dataset.private='';e.textContent='PRIVATE_NOTE';document.querySelector('input').before(e);
                      globalThis.privateReads=0;for(const key of ['textContent','innerText'])Object.defineProperty(e,key,{get(){privateReads++;throw Error('PRIVATE_READ');}});
                      for(const key of ['value','textContent','innerText','checked'])Object.defineProperty(HTMLInputElement.prototype,key,{get(){privateReads++;throw Error('PRIVATE_READ');}});
                      // No aggregate text or document-wide result arrays are needed by either mapper.
                      Object.defineProperty(Node.prototype,'textContent',{get(){throw Error('AGGREGATE_READ');}});
                      Document.prototype.querySelectorAll=Element.prototype.querySelectorAll=()=>{throw Error('UNBOUNDED_QUERY');};
                    }''')
                await page.evaluate("globalThis.fixtureAdapter=FreightDeskV2Compatibility.install({mode:'OFFLINE'})")
                first = await page.evaluate(CALL, '1')
                if scenario == 'capacity' and count == 32:
                    assert first == {'ok': False, 'error': 'MAPPING_PAYLOAD_BOUND', 'diagnostic': None}
                    return  # Explicit finite transport capacity, not a promised unbounded form size.
                if scenario in {'between_phases', 'unbounded_chrome'}:
                    assert not first['ok']
                    assert first['error'] == ('WORKSPACE_CHANGED' if scenario == 'between_phases' else 'WORKSPACE_BOUND')
                    return
                assert first['ok'], first
                mapped = first['value']
                graph = valid_graph(mapped['webbridge_v2']['graph'])
                assert len(mapped['section']['fields']) == count
                assert len(mapped['webbridge_v2']['fields']) == count
                assert 'PRIVATE_AUDIT_FIXTURE' not in json.dumps(mapped) and 'PRIVATE_NOTE' not in json.dumps(mapped)
                wire_bytes = len(json.dumps(mapped['webbridge_v2']['graph'], separators=(',', ':')).encode())
                payload_bytes = len(json.dumps(mapped, separators=(',', ':')).encode())
                assert wire_bytes <= 32000 and payload_bytes <= 45000 and first['elapsed_ms'] < 3000
                (tmp_path / 'metrics.json').write_text(json.dumps(dict(scenario=scenario, fields=count,
                    wire_bytes=wire_bytes, payload_bytes=payload_bytes, elapsed_ms=first['elapsed_ms'])))
                if scenario == 'private':
                    assert await page.evaluate('privateReads') == 0
                if scenario == 'node_replaced':
                    original_id = next(n.id for n in graph.nodes if n.tag == 'input')
                    await page.evaluate("()=>{const old=document.querySelector('input');old.replaceWith(old.cloneNode(true));}")
                    second = await page.evaluate(CALL, '2')
                    assert second['ok'], second
                    second_graph = valid_graph(second['value']['webbridge_v2']['graph'])
                    assert second_graph.document_key == graph.document_key
                    assert next(n.id for n in second_graph.nodes if n.tag == 'input') != original_id
                    assert next(n.id for n in second_graph.nodes if n.tag == 'button') == next(n.id for n in graph.nodes if n.tag == 'button')
                    await page.evaluate("()=>dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}))")
                    restored = await page.evaluate(CALL, '4')
                    assert restored['ok'], restored
                    assert valid_graph(restored['value']['webbridge_v2']['graph']).nodes == second_graph.nodes
                    await page.evaluate("()=>{__freightdeskX1Document.id='b'.repeat(32);__freightdeskX1Document.generation=2;}")
                    third = await page.evaluate(CALL, '3')
                    assert third['ok'], third
                    assert valid_graph(third['value']['webbridge_v2']['graph']).document_key != graph.document_key
                    await page.evaluate('fixtureAdapter.dispose()')
                    assert (await page.evaluate(CALL, '5'))['error'] == 'V2_CLOSED'
                # Redundant fields cannot contradict reference resolution or integer schema.
                raw = expand_graph(mapped['webbridge_v2']['graph'])
                def check(value):
                    validate_graph(value, expected_binding=graph.binding,
                        vocabulary=frozenset(SCOPE['sections'] + list(SCOPE['fields']) + SCOPE['actions']))
                contradictory = copy.deepcopy(raw)
                resolution = next(r for r in contradictory['resolutions'] if r['kind'] == 'CONTROLS' and r['status'] == 'RESOLVED')
                resolution.update(status='AMBIGUOUS', candidates=[resolution['candidates'][0], graph.root], candidate_count=2)
                with pytest.raises(ValueError, match='V2_REFERENCE_INVALID'):
                    check(contradictory)
                for field in ['schema_version']:
                    invalid = copy.deepcopy(raw)
                    invalid[field] = float(invalid[field])
                    with pytest.raises(ValueError, match='V2_SCALAR_INVALID'):
                        check(invalid)
                invalid = copy.deepcopy(raw)
                invalid['observation_binding']['mutation_revision'] = 0.0
                with pytest.raises(ValueError, match='V2_SCALAR_INVALID'):
                    check(invalid)
            finally:
                await context.close()
                await browser.close()
    asyncio.run(exercise())


@pytest.mark.parametrize('changes', [dict(domain='financials'), dict(value={'raw': 'invalid'}), dict(value=float('nan')),
    dict(value=None), dict(observed_at=True), dict(observed_at=float('inf')), dict(source='untrusted')])
def test_context_rejects_misclassified_or_invalid_observation(changes):
    current = AscendProviderMap.model_validate(provider_map())
    field = current.section.fields[0]
    validation = ReadMappingValidation.controlled_comparison(field, 'synthetic-evidence', matched=True, owner_authorized=True)
    observation = VerifiedProviderObservation('1755', 'equipment', 'equipment', field.contract_fingerprint, 'SYNTHETIC', 1000)
    assembler = VerifiedAscendLoadContextAssembler()
    assert assembler.assemble(current, [], [observation], [validation], now=1001)['equipment']['confidence'] == 'VERIFIED'
    rejected = assembler.assemble(current, [], [replace(observation, **changes)], [validation], now=1001)
    assert rejected['equipment']['confidence'] == rejected['financials']['confidence'] == 'UNKNOWN'


def test_history_queries_decode_only_bounded_relevant_records(tmp_path):
    path = tmp_path / 'history.sqlite3'
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE runtime_provider_maps(id INTEGER PRIMARY KEY,body TEXT)')
    ensure_map_indexes(db)
    old = dict(provider_map_version=1, workspace_contract_version=1, section_contract_version=1,
        session_id='old-session', map=provider_map(number='900009'), navigation='FIRST_OBSERVATION', structural_drift=False)
    db.executemany('INSERT INTO runtime_provider_maps(body) VALUES (?)', [(json.dumps(old),)] * 2000)
    approval = MappingSessionApproval(session_id='owner-x1-mapping-synthetic-current', operation_mode='OBSERVE', mode='NORMAL_OWNER_PRESENT')
    lease = {'mapping': approval.model_dump()}
    pending = {'deadline': 1010, 'route': {'document_id': 'synthetic-document'}}
    with patch('executors.ascend_extension.mapping_store.json.loads', wraps=json.loads) as loads:
        record = persist_map(db, {}, lease, pending, provider_map(), 1001)
        assert loads.call_count <= 4
    assert record['provider_map_version'] == 2001
    plan = str(db.execute("EXPLAIN QUERY PLAN SELECT body FROM runtime_provider_maps WHERE json_extract(body,'$.map.section.section')=? ORDER BY id DESC LIMIT 1", ('Load Basics',)).fetchall())
    assert 'runtime_maps_section' in plan and 'SCAN runtime_provider_maps' not in plan
    db.commit()
    class Access:
        def __init__(self):
            self.path = path
        def database(self, readonly=False):
            assert readonly
            return sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    with patch('executors.ascend_extension.mapping_store.json.loads', wraps=json.loads) as loads:
        report = report_maps(Access(), 'owner-x1-mapping-synthetic-current')
        assert loads.call_count == 1
    assert report['captures'] == 1
    assert db.execute('SELECT count(*) FROM runtime_provider_maps').fetchone()[0] == 2001
    db.close()
