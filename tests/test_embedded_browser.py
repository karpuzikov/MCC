"""Chromium smoke test: embedded map and destination stay in one native view."""
import unittest

from test_audio_safety import mcc

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, "Playwright unavailable")
class EmbeddedMapSmoke(unittest.TestCase):
    def test_embedded_map_and_visible_copy_destination(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            main = mcc._webview_main_html()
            map_html = mcc._webview_release_map_html()
            page.route("http://mcc.test/**", lambda route: route.fulfill(
                status=200, content_type="text/html; charset=utf-8", body=main))
            page.goto("http://mcc.test/app")
            page.evaluate("(html) => showMapInWindow(html)", map_html)
            frame = page.frame_locator("#mapFrame")
            frame.locator("#title").wait_for()
            self.assertEqual(frame.locator("#title").inner_text(), "Release Map")
            self.assertTrue(page.locator("#mapShell").is_visible())
            self.assertEqual(len(page.context.pages), 1)
            page.evaluate("""() => {
                state={running:true,status:"Writing to C:\\\\Music\\\\Output\\\\Example",copyDestination:"C:\\\\Music\\\\Output"};
                updateCopyBar();
            }""")
            self.assertTrue(page.locator("#copyOpen").is_visible())
            self.assertTrue(page.locator("#copyOpen").is_enabled())
            self.assertIn("Example", page.locator("#copyPath").inner_text())
            self.assertTrue(page.locator("#mapShell").is_visible())
            # The map must remain visible after copying starts.
            self.assertEqual(frame.locator("#title").inner_text(), "Release Map")
            browser.close()
            # Absence of the desktop bridge is expected in this static mock.
            unexpected = [err for err in errors if "Desktop bridge" not in err]
            self.assertEqual(unexpected, [])
