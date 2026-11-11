"""Source folder rows: migration of old settings, split by star, extra roots in scanning and the IO plan."""
from pathlib import Path
import tempfile
import unittest

from test_audio_safety import mcc


class SourceFolders(unittest.TestCase):
    def test_old_settings_become_starred_folder_one_and_folder_two(self):
        rows = mcc._load_source_folders({"existing_discography": "D:/Old", "recycle_update_folder": "D:/New"})
        self.assertEqual(rows, [{"path": "D:/Old", "star": True}, {"path": "D:/New", "star": False}])

    def test_empty_old_settings_still_show_two_rows(self):
        self.assertEqual(len(mcc._load_source_folders({})), 2)

    def test_saved_rows_win_over_old_keys(self):
        saved = {"existing_discography": "x", "recycle_update_folder": "y",
                 "source_folders_v1": [{"path": "A", "star": False}, {"path": "B", "star": True}, {"path": "C"}]}
        self.assertEqual([r["path"] for r in mcc._load_source_folders(saved)], ["A", "B", "C"])

    def test_split_by_star_skips_empty_paths(self):
        rows = [{"path": "A", "star": True}, {"path": "", "star": False},
                {"path": "B", "star": True}, {"path": "C", "star": False}]
        existing, new = mcc._split_source_folders(rows)
        self.assertEqual(existing, [Path("A"), Path("B")])
        self.assertEqual(new, [Path("C")])

    def test_non_list_input_is_safe(self):
        self.assertEqual(mcc._normalize_source_folders(None), [{"path": "", "star": False}] * 2)
        self.assertEqual(len(mcc._normalize_source_folders([1, "x", None])), 2)

    def test_extra_roots_are_part_of_the_io_plan(self):
        kinds = {"a": "ssd", "b": "ssd", "c": "hdd"}
        plan = mcc._io_worker_plan(Path("a"), Path("b"), "auto", classify=lambda p: kinds[str(p)],
                                   extra_roots=[Path("c")])
        self.assertEqual(plan, (2, "HDD"))

    def test_save_keeps_rows_when_a_caller_passes_only_old_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            old = mcc._settings_path
            mcc._settings_path = lambda: settings
            try:
                rows = [{"path": "A", "star": False}, {"path": "B", "star": True}, {"path": "C", "star": False}]
                mcc._save_app_settings("", "", source_folders=rows)
                saved = mcc._load_app_settings()
                self.assertEqual(saved["existing_discography"], "B")
                self.assertEqual(saved["recycle_update_folder"], "A")
                mcc._save_app_settings("B", "A", True)
                self.assertEqual(mcc._load_source_folders(mcc._load_app_settings()), rows)
            finally:
                mcc._settings_path = old


if __name__ == "__main__":
    unittest.main()
