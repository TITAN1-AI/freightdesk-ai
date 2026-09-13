"""Deterministic browser primitives; all provider semantics live in the adapter."""
from urllib.parse import urlsplit

from app.core.runtime import RuntimePaths
from integrations.ascend.models import AscendError, FieldSelector


class BrowserExecutor:
    def __init__(self, page):
        self.page = page
        self.status = 'READY'

    @property
    def url(self):
        return self.page.url

    async def navigate(self, url):
        self.status = 'READING'
        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=15000)
        except Exception:
            self.status = 'RECOVERY_REQUIRED'
            raise AscendError('browser_navigation_failed_no_retry') from None

    def locator(self, selector):
        if selector.kind == 'role':
            return self.page.get_by_role(selector.value, name=selector.name, exact=True)
        if selector.kind == 'label':
            return self.page.get_by_label(selector.value, exact=True)
        if selector.kind == 'test_id':
            return self.page.get_by_test_id(selector.value)
        return self.page.locator(selector.value)

    async def read(self, field: FieldSelector):
        try:
            for selector in field.selectors:
                locator = self.locator(selector)
                count = await locator.count()
                if count > 1:
                    raise AscendError('ambiguous_selector')
                if count == 0:
                    continue
                await locator.wait_for(state='visible', timeout=5000)
                value = await locator.input_value() if selector.read == 'input' else await locator.inner_text()
                if len(value) > 32000:
                    raise AscendError('field_size_exceeded')
                return value
            if field.optional:
                return None
            raise AscendError('required_selector_missing')
        except AscendError:
            self.status = 'DOM_REVIEW_REQUIRED'
            raise
        except Exception:
            self.status = 'RECOVERY_REQUIRED'
            raise AscendError('browser_read_failed_no_retry') from None

    async def wait_ready(self, field):
        # Required stable page anchor is waited for explicitly, never sleep-based.
        try:
            await self.locator(field.selectors[0]).wait_for(state='visible', timeout=10000)
        except Exception:
            raise AscendError('page_not_ready') from None
        await self.read(field)


class AveryBrowserSession:
    """Dedicated persistent Edge profile; lazy imports, no launch at app startup."""
    def __init__(self, paths=None):
        self.paths = paths or RuntimePaths.from_environment()
        self.context = None
        self.runtime = None

    channel = 'msedge'

    def launch_configuration(self, *, normal_application_network=False):
        """Public configuration only; never return environment/proxy/credential values."""
        return {'implementation':'chromium.launch_persistent_context', 'channel':self.channel,
            'user_data_dir':str(self.profile), 'subprofile':'Default (no profile-directory override)',
            'headless':False, 'java_script_enabled':True,
            'service_workers':'allow' if normal_application_network else 'block',
            'arguments':['--disable-background-networking', '--no-first-run'],
            'proxy':'no explicit override; inherited system configuration not inspected',
            'extensions':'Playwright default Chromium flags; no custom extension loading',
            'initial_offline':True}

    def persistence_status(self):
        base = ('Browser', 'booking-logistics', 'ascend')
        return {'profile_exists':self.profile.is_dir(),
            'preferences_present':self.paths.path(*base, 'Default', 'Preferences').is_file(),
            'cookie_database_present':self.paths.path(*base, 'Default', 'Network', 'Cookies').is_file(),
            'local_storage_present':self.paths.path(*base, 'Default', 'Local Storage').is_dir(),
            'cookie_values_read':False, 'authenticated_session_verified':False}

    @property
    def profile(self):
        return self.paths.path('Browser', 'booking-logistics', 'ascend')

    async def launch(self, *, owner_authorized: bool, require_existing: bool = False,
                     normal_application_network: bool = False):
        if owner_authorized is not True:
            raise AscendError('owner_browser_authorization_required')
        if require_existing and not self.persistence_status()['preferences_present']:
            raise AscendError('existing_ascend_profile_required_no_profile_created')
        from playwright.async_api import async_playwright
        # Browser caches, temporary downloads and crash artifacts also remain nonsynced.
        import os
        self.profile.mkdir(parents=True, exist_ok=True)
        temp = self.paths.path('Browser', 'booking-logistics', 'ascend-temp')
        temp.mkdir(parents=True, exist_ok=True)
        self.runtime = await async_playwright().start()
        try:
            self.context = await self.runtime.chromium.launch_persistent_context(
                str(self.profile), channel=self.channel, headless=False, accept_downloads=False,
                downloads_path=str(temp), env={**os.environ, 'TEMP':str(temp), 'TMP':str(temp)},
                java_script_enabled=True, service_workers='allow' if normal_application_network else 'block', offline=True,
                args=['--disable-background-networking', '--no-first-run'])
            # Never restore an old tab online before the read network boundary is installed.
            old_pages = list(self.context.pages)
            await self.context.new_page()
            for page in old_pages:
                await page.close()
            return self.context
        except Exception:
            await self.close()
            raise AscendError('browser_launch_failed_close_other_avery_session') from None

    async def readonly_network(self, origin):
        async def route(request_route):
            request = request_route.request
            parsed = urlsplit(request.url)
            actual = f'{parsed.scheme}://{parsed.netloc}'
            if request.method not in {'GET', 'HEAD'} or actual != origin:
                await request_route.abort()
            else:
                await request_route.continue_()
        await self.context.route('**/*', route)
        # Read-only phase does not permit websocket outbound traffic.
        async def block_socket(socket):
            await socket.close()
        await self.context.route_web_socket('**/*', block_socket)
        await self.context.set_offline(False)

    async def close(self):
        if self.context:
            await self.context.close()
            self.context = None
        if self.runtime:
            await self.runtime.stop()
            self.runtime = None
