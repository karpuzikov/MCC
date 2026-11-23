"""MCC v0.5.174: incremental planning, release identity and single-window UX."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_audio_safety import mcc


class MCC174Regression(unittest.TestCase):
    def test_explicit_ep_beats_anthology_and_compilation_hints(self):
        title = "Extended Movement (EP)"
        folder = "[2000] BT - Extended Movement (EP) [0 6700 39957 2 6] CD"
        for tags in ({}, {"COMPILATION": "1"}, {"RELEASETYPE": "album"}):
            with self.subTest(tags=tags):
                kind, _source = mcc.infer_release_type(
                    title, folder, 9, tags,
                    track_artists=["BT"] * 9, discography_artist="BT")
                self.assertEqual(kind, "ep")

    def test_ep_column_cannot_be_overridden_by_anthology_guess(self):
        node = {
            "id": 1, "name": "[2000] BT - Extended Movement (EP) [0 6700 39957 2 6] CD",
            "path": "D:/Music/[2000] BT - Extended Movement (EP) [0 6700 39957 2 6] CD",
            "releaseType": "anthology", "albumTitles": ["Extended Movement"],
        }
        mcc._assign_release_map_display_groups([node])
        self.assertEqual(node["releaseType"], "ep")
        self.assertEqual(node.get("displayGroupKind", "ep"), "ep")

    def _fixture(self, folder, fingerprint=(1, 2, 3)):
        path = Path(folder) / "audio.flac"
        path.write_bytes(b"representative audio bytes")
        track = mcc.Track(0, path, 0, title="Original Song", artist="BT",
                          album="Original Song", duration=180.0,
                          fingerprint=fingerprint, group_id=0 if fingerprint else -1)
        release = mcc.Release(0, "recycle", Path(folder), "Original Song",
                              tracks=[track], release_type="single", type_source="name")
        key, label = mcc._classify_track_pattern(track, "remix")
        sigs = {str(path): mcc._audio_file_signature(path)}
        return path, track, release, key, label, sigs

    def test_mark_remix_then_clear_uses_cached_identity_without_media_work(self):
        with tempfile.TemporaryDirectory() as folder:
            path, track, release, key, label, sigs = self._fixture(folder)
            groups = {0: [0]}
            blocked = {"verify_audio_integrity", "merge_equivalent_tracks", "chromaprint_fingerprint"}
            with patch.object(mcc, "verify_audio_integrity", side_effect=AssertionError("full decode")) as verify, \
                 patch.object(mcc, "merge_equivalent_tracks", side_effect=AssertionError("compare")) as compare, \
                 patch.object(mcc, "chromaprint_fingerprint", side_effect=AssertionError("fingerprint")) as fp:
                yes = mcc._reclassify_without_acoustic_work(
                    [release], [track], groups, False, False, [],
                    {key: {"kind": "remix", "label": label}}, sigs)
                self.assertTrue(yes)
                self.assertTrue(track.is_remix)
                self.assertTrue(track.exclude_from_coverage)
                self.assertEqual(groups, {})
                yes = mcc._reclassify_without_acoustic_work(
                    [release], [track], groups, False, False, [],
                    {key: {"kind": "normal", "label": label}}, sigs)
                self.assertTrue(yes)
                self.assertFalse(track.is_remix)
                self.assertFalse(track.exclude_from_coverage)
                self.assertEqual(groups, {0: [0]})
                verify.assert_not_called()
                compare.assert_not_called()
                fp.assert_not_called()

    def test_changed_file_blocks_stale_acoustic_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            path, track, release, key, label, sigs = self._fixture(folder)
            path.write_bytes(b"modified media - old fingerprints are now stale")
            groups = {0: [0]}
            self.assertFalse(mcc._reclassify_without_acoustic_work(
                [release], [track], groups, False, False, [],
                {key: {"kind": "remix", "label": label}}, sigs))
            self.assertEqual(groups, {0: [0]})

    def test_no_fingerprint_blocks_newly_wanted_track(self):
        with tempfile.TemporaryDirectory() as folder:
            path, track, release, key, label, sigs = self._fixture(folder, fingerprint=())
            track.is_remix = True
            track.exclude_from_coverage = True
            track.base_excluded_from_coverage = True
            groups = {}
            self.assertFalse(mcc._reclassify_without_acoustic_work(
                [release], [track], groups, False, False, [],
                {key: {"kind": "normal", "label": label}}, sigs))
            self.assertTrue(track.exclude_from_coverage)
            self.assertTrue(track.is_remix)

    def test_ui_only_one_window_and_mappable_copy_progress(self):
        source = Path(mcc.__file__).read_text(encoding="utf-8")
        map_html = mcc._webview_release_map_html()
        main_html = mcc._webview_main_html()
        self.assertIn('id="mapFrame"', main_html)
        self.assertIn('id="homeBtn"', main_html)
        self.assertIn('id="copyTarget"', map_html)
        self.assertIn('id="openCopyDestination"', map_html)
        self.assertIn('selected?"clear":kind', map_html)
        self.assertNotIn('>Mark Remix<', map_html)
        self.assertNotIn('>Mark Live<', map_html)
        self.assertIn('scene==="integrity"', main_html)
        self.assertIn('scene==="silence"', main_html)
        self.assertIn('on_copy=self._start_embedded_copy', source)


if __name__ == "__main__":
    unittest.main()
