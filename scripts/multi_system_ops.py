"""Owner-run staged POC002 reads. No production write or canonical store is reachable."""
import argparse
import asyncio
import json
import os
import sys
from datetime import date, timedelta

from pydantic import SecretStr

from app.core.config import ROOT
from app.core.runtime import RuntimePaths
from app.models.domain import ActionPolicy, utcnow
from app.policies.engine import PolicyEngine
from app.services.ascend_live import local_records
from app.services.carrierview_audit import CarrierViewAudit
from app.services.carrierview_replay_discovery import SERVICE_REASON
from app.services.live_ops import OpsCandidate, TENANT, TrackingEvidence
from app.services.live_ops_carrierview import MANIFEST_ID, reconcile_ops, validate_reconciliation_scope
from app.services.mail_view import graph_audit
from app.services.multi_system_ops import email_proposals, outlook_targets, report
from app.services.multi_phase_progress import PhaseProgress, safe_failure
from app.services.store import Store
from integrations.ascend.field_discovery import ReadOnly1752Executor
from integrations.ascend.ops_board import FIELDS, HEADERS, SCAN, select_grid
from integrations.ascend.ops_discovery import board_candidates, read_candidate, select_active_loads_view
from integrations.ascend.session_continuity import checked_browser, owner_login_page
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.config import CarrierViewConfig, CredentialClass
from integrations.carrierview.contract import ResponseContract

RUN_ID='owner-multi-system-20260911-01'


def candidates(store):
    return [OpsCandidate.model_validate(r) for r in store.get(TENANT,'multi_ascend',RUN_ID)['candidates']]


def phase_guard(paths,action):
    if PolicyEngine(ROOT/'config'/'policies.json').evaluate(action)!=ActionPolicy.ALLOW:
        raise PermissionError('read_policy_not_allow')
    controls=local_records(paths.path('Data',TENANT,'ascend.sqlite3'),'ascend_controls')
    if any(c.get('paused',True) or c.get('human_takeover',True) for c in controls):
        raise PermissionError('paused_or_human_takeover')


def fresh(c):
    if not c or any(not x.facts or any(not timedelta(0)<=utcnow()-f.observed_at<=timedelta(hours=4)
            for f in x.facts.values() if f.verified) for x in c):
        raise PermissionError('fresh_ascend_detail_evidence_required')


async def ascend(store,paths,manifest,progress=None):
    progress=progress or PhaseProgress(store,RUN_ID,'ascend')
    progress.stage('browser_launch_owner_confirmation')
    browser=checked_browser(paths)
    try:
        page=await owner_login_page(browser,normal_application_network=True)
        expires=utcnow()+timedelta(minutes=30)
        def running():
            phase_guard(paths,'read_ascend')
            return utcnow()<expires
        executor=ReadOnly1752Executor(page,running)
        async def board(final=False):
            progress.stage('final_board_freshness_check' if final else 'active_loads_refresh')
            await executor.navigate_loads()
            if not final:
                progress.stage('active_loads_view_selection')
            await select_active_loads_view(executor)
            args={'headers':HEADERS,'fields':FIELDS,'display_date':'09/11/2026','format':'US'}
            results=[]
            if not final:
                progress.stage('data_grid_detection')
            for _ in range(20):
                await executor.guard()
                results=[await frame.evaluate(SCAN,args) for frame in executor.frames()]
                if any(r['overflow'] or r['grids'] for r in results):
                    break
                await asyncio.sleep(0.5)
            return select_grid(results)
        initial=await board()
        progress.stage('board_reconciliation')
        current=board_candidates(initial,date(2026,9,11),'US',RUN_ID)
        validate_reconciliation_scope(manifest,current)
        progress.data['initial_board_reconciled']=True
        rows={r['load_id']:r for r in initial['rows']}
        extracted=[]
        for c in current:
            progress.load(c.load_number)
            r=rows[c.load_number]
            candidate=await read_candidate(page,c.load_number,tuple(rows),
                {'load_number':c.load_number,'pickup_date':r['pick_date'],'delivery_date':r['drop_date']},
                date(2026,9,11),running,RUN_ID,'US',active_only=True,progress=progress.stage)
            extracted.append(candidate)
            progress.completed()
        progress.data['affected_load_id']=None
        progress.data['board_changed']=initial!=await board(final=True)
        progress.stage('final_board_freshness_check')
        if progress.data['board_changed']:
            raise PermissionError('active_board_changed_during_details')
        validate_reconciliation_scope(manifest,extracted)
        progress.stage('persistence')
        store.put(TENANT,'multi_ascend',RUN_ID,{'candidates':[c.model_dump(mode='json') for c in extracted],
            'source_manifest':MANIFEST_ID,'observed_at':utcnow().isoformat()})
    finally:
        primary=sys.exception()
        if primary is None:
            progress.stage('browser_close')
        try:
            await browser.close()
        except Exception:
            if primary is None:
                raise


async def carrierview(store,paths,manifest):
    current=candidates(store)
    fresh(current)
    validate_reconciliation_scope(manifest,current)
    config=CarrierViewConfig(api_token=SecretStr(os.environ['CARRIERVIEW_TENANT_API_TOKEN']),
        base_url='https://carrierview.com',credential_class=CredentialClass.TENANT,elevation_reason=SERVICE_REASON,
        origin_verified=True,network_reads_authorized=True,discovery_reads_authorized=True)
    phase_guard(paths,'read_tracking')
    def audit(event):
        phase_guard(paths,'read_tracking')
        CarrierViewAudit(store,TENANT,'FreightDesk/Avery')(event)
    async with CarrierViewAdapter(config,ResponseContract(source_reference='Owner supplied active/future read scope',selectors={}),
                                  audit) as adapter:
        result=await reconcile_ops(adapter,[c.load_number for c in current],filters=('active','future'))
    store.put(TENANT,'multi_carrierview',RUN_ID,{n:t.model_dump(mode='json') for n,t in result.items()})


