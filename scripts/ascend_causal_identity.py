"""One owner-executed causal identity observation; importing/help never launches a browser."""
import argparse
import asyncio
import json

from integrations.ascend.causal_identity_diagnostic import ATTEMPT, run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='1755-only causal DOM identity diagnostic; no operational extraction.')
    parser.add_argument('--owner-authorized', action='store_true', required=True)
    parser.add_argument('--attempt-id', choices=[ATTEMPT], required=True)
    parser.parse_args()
    try:
        result = asyncio.run(run())
        print(json.dumps(result))
    except Exception:
        raise SystemExit('Causal identity diagnostic stopped at local preflight/persistence; private details omitted.') from None
    if result.get('status') != 'CAUSAL_IDENTITY_DIAGNOSTIC_COMPLETE':
        raise SystemExit(1)
