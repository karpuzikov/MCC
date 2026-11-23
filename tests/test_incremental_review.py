"""MCC 0.5.174: classification-only replan and single-window regressions."""
from pathlib import Path
import unittest
from unittest.mock import patch

from test_audio_safety import mcc


class IncrementalReview(unittest.TestCase):
    def test_explicit_ep_beats_inherited_compilation_and_other_artist_tags(self):
        folder = "[2000] BT - Extended Movement (EP) [0 6700 39957 2 6] CD"
        kind, source = mcc.infer_release_type(
            "Extended Movement (EP)", folder, 11,
            {"compilation": "1", "albumartist": "Various Artists"},
            track_artists=[f"Other Artist {i}" for i in range(11)],
            discography_artist="BT",
        )
        self.assertEqual((kind, source), ("ep", "name"))

    def test_mixed_acoustic_family_does_not_retype_ep_as_anthology(self):
        ep = mcc.Release(1, "recycle", Path("e"), "Extended Movement", release_type="ep")
        album = mcc.Release(2, "recycle", Path("a"), "Extended Movement", release_type="anthology")
        nodes = [
            {"id": 1, "releaseType": "ep", "path": "e", "name": "Extended Movement (EP)"},
            {"id": 2, "releaseType": "anthology", "path": "a", "name": "Extended Movement"},
        ]
        with patch.object(mcc, "_album_clusters", return_value=[[ep, album]]), \
             patch.object(mcc, "_manual_album_group_links", return_value={}):
            mcc._assign_release_map_display_groups(nodes, [ep, album])
        self.assertEqual(nodes[0]["displayGroupKind"], "ep")
        self.assertEqual(nodes[1]["displayGroupKind"], "anthology")

    def test_remix_label_reuses_verified_groups_without_audio_analysis(self):
        track = mcc.Track(1, Path("control.flac"), 0, title="Control",
                          duration=240, group_id=7, fingerprint=(1, 2, 3))
        release = mcc.Release(1, "recycle", Path("release"), "Control",
                              release_type="single", type_source="tag", tracks=[track])
        groups = {7: [0]}
        with patch.object(mcc, "apply_persistent_track_skips"), \
             patch.object(mcc, "merge_equivalent_tracks", side_effect=AssertionError("repeat comparisons")), \
             patch.object(mcc, "verify_audio_integrity", side_effect=AssertionError("repeat decode")), \
             patch.object(mcc, "chromaprint_fingerprint", side_effect=AssertionError("repeat fingerprint")):
            mcc.replan_cached_classification(
                [release], [track], groups,
                exclude_remixes=True, exclude_live=True,
                pattern_categories={"title:control": {"kind": "remix", "label": "Control"}},
            )
            self.assertTrue(track.exclude_from_coverage)
            self.assertEqual(groups, {})
            self.assertEqual(track.group_id, 7)
            mcc.replan_cached_classification(
                [release], [track], groups,
                exclude_remixes=True, exclude_live=True,
                pattern_categories={"title:control": {"kind": "standard", "label": "Control"}},
            )
        self.assertFalse(track.exclude_from_coverage)
        self.assertFalse(track.is_remix)
        self.assertEqual(groups, {7: [0]})

    def test_unverified_new_inclusion_is_refused_not_silently_unique(self):
        track = mcc.Track(1, Path("not-analyzed.flac"), 0, title="Song",
                          group_id=-1, exclude_from_coverage=True)
        release = mcc.Release(1, "recycle", Path("release"), "Song",
                              release_type="single", type_source="tag", tracks=[track])
        groups = {}
        with self.assertRaisesRegex(RuntimeError, "fingerprint"):
            mcc.replan_cached_classification(
                [release], [track], groups,
                exclude_remixes=True, exclude_live=True,
                pattern_categories={"title:song": {"kind": "standard", "label": "Song"}},
            )
        self.assertTrue(track.exclude_from_coverage)
        self.assertEqual(groups, {})

    def test_cached_replan_rejects_changed_verified_media(self):
        import tempfile
        import time
        with tempfile.TemporaryDirectory() as root:
            media = Path(root) / "recording.flac"
            media.write_bytes(b"first")
            track = mcc.Track(
                1, media, 0, title="Example", group_id=2,
                fingerprint=(1, 2), integrity_checked=True,
            )
            baseline = mcc._verified_media_signatures([track])
            mcc._assert_unchanged_verified_media(baseline, [track])
            media.write_bytes(b"changed content")
            with self.assertRaisesRegex(RuntimeError, "changed after Scan"):
                mcc._assert_unchanged_verified_media(baseline, [track])

    def test_missing_verified_media_never_reuses_cached_identity(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            media = Path(root) / "recording.flac"
            media.write_bytes(b"available")
            track = mcc.Track(
                1, media, 0, title="Example", group_id=2,
                fingerprint=(1, 2), integrity_checked=True,
            )
            baseline = mcc._verified_media_signatures([track])
            media.unlink()
            with self.assertRaisesRegex(RuntimeError, "Source file inaccessible"):
                mcc._assert_unchanged_verified_media(baseline, [track])

    def test_category_menu_is_reversible_without_mark_prefix(self):
        html = mcc._webview_release_map_html()
        self.assertIn('role="menuitemcheckbox"', html)
        self.assertNotIn('>Mark ', html)
        self.assertIn('const checked=t.patternKind===kind', html)
        self.assertFalse(mcc._promote_pattern_choice("remix", "remix"))
        self.assertTrue(mcc._promote_pattern_choice("keep", "remix"))

    def test_integrity_and_padding_have_specific_visual_scenes(self):
        html = mcc._webview_main_html()
        self.assertIn('if(scene==="decode")', html)
        self.assertIn('if(scene==="silence")', html)
        self.assertIn('measuring silent boundary padding', html.lower())

    def test_release_map_is_embedded_and_copy_destination_is_accessible(self):
        html = mcc._webview_main_html()
        self.assertIn('id="mapFrame"', html)
        self.assertIn('id="copyOpen"', html)
        self.assertIn('function showMapInWindow(html)', html)
        code = Path(mcc.__file__).read_text(encoding="utf-8")
        self.assertIn("def _embedded_map_copy", code)
        self.assertIn("self.parent_main._embedded_map_copy(self.result_payload)", code)


if __name__ == "__main__":
    unittest.main()
