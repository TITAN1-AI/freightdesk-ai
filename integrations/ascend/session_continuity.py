"""Metadata-only continuity diagnostics and owner-interactive, same-process read entry point."""
import asyncio
import json
import time
from collections import Counter
from urllib.parse import urlsplit

from app.core.runtime import RuntimePaths
from app.models.domain import utcnow
from executors.playwright.browser import AveryBrowserSession
from integrations.ascend.identity import IdentityConfig, OwnerAttestedIdentity, observe_session
from integrations.ascend.models import AscendError
from integrations.ascend.structural_diagnostic import ORIGIN, poll_structure, safe_path


def aggregate_cookies(cookies, now: float):
    """Never return names, values, domain strings, cookie records or expiry timestamps."""
    first_party = [c for c in cookies if c.get('domain', '').lstrip('.') == 'ascendtms.com']
    session = sum(c.get('expires', -1) <= 0 for c in first_party)
    return {'first_party_cookie_count':len(first_party), 'session_only_cookie_count':session,
        'persistent_cookie_count':len(first_party)-session,
        'first_party_cookie_future_expiry':any(c.get('expires', -1) > now for c in first_party)}


async def auth_metadata(context, page):
    if safe_path(page.url, ORIGIN) is None:
        raise AscendError('metadata_origin_mismatch')
    # Playwright's cookie API returns complete records; reduce immediately in memory and discard.
    # No cookie/storage record is persisted, printed, included in errors or sent elsewhere.
    cookies = await context.cookies()
    counts = aggregate_cookies(cookies, time.time())
    del cookies
    storage = await asyncio.wait_for(page.evaluate('''async () => {
        const count = getter => { try { return getter(); } catch (_) { return null; } };
        let workers = null;
        try { workers = 'serviceWorker' in navigator ? (await navigator.serviceWorker.getRegistrations()).length : 0; }
        catch (_) {}
        return {local_storage_entry_count:count(() => localStorage.length),
            session_storage_entry_count:count(() => sessionStorage.length),
            service_worker_registration_count:workers,
            body_text_length:document.body?.innerText.length || 0};
    }'''), 3)
    diagnostic = await observe_session(page, IdentityConfig(origin=ORIGIN))
    return {**counts, **storage, 'current_path':safe_path(page.url, ORIGIN),
        'authenticated_navigation_marker_count':len(diagnostic.authenticated_nav_markers),
        'session_authenticated':diagnostic.session_authenticated}


def compare_auth(before, after):
    count_fields = ('first_party_cookie_count', 'session_only_cookie_count', 'persistent_cookie_count',
        'local_storage_entry_count', 'session_storage_entry_count', 'service_worker_registration_count',
        'body_text_length', 'authenticated_navigation_marker_count')
    return {'before':before, 'after':after, 'count_delta_after_minus_before':{
        key:after[key]-before[key] if before[key] is not None and after[key] is not None else None
        for key in count_fields},
        'session_storage_loss_observed':before['session_storage_entry_count'] not in {None, 0} and
                                       after['session_storage_entry_count'] == 0,
        'authentication_survived_reopen':before['session_authenticated'] and after['session_authenticated'],
        'causality_established':False}


class RenderSignals:
    """Observe counts only. Never inspect response bodies, API contracts, console/error text or headers."""
    def __init__(self, page):
        self.page = page
        self.console_errors = 0
        self.page_errors = 0
        self.failed_types = Counter()
        self.failed_origins = Counter()
        self.origin_ids = {}
        self.listeners = [('console', self.console), ('pageerror', self.error), ('requestfailed', self.failed)]
        for event, callback in self.listeners:
            page.on(event, callback)

    def console(self, message):
        self.console_errors += message.type == 'error'

    def error(self, _):
        self.page_errors += 1

    def failed(self, request):
        kind = request.resource_type
        allowed = {'document','stylesheet','image','media','font','script','texttrack','xhr','fetch',
                   'eventsource','websocket','manifest','other'}
        self.failed_types[kind if kind in allowed else 'other'] += 1
        url = urlsplit(request.url)
        origin = (url.scheme, url.hostname, url.port)
        if origin == ('https', 'ascendtms.com', None):
            bucket = 'ascendtms.com'
        else:
            # Stable within this diagnostic, opaque externally: no unrelated hostname is retained.
            if origin not in self.origin_ids:
                self.origin_ids[origin] = 'other-origin-'+str(len(self.origin_ids)+1)
            bucket = self.origin_ids[origin]
        self.failed_origins[bucket] += 1

    async def summary(self, response):
        paths = []
        request = response.request if response else None
        # Top-level navigation chain only, no subresource/API responses are inspected.
        while request is not None and len(paths) < 20:
            path = safe_path(request.url, ORIGIN)
            if path is not None:
                paths.append(path)
            request = request.redirected_from
        elements = await self.page.evaluate('''() => ({script_element_count:document.scripts.length,
            stylesheet_count:document.styleSheets.length})''')
        return {'top_level_document_http_status':response.status if response else None,
            'redirect_path_chain':list(reversed(paths)), 'javascript_console_error_count':self.console_errors,
            'pageerror_count':self.page_errors, 'requestfailed_by_resource_type':dict(self.failed_types),
            'failed_resource_origin_counts':dict(self.failed_origins), **elements}

    def detach(self):
        for event, callback in self.listeners:
            self.page.remove_listener(event, callback)
        self.origin_ids.clear()


