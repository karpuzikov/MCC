"""Every Python method the main window page calls is exposed to it."""
import re
import unittest

from test_audio_safety import mcc, SOURCE

SOURCE_TEXT = SOURCE.read_text(encoding="utf-8")


class MainBridgeExposed(unittest.TestCase):
    def test_every_called_method_is_exposed(self):
        page = mcc._webview_main_html()
        called = set(re.findall(r"\bbridge\.(\w+)\(", page)) - {"stateChanged", "eventRaised"}
        exposed_block = SOURCE_TEXT[SOURCE_TEXT.index("    bridge = MainBridge()"):]
        exposed_block = exposed_block[:exposed_block.index("    def _closed():")]
        exposed = set(re.findall(r'^\s+"(\w+)",$', exposed_block, re.M))
        self.assertEqual(called - exposed, set())


if __name__ == "__main__":
    unittest.main()
