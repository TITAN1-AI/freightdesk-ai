"""Offline adapter isolation, diagnostic privacy and pinned incorporation records."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from executors.ascend_extension.mapping_diagnostics import V2StructuralDiagnostic
from executors.ascend_extension.mapping_orchestrator import failed_predicate
from executors.webbridge_v2.runtime_bridge import install_offline

ROOT = Path(__file__).resolve().parents[1]


def test_adapter_cannot_install_on_tenant_store():
    access = SimpleNamespace(path=Path(r'C:\FreightDeskRuntime\Data\booking-logistics\ascend-native\runtime.sqlite3'))
    with pytest.raises(PermissionError, match='V2_OFFLINE_STORE_ONLY'):
        install_offline(access)
    assert not hasattr(access, '_offline_v2_adapter')


@pytest.mark.parametrize('private', [{'predicate': 'PRIVATE_ERROR'}, {'stage': 'PRIVATE_STAGE'}, {'raw_html': 'PRIVATE_HTML'}, {'bound_category': 'PRIVATE_ATTRIBUTE'}])
def test_diagnostic_cannot_export_unreviewed_strings(private):
    diagnostic = dict(schema_version=2, stage='RELATIONSHIPS_RESOLVED', predicate='TARGET_REFERENCE_UNRESOLVED')
    with pytest.raises(ValidationError):
        V2StructuralDiagnostic.model_validate(diagnostic | private)


def test_exact_adaptation_has_notices_and_frozen_hash():
    record = json.loads((ROOT / 'third_party/webbridge-v2-implementation.json').read_text())
    assert hashlib.sha256((ROOT / record['destination']).read_bytes()).hexdigest() == record['destination_sha256']
    assert record['incorporated'] and record['commit'] == 'd1ead3ecca23182f2d06d761c28e3d4edafb6595'
    assert 'Apache License' in (ROOT / record['notices'][0]).read_text()
    assert 'Puppeteer' in (ROOT / record['notices'][1]).read_text()


def test_owner_status_reports_validated_v2_predicate():
    diagnostic = V2StructuralDiagnostic(schema_version=2, stage='RELATIONSHIPS_RESOLVED', predicate='TARGET_REFERENCE_UNRESOLVED')
    job = {'stop_code': 'WORKSPACE_SECTION_UNVERIFIED', 'diagnostic': {'section_diagnostic': {'v2_diagnostic': diagnostic.model_dump()}}}
    assert failed_predicate(job) == 'TARGET_REFERENCE_UNRESOLVED'