def checked_browser(paths):
    browser = AveryBrowserSession(paths)
    approved = OwnerAttestedIdentity(owner_authorized=True)
    if str(browser.profile).rstrip('\\/').lower() != approved.profile.lower() or browser.channel != 'msedge':
        raise AscendError('continuity_profile_or_channel_mismatch')
    return browser


async def owner_login_page(browser, *, normal_application_network=False):
    options = {'normal_application_network':True} if normal_application_network else {}
    context = await browser.launch(owner_authorized=True, require_existing=True, **options)
    await context.set_offline(False)
    print('Existing dedicated Edge profile opened. Owner: log in manually at https://ascendtms.com and confirm Booking Logistics.')
    print('Do not edit loads or send communications. Leave exactly one authenticated Ascend tab open.')
    await asyncio.to_thread(input, 'After confirming Booking Logistics, press Enter here to begin the bounded read-only phase: ')
    candidates = [p for p in context.pages if safe_path(p.url, ORIGIN) in {'/', '/loads'}]
    if len(candidates) != 1 or len([p for p in context.pages if p.url != 'about:blank']) != 1:
        raise AscendError('owner_login_page_ambiguous')
    if not normal_application_network:
        await browser.readonly_network(ORIGIN)
    return candidates[0]


def save_report(paths, prefix, report):
    stamp = utcnow().strftime('%Y%m%dT%H%M%S%fZ')
    path = paths.path('Data', 'booking-logistics', 'ascend', prefix+'-'+stamp+'.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')


async def diagnose_continuity(*, paths=None):
    """Future owner-authorized manual login, before/after reopen. Never reads a load or consumes a grant."""
    paths = paths or RuntimePaths.from_environment()
    browser = checked_browser(paths)
    report = {'status':'STOPPED_CONTINUITY_DIAGNOSTIC', 'tenant_identity':'Booking Logistics',
        'tenant_identity_source':'OWNER_ATTESTED', 'load_attempt_consumed':False, 'load_opened':False}
    signals = None
    try:
        page = await owner_login_page(browser)
        before = await auth_metadata(browser.context, page)
        report['before'] = before
        if not before['session_authenticated']:
            raise AscendError('interactive_session_not_authenticated')
        # Persist the aggregate baseline before closure so a failed reopen cannot lose it.
        save_report(paths, 'continuity-before', report)
        await browser.close()
        context = await browser.launch(owner_authorized=True, require_existing=True)
        await browser.readonly_network(ORIGIN)
        page = context.pages[0]
        signals = RenderSignals(page)
        response = await page.goto(ORIGIN+'/', wait_until='domcontentloaded', timeout=20000)
        report['render'] = await poll_structure(page)
        after = await auth_metadata(context, page)
        report['comparison'] = compare_auth(before, after)
        report['resources'] = await signals.summary(response)
        report['status'] = 'CONTINUITY_DIAGNOSTIC_COMPLETE'
    except Exception:
        pass  # Fixed status only; no raw browser/provider errors.
    finally:
        if signals:
            signals.detach()
        try:
            await browser.close()
        finally:
            save_report(paths, 'continuity-result', report)
    return report


async def login_validate_1752(*, attempt_id: str, paths=None):
    from app.services.ascend_bootstrap import validate_1752
    from integrations.ascend.models import ReadGrant

    if attempt_id == 'owner-bootstrap-1752-20260910-02':
        raise AscendError('reserved_load_attempt_must_not_be_consumed')
    # Validate before launching; the actual one-use read clock starts after owner confirmation.
    ReadGrant(id=attempt_id, owner_authorized=True, load_number='1752', expires_at=utcnow(), contract_hash='pending')
    paths = paths or RuntimePaths.from_environment()
    browser = checked_browser(paths)
    report = {'status':'STOPPED_SAME_PROCESS_VALIDATION', 'tenant_identity':'Booking Logistics',
        'tenant_identity_source':'OWNER_ATTESTED', 'persistent_cross_process_session_reuse':False}
    try:
        page = await owner_login_page(browser, normal_application_network=True)
        # No cookie/storage or network instrumentation on the owner-executed read path.
        diagnostic = await observe_session(page, IdentityConfig(origin=ORIGIN))
        report['interactive_session_authenticated'] = diagnostic.session_authenticated
        if not diagnostic.session_authenticated:
            raise AscendError('interactive_session_not_authenticated')
        # Pass the exact live page/context: no close, new page, replacement context or root reload.
        report['read_result'] = await validate_1752(attempt_id=attempt_id, owner_attested=True, paths=paths,
                                                  existing_browser=browser, existing_page=page)
        report['status'] = report['read_result']['status']
    except Exception:
        pass
    finally:
        try:
            await browser.close()
        finally:
            save_report(paths, 'same-process-result', report)
    return report
