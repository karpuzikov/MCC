"""The shared stylesheet uses only DESIGN.md tokens: colours live in :root, no glows or gradients, one stylesheet per page."""
import re
import unittest

from test_audio_safety import mcc


def _stylesheet_without_tokens():
    css = mcc.APP_STYLE_CSS
    return css[css.index("}", css.index(":root")) + 1:]


class DesignSystemTests(unittest.TestCase):
    def test_colours_are_defined_only_in_root_tokens(self):
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)", _stylesheet_without_tokens()), [])

    def test_every_used_variable_is_defined(self):
        css = mcc.APP_STYLE_CSS
        defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
        self.assertEqual(set(re.findall(r"var\((--[a-z0-9-]+)", css)) - defined, {"--visible-columns"})

    def test_flat_look_only_the_focus_ring_casts_a_shadow(self):
        css = _stylesheet_without_tokens()
        self.assertNotRegex(css, r"gradient|text-shadow|backdrop-filter|blur\(")
        for value in re.findall(r"box-shadow:([^;}]*)", css):
            self.assertIn(value.strip(), {"var(--focus-ring)", "var(--focus-ring-inset)"})

    def test_both_windows_share_one_stylesheet(self):
        for html in (mcc._webview_main_html(), mcc._webview_release_map_html()):
            self.assertEqual(html.count("<style"), 1)
            self.assertIn("--canvas:#0B0E11", html)

    def test_scripts_do_not_reference_the_removed_theme_styles(self):
        for html in (mcc._webview_main_html(), mcc._webview_release_map_html()):
            self.assertNotRegex(html, r'neonTheme|sbTheme|"Theme"\)|uiTheme|setTheme')

    def test_font_families_come_from_tokens(self):
        self.assertNotRegex(_stylesheet_without_tokens(), r"font-family:(?!var\()")


if __name__ == "__main__":
    unittest.main()
