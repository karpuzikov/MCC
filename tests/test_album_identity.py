"""Album identity regressions; logged metrics are evidence, not original audio."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from test_audio_safety import mcc, fp


# Actual aligned metrics in the supplied 0.5.44 log. No fingerprint words or
# media were available for these rows; separate generated-vector tests exercise
# the real local-window calculation and end-to-end grouping.
TARGET_PROFILES = {
    'College Dropout': (.383459, 1, 1, 0, 1, 0, 1, .55),
    'Late Registration Bring Me Down': (1.472257, 1, 1, 0, .997478, 1, 3, 1.875),
    'Graduation Good Life': (2.035152, .998788, 1, 0, .981818, 2, 4, 5.175),
    'Graduation Barry Bonds': (2.122775, 1, 1, 0, .986495, 2, 4, 2.7),
    'MBDTF Lost In The World': (.646514, 1, 1, 1, 1, 0, 2, .925),
    '808s Love Lockdown EP/WEB': (.257751, 1, .999537, -1, 1, 0, 1, .525),
}


class AlbumIdentity(unittest.TestCase):
    def test_consistent_mastering_profiles_are_not_rejected_by_carbon_cutoff(self):
        for title, profile in TARGET_PROFILES.items():
            with self.subTest(title=title):
                self.assertTrue(mcc._definitive_acoustic_identity(profile[:7]))
                self.assertTrue(mcc._fingerprint_profile_identity(profile[:7], profile[7]))

    def test_calibrated_profiles_use_the_primary_limit_without_secondary_vetoes(self):
        profiles = [
            ('Wolves', (.293289,.9971,1,0,.983430,0,0), 5.65,True),
            ('Touch The Sky instrumental', (6.364501,.918119,.999472,-1,.413101,6,10),10.975,False),
            ('CARNIVAL instrumental', (3.386471,.938978,1,0,.796594,3,9),15.425,True),
            ('Jail alternate', (4.801263,.845474,1,0,.673263,3,12),13.8,False),
            ('I Love It edit', (1.486166,.984190,1,0,.946640,1,4),6.125,True),
        ]
        for title, sim, worst,expected in profiles:
            with self.subTest(title=title):
                self.assertEqual(mcc._fingerprint_profile_identity(sim,worst),expected)
        forever=(1.911344,1,1,-3,.980454,2,4)
        self.assertTrue(mcc._fingerprint_profile_identity(forever,3.35,advisory_conflict=True))

    def test_uniform_mastering_and_small_local_variation_share_a_group(self):
        original = fp()
        mastered = tuple(value ^ (7 if 200 <= i < 240 else 3)
                         for i, value in enumerate(original))
        self.assertTrue(mcc.fingerprint_auto_match_values(original, 200, mastered, 200.1)[0])

    def test_localized_section_does_not_veto_a_passing_primary_comparison(self):
        original = fp(count=4000)
        changed = tuple(value ^ (63 if 2000 <= i < 2040 else 0)
                        for i, value in enumerate(original))
        self.assertTrue(mcc.fingerprint_auto_match_values(original, 498, changed, 498)[0])

    def test_love_lockdown_three_copy_triangle_keeps_all_equivalent(self):
        original = fp()
        variants = [original, tuple(v ^ (1 if i % 4 == 0 else 0) for i,v in enumerate(original)),
                    tuple(v ^ (1 if i % 4 == 0 or i == 999 else 0) for i,v in enumerate(original))]
        tracks = [mcc.Track(i, Path(f'copy-{i}.flac'), 1, title='Love Lockdown',
                           duration=270+i*.2, fingerprint=value)
                  for i,value in enumerate(variants)]
        with patch.object(mcc, '_compare_workers', return_value=1), \
             patch.object(mcc._PCMIdentityVerifier, 'verify', side_effect=AssertionError('consistent fingerprints need no PCM veto')):
            mcc.merge_equivalent_tracks(tracks)
        self.assertEqual(len({track.group_id for track in tracks}), 1)

    def test_clean_explicit_labels_do_not_require_secondary_audio_confirmation(self):
        original = fp()
        clean = mcc.Track(1, Path('clean.flac'), 1, title='Forever', explicit='clean',
                          duration=200, fingerprint=original)
        explicit = mcc.Track(2, Path('explicit.flac'), 1, title='Forever', explicit='explicit',
                             duration=200, fingerprint=tuple(v ^ 3 for v in original))
        with patch.object(mcc, '_compare_workers', return_value=1), \
             patch.object(mcc._PCMIdentityVerifier, 'verify', side_effect=AssertionError('No secondary identity check')):
            mcc.merge_equivalent_tracks([clean, explicit])
        self.assertEqual(clean.group_id, explicit.group_id)

    def test_all_passing_fingerprint_edges_have_equal_authority(self):
        original=fp()
        tracks=[mcc.Track(i,Path(f'{i}.flac'),1,title='Song',duration=duration,
                          fingerprint=tuple(value^mask for value in original))
                for i,mask,duration in ((0,0,200.6),(1,1,200.4),(2,15,200.3))]
        with patch.object(mcc,'_compare_workers',return_value=1), \
             patch.object(mcc._PCMIdentityVerifier,'verify',side_effect=AssertionError('No secondary identity check')):
            mcc.merge_equivalent_tracks(tracks)
        self.assertEqual(tracks[0].group_id,tracks[1].group_id)
        self.assertEqual(tracks[0].group_id,tracks[2].group_id)

    def test_verified_silent_padding_normalizes_group_duration_and_log(self):
        original = fp()
        tracks = [mcc.Track(1,Path('short.flac'),1,title='Gone',duration=200,fingerprint=original),
                  mcc.Track(2,Path('long.flac'),1,title='Gone',duration=230,
                            fingerprint=original+(0,)*237)]
        verdict={'passed':True,'method':'decoded-boundary-silence-v1','reason':'all extra samples verified silent',
                 'effective_durations_seconds':[200.0,200.0],'padding_seconds':[0.0,30.0]}
        with tempfile.TemporaryDirectory() as td:
            log=Path(td)/'padding.jsonl'
            with patch.object(mcc,'_compare_workers',return_value=1), \
                 patch.object(mcc._PCMIdentityVerifier,'verify_padding',return_value=verdict,create=True):
                mcc.merge_equivalent_tracks(tracks,comparison_log_path=log)
            decisions=[json.loads(line) for line in log.read_text().splitlines()
                       if json.loads(line)['record_type']=='comparison']
        self.assertEqual(tracks[0].group_id,tracks[1].group_id)
        self.assertEqual([t.duration for t in tracks],[200,230])
        self.assertEqual(decisions[0]['decision'],'MATCH')
        self.assertEqual(decisions[0]['details']['raw_duration_difference_seconds'],30)
        self.assertEqual(decisions[0]['details']['duration_difference_seconds'],0)
        self.assertTrue(decisions[0]['details']['decoded_padding_verification']['passed'])
        self.assertTrue(decisions[0]['details']['decision_consistent'])

    def test_fingerprint_silence_hint_cannot_erase_audible_length_difference(self):
        original=fp()
        tracks=[mcc.Track(1,Path('short.flac'),1,title='Gone',duration=200,fingerprint=original),
                mcc.Track(2,Path('long.flac'),1,title='Gone',duration=230,fingerprint=original+(0,)*237)]
        with patch.object(mcc,'_compare_workers',return_value=1), \
             patch.object(mcc._PCMIdentityVerifier,'verify_padding',return_value={'passed':False,'reason':'audible extra material'},create=True):
            mcc.merge_equivalent_tracks(tracks)
        self.assertNotEqual(tracks[0].group_id,tracks[1].group_id)


if __name__ == '__main__':
    unittest.main()
