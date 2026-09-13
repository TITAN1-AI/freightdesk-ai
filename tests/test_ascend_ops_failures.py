import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest

from integrations.ascend import ops_discovery as module


@pytest.mark.parametrize('href',['#active','/loads'])
def test_active_link_uses_python_prefix_check(href):
    calls=[]
    class Control:
        async def count(self):
            return 1
        async def is_visible(self):
            return True
        async def evaluate(self,script):
            return {'tag':'A','role':None,'type':None,'inForm':False,'href':href}
        async def get_attribute(self,key):
            return None
        async def click(self,**kwargs):
            calls.append('click')
    class Empty(Control):
        async def count(self):
            return 0
    class Frame:
        def get_by_role(self,role,**kwargs):
            return Control() if role=='link' else Empty()
    async def guard():
        calls.append('guard')
    executor=SimpleNamespace(frames=lambda:[Frame()],guard=guard)
    asyncio.run(module.select_active_loads_view(executor))
    assert calls==['click','guard']
    # The old implementation fails before click for these same nonempty strings.
    with pytest.raises(AttributeError):
        getattr(href,'startsWith')('#')


def test_failure_reports_stage_without_private_exception(tmp_path,monkeypatch):
    class Paths:
        def path(self,*parts):
            return tmp_path.joinpath(*parts)
    async def close():
        pass
    async def login(*args,**kwargs):
        return object()
    class Executor:
        def __init__(self,*args):
            pass
        async def navigate_loads(self):
            pass
    async def fail(executor):
        raise AttributeError('PRIVATE_COOKIE_TOKEN_DRIVER_DATA')
    monkeypatch.setattr(module,'checked_browser',lambda p:SimpleNamespace(close=close))
    monkeypatch.setattr(module,'owner_login_page',login)
    monkeypatch.setattr(module,'ReadOnly1752Executor',Executor)
    monkeypatch.setattr(module,'select_active_loads_view',fail)
    result=asyncio.run(module.login_discover_ops(service_date=date(2026,9,11),
        attempt_id='synthetic-failure-001',board_date_format='US',paths=Paths()))
    assert result['error_code']=='ops_internal_attribute_error'
    assert result['stage']=='active_loads_view_selection'
    assert result['reason'] and result['status']=='STOPPED_OPS_DISCOVERY'
    assert 'PRIVATE' not in json.dumps(result)
    saved=list(tmp_path.rglob('ops-discovery-result-*.json'))
    assert len(saved)==1 and 'PRIVATE' not in saved[0].read_text(encoding='utf-8')


@pytest.mark.parametrize('error',[ValueError('PRIVATE_TOKEN'),TimeoutError('PRIVATE_URL')])
def test_unknown_failure_messages_are_never_exposed(error):
    result=module.sanitized_failure(error)
    assert result['error_code'] and result['reason']
    assert 'PRIVATE' not in json.dumps(result)
