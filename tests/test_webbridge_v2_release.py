"""Source-only rollback verification; no project reset or installed-state operation."""
import json
from pathlib import Path

import pytest

from scripts.webbridge_v2_release import main, rehearse_rollback, source_manifest


def test_source_manifest_excludes_runtime_and_secret_files():
    hashes, digest = source_manifest()
    assert len(digest) == 64 and hashes['extensions/ascend-x1/manifest.json']
    assert not any(Path(name).suffix in {'.sqlite3', '.db', '.dpapi', '.exe'} or '.tools/' in name
        or Path(name).name.startswith('.env') and Path(name).name != '.env.example' for name in hashes)
    manifest = json.loads(Path('extensions/ascend-x1/manifest.json').read_text())
    assert 'webbridge-v2' not in json.dumps(manifest)


def test_rollback_restores_verified_baseline_only_under_testruns(tmp_path):
    result = rehearse_rollback(tmp_path / 'baseline')
    assert result['verified_files'] == 358 and result['v1_default']
    assert result['installed_state_changed'] is False
    assert rehearse_rollback(tmp_path / 'baseline') == result
    (tmp_path / 'baseline/extensions/ascend-x1/manifest.json').write_text('{}')
    with pytest.raises(ValueError, match='BASELINE_REHEARSAL_CONFLICT'):
        rehearse_rollback(tmp_path / 'baseline')


def test_rollback_rejects_selected_project():
    with pytest.raises(ValueError):
        rehearse_rollback(Path.cwd())


def test_release_requires_committed_source(monkeypatch):
    monkeypatch.setattr('scripts.webbridge_v2_release.git', lambda *args: b' M synthetic-source.py')
    with pytest.raises(ValueError, match='SOURCE_NOT_COMMITTED'):
        main()