async def outlook(store,paths,manifest):
    from integrations.outlook.adapter import MicrosoftGraphMailAdapter
    from integrations.outlook.auth import MicrosoftAuth
    from integrations.outlook.config import MicrosoftConfig
    current=candidates(store)
    fresh(current)
    validate_reconciliation_scope(manifest,current)
    store.get(TENANT,'multi_carrierview',RUN_ID)  # Ordered workflow; no mail before bounded CV read.
    targets=outlook_targets(current)
    if len(targets)>8:
        raise PermissionError('outlook_target_bound')
    proposals=[]
    searched=[]
    if targets:
        phase_guard(paths,'read_mail')
        config=MicrosoftConfig.load()
        config.network_authorized=True
        config.drafts_authorized=False
        async with MicrosoftGraphMailAdapter(config,MicrosoftAuth(config).get_token,graph_audit(store)) as adapter:
            await adapter.get_mailbox_profile()
            for c in targets:
                phase_guard(paths,'read_mail')
                # A load-specific subject search is bounded to a single page; no broad mailbox mining.
                messages,_=await adapter.search_messages('subject:'+c.load_number,limit=10)
                if len(messages)>10:
                    raise PermissionError('outlook_response_count_bound')
                proposals.extend(email_proposals(c,messages))
                searched.append({'load_id':c.load_number,'message_count':len(messages),'coverage':'FIRST_PAGE_ONLY'})
    store.put(TENANT,'multi_mail',RUN_ID,{'proposals':proposals,'searches':searched})


def build_report(store,paths):
    current=candidates(store)
    tracking={n:TrackingEvidence.model_validate(t) for n,t in store.get(TENANT,'multi_carrierview',RUN_ID).items()}
    mail=store.get(TENANT,'multi_mail',RUN_ID)
    result=report(current,tracking,mail['proposals'])
    result['run_id']=RUN_ID
    result['read_phases_executed']=['ASCEND_EXACT_DETAILS','CARRIERVIEW_ACTIVE_FUTURE','OUTLOOK_GAP_ONLY']
    result['outlook_searches']=mail['searches']
    if result['pilot_load_id']:
        from app.services.live_ops import tracking_inputs
        selected=next(c for c in current if c.load_number==result['pilot_load_id'])
        payload,_=tracking_inputs(selected)
        store.put(TENANT,'multi_pilot_payload',RUN_ID,{'load_id':selected.load_number,
            'payload':payload.model_dump(mode='json',exclude_none=True),'stops':selected.stops,
            'state':'OWNER_REVIEW_ONLY','execution_enabled':False})
    store.put(TENANT,'multi_report',RUN_ID,result)
    paths.path('Data',TENANT,'operations',RUN_ID+'-report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


async def run(phase):
    paths=RuntimePaths.from_environment()
    store=Store(paths.path('Data',TENANT,'operations','operations.sqlite3'))
    progress=PhaseProgress(store,RUN_ID,phase)
    try:
        manifest=store.get(TENANT,'ops_manifest',MANIFEST_ID)
        if phase=='report':
            progress.stage('local_report')
            return build_report(store,paths)
        phase_guard(paths,{'outlook':'read_mail','carrierview':'read_tracking','ascend':'read_ascend'}[phase])
        if phase!='ascend':
            validate_reconciliation_scope(manifest,candidates(store))
        progress.stage('phase_grant')
        with store.transaction():
            key=RUN_ID+':'+phase
            if any(g['id']==key for g in store.all(TENANT,'multi_read_grant')):
                raise PermissionError('one_use_phase_consumed_no_retry')
            store.put(TENANT,'multi_read_grant',key,{'id':key,'phase':phase,'consumed':True})
        if phase=='ascend':
            await ascend(store,paths,manifest,progress)
        else:
            progress.stage('carrierview_read' if phase=='carrierview' else 'outlook_read')
            await {'carrierview':carrierview,'outlook':outlook}[phase](store,paths,manifest)
        progress.stage('complete')
        return {'run_id':RUN_ID,'phase':phase,'status':'BOUNDED_READ_COMPLETE','production_writes':False}
    except Exception as error:
        return progress.failed(error)
    finally:
        store.close()


def execute(phase):
    try:
        result=asyncio.run(run(phase))
        print(json.dumps(result))
        if result.get('status')=='STOPPED_MULTI_SYSTEM':
            raise SystemExit(1)
    except Exception as error:
        code,reason=safe_failure(error)
        print(json.dumps({'run_id':RUN_ID,'phase':phase,'status':'STOPPED_MULTI_SYSTEM',
            'execution_stage':'preflight_or_diagnostic_persistence','affected_load_id':None,'completed_load_count':0,
            'error_code':code,'reason':reason,
            'production_writes':False}))
        raise SystemExit(1) from None


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['ascend','outlook','report'])
    parser.add_argument('--owner-authorized',action='store_true',required=True)
    args=parser.parse_args()
    execute(args.phase)
