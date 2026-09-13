"""Offline preparation and explicitly authorized future manual login / one-load read."""
import argparse
import asyncio
import json

from app.core.runtime import RuntimePaths
from app.services.ascend_live import bounded_read
from executors.playwright.browser import AveryBrowserSession
from integrations.ascend.models import BrowserContract, ReadGrant


def prepare():
    paths = RuntimePaths.from_environment()
    for parts in [('Browser','booking-logistics','ascend'), ('Data','booking-logistics','ascend')]:
        paths.path(*parts).mkdir(parents=True, exist_ok=True)
    target = paths.path('Data','booking-logistics','ascend','setup-status.json')
    if not target.exists():
        target.write_text(json.dumps({'status':'AWAITING_OWNER_AUTHORIZATION', 'live_navigation_authorized':False,
            'contract_verified':False, 'proposed_load_number':'1752', 'production_writes_enabled':False,
            'required_next_evidence':['owner-verified login URL', 'account/company identity selectors and exact values',
                'exact-load URL and observed DOM selectors', 'one-load owner grant bound to contract hash']}, indent=2),
            encoding='utf-8')
    print('Offline setup prepared. No browser launched; no Ascend networking.')
    print('Dedicated profile: '+str(paths.path('Browser','booking-logistics','ascend')))


async def manual_login():
    browser = AveryBrowserSession()
    try:
        context = await browser.launch(owner_authorized=True)
        await context.set_offline(False)
        print('Dedicated Avery window is blank. Owner: enter the verified Ascend login URL and complete login/MFA manually.')
        print('Do not import browser data or save the password. No automated load read or write will run.')
        await asyncio.to_thread(input, 'After confirming the Booking Logistics account, press Enter here to close safely: ')
    finally:
        await browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['prepare','login','read','identity','validate-1752','diagnose-session',
                                            'diagnose-continuity','login-validate-1752','login-discover-ops','login-diagnose-table'])
    parser.add_argument('--owner-authorized', action='store_true')
    parser.add_argument('--contract', default='browser-contract.json')
    parser.add_argument('--grant', default='read-grant.json')
    parser.add_argument('--origin', help='Owner-verified https://hostname only; no path/query/token')
    parser.add_argument('--owner-attested-booking-logistics', action='store_true')
    parser.add_argument('--attempt-id', help='One-use audit identifier; consumed on success or failure')
    parser.add_argument('--service-date', help='Owner-selected operating date YYYY-MM-DD; otherwise prompted locally')
    parser.add_argument('--board-date-format', choices=['ISO','US'], help='Owner-confirmed UI format: ISO or US MM/DD/YYYY')
    args = parser.parse_args()
    if args.operation == 'prepare':
        prepare()
        return
    if not args.owner_authorized:
        raise ValueError('explicit_owner_live_authorization_required')
    if args.operation == 'login-diagnose-table':
        from integrations.ascend.table_diagnostic import diagnose_table
        if not args.owner_attested_booking_logistics or args.origin != 'https://ascendtms.com':
            raise ValueError('owner_attestation_fixed_origin_required')
        if args.service_date not in {None,'2026-09-11'} or args.board_date_format not in {None,'US'}:
            raise ValueError('table_diagnostic_fixed_date_required')
        print(json.dumps(asyncio.run(diagnose_table(attempt_id=args.attempt_id or ''))))
        return
    if args.operation == 'login-discover-ops':
        from datetime import date

        from integrations.ascend.ops_discovery import login_discover_ops
        if not args.owner_attested_booking_logistics or not args.attempt_id or args.origin not in {None,'https://ascendtms.com'}:
            raise ValueError('owner_attestation_fixed_origin_and_attempt_required')
        chosen = args.service_date or input('Operating date for tomorrow\'s board (YYYY-MM-DD, no timezone conversion): ').strip()
        board_format = args.board_date_format or input('Ascend board date format (ISO for YYYY-MM-DD, US for MM/DD/YYYY): ').strip().upper()
        print(json.dumps(asyncio.run(login_discover_ops(service_date=date.fromisoformat(chosen), attempt_id=args.attempt_id,
                                                       board_date_format=board_format))))
        return
    if args.operation in {'diagnose-continuity', 'login-validate-1752'}:
        from integrations.ascend.session_continuity import diagnose_continuity, login_validate_1752
        if args.origin not in {None, 'https://ascendtms.com'}:
            raise ValueError('fixed_verified_origin_required')
        if args.operation == 'diagnose-continuity':
            if args.attempt_id:
                raise ValueError('continuity_diagnostic_does_not_take_load_grants')
            result = asyncio.run(diagnose_continuity())
        else:
            if not args.owner_attested_booking_logistics or not args.attempt_id:
                raise ValueError('owner_attestation_and_attempt_required')
            result = asyncio.run(login_validate_1752(attempt_id=args.attempt_id))
        print(json.dumps(result))
        return
    if args.operation == 'diagnose-session':
        from integrations.ascend.structural_diagnostic import run_structural_diagnostic
        if args.origin not in {None, 'https://ascendtms.com'} or args.attempt_id:
            raise ValueError('diagnostic_fixed_origin_no_load_grant')
        print(json.dumps(asyncio.run(run_structural_diagnostic())))
        return
    if args.operation == 'validate-1752':
        from app.services.ascend_bootstrap import validate_1752
        if not args.owner_attested_booking_logistics or not args.attempt_id:
            raise ValueError('owner_attestation_and_one_use_attempt_required')
        if args.origin not in {None, 'https://ascendtms.com'}:
            raise ValueError('owner_attestation_origin_mismatch')
        print(json.dumps(asyncio.run(validate_1752(attempt_id=args.attempt_id, owner_attested=True))))
        return
    if args.operation == 'login':
        asyncio.run(manual_login())
        return
    if args.operation == 'identity':
        from integrations.ascend.identity import IdentityConfig, identity_probe
        if not args.origin:
            raise ValueError('verified_authenticated_origin_required')
        config = IdentityConfig(origin=args.origin)
        result = asyncio.run(identity_probe(config))
        print(json.dumps(result))
        return
    paths = RuntimePaths.from_environment()
    contract = BrowserContract.model_validate_json(paths.path('Data','booking-logistics','ascend',args.contract).read_text())
    grant = ReadGrant.model_validate_json(paths.path('Data','booking-logistics','ascend',args.grant).read_text())
    asyncio.run(bounded_read(contract, grant, paths=paths))
    print('Bounded read completed. Review sanitized protected dashboard and private local evidence; no writes executed.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Ascend browser workflow stopped. Check authorization/contract/session locally; no raw details printed.') from None
