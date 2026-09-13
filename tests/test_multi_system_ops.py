import asyncio
import json
from datetime import date

import httpx
import pytest
from pydantic import SecretStr

from app.models.domain import utcnow
from app.services.live_ops import OpsCandidate, OpsFact, TrackingEvidence
from app.services.live_ops_carrierview import DELIVERIES, PICKUPS, reconcile_ops
from app.services.multi_system_ops import assignment, email_proposals, outlook_targets, report
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.config import CarrierViewConfig, CredentialClass
from integrations.carrierview.contract import ResponseContract
from integrations.outlook.models import Message


def candidate(number):
    def fact(v):
        return OpsFact(value=v,source='AscendTMS',verified=True,source_reference='synthetic-detail')
    return OpsCandidate(load_number=number,service_date=date(2026,9,11),identity_verified=True,
        pickup_due=number in PICKUPS,delivery_due=number in DELIVERIES,
        facts={k:fact(v) for k,v in {'carrier':'Synthetic Carrier','carrier_mc':'123456','driver':'Synthetic Driver',
            'truck':'truck','trailer':'trailer','driver_phone':'+15555550123','dispatcher_email':'dispatch@example.test'}.items()})


def test_oracle_does_not_drive_assignment():
    cs=[candidate(n) for n in PICKUPS|DELIVERIES]
    ts={n:TrackingEvidence(load_number=n,existence='EXISTS',observed_at=utcnow()) for n in DELIVERIES}
    r=report(cs,ts)
    assert r['observed']['covered']==8 and r['observed']['uncovered']==0
    assert r['status']=='POC_002_RECONCILIATION_MISMATCH'
    c=next(c for c in cs if c.pickup_due)
    c.facts['carrier'].value=''
    c.facts['driver'].value=''
    r=report(cs,ts)
    assert r['status']=='POC_002_MULTI_SYSTEM_RECONCILED'
    row=next(x for x in r['loads'] if x['load_id']==c.load_number)
    assert row['next_action']=='COVERAGE_REQUIRED' and row['operational_state']=='UNCOVERED'
    assert '15555550123' not in json.dumps(r) and 'Synthetic Driver' not in json.dumps(r)
    assert r['pilot_load_id'] is None


def test_unknown_assignment_and_contact_gap():
    c=candidate('1755')
    del c.facts['carrier_mc']
    assert assignment(c)=='UNKNOWN'
    assert not outlook_targets([c])
    c.facts['carrier_mc']=OpsFact(value='123456',source='AscendTMS',verified=True,source_reference='fixture')
    del c.facts['driver_phone']
    assert outlook_targets([c])==[c]
    c.facts['carrier'].value='Unknown'
    assert assignment(c)=='UNKNOWN'


def test_wrong_load_and_sender_email_not_promoted():
    c=candidate('1755')
    def message(subject,sender='dispatch@example.test'):
        return Message.model_validate({'id':'private-message-id','subject':subject,
            'from':{'emailAddress':{'address':sender}},'receivedDateTime':utcnow(),
            'body':{'content':'Driver Phone: +15555550124'}})
    assert not email_proposals(c,[message('Booking load 1756')])
    assert not email_proposals(c,[message('Booking load 1755','other@example.test')])
    assert not email_proposals(c,[message('Booking load 1755 and load 1756')])
    proposals=email_proposals(c,[message('Booking load 1755')])
    assert len(proposals)==1 and not proposals[0]['verified']
    assert proposals[0]['message_id']=='private-message-id'
    assert c.facts['driver_phone'].value=='+15555550123'


def test_active_future_max_fourteen_gets_and_no_past():
    ids=sorted(PICKUPS|DELIVERIES)
    calls=[]
    def handler(request):
        calls.append((request.method,request.url.path,str(request.url.query)))
        assert request.method=='GET'
        if request.url.path=='/api/profile':
            data={'company_name':'Booking Logistics LLC'}
        elif request.url.path=='/api/loads':
            assert request.url.params['filter'] in {'active','future'}
            data=[{'load_id':n,'id':n} for n in ids]
        else:
            n=request.url.path.rsplit('/',1)[1]
            data={'load_id':n,'id':n,'integration_type':'carrier_view','driver_phone':'PRIVATE_PHONE'}
        return httpx.Response(200,json={'success':True,'data':data})
    async def run():
        cfg=CarrierViewConfig(api_token=SecretStr('synthetic'),base_url='https://carrierview.com',
            credential_class=CredentialClass.TENANT,elevation_reason='fixture')
        async with CarrierViewAdapter(cfg,ResponseContract(source_reference='fixture',selectors={}),lambda e:None,
                                      httpx.MockTransport(handler)) as adapter:
            result=await reconcile_ops(adapter,ids,filters=('active','future'))
            assert len(result)==11 and result[ids[0]].observed_list_filters==['active','future']
            assert 'PRIVATE_PHONE' not in json.dumps({n:t.model_dump(mode='json') for n,t in result.items()})
    asyncio.run(run())
    assert len(calls)==14


def test_unknown_filters_stop_before_request():
    with pytest.raises(ValueError):
        asyncio.run(reconcile_ops(None,['1755'],filters=('all',)))
