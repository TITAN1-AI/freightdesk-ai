import asyncio
import json
from types import SimpleNamespace

import pytest

from app.services.multi_phase_progress import PhaseProgress, safe_failure
from app.services.store import Store
from integrations.ascend.models import AscendError
from scripts import multi_system_ops as module


@pytest.mark.parametrize('error,code',[
    (AscendError('detail_load_identity_unverified'),'detail_load_identity_unverified'),
    (AttributeError('PRIVATE_PHONE_COOKIE'),'internal_attribute_error'),
    (ValueError('PRIVATE_TOKEN'),'unexpected_phase_execution_error'),
    (KeyError('PRIVATE_ADDRESS'),'local_evidence_or_contract_key_missing'),
    (TimeoutError('PRIVATE_URL'),'bounded_read_timeout')])
def test_safe_codes_never_expose_exception_values(error,code):
    result=safe_failure(error)
    assert result[0]==code and 'PRIVATE' not in json.dumps(result)


def test_actual_ascend_loop_records_failed_load_and_completed_count(tmp_path,monkeypatch):
    store=Store(tmp_path/'ops.sqlite3')
    progress=PhaseProgress(store,module.RUN_ID,'ascend')
    cs=[SimpleNamespace(load_number=n) for n in ('1755','1756','1757')]
    grid={'rows':[{'load_id':c.load_number,'pick_date':'09/11/2026','drop_date':'09/12/2026'} for c in cs]}
    class Frame:
        async def evaluate(self,*args):
            return {'overflow':False,'grids':[grid]}
    class Executor:
        def __init__(self,*args):
            pass
        async def navigate_loads(self):
            pass
        async def guard(self):
            pass
        def frames(self):
            return [Frame()]
    async def login(*args,**kwargs):
        return object()
    async def no_op(*args):
        pass
    async def read(*args,**kwargs):
        kwargs['progress']('detail_identity_verification')
        if args[1]=='1757':
            raise AscendError('detail_load_identity_unverified')
        return cs[0]
    async def close():
        # Cleanup must not replace the first failure.
        raise RuntimeError('PRIVATE_CLEANUP_ERROR')
    monkeypatch.setattr(module,'checked_browser',lambda p:SimpleNamespace(close=close))
    monkeypatch.setattr(module,'owner_login_page',login)
    monkeypatch.setattr(module,'ReadOnly1752Executor',Executor)
    monkeypatch.setattr(module,'select_active_loads_view',no_op)
    monkeypatch.setattr(module,'board_candidates',lambda *args:cs)
    monkeypatch.setattr(module,'validate_reconciliation_scope',lambda *args:None)
    monkeypatch.setattr(module,'read_candidate',read)
    try:
        with pytest.raises(AscendError) as caught:
            asyncio.run(module.ascend(store,None,{},progress))
        result=progress.failed(caught.value)
        assert result['execution_stage']=='detail_identity_verification'
        assert result['affected_load_id']=='1757' and result['completed_load_count']==2
        assert result['initial_board_reconciled'] is True and result['board_changed'] is None
        assert not store.all('booking-logistics','multi_ascend')
        assert store.all('booking-logistics','multi_failure')[0]['error_code']=='detail_load_identity_unverified'
        assert 'PRIVATE' not in json.dumps(store.all('booking-logistics','multi_progress'))
    finally:
        store.close()


def test_run_returns_persisted_failure_without_consuming_later_phases(tmp_path,monkeypatch):
    class Paths:
        def path(self,*parts):
            return tmp_path.joinpath(*parts)
    paths=Paths()
    store=Store(paths.path('Data',module.TENANT,'operations','operations.sqlite3'))
    store.put(module.TENANT,'ops_manifest',module.MANIFEST_ID,{'id':module.MANIFEST_ID})
    store.close()
    async def fail(store,paths,manifest,progress):
        progress.stage('active_loads_refresh')
        raise AscendError('discovery_session_not_authenticated')
    monkeypatch.setattr(module.RuntimePaths,'from_environment',lambda:paths)
    monkeypatch.setattr(module,'phase_guard',lambda *args:None)
    monkeypatch.setattr(module,'ascend',fail)
    result=asyncio.run(module.run('ascend'))
    assert result['error_code']=='discovery_session_not_authenticated'
    assert result['completed_load_count']==0 and result['affected_load_id'] is None
    store=Store(paths.path('Data',module.TENANT,'operations','operations.sqlite3'))
    try:
        assert [r['phase'] for r in store.all(module.TENANT,'multi_read_grant')]==['ascend']
        assert len(store.all(module.TENANT,'multi_failure'))==1
    finally:
        store.close()
