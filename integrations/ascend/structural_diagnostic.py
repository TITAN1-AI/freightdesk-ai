"""Bounded DOM-only session diagnostic; never consumes a load grant or opens a load."""
import asyncio
import json
import time
from typing import Literal
from urllib.parse import urlsplit

from app.core.runtime import RuntimePaths
from app.models.domain import Model, utcnow
from executors.playwright.browser import AveryBrowserSession
from integrations.ascend.identity import NAV_MARKERS, OwnerAttestedIdentity
from integrations.ascend.models import AscendError

ORIGIN = 'https://ascendtms.com'
ROUTES = ('dashboard', 'loads', 'customer', 'carrier', 'locations', 'accounting')

# Only scalar structural facts leave the browser. URLs and text are classified in-place.
STRUCTURE_JS = r'''({origin, labels}) => {
    const visible = e => !!e && e.getClientRects().length > 0 &&
        getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none';
    const counts = Object.fromEntries(labels.map(s => [s, 0]));
    const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const e = node.parentElement;
        if (!e || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(e.tagName) || !visible(e)) continue;
        const text = (node.textContent || '').trim();
        if (Object.hasOwn(counts, text)) counts[text]++;
    }
    const routes = {dashboard:0, loads:0, customer:0, carrier:0, locations:0, accounting:0};
    for (const e of document.querySelectorAll('a[href],area[href],[role="link"][href]')) {
        if (!visible(e)) continue;
        try {
            const u = new URL(e.getAttribute('href'), document.baseURI);
            if (u.origin !== origin || u.username || u.password) continue;
            const path = u.pathname.replace(/\/$/, '') || '/';
            if (path === '/') routes.dashboard++;
            else if (path === '/loads') routes.loads++;
            else if (/^\/customers?(?:\/|$)/i.test(path)) routes.customer++;
            else if (/^\/carriers?(?:\/|$)/i.test(path)) routes.carrier++;
            else if (/^\/locations?(?:\/|$)/i.test(path)) routes.locations++;
            else if (/^\/accounting(?:\/|$)/i.test(path)) routes.accounting++;
        } catch (_) { /* No URL or error text is returned. */ }
    }
    const login = !!document.querySelector('input[type="password"],input[autocomplete="current-password"]') ||
        [...document.forms].some(e => /(?:login|sign.?in)/i.test(e.getAttribute('action') || '') ||
            !!e.querySelector('input[autocomplete="username"]'));
    return {same_origin_document:globalThis.origin === origin,
        ready_state:document.readyState, body_child_count:document.body?.children.length || 0,
        body_text_length:document.body?.innerText.length || 0, login_form_found:login,
        navigation_marker_counts:counts, route_link_counts:routes};
}'''


class FrameStructure(Model):
    same_origin: bool
    same_origin_path: str | None
    inspected: bool = False
    ready_state: Literal['loading', 'interactive', 'complete'] | None = None
    body_child_count: int = 0
    body_text_length: int = 0
    login_form_found: bool = False
    navigation_marker_counts: dict[str, int] = {}
    route_link_counts: dict[str, int] = {}


def safe_path(url: str, origin: str) -> str | None:
    u = urlsplit(url)
    if f'{u.scheme}://{u.netloc}' != origin:
        return None
    return u.path if u.path in {'/', '/loads', '/login.html', '/customers', '/carriers',
                               '/locations', '/accounting'} else '[redacted path]'


def recommend_authenticated(final_path: str | None, frames: list[FrameStructure]) -> bool:
    if final_path in {None, '/login.html'} or not frames or any(
            not f.inspected or f.login_form_found or f.same_origin_path == '/login.html' for f in frames):
        return False
    for frame in frames:
        if not frame.same_origin or frame.ready_state not in {'interactive', 'complete'} or not frame.body_text_length:
            continue
        labels = {label for label, count in frame.navigation_marker_counts.items() if count > 0}
        routes = frame.route_link_counts
        # Independent links can reveal icon-only/inaccessible navigation. Root links alone cannot pass.
        named_nav = {'Dashboard', 'Loads'} <= labels and len(labels) >= 4
        route_nav = routes.get('loads', 0) > 0 and sum(routes.get(key, 0) > 0
                     for key in ('customer', 'carrier', 'locations', 'accounting')) >= 3
        if named_nav or route_nav:
            return True
    return False


