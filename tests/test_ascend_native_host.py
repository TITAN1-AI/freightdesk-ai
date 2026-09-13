import hashlib
import hmac
import io
import json
import sqlite3
import struct
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest

from executors.ascend_extension.contracts import OPERATIONS
from executors.ascend_extension.host import HostSession, receive, serve
from executors.ascend_extension.native import canonical, decode_message, encode_message
from executors.ascend_extension.pairing import PairingRepository
from scripts.ascend_native_setup import setup


@pytest.fixture
def repo(tmp_path):
    class Paths:
        def path(self,*parts):
            return tmp_path.joinpath(*parts)
    def fixture_cipher(data, *, decrypt=False):
        return data[8:] if decrypt else b'FIXTURE:'+data
    r=PairingRepository(Paths(),sid=lambda:'fixture-sid',protect=fixture_cipher)
    setup('capture',r,lambda _: 'a'*32)
    return r


def authenticate(repo):
    repo.begin_pairing()
    package=repo.load_pairing()
    host=HostSession(repo,'chrome-extension://'+'a'*32+'/')
    challenge=host.handle({'kind':'HELLO','protocol':1,'request_id':uuid4().hex})['challenge']
    signed={k:challenge[k] for k in ('session_id','extension_origin','tenant_id','actor')}
    proof=hmac.new(bytes.fromhex(package['key']),canonical(signed),hashlib.sha256).hexdigest()
    response=host.handle({'kind':'PAIR','protocol':1,'request_id':uuid4().hex,'proof':proof})
    assert response['envelope']['body']['state']=='PAIRED'
    assert not response['envelope']['body']['read_dispatch_enabled']
    return host,package,challenge


def envelope(host, package, body, sequence=1):
    signed={'session_id':host.auth.session_id,'sequence':sequence,'direction':'extension_to_host','body':body}
    return {'kind':'AUTHENTICATED','protocol':1,'envelope':signed|{
        'mac':hmac.new(bytes.fromhex(package['key']),canonical(signed),hashlib.sha256).hexdigest()}}


def test_local_capture_manifest_binding_and_no_registry(repo):
    manifest=json.loads(repo.path('host-manifest.json').read_text())
    assert manifest['allowed_origins']==['chrome-extension://'+'a'*32+'/']
    assert manifest['type']=='stdio' and manifest['name']=='com.freightdesk.ascend_x1'
    assert not repo.secret_path().exists()
    with pytest.raises(PermissionError):
        HostSession(repo,'chrome-extension://'+'b'*32+'/').handle({'kind':'HELLO','protocol':1,'request_id':uuid4().hex})
    config=json.loads(repo.path('installation.json').read_text())
    config['windows_sid']='other-windows-installation'
    repo.path('installation.json').write_text(json.dumps(config))
    with pytest.raises(PermissionError):
        repo.config()


def test_pairing_restart_replay_reset_and_audit(repo):
    host,package,_=authenticate(repo)
    assert not repo.path('pairing-bootstrap.json').exists()
    request_id=uuid4().hex
    status={'kind':'STATUS','request_id':request_id}
    assert host.handle(envelope(host,package,status))['envelope']['body']['state']=='PAIRED'
    with pytest.raises(PermissionError,match='duplicate_request'):
        host.handle(envelope(host,package,status,2))
    # A fresh host cannot redeem an already used bootstrap, even with the old correct key.
    restarted=HostSession(repo,host.origin)
    with pytest.raises(PermissionError,match='pairing_already_used'):
        restarted.handle({'kind':'HELLO','protocol':1,'request_id':uuid4().hex})
    repo.reset()
    repo.begin_pairing()
    with pytest.raises(PermissionError,match='stale_pairing'):
        host.handle(envelope(host,package,{'kind':'STATUS','request_id':uuid4().hex},3))
    with pytest.raises(PermissionError,match='duplicate_request'):
        repo.consume_request(request_id)
    with sqlite3.connect(repo.path('bridge.sqlite3')) as db:
        audit=json.dumps(db.execute('SELECT * FROM audit').fetchall())
    assert package['key'] not in audit and host.auth.session_id not in audit
    for table in ('audit','consumed'):
        with sqlite3.connect(repo.path('bridge.sqlite3')) as db:
            with pytest.raises(sqlite3.IntegrityError,match='append_only_native_ledger'):
                db.execute(f'DELETE FROM {table}')
    repo.audit('PRIVATE_SCRIPT','PRIVATE_PHONE')
    with sqlite3.connect(repo.path('bridge.sqlite3')) as db:
        assert db.execute('SELECT operation,outcome FROM audit ORDER BY rowid DESC LIMIT 1').fetchone()==('CONTROL','STOPPED')


