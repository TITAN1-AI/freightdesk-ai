"""Offline dashboard rendering only; no real server, enrollment, browser profile or Ascend requests."""

import asyncio
import os
from pathlib import Path


def test_runtime_dashboard_desktop_and_mobile(tmp_path):
    async def run():
        from playwright.async_api import async_playwright

        root = Path(__file__).resolve().parents[1]
        markup = (root / "app/dashboard/index.html").read_text(encoding="utf-8")
        start = markup.index('<section class="panel" id="x1-runtime"')
        panel = markup[start:markup.index("</section>", start) + len("</section>")]
        requests = []
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(tmp_path / "fixture-profile"), channel="msedge", headless=True,
                service_workers="block", env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
            )
            try:
                async def intercept(route):
                    requests.append(route.request.url)
                    assert route.request.method == "GET"
                    if route.request.url == "http://localhost:8787/api/ascend/runtime/status":
                        await route.fulfill(json={"state": "READ_ONLY_READY", "extension": "CONNECTED",
                            "native_host": "CONNECTED", "pairing": "VALID", "session": "AUTHENTICATED",
                            "read_access": "ENABLED", "bound_tab": "ACTIVE", "view": "ACTIVE_LOADS",
                            "last_board_sync": "2026-09-11T18:00:00+00:00", "board_hash": "a" * 64,
                            "load_count": 11, "lease_expires_at": "2026-09-12T02:00:00+00:00",
                            "action": "Synthetic fixture. No Ascend request was made."})
                    else:
                        assert route.request.url == "http://localhost:8787/"
                        css = (root / "app/dashboard/styles.css").read_text(encoding="utf-8")
                        await route.fulfill(content_type="text/html", body=
                            '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                            f"<title>Offline X1 runtime fixture</title><style>{css}</style><main>{panel}</main></html>")

                await context.route("**/*", intercept)
                page = await context.new_page()
                await page.goto("http://localhost:8787/")
                await page.add_script_tag(path=str(root / "app/dashboard/ascend-runtime.js"))
                await page.locator("#x1-state").filter(has_text="READ_ONLY_READY").wait_for()
                for width in (1200, 390):
                    await page.set_viewport_size({"width": width, "height": 980})
                    assert await page.locator("body").evaluate("e=>e.scrollWidth<=innerWidth")
                    assert await page.get_by_role("button", name="Enable read-only access", exact=True).is_disabled()
                    assert await page.get_by_role("button", name="Disable read-only access", exact=True).is_enabled()
                    await page.screenshot(path=str(tmp_path / f"x1-runtime-{width}.png"), full_page=True)
                assert set(requests) <= {"http://localhost:8787/", "http://localhost:8787/api/ascend/runtime/status"}
            finally:
                await context.close()

    asyncio.run(run())
