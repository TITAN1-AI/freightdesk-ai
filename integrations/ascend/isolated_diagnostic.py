"""Separate owner-executed Ascend diagnostic. Persists metadata only, never operational facts."""
import json
import sqlite3
from datetime import date, timedelta
from uuid import uuid4

from app.core.config import ROOT
from app.core.runtime import RuntimePaths
from app.models.domain import ActionPolicy, utcnow
from app.policies.engine import PolicyEngine
from app.services.ascend_live import local_records
from app.services.live_ops_carrierview import MANIFEST_ID, PICKUPS, DELIVERIES, validate_reconciliation_scope
from app.services.multi_phase_progress import safe_failure
from app.services.store import Store
from integrations.ascend.field_discovery import ReadOnly1752Executor, TABS
from integrations.ascend.board_normalization import normalize_board, semantic_hash
from integrations.ascend.ops_discovery import board_candidates, read_candidate, select_active_loads_view, local_date
from integrations.ascend.session_continuity import checked_browser, owner_login_page

ATTEMPT='owner-multi-system-ascend-diagnostic-20260911-02'
TENANT='booking-logistics'
ORDER=tuple(sorted(PICKUPS|DELIVERIES,key=int))


def detail_metadata(candidate):
    groups={'load_identity':'load_number','carrier_assignment':'carrier','driver_identity':'driver',
        'driver_contact':'driver_phone','power_unit':'truck','trailer':'trailer','truck_status':'truck_status',
        'references':'reference','pickup_appointment':'pickup_start','delivery_appointment':'delivery_start'}
    result={}
    for group,key in groups.items():
        fact=candidate.facts.get(key)
        result[group]={'presence':'UNKNOWN' if not fact or not fact.verified or fact.value is None else
            'PRESENT' if fact.value.strip() else 'MISSING','mapping':'VERIFIED_FOR_THIS_OBSERVATION' if
            fact and fact.verified else 'UNKNOWN'}
    for group,kind in [('pickup_stops','pickup'),('delivery_stops','destination')]:
        present=candidate.additional_stops_verified and any(s.get('type')==kind and s.get('verified') for s in candidate.stops)
        result[group]={'presence':'PRESENT' if present else 'UNKNOWN','mapping':'VERIFIED_FOR_THIS_OBSERVATION' if present else 'UNKNOWN'}
    return {'field_groups':result,'detail_contract_version':'bounded-label-observation-v1',
            'general_contract_verified':False}


class LocalSession:
    def __init__(self,paths):
        self.paths=paths
        self.browser=checked_browser(paths)

    def running(self):
        controls=local_records(self.paths.path('Data',TENANT,'ascend.sqlite3'),'ascend_controls')
        return utcnow()<self.expires and PolicyEngine(ROOT/'config'/'policies.json').evaluate('read_ascend')==ActionPolicy.ALLOW and not any(
            c.get('paused',True) or c.get('human_takeover',True) for c in controls)

    async def confirm(self):
        self.page=await owner_login_page(self.browser,normal_application_network=True)
        self.expires=utcnow()+timedelta(minutes=30)
        self.executor=ReadOnly1752Executor(self.page,self.running)
        await self.executor.guard()

    async def board(self,selected):
        await self.executor.navigate_loads()
        await select_active_loads_view(self.executor)
        selected()
        return await normalize_board(self.executor,self.observe_board)

    async def detail(self,number,row,progress,event):
        return await read_candidate(self.page,number,ORDER,
            {'load_number':number,'pickup_date':row['pick_date'],'delivery_date':row['drop_date']},
            date(2026,9,11),self.running,ATTEMPT,'US',active_only=True,progress=progress,diagnostic=event)

    async def close(self):
        await self.browser.close()


def load_manifest(paths):
    path=paths.path('Data',TENANT,'operations','operations.sqlite3')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT body FROM records WHERE tenant=? AND kind=? AND id=?',
                       (TENANT,'ops_manifest',MANIFEST_ID)).fetchone()
    if not row:
        raise KeyError('manifest')
    return json.loads(row[0])


