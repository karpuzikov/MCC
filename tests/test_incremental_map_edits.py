import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_audio_safety import mcc


class IncrementalMap(unittest.TestCase):
    def test_track_edit_and_warning_use_existing_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tracks, releases = [], []
            for index, name in enumerate(("First", "Second", "Third")):
                folder = root / name
                folder.mkdir()
                path = folder / (name + ".flac")
                path.write_bytes(name.encode())
                track = mcc.Track(index, path, 0, title=name, artist="BT", album=name, duration=60,
                                  fingerprint=(index+1,)*100, group_id=index, integrity_checked=True)
                tracks.append(track)
                releases.append(mcc.Release(index, "recycle", folder, name, tracks=[track],
                                            release_type="single", type_source="name"))
            selected = {0, 1, 2}
            groups = {i:[i] for i in selected}
            releases[-1].validation_issues = ["Check track numbers"]
            decisions = mcc.build_release_decisions(releases, tracks, selected, [])
            snapshots = mcc.build_decision_snapshot(releases, tracks, selected, decisions)
            session = dict(allow_apply=True, tracks=tracks, groups=groups, releases=releases, decisions=decisions,
                           selected=selected, snapshots=snapshots, recycle=root,
                           file_signatures={str(t.path):mcc._audio_file_signature(t.path) for t in tracks})
            with patch.object(mcc, "_saved_data_dir", return_value=root/"state"), \
                 patch.object(mcc, "ensure_light_ui_dependencies"), patch.object(mcc, "_ensure_webview2_runtime"), \
                 patch.object(mcc, "chromaprint_fingerprint", side_effect=AssertionError("fingerprinting")), \
                 patch.object(mcc, "verify_audio_integrity", side_effect=AssertionError("decoding")), \
                 patch.object(mcc, "merge_equivalent_tracks", side_effect=AssertionError("matching")), \
                 patch.object(mcc, "optimize_collection", wraps=mcc.optimize_collection) as optimize:
                bridge = mcc.launch_webview_release_map(session, embedded_window=object())
                self.assertTrue(json.loads(bridge.reviewRelease(2, "approve"))["dirty"])
                self.assertTrue(json.loads(bridge.reanalyze())["applyEnabled"])
                optimize.assert_not_called()
                for classification, expected in (("remix",{1,2}), ("clear",{0,1,2}), ("live",{1,2})):
                    delta=json.loads(bridge.markTrackPattern(0, classification))
                    self.assertTrue(delta["dirty"])
                    self.assertFalse(delta["requiresFreshScan"])
                    bridge.reanalyze()
                    self.assertEqual(bridge.selected,expected)
                    self.assertEqual([r.rid for r in optimize.call_args.args[0]],[0])
                    self.assertEqual([t.group_id for t in tracks],[0,1,2])
