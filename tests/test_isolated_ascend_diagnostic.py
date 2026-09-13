import asyncio
import json
import sqlite3
from datetime import date

import pytest

from app.services.live_ops import OpsCandidate, OpsFact
from app.services.live_ops_carrierview import MANIFEST_ID, PICKUPS, DELIVERIES
from integrations.ascend import isolated_diagnostic as module
from integrations.ascend.models import AscendError
from integrations.ascend.ops_board import FIELDS


def setup(tmp_path,fail_at=None,changed=False,wrong_counts=False,cleanup_fails=False):
    class Paths:
        def path(self,*parts):
            return tmp_path.joinpath(*parts)
    rows=[dict.fromkeys(FIELDS,'')|{'load_id':n,'pick_date':'09/11/2026' if n in PICKUPS else '09/10/2026',
          'drop_date':'09/11/2026' if n in DELIVERIES else '09/12/2026'} for n in module.ORDER]
    if wrong_counts:
        rows[0]['pick_date']='09/10/2026'
    grid={'rows':rows,'visible_rows':12,'unknown_dates':0,'pagination':{}}
    manifest={'id':MANIFEST_ID,'service_date':'2026-09-11','source_view':'Active Loads',
        'reconciliation_status':'OPS_BOARD_RECONCILED','observed_at':'2026-09-11T00:00:00Z',
        'immutable_evidence_hash':'fixture','PICKUP_TRACKING_QUEUE':[{'load_number':n} for n in PICKUPS],
        'DELIVERY_WATCH_QUEUE':[{'load_number':n} for n in DELIVERIES]}
    class Session:
        reads=[]
        boards=0
        async def confirm(self):
            pass
        async def board(self,selected):
            selected()
            self.boards+=1
            if changed and self.boards==2:
                return grid | {'rows':[dict(r,load_status='changed') for r in grid['rows']]}
            return grid
        async def detail(self,number,row,progress,event):
            self.reads.append(number)
            progress('detail_identity_verification')
            if len(self.reads)-1==fail_at:
                raise AscendError('detail_load_identity_unverified')
            event('LOAD_IDENTITY_VERIFIED','Current detail')
            return OpsCandidate(load_number=number,service_date=date(2026,9,11),identity_verified=True,
                facts={'driver_phone':OpsFact(value='+15555550123',source='AscendTMS',verified=True,source_reference='PRIVATE_SOURCE'),
                       'driver':OpsFact(value='PRIVATE_DRIVER',source='AscendTMS',verified=True,source_reference='fixture')})
        async def close(self):
            if cleanup_fails:
                raise ValueError('PRIVATE_CLEANUP_ERROR')
    session=Session()
    paths=Paths()
    def run():
        return asyncio.run(module.run_diagnostic(paths,lambda p:session,lambda p:manifest))
    def records():
        with sqlite3.connect(paths.path('Data','booking-logistics','ascend','diagnostics.sqlite3')) as db:
            return [(k,json.loads(b)) for k,b in db.execute('SELECT kind,body FROM records ORDER BY rowid')]
    return run,records,session,paths


@pytest.mark.parametrize('fail_at',[0,2])
def test_first_failure_checkpoints_and_cleanup_preserves_root(tmp_path,fail_at):
    run,records,session,paths=setup(tmp_path,fail_at=fail_at,cleanup_fails=True)
    result=run()
    assert result['error_code']=='detail_load_identity_unverified'
    assert result['affected_load_id']==module.ORDER[fail_at]
    assert result['completed_load_count']==fail_at
    assert result['execution_stage']=='detail_identity_verification'
    assert result['starting_board_hash'] and result['initial_board_reconciled'] is True
    assert result['board_current_at_failure']=='UNKNOWN'
    assert session.reads==list(module.ORDER[:fail_at+1])
    entries=records()
    stages=[b['execution_stage'] for k,b in entries if k=='diagnostic_checkpoint']
    assert 'BOARD_READ' in stages and stages.count('OPENING_LOAD')==fail_at+1
    assert stages.count('LOAD_DETAIL_READ_COMPLETE')==fail_at
    assert stages.count('COMPLETED_LOAD_COUNT_UPDATED')==fail_at
    assert 'PRIVATE' not in json.dumps(entries) and '15555550123' not in json.dumps(entries)
    assert not paths.path('Data','booking-logistics','operations','operations.sqlite3').exists()
    assert {k for k,_ in entries}=={'diagnostic_grant','diagnostic_checkpoint','diagnostic_failure'}


def test_success_all_eleven_and_no_phase_advancement(tmp_path):
    run,records,session,_=setup(tmp_path)
    result=run()
    assert result['status']=='ASCEND_DIAGNOSTIC_COMPLETE'
    assert result['completed_load_count']==11 and session.reads==list(module.ORDER)
    assert result['starting_board_hash']==result['ending_board_hash']
    assert result['ending_pickup_count']==8 and result['ending_delivery_count']==3
    stages=[b['execution_stage'] for k,b in records() if k=='diagnostic_checkpoint']
    assert stages.count('LOAD_IDENTITY_VERIFIED')==11
    assert stages.count('LOAD_DETAIL_READ_COMPLETE')==11
    assert stages.index('BOARD_READ')<stages.index('BEGIN_DETAIL_READS')
    assert {k for k,_ in records()}=={'diagnostic_grant','diagnostic_checkpoint'}
    second=run()
    assert second['error_code']=='one_use_phase_consumed_no_retry'
    assert len(session.reads)==11


def test_previous_attempt_grant_does_not_block_new_namespace(tmp_path):
    from app.services.store import Store
    run,_,session,paths=setup(tmp_path)
    db=Store(paths.path('Data','booking-logistics','ascend','diagnostics.sqlite3'))
    previous='owner-multi-system-ascend-diagnostic-20260911-01'
    db.put('booking-logistics','diagnostic_grant',previous,{'id':previous,'consumed':True})
    db.close()
    assert run()['status']=='ASCEND_DIAGNOSTIC_COMPLETE' and len(session.reads)==11


def test_changed_board_stops_after_eleven(tmp_path):
    run,_,session,_=setup(tmp_path,changed=True)
    result=run()
    assert result['error_code']=='active_board_changed_during_details'
    assert result['board_changed'] and len(session.reads)==11


def test_exact_board_counts_stop_before_details(tmp_path):
    run,records,session,_=setup(tmp_path,wrong_counts=True)
    result=run()
    assert result['initial_board_reconciled'] is False and result['pickup_count']==7
    assert result['execution_stage']=='BOARD_READ' and not session.reads
    assert any(k=='diagnostic_checkpoint' and b['execution_stage']=='BOARD_READ' for k,b in records())
