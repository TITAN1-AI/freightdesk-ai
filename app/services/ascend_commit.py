"""Owner-approved historical persistence only; no operational stores or adapters."""
import json
import sqlite3
from typing import Literal

from pydantic import PositiveInt

from app.core.runtime import RuntimePaths
from app.models.domain import AuditEvent, Model, utcnow
from app.services.ascend_staging import AscendRealStager, normalize, summarize
from app.services.mail_sync import digest
from app.services.store import Store

TENANT = 'booking-logistics'
LIMITATIONS = ('expenses_not_carrier_pay', 'raw_customer_identities_separate',
    'equipment_mappings_proposals_only', 'unknown_timezones_no_conversions',
    'missing_delivery_unverified', 'raw_identifiers_preserved',
    'exchange_rate_date_metadata_only', 'historical_store_only')


class HistoricalApproval(Model):
    tenant_id: Literal['booking-logistics'] = TENANT
    actor: Literal['owner'] = 'owner'
    source_hash: str
    batch_id: str
    mapping_hash: str
    row_count: PositiveInt
    currency: Literal['USD']
    limitations: tuple[str, ...]
    authorization: Literal['M4A_OWNER_HISTORICAL_COMMIT']


class AscendHistoricalCommitter:
    def __init__(self, paths=None):
        self.paths = paths or RuntimePaths.from_environment()

    def commit(self, filename: str, approval: HistoricalApproval):
        if tuple(approval.limitations) != LIMITATIONS:
            raise ValueError('historical_limitations_required')
        source = self.paths.path('Data', TENANT, 'history', 'inbox', filename)
        export, mapping, rows = AscendRealStager(self.paths).inspect(source)
        batch_id = digest([export['source_hash'], mapping.model_dump()])
        if (approval.source_hash != export['source_hash'] or approval.batch_id != batch_id or
                approval.mapping_hash != digest(mapping.model_dump()) or approval.row_count != len(rows)):
            raise ValueError('approval_source_mapping_mismatch')
        validation = summarize(export, rows, {})
        if not validation['validation_passed']:
            raise ValueError('source_validation_failed')
        path = self.paths.path('Data', TENANT, 'history', 'history.sqlite3')
        if not path.exists():
            raise ValueError('staged_store_required')
        store = Store(path)
        try:
            with store.transaction():
                batch = store.get(TENANT, 'ascend_stage_batch', batch_id)
                if (not batch['report']['validation_passed'] or batch['mapping'] != mapping.model_dump() or
                        batch['row_count'] != len(rows) or batch['source_hash'] != export['source_hash']):
                    raise ValueError('staged_batch_validation_failed')
                staged = [r for r in store.all(TENANT, 'ascend_stage_row') if r['batch_id'] == batch_id]
                if len(staged) != len(rows):
                    raise ValueError('staged_row_count_mismatch')
                staged_by_line = {r['row']: r for r in staged}
                for row in rows:
                    old = staged_by_line.get(row['row'], {})
                    if any(old.get(k) != row[k] for k in ['source_load_id', 'evidence_hash', 'raw_source', 'data']):
                        raise ValueError('staged_evidence_mismatch')
                existing = store.all(TENANT, 'ascend_history_record')
                by_source = {r['source_load_id']: r for r in existing}
                if len(by_source) != len(existing):
                    raise ValueError('existing_duplicate_source_identity')
                if any(r.get('provenance', {}).get('source_system') == 'ascend_export'
                       for r in store.all(TENANT, 'history_record')):
                    raise ValueError('legacy_history_requires_reconciliation')
                for row in rows:
                    old = by_source.get(row['source_load_id'])
                    if old and (old['evidence_hash'] != row['evidence_hash'] or
                                old['raw_source'] != row['raw_source'] or old['data'] != row['data'] or
                                old['currency'] != approval.currency):
                        raise ValueError('source_version_requires_owner_reconciliation')
                receipts = store.all(TENANT, 'ascend_commit_receipt')
                prior = next((r for r in receipts if r['batch_id'] == batch_id), None)
                if prior:
                    if prior['approval'] != approval.model_dump(mode='json') or any(
                            row['source_load_id'] not in by_source for row in rows):
                        raise ValueError('commit_receipt_integrity_failed')
                    return {**prior, 'inserted_this_run': 0, 'idempotent_reimport': True}
                now = utcnow().isoformat()
                inserted = 0
                record_ids = []
                for row in rows:
                    old = by_source.get(row['source_load_id'])
                    record_id = old['id'] if old else digest(['ascend_export', row['source_load_id'], row['evidence_hash']])
                    record_ids.append(record_id)
                    if old:
                        continue
                    store.put(TENANT, 'ascend_history_record', record_id, {
                        'id': record_id, **row, 'status': 'COMMITTED_HISTORICAL_ONLY',
                        'currency': approval.currency, 'currency_basis': 'owner_confirmation',
                        'provenance': {'source_system': 'ascend_export', 'source_identifier': filename,
                            'source_hash': export['source_hash'], 'batch_id': batch_id,
                            'mapping_hash': approval.mapping_hash, 'source_row': row['row'],
                            'committed_at': now, 'approval_hash': digest(approval.model_dump(mode='json'))},
                        'limitations': list(LIMITATIONS)})
                    inserted += 1
                receipt = {'batch_id': batch_id, 'source_hash': export['source_hash'],
                    'committed_at': now, 'committed_record_count': len(rows), 'inserted_records': inserted,
                    'reused_identical_records': len(rows)-inserted, 'record_ids': record_ids,
                    'approval': approval.model_dump(mode='json'), 'validation': validation}
                receipt['validation'] = {**validation, 'commit_status': 'COMMITTED_HISTORICAL_ONLY',
                    'committed_rows': len(rows), 'currency': 'USD', 'currency_basis': 'owner_confirmation'}
                store.put(TENANT, 'ascend_commit_receipt', batch_id, receipt)
                store.audit(AuditEvent(tenant_id=TENANT, source='ascend_historical_csv', actor_id='FreightDesk/Avery',
                    event='ASCEND_HISTORY_COMMITTED', explanation='Owner-approved USD historical evidence; no operational mutation',
                    facts={'batch_id': batch_id, 'source_hash': export['source_hash'], 'rows': len(rows),
                           'inserted': inserted, 'approval_hash': digest(approval.model_dump(mode='json'))}))
                return {**receipt, 'inserted_this_run': inserted, 'idempotent_reimport': False}
        finally:
            store.close()

    def read_committed(self, batch_id):
        path = self.paths.path('Data', TENANT, 'history', 'history.sqlite3')
        with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
            receipt = db.execute('SELECT body FROM records WHERE tenant=? AND kind=? AND id=?',
                                 (TENANT, 'ascend_commit_receipt', batch_id)).fetchone()
            if not receipt:
                raise ValueError('committed_batch_required')
            receipt = json.loads(receipt[0])
            records = {json.loads(r[0])['id']: json.loads(r[0]) for r in db.execute(
                'SELECT body FROM records WHERE tenant=? AND kind=?', (TENANT, 'ascend_history_record'))}
        selected = [records[key] for key in receipt['record_ids']]
        if len(selected) != receipt['committed_record_count'] or any(
                digest(r['raw_source']) != r['evidence_hash'] or
                normalize(r['raw_source'], r['row'])['data'] != r['data'] or
                r['currency'] != receipt['approval']['currency'] for r in selected):
            raise ValueError('committed_integrity_failed')
        return receipt, sorted(selected, key=lambda r: r['row'])
