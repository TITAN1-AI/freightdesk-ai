import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.models.domain import ActionPolicy
from executors.ascend_extension.contracts import OPERATIONS, ReadCommand
from executors.ascend_extension.executor import AscendExtensionExecutor, safe_result
from executors.ascend_extension.native import NativeAuthenticator, canonical, decode_message, encode_message
from integrations.ascend.ops_board import HEADERS

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT/'extensions'/'ascend-x1'


def command(operation='ASCEND_GET_SESSION_STATE', load=None, revision=None):
    return ReadCommand(request_id=uuid4().hex, operation=operation, load_id=load, expected_revision=revision)


def test_manifest_and_installation_are_restricted_and_dormant():
    manifest=json.loads((EXT/'manifest.json').read_text())
    assert manifest['manifest_version']==3
    assert manifest['host_permissions']==['https://ascendtms.com/*']
    # 0.4.1 added fixed packaged ISOLATED content-script recovery; no new permission in 0.4.2.
    assert manifest['permissions']==['nativeMessaging','storage','alarms','scripting']
    assert manifest['content_scripts'][0]['matches']==manifest['host_permissions']
    assert not manifest['content_scripts'][0]['all_frames']
    assert not any(k in manifest for k in ['externally_connectable','web_accessible_resources','optional_permissions'])
    for name in ('content.js','background.js'):
        text=(EXT/name).read_text()
        assert 'PRODUCTION_CONNECTION_ENABLED=false' in text
        assert not any(t in text for t in ('fetch(', 'WebSocket(', 'document.cookie', 'eval(', 'new Function'))


@pytest.mark.parametrize('mutation', [
    {'operation':'ASCEND_SAVE_LOAD'}, {'operation':'ASCEND_SET_DRIVER'}, {'operation':'eval'},
    {'script':'window.steal()'}, {'selector':'input'}, {'tenant_id':'other'}, {'actor':'other'},
    {'load_id':'1755'}, {'request_id':'PRIVATE_TOKEN'},
])
def test_command_contract_rejects_untyped_or_unbound_inputs(mutation):
    with pytest.raises(ValueError):
        ReadCommand.model_validate(command().model_dump()|mutation)


def test_native_authentication_replay_and_framing():
    key=os.urandom(32)
    auth=NativeAuthenticator('a'*32,key)
    with pytest.raises(PermissionError):
        auth.challenge('chrome-extension://'+'b'*32+'/')
    challenge=auth.challenge(auth.origin)
    with pytest.raises(PermissionError):
        auth.authenticate(auth.origin,'0'*64)
    auth.authenticate(auth.origin,hmac.new(key,canonical(challenge),hashlib.sha256).hexdigest())
    message={'session_id':auth.session_id,'sequence':1,'direction':'extension_to_host','body':{'load_id':'1755'}}
    signed=message|{'mac':hmac.new(key,canonical(message),hashlib.sha256).hexdigest()}
    assert auth.verify(auth.origin,decode_message(encode_message(signed)))=={'load_id':'1755'}
    for bad in (signed,signed|{'sequence':2},auth.sign({'load_id':'1755'})):
        with pytest.raises(PermissionError):
            auth.verify(auth.origin,bad)
    with pytest.raises(ValueError):
        decode_message(b'\xff\xff\xff\xff')
    with pytest.raises(ValueError):
        encode_message({'data':'x'*65536})


def test_executor_policy_scope_audit_and_closed_transport():
    events=[]
    class Policy:
        def evaluate(self, action):
            assert action=='read_ascend'
            return ActionPolicy.ALLOW
    class MockTransport:
        calls=0
        async def exchange(self, cmd):
            self.calls+=1
            return {'session_authenticated':True,'path':'/loads','tenant_identity_source':'OWNER_ATTESTED'}
    transport=MockTransport()
    executor=AscendExtensionExecutor(Policy(),lambda:True,events.append,transport=transport)
    with pytest.raises(PermissionError):
        asyncio.run(executor.execute_read(command()))
    assert transport.calls==0
    executor.live_enabled=True  # Offline injected transport only.
    read=command()
    assert asyncio.run(executor.execute_read(read))['session_authenticated']
    with pytest.raises(PermissionError):
        asyncio.run(executor.execute_read(read))
    with pytest.raises(PermissionError):
        asyncio.run(executor.execute_read(command('ASCEND_READ_LOAD','1755','a'*64)))
    executor.approved_loads=frozenset({'1755'})
    with pytest.raises(PermissionError):  # A session-only response cannot satisfy detail identity.
        asyncio.run(executor.execute_read(command('ASCEND_READ_LOAD','1755','a'*64)))
    for response in ({'cookies':'PRIVATE'}, {'load_status':'PRIVATE_DRIVER'}, {'driver_presence':'PRIVATE_PHONE'}):
        with pytest.raises(ValueError):
            safe_result(response)
    assert all(e['tenant_id']=='booking-logistics' and e['actor']=='FreightDesk/Avery' for e in events)
    assert not any('result' in e for e in events)
    with pytest.raises(PermissionError):
        asyncio.run(executor.navigate('https://ascendtms.com/loads'))
    with pytest.raises(PermissionError):
        asyncio.run(executor.read('input'))


