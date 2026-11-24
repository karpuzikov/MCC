import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


from test_audio_safety import mcc as app


class ScanCacheTests(unittest.TestCase):
    def setUp(self):
        tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.library = Path(tmp).resolve() / 'music'
        self.cache_path = Path(tmp) / 'cache' / 'scan.json'
        self.one = self.library / 'One'
        self.two = self.library / 'Two'
        self.one.mkdir(parents=True)
        self.two.mkdir()
        self.first = self.one / '01.flac'
        self.second = self.one / '02.flac'
        self.third = self.two / '01.flac'
        for path in (self.first, self.second, self.third):
            path.write_text('Song', encoding='utf-8')
        self.enterContext(patch.multiple(app,
            _migrate_legacy_app_data=lambda: None, _ensure_app_data_dirs=lambda: None,
            _verify_external_audio_tools=lambda *_: None, bootstrap_winget=lambda: None,
            ensure_ffmpeg=lambda: ('ffmpeg', 'ffprobe'), ensure_fpcalc=lambda: 'fpcalc',
            _load_manual_ignored_release_paths=lambda: set(),
            _load_manual_track_skip_rules=lambda: [], _load_manual_kept_release_paths=lambda: set(),
            _manual_album_group_links=lambda: {},
            ProcessPoolExecutor=app.ThreadPoolExecutor, _compare_workers=lambda: 1))
        self.probe = self.enterContext(patch.object(app, 'probe_track', side_effect=self.fake_probe))
        self.decode = self.enterContext(patch.object(app, '_verify_audio_file', return_value=''))
        self.fingerprint = self.enterContext(patch.object(app, 'chromaprint_fingerprint', side_effect=self.fake_fp))
        self.compare = self.enterContext(patch.object(app, '_compare_pair_batch_worker', wraps=app._compare_pair_batch_worker))

    @staticmethod
    def fake_probe(_, track):
        track.title = track.path.read_text(encoding='utf-8')
        track.duration = 45

    @staticmethod
    def fake_fp(_, track):
        rng = random.Random(track.path.parent.name + track.path.name)
        return tuple(rng.getrandbits(32) for _ in range(250)), 45.0

    def scan(self, full=False, exclude_live=False):
        for spy in (self.probe, self.decode, self.fingerprint, self.compare):
            spy.reset_mock()
        cache = app.ScanCache(full_rescan=full, path=self.cache_path)
        releases, tracks = app.prepare_analysis(None, self.library, lambda *_: None, 1, scan_cache=cache)
        result = app.analyze_prepared(releases, tracks, True, lambda *_: None, io_workers=1,
                                      pattern_categories={}, scan_cache=cache, exclude_live=exclude_live)
        cache.save()
        counts = tuple(spy.call_count for spy in (self.probe, self.decode, self.fingerprint, self.compare))
        return counts, [(t.path, t.title, t.group_id) for t in result[1]]

    def test_unchanged_reuses_raw_acoustic_comparisons_and_full_scan_bypasses(self):
        cold, first = self.scan()
        warm, second = self.scan()
        full, third = self.scan(full=True)
        self.assertEqual((3, 3, 3, 1), cold)
        self.assertEqual((0, 0, 0, 0), warm)
        self.assertEqual(cold, full)
        self.assertEqual(first, second)
        self.assertEqual(first, third)

    def test_edit_replacement_addition_and_deletion_invalidate_all_release_members(self):
        self.scan()
        before = self.first.stat()
        self.first.write_text('Edit', encoding='utf-8')
        os.utime(self.first, ns=(before.st_atime_ns, before.st_mtime_ns))
        counts, tracks = self.scan()
        self.assertEqual((2, 2, 2), counts[:3])
        self.assertIn('Edit', [title for _, title, _ in tracks])
        same_name_replacement = self.one / 'temp'
        same_name_replacement.write_text('Swap', encoding='utf-8')
        os.utime(same_name_replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
        os.replace(same_name_replacement, self.first)
        counts, tracks = self.scan()
        self.assertEqual((2, 2, 2), counts[:3])
        self.assertIn('Swap', [title for _, title, _ in tracks])
        added = self.one / '03.flac'
        added.write_text('More', encoding='utf-8')
        self.assertEqual((3, 3, 3), self.scan()[0][:3])
        added.unlink()
        self.assertEqual((2, 2, 2), self.scan()[0][:3])

    def test_skip_policies_before_fingerprinting_with_independent_switches(self):
        self.first.write_text('Song (Radio Remix)', encoding='utf-8')
        self.second.write_text('Song (Live)', encoding='utf-8')
        cache = app.ScanCache(full_rescan=True, path=self.cache_path)
        releases, tracks = app.prepare_analysis(None, self.library, lambda *_: None, 1, scan_cache=cache)
        app.analyze_prepared(releases, tracks, True, lambda *_: None, exclude_remixes=True,
                             exclude_live=False, io_workers=1, pattern_categories={}, scan_cache=cache)
        decoded = {item.args[1] for item in self.decode.call_args_list}
        fingerprinted = {item.args[1].path for item in self.fingerprint.call_args_list}
        self.assertEqual(decoded, {self.second, self.third})
        self.assertEqual(fingerprinted, {self.second, self.third})
        self.assertLess(next(t for t in tracks if t.path == self.first).group_id, 0)

    def test_preexisting_fingerprint_is_not_matched_when_release_becomes_blocked(self):
        self.scan()
        with patch.object(app, '_load_manual_ignored_release_paths',
                          return_value={app._manual_album_group_path_key(self.one)}):
            counts, tracks = self.scan()
        self.assertEqual((0, 0, 0, 0), counts)
        self.assertEqual([-1, -1], [group for path, _, group in tracks if path.parent == self.one])


    def test_saved_instance_skip_excludes_audio_before_decode_and_fingerprint(self):
        self.first.write_text("Never Gonna Come Back Down (Scott Humpries Radio Edit)", encoding="utf-8")
        self.second.write_text("Never Gonna Come Back Down (Rock Edit)", encoding="utf-8")
        cache = app.ScanCache(full_rescan=True, path=self.cache_path)
        releases, tracks = app.prepare_analysis(None, self.library, lambda *_: None, 1, scan_cache=cache)
        skipped = next(t for t in tracks if t.path == self.first)
        rule = {"id": "fixture-skip", "instance_keys": [app._track_instance_key(skipped)], "fingerprint_evidence": []}
        with patch.object(app, "_load_manual_track_skip_rules", return_value=[rule]):
            app.analyze_prepared(releases, tracks, True, lambda *_: None, exclude_remixes=False,
                                 exclude_live=False, io_workers=1, pattern_categories={}, scan_cache=cache)
        self.assertTrue(skipped.exclude_from_coverage)
        self.assertFalse(skipped.fingerprint)
        self.assertLess(skipped.group_id, 0)
        self.assertNotIn(self.first, {item.args[1] for item in self.decode.call_args_list})
        self.assertNotIn(self.first, {item.args[1].path for item in self.fingerprint.call_args_list})


if __name__ == '__main__':
    unittest.main()
