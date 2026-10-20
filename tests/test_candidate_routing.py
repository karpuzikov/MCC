"""Candidate routing must reach comparison despite edition/censorship labels."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_audio_safety import mcc, fp


class EditionCandidateRouting(unittest.TestCase):
    def illest_tracks(self, album_slot=True):
        # Actual metadata, durations and item counts from the user's v0.5.50
        # log (SHA256 8f82f752fe746605f72b5c3532fd3eab56f10bc52a3d2b99dda646a519fbf8dc).
        # Vectors are generated, not the unavailable original fingerprints.
        short = fp(count=2589)
        mastered = tuple(value ^ (0x08400000 if i % 10 < 6 else 0)
                         for i, value in enumerate(short))
        long = (0,) * 1454 + mastered + (0,)
        return [
            mcc.Track(10, Path('13 Illest Motherfucker Alive.m4a' if album_slot else 'cd.m4a'), 13,
                      title='Illest Motherfucker Alive', artist='Jay-Z & Kanye West',
                      album='Watch the Throne (Deluxe Edition)' if album_slot else '',
                      duration=503.32, fingerprint=long),
            mcc.Track(55, Path('13 Illest Motherf***** Alive.flac' if album_slot else 'web.flac'), 13,
                      title='Illest Motherf***** Alive', artist='Kanye West;JAY-Z',
                      album='Watch The Throne (Deluxe)' if album_slot else '',
                      duration=323.260635, fingerprint=short),
        ]

    def compare(self, tracks):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / 'comparison.jsonl'
            # A random shadow sample must not conceal a missing safety route.
            with patch.object(mcc, 'FP_SHADOW_SAMPLE_SIZE', 0), \
                 patch.object(mcc, '_compare_workers', return_value=1):
                mcc.merge_equivalent_tracks(tracks, comparison_log_path=log)
            return [json.loads(line) for line in log.read_text().splitlines()]

    def test_actual_watch_the_throne_names_reach_comparison_by_album_slot(self):
        rows = self.compare(self.illest_tracks())
        pairs = [row for row in rows if row['record_type'] == 'comparison']
        self.assertEqual(len(pairs), 1, 'Illest must be compared, not silently prefiltered')
        self.assertIn('same_album_track_slot', pairs[0]['candidate']['reasons'])
        self.assertTrue(pairs[0]['details']['strict_pass'])
        # Real source audio is absent here, so this test cannot certify silence.
        self.assertEqual(pairs[0]['decision'], 'REJECT')
        self.assertIsNotNone(pairs[0]['details']['decoded_padding_verification'])

    def test_censored_title_reaches_comparison_without_an_album_or_number(self):
        rows = self.compare(self.illest_tracks(album_slot=False))
        pairs = [row for row in rows if row['record_type'] == 'comparison']
        self.assertEqual(len(pairs), 1, 'Censored spelling must route without slot metadata')
        self.assertIn('masked_title', pairs[0]['candidate']['reasons'])
        self.assertTrue(pairs[0]['details']['strict_pass'])

    def test_metadata_route_never_merges_different_audio(self):
        tracks = self.illest_tracks()
        tracks[0].duration = tracks[1].duration = 200
        tracks[0].fingerprint, tracks[1].fingerprint = fp(1), fp(2)
        rows = self.compare(tracks)
        run = next(row for row in rows if row['record_type'] == 'run')
        summary = next(row for row in rows if row['record_type'] == 'summary')
        self.assertEqual(run['candidate_routes'].get('same_album_track_slot', 0), 1)
        self.assertEqual(run['candidate_routes'].get('masked_title', 0), 1)
        self.assertEqual(summary['comparisons_evaluated_or_skipped'], 1)
        self.assertEqual(summary['counts'].get('matched', 0), 0)
        self.assertNotEqual(tracks[0].group_id, tracks[1].group_id)

    def test_fully_masked_titles_do_not_route_arbitrary_other_tracks(self):
        for titles in [('****', 'Unrelated'), ('Illest Motherf***** Alive', '****')]:
            with self.subTest(titles=titles):
                tracks = self.illest_tracks(album_slot=False)
                tracks[0].title, tracks[1].title = titles
                rows = self.compare(tracks)
                run = next(row for row in rows if row['record_type'] == 'run')
                self.assertEqual(run['candidate_routes'].get('masked_title', 0), 0)
                self.assertEqual(run['candidate_pairs'], 0)


if __name__ == '__main__':
    unittest.main()
