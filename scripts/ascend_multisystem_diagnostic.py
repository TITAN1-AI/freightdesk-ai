"""Owner-executed Ascend-only namespace; no multi-system phase dispatcher."""
import argparse
import asyncio
import json

from app.services.multi_phase_progress import safe_failure
from integrations.ascend.isolated_diagnostic import ATTEMPT, run_diagnostic

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--owner-authorized',action='store_true',required=True)
    parser.parse_args()
    try:
        result=asyncio.run(run_diagnostic())
    except Exception as error:
        code,reason=safe_failure(error)
        result={'attempt_id':ATTEMPT,'status':'STOPPED_ASCEND_DIAGNOSTIC','execution_stage':'PREFLIGHT_OR_PERSISTENCE',
            'error_code':code,'reason':reason,'production_writes':False}
    print(json.dumps(result))
    if result['status']!='ASCEND_DIAGNOSTIC_COMPLETE':
        raise SystemExit(1)
