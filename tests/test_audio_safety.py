"""Functional regressions for the October 20 comparison-log audit."""
import contextlib
import importlib.machinery
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('MCC_TEST_SOURCE', str(ROOT / 'Music Collection Cleaner v0.05.50.pyw')))
loader = importlib.machinery.SourceFileLoader('mcc_test_subject', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
mcc = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = mcc
loader.exec_module(mcc)


def fp(seed=42, count=1000):
    rng = random.Random(seed)
    return tuple(rng.getrandbits(32) for _ in range(count))


class AcousticSafety(unittest.TestCase):
    def test_authoritative_fingerprint_tolerates_small_unmatched_ends(self):
        original=fp()
        for extra,delta in ((1,.133333),(4,.426667),(10,1.24)):
            extended=original+fp(314,extra)
            for reverse in (False,True):
                with self.subTest(extra=extra,reverse=reverse):
                    args=(original,200,extended,200+delta)
                    if reverse:args=(args[2],args[3],args[0],args[1])
                    self.assertTrue(mcc.fingerprint_auto_match_values(*args)[0])

    def test_authoritative_fingerprint_obeys_eight_second_boundary(self):
        original=fp();extended=original+fp(314,10)
        for delta,expected in ((0,True),(7.999,True),(8,True),(8.001,False),(29.3,False)):
            with self.subTest(delta=delta):
                self.assertEqual(mcc.fingerprint_auto_match_values(original,200,extended,200+delta)[0],expected)

    def test_authoritative_fingerprint_precedes_unmatched_content_gate(self):
        original=fp(count=400);extended=original+fp(314,160)
        self.assertTrue(mcc.fingerprint_auto_match_values(original,100,extended,107)[0])

    def test_logged_808s_profiles_accept_fingerprint_authority(self):
        for frames,extra,duration,delta,score,worst in ((2102,4,262.933333,.426667,.027117,.125),
                (2063,1,258.12,.133333,.040233,.2),(1306,10,164.333333,1.24,.062787,1.1)):
            with self.subTest(score=score):
                # Synthetic vectors reproduce the logged mean/local distances;
                # the log does not contain the user's original fingerprint words.
                short=fp(count=frames);long=list(short)
                local_bits=round(worst*40);position=0
                while local_bits:
                    bits=min(5,local_bits);long[position]^=(1<<bits)-1
                    local_bits-=bits;position+=1
                remaining=round(score*frames)-round(worst*40)
                step=(frames-61)//max(1,remaining-1)
                for index in range(remaining):long[60+index*step]^=1
                long=tuple(long)+fp(314,extra)
                matched,sim=mcc.fingerprint_auto_match_values(long,duration+delta,short,duration)
                self.assertTrue(matched)
                self.assertAlmostEqual(sim[0],score,places=6)
                self.assertEqual(mcc._fingerprint_local_identity(long,short,sim)['worst_window_score'],worst)
                details=mcc._comparison_decision_details(long,duration+delta,short,duration,True,sim,
                    {'passed':False,'reason':'PCM would reject mastering or boundary difference'})
                self.assertTrue(details['identity_confirmed'])
                self.assertTrue(details['derived_final_match'])
                self.assertTrue(details['decision_consistent'])

    def test_authoritative_fingerprint_pipeline_does_not_invoke_pcm(self):
        original=fp()
        tracks=[mcc.Track(1,Path('missing-cd.flac'),1,title='Song',duration=200,
                          fingerprint=original+fp(314,4)),
                mcc.Track(2,Path('missing-web.flac'),1,title='Unrelated wrong title',duration=199.573333,
                          fingerprint=original)]
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'authority.jsonl'
            with patch.object(mcc,'_compare_workers',return_value=1), \
                 patch.object(mcc._PCMIdentityVerifier,'verify',side_effect=AssertionError('PCM must not veto authoritative fingerprints')):
                mcc.merge_equivalent_tracks(tracks,comparison_log_path=path)
            rows=[json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(tracks[0].group_id,tracks[1].group_id)
        decisions=[row for row in rows if row['record_type']=='comparison']
        self.assertEqual(len(decisions),1)
        self.assertEqual(decisions[0]['decision'],'MATCH')
        self.assertTrue(decisions[0]['details']['decision_consistent'])
        self.assertIsNone(decisions[0]['details']['decoded_audio_verification'])

    def test_primary_fingerprint_match_cannot_be_vetoed_by_a_changed_section(self):
        original = fp()
        changed = tuple(value ^ (0xffffffff if 400 <= i < 490 else 0)
                        for i, value in enumerate(original))
        match, _ = mcc.fingerprint_auto_match_values(original, 126, changed, 126)
        self.assertTrue(match)

    def test_near_perfect_mislabeled_pinocchio_still_matches(self):
        original = fp()
        changed = tuple(v ^ (1 if i % 30 == 0 else 0) for i, v in enumerate(original))
        self.assertTrue(mcc.fingerprint_auto_match_values(original, 361.6, changed, 361.6)[0])

    def test_local_fingerprint_difference_does_not_add_another_gate(self):
        original = fp(count=4000)
        changed = list(original)
        for i in range(2000, 2020): changed[i] ^= 0xffffffff
        self.assertTrue(mcc.fingerprint_auto_match_values(original, 498, tuple(changed), 498)[0])

    def test_default_live_label_does_not_defeat_matching_cd(self):
        a = mcc.Track(1, Path('digital.flac'), 1, title='Pinocchio Story',
                      duration=361.6, fingerprint=fp())
        b = mcc.Track(2, Path('cd.m4a'), 1, title='Pinocchio Story (Live)',
                      duration=361.6, fingerprint=fp(), is_live=True,
                      exclude_from_coverage=True, base_excluded_from_coverage=True)
        with patch.object(mcc, '_compare_workers', return_value=1):
            groups, _, _ = mcc.merge_equivalent_tracks([a, b])
        self.assertEqual(a.group_id, b.group_id)
        self.assertFalse(b.exclude_from_coverage)
        self.assertFalse(b.base_excluded_from_coverage)
        self.assertEqual(groups[a.group_id], [0, 1])

    def test_explicit_skip_is_not_restored_by_an_allowed_copy(self):
        a = mcc.Track(1, Path('digital.flac'), 1, title='Song', duration=120, fingerprint=fp())
        b = mcc.Track(2, Path('cd.flac'), 1, title='Song (Live)', duration=120,
                      fingerprint=fp(), is_live=True, exclude_from_coverage=True,
                      base_excluded_from_coverage=True, excluded_by_pattern='saved skip')
        mcc.merge_equivalent_tracks([a, b])
        self.assertTrue(b.exclude_from_coverage)

    def test_saved_live_category_survives_matching_allowed_copy(self):
        a=mcc.Track(1,Path('base.flac'),1,title='Song',duration=120,fingerprint=fp())
        b=mcc.Track(2,Path('live.flac'),1,title='Song (Live)',duration=120,fingerprint=fp())
        key,label=mcc._classify_track_pattern(b,'live')
        releases=[mcc.Release(1,'existing',Path('base'),'Base',tracks=[a]),
                  mcc.Release(2,'recycle',Path('live'),'Live',tracks=[b])]
        mcc.configure_exclusions(releases,True,True,[],{key:{'kind':'live','label':label}})
        self.assertTrue(b.exclude_from_coverage)
        mcc.merge_equivalent_tracks([a,b])
        self.assertTrue(b.exclude_from_coverage)

    def test_rejected_pair_cannot_co_cluster_transitively(self):
        tracks=[mcc.Track(i,Path(str(i)+'.flac'),1,duration=100) for i in range(3)]
        groups=mcc._coherent_duration_audio_groups(tracks,[0,1,2],[(0,1),(1,2)],forbidden_pairs={(0,2)})
        self.assertNotEqual(groups.find(0),groups.find(2))

    def test_distinct_length_versions_keep_separate_coverage(self):
        a = mcc.Track(1, Path('long.flac'), 1, title='Jesus Lord', artist='Kanye West',
                      duration=573.66, fingerprint=fp(count=4500), group_id=1)
        b = mcc.Track(2, Path('short.flac'), 1, title='Jesus Lord', artist='Kanye West',
                      duration=538.54, fingerprint=fp(count=4200), group_id=2)
        sim = (3.939695, .95, 1, 0, .8, 3, 9)
        substitutions = mcc._assign_replaceable_version_coverage([a, b], [(1, 0, 1, False, sim)])
        self.assertEqual(substitutions, [])
        self.assertNotEqual(mcc._track_coverage_gid(a), mcc._track_coverage_gid(b))

    def test_collaboration_is_not_foreign_artist_compilation(self):
        kind, _ = mcc.infer_release_type('Watch the Throne', 'Watch the Throne', 16,
             {'MusicBrainz Album Type': 'album', 'albumartist': 'Jay-Z & Kanye West'},
             3600, ['Jay-Z & Kanye West'] * 16, 'kanyewest')
        self.assertEqual(kind, 'album')

    def test_alias_and_joint_group_credits_are_not_compilations(self):
        for album_artist, artist in [('Kanye West;Ye', 'Ye'),
             ('¥$;Kanye West;Ty Dolla $ign', '¥$;Kanye West;Ty Dolla $ign'),
             ('KIDS SEE GHOSTS;Kanye West;Kid Cudi', 'KIDS SEE GHOSTS')]:
            with self.subTest(artist=artist):
                kind, _ = mcc.infer_release_type('Album', 'Album', 12,
                     {'MusicBrainz Album Type': 'album', 'albumartist': album_artist},
                     2400, [artist] * 12, 'kanyewest')
                self.assertEqual(kind, 'album')

    def test_real_majority_other_artists_remains_compilation(self):
        kind, _ = mcc.infer_release_type('Collection', 'Collection', 4,
             {'albumartist': 'Kanye West'}, 900,
             ['Other A', 'Other B', 'Other C', 'Kanye West'], 'kanyewest')
        self.assertEqual(kind, 'compilation')

    def test_known_artist_alias_does_not_split_acoustic_album_family(self):
        cd=[mcc.Track(i,Path('cd/'+str(i)+'.flac'),1,title='Song'+str(i),
                      artist='Kanye West',group_id=i) for i in range(4)]
        web=[mcc.Track(i+10,Path('web/'+str(i)+'.flac'),2,title='Song'+str(i),
                       artist='Ye',group_id=i) for i in range(4)]
        web.append(mcc.Track(20,Path('web/live.flac'),2,artist='Ye',group_id=5,
                             is_live=True,exclude_from_coverage=True))
        releases=[mcc.Release(1,'existing',Path('cd'),'Album',release_type='album',
                              source_medium='CD',tracks=cd),
                  mcc.Release(2,'recycle',Path('web'),'Album',release_type='album',
                              source_medium='WEB',tracks=web)]
        self.assertTrue(mcc._album_editions_related_by_audio(*releases))
        with patch.object(mcc,'_manual_album_group_links',return_value={}), \
             patch.object(mcc,'apply_dynamic_range_final_ties',side_effect=lambda releases,selected,*args:selected):
            selected=mcc.optimize_collection(releases,{i:[i,i+4] for i in range(4)},forced_release_ids=set())
        self.assertEqual(selected,{1})

    def test_featured_artist_is_not_promoted_to_co_primary(self):
        self.assertTrue(mcc._other_artist_majority(
            ['Other Artist feat. Kanye West'] * 3, 'kanyewest', 'Other Artist;Kanye West'))

    def test_featured_alias_remains_secondary(self):
        for featured in ('Kanye West', 'Ye'):
            with self.subTest(featured=featured):
                self.assertTrue(mcc._other_artist_majority(
                    ['Other Artist feat. '+featured]*3, 'kanyewest', 'Other Artist;Kanye West;Ye'))
        self.assertFalse(mcc._other_artist_majority(
            ['Ye feat. Unrelated Guest']*3, 'kanyewest', 'Kanye West;Ye'))
        self.assertFalse(mcc._other_artist_majority(
            ['Ye feat. Kid Cudi']*3, 'kanyewest', 'Kanye West;Ye;Kid Cudi'))

    def test_clean_live_copy_cannot_bypass_advisory_policy(self):
        a=mcc.Track(1,Path('explicit/Song.flac'),1,title='Song',artist='Artist',
                    explicit='explicit',duration=120,fingerprint=fp())
        b=mcc.Track(2,Path('clean/Song (Live).flac'),1,title='Song',artist='Artist',
                    explicit='clean',duration=120,fingerprint=fp())
        releases=[mcc.Release(1,'existing',Path('explicit'),'Album',tracks=[a]),
                  mcc.Release(2,'recycle',Path('clean'),'Album',tracks=[b])]
        mcc.configure_exclusions(releases,True,True,[],{})
        mcc.apply_explicit_over_clean_policy(releases)
        groups,_,_=mcc.merge_equivalent_tracks([a,b])
        self.assertTrue(b.exclude_from_coverage)
        self.assertEqual(b.excluded_by_pattern,'Explicit>Clean')
        self.assertEqual(groups[a.group_id],[0])

    def test_too_few_fingerprint_items_cannot_produce_a_primary_match(self):
        tracks=[mcc.Track(i,Path('missing'+str(i)+'.wav'),i,title='Song',duration=4,
                          fingerprint=(1,2,3)) for i in (1,2)]
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'short.jsonl'
            mcc.merge_equivalent_tracks(tracks,comparison_log_path=path)
            rows=[json.loads(line) for line in path.read_text().splitlines()]
        self.assertNotEqual(tracks[0].group_id,tracks[1].group_id)
        decisions=[row for row in rows if row['record_type']=='comparison']
        self.assertEqual(len(decisions),1)
        self.assertTrue(decisions[0]['details']['decision_consistent'])

    def test_restored_explicit_copy_still_supersedes_clean(self):
        tracks=[mcc.Track(1,Path('explicit/Song (Live).flac'),1,title='Song',artist='Artist',
                          explicit='explicit',duration=120,fingerprint=fp()),
                mcc.Track(2,Path('clean/Song.flac'),1,title='Song',artist='Artist',
                          explicit='clean',duration=120,fingerprint=fp()),
                mcc.Track(3,Path('unknown/Song.flac'),1,title='Song',artist='Artist',
                          duration=120,fingerprint=fp())]
        releases=[mcc.Release(i,'existing',track.path.parent,'Album',tracks=[track])
                  for i,track in enumerate(tracks)]
        mcc.configure_exclusions(releases,True,True,[],{})
        mcc.apply_explicit_over_clean_policy(releases)
        groups,_,_=mcc.merge_equivalent_tracks(tracks)
        self.assertFalse(tracks[0].exclude_from_coverage)
        self.assertTrue(tracks[1].exclude_from_coverage)
        self.assertNotIn(1,groups[tracks[0].group_id])

    def test_final_log_explains_manual_ignore_and_dominated_releases(self):
        a = mcc.Track(1, Path('cd/01 Song.flac'), 1, title='Song', group_id=4,
                      tags={'barcode':'1234567890123'})
        b = mcc.Track(2, Path('web/01 Song.flac'), 1, title='Song', group_id=4,
                      tags={'barcode':'1234567890123'})
        ignored = mcc.Track(3, Path('ignored/01 Big Brother.flac'), 1,
             title='Big Brother', group_id=5, exclude_from_coverage=True,
             manual_skip_rule='saved-ignore')
        pool = [mcc.Release(1, 'existing', Path('cd'), 'Album', release_type='album',
                  source_medium='CD', tracks=[a]),
                mcc.Release(2, 'recycle', Path('web'), 'Album', release_type='album',
                  source_medium='WEB', tracks=[b]),
                mcc.Release(3, 'recycle', Path('ignored'), 'Ignored', release_type='single', tracks=[ignored])]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'log.jsonl'
            with patch.object(mcc, '_manual_album_group_links', return_value={}), \
                 patch.object(mcc, 'apply_dynamic_range_final_ties', side_effect=lambda releases, selected, *args: selected):
                mcc.optimize_collection(pool, {4:[0,1]}, comparison_log_path=path, forced_release_ids=set())
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        states = [r for r in rows if r['record_type'] == 'final_track_state']
        self.assertEqual(len(states), 3)
        self.assertEqual(next(r for r in states if r['release_id'] == 3)['manual_skip_rule'], 'saved-ignore')
        catalog = next(r for r in rows if r['record_type']=='optimizer')['release_source_catalog']
        self.assertEqual({r['release_id'] for r in catalog}, {1,2,3})
        self.assertTrue(next(r for r in catalog if r['release_id']==2)['dominated'])


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg unavailable')
class PCMVerification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch.object(mcc, '_temp_dir', return_value=self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def write_audio(self, name, gain=1.0, vocal=False, delay=0, change_after=None):
        rate = 8000
        rng = random.Random(314)
        data = []
        for i in range(8 * rate):
            sec = i / rate
            backing = (.27 * math.sin(2*math.pi*139*sec) + .15 * math.sin(2*math.pi*293*sec)
                       + .05 * math.sin(2*math.pi*631*sec) + .035*rng.uniform(-1,1))
            voice = .2*math.sin(2*math.pi*(190+12*math.sin(4*sec))*sec) if vocal and (change_after is None or sec>=change_after) else 0
            left = max(-.99,min(.99,gain*(backing+voice)))
            right = max(-.99,min(.99,gain*(.9*backing+.8*voice)))
            data.extend([round(left*32767), round(right*32767)])
        if delay: data = [0]*(2*delay)+data
        path = self.root / name
        with wave.open(str(path),'wb') as out:
            out.setnchannels(2); out.setsampwidth(2); out.setframerate(rate)
            out.writeframes(struct.pack('<'+'h'*len(data),*data))
        return mcc.Track(1,path,1,duration=len(data)/2/rate,fingerprint=fp())

    def verify(self, a, b):
        self.assertTrue(hasattr(mcc, '_PCMIdentityVerifier'), 'Independent acoustic verifier missing')
        with mcc._PCMIdentityVerifier() as verifier:
            return verifier.verify(a, b, (3.5,.95,1,0,.8,3,9))

    def test_level_changed_same_recording_and_offset_pass(self):
        a = self.write_audio('original.wav', gain=1)
        for delay in (24,81,240,761):
            with self.subTest(delay=delay):
                b = self.write_audio('mastered'+str(delay)+'.wav', gain=.6, delay=delay)
                result = self.verify(a,b)
                self.assertTrue(result['passed'], result)

    def test_vocal_and_instrumental_fail(self):
        result = self.verify(self.write_audio('instrumental.wav'), self.write_audio('vocal.wav', vocal=True))
        self.assertFalse(result['passed'],result)

    def test_changed_section_inside_aligned_audio_fails(self):
        result = self.verify(self.write_audio('base.wav'),self.write_audio('changed.wav', vocal=True, change_after=5))
        self.assertFalse(result['passed'],result)

    def test_audible_unmatched_tail_is_not_discarded(self):
        a=self.write_audio('base.wav')
        b=self.write_audio('tail.wav',gain=.6)
        with wave.open(str(b.path),'rb') as src:
            params=src.getparams(); audio=src.readframes(src.getnframes())
        tail=struct.pack('<'+'h'*4800,*[12000 if i%4<2 else -12000 for i in range(4800)])
        with wave.open(str(b.path),'wb') as dst:
            dst.setparams(params);dst.writeframes(audio+tail)
        b.duration+=.3
        result=self.verify(a,b)
        self.assertFalse(result['passed'],result)

    def test_unavailable_audio_never_counts_as_verified(self):
        a=mcc.Track(1,self.root/'missing.wav',1,duration=100)
        result=self.verify(a,a)
        self.assertFalse(result['passed'])

    def test_short_aligned_last_section_is_also_verified(self):
        a=self.write_audio('last-a.wav');b=self.write_audio('last-b.wav')
        for track,period in ((a,7),(b,11)):
            with wave.open(str(track.path),'rb') as src:
                params=src.getparams();audio=src.readframes(src.getnframes())
            tail=struct.pack('<'+'h'*1600,*[12000 if i%period<period//2 else -12000 for i in range(1600)])
            with wave.open(str(track.path),'wb') as dst:
                dst.setparams(params);dst.writeframes(audio+tail)
            track.duration+=.1
        result=self.verify(a,b)
        self.assertFalse(result['passed'],result)

    def test_decoded_waveforms_cannot_veto_passing_fingerprints(self):
        tracks=[]
        for index,coefficient in enumerate((0,.15,.30)):
            rng=random.Random(314);data=[]
            for i in range(8*8000):
                t=i/8000
                backing=.25*math.sin(2*math.pi*139*t)+.25*math.sin(2*math.pi*293*t)+.03*rng.uniform(-1,1)
                voice=.35*math.sin(2*math.pi*443*t)
                value=round((backing+coefficient*voice)*30000)
                data.extend((value,value))
            path=self.root/('chain'+str(index)+'.wav')
            with wave.open(str(path),'wb') as dst:
                dst.setnchannels(2);dst.setsampwidth(2);dst.setframerate(8000)
                dst.writeframes(struct.pack('<'+'h'*len(data),*data))
            # All variants pass the primary comparison. Decoded waveforms
            # cannot override that result under the current user policy.
            mask = (0, 7, 56)[index]
            tracks.append(mcc.Track(index+1,path,1,title='Song',duration=8,
                          fingerprint=tuple(value^mask for value in fp())))
        path=self.root/'chain.jsonl'
        with patch.object(mcc,'_compare_workers',return_value=1):
            mcc.merge_equivalent_tracks(tracks,comparison_log_path=path)
        self.assertEqual(tracks[0].group_id,tracks[2].group_id)
        decisions=[json.loads(line) for line in path.read_text().splitlines()
                   if json.loads(line)['record_type']=='comparison']
        self.assertTrue(all(row['details']['decision_consistent'] for row in decisions))
        for row in decisions:
            if row['decision']=='MATCH':
                self.assertEqual(tracks[row['track_a_index']].group_id,tracks[row['track_b_index']].group_id)
            else:
                # Accepted links through another copy are not vetoed by
                # a different pair falling outside the primary score cap.
                self.assertFalse(row['details']['strict_pass'] or row['details']['mastering_pass'])

    def test_pipeline_logs_fingerprint_authority_without_pcm_confirmation(self):
        a = self.write_audio('original.wav')
        b = self.write_audio('mastered.wav', gain=.6, delay=81)
        c = self.write_audio('vocal.wav', vocal=True)
        a.release_id, b.release_id, c.release_id = 1, 2, 3
        b.fingerprint = tuple(value ^ 7 for value in a.fingerprint)
        c.fingerprint = tuple(value ^ 56 for value in a.fingerprint)
        path=self.root/'comparison.jsonl'
        groups, _, _ = mcc.merge_equivalent_tracks([a,b,c], comparison_log_path=path)
        self.assertEqual(a.group_id,b.group_id)
        self.assertEqual(a.group_id,c.group_id)
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        decisions=[row for row in rows if row['record_type']=='comparison']
        self.assertTrue(all(row['details']['decision_consistent'] for row in decisions))
        confirmed=next(row for row in decisions if {row['track_a_index'],row['track_b_index']}=={0,1})
        self.assertIsNone(confirmed['details']['decoded_audio_verification'])
        self.assertTrue(confirmed['details']['fingerprint_identity_authoritative'])
        self.assertEqual(confirmed['decision'],'MATCH')
        self.assertEqual(len(groups),1)


if __name__ == '__main__':
    unittest.main()