@pytest.mark.parametrize('mutation', [
    {'operation':'execute_js'},{'operation':'eval'},{'operation':'run_script'},{'operation':'shell'},
    {'operation':'ASCEND_SAVE_LOAD'},{'operation':'ASCEND_SET_DRIVER'},{'operation':'ASCEND_UPDATE_STATUS'},
    {'operation':'ASCEND_ADD_NOTE'},{'operation':'ASCEND_UPLOAD_DOCUMENT'},{'selector':'PRIVATE_SCRIPT'},
    {'url':'https://unrelated.invalid/'},{'tenant_id':'other'},{'actor':'other'},{'version':2},
    {'version':True},{'version':1.0},{'operation':'UNKNOWN'},
    {'request_id':'f'*33},{'request_id':'f'*32+'\n'},
])
def test_native_command_rejection_is_sanitized(repo,mutation):
    host,package,_=authenticate(repo)
    command={'version':1,'request_id':uuid4().hex,'operation':'ASCEND_GET_SESSION_STATE','load_id':None,
        'expected_revision':None,'tenant_id':'booking-logistics','actor':'FreightDesk/Avery'}|mutation
    stream=io.BytesIO(encode_message(envelope(host,package,command)))
    output=io.BytesIO()
    serve(stream,output,host)
    response=decode_message(output.getvalue())
    assert response['kind']=='ERROR'
    assert 'PRIVATE' not in output.getvalue().decode('utf-8',errors='ignore')


@pytest.mark.parametrize('operation',OPERATIONS)
def test_all_read_commands_validate_but_do_not_dispatch(repo,operation):
    host,package,_=authenticate(repo)
    scoped=operation not in OPERATIONS[:2]
    cmd={'version':1,'request_id':uuid4().hex,'operation':operation,'load_id':'1755' if scoped else None,
        'expected_revision':'b'*64 if scoped else None,'tenant_id':'booking-logistics','actor':'FreightDesk/Avery'}
    body=host.handle(envelope(host,package,cmd))['envelope']['body']
    assert body['error_code']=='read_release_required' and not body['read_dispatch_enabled']


def test_expiry_bad_proof_protocol_and_runtime_unavailable(repo):
    repo.begin_pairing()
    repo.clock=lambda:time.time()+601
    with pytest.raises(PermissionError,match='pairing_expired'):
        repo.load_pairing()
    repo.clock=time.time
    host=HostSession(repo,'chrome-extension://'+'a'*32+'/')
    for version in (2,True,'1'):
        with pytest.raises(PermissionError,match='unsupported_protocol'):
            host.handle({'kind':'HELLO','protocol':version,'request_id':uuid4().hex})
    host.handle({'kind':'HELLO','protocol':1,'request_id':uuid4().hex})
    with pytest.raises(PermissionError):
        host.handle({'kind':'PAIR','protocol':1,'request_id':uuid4().hex,'proof':'PRIVATE_BAD_PROOF'})
    repo.path('installation.json').unlink()
    output=io.BytesIO()
    serve(io.BytesIO(encode_message({'kind':'HELLO','protocol':1,'request_id':uuid4().hex})),output,host)
    assert decode_message(output.getvalue())['state']=='PAIRING_REQUIRED'


