"""Release guard/replacement fixtures: never inspect or change the installed host."""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from executors.ascend_extension.bridge_build import BUILD, DocumentHandshake
from scripts import ascend_native_selftest
from scripts import x1_release as release


def repository(tmp_path, *, state=None, lease=None, jobs=()):
    repo = SimpleNamespace(path=lambda name: tmp_path / name)
    with sqlite3.connect(repo.path('runtime.sqlite3')) as db:
        db.execute('create table runtime_state(id integer primary key,body text)')
        db.execute('create table runtime_leases(id text primary key,body text)')
        db.execute('insert into runtime_state values(1,?)', (json.dumps(state or {}),))
        if lease:
            db.execute('insert into runtime_leases values(?,?)', ('fixture', json.dumps(lease)))
    with sqlite3.connect(repo.path('mapping-orchestrator.sqlite3')) as db:
        db.execute('create table jobs(id integer primary key,body text)')
        for job in jobs:
            db.execute('insert into jobs(body) values(?)', (json.dumps(job),))
    return repo


@pytest.mark.parametrize('state,lease,jobs,code', [
    ({'pending': {'operation': 'FIXTURE'}}, None, [], 'RELEASE_READ_PENDING'),
    ({'mapping_capture_requested': True}, None, [], 'RELEASE_READ_PENDING'),
    ({'paused': True}, {'generation': 'fixture', 'expires_at': 101}, [], 'RELEASE_AUTHORITY_ACTIVE'),
    ({}, None, [{'stage': 'PREFLIGHT'}], 'RELEASE_JOB_ACTIVE'),
    ({}, None, [{'stage': 'OWNER_REVIEW_REQUIRED', 'cleanup_complete': False}], 'RELEASE_JOB_ACTIVE'),
])
def test_idle_gate_preserves_unrelated_jobs_and_leases(tmp_path, state, lease, jobs, code):
    repo = repository(tmp_path, state=state, lease=lease, jobs=jobs)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match=code):
        release.require_idle(repo, now=100)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_closed_authority_and_preserved_review_history_allow_maintenance(tmp_path):
    repo = repository(tmp_path, state={'revoked_generation': 'fixture'},
                      lease={'generation': 'fixture', 'expires_at': 1000},
                      jobs=[{'stage': 'OWNER_REVIEW_REQUIRED', 'cleanup_complete': True}, {'stage': 'STOPPED'}])
    release.require_idle(repo, now=100)


def test_file_update_and_reverse_restore_exact_bytes(tmp_path):
    current, candidate, backup = (tmp_path / name for name in ['host.exe', 'candidate.exe', 'backup.exe'])
    current.write_bytes(b'old fixture')
    backup.write_bytes(current.read_bytes())
    candidate.write_bytes(b'new fixture')
    before, after = release.digest(backup), release.digest(candidate)
    release.atomic_replace(candidate, current, expected_before=before, expected_after=after)
    assert current.read_bytes() == b'new fixture' and backup.read_bytes() == b'old fixture'
    release.atomic_replace(backup, current, expected_before=after, expected_after=before)
    assert current.read_bytes() == b'old fixture'
    assert not current.with_name('host.exe.pending').exists()


def test_locked_host_preserves_old_file_and_cleans_own_pending_file(tmp_path):
    current, candidate = tmp_path / 'host.exe', tmp_path / 'candidate.exe'
    current.write_bytes(b'old')
    candidate.write_bytes(b'new')
    def locked(source, target):
        raise PermissionError('fixture locked')
    with pytest.raises(PermissionError):
        release.atomic_replace(candidate, current, expected_before=release.digest(current),
                               expected_after=release.digest(candidate), replace=locked)
    assert current.read_bytes() == b'old' and not (tmp_path / 'host.exe.pending').exists()


def test_external_file_change_is_never_overwritten(tmp_path):
    current, candidate = tmp_path / 'host.exe', tmp_path / 'candidate.exe'
    current.write_bytes(b'external')
    candidate.write_bytes(b'new')
    with pytest.raises(ValueError, match='RELEASE_FILE_CHANGED'):
        release.atomic_replace(candidate, current, expected_before='0' * 64, expected_after=release.digest(candidate))
    assert current.read_bytes() == b'external'


def test_replacement_rejects_paths_outside_authorized_runtime():
    with pytest.raises(ValueError):
        release.checked_runtime(Path.cwd() / 'host.exe')


def test_explicit_owner_gate_precedes_access_to_installation():
    with pytest.raises(PermissionError, match='RELEASE_OWNER_REQUIRED'):
        release.install_host(None)


