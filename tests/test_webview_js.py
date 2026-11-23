"""Check that both embedded browser scripts are parseable by Node/V8."""
import re
import shutil
import subprocess
import unittest
from test_audio_safety import mcc

NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js unavailable")
class WebviewJavaScript(unittest.TestCase):
    def test_valid_browser_scripts(self):
        for name, html in (
            ("main", mcc._webview_main_html()),
            ("map", mcc._webview_release_map_html()),
        ):
            with self.subTest(view=name):
                scripts = re.findall(
                    r'<script(?:\s+type="module")?>(.*?)</script>',
                    html, re.S,
                )
                self.assertEqual(len(scripts), 1)
                command = [NODE, "--check"]
                if name == "map":
                    command += ["--input-type=module"]
                proc = subprocess.run(
                    command, input=scripts[0], encoding="utf-8",
                    capture_output=True, check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
