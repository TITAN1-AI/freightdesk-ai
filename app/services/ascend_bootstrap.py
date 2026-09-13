"""One-use Customer Zero bootstrap. No automatic login, retries or selector invention."""
import json
from datetime import timedelta

from app.core.runtime import RuntimePaths
from app.models.domain import ActionPolicy, utcnow
from app.services.ascend_live import ROOT, PolicyEngine, existing_evidence, local_records
from app.services.mail_sync import digest
from executors.playwright.browser import AveryBrowserSession, BrowserExecutor
from integrations.ascend.adapter import AscendBrowserAdapter
from integrations.ascend.identity import IdentityConfig, OwnerAttestedIdentity, observe_session
from integrations.ascend.models import AscendError, BrowserContract, ReadGrant


async def validate_1752(*, attempt_id: str, owner_attested: bool, paths=None,
                        existing_browser=None, existing_page=None):
    """Stop after discovery when no observed/verified load DOM contract exists."""
    from app.services.ascend_reconciliation import reconcile

    paths = paths or RuntimePaths.from_environment()
    attestation = OwnerAttestedIdentity(owner_authorized=owner_attested)
    config = IdentityConfig(origin=attestation.origin)
    now = utcnow()
    # Validate the identifier before using it as a runtime filename.
    grant = ReadGrant(id=attempt_id, owner_authorized=True, load_number='1752',
                     expires_at=now+timedelta(minutes=10), contract_hash='bootstrap-pending-observed-contract')
    browser = existing_browser or AveryBrowserSession(paths)
    if (existing_browser is None) != (existing_page is None):
        raise AscendError('same_process_context_pair_required')
    if existing_page is not None and existing_page.context is not browser.context:
        raise AscendError('same_process_page_context_mismatch')
    if str(browser.profile).rstrip('\\/').lower() != attestation.profile.lower():
        raise AscendError('owner_attestation_profile_mismatch')
    policies = PolicyEngine(ROOT/'config'/'policies.json')
    def running():
        controls = local_records(paths.path('Data', 'booking-logistics', 'ascend.sqlite3'), 'ascend_controls')
        return policies.evaluate('read_ascend') == ActionPolicy.ALLOW and not any(
            c.get('paused', True) or c.get('human_takeover', True) for c in controls)
    if not running():
        raise AscendError('bootstrap_policy_or_pause_blocked')
    base = ('Data', 'booking-logistics', 'ascend')
    claim = paths.path(*base, attempt_id+'-claim.json')
    claim.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation consumes the attempt even on a crash. Never retry this ID.
    with claim.open('x', encoding='utf-8') as out:
        json.dump({'grant':grant.model_dump(mode='json'), 'attestation':attestation.model_dump(mode='json'),
                   'consumed':True}, out, indent=2)
    report = {'observed_at':now.isoformat(), 'tenant_identity':'Booking Logistics',
        'tenant_identity_source':'OWNER_ATTESTED', 'provider_tenant_identity_verified':False,
        'session_authenticated':False, 'exact_load_discovered':False, 'load_fields_read':False,
        'field_reconciliation':False, 'production_writes':False, 'canonical_mutation':False,
        'persistent_cross_process_session_reuse':False,
        'same_process_owner_login':existing_page is not None,
        'status':'STOPPED_BEFORE_SESSION_CHECK'}
    async def session_check(page, stage):
        diagnostic = await observe_session(page, config)
        paths.path(*base, attempt_id+'-'+stage+'-diagnostic.json').write_text(
            diagnostic.model_dump_json(indent=2), encoding='utf-8')
        if not diagnostic.session_authenticated:
            raise AscendError('SESSION_NOT_AUTHENTICATED')
        if not running() or grant.expires_at <= utcnow():
            raise AscendError('AUTHORITY_EXPIRED_OR_PAUSED')
        return diagnostic
    try:
        context = browser.context if existing_page is not None else await browser.launch(owner_authorized=True, require_existing=True)
        if existing_page is None:
            await browser.readonly_network(config.origin)
        page = existing_page if existing_page is not None else context.pages[0]
        if existing_page is None:
            await page.goto(config.origin+'/', wait_until='load', timeout=20000)
        # Bounded readiness wait; this observes the existing document, never reloads/retries a request.
        try:
            await page.get_by_role('link', name='Loads', exact=True).first.wait_for(state='visible', timeout=8000)
        except Exception:
            pass
        await session_check(page, 'dashboard')
        report['session_authenticated'] = True
        evidence = existing_evidence(paths, '1752')
        if not all(any(e.source == source and e.identity_reconciled and e.load_number == '1752' for e in evidence)
                   for source in ('Ascend history', 'CarrierView')):
            raise AscendError('EXACT_1752_EXISTING_EVIDENCE_NOT_RECONCILED')
        if existing_page is not None:
            from integrations.ascend.field_discovery import discover_1752
            discovered = await discover_1752(page, evidence, running=lambda:running() and grant.expires_at > utcnow())
            paths.path(*base, attempt_id+'-field-contract.json').write_text(
                discovered.model_dump_json(indent=2), encoding='utf-8')
            report.update(exact_load_discovered=True, load_fields_read=True, field_reconciliation=True,
                status='OBSERVED_FIELD_CONTRACT_PROPOSED', field_contract_version=discovered.version,
                reconciled_field_count=sum(f.state == 'RECONCILED_FOR_1752' for f in discovered.fields),
                unknown_field_count=sum(f.state == 'UNKNOWN' for f in discovered.fields))
            return report
        await page.goto(config.origin+'/loads', wait_until='load', timeout=20000)
        await session_check(page, 'loads')
        # Read only the exact identifier, never table/body text or other loads.
        matches = page.get_by_text('1752', exact=True)
        if await matches.count() != 1 or not await matches.is_visible():
            raise AscendError('EXACT_1752_NOT_UNIQUELY_VISIBLE')
        report['exact_load_discovered'] = True
        contract_path = paths.path(*base, 'browser-contract.json')
        if not contract_path.is_file():
            raise AscendError('OBSERVED_LOAD_DOM_CONTRACT_REQUIRED')
        contract = BrowserContract.model_validate_json(contract_path.read_text(encoding='utf-8'))
        if (contract.tenant_identity_source != 'OWNER_ATTESTED' or not contract.owner_attested_booking_logistics):
            raise AscendError('OWNER_ATTESTED_LOAD_CONTRACT_REQUIRED')
        grant.contract_hash = digest(contract.model_dump(mode='json'))
        with paths.path(*base, attempt_id+'-read-grant.json').open('x', encoding='utf-8') as out:
            json.dump(grant.model_dump(mode='json'), out, indent=2)
        adapter = AscendBrowserAdapter(BrowserExecutor(page), contract, policies, running)
        observation = await adapter.read_load(grant, use_current_session=True) if existing_page is not None else await adapter.read_load(grant)
        report['load_fields_read'] = True
        comparisons = reconcile(observation, evidence)
        # Retain provenance and comparison outcomes, not customer data, notes or raw field values.
        # The complete values exist only in memory for the bounded reconciliation.
        metadata = observation.model_dump(mode='json', exclude={'fields'})
        metadata['fields'] = {key:fact.model_dump(mode='json', exclude={'raw_value','normalized'})
                              for key, fact in observation.fields.items()}
        paths.path(*base, attempt_id+'-observation.json').write_text(json.dumps(
            {'observation':metadata, 'reconciliation':comparisons}, indent=2), encoding='utf-8')
        report['field_reconciliation'] = True
        report['status'] = 'READ_AND_RECONCILIATION_COMPLETE'
    except AscendError as exc:
        allowed = {'SESSION_NOT_AUTHENTICATED', 'AUTHORITY_EXPIRED_OR_PAUSED',
            'EXACT_1752_EXISTING_EVIDENCE_NOT_RECONCILED', 'EXACT_1752_NOT_UNIQUELY_VISIBLE',
            'OBSERVED_LOAD_DOM_CONTRACT_REQUIRED', 'OWNER_ATTESTED_LOAD_CONTRACT_REQUIRED'}
        allowed |= {'discovery_policy_pause_or_expiry', 'discovery_session_not_authenticated',
            'exact_load_discovery_ambiguous_or_missing', 'exact_load_read_control_unknown',
            'exact_load_read_control_ambiguous', 'non_read_load_control_blocked', 'non_read_load_destination_blocked',
            'field_discovery_bound_exceeded', 'detail_load_identity_unverified', 'detail_identity_changed_during_scan',
            'detail_fields_changed_during_scan', 'ambiguous_read_tab', 'read_section_bound_exceeded',
            'section_action_not_allowed', 'section_control_not_read_only'}
        report['status'] = 'STOPPED_'+(str(exc) if str(exc) in allowed else 'BOUNDED_VALIDATION_FAILED')
    except Exception:
        report['status'] = 'STOPPED_BOUNDED_VALIDATION_FAILED'
    finally:
        try:
            if existing_browser is None:
                await browser.close()
        finally:
            paths.path(*base, attempt_id+'-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
