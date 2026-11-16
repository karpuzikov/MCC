"""The saved UI theme falls back to Neon Arcade, rejects unknown names and switches the injected CSS media."""
import unittest
from unittest.mock import patch

from test_audio_safety import mcc


class UiThemeTests(unittest.TestCase):
    def test_unknown_or_missing_theme_falls_back_to_neon(self):
        self.assertEqual(mcc._ui_theme_name({}), "neon")
        self.assertEqual(mcc._ui_theme_name({"ui_theme": "bogus"}), "neon")
        self.assertEqual(mcc._ui_theme_name({"ui_theme": "classic"}), "classic")

    def test_saving_unknown_theme_fails_fast(self):
        with self.assertRaises(ValueError):
            mcc._save_ui_theme("bogus")

    def test_classic_theme_disables_the_neon_style_element(self):
        with patch.object(mcc, "_load_app_settings", return_value={"ui_theme": "classic"}):
            html = mcc._webview_main_html()
        self.assertIn('id="neonTheme" media="not all"', html)
        self.assertIn('id="sbTheme" media="not all"', html)
        with patch.object(mcc, "_load_app_settings", return_value={"ui_theme": "sb"}):
            html = mcc._webview_main_html()
        self.assertIn('id="sbTheme" media="all"', html)
        self.assertIn('id="neonTheme" media="not all"', html)
        with patch.object(mcc, "_load_app_settings", return_value={}):
            html = mcc._webview_release_map_html()
        self.assertIn('id="neonTheme" media="all"', html)


if __name__ == "__main__":
    unittest.main()
