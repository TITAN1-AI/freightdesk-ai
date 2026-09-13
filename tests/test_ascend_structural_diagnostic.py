import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from integrations.ascend.structural_diagnostic import poll_structure, structural_snapshot

FIXTURE = 'https://ascend-fixture.invalid'
NAV = '<nav>'+''.join('<a href="#">'+name+'</a>' for name in
    ('Dashboard', 'Loads', 'Customers', 'Carriers', 'Locations', 'Reporting', 'Accounting', 'Settings'))+'</nav>'


@pytest.mark.parametrize('scenario', ['delayed', 'iframe_nav', 'iframe_login', 'routes_only', 'no_app'])
def test_real_edge_structural_scenarios(tmp_path, scenario):
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as runtime:
            context = await runtime.chromium.launch_persistent_context(str(tmp_path/'fixture-profile'),
                channel='msedge', headless=True, service_workers='block',
                env={**os.environ, 'TEMP':str(tmp_path), 'TMP':str(tmp_path)})
            try:
                html = '<title>AscendTMS</title>'
                frame_html = NAV
                if scenario == 'delayed':
                    html += '<div id="app"></div><script>setTimeout(()=>{document.querySelector("#app").innerHTML='+json.dumps(NAV)+'}, 250)</script>'
                elif scenario == 'iframe_nav':
                    html += '<iframe src="/embedded?secret=DO_NOT_LOG"></iframe>'
                elif scenario == 'iframe_login':
                    html += NAV+'<iframe src="https://foreign.invalid/login?token=DO_NOT_LOG"></iframe>'
                    frame_html = '<form><input type="password"></form>'
                elif scenario == 'routes_only':
                    html += ''.join('<a href="'+route+'?token=DO_NOT_LOG">icon</a>' for route in
                                    ('/', '/loads', '/customers', '/carriers', '/locations', '/accounting'))
                else:
                    html += '<div></div>'
                requests = []
                async def fulfill(route):
                    requests.append(route.request.method)
                    await route.fulfill(content_type='text/html', body=html if route.request.url == FIXTURE+'/' else frame_html)
                await context.route('**/*', fulfill)
                page = await context.new_page()
                await page.goto(FIXTURE+'/', wait_until='load')
                result = await poll_structure(page, origin=FIXTURE, render_seconds=0.8, interval=0.05)
                assert result['session_authenticated_recommended'] == (scenario in {'delayed','iframe_nav','routes_only'})
                if scenario == 'delayed':
                    assert result['render_wait_elapsed'] >= 0.2
                if scenario.startswith('iframe'):
                    assert result['frame_count'] == 2 and result['all_frames_inspected']
                if scenario == 'iframe_login':
                    assert result['login_form_found'] and not result['frames'][1]['same_origin']
                    assert result['frames'][1]['same_origin_path'] is None
                if scenario == 'routes_only':
                    assert result['dashboard_marker_count'] == 0
                    assert result['authenticated_route_link_count'] == 5
                if scenario == 'no_app':
                    assert result['body_text_length'] == 0 and result['render_wait_elapsed'] >= 0.75
                encoded = json.dumps(result)
                assert 'DO_NOT_LOG' not in encoded and 'foreign.invalid' not in encoded and '<nav>' not in encoded
                assert 'body_text' not in result and set(requests) == {'GET'}
                # Root links alone are never authenticated-app evidence.
                await page.set_content('<a href="/">Home</a>')
                assert not (await structural_snapshot(page, origin=FIXTURE))['session_authenticated_recommended']
            finally:
                await context.close()
    asyncio.run(run())


def test_diagnostic_only_root_existing_profile_and_no_grant(tmp_path, monkeypatch):
    from integrations.ascend import structural_diagnostic as module
    calls = []
    class Page:
        async def goto(self, url, **kwargs):
            calls.append(url)
    class Browser:
        channel = 'msedge'
        profile = Path(r'C:\FreightDeskRuntime\Browser\booking-logistics\ascend')
        def __init__(self, paths):
            pass
        async def launch(self, **kwargs):
            assert kwargs == {'owner_authorized':True, 'require_existing':True}
            return SimpleNamespace(pages=[Page()])
        async def readonly_network(self, origin):
            assert origin == module.ORIGIN
        async def close(self):
            calls.append('closed')
    async def poll(page):
        return {'session_authenticated_recommended':False}
    monkeypatch.setattr(module, 'AveryBrowserSession', Browser)
    monkeypatch.setattr(module, 'poll_structure', poll)
    paths = SimpleNamespace(path=lambda *parts:tmp_path.joinpath(*parts))
    result = asyncio.run(module.run_structural_diagnostic(paths=paths))
    assert calls == [module.ORIGIN+'/', 'closed']
    assert not result['load_validation_attempt_consumed'] and not result['load_opened']
    assert result['tenant_identity_source'] == 'OWNER_ATTESTED'
    files = [p for p in tmp_path.rglob('*') if p.is_file()]
    assert len(files) == 1 and files[0].name.startswith('structural-diagnostic-')
