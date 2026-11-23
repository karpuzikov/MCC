"""Regressions for MCC v0.5.174 incremental scan and unified map."""
import ast
import json
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

    def test_two_remix_choices_replan_3402_tracks_without_audio_work(self):
        source = Path(mcc.__file__).read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        launcher = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "launch_webview_release_map")
        bridge_class = next(node for node in launcher.body
                            if isinstance(node, ast.ClassDef)
                            and node.name == "ReleaseMapBridge")
        tracks = [
            mcc.Track(1, Path("library") / f"{i:04d}.flac", i + 1,
                      title=f"Recording {i}", artist="BT", duration=180.0,
                      fingerprint=(10, 20, 30), group_id=i)
            for i in range(3402)
        ]
        release = mcc.Release(1, "recycle", Path("library"), "Test",
                              release_type="album", tracks=tracks)
        snapshots = [{"release_id": 1, "name": "Test", "action": "ADD",
                      "audit_issues": [], "tracklist": []}]
        session = dict(
            snapshots=snapshots, releases=[release], tracks=tracks,
            groups={i: [i] for i in range(len(tracks))}, selected={1},
            reviews=[], decisions=[mcc.ReleaseDecision(1, "ADD", "Test")],
            allow_apply=True, initial_plan_counts=dict(releases=1, tracks=3402),
        )
        categories = {}
        def save_categories(updated):
            categories.clear()
            categories.update(updated)
        namespace = dict(vars(mcc), session=session)
        exec(compile(ast.Module(body=[bridge_class], type_ignores=[]),
                     str(mcc.__file__), "exec"), namespace)
        with tempfile.TemporaryDirectory() as td, \
             patch.object(mcc, "_load_app_settings", return_value={}), \
             patch.object(mcc, "_load_personal_keep_rules", return_value=[]), \
             patch.object(mcc, "_load_pattern_categories", side_effect=lambda: dict(categories)), \
             patch.object(mcc, "_save_pattern_categories", side_effect=save_categories), \
             patch.object(mcc, "_release_map_state_for_ui", return_value={"nodes": []}), \
             patch.object(mcc, "_load_manual_kept_release_paths", return_value=set()), \
             patch.object(mcc, "_load_manual_ignored_release_paths", return_value=set()), \
             patch.object(mcc, "verify_audio_integrity", side_effect=AssertionError("Integrity must not run")), \
             patch.object(mcc, "chromaprint_fingerprint", side_effect=AssertionError("Fingerprint must not run")), \
             patch.object(mcc, "merge_equivalent_tracks", side_effect=AssertionError("Pair comparison must not run")), \
             patch.object(mcc, "optimize_collection", return_value={1}) as optimization, \
             patch.object(mcc, "build_release_decisions", return_value=session["decisions"]), \
             patch.object(mcc, "build_decision_snapshot", return_value=snapshots), \
             patch.object(mcc, "_save_manual_ignored_release_paths"), \
             patch.object(mcc, "_save_manual_kept_release_paths"), \
             patch.object(mcc, "_save_decision_snapshot"), \
             patch.object(mcc, "_write_reanalysis_audit", return_value=Path(td) / "audit.json"):
            # The nested bridge class was extracted with its own module globals.
            # Bind patched dependencies into those globals, too.
            for name in (
                "_load_app_settings", "_load_personal_keep_rules",
                "_load_pattern_categories", "_save_pattern_categories",
                "_release_map_state_for_ui", "_load_manual_kept_release_paths",
                "_load_manual_ignored_release_paths", "verify_audio_integrity",
                "chromaprint_fingerprint", "merge_equivalent_tracks",
                "optimize_collection", "build_release_decisions",
                "build_decision_snapshot", "_save_manual_ignored_release_paths",
                "_save_manual_kept_release_paths", "_save_decision_snapshot",
                "_write_reanalysis_audit",
            ):
                namespace[name] = getattr(mcc, name)
            bridge = namespace["ReleaseMapBridge"]()
            for index in (4, 9):
                event = json.loads(bridge.markTrackPattern(index, "remix"))
                self.assertEqual(event["kind"], "patternToggle")
            self.assertTrue(bridge.dirty)
            bridge.reanalyze()
            self.assertEqual(optimization.call_count, 1)
            self.assertEqual(sum(track.exclude_from_coverage for track in tracks), 2)
            self.assertFalse(bridge.dirty)
            # Both saved classifications must be reversible in the same menu.
            for index in (4, 9):
                bridge.markTrackPattern(index, "remix")
            bridge.reanalyze()
            self.assertEqual(optimization.call_count, 2)
            self.assertEqual(sum(track.exclude_from_coverage for track in tracks), 0)

    def test_process_scenes_are_non_generic_for_safety_stages(self):
        html = mcc._webview_main_html()
        self.assertIn('[/verifying audio file integrity|checking audio files/i,"integrity"]', html)
        self.assertIn('[/measuring silent boundary padding|measuring silence/i,"silence"]', html)
        self.assertIn('if(scene==="integrity")', html)
        self.assertIn('if(scene==="silence")', html)
        self.assertIn('if(scene==="process")', html)


if __name__ == "__main__":
    unittest.main()
