"""Regressions for MCC v0.5.174 incremental scan and unified map."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_audio_safety import mcc


class IncrementalWorkflow(unittest.TestCase):
    def test_explicit_ep_title_beats_guest_artist_and_compilation_heuristics(self):
        folder = "[2000] BT - Extended Movement (EP) [0 6700 39957 2 6] CD"
        kind, source = mcc.infer_release_type(
            "Extended Movement (EP)", folder, 4,
            {"compilation": "1", "albumartist": "BT"},
            track_artists=["BT", "BT feat. somebody", "Another Artist", "Guest"],
            discography_artist="BT",
        )
        self.assertEqual(kind, "ep")
        self.assertEqual(source, "name")

    def test_labeled_ep_stays_in_ep_column_even_when_family_is_mixed(self):
        html = mcc._webview_release_map_html()
        self.assertIn('if(own==="ep"||own==="single")return own;', html)
        self.assertIn('{key:"ep",label:"EPs"}', html)
        self.assertIn('ep:"EPs"', html)

    def test_integrity_uses_cached_verified_results_for_unchanged_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            audio = directory / "01.flac"
            audio.write_bytes(b"initial")
            track = mcc.Track(1, audio, 1)
            with patch.object(mcc, "_cache_dir", return_value=directory), \
                 patch.object(mcc, "_verify_audio_file", return_value="") as verify:
                mcc.verify_audio_integrity("dummy-ffmpeg", [track], 2, lambda *_: None)
                self.assertTrue(track.integrity_checked)
                mcc.verify_audio_integrity("dummy-ffmpeg", [track], 2, lambda *_: None)
                self.assertEqual(verify.call_count, 1)
                audio.write_bytes(b"modified data of different length")
                mcc.verify_audio_integrity("dummy-ffmpeg", [track], 2, lambda *_: None)
                self.assertEqual(verify.call_count, 2)

    def test_failed_integrity_checks_are_never_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            audio = directory / "01.flac"
            audio.write_bytes(b"broken")
            good = directory / "02.flac"
            good.write_bytes(b"ok")
            tracks = [mcc.Track(1, audio, 1), mcc.Track(1, good, 2)]
            def decode(_ffmpeg, path):
                return "invalid sync code" if path.name == "01.flac" else ""
            with patch.object(mcc, "_cache_dir", return_value=directory), \
                 patch.object(mcc, "_verify_audio_file", side_effect=decode) as verify:
                for _ in range(2):
                    errors = mcc.verify_audio_integrity("dummy-ffmpeg", tracks, 2, lambda *_: None)
                    self.assertEqual(len(errors), 1)
                self.assertEqual(verify.call_count, 3)

    def test_fingerprint_binary_codec_round_trip(self):
        vectors = (0, 1, 0xFFFFFFFF, 0x80000000, 2844982)
        self.assertEqual(mcc._unpack_fingerprint(mcc._pack_fingerprint(vectors)), vectors)

    def test_media_signature_invalidates_when_cue_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio, cue = Path(tmp) / "image.flac", Path(tmp) / "disc.cue"
            audio.write_bytes(b"audio")
            cue.write_text("FILE first", encoding="utf-8")
            track = mcc.Track(1, audio, 1, virtual_from_cue=True, cue_path=cue)
            first = mcc._fingerprint_cache_key(track, "dummy-fpcalc")
            cue.write_text("FILE second and different", encoding="utf-8")
            self.assertNotEqual(first, mcc._fingerprint_cache_key(track, "dummy-fpcalc"))

    def test_category_menu_is_reversible_and_uses_one_vocabulary(self):
        html = mcc._webview_release_map_html(inline=True)
        self.assertIn('role="menuitemcheckbox"', html)
        self.assertIn('aria-checked=', html)
        self.assertNotIn(">Mark Remix<", html)
        self.assertNotIn(">Mark Live<", html)
        self.assertIn('?"Keep":"Skip"', html)
        self.assertIn('Skip recording everywhere', html)
        self.assertIn('MAP_API_PREFIX="map_"', html)

    def test_single_window_has_accessible_destination_and_progress(self):
        html = mcc._webview_release_map_html(inline=True)
        self.assertIn('id="backToScan"', html)
        self.assertIn('id="exportPath"', html)
        self.assertIn('id="openDestination"', html)
        self.assertIn('id="copyLiveStatus"', html)
        self.assertIn('id="copyLiveCount"', html)
        self.assertIn('window.__deaStateChanged', html)
        self.assertIn('window.__deaEventRaised', html)

    def test_repeated_full_scan_reuses_exact_acoustic_group_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mcc, "_cache_dir", return_value=Path(tmp)):
                first = mcc.Track(1, Path(tmp) / "song.flac", 1, title="Song",
                                  duration=180.0, fingerprint=(12, 34, 56))
                second = mcc.Track(1, first.path, 1, title="Song",
                                   duration=180.0, fingerprint=(12, 34, 56))
                def compare(tracks, *_args):
                    tracks[0].group_id = 7
                    tracks[0].comparison_index = 0
                    return {7: [0]}, [], []
                with patch.object(mcc, "merge_equivalent_tracks", side_effect=compare) as expensive:
                    self.assertEqual(mcc.merge_equivalent_tracks_cached([first])[0], {7: [0]})
                    self.assertEqual(mcc.merge_equivalent_tracks_cached([second])[0], {7: [0]})
                    self.assertEqual(expensive.call_count, 1)
                    self.assertEqual(second.group_id, 7)
                    third = mcc.Track(1, first.path, 1, title="Different title",
                                      duration=180.0, fingerprint=(12, 34, 56))
                    mcc.merge_equivalent_tracks_cached([third])
                    self.assertEqual(expensive.call_count, 2)

    def test_diagnostic_logging_bypasses_acoustic_group_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mcc, "_cache_dir", return_value=Path(tmp)):
                track = mcc.Track(1, Path(tmp) / "song.flac", 1, title="Song",
                                  duration=180.0, fingerprint=(12, 34, 56))
                with patch.object(mcc, "merge_equivalent_tracks",
                                  return_value=({0: [0]}, [], [])) as expensive:
                    mcc.merge_equivalent_tracks_cached([track])
                    mcc.merge_equivalent_tracks_cached([track], comparison_log_path=Path(tmp) / "log.jsonl")
                    self.assertEqual(expensive.call_count, 2)

    def test_acoustic_cache_changes_with_audio_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            song = Path(tmp) / "song.flac"
            song.write_bytes(b"audio one")
            track = mcc.Track(1, song, 1, title="Song", duration=100.0,
                              fingerprint=(10, 11, 12))
            baseline = mcc._acoustic_group_cache_key([track])
            track.fingerprint = (10, 11, 13)
            changed_fingerprint = mcc._acoustic_group_cache_key([track])
            self.assertNotEqual(baseline, changed_fingerprint)
            track.fingerprint = (10, 11, 12)
            song.write_bytes(b"changed longer audio")
            self.assertNotEqual(baseline, mcc._acoustic_group_cache_key([track]))

    def test_process_scenes_are_non_generic_for_safety_stages(self):
        html = mcc._webview_main_html()
        self.assertIn('[/verifying audio file integrity|checking audio files/i,"integrity"]', html)
        self.assertIn('[/measuring silent boundary padding|measuring silence/i,"silence"]', html)
        self.assertIn('if(scene==="integrity")', html)
        self.assertIn('if(scene==="silence")', html)
        self.assertIn('if(scene==="process")', html)


if __name__ == "__main__":
    unittest.main()