async def run_diagnostic(paths=None,session_factory=LocalSession,manifest_loader=load_manifest):
    paths=paths or RuntimePaths.from_environment()
    store=Store(paths.path('Data',TENANT,'ascend','diagnostics.sqlite3'))
    state={'attempt_id':ATTEMPT,'phase':'ascend_diagnostic','execution_stage':'PREFLIGHT',
        'current_load_id':None,'affected_load_id':None,'completed_load_count':0,'starting_board_hash':None,
        'ending_board_hash':None,'initial_board_reconciled':None,'board_changed':None,
        'board_current_at_failure':'UNKNOWN','last_known_board_reconciled':None,
        'section':None,'failed_field_or_mapping':'UNKNOWN','production_writes':False,
        'tenant_identity_source':'OWNER_ATTESTED','tenant_identity':'Booking Logistics'}
    session=None
    def checkpoint(stage):
        state['execution_stage']=stage
        store.put(TENANT,'diagnostic_checkpoint',ATTEMPT+':'+uuid4().hex,dict(state,observed_at=utcnow().isoformat()))
    def event(name,section):
        state['section']=section if section in TABS or section=='Current detail' else 'UNKNOWN'
        checkpoint(name)
    try:
        manifest=manifest_loader(paths)
        with store.transaction():
            if any(g['id']==ATTEMPT for g in store.all(TENANT,'diagnostic_grant')):
                raise PermissionError('one_use_phase_consumed_no_retry')
            store.put(TENANT,'diagnostic_grant',ATTEMPT,{'id':ATTEMPT,'consumed':True})
        session=session_factory(paths)
        def observe_board(metadata):
            state.update(metadata)
            checkpoint('BOARD_NORMALIZATION')
        session.observe_board=observe_board
        checkpoint('SESSION_CONFIRMATION')
        await session.confirm()
        checkpoint('SESSION_CONFIRMED')
        initial=await session.board(lambda:checkpoint('ACTIVE_LOADS_VIEW_SELECTED'))
        state.update(observed_row_count=initial['visible_rows'],
            pickup_count=sum(local_date(r.get('pick_date'),'US')==date(2026,9,11) for r in initial['rows']),
            delivery_count=sum(local_date(r.get('drop_date'),'US')==date(2026,9,11) for r in initial['rows']),
            starting_board_hash=semantic_hash(initial))
        try:
            current=board_candidates(initial,date(2026,9,11),'US',ATTEMPT)
            validate_reconciliation_scope(manifest,current)
            state.update(initial_board_reconciled=True,last_known_board_reconciled=True,reconciliation_status='OPS_BOARD_RECONCILED')
            state.update(normalized_board_hash=state['starting_board_hash'],starting_pickup_count=state['pickup_count'],
                         starting_delivery_count=state['delivery_count'],normalized_board_observed_at=utcnow().isoformat())
        except Exception:
            state.update(initial_board_reconciled=False,last_known_board_reconciled=False,reconciliation_status='OPS_BOARD_MISMATCH')
            checkpoint('BOARD_READ')
            raise
        checkpoint('BOARD_READ')
        checkpoint('BEGIN_DETAIL_READS')
        rows={r['load_id']:r for r in initial['rows']}
        for number in ORDER:
            state.update(current_load_id=number,affected_load_id=number,section=None)
            checkpoint('OPENING_LOAD')
            c=await session.detail(number,rows[number],checkpoint,event)
            if c.load_number!=number or not c.identity_verified:
                raise PermissionError('detail_load_identity_unverified')
            state['detail_metadata']=detail_metadata(c)
            checkpoint('LOAD_DETAIL_READ_COMPLETE')
            state['completed_load_count']+=1
            checkpoint('COMPLETED_LOAD_COUNT_UPDATED')
            state.pop('detail_metadata',None)
            del c
        state.update(current_load_id=None,affected_load_id=None,section=None)
        checkpoint('FINAL_BOARD_READ')
        end=await session.board(lambda:checkpoint('FINAL_ACTIVE_LOADS_VIEW_SELECTED'))
        state.update(ending_board_hash=semantic_hash(end),
            ending_pickup_count=sum(local_date(r.get('pick_date'),'US')==date(2026,9,11) for r in end['rows']),
            ending_delivery_count=sum(local_date(r.get('drop_date'),'US')==date(2026,9,11) for r in end['rows']))
        state['board_changed']=state['starting_board_hash']!=state['ending_board_hash']
        checkpoint('FINAL_BOARD_READ')
        final=board_candidates(end,date(2026,9,11),'US',ATTEMPT)
        validate_reconciliation_scope(manifest,final)
        state['board_current_at_failure']='RECONCILED_AT_FINAL_READ'
        if state['board_changed']:
            raise PermissionError('active_board_changed_during_details')
        state['last_known_board_reconciled']=True
        checkpoint('FINAL_BOARD_VERIFIED')
        closing,session=session,None
        checkpoint('BROWSER_CLOSE')
        await closing.close()
        state['status']='ASCEND_DIAGNOSTIC_COMPLETE'
        checkpoint('ASCEND_DIAGNOSTIC_COMPLETE')
    except Exception as error:
        code,reason=safe_failure(error)
        if code=='detail_load_identity_unverified':
            state['failed_field_or_mapping']='load_identity'
        state.update(status='STOPPED_ASCEND_DIAGNOSTIC',error_code=code,reason=reason)
        store.put(TENANT,'diagnostic_failure',ATTEMPT+':'+uuid4().hex,dict(state,observed_at=utcnow().isoformat()))
    finally:
        # Failure is already recorded. A secondary cleanup failure must not replace it.
        if session is not None:
            try:
                await session.close()
            except Exception:
                pass  # Primary failure is already durably recorded; no retry.
        store.close()
    return state