async def structural_snapshot(page, *, origin=ORIGIN):
    final_path = safe_path(page.url, origin)
    if final_path is None:
        raise AscendError('diagnostic_origin_changed')
    frames = []
    for frame in list(page.frames):
        path = safe_path(frame.url, origin)
        result = FrameStructure(same_origin=path is not None, same_origin_path=path)
        try:
            # ALL Playwright frames are inspected, including cross-origin frames, for structural
            # booleans/counts. Only same-origin frames may supply positive authentication evidence.
            raw = await asyncio.wait_for(frame.evaluate(STRUCTURE_JS, {'origin':origin, 'labels':list(NAV_MARKERS)}), 1)
            same_origin = raw.pop('same_origin_document')
            result = FrameStructure(same_origin=same_origin, same_origin_path=path, inspected=True, **raw)
        except Exception:
            pass  # Detached/inaccessible frames remain explicit incomplete evidence; never log errors.
        frames.append(result)
    title = await page.title()
    title = title if title in {'AscendTMS', 'Dashboard', 'Loads', 'Dashboard - AscendTMS',
                              'Loads - AscendTMS'} else '[redacted title]'
    # page.frames[0] is Playwright's main frame; other frames retain their individual counts.
    main = frames[0] if frames else FrameStructure(same_origin=True, same_origin_path=final_path)
    return {'final_path':final_path, 'page_title':title, 'document_ready_state':main.ready_state,
        'top_level_body_child_count':main.body_child_count, 'body_text_length':main.body_text_length,
        'frame_count':len(frames), 'child_frame_count':max(0, len(frames)-1),
        'frames':[f.model_dump() for f in frames],
        'login_form_found':any(f.login_form_found for f in frames),
        'dashboard_marker_count':sum(f.navigation_marker_counts.get('Dashboard', 0) for f in frames),
        'authenticated_navigation_text_found':any(any(f.navigation_marker_counts.values()) for f in frames),
        'authenticated_route_link_count':sum(sum(v for k, v in f.route_link_counts.items() if k != 'dashboard')
                                             for f in frames),
        'all_frames_inspected':all(f.inspected for f in frames),
        'session_authenticated_recommended':recommend_authenticated(final_path, frames)}


async def poll_structure(page, *, origin=ORIGIN, render_seconds=15.0, interval=0.5):
    if not 0 < interval <= render_seconds <= 15:
        raise ValueError('bounded_render_interval_required')
    start = time.monotonic()
    deadline = start+render_seconds
    latest = None
    positive_samples = 0
    timed_out = False
    while time.monotonic() < deadline:
        # Always allow rendering before the first inspection; never navigate/reload inside polling.
        await asyncio.sleep(min(interval, max(0, deadline-time.monotonic())))
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            break
        try:
            latest = await asyncio.wait_for(structural_snapshot(page, origin=origin), remaining)
        except TimeoutError:
            timed_out = True
            break
        positive_samples = positive_samples+1 if latest['session_authenticated_recommended'] else 0
        if positive_samples >= 2:
            break
    if latest is None:
        raise AscendError('diagnostic_no_complete_snapshot')
    latest['render_wait_elapsed'] = round(time.monotonic()-start, 3)
    latest['snapshot_timeout'] = timed_out
    latest['session_authenticated_recommended'] &= positive_samples >= 2 and not timed_out
    return latest


async def run_structural_diagnostic(*, paths=None):
    paths = paths or RuntimePaths.from_environment()
    browser = AveryBrowserSession(paths)
    attestation = OwnerAttestedIdentity(owner_authorized=True)
    if str(browser.profile).rstrip('\\/').lower() != attestation.profile.lower() or browser.channel != 'msedge':
        raise AscendError('diagnostic_executor_profile_mismatch')
    report = {'tenant_identity':'Booking Logistics', 'tenant_identity_source':'OWNER_ATTESTED',
        'provider_tenant_identity_verified':False, 'load_validation_attempt_consumed':False,
        'load_opened':False, 'production_writes':False, 'status':'STOPPED_DIAGNOSTIC_FAILED'}
    try:
        context = await browser.launch(owner_authorized=True, require_existing=True)
        await browser.readonly_network(ORIGIN)
        page = context.pages[0]
        await page.goto(ORIGIN+'/', wait_until='domcontentloaded', timeout=20000)
        report.update(await poll_structure(page))
        report['status'] = 'STRUCTURAL_DIAGNOSTIC_COMPLETE'
    except Exception:
        report['session_authenticated_recommended'] = False
    finally:
        try:
            await browser.close()
        finally:
            stamp = utcnow().strftime('%Y%m%dT%H%M%S%fZ')
            target = paths.path('Data','booking-logistics','ascend','structural-diagnostic-'+stamp+'.json')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
