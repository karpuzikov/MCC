"""The shared stylesheet follows DESIGN.md (MCC): tokens in :root, the 11 rules, the step layout."""
import re
import unittest

from test_audio_safety import mcc


def _stylesheet_without_tokens():
    css = mcc.APP_STYLE_CSS
    return css[css.index("}", css.index(":root")) + 1:]


def _rule(selector):
    return re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", mcc.APP_STYLE_CSS).group(1)


PAGES = (mcc._webview_main_html(), mcc._webview_release_map_html())


class DesignSystemTests(unittest.TestCase):
    def test_colours_are_defined_only_in_root_tokens(self):
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)", _stylesheet_without_tokens()), [])
        for token in ("--canvas:#101010", "--primary:#2bc4d4", "--primary-soft:#6fd8e3", "--status-added:#00d992",
                      "--hairline:#3d3a39", "--canvas-soft:#1a1a1a"):
            self.assertIn(token, mcc.APP_STYLE_CSS)

    def test_every_used_variable_is_defined(self):
        css = mcc.APP_STYLE_CSS
        self.assertEqual(set(re.findall(r"var\((--[a-z0-9-]+)", css)) - set(re.findall(r"(--[a-z0-9-]+)\s*:", css)), set())

    def test_flat_look_only_the_focus_ring_casts_a_shadow(self):
        css = _stylesheet_without_tokens()
        self.assertNotRegex(css, r"gradient|text-shadow|backdrop-filter|blur\(")
        self.assertEqual(set(re.findall(r"box-shadow:([^;}]*)", css)), {"var(--focus-ring)"})

    def test_both_windows_share_one_stylesheet_and_bundled_fonts(self):
        for html in PAGES:
            self.assertEqual(html.count("<style"), 1)
            self.assertEqual(html.count("@font-face"), 4)
            self.assertNotIn("fonts.googleapis", html)

    def test_text_uses_only_the_type_scale(self):
        css = _stylesheet_without_tokens()
        self.assertNotRegex(css, r"font-size:|font-weight:|font-family:(?!var\()|font:\s*\d")
        scale = {"page-title": "700 24px/24px", "card-title": "600 16px/16px", "step-label": "600 14px/18px",
                 "tab": "600 14px/14px", "button": "600 14px/14px", "body": "400 14px/18px", "row-title": "600 14px/18px",
                 "mono-body": "400 14px/18px", "secondary": "400 12px/16px", "table-header": "600 12px/12px",
                 "mono-small": "400 12px/12px", "chip": "500 11px/11px", "marker": "500 10px/10px"}
        root = mcc.APP_STYLE_CSS[: mcc.APP_STYLE_CSS.index("}", mcc.APP_STYLE_CSS.index(":root"))]
        self.assertEqual(dict(re.findall(r"--type-([a-z-]+):(\d{3} \d+px/\d+px)", root)), scale)
        self.assertEqual(set(re.findall(r"var\(--type-([a-z-]+)\)", css)), set(scale))

    def test_spacing_uses_only_space_1_2_3(self):
        self.assertIn("--space-1:4px; --space-2:8px; --space-3:12px;", mcc.APP_STYLE_CSS)
        bad = []
        for selector, declarations in re.findall(r"([^{}]+)\{([^}]*)\}", _stylesheet_without_tokens()):
            for declaration in re.findall(r"(?:margin|padding|gap|row-gap|column-gap)[-a-z]*:[^;]+", declarations):
                value = declaration.split(":", 1)[1]
                if selector.strip() == ".btn.primary" and value.strip() == "var(--pad-primary)":
                    continue  # primary buttons: 5px, per DESIGN.md
                leftover = re.sub(r"var\(--space-[123]\)|var\(--pad-tight\)|var\(--mkbox-pad-[a-z]+\)|var\(--icon-size\)|calc|\b0\b|auto|[\d.]+(?![\d.]*px)|[-*+() ]", "", value)
                if leftover:
                    bad.append((selector.strip()[-40:], declaration))
        for html in PAGES:
            bad += re.findall(r"(?:margin|padding|gap)[-a-z]*:\s*\d+px", html[html.index("</style>"):])
        self.assertEqual(bad, [])

    def test_equal_padding_and_no_fixed_control_heights(self):
        for selector, pad in ((".btn", "var(--space-1)"), (".changeChip", "var(--space-1)"),
                              (".field,select", "var(--space-1)")):
            rule = _rule(selector)
            self.assertIn("padding:%s;" % pad, rule)
            self.assertNotRegex(rule, r"(?<![-\w])height:")
        self.assertIn("padding:var(--pad-primary)", _rule(".btn.primary"))

    def test_icon_buttons_are_never_outlined_and_icons_are_cropped(self):
        rule = _rule(".iconBtn")
        self.assertIn("border:0", rule)
        self.assertIn("padding:0", rule)
        for name, (view_box, _w, height, _cls, _shapes) in mcc.MCC_ICON_SVG.items():
            if name not in {"dots", "music", "arrow", "swap", "chevron"}:
                self.assertEqual(height, 14, name)
            self.assertNotEqual(view_box, "0 0 24 24") if name != "music" else None
        self.assertIn("vector-effect:non-scaling-stroke", mcc.APP_STYLE_CSS)

    def test_no_pills_no_ellipsis_no_close_buttons_no_emoji(self):
        self.assertNotIn("9999px", mcc.APP_STYLE_CSS)
        self.assertNotIn("ellipsis", mcc.APP_STYLE_CSS)
        for html in PAGES:
            self.assertNotRegex(html, r'id="closeBtn"|>Close<')
            self.assertNotRegex(html, "[\U0001F300-\U0001FAFF★☆⬆]")
            self.assertNotRegex(html[html.index("</style>"):], r"…|\.\.\.(?![.\w])")

    def test_step_layout_and_scan_wording(self):
        main, release_map = PAGES
        steps = ["Step 1: Select folders", "Step 2: Scan selected folders", "Step 3: Open the map"]
        self.assertEqual([main.index(x) for x in steps], sorted(main.index(x) for x in steps))
        self.assertLess(release_map.index("Step 4: Check the scan result"), release_map.index("Step 5: Save results"))
        for html in PAGES:
            self.assertNotRegex(html, r"(?<![A-Za-z])Analy[sz]")


if __name__ == "__main__":
    unittest.main()
