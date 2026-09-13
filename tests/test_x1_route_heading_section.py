"""Observed signal relationships in synthetic DOM; never live provider selectors or values."""

import asyncio
import json
import os

from executors.ascend_extension.mapping_diagnostics import MappingSectionDiagnostic
from executors.ascend_extension.workspace_contracts import AscendProviderMap
from tests.test_ascend_x1_dom import EXT


def test_selected_route_and_heading_require_bounded_form_region(tmp_path):
    async def run():
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="msedge", headless=True,
                env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)})
            context = await browser.new_context(service_workers="block")
            await context.route("**/*", lambda request: request.fulfill(content_type="text/html", body="<title>Offline route-heading fixture</title>"))
            page = await context.new_page()
            try:
                await page.goto("https://ascendtms.com/loads")
                for file in ["contract.js", "read-errors.js", "load-board-view.js", "detail-scope.js", "webbridge.js", "mapping-scope.js", "workspace.js", "reader.js"]:
                    await page.add_script_tag(path=str(EXT / file))
                provider_nav = '<nav>'+''.join('<a href="#">'+name+'</a>' for name in ["Dashboard", "Loads", "Customers", "Carriers"] )+'</nav>'
                def form(index=0):
                    return f'<form><legend>PRIVATE_LEGEND_{index}</legend><label for="f{index}">Equipment</label><input id="f{index}" value="PRIVATE_VALUE"><button>Save</button></form>'
                def html(*, href='/loads', label='Load Basics', heading='Load Basics', forms=None, extra='', controls=''):
                    forms = ''.join(form(i) for i in range(3)) if forms is None else forms
                    other_label = 'Load Basics' if label == 'Customer Info' else 'Customer Info'
                    return provider_nav+'<main><h1>Load #1763</h1><ul><li class="active"><a href="'+href+'">'+label+'</a></li>' \
                        '<li><a href="/fixture-other">'+other_label+'</a></li></ul>'+controls+ \
                        '<div id="section-content"><div id="heading-toolbar"><h1>'+heading+'</h1><input aria-label="PRIVATE_SEARCH" value="PRIVATE_SEARCH_VALUE"></div>'+forms+extra+'</div></main>'
                async def inspect(body):
                    await page.evaluate("body=>document.body.innerHTML=body", body)
                    result = await page.evaluate("""()=>{try{
                      const workspace=FreightDeskWorkspace.observeWorkspace(document,null,1), section=FreightDeskWorkspace.observeSection(workspace);
                      return {section:section.name,root_id:section.root.id,signal:section.signal,diagnostic:section.diagnostic};
                    }catch(error){return {code:error.message,diagnostic:error.section_diagnostic};}}""")
                    MappingSectionDiagnostic.model_validate(result['diagnostic'])
                    assert 'PRIVATE' not in json.dumps(result)
                    return result

                good = await inspect(html())
                assert good['section'] == 'Load Basics' and good['root_id'] == 'section-content'
                assert good['signal'] == 'SELECTED_ROUTE_AND_VISIBLE_HEADING'
                diagnostic = good['diagnostic']['route_heading_diagnostic']
                assert diagnostic['route_anchor_candidate_count'] == diagnostic['matching_heading_count'] == 1
                assert diagnostic['selected_ancestor_depth'] == 2
                assert diagnostic['visible_field_candidate_count'] == 4
                assert diagnostic['ancestor_candidates'][0]['predicate'] == 'NO_VISIBLE_FORM_FIELDS'
                assert diagnostic['ancestor_candidates'][1]['visible_form_count'] == 3
                assert diagnostic['ancestor_candidates'][1]['forms_with_visible_fields'] == 3
                assert diagnostic['failed_predicate'] is None
                observed = await page.evaluate("()=>FreightDeskWorkspace.capture(document,['1763'],()=>{})")
                AscendProviderMap.model_validate(observed)
                assert observed['activation'] == 'CANDIDATE_ONLY' and observed['values_included'] is False
                assert observed['writes_allowed'] is False
                assert observed['section']['coverage'] == 'CURRENT_VISIBLE_SECTION_ONLY'
                assert observed['section']['section_signal'] == 'SELECTED_ROUTE_AND_VISIBLE_HEADING'
                assert observed['workspace']['navigation_candidates'] == []
                assert 'PRIVATE' not in json.dumps(observed)

                # An input beside a heading is insufficient; a visible form region is required.
                toolbar = await inspect(html(forms=''))
                assert toolbar['code'] == 'WORKSPACE_SECTION_UNVERIFIED'
                assert toolbar['diagnostic']['route_heading_diagnostic']['failed_predicate'] == 'NO_ELIGIBLE_ROOT'
                assert all(row['predicate'] == 'NO_VISIBLE_FORM_FIELDS' for row in toolbar['diagnostic']['route_heading_diagnostic']['ancestor_candidates'])
                hidden = await inspect(html(forms='<form hidden><input value="PRIVATE"></form>'))
                assert hidden['diagnostic']['route_heading_diagnostic']['failed_predicate'] == 'NO_ELIGIBLE_ROOT'

                for href in ['', ' ', '#', '?', '/loads#x', '/loads?x', 'https://example.invalid/loads', 'javascript:PRIVATE_SCRIPT()']:
                    stopped = await inspect(html(href=href))
                    assert stopped['code'] == 'WORKSPACE_SECTION_UNVERIFIED'
                    assert stopped['diagnostic']['route_heading_diagnostic']['failed_predicate'] == 'ROUTE_ANCHOR_COUNT_ZERO'
                missing_heading = await inspect(html(heading='PRIVATE_OTHER'))
                assert missing_heading['diagnostic']['route_heading_diagnostic']['failed_predicate'] == 'MATCHING_HEADING_COUNT_ZERO'
                disagreeing = await inspect(html(heading='Customer Info'))
                assert disagreeing['diagnostic']['route_heading_diagnostic']['failed_predicate'] == 'MATCHING_HEADING_COUNT_ZERO'
                duplicate_heading = await inspect(html(extra='<h1>Load Basics</h1>'))
                assert duplicate_heading['diagnostic']['route_heading_diagnostic']['failed_predicate'] == 'MATCHING_HEADING_COUNT_MULTIPLE'
                duplicate_anchor = await inspect(html(controls='<a class="active" href="/loads">Customer Info</a>'))
                assert duplicate_anchor['diagnostic']['route_heading_diagnostic']['failed_predicate'] == 'ROUTE_ANCHOR_COUNT_MULTIPLE'
                for extra, predicate in [('<h2>Load #1763</h2>', 'CONTAINS_WORKSPACE_IDENTITY'),
                    ('<button>Customer Info</button>', 'CONTAINS_SECTION_NAVIGATION'),
                    ('<h2>Financials</h2>', 'CONTAINS_OTHER_SECTION_HEADING')]:
                    stopped = await inspect(html(extra=extra))
                    assert stopped['code'] == 'WORKSPACE_SECTION_UNVERIFIED'
                    assert predicate in [row['predicate'] for row in stopped['diagnostic']['route_heading_diagnostic']['ancestor_candidates']]

                bounded_forms = await inspect(html(forms=''.join(form(i) for i in range(17))))
                assert 'FORM_CANDIDATE_BOUND' in [row['predicate'] for row in bounded_forms['diagnostic']['route_heading_diagnostic']['ancestor_candidates']]
                bounded_fields = await inspect(html(forms='<form>'+'<input type="hidden">'*257+'</form>'))
                assert 'FORM_FIELD_CANDIDATE_BOUND' in [row['predicate'] for row in bounded_fields['diagnostic']['route_heading_diagnostic']['ancestor_candidates']]
                deep = html().replace('<div id="heading-toolbar">', '<div>'*8+'<div id="heading-toolbar">').replace('</h1><input aria-label="PRIVATE_SEARCH" value="PRIVATE_SEARCH_VALUE"></div>', '</h1><input aria-label="PRIVATE_SEARCH" value="PRIVATE_SEARCH_VALUE"></div>'+'</div>'*8)
                too_deep = await inspect(deep)
                assert too_deep['diagnostic']['route_heading_diagnostic']['failed_predicate'] == 'ANCESTOR_BOUND'
                assert too_deep['diagnostic']['route_heading_diagnostic']['ancestor_count'] == 8

                # The fallback cannot erase an ambiguity already established by the existing resolver.
                ambiguous = await inspect(html(extra='<section><h2>Financials</h2></section><section><h2>Customer Info</h2></section>'))
                assert ambiguous['diagnostic']['failed_predicate'] == 'UNIQUE_CANDIDATE_COUNT_MULTIPLE'
                assert ambiguous['diagnostic'].get('route_heading_diagnostic') is None

                # Wrong requested section remains a target mismatch, never proof of the requested name.
                await inspect(html(label='Customer Info', heading='Customer Info'))
                target_mismatch = await page.evaluate("""async()=>{try{
                  await FreightDeskWorkspace.capture(document,['1763'],()=>{},()=>{},performance.now(),{capture_load_id:'1763',capture_section:'Load Basics'});
                  return 'BAD';}catch(error){return error.message;}}""")
                assert target_mismatch == 'STARTING_SECTION_MISMATCH'

                # The unchanged 64-visible-field guard has its precise count persisted before extraction.
                await inspect(html(forms='<form>'+'<input aria-label="Equipment">'*65+'</form>'))
                bounded_capture = await page.evaluate("""async()=>{const stages=[];try{
                  await FreightDeskWorkspace.capture(document,['1763'],()=>{},d=>stages.push(d));return {unexpected:true};
                }catch(error){return {code:error.message,stages};}}""")
                assert bounded_capture['code'] == 'WORKSPACE_BOUND'
                assert bounded_capture['stages'][-1]['stage'] == 'SECTION_IDENTIFIED'
                assert bounded_capture['stages'][-1]['section_diagnostic']['route_heading_diagnostic']['visible_field_candidate_count'] == 66

                await inspect(html())
                await page.evaluate("""()=>{window.fixtureClicks=0;document.addEventListener('click',()=>fixtureClicks++);
                  Object.defineProperty(HTMLInputElement.prototype,'value',{get(){throw Error('PRIVATE_VALUE_READ')}});
                  window.fetch=()=>{throw Error('NETWORK_NOT_ALLOWED')};window.XMLHttpRequest=()=>{throw Error('NETWORK_NOT_ALLOWED')};}""")
                safe = await page.evaluate("()=>FreightDeskWorkspace.capture(document,['1763'],()=>{})")
                assert safe['values_included'] is False and await page.evaluate('fixtureClicks') == 0
                assert await page.evaluate('FreightDeskWorkspace.readerRevision') == 2
            finally:
                await context.close()
                await browser.close()
    asyncio.run(run())
