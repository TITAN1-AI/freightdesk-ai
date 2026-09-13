"""Single-load identity observation. Never read operational detail fields or advance other phases."""
import asyncio
import re
import time
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from uuid import uuid4

from app.core.runtime import RuntimePaths
from app.models.domain import utcnow
from app.services.live_ops_carrierview import PICKUPS, DELIVERIES, validate_reconciliation_scope
from app.services.multi_phase_progress import safe_failure
from app.services.store import Store
from integrations.ascend.field_discovery import ReadOnly1752Executor
from integrations.ascend.isolated_diagnostic import LocalSession, load_manifest
from integrations.ascend.ops_discovery import board_candidates

ATTEMPT='owner-ascend-detail-identity-1755-20260911-01'
ORIGIN='https://ascendtms.com'
APPROVED=PICKUPS|DELIVERIES
SCAN=Path(__file__).with_name('detail_identity.js').read_text(encoding='utf-8')


def path_metadata(url):
    u=urlsplit(url)
    if u.scheme+'://'+u.netloc!=ORIGIN or u.username or u.password:
        return {'same_origin':False,'path':None,'route_id':None}
    parts=[p for p in u.path.split('/') if p]
    known={'loads','load','detail','details','view','booking-loads'}
    safe=all(p.lower() in known or p in APPROVED for p in parts)
    match=re.fullmatch(r'/(?:loads|load|booking-loads)/(\d{1,20})/?',u.path)
    return {'same_origin':True,'path':u.path if safe else '[redacted path]',
        'route_id':match[1] if match and match[1] in APPROVED else None,
        'unapproved_route_id':bool(match and match[1] not in APPROVED)}


def decide(signals,path,navigation,expected='1755'):
    evidence=list(signals)
    if path.get('route_id'):
        # Route alone needs the exact row's observed link destination to establish its role.
        if navigation.get('path')==path['path'] and navigation.get('row_load_id')==expected:
            evidence.append({'kind':'row_link_route','candidate_value':path['route_id'],
                'unapproved_value':False,'selector':path['path'],'label':'row-linked route'})
        else:
            return {'state':'UNKNOWN','error_code':'ambiguous_identity_route'}
    if path.get('unapproved_route_id') or any(s['unapproved_value'] for s in evidence):
        return {'state':'UNKNOWN','error_code':'conflicting_identity_signals'}
    values={s['candidate_value'] for s in evidence}
    if not evidence:
        return {'state':'UNKNOWN','error_code':'detail_identity_missing'}
    if values!={expected}:
        return {'state':'UNKNOWN','error_code':'conflicting_identity_signals'}
    priority={'visible_field':0,'named_input':1,'heading':2,'data_attribute':3,'row_link_route':4}
    best=min(priority[s['kind']] for s in evidence)
    primary=[s for s in evidence if priority[s['kind']]==best]
    if len(primary)!=1:
        return {'state':'UNKNOWN','error_code':'ambiguous_identity_sources'}
    return {'state':'VERIFIED','strategy':primary[0], 'supporting_signal_count':len(evidence)-1,
            'provider_observed_load_id':expected}


async def inspect(page,guard,navigation,observe,timeout=10):
    start=time.monotonic()
    previous=None
    stable=0
    while True:
        await guard()
        path=path_metadata(page.url)
        if not path['same_origin']:
            raise PermissionError('detail_identity_origin_mismatch')
        signals=[]
        for i,frame in enumerate(page.frames):
            if not path_metadata(frame.url)['same_origin']:
                continue
            found=await asyncio.wait_for(frame.evaluate(SCAN,sorted(APPROVED)),3)
            if found['overflow']:
                raise ValueError('detail_identity_scan_bound')
            signals.extend(dict(s,frame_index=i) for s in found['signals'])
        title=await page.title()
        safe_title=title if title in {'AscendTMS','Ascend TMS'} else '[redacted title]'
        decision=decide(signals,path,navigation)
        metadata={'current_path':path['path'],'page_title':safe_title,'identity_signals':signals,
            'candidate_identity_field_count':len(signals),'decision':decision}
        observe('IDENTITY_OBSERVATION',metadata)
        stable=stable+1 if metadata==previous else 0
        previous=metadata
        if decision['state']=='UNKNOWN' and decision['error_code']!='detail_identity_missing':
            return metadata
        if decision['state']=='VERIFIED' and stable>=2:
            return metadata
        if time.monotonic()-start>=timeout:
            if decision['state']=='VERIFIED':
                metadata['decision']={'state':'UNKNOWN','error_code':'detail_identity_unstable'}
                observe('IDENTITY_OBSERVATION',metadata)
            return metadata
        await asyncio.sleep(.25)


