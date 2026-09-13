"""Local, existing-profile account probe. No shipment lookup and no operational controls."""
import json
from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator

from app.core.runtime import RuntimePaths
from app.models.domain import Model, utcnow
from executors.playwright.browser import AveryBrowserSession
from integrations.ascend.models import AscendError

NAV_MARKERS = ('Dashboard', 'Loads', 'Customers', 'Carriers', 'Locations', 'Reporting', 'Accounting', 'Settings')


class SessionDiagnostic(Model):
    current_path: str
    page_title: str
    authenticated_nav_markers: list[str]
    login_form_present: bool
    session_authenticated: bool


class OwnerAttestedIdentity(Model):
    """Customer Zero exception, never a provider account identifier."""
    tenant_identity_source: Literal['OWNER_ATTESTED'] = 'OWNER_ATTESTED'
    tenant_identity: Literal['Booking Logistics'] = 'Booking Logistics'
    origin: Literal['https://ascendtms.com'] = 'https://ascendtms.com'
    profile: Literal[r'C:\FreightDeskRuntime\Browser\booking-logistics\ascend'] = r'C:\FreightDeskRuntime\Browser\booking-logistics\ascend'
    load_number: Literal['1752'] = '1752'
    owner_authorized: Literal[True]


def authenticated_session(path: str, markers: list[str], login_present: bool) -> bool:
    # An absent login form or a branded title alone cannot establish authentication.
    found = set(markers) & set(NAV_MARKERS)
    return (path.lower().rstrip('/') != '/login.html' and not login_present and
            {'Dashboard', 'Loads'} <= found and len(found) >= 4)


async def observe_session(page, config: 'IdentityConfig') -> SessionDiagnostic:
    """Only approved control names/booleans leave the DOM; no body or form values."""
    current = urlsplit(page.url)
    if f'{current.scheme}://{current.netloc}' != config.origin:
        raise AscendError('session_origin_changed')
    frame_markers = []
    login_present = False
    for frame in page.frames:
        u = urlsplit(frame.url)
        if f'{u.scheme}://{u.netloc}' != config.origin:
            continue
        result = await frame.evaluate('''(approved) => {
            const visible = e => !!(e.getClientRects().length) &&
                getComputedStyle(e).visibility !== 'hidden';
            const controls = [...document.querySelectorAll('a,button,[role="link"],[role="menuitem"]')];
            const markers = approved.filter(name => controls.some(e => visible(e) &&
                (e.getAttribute('aria-label') || e.textContent || '').trim() === name));
            const login = [...document.querySelectorAll('input[type="password"],form')].some(e =>
                visible(e) && (e.matches('input[type="password"]') ||
                /(?:login|sign.?in)/i.test(e.getAttribute('action') || '') ||
                !!e.querySelector('input[autocomplete="username"],input[autocomplete="current-password"]')));
            return {markers, login};
        }''', list(NAV_MARKERS))
        frame_markers.append(result['markers'])
        login_present |= result['login'] or u.path.lower().rstrip('/') == '/login.html'
    # Require the complete navigation evidence in one frame, not stitched across unrelated frames.
    markers = sorted(set(m for found in frame_markers for m in found))
    authenticated = any(authenticated_session(current.path, found, login_present) for found in frame_markers)
    title = await page.title()
    # Page titles may contain customer data. Keep known application branding only.
    safe_title = title if title in {'AscendTMS', 'Dashboard', 'Loads', 'Dashboard - AscendTMS',
                                   'Loads - AscendTMS'} else '[redacted unapproved title]'
    safe_path = current.path if current.path in {'', '/', '/loads', '/login.html'} else '[unapproved path]'
    return SessionDiagnostic(current_path=safe_path or '/', page_title=safe_title,
        authenticated_nav_markers=markers, login_form_present=login_present,
        session_authenticated=authenticated)


class IdentityConfig(Model):
    origin: str
    expected_company: str = 'BOOKING LOGISTICS LLC'
    expected_user: str = 'Hello Manuel'

    @field_validator('origin')
    @classmethod
    def strict_origin(cls, value):
        u = urlsplit(value)
        if (u.scheme != 'https' or not u.hostname or u.username or u.password or
                u.query or u.fragment or u.path not in {'','/'} or u.port is not None or
                u.netloc != u.hostname or any(c.isspace() for c in value)):
            raise ValueError('https_hostname_origin_only_required')
        return 'https://'+u.hostname


async def observe_identity(page, config):
    """Inspect exact owner-supplied identity text in same-origin frames, without reading load fields."""
    current = urlsplit(page.url)
    if f'{current.scheme}://{current.netloc}' != config.origin:
        raise AscendError('identity_probe_origin_changed')
    results = []
    foreign_origins = set()
    for frame in page.frames:
        u = urlsplit(frame.url)
        origin = f'{u.scheme}://{u.netloc}'
        if origin != config.origin:
            if u.scheme in {'http','https'}:
                foreign_origins.add(origin)
            continue
        # Never extract body text, form values, cookies, HTML or raw unrelated account/load content.
        company = frame.get_by_text(config.expected_company, exact=False)
        user = frame.get_by_text(config.expected_user, exact=False)
        headings = frame.get_by_role('heading', name='Dashboard', exact=True)
        company_visible = await company.count() == 1 and await company.is_visible()
        user_visible = await user.count() == 1 and await user.is_visible()
        dashboard_visible = await headings.count() == 1 and await headings.is_visible()
        results.append({'same_origin':True, 'company_visible':company_visible,
            'user_visible':user_visible, 'dashboard_visible':dashboard_visible})
    verified_frames = sum(r['company_visible'] and r['user_visible'] and r['dashboard_visible'] for r in results)
    return {'identity_verified':verified_frames == 1, 'frame_indicators':results,
            'uninspected_frame_origins':sorted(foreign_origins)}


async def identity_probe(config: IdentityConfig, *, paths=None):
    paths = paths or RuntimePaths.from_environment()
    browser = AveryBrowserSession(paths)
    before = browser.persistence_status()
    report = {'observed_at':utcnow().isoformat(), 'provider':'AscendTMS', 'actor':'FreightDesk/Avery',
        'session_class':'Avery operational browser session', 'executor':'local Python Playwright',
        'channel':browser.channel, 'persistent_profile':str(browser.profile),
        'origin':config.origin, 'origin_basis':'owner-provided post-login origin and dashboard screenshot',
        'persistence_before_launch':before, 'identity_verified':False, 'load_read':False,
        'operational_writes':False, 'canonical_mutation':False, 'computer_use_used':False,
        'incognito_context_created':False, 'cookie_import_or_export':False}
    target = paths.path('Data','booking-logistics','ascend','identity-only-result.json')
    try:
        context = await browser.launch(owner_authorized=True, require_existing=True)
        await browser.readonly_network(config.origin)
        page = context.pages[0]
        await page.goto(config.origin+'/', wait_until='load', timeout=20000)
        report.update(await observe_identity(page, config))
        report['status'] = 'IDENTITY_VERIFIED' if report['identity_verified'] else 'STOPPED_IDENTITY_NOT_ESTABLISHED'
    except Exception:
        report['status'] = 'STOPPED_LOCAL_IDENTITY_PROBE_FAILED'
    finally:
        await browser.close()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