def test_packaged_manifest_and_handshake_share_new_version():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'extensions/ascend-x1/manifest.json').read_text())
    assert manifest['version'] == BUILD['extension_version'] == '0.6.4'
    assert 'webbridge-v2' not in json.dumps(manifest)
    body = dict(BUILD, service_worker_version='0.6.4', content_script_version='0.6.4',
                document_generation=1, tab_id=1, document_id='a' * 32)
    DocumentHandshake.model_validate(body)
    with pytest.raises(ValueError):
        DocumentHandshake.model_validate(dict(body, content_script_version='0.6.2'))


@pytest.mark.parametrize('winerror,expected', [
    (4551, 'SELF_TEST_APPLICATION_CONTROL_BLOCKED'),
    (2, 'SELF_TEST_HOST_UNAVAILABLE'),
])
def test_os_denial_is_safe_precise_and_never_retried(monkeypatch, winerror, expected):
    calls = []
    def denied(*args, **kwargs):
        calls.append(True)
        error = OSError('PRIVATE_RAW_WINDOWS_ERROR')
        error.winerror = winerror
        raise error
    monkeypatch.setattr(ascend_native_selftest.subprocess, 'Popen', denied)
    result = ascend_native_selftest.probe('fixture.exe', 'fixture-origin')
    assert result['status'] == 'STOPPED' and result['safe_error_code'] == expected
    assert result['launcher_started'] is False and len(calls) == 1
    assert 'PRIVATE' not in json.dumps(result) and result['production_reads'] is False


def staged_fixture(tmp_path, monkeypatch):
    repo = repository(tmp_path)
    base = tmp_path / 'release'
    for name in ('candidate', 'pre-update'):
        (base / name).mkdir(parents=True)
    for folder, content in [('candidate', b'new'), ('pre-update', b'old')]:
        (base / folder / 'FreightDeskAscendHost.exe').write_bytes(content)
        (base / folder / 'launcher.cs').write_bytes(content + b' source')
    repo.path('FreightDeskAscendHost.exe').write_bytes(b'old')
    repo.path('launcher.cs').write_bytes(b'old source')
    value = {
        'candidate_host_sha256': release.digest(base / 'candidate/FreightDeskAscendHost.exe'),
        'prior_host_sha256': release.digest(base / 'pre-update/FreightDeskAscendHost.exe'),
        'candidate_launcher_sha256': release.digest(base / 'candidate/launcher.cs'),
        'prior_launcher_sha256': release.digest(base / 'pre-update/launcher.cs'),
    }
    monkeypatch.setattr(release, 'release_root', lambda repo: base)
    monkeypatch.setattr(release, 'verify', lambda repo: value)
    monkeypatch.setattr(release, 'configuration', lambda repo: 'fixture-origin')
    return repo, base, value


def test_failed_candidate_is_consumed_and_installation_stays_blocked(tmp_path, monkeypatch):
    repo, base, _ = staged_fixture(tmp_path, monkeypatch)
    calls = []
    def denied(*args):
        calls.append(True)
        assert json.loads((base / 'candidate-selftest.json').read_text())['status'] == 'STARTED'
        return {'status': 'STOPPED', 'safe_error_code': 'SELF_TEST_APPLICATION_CONTROL_BLOCKED',
                'production_reads': False, 'production_writes': False}
    monkeypatch.setattr(release, 'probe', denied)
    result = release.check_candidate(repo, owner_authorized=True)
    assert result['safe_error_code'] == 'SELF_TEST_APPLICATION_CONTROL_BLOCKED'
    with pytest.raises(ValueError, match='RELEASE_SELFTEST_ALREADY_ATTEMPTED'):
        release.check_candidate(repo, owner_authorized=True)
    with pytest.raises(ValueError, match='RELEASE_SELFTEST_REQUIRED'):
        release.install_host(repo, owner_authorized=True)
    assert len(calls) == 1 and repo.path('FreightDeskAscendHost.exe').read_bytes() == b'old'
    assert repo.path('launcher.cs').read_bytes() == b'old source'


def test_uncertain_candidate_execution_is_not_retried(tmp_path, monkeypatch):
    repo, base, _ = staged_fixture(tmp_path, monkeypatch)
    def interrupted(*args):
        raise RuntimeError('fixture crash')
    monkeypatch.setattr(release, 'probe', interrupted)
    with pytest.raises(RuntimeError):
        release.check_candidate(repo, owner_authorized=True)
    assert json.loads((base / 'candidate-selftest.json').read_text())['status'] == 'STARTED'
    with pytest.raises(ValueError, match='RELEASE_SELFTEST_ALREADY_ATTEMPTED'):
        release.check_candidate(repo, owner_authorized=True)


def successful_candidate(base, value):
    (base / 'candidate-selftest.json').write_text(json.dumps({
        'release': release.RELEASE, 'status': 'PASS', 'safe_error_code': 'SELF_TEST_OK',
        'candidate_host_sha256': value['candidate_host_sha256'],
        'production_reads': False, 'production_writes': False,
    }))


