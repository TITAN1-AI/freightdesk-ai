"""Offline owner-approved historical commit, bounded idempotence check and private report."""
import argparse
import json
import sqlite3

from app.core.runtime import RuntimePaths
from app.services.ascend_commit import TENANT, AscendHistoricalCommitter, HistoricalApproval
from app.services.ascend_intelligence import write_intelligence
from app.services.mail_sync import digest


def snapshot(path):
    with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
        records = db.execute('SELECT tenant,kind,id,body FROM records ORDER BY tenant,kind,id').fetchall()
        audit = db.execute('SELECT seq,tenant,body FROM audit ORDER BY seq').fetchall()
        counts = dict(db.execute('SELECT kind,count(*) FROM records WHERE tenant=? GROUP BY kind', (TENANT,)))
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    return {'records_hash': digest(records), 'audit_hash': digest(audit), 'counts': counts,
            'sqlite_integrity': integrity}


def execute(filename, approval_filename):
    paths = RuntimePaths.from_environment()
    approval_path = paths.path('Data', TENANT, 'history', 'approvals', approval_filename)
    approval = HistoricalApproval.model_validate_json(approval_path.read_text(encoding='utf-8'))
    database = paths.path('Data', TENANT, 'history', 'history.sqlite3')
    before = snapshot(database)
    backups = paths.path('Data', TENANT, 'history', 'backups')
    backups.mkdir(parents=True, exist_ok=True)
    backup = paths.path('Data', TENANT, 'history', 'backups', approval.batch_id+'-before-commit.sqlite3')
    if not backup.exists():
        with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as src:
            with sqlite3.connect(backup) as dest:
                src.backup(dest)
    committer = AscendHistoricalCommitter(paths)
    committed = committer.commit(filename, approval)
    first = snapshot(database)
    repeated = committer.commit(filename, approval)
    second = snapshot(database)
    if first != second or repeated['inserted_this_run'] != 0 or not repeated['idempotent_reimport']:
        raise ValueError('idempotence_verification_failed')
    report, target = write_intelligence(committer, approval.batch_id)
    v = report['validation']
    if not v['validation_passed'] or v['rows'] != approval.row_count or first['sqlite_integrity'] != 'ok':
        raise ValueError('post_commit_validation_failed')
    for kind in ['shipment', 'task', 'mail_update_proposal', 'history_record']:
        if before['counts'].get(kind, 0) != second['counts'].get(kind, 0):
            raise ValueError('historical_kind_isolation_failed')
    verification = {'context': report['context'], 'source_identifier': filename,
        'mapping_hash': approval.mapping_hash, 'approval_hash': digest(approval.model_dump(mode='json')),
        'batch_committed_records': committed['committed_record_count'],
        'total_committed_records': second['counts'].get('ascend_history_record', 0),
        'inserted_this_execution': committed['inserted_this_run'], 'reimport_inserted': repeated['inserted_this_run'],
        'reimport_records_and_audit_unchanged': first == second, 'sqlite_integrity': first['sqlite_integrity'],
        'source_duplicate_rows': v['duplicate_rows'], 'source_conflicting_duplicate_ids': v['conflicting_duplicate_ids'],
        'changed_version_handling': 'synthetic tests only; no changed production export exercised',
        'post_commit_validation': v, 'before': before, 'after': second,
        'profile_counts': {k: len(report[k]) for k in ['CustomerProfile','LaneProfile','CarrierProfile','FacilityProfile','EquipmentUsage']},
        'RateHistorySummary_count': 1, 'storage_scope': 'history.sqlite3 and private history reports only'}
    (target/'commit-verification.json').write_text(json.dumps(verification, indent=2), encoding='utf-8')
    print(json.dumps({k: verification[k] for k in ['batch_committed_records', 'total_committed_records',
        'inserted_this_execution', 'reimport_inserted', 'reimport_records_and_audit_unchanged',
        'sqlite_integrity', 'profile_counts']}))
    print('Historical report: '+str(target/'historical-intelligence.md'))
    return verification


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help='Approved CSV basename in runtime history/inbox')
    parser.add_argument('approval_filename', help='Owner authorization JSON basename in runtime history/approvals')
    args = parser.parse_args()
    try:
        execute(args.filename, args.approval_filename)
    except Exception:
        raise SystemExit('Historical workflow stopped; inspect the private commit ledger before retrying. No raw details printed.') from None
