"""Windows launcher fixtures; subprocesses use synthetic scripts under TestRuns, never live pairing."""
import json
import io
import os
import queue
import subprocess
import threading
from pathlib import Path

import pytest

from executors.ascend_extension.native import decode_message, encode_message
from executors.ascend_extension.host import main
from executors.ascend_extension.startup import StartupRecorder
from scripts.ascend_native_host import run
from scripts.ascend_native_selftest import probe

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'chrome-extension://' + 'a' * 32 + '/'


def compile_launcher(tmp_path, *, template=None, child=None):
    folder = tmp_path / 'source with spaces'
    (folder / 'scripts').mkdir(parents=True)
    (folder / 'scripts/__init__.py').write_text('', encoding='utf-8')
    (folder / 'scripts/ascend_native_host.py').write_text(child or '''import json, struct, sys
from pathlib import Path
def mark(stage, **facts):
    Path('fixture-status.json').write_text(json.dumps(dict(stage=stage,**facts)))
mark('CHILD_STARTED')
try:
    for _ in range(2):
        prefix=sys.stdin.buffer.read(4)
        mark('PREFIX_RECEIVED',prefix_length=len(prefix))
        size, = struct.unpack('<I', prefix)
        mark('SIZE_READ',declared_size=size)
        if size>65536: raise ValueError()
        data = json.loads(sys.stdin.buffer.read(size))
        result = json.dumps({'kind':'FIXTURE_PONG','protocol':1}).encode()
        sys.stdout.buffer.write(struct.pack('<I',len(result))+result)
        sys.stdout.buffer.flush()
        mark('RESPONSE_FLUSHED')
except Exception as exc:
    mark('CHILD_FAILED',exception_type=type(exc).__name__)
''', encoding='utf-8')
    code = template or (ROOT / 'scripts/native_host_launcher.cs').read_text(encoding='utf-8')
    # Replace the fixed production root before inserting fixture paths, which themselves live under it.
    code = code.replace(r'C:\FreightDeskRuntime', str(tmp_path / 'runtime'))
    code = code.replace('__PYTHON__', str(ROOT / '.tools/python/python.exe')).replace('__SOURCE__', str(folder))
    # Embedded project Python has a configured module path; invoke the isolated fixture explicitly.
    code = code.replace('"-B -m scripts.ascend_native_host "', json.dumps('-B "'+str(folder/'scripts/ascend_native_host.py')+'" '))
    # Only the isolated compiled test binary has a fixture runtime. Production template remains fixed.
    (tmp_path / 'runtime/Data/booking-logistics/ascend-native').mkdir(parents=True)
    source, output = tmp_path / 'launcher.cs', tmp_path / 'launcher with spaces.exe'
    source.write_text(code, encoding='utf-8')
    compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    result = subprocess.run([str(compiler), '/nologo', '/target:exe', '/out:' + str(output), str(source)],
        capture_output=True, timeout=20)
    assert result.returncode == 0, 'Fixture launcher compilation failed; no raw diagnostics printed.'
    return output


def response_while_input_open(process, timeout=3):
    result = queue.Queue()
    def read():
        try:
            prefix = process.stdout.read(4)
            if len(prefix) != 4:
                result.put(None)
                return
            size = int.from_bytes(prefix, 'little')
            if size > 65536:
                result.put(None)
                return
            result.put(decode_message(prefix + process.stdout.read(size)))
        except Exception:
            result.put(None)
    threading.Thread(target=read, daemon=True).start()
    try:
        return result.get(timeout=timeout)
    except queue.Empty:
        return None


