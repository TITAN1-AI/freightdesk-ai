"""Candidate Stops sensor in disposable, network-intercepted synthetic Edge DOM."""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright
from pydantic import ValidationError

from executors.ascend_extension.workspace_contracts import AscendProviderMap
from tests.test_ascend_x1_controller import repo as repo
from tests.test_ascend_x1_runtime import runtime as runtime
from tests.test_x1_workspace_mapping import approval, capture as finish_mapping

EXT = Path(__file__).resolve().parents[1] / 'extensions' / 'ascend-x1'
HEADERS = ['Stop Order', 'Action(s)', 'Scheduled Date/Time', 'Actual Date/Time',
           'Location', 'Address', 'Private Notes', 'Cargo', 'Reference #', 'Show on', 'Reorder']


def fixture_html(order=None):
    order = order or HEADERS
    rows = []
    for kind, color, arrow in [('pickup', 'success', 'up'), ('delivery', 'danger', 'down')]:
        cells = {h: '<span data-private>PRIVATE_SENTINEL</span>' for h in HEADERS}
        cells['Action(s)'] = f'<span class="label-{color}"><i class="fa-arrow-{arrow}"></i></span>'
        cells['Scheduled Date/Time'] = '<a data-private>PRIVATE_SENTINEL</a>'
        cells['Actual Date/Time'] = ''.join(
            f'<div class="editable-cell {kind}-{phase}"><a data-private>PRIVATE_SENTINEL</a></div>'
            for phase in ['arrival', 'departure'])
        rows.append('<tr>' + ''.join(f'<td>{cells[h]}</td>' for h in order) + '</tr>')
    rows.insert(1, '<tr><td colspan="11"><details><summary>Auxiliary</summary></details></td></tr>')
    return ('<main><h1>Load #900001</h1><div role="tablist">'
            '<button role="tab" aria-selected="false" aria-controls="other">Load Basics</button>'
            '<button role="tab" aria-selected="true" aria-controls="panel">Edit Stops</button></div>'
            '<section id="panel" role="tabpanel"><h2>Edit Stops</h2>'
            '<table class="table-hover table-striped table-condensed table-bordered"><thead><tr>'
            + ''.join(f'<th>{h}</th>' for h in order) + '</tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></section></main>')


@pytest.fixture(scope='module')
def page(tmp_path_factory):
    temp = tmp_path_factory.mktemp('stops-browser')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True,
                                     env={**os.environ, 'TEMP': str(temp), 'TMP': str(temp)})
        context = browser.new_context(service_workers='block')
        context.route('**/*', lambda route: route.fulfill(body='<title>Synthetic only</title>', content_type='text/html'))
        tab = context.new_page()
        tab.goto('https://ascendtms.com/loads/900001/stops')
        for name in ['contract.js', 'read-errors.js', 'load-board-view.js', 'detail-scope.js',
                     'webbridge.js', 'mapping-scope.js', 'workspace.js', 'stops-metadata.js']:
            tab.add_script_tag(path=str(EXT / name))
        yield tab
        context.close()
        browser.close()


def capture(page, change='', order=None, guard='()=>{}'):
    page.evaluate('(html)=>document.body.innerHTML=html', fixture_html(order))
    if change:
        page.evaluate(change)
    return page.evaluate('''async guardSource => {
        const guard = (0,eval)(guardSource);
        try {return await FreightDeskStopsMetadata.capture(document, {
          operation:'ASCEND_MAP_WORKSPACE', capture_load_id:'900001',capture_section:'Edit Stops'
        },guard);} catch(e) {return {error:e.message};}
    }''', guard)


def test_auxiliary_and_metadata_privacy(page):
    result = capture(page)
    assert 'error' not in result, result
    assert result['auxiliary_row_count'] == 1
    assert [r['action'] for r in result['rows']] == ['PICKUP', 'DELIVERY']
    assert all(r['provider_row_key'] is None for r in result['rows'])
    assert 'PRIVATE_SENTINEL' not in json.dumps(result)
    assert result['values_included'] is result['writes_allowed'] is False


def test_off_viewport(page):
    result = capture(page, "()=>document.querySelector('tbody tr:last-child').style.transform='translateY(4000px)'")
    assert len(result['rows']) == 2


def test_reordered_headers(page):
    result = capture(page, order=list(reversed(HEADERS)))
    assert result['rows'][0]['actual']['arrival']['present']
    assert result['rows'][1]['scheduled']['subtype'] == 'UNKNOWN'


@pytest.mark.parametrize(('change', 'error'), [
    ("()=>document.querySelector('th').textContent='Action(s)'", 'STOPS_HEADER_DUPLICATE'),
    ("()=>document.querySelector('h1').textContent='Load #900002'", 'WORKSPACE_IDENTITY_CONFLICT'),
    ("()=>document.querySelector('.pickup-arrival').closest('tr').lastElementChild.append(document.querySelector('.pickup-arrival'))", 'STOPS_CONTAINMENT_INVALID'),
    ("()=>document.querySelector('.pickup-arrival').remove()", 'STOPS_CONTAINMENT_INVALID'),
    ("()=>document.querySelector('tbody').append(document.querySelector('tbody tr').cloneNode(true))", None),
    ("()=>document.querySelector('tbody tr:nth-child(2) details').remove()", 'STOPS_ROW_INVALID'),
    ("()=>document.querySelector('table').after(document.querySelector('table').cloneNode(true))", 'STOPS_TABLE_AMBIGUOUS'),
    ("()=>document.querySelector('tbody tr').style.display='none'", 'STOPS_ROW_HIDDEN'),
])
def test_fail_closed_and_repeated_stop_types(page, change, error):
    result = capture(page, change)
    if error:
        assert result['error'] == error
    else:
        assert len(result['rows']) == 3
        assert len({r['capture_row_ref'] for r in result['rows']}) == 3


