import argparse
import asyncio
import json

from integrations.ascend.detail_identity_diagnostic import run

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--owner-authorized',action='store_true',required=True)
    parser.parse_args()
    try:
        result=asyncio.run(run())
        print(json.dumps(result))
    except Exception:
        raise SystemExit('Identity diagnostic stopped at local preflight/persistence; no private details printed.') from None
    if result.get('status')!='IDENTITY_DIAGNOSTIC_COMPLETE':
        raise SystemExit(1)
