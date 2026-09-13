"""Owner-bound API tests; injected orchestrator and intercepted dashboard only."""
import asyncio
import json
import os
from pathlib import Path

from app.api import ascend_mapping
from tests.test_x1_runtime_api import runtime_client as runtime_client, owner


def test_mapping_owner_boundary_and_one_action(runtime_client, monkeypatch):
    client, _ = runtime_client
    calls=[]
    class Orchestrator:
        def status(self):
            return {'status':'IDLE','stage':'PREFLIGHT'}
        def start(self, intent, **kw):
            calls.append(('start',intent,kw))
            return {'status':'VERIFY_SESSION','stage':'VERIFY_SESSION'}
        def control(self, action, **kw):
            calls.append((action,kw))
            return {'stage':'STOPPED'}
    monkeypatch.setattr(ascend_mapping,'mapping_orchestrator',Orchestrator)
    assert client.post('/api/ascend/mapping/control',json={'action':'start'}).status_code in {401,403}
    owner(client)
    assert client.get('/api/ascend/mapping/status').status_code==200 and calls==[]
    response=client.post('/api/ascend/mapping/control',json={'action':'start','intent':{'scope':'CURRENT_LOAD'}})
    assert response.status_code==200
    assert calls[0][0]=='start' and calls[0][2]['owner_authorized'] is True
    assert client.post('/api/ascend/mapping/control',json={'action':'SAVE'}).status_code==422
    assert client.post('/api/ascend/mapping/control',json={'action':'start','intent':{'scope':'CURRENT_LOAD','selector':'PRIVATE'}}).status_code==422


def test_dashboard_mapping_controls_offline(tmp_path):
    async def run():
        from playwright.async_api import async_playwright
        root=Path(__file__).resolve().parents[1]
        status={'status':'IDLE','stage':'PREFLIGHT','scope':'CURRENT_LOAD','message':'Ready','review_sections':[]}
        calls=[]
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(channel='msedge',headless=True,env={**os.environ,'TEMP':str(tmp_path),'TMP':str(tmp_path)})
            context=await browser.new_context(service_workers='block')
            async def serve(route):
                url=route.request.url
                if '/api/ascend/mapping/' in url:
                    if url.endswith('/control'):
                        calls.append(route.request.post_data_json)
                        status.update(status='OWNER_REVIEW_REQUIRED',stage='OWNER_REVIEW_REQUIRED',needs_review=True,owner_action='REVIEW_NEW_NAVIGATION',review_sections=['Load Basics','Customer Info'])
                    return await route.fulfill(content_type='application/json',body=json.dumps(status))
                if url.endswith('/assets/styles.css'):
                    return await route.fulfill(content_type='text/css',body=(root/'app/dashboard/styles.css').read_text(encoding='utf-8'))
                if url.endswith('/assets/ascend-mapping.js'):
                    return await route.fulfill(content_type='text/javascript',body=(root/'app/dashboard/ascend-mapping.js').read_text(encoding='utf-8-sig'))
                # Use the real panel markup; all navigation/resources are fixture fulfilled.
                html=(root/'app/dashboard/index.html').read_text(encoding='utf-8')
                panel=html[html.index('<section class="panel" id="ascend-mapping"'):html.index('<section class="panel" id="x1-runtime"')]
                return await route.fulfill(content_type='text/html',body='<link rel="stylesheet" href="/assets/styles.css"><main>'+panel+'</main><script src="/assets/ascend-mapping.js"></script>')
            await context.route('**/*',serve)
            page=await context.new_page()
            await page.goto('http://localhost:8787/fixture')
            await page.locator('[data-mapping-action=start]').click()
            await page.locator('#mapping-review').wait_for(state='visible')
            assert calls==[{'action':'start','intent':{'scope':'CURRENT_LOAD'}}]
            assert await page.locator('#mapping-review-sections input').count()==2
            assert not await page.locator('#mapping-review-sections input:checked').count()
            assert 'session-id' not in await page.locator('#ascend-mapping').inner_text()
            await page.screenshot(path=str(tmp_path/'mapping-panel.png'))
            await context.close()
            await browser.close()
    asyncio.run(run())
