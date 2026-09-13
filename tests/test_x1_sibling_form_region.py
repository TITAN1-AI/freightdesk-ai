"""Synthetic sibling section relationships; intercepted networking, no provider execution."""

import asyncio
import json
import os

from executors.ascend_extension.mapping_diagnostics import MappingSectionDiagnostic
from executors.ascend_extension.workspace_contracts import AscendProviderMap
from tests.test_ascend_x1_dom import EXT


def test_unique_later_sibling_form_region_preserves_section_identity_and_bounds(tmp_path):
    async def run():
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="msedge", headless=True,
                env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)})
            context = await browser.new_context(service_workers="block")
            await context.route("**/*", lambda route: route.fulfill(content_type="text/html", body="<title>Offline sibling fixture</title>"))
            page = await context.new_page()
            try:
                await page.goto("https://ascendtms.com/loads")
                for file in ["contract.js", "read-errors.js", "load-board-view.js", "detail-scope.js", "webbridge.js", "mapping-scope.js", "workspace.js", "reader.js"]:
                    await page.add_script_tag(path=str(EXT / file))
                provider_nav = '<nav>'+''.join('<a href="#">'+name+'</a>' for name in ["Dashboard", "Loads", "Customers", "Carriers"] )+'</nav>'

                def form(index=0):
                    return f'<form><legend>PRIVATE_LEGEND_{index}</legend><label for="f{index}">Equipment</label><input id="f{index}" value="PRIVATE_VALUE"><button>Save</button></form>'

                def html(*, before=False, branch='', region_extra='', context_extra='', heading='Load Basics', selected='Load Basics', filler=0, depth=0, href='/loads', forms=None):
                    heading_group = '<div id="heading-group"><h1>'+heading+'</h1><input aria-label="PRIVATE_SEARCH" value="PRIVATE_SEARCH_VALUE"></div>'
                    heading_group = '<div>'*depth+heading_group+'</div>'*depth
                    other = 'Customer Info' if selected == 'Load Basics' else 'Load Basics'
                    nav = '<nav><ul><li class="active"><a href="'+href+'">'+selected+'</a></li><li><a href="/fixture-other">'+other+'</a></li></ul></nav>'
                    region = '<div id="form-region">'+(form()+form(1) if forms is None else forms)+region_extra+'</div>'
                    children = region+heading_group+nav if before else heading_group+nav+region
                    return provider_nav+'<main><h1>Load #1763</h1><div id="section-layout">'+children+branch+context_extra+'<span></span>'*filler+'</div></main>'

                async def inspect(body):
                    await page.evaluate("body=>document.body.innerHTML=body", body)
                    output = await page.evaluate("""()=>{try{
                      const workspace=FreightDeskWorkspace.observeWorkspace(document,null,1), section=FreightDeskWorkspace.observeSection(workspace);
                      return {section:section.name,root_id:section.root.id,signal:section.signal,diagnostic:section.diagnostic};
                    }catch(error){return {code:error.message,diagnostic:error.section_diagnostic};}}""")
                    MappingSectionDiagnostic.model_validate(output['diagnostic'])
                    assert 'PRIVATE' not in json.dumps(output)
                    return output

                good = await inspect(html())
                assert good['section'] == 'Load Basics' and good['root_id'] == 'form-region'
                assert good['signal'] == 'SELECTED_ROUTE_AND_VISIBLE_HEADING'
                relationship = good['diagnostic']['route_heading_diagnostic']
                assert relationship['root_relationship'] == 'SIBLING_FORM_REGION'
                assert relationship['visible_field_candidate_count'] == 2
                sibling = relationship['sibling_form_diagnostic']
                assert sibling['strategy'] == 'NEAREST_HEADING_CONTEXT_UNIQUE_LATER_FORM_REGION'
                assert sibling['selected_context_depth'] == 2 and sibling['failed_predicate'] is None
                proof = sibling['context_candidates'][-1]
                assert proof['heading_child_count'] == proof['form_bearing_child_count'] == 1
                assert proof['heading_child_index'] == 0 and proof['form_child_index'] == 2
                assert proof['all_visible_forms_contained'] is True and proof['visible_form_count'] == 2
                mapped = await page.evaluate("()=>FreightDeskWorkspace.capture(document,['1763'],()=>{})")
                AscendProviderMap.model_validate(mapped)
                assert mapped['workspace']['load_id'] == '1763'
                assert mapped['section']['coverage'] == 'CURRENT_VISIBLE_SECTION_ONLY'
                assert mapped['workspace']['navigation_candidates'] == []
                assert mapped['values_included'] is False and mapped['writes_allowed'] is False
                assert mapped['activation'] == 'CANDIDATE_ONLY' and 'PRIVATE' not in json.dumps(mapped)
                assert await page.evaluate('FreightDeskWorkspace.readerRevision') == 2

                cases = [
                    (html(branch='<div>'+form(2)+'</div>'), 'FORM_CHILD_NOT_UNIQUE'),
                    (html(region_extra='<button>Customer Info</button>'), 'FORM_REGION_CONTAINS_NAVIGATION'),
                    (html(before=True), 'FORM_REGION_PRECEDES_HEADING'),
                    (html(context_extra='<span data-load-workspace data-load-id="1763">Identity</span>'), 'CONTEXT_CONTAINS_IDENTITY'),
                    (html(context_extra='<h2>Financials</h2>'), 'CONTEXT_CONTAINS_OTHER_HEADING'),
                    (html(filler=22), 'DIRECT_CHILD_BOUND'),
                    (html(depth=8), 'CONTEXT_ANCESTOR_BOUND'),
                    (html(forms=''.join(form(i) for i in range(17))), 'CONTEXT_FORM_BOUND'),
                    (html(forms='<form><input aria-label="Equipment">'+'<input type="hidden">'*256+'</form>'), 'FORM_FIELD_BOUND'),
                ]
                for body, predicate in cases:
                    stopped = await inspect(body)
                    assert stopped['code'] == 'WORKSPACE_SECTION_UNVERIFIED', predicate
                    diagnostic = stopped['diagnostic']['route_heading_diagnostic']['sibling_form_diagnostic']
                    assert diagnostic['failed_predicate'] == predicate
                    assert diagnostic['selected_context_depth'] is None
                    if predicate == 'DIRECT_CHILD_BOUND':
                        assert diagnostic['context_candidates'][-1]['direct_child_count'] == 25
                    if predicate == 'CONTEXT_ANCESTOR_BOUND':
                        assert diagnostic['context_count'] == len(diagnostic['context_candidates']) == 8
                    if predicate == 'CONTEXT_FORM_BOUND':
                        assert diagnostic['context_candidates'][-1]['form_candidate_count'] == 17
                    if predicate == 'FORM_FIELD_BOUND':
                        assert diagnostic['context_candidates'][-1]['field_candidate_count'] == 257

                # An invisible second branch is outside current-visible-section coverage.
                hidden = await inspect(html(branch='<div hidden>'+form(2)+'</div>'))
                assert hidden['root_id'] == 'form-region'
                # URL or requested target names cannot substitute for provider-selected agreement.
                for kwargs, predicate in [({'heading':'Customer Info'}, 'MATCHING_HEADING_COUNT_ZERO'),
                    ({'href':'#'}, 'ROUTE_ANCHOR_COUNT_ZERO')]:
                    stopped = await inspect(html(**kwargs))
                    assert stopped['code'] == 'WORKSPACE_SECTION_UNVERIFIED'
                    assert stopped['diagnostic']['route_heading_diagnostic']['failed_predicate'] == predicate
                await inspect(html(selected='Customer Info', heading='Customer Info'))
                mismatch = await page.evaluate("""async()=>{try{
                  await FreightDeskWorkspace.capture(document,['1763'],()=>{},()=>{},performance.now(),{capture_load_id:'1763',capture_section:'Load Basics'});
                  return 'UNEXPECTED';}catch(error){return error.message;}}""")
                assert mismatch == 'STARTING_SECTION_MISMATCH'

                await inspect(html(forms='<form>'+'<input aria-label="Equipment">'*65+'</form>'))
                bounded_capture = await page.evaluate("""async()=>{const stages=[];try{
                  await FreightDeskWorkspace.capture(document,['1763'],()=>{},stage=>stages.push(stage));return {unexpected:true};
                }catch(error){return {code:error.message,stages};}}""")
                assert bounded_capture['code'] == 'WORKSPACE_BOUND'
                assert bounded_capture['stages'][-1]['stage'] == 'SECTION_IDENTIFIED'
                assert bounded_capture['stages'][-1]['section_diagnostic']['route_heading_diagnostic']['visible_field_candidate_count'] == 65

                await inspect(html())
                await page.evaluate("""()=>{
                  window.fixtureWrites=0;document.addEventListener('click',()=>fixtureWrites++);document.addEventListener('submit',()=>fixtureWrites++);
                  HTMLFormElement.prototype.submit=HTMLFormElement.prototype.requestSubmit=HTMLElement.prototype.click=()=>{fixtureWrites++;throw Error('WRITE_BLOCKED');};
                  Object.defineProperty(HTMLInputElement.prototype,'value',{get(){throw Error('PRIVATE_VALUE_READ');}});
                  const attribute=Element.prototype.getAttribute;Element.prototype.getAttribute=function(name){if(name.toLowerCase()==='value')throw Error('PRIVATE_VALUE_ATTRIBUTE_READ');return attribute.call(this,name);};
                  window.fetch=()=>{throw Error('NETWORK_BLOCKED');};window.XMLHttpRequest=()=>{throw Error('NETWORK_BLOCKED');};
                }""")
                safe = await page.evaluate("()=>FreightDeskWorkspace.capture(document,['1763'],()=>{})")
                AscendProviderMap.model_validate(safe)
                assert safe['values_included'] is False and safe['writes_allowed'] is False
                assert 'PRIVATE' not in json.dumps(safe) and await page.evaluate('fixtureWrites') == 0
            finally:
                await context.close()
                await browser.close()
    asyncio.run(run())