def test_two_file_host_update_recovers_source_when_executable_is_locked(tmp_path, monkeypatch):
    repo, base, value = staged_fixture(tmp_path, monkeypatch)
    successful_candidate(base, value)
    replace = release.atomic_replace
    def locked(candidate, target, **kwargs):
        if target.suffix == '.exe':
            raise PermissionError('fixture lock')
        return replace(candidate, target, **kwargs)
    monkeypatch.setattr(release, 'atomic_replace', locked)
    with pytest.raises(PermissionError):
        release.install_host(repo, owner_authorized=True)
    assert repo.path('launcher.cs').read_bytes() == b'old source'
    assert repo.path('FreightDeskAscendHost.exe').read_bytes() == b'old'
    assert not (base / 'installed.json').exists()


def test_two_file_host_update_and_rollback_preserve_authority(tmp_path, monkeypatch):
    repo, base, value = staged_fixture(tmp_path, monkeypatch)
    successful_candidate(base, value)
    before = repo.path('runtime.sqlite3').read_bytes()
    result = release.install_host(repo, owner_authorized=True)
    assert result['status'] == 'HOST_INSTALLED' and result['authority_changed'] is False
    assert repo.path('FreightDeskAscendHost.exe').read_bytes() == b'new'
    with pytest.raises(ValueError, match='RELEASE_RECEIPT_EXISTS'):
        release.install_host(repo, owner_authorized=True)
    result = release.install_host(repo, owner_authorized=True, rollback=True)
    assert result['status'] == 'HOST_ROLLED_BACK'
    assert repo.path('FreightDeskAscendHost.exe').read_bytes() == b'old'
    assert repo.path('launcher.cs').read_bytes() == b'old source'
    assert repo.path('runtime.sqlite3').read_bytes() == before


def test_install_receipt_failure_reports_that_hash_inspection_is_required(tmp_path, monkeypatch):
    repo, base, value = staged_fixture(tmp_path, monkeypatch)
    successful_candidate(base, value)
    original = Path.open
    def unavailable(path, *args, **kwargs):
        if path == base / 'installed.json':
            raise OSError('PRIVATE_STORAGE_ERROR')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', unavailable)
    with pytest.raises(ValueError, match='^RELEASE_INSTALL_RECEIPT_FAILED$'):
        release.install_host(repo, owner_authorized=True)
    assert repo.path('FreightDeskAscendHost.exe').read_bytes() == b'new'
    assert repo.path('launcher.cs').read_bytes() == b'new source'
    assert not (base / 'installed.json').exists()


def test_prepare_compiles_without_executing_candidate(tmp_path, monkeypatch):
    repo, base, _ = staged_fixture(tmp_path, monkeypatch)
    # Use a fresh stage root with the same verified backup; never remove an attempted candidate.
    fresh = tmp_path / 'new-release'
    (fresh / 'pre-update').mkdir(parents=True)
    for name in ('FreightDeskAscendHost.exe', 'launcher.cs'):
        (fresh / 'pre-update' / name).write_bytes((base / 'pre-update' / name).read_bytes())
    monkeypatch.setattr(release, 'release_root', lambda repo: fresh)
    source = tmp_path / 'source'
    for name in ('scripts', 'extensions/ascend-x1', '.tools/python'):
        (source / name).mkdir(parents=True)
    (source / 'scripts/native_host_launcher.cs').write_text('synthetic __PYTHON__ __SOURCE__')
    (source / '.tools/python/python.exe').write_bytes(b'synthetic')
    (source / 'extensions/ascend-x1/manifest.json').write_text(json.dumps({
        'version': BUILD['extension_version'], 'host_permissions': ['https://ascendtms.com/*'],
        'permissions': ['nativeMessaging', 'storage', 'alarms', 'scripting'],
    }))
    monkeypatch.setattr(release, 'ROOT', source)
    monkeypatch.setattr(release, 'source_hashes', lambda: {'fixture': 'a' * 64})
    def commands(argv, **kwargs):
        if argv[:2] == ['git', 'status']:
            return SimpleNamespace(stdout=b'')
        if argv[:2] == ['git', 'rev-parse']:
            return SimpleNamespace(stdout='a' * 40)
        assert argv[0].endswith('csc.exe')
        (fresh / 'candidate/FreightDeskAscendHost.exe').write_bytes(b'compiled fixture')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(release.subprocess, 'run', commands)
    monkeypatch.setattr(release, 'probe', lambda *args: pytest.fail('staging must never execute'))
    result = release.prepare(repo)
    assert result['status'] == 'RELEASE_STAGED' and result['candidate_execution'] == 'NOT_RUN'
    assert json.loads((fresh / 'prepared.json').read_text())['candidate_execution'] == 'NOT_RUN'
    assert repo.path('FreightDeskAscendHost.exe').read_bytes() == b'old'