def test_authority_required_and_revocation(page):
    assert capture(page, guard='undefined')['error'] == 'STOPS_AUTHORITY_REQUIRED'
    assert capture(page, guard="()=>{throw Error('READ_LEASE_REVOKED')}")['error'] == 'READ_LEASE_REVOKED'
    assert capture(page, guard="(()=>{let n=0;return ()=>{if(++n>5)throw Error('READ_LEASE_REVOKED')}})()")['error'] == 'READ_LEASE_REVOKED'


def test_no_value_access_or_clicks(page):
    result = capture(page, """()=>{
      window.clicks=0;document.addEventListener('click',()=>window.clicks++);
      for(const e of document.querySelectorAll('[data-private]')) {
        Object.defineProperty(e,'textContent',{get(){throw Error('PRIVATE_READ')}});
        Object.defineProperty(e,'innerText',{get(){throw Error('PRIVATE_READ')}});
      }
    }""")
    assert 'error' not in result, result
    assert page.evaluate('window.clicks') == 0


def test_mid_capture_identity_change(page):
    result = capture(page, guard="(()=>{let once=false;return ()=>{if(!once){once=true;setTimeout(()=>document.querySelector('h1').textContent='Load #900002',0)}}})()")
    assert result['error'] == 'WORKSPACE_IDENTITY_CONFLICT'


def test_packaged_in_source_manifest():
    assert 'stops-metadata.js' in (EXT / 'manifest.json').read_text()


@pytest.mark.parametrize(('change', 'error'), [
    ("()=>{let b=document.querySelector('tbody');while(b.rows.length<21)b.append(b.rows[0].cloneNode(true))}", 'STOPS_ROW_BOUND'),
    ("()=>{let c=document.querySelector('tbody tr td');for(let i=0;i<21;i++)c.append(document.createElement('a'))}", 'STOPS_CONTROL_BOUND'),
    ("()=>document.querySelector('th').colSpan=2", 'STOPS_HEADER_INVALID'),
    ("()=>document.querySelector('button[aria-selected=true]').setAttribute('aria-selected','false')", 'WORKSPACE_SECTION_UNVERIFIED'),
])
def test_bounds_and_section_gate(page, change, error):
    assert capture(page, change)['error'] == error


def test_owner_presence_required(page):
    try:
        assert capture(page, '()=>document.hasFocus=()=>false')['error'] == 'MAPPING_OWNER_NOT_PRESENT'
    finally:
        page.evaluate('()=>delete document.hasFocus')


def workspace_capture(page):
    page.evaluate('(html)=>document.body.innerHTML=html', fixture_html())
    page.evaluate("""()=>{for(const e of document.querySelectorAll('td a')){Object.defineProperty(e,'firstChild',{get(){throw Error('PRIVATE_ANCHOR_TEXT_READ')}});}}""")
    return page.evaluate("""()=>FreightDeskWorkspace.capture(document,['900001'],()=>{},()=>{},performance.now(),
      {capture_load_id:'900001',capture_section:'Edit Stops'})""")


def test_workspace_to_host_persistence(page, runtime):
    evidence = workspace_capture(page)
    parsed = AscendProviderMap.model_validate(evidence)
    assert parsed.section.stops_metadata.rows[0].actual.arrival.present
    access, controller, now, *_ = runtime
    now[0] = evidence["workspace"]["observed_at"]
    access.enable(mapping=approval(), owner_authorized=True)
    result = finish_mapping(controller, access, evidence)
    assert result['status']['mapping_capture_count'] == 1
    with access.database(readonly=True) as db:
        stored = json.loads(db.execute('SELECT body FROM runtime_provider_maps').fetchone()[0])
    assert stored['map']['section']['stops_metadata'] == evidence['section']['stops_metadata']
    assert not stored['live_validated'] and not stored['production_writes']
    assert 'PRIVATE_SENTINEL' not in json.dumps(stored)


@pytest.mark.parametrize('mutation', ['value', 'hash', 'row_identity', 'section', 'bounds'])
def test_host_rejects_tampered_stops_metadata(page, mutation):
    evidence = workspace_capture(page)
    stops = evidence['section']['stops_metadata']
    if mutation == 'value':
        stops['rows'][0]['actual']['arrival']['value'] = 'PRIVATE'
    elif mutation == 'hash':
        stops['auxiliary_row_count'] = 0
    elif mutation == 'row_identity':
        stops['rows'][0]['provider_row_key'] = 'INVENTED'
    elif mutation == 'section':
        evidence['section']['section'] = 'Load Basics'
    else:
        stops['rows'][0]['control_count'] = 21
    with pytest.raises(ValidationError):
        AscendProviderMap.model_validate(evidence)


def test_exact_stops_start_requires_load_identity():
    from executors.ascend_extension.mapping_orchestrator import MappingIntent
    assert MappingIntent(expected_load_id='900001', starting_section='Edit Stops').starting_section == 'Edit Stops'
    with pytest.raises(ValidationError):
        MappingIntent(starting_section='Edit Stops')


def test_old_build_cannot_claim_new_stops_release():
    from executors.ascend_extension.bridge_build import BUILD, BridgeBuild
    with pytest.raises(ValidationError):
        BridgeBuild.model_validate({**BUILD, 'extension_version': '0.6.3'})