def test_framing_partial_malformed_oversize_and_timeout():
    valid=encode_message({'kind':'STATUS'})
    class Fragmented(io.BytesIO):
        def read(self,n):
            return super().read(min(n,2))
    assert receive(Fragmented(valid))=={'kind':'STATUS'}
    for data in (struct.pack('<I',65537),struct.pack('<I',1)+b'{',struct.pack('<I',13)+b'{"a":1,"a":2}'):
        with pytest.raises(ValueError):
            receive(io.BytesIO(data))
    class Slow:
        def read(self,n):
            time.sleep(.1)
            return b''
    with pytest.raises(TimeoutError):
        receive(Slow(),timeout=.01)


def test_worker_lifecycle_and_python_protocol_interoperability(repo):
    host,package,challenge=authenticate(repo)
    signed={k:challenge[k] for k in ('session_id','extension_origin','tenant_id','actor')}
    # A fresh outgoing counter matches the worker's first received signed envelope.
    host.auth._outgoing=0
    client_body={'kind':'STATUS','request_id':uuid4().hex,'fixture_unicode':'caf\u00e9 \U0001f69b'}
    vector={'bundle':package,'challenge':challenge,
        'proof':hmac.new(bytes.fromhex(package['key']),canonical(signed),hashlib.sha256).hexdigest(),
        'host_envelope':host.auth.sign({'state':'PAIRED','fixture_unicode':'caf\u00e9 \U0001f69b'}),
        'client_body':client_body,'client_mac':envelope(host,package,client_body)['envelope']['mac']}
    result=subprocess.run(['node','scripts/check-ascend-native.js','--python-vectors'],input=json.dumps(vector),
        text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1],timeout=20)
    assert result.returncode==0, 'Offline worker/protocol fixture failed; private values omitted.'


def test_windows_crypto_primitives_without_installation():
    # Public test bytes in memory only: no actual installation, pairing file, registry or browser access.
    from executors.ascend_extension.pairing import dpapi, windows_sid
    assert windows_sid().startswith('S-1-')
    public_fixture=b'FreightDesk offline crypto roundtrip fixture'
    protected=dpapi(public_fixture)
    assert protected!=public_fixture and dpapi(protected,decrypt=True)==public_fixture


def pairing_rows(repo):
    with sqlite3.connect(repo.path('bridge.sqlite3')) as db:
        names=[row[1] for row in db.execute('PRAGMA table_info(pairing_attempts)')]
        assert names==['timestamp','extension_id_match','bootstrap_expired','bootstrap_consumed','handshake_stage','result_code']
        return [dict(zip(names,row)) for row in db.execute('SELECT * FROM pairing_attempts')]


def test_detailed_audit_success_only_after_verified_acknowledgement(repo):
    host,package,_=authenticate(repo)
    before=pairing_rows(repo)
    assert before[-1]['handshake_stage']=='ACK_VERIFICATION'
    assert before[-1]['bootstrap_consumed']==1
    assert not any(r['result_code']=='PAIRING_SUCCESS' for r in before)
    event={'kind':'PAIRING_DIAGNOSTIC','protocol':1,'request_id':uuid4().hex,'diagnostic':{
        'handshake_stage':'ACK_VERIFICATION','result_code':'PAIRING_SUCCESS','extension_id_match':True,
        'bootstrap_expired':False,'bootstrap_consumed':True}}
    assert host.handle(event)['kind']=='DIAGNOSTIC_SAVED'
    last=pairing_rows(repo)[-1]
    assert last['result_code']=='PAIRING_SUCCESS'
    assert (last['extension_id_match'],last['bootstrap_expired'],last['bootstrap_consumed'])==(1,0,1)
    serialized=json.dumps(pairing_rows(repo))
    assert all(private not in serialized for private in [package['key'],package['generation'],host.auth.session_id,'a'*32])
    with sqlite3.connect(repo.path('bridge.sqlite3')) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('DELETE FROM pairing_attempts')
    repo.reset()
    assert pairing_rows(repo)[-1]==last


