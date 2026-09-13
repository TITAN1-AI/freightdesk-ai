"""Owner-run local pipe probe. No Edge, bootstrap, DPAPI decryption, grant or vendor operation."""
import argparse
import json
import subprocess

from executors.ascend_extension.native import encode_message
from executors.ascend_extension.host import receive
from executors.ascend_extension.pairing import HOST_NAME, PairingRepository


def probe(executable: str, origin: str, *, timeout: float = 10) -> dict:
    result = {'status':'STOPPED','safe_error_code':'SELF_TEST_HOST_UNAVAILABLE','launcher_started':False,
        'python_started':False,'host_initialized':False,'first_message_received':False,
        'response_framing_valid':False,'stdout_clean':False,'production_reads':False,'production_writes':False}
    process = None
    try:
        process = subprocess.Popen([executable,origin,'--self-test'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL)
        result['launcher_started'] = True
        process.stdin.write(encode_message({'kind':'SELF_TEST_PING','protocol':1}))
        process.stdin.flush()
        # Keep stdin OPEN until the response: closing it first would hide the original relay-buffer bug.
        response = receive(process.stdout,timeout=timeout)
        expected = {'kind':'SELF_TEST_PONG','protocol':1,'production_reads':False,'production_writes':False}
        if response != expected or type(response.get('protocol')) is not int:
            result['safe_error_code'] = 'SELF_TEST_RESPONSE_INVALID'
            return result
        result.update(python_started=True,host_initialized=True,first_message_received=True,response_framing_valid=True)
        process.stdin.close()
        if process.wait(timeout=3) != 0 or process.stdout.read(65537) != b'':
            result['safe_error_code'] = 'SELF_TEST_STDOUT_OR_EXIT_INVALID'
            return result
        result.update(status='PASS',safe_error_code='SELF_TEST_OK',stdout_clean=True)
    except TimeoutError:
        result['safe_error_code'] = 'SELF_TEST_RESPONSE_TIMEOUT'
    except EOFError:
        result['safe_error_code'] = 'SELF_TEST_EXIT_BEFORE_RESPONSE'
    except ValueError:
        result['safe_error_code'] = 'SELF_TEST_FRAMING_INVALID'
    except Exception:
        result['safe_error_code'] = 'SELF_TEST_HOST_UNAVAILABLE'
    finally:
        if process:
            if not process.stdin.closed:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            if process.poll() is None:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
    return result


def selftest(repository=None) -> dict:
    repo = repository or PairingRepository()
    config = repo.config()  # Windows/runtime/exact extension binding; no pairing secret read.
    manifest = json.loads(repo.path('host-manifest.json').read_text(encoding='utf-8'))
    origin = f"chrome-extension://{config['extension_id']}/"
    executable = repo.path('FreightDeskAscendHost.exe')
    if (manifest.get('name') != HOST_NAME or manifest.get('type') != 'stdio' or
        manifest.get('allowed_origins') != [origin] or manifest.get('path') != str(executable) or not executable.is_file()):
        raise ValueError('self_test_manifest_invalid')
    return probe(str(executable),origin)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Owner-run synthetic native ping; no pairing or vendor action.')
    parser.add_argument('--owner-executed',action='store_true',required=True)
    parser.parse_args()
    try:
        report = selftest()
    except Exception:
        report = {'status':'STOPPED','safe_error_code':'SELF_TEST_CONFIGURATION_INVALID','production_reads':False,'production_writes':False}
    print(json.dumps(report,sort_keys=True))
    raise SystemExit(0 if report['status']=='PASS' else 1)
