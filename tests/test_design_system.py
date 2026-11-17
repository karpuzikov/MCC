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
            self.assertIn("--canvas:#101010", html)

    def test_scripts_do_not_reference_the_removed_theme_styles(self):
        for html in (mcc._webview_main_html(), mcc._webview_release_map_html()):
            self.assertNotRegex(html, r'neonTheme|sbTheme|"Theme"\)|uiTheme|setTheme')

    def test_font_families_come_from_tokens(self):
        self.assertNotRegex(_stylesheet_without_tokens(), r"font-family:(?!var\()")


    def test_fonts_are_bundled_for_latin_and_cyrillic(self):
        faces = re.findall(r'@font-face\{font-family:"([^"]+)".*?unicode-range:([^;]+);', mcc.APP_FONT_FACE_CSS, re.S)
        self.assertEqual(sorted({name for name, _ in faces}), ["Inter", "JetBrains Mono"])
        self.assertEqual(len(faces), 4)
        self.assertNotIn("http", re.sub(r"data:font/woff2;base64,[A-Za-z0-9+/=]+", "", mcc.APP_FONT_FACE_CSS).replace("github.com", ""))
        self.assertIn(mcc.APP_FONT_FACE_CSS, mcc._apply_app_theme("/*APP_THEME*/"))

    def test_every_text_uses_a_design_md_type_style(self):
        css = _stylesheet_without_tokens()
        self.assertNotRegex(css, r"font-size:|font-weight:")
        root = mcc.APP_STYLE_CSS[: mcc.APP_STYLE_CSS.index("}", mcc.APP_STYLE_CSS.index(":root"))]
        defined = set(re.findall(r"--type-([a-z-]+):", root))
        used = set(re.findall(r"font:var\(--type-([a-z-]+)\)", css))
        self.assertTrue(used <= defined, used - defined)
        for name, spec in {"body-md": "400 14px/20px", "button": "600 16px/24px", "eyebrow": "600 14px/20px"}.items():
            self.assertIn("--type-%s:%s " % (name, spec), root)

    def test_control_sizes_come_from_tokens(self):
        root = mcc.APP_STYLE_CSS[: mcc.APP_STYLE_CSS.index("}", mcc.APP_STYLE_CSS.index(":root"))]
        for token in ("--control-height:44px", "--control-height-footer:48px", "--radius-md:6px", "--radius-lg:8px", "--radius-pill:9999px"):
            self.assertIn(token, root)
        for selector in (".btn,.iconBtn", ".field,.pathInput,#search,.exportPath", "select "):
            rule = re.search(r"(?m)^" + re.escape(selector) + r"[^{]*\{([^}]*)\}", mcc.APP_STYLE_CSS).group(1)
            self.assertIn("height:var(--control-height)", rule)
        self.assertNotRegex(_stylesheet_without_tokens(), r"(?<![-\w])height:\s*(?:28|32|36|40|44|48)px")

    def test_pages_use_line_icons_not_emoji(self):
        for html in (mcc._webview_main_html(), mcc._webview_release_map_html()):
            self.assertNotRegex(html, "[\U0001F300-\U0001FAFF\u2605\u2606\u2715\u2B06]")
            self.assertNotIn("{{icon:", html)


if __name__ == "__main__":
    unittest.main()