@pytest.mark.parametrize('kind,expected,stage',[
    ('expired','PAIRING_EXPIRED','DPAPI_VALIDATION'),
    ('consumed','PAIRING_ALREADY_CONSUMED','ONE_TIME_VALIDATION'),
    ('dpapi','PAIRING_DPAPI_FAILED','DPAPI_VALIDATION'),
    ('proof','PAIRING_PROOF_REJECTED','PROOF_VALIDATION'),
    ('persist','PAIRING_PERSIST_FAILED','PAIRING_PERSIST'),
    ('origin','EXTENSION_ID_MISMATCH','NATIVE_CONNECT')])
def test_safe_pairing_root_codes_and_stage_audit(repo,monkeypatch,kind,expected,stage):
    repo.begin_pairing()
    package=repo.load_pairing()
    host=HostSession(repo,'chrome-extension://'+('b' if kind=='origin' else 'a')*32+'/')
    message={'kind':'HELLO','protocol':1,'request_id':uuid4().hex}
    if kind=='expired':
        repo.clock=lambda:time.time()+601
    elif kind=='consumed':
        repo.claim(package['generation'])
    elif kind=='dpapi':
        def broken(*args,**kwargs):
            raise ValueError('PRIVATE_DPAPI')
        repo.protect=broken
    elif kind in ('proof','persist'):
        challenge=host.handle(message)['challenge']
        signed={k:challenge[k] for k in ('session_id','extension_origin','tenant_id','actor')}
        proof=hmac.new(bytes.fromhex(package['key']),canonical(signed),hashlib.sha256).hexdigest()
        message={'kind':'PAIR','protocol':1,'request_id':uuid4().hex,'proof':'PRIVATE_PROOF' if kind=='proof' else proof}
        if kind=='persist':
            def fail_claim(*args):
                raise sqlite3.OperationalError('PRIVATE_DATABASE_PATH')
            monkeypatch.setattr(repo,'claim',fail_claim)
    output=io.BytesIO()
    serve(io.BytesIO(encode_message(message)),output,host)
    response=decode_message(output.getvalue())
    assert response['kind']=='ERROR' and response['result_code']==expected
    last=pairing_rows(repo)[-1]
    assert (last['handshake_stage'],last['result_code'])==(stage,expected)
    if kind=='expired':
        assert last['bootstrap_expired']==1 and last['bootstrap_consumed'] is None
    if kind=='consumed':
        assert last['bootstrap_consumed']==1
    assert 'PRIVATE' not in str(response) and 'PRIVATE' not in str(pairing_rows(repo))


def test_frontend_diagnostic_before_pairing_and_invalid_metadata(repo,monkeypatch):
    host=HostSession(repo,'chrome-extension://'+'a'*32+'/')
    message={'kind':'PAIRING_DIAGNOSTIC','protocol':1,'request_id':uuid4().hex,
        'diagnostic':{'handshake_stage':'JSON_PARSE','result_code':'PAIRING_SCHEMA_INVALID'}}
    assert host.handle(message)['kind']=='DIAGNOSTIC_SAVED'
    assert not repo.secret_path().exists()
    assert pairing_rows(repo)[-1]['bootstrap_consumed'] is None
    with pytest.raises(PermissionError,match='duplicate_request'):
        host.handle(message)
    for mutation in ({'secret':'PRIVATE'},{'result_code':'PRIVATE'},{'bootstrap_consumed':'false'},
        {'result_code':'PAIRING_SUCCESS'}):
        with pytest.raises((PermissionError,ValueError)):
            host.handle(message|{'request_id':uuid4().hex,'diagnostic':message['diagnostic']|mutation})
    assert 'PRIVATE' not in str(pairing_rows(repo))
    def no_disk(*args):
        raise OSError('PRIVATE_PATH')
    monkeypatch.setattr(repo,'pairing_audit',no_disk)
    out=io.BytesIO()
    serve(io.BytesIO(encode_message(message|{'request_id':uuid4().hex})),out,host)
    assert decode_message(out.getvalue())['result_code']=='PAIRING_PERSIST_FAILED'


def test_popup_file_import_and_restart_fixtures():
    result=subprocess.run(['node','scripts/check-ascend-pairing-popup.js'],capture_output=True,
        cwd=Path(__file__).resolve().parents[1],timeout=20)
    assert result.returncode==0,'Offline popup import fixture failed; no raw values printed.'
