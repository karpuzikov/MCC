"""A passing fingerprint comparison is the identity decision, without later vetoes."""
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_audio_safety import mcc, fp, ROOT


class FingerprintPolicy(unittest.TestCase):
    def test_calibrated_limit_is_rounded_up_from_actual_mastering_comparisons(self):
        fixture=json.loads((ROOT/'tests/fixtures/watch_the_throne_fingerprint_profiles.json').read_text())
        largest=max(Decimal(str(row['similarity'][0])) for row in fixture['pairs'])
        self.assertEqual(largest,Decimal('4.014241'))
        threshold=largest.quantize(Decimal('.01'),rounding=ROUND_CEILING)
        self.assertEqual(Decimal(str(mcc.FP_AUTO_SCORE)),threshold)
        self.assertEqual(Decimal(str(mcc.FP_MASTERING_SCORE)),threshold)

    def test_calibrated_limit_cannot_be_bypassed_by_mastering_or_later_checks(self):
        original=fp()
        for count,expected in [(20,True),(21,False)]:
            changed=tuple(v^(31 if i<count else 15) for i,v in enumerate(original))
            with self.subTest(score=4+count/1000):
                matched,sim=mcc.fingerprint_auto_match_values(original,200,changed,200)
                self.assertAlmostEqual(sim[0],4+count/1000)
                self.assertEqual(matched,expected)
                details=mcc._comparison_decision_details(original,200,changed,200,matched,sim)
                self.assertEqual(details['derived_final_match'],expected)
                self.assertTrue(details['decision_consistent'])
        self.assertFalse(mcc._fingerprint_profile_identity((4.020001,1,1,0,1,4,5)))

    def test_all_logged_watch_the_throne_profiles_pass_the_primary_comparison(self):
        fixture=json.loads((ROOT/'tests/fixtures/watch_the_throne_fingerprint_profiles.json').read_text())
        self.assertEqual(len(fixture['pairs']),16)
        for row in fixture['pairs']:
            with self.subTest(title=row['title']):
                # Replay actual metrics, not invented original fingerprint words.
                self.assertTrue(mcc._fingerprint_profile_identity(tuple(row['similarity']),row['local_worst'],True))
                a,b=((0,)*n for n in row['fingerprint_frames'])
                durations=row['durations']
                accepted=abs(durations[0]-durations[1])<=8
                matched,sim=mcc._fingerprint_candidate_match_values(a,durations[0],b,durations[1],tuple(row['similarity']))
                self.assertEqual(matched,accepted)
                details=mcc._comparison_decision_details(a,durations[0],b,durations[1],accepted,sim,
                    {'passed':False,'reason':'Retired secondary verifier'},True)
                self.assertEqual(details['derived_final_match'],accepted)
                self.assertTrue(details['decision_consistent'])
                self.assertFalse(details['content_gate_triggered'])
                self.assertIsNone(details['decoded_audio_verification'])

    def test_primary_match_has_no_local_pcm_or_tag_veto_in_workers_and_pipeline(self):
        original=fp(count=4000)
        changed=tuple(v^(0xffffffff if 2000<=i<2020 else 0) for i,v in enumerate(original))
        tracks=[mcc.Track(1,Path('cd.flac'),1,title='Song',duration=498,explicit='clean',fingerprint=original),
                mcc.Track(2,Path('web.flac'),1,title='Song',duration=498,explicit='explicit',fingerprint=changed)]
        with patch.object(mcc,'_fingerprint_local_identity',side_effect=AssertionError('No secondary fingerprint check')), \
             patch.object(mcc._PCMIdentityVerifier,'verify',side_effect=AssertionError('No decoded identity check')), \
             patch.object(mcc,'_compare_workers',return_value=1):
            self.assertTrue(mcc.fingerprint_auto_match(*tracks)[0])
            mcc._init_compare_worker([(t.fingerprint,t.duration) for t in tracks])
            self.assertTrue(mcc._compare_pair_worker((0,1))[2])
            self.assertTrue(mcc._compare_pair_batch_worker([(1,0,1)])[0][3])
            with tempfile.TemporaryDirectory() as td:
                log=Path(td)/'comparison.jsonl'
                mcc.merge_equivalent_tracks(tracks,comparison_log_path=log)
                records=[json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(tracks[0].group_id,tracks[1].group_id)
        pair=next(r for r in records if r['record_type']=='comparison')
        self.assertEqual(pair['decision'],'MATCH')
        self.assertTrue(pair['details']['decision_consistent'])
        self.assertTrue(pair['details']['fingerprint_identity_authoritative'])
        self.assertIsNone(pair['details']['decoded_audio_verification'])
        summary=next(r for r in records if r['record_type']=='summary')
        self.assertEqual(summary['identity_verification']['decoded_candidates'],0)

    def test_genuine_fingerprint_mismatch_stays_separate(self):
        original=fp()
        different=tuple(v^0xffffffff for v in original)
        self.assertFalse(mcc.fingerprint_auto_match_values(original,200,different,200)[0])

    def test_duration_boundary_is_inclusive(self):
        original=fp()
        self.assertTrue(mcc.fingerprint_auto_match_values(original,200,original,208)[0])
        self.assertFalse(mcc.fingerprint_auto_match_values(original,200,original,208.001)[0])

    def test_accepted_edges_are_not_rejected_again_by_grouping(self):
        original=fp()
        tracks=[mcc.Track(i,Path(str(i)+'.flac'),1,title='Song',duration=200,
                          fingerprint=tuple(v^mask for v in original))
                for i,mask in enumerate((0,15,255))]
        with patch.object(mcc,'_compare_workers',return_value=1), \
             patch.object(mcc._PCMIdentityVerifier,'verify',side_effect=AssertionError('No PCM')):
            mcc.merge_equivalent_tracks(tracks)
        self.assertEqual(len({t.group_id for t in tracks}),1)


if __name__=='__main__':
    unittest.main()