def test_extension_dom_fixtures_only(tmp_path):
    async def run():
        from playwright.async_api import async_playwright
        nav='<nav>'+''.join('<a href="#">'+n+'</a>' for n in ('Dashboard','Loads','Customers','Carriers','Locations','Reporting','Accounting','Settings'))+'</nav>'
        hs='<thead><tr>'+''.join('<th>'+(h or '')+'</th>' for h in HEADERS)+'</tr></thead>'
        values=['PRIVATE']*33
        values[0]='<a id="open" href="#detail" data-target="#detail" data-load-id="1755">1755</a>'
        values[1]='Dispatched'
        values[5]='09/11/2026'
        values[7]='09/12/2026'
        values[21]='UNKNOWN'
        board='<button role="tab" aria-selected="true">Active Loads</button><table>'+hs+'<tbody><tr>'+''.join('<td>'+v+'</td>' for v in values)+'</tr></tbody></table>'
        # Eight decorative tables and a header clone must not replace a data-bearing grid.
        markup=nav+'<table>'+hs+'</table>'+ '<table><tr><td>Decoration</td></tr></table>'*8+board
        async with async_playwright() as runtime:
            context=await runtime.chromium.launch_persistent_context(str(tmp_path/'profile'),channel='msedge',headless=True,
                service_workers='block',env={**os.environ,'TEMP':str(tmp_path),'TMP':str(tmp_path)})
            await context.route('**/*',lambda r:r.fulfill(content_type='text/html',body='<title>AscendTMS</title>'))
            try:
                for case in ('detail_field','opener_binding','selected_binding','conflict','click_alone','multiple','stale','user_selection','no_change'):
                    page=await context.new_page()
                    await page.goto('https://ascendtms.com/loads?token=PRIVATE_QUERY')
                    await page.set_content(markup)
                    if case=='no_change':
                        await page.evaluate("() => document.body.insertAdjacentHTML('beforeend','<div role=dialog id=detail>Existing panel</div>')")
                    for name in ('contract.js','load-board-view.js','reader.js'):
                        await page.add_script_tag(path=str(EXT/name))
                    await page.evaluate('''async () => {
                        Object.defineProperty(document,'cookie',{get(){throw Error('cookie read forbidden');}});
                        window.reader=await FreightDeskX1Reader.create(document,location.origin);
                    }''')
                    async def execute(op, load=None, revision=None):
                        return await page.evaluate('(c)=>reader.execute(c)',command(op,load,revision).model_dump())
                    session=await execute('ASCEND_GET_SESSION_STATE')
                    assert session['session_authenticated']
                    data=await execute('ASCEND_GET_ACTIVE_LOADS')
                    assert data['rows'][0]['load_id']=='1755' and len(data['rows'])==1
                    assert 'PRIVATE' not in json.dumps(data)
                    assert (await execute('ASCEND_FIND_LOAD','1755',data['revision']))['exact_row']
                    await page.evaluate('''kind => {
                        const open=document.querySelector('#open');
                        if(['detail_field','selected_binding','click_alone'].includes(kind))open.removeAttribute('data-load-id');
                        if(kind==='click_alone'){open.setAttribute('href','#');open.removeAttribute('data-target');}
                        open.addEventListener('click',e=>{
                            e.preventDefault();
                            if(kind==='no_change')return;
                            if(kind==='selected_binding')open.setAttribute('aria-expanded','true');
                            const panel=document.createElement('div');panel.id='detail';panel.setAttribute('role','dialog');
                            panel.innerHTML='<h2>Stops</h2><h3>Appointments</h3><textarea>PRIVATE_NOTES</textarea>';
                            if(['detail_field','conflict'].includes(kind))panel.innerHTML+='<label for=load-id>Load ID</label><input id=load-id value='+ (kind==='conflict'?'1756':'1755') +'>';
                            document.body.append(panel);
                            if(kind==='multiple')document.body.append(panel.cloneNode(true));
                        });
                    }''',case)
                    if case=='user_selection':
                        await page.evaluate("() => document.addEventListener('click',e=>{window.selection=reader.observeSelected(e);},{capture:true,once:true})")
                        await page.locator('#open').click()
                        assert (await page.evaluate('selection')).get('selection_observed')
                        await page.close()
                        continue
                    await execute('ASCEND_OPEN_LOAD_READONLY','1755',data['revision'])
                    if case=='stale':
                        await page.evaluate("() => document.querySelector('#open').closest('tr').children[1].textContent='Delivered'")
                    if case in ('conflict','click_alone','multiple','stale','no_change'):
                        with pytest.raises(Exception):
                            await execute('ASCEND_READ_LOAD','1755',data['revision'])
                    else:
                        result=await execute('ASCEND_READ_LOAD','1755',data['revision'])
                        assert result['identity']['provider_observed_load_id']=='1755'
                        assert result['stop_section_presence'] and result['appointment_section_presence']
                        safe_result(result)
                        assert 'PRIVATE' not in json.dumps(result)
                    for operation in ('ASCEND_SAVE_LOAD','ASCEND_SET_DRIVER','eval'):
                        payload=command().model_dump()|{'operation':operation,'script':'PRIVATE_JS'}
                        with pytest.raises(Exception):
                            await page.evaluate('(c)=>reader.execute(c)',payload)
                    await page.close()
                page=await context.new_page()
                await page.goto('https://unrelated.invalid/')
                for name in ('contract.js','load-board-view.js','reader.js'):
                    await page.add_script_tag(path=str(EXT/name))
                with pytest.raises(Exception):
                    await page.evaluate('()=>FreightDeskX1Reader.create(document,location.origin)')
                await page.close()
            finally:
                await context.close()
    asyncio.run(run())


def test_python_js_command_names_match():
    text=(EXT/'contract.js').read_text()
    assert all(op in text for op in OPERATIONS)