async def run(paths=None):
    from datetime import date
    paths=paths or RuntimePaths.from_environment()
    store=Store(paths.path('Data','booking-logistics','ascend','identity-diagnostics.sqlite3'))
    state={'attempt_id':ATTEMPT,'load_id':'1755','execution_stage':'PREFLIGHT','production_writes':False}
    session=None
    def observe(stage,metadata):
        state.update(execution_stage=stage,**metadata)
        store.put('booking-logistics','identity_checkpoint',ATTEMPT+':'+uuid4().hex,dict(state,observed_at=utcnow().isoformat()))
    try:
        manifest=load_manifest(paths)
        with store.transaction():
            if store.all('booking-logistics','identity_grant'):
                raise PermissionError('one_use_phase_consumed_no_retry')
            store.put('booking-logistics','identity_grant',ATTEMPT,{'id':ATTEMPT,'consumed':True})
        session=LocalSession(paths)
        session.observe_board=lambda m:observe('BOARD_NORMALIZATION',m)
        await session.confirm()
        grid=await session.board(lambda:observe('ACTIVE_LOADS_SELECTED',{}))
        validate_reconciliation_scope(manifest,board_candidates(grid,date(2026,9,11),'US',ATTEMPT))
        observe('BOARD_RECONCILED',{'exact_scope_reconciled':True})
        executor=ReadOnly1752Executor(session.page,session.running,load_number='1755',authorized_loads=('1755',))
        navigation={}
        def before_open(info):
            navigation.update(path_metadata(urljoin(session.page.url,info.get('href') or '')))
            navigation.update(row_load_id='1755',element_type=info['tag'],link_or_button_exists=True,
                id_present=info['id_present'],name_present=info['name_present'],data_attribute_count=info['data_attribute_count'])
            observe('BEFORE_DETAIL_OPEN',{'navigation':navigation})
        await executor.open_1752(before_open=before_open)
        observed=await inspect(session.page,executor.guard,navigation,observe)
        decision=observed['decision']
        if decision['state']=='VERIFIED':
            contract={'contract_type':'AscendLoadDetailIdentityContract','version':1,'provider':'AscendTMS',
                'observed_load':'1755','observed_at':utcnow().isoformat(),'confidence':'VERIFIED',
                'evidence_source':'live browser DOM and exact-row navigation','strategy':decision['strategy'],
                'supporting_signal_count':decision['supporting_signal_count'],'scope':'OBSERVED_LOAD_1755_ONLY',
                'automatic_reader_activation':False}
            store.put('booking-logistics','identity_contract',ATTEMPT,contract)
            observe('IDENTITY_CONTRACT_OBSERVED',{'status':'IDENTITY_DIAGNOSTIC_COMPLETE','contract':contract})
        else:
            observe('IDENTITY_UNVERIFIED',{'status':'STOPPED_IDENTITY_DIAGNOSTIC','error_code':decision['error_code']})
    except Exception as error:
        code,reason=safe_failure(error)
        observe(state['execution_stage'],{'status':'STOPPED_IDENTITY_DIAGNOSTIC','error_code':code,'reason':reason})
    finally:
        if session:
            try:
                await session.close()
            except Exception:
                if state.get('status')!='STOPPED_IDENTITY_DIAGNOSTIC':
                    observe('CLEANUP',{'status':'STOPPED_IDENTITY_DIAGNOSTIC','error_code':'identity_cleanup_failed'})
        store.close()
    return state
