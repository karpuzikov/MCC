import runpy
import unittest
from pathlib import Path

app = runpy.run_path(str(next(Path(__file__).resolve().parent.parent.glob("Music Collection Cleaner v*.pyw"))),
                     run_name="display_scaling_test")
zoom_factor = app["_css_zoom_factor"]


def mm_per_css_px(physical_mm, native_px, scale):
    zoom, known = zoom_factor(physical_mm, native_px, scale, 100)
    assert known
    return physical_mm / native_px * scale * zoom


class DisplayScalingTests(unittest.TestCase):
    def test_42_inch_4k_and_15_inch_4k_show_the_same_physical_size(self):
        desk = mm_per_css_px(930, 3840, 1.0)
        laptop = mm_per_css_px(345, 3840, 2.5)
        self.assertAlmostEqual(desk / laptop, 1.0, delta=0.01)
        self.assertAlmostEqual(desk, 0.2645, delta=0.003)

    def test_unknown_or_implausible_size_falls_back_to_ui_size(self):
        self.assertEqual(zoom_factor(None, 3840, 1.5, 120), (1.2, False))
        self.assertEqual(zoom_factor(150, 3840, 1.5, 100), (1.0, False))
        self.assertEqual(zoom_factor(3000, 3840, 1.5, 100), (1.0, False))

    def test_zoom_is_clamped_then_multiplied_by_ui_size(self):
        self.assertEqual(zoom_factor(1500, 1280, 1.0, 100)[0], 0.75)
        self.assertAlmostEqual(zoom_factor(1500, 1280, 1.0, 150)[0], 1.125)
        self.assertEqual(zoom_factor(300, 3840, 1.0, 100)[0], 2.0)


if __name__ == "__main__":
    unittest.main()
