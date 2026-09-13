"""Offline source manifest and rollback rehearsal. No install, host, lease or vendor entry point."""
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from app.core.runtime import RuntimePaths

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '6d4a781'


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True).stdout


def source_manifest():
    files = git('ls-files', '--cached', '--others', '--exclude-standard', '-z').decode().split('\0')
    hashes = {}
    for name in sorted(set(files) - {''}):
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('SOURCE_FILE_INVALID')
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    canonical = json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()
    return hashes, hashlib.sha256(canonical).hexdigest()


def rehearse_rollback(destination):
    """Extract the immutable baseline in TestRuns and check every blob; never replace the project."""
    paths = RuntimePaths.from_environment()
    relative = destination.absolute().relative_to(paths.path('Data', 'TestRuns').absolute())
    destination = paths.path('Data', 'TestRuns', *relative.parts)
    baseline = git('rev-parse', BASELINE).decode().strip()
    archive = git('-c', 'core.autocrlf=false', 'archive', '--format=zip', baseline)
    tree = {}
    for entry in git('ls-tree', '-r', '-z', baseline).split(b'\0'):
        if entry:
            metadata, name = entry.split(b'\t', 1)
            mode, kind, blob = metadata.decode().split()
            if mode != '100644' or kind != 'blob':
                raise ValueError('BASELINE_ENTRY_INVALID')
            tree[name.decode()] = blob
    observed = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        for info in zipped.infolist():
            if info.is_dir():
                continue
            name = PurePosixPath(info.filename)
            if name.is_absolute() or '..' in name.parts or info.filename not in tree:
                raise ValueError('BASELINE_PATH_INVALID')
            data = zipped.read(info)
            digest = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
            if tree[info.filename] != digest:
                raise ValueError('BASELINE_HASH_MISMATCH')
            target = paths.path('Data', 'TestRuns', *relative.parts, *name.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.read_bytes() != data:
                    raise ValueError('BASELINE_REHEARSAL_CONFLICT')
            else:
                with target.open('xb') as output:
                    output.write(data)
            observed[info.filename] = digest
    if observed != tree:
        raise ValueError('BASELINE_INCOMPLETE')
    manifest = json.loads((destination / 'extensions/ascend-x1/manifest.json').read_text())
    if 'webbridge-v2' in json.dumps(manifest):
        raise ValueError('BASELINE_NOT_V1')
    return {'baseline_commit': baseline, 'verified_files': len(observed), 'v1_default': True,
        'rollback_scope': 'SOURCE_ONLY_TESTRUNS', 'installed_state_changed': False}


def main():
    paths = RuntimePaths.from_environment()
    if git('status', '--porcelain').strip():
        raise ValueError('SOURCE_NOT_COMMITTED')
    source_commit = git('rev-parse', 'HEAD').decode().strip()
    hashes, digest = source_manifest()
    destination = paths.path('Data', 'TestRuns', 'webbridge-v2-offline-release', digest)
    rollback = rehearse_rollback(destination / 'rollback-baseline')
    result = {'schema_version': 1, 'release': 'V2_OFFLINE_AUDIT_FIXES_1', 'source_sha256': digest,
        'source_commit': source_commit,
        'files': hashes, 'rollback': rollback, 'compatibility_version': 3, 'graph_schema': 2, 'wire_version': 1,
        'activation': 'CANDIDATE_ONLY', 'v1_default': True, 'v2_live_packaging': 'BLOCKED',
        'live_validated': False, 'production_writes': False}
    target = destination / 'source-manifest.json'
    data = json.dumps(result, sort_keys=True, indent=2).encode()
    if target.exists() and target.read_bytes() != data:
        raise ValueError('MANIFEST_CONFLICT')
    if not target.exists():
        with target.open('xb') as output:
            output.write(data)
    print(json.dumps({'status': 'OFFLINE_SOURCE_VERIFIED', 'source_sha256': digest,
        'source_file_count': len(hashes), 'rollback_files': rollback['verified_files'],
        'manifest': str(target), 'live_packaging': 'BLOCKED', 'installed_state_changed': False}))


if __name__ == '__main__':
    main()
