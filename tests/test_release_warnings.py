"""Release warnings name the real artist folder and any unreadable CUE sheet."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_audio_safety import mcc


def make_release(type_source='', scan_root='Music/AC_DC', unreadable=()):
    return SimpleNamespace(type_source=type_source, scan_root=Path(scan_root),
                           unreadable_cue_paths=[Path(p) for p in unreadable])


class ReleaseWarnings(unittest.TestCase):
    def test_compilation_warning_names_the_folder_not_the_comparison_key(self):
        warning = mcc._release_warning(make_release('majority-other-artist'))
        self.assertIn('AC_DC', warning)
        self.assertNotIn('acdc', warning)

    def test_unreadable_cue_is_named(self):
        warning = mcc._release_warning(make_release(unreadable=['X/disc.cue']))
        self.assertIn('disc.cue', warning)

    def test_clean_release_has_no_warning(self):
        self.assertEqual(mcc._release_warning(make_release()), '')


if __name__ == '__main__':
    unittest.main()