def test_launcher_handles_small_interactive_frames_and_spaces(tmp_path):
    exe = compile_launcher(tmp_path)
    process = subprocess.Popen([str(exe), ORIGIN], cwd=str(tmp_path), stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for _ in range(2):
            process.stdin.write(encode_message({'kind':'FIXTURE_PING','protocol':1}))
            process.stdin.flush()
            assert response_while_input_open(process) == {'kind':'FIXTURE_PONG','protocol':1}
        process.stdin.close()
        assert process.wait(timeout=5) == 0
        assert process.stdout.read() == b'' and process.stderr.read() == b''
    finally:
        if process.poll() is None:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def test_original_copyto_relay_cannot_respond_before_eof(tmp_path):
    code=(ROOT/'scripts/native_host_launcher.cs').read_text(encoding='utf-8')
    code=code.replace('Relay(Console.OpenStandardInput(), child.StandardInput.BaseStream);',
        'Console.OpenStandardInput().CopyTo(child.StandardInput.BaseStream);')
    code=code.replace('Relay(child.StandardOutput.BaseStream, Console.OpenStandardOutput());',
        'child.StandardOutput.BaseStream.CopyTo(Console.OpenStandardOutput());')
    exe=compile_launcher(tmp_path,template=code)
    process=subprocess.Popen([str(exe),ORIGIN],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        process.stdin.write(encode_message({'kind':'FIXTURE_PING','protocol':1}))
        process.stdin.flush()
        assert response_while_input_open(process,timeout=1) is None
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


class FixtureRepository:
    def config(self):
        return {'extension_id':'a'*32}


def local_main(argv,stdin,stdout,*,startup):
    return main(argv,stdin,stdout,startup=startup,repository=FixtureRepository())


def test_entrypoint_stdout_clean_and_import_failure(tmp_path):
    recorder=StartupRecorder(tmp_path/'runtime')
    output=io.BytesIO()
    def noisy_import():
        import warnings
        print('PRIVATE_IMPORT_BANNER')
        warnings.warn('PRIVATE_IMPORT_WARNING')
        return local_main
    assert run([ORIGIN,'--self-test'],io.BytesIO(encode_message({'kind':'SELF_TEST_PING','protocol':1})),
        output,recorder=recorder,loader=noisy_import)==0
    assert decode_message(output.getvalue())['kind']=='SELF_TEST_PONG'
    def failing_import():
        raise ModuleNotFoundError('PRIVATE_MODULE_PATH')
    failed=io.BytesIO()
    assert run([ORIGIN],io.BytesIO(),failed,recorder=StartupRecorder(tmp_path/'failure'),loader=failing_import)==1
    assert failed.getvalue()==b''
    records=[json.loads(line) for line in (tmp_path/'runtime/Data/booking-logistics/ascend-native/startup-python.jsonl').read_text().splitlines()]
    assert any(r['safe_error_code']=='IMPORT_OUTPUT_SUPPRESSED' for r in records)
    assert any(r['first_message_received'] and r['host_initialized'] for r in records)
    error_records=(tmp_path/'failure/Data/booking-logistics/ascend-native/startup-python.jsonl').read_text()
    assert 'MODULE_IMPORT_FAILED' in error_records and 'ModuleNotFoundError' in error_records
    assert 'PRIVATE' not in str(records)+error_records


def test_compiled_launcher_real_entrypoint_synthetic_ping_and_origin(tmp_path):
    child=f'''import sys
from pathlib import Path
sys.path.insert(0,{str(ROOT)!r})
from scripts.ascend_native_host import run
from executors.ascend_extension.host import main
from executors.ascend_extension.startup import StartupRecorder
class Repo:
    def config(self): return {{'extension_id':{'a'*32!r}}}
def entry(argv,stdin,stdout,*,startup):
    return main(argv,stdin,stdout,startup=startup,repository=Repo())
raise SystemExit(run(sys.argv[1:],sys.stdin,sys.stdout,recorder=StartupRecorder(Path({str(tmp_path/'runtime')!r})),loader=lambda:entry))
'''
    exe=compile_launcher(tmp_path,child=child)
    report=probe(str(exe),ORIGIN,timeout=3)
    assert report['status']=='PASS' and report['stdout_clean'] and report['response_framing_valid']
    assert not report['production_reads'] and not report['production_writes']
    denied=probe(str(exe),'chrome-extension://'+'b'*32+'/',timeout=3)
    assert denied['status']=='STOPPED' and not denied['response_framing_valid']
    for file in (tmp_path/'runtime/Data/booking-logistics/ascend-native').glob('startup-*.jsonl'):
        records=[json.loads(line) for line in file.read_text().splitlines()]
        assert all(set(r)=={'timestamp','startup_stage','safe_error_code','exception_type','launcher_started',
            'python_started','host_initialized','first_message_received'} for r in records)
        assert 'a'*32 not in str(records) and 'SELF_TEST_PING' not in str(records)


@pytest.mark.parametrize('behavior,expected',[
    ('exit','SELF_TEST_EXIT_BEFORE_RESPONSE'),('noise','SELF_TEST_FRAMING_INVALID')])
def test_host_exits_or_contaminates_stdout(tmp_path,behavior,expected):
    child='raise SystemExit(3)' if behavior=='exit' else "import sys; sys.stdout.buffer.write(b'not-a-frame');sys.stdout.buffer.flush()"
    exe=compile_launcher(tmp_path,child=child)
    result=probe(str(exe),ORIGIN,timeout=3)
    assert result['status']=='STOPPED' and result['safe_error_code']==expected
    log=(tmp_path/'runtime/Data/booking-logistics/ascend-native/startup-launcher.jsonl').read_text()
    assert 'PYTHON_LAUNCH' in log and 'python_started":true' in log


def test_launcher_start_exception_is_sanitized(tmp_path):
    template=(ROOT/'scripts/native_host_launcher.cs').read_text(encoding='utf-8')
    template=template.replace('__PYTHON__',str(tmp_path/'missing python.exe'))
    exe=compile_launcher(tmp_path,template=template)
    result=probe(str(exe),ORIGIN,timeout=3)
    assert result['status']=='STOPPED'
    records=[json.loads(line) for line in (tmp_path/'runtime/Data/booking-logistics/ascend-native/startup-launcher.jsonl').read_text().splitlines()]
    assert records[-1]['safe_error_code']=='LAUNCHER_START_FAILED'
    assert records[-1]['python_started'] is False and records[-1]['exception_type']=='Win32Exception'
    assert 'missing python.exe' not in str(records)


def test_stderr_is_not_native_stdout(tmp_path):
    child='''import sys,struct,json
sys.stderr.write('PRIVATE_STDERR_WARNING');sys.stderr.flush()
n,=struct.unpack('<I',sys.stdin.buffer.read(4));sys.stdin.buffer.read(n)
b=json.dumps({'kind':'SELF_TEST_PONG','protocol':1,'production_reads':False,'production_writes':False}).encode()
sys.stdout.buffer.write(struct.pack('<I',len(b))+b);sys.stdout.buffer.flush()
'''
    exe=compile_launcher(tmp_path,child=child)
    assert probe(str(exe),ORIGIN,timeout=3)['status']=='PASS'
    assert 'PRIVATE' not in (tmp_path/'runtime/Data/booking-logistics/ascend-native/startup-launcher.jsonl').read_text()
