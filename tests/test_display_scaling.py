import runpy
import unittest
from pathlib import Path

app = runpy.run_path(str(next(Path(__file__).resolve().parent.parent.glob("Music Collection Cleaner v*.pyw"))),
                     run_name="display_scaling_test")
zoom_factor = app["_css_zoom_factor"]


def mm_per_css_px(physical_mm, native_px, scale):
    zoom, known, _mm = zoom_factor(physical_mm, native_px, scale, 100)
    assert known
    return physical_mm / native_px * scale * zoom


class DisplayScalingTests(unittest.TestCase):
    def test_42_inch_4k_at_100_percent(self):
        zoom, known, mm = zoom_factor(930, 3840, 1.0, 100)
        self.assertTrue(known)
        self.assertAlmostEqual(zoom, 1.09, delta=0.01)
        self.assertAlmostEqual(mm, 0.2422, delta=0.001)

    def test_15_inch_4k_at_250_percent(self):
        # 345 mm / 3840 px * 2.5 = 0.2246 mm per CSS px before zoom -> 0.2645 / 0.2246 = 1.18.
        zoom, known, _mm = zoom_factor(345, 3840, 2.5, 100)
        self.assertTrue(known)
        self.assertAlmostEqual(zoom, 1.18, delta=0.01)

    def test_both_displays_show_the_same_physical_size(self):
        self.assertAlmostEqual(mm_per_css_px(930, 3840, 1.0) / mm_per_css_px(345, 3840, 2.5), 1.0, delta=0.01)

    def test_fake_tv_size_falls_back_to_windows_scaling(self):
        # 160 cm on 3840 px = 61 PPI, outside 80-350.
        self.assertEqual(zoom_factor(1600, 3840, 1.0, 100), (1.0, False, None))
        self.assertEqual(zoom_factor(1600, 3840, 1.0, 120), (1.2, False, None))
        self.assertEqual(zoom_factor(None, 3840, 1.5, 100), (1.0, False, None))

    def test_zoom_is_clamped_then_multiplied_by_ui_size(self):
        self.assertEqual(zoom_factor(700, 2560, 2.0, 100)[0], 0.75)  # 93 PPI at 200%: 0.547 mm/px -> 0.48
        self.assertAlmostEqual(zoom_factor(700, 2560, 2.0, 150)[0], 1.125)
        self.assertEqual(zoom_factor(280, 3840, 1.0, 100)[0], 2.0)  # 348 PPI at 100%


if __name__ == "__main__":
    unittest.main()
