"""Browser integration for the same-window Release Map bridge and actions."""
import json
import unittest

from test_audio_safety import mcc
from test_layout import map_fixture

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, "Playwright unavailable")
class EmbeddedMapBridge(unittest.TestCase):
    def test_iframe_calls_parent_bridge_and_renders_real_map(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            fixture = json.dumps(map_fixture(), ensure_ascii=False)
            mock = (
                "window.__mapCalls=[];"
                "window.__mapState=" + fixture + ";"
                "window.pywebview={api:{"
                "mapCall:(name,args)=>{window.__mapCalls.push(name);"
                "if(name==='getState')return JSON.stringify(window.__mapState);"
                "if(name==='getOrganizer')return JSON.stringify({format:'ALAC'});"
                "return JSON.stringify(window.__mapState);},"
                "getState:()=>JSON.stringify({folders:[],status:'Ready',activity:[],"
                "ioWorkers:'auto',uiSizePercent:100}),"
                "getOrganizer:()=>JSON.stringify({format:'ALAC'})"
                "}};"
            )
            page.add_init_script(mock)
            html = mcc._webview_main_html()
            page.route("http://mcc.test/**", lambda route: route.fulfill(
                status=200, content_type="text/html; charset=utf-8", body=html))
            page.goto("http://mcc.test/app")
            page.evaluate("(html) => showMapInWindow(html)", mcc._webview_release_map_html())
            frame = page.frame_locator("#mapFrame")
            frame.locator("#fullViewBtn").click(timeout=15000)
            frame.locator(".releaseRow").first.wait_for(timeout=15000)
            self.assertGreater(frame.locator(".releaseRow").count(), 5)
            self.assertIn("getState", page.evaluate("window.__mapCalls"))
            self.assertTrue(page.locator("#mapShell").is_visible())
            self.assertEqual(len(page.context.pages), 1)
            self.assertEqual(errors, [])
            browser.close()
