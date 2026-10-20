"""Read-only decoded boundary-padding regressions, independent of match policy."""
from array import array
from functools import lru_cache
import hashlib
import importlib.machinery
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('MCC_TEST_SOURCE', str(ROOT / 'Music Collection Cleaner v0.05.53.pyw')))
loader = importlib.machinery.SourceFileLoader('mcc_padding_subject', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
mcc = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = mcc
loader.exec_module(mcc)


@lru_cache(maxsize=8)
def body_samples(rate, seconds, silent=False):
    samples = array('h')
    for i in range(round(rate * seconds)):
        t = i / rate
        value = 0 if silent else round(6500 * math.sin(2 * math.pi * (173*t + .7*t*t))
                                      + 1900 * math.sin(2 * math.pi * 431*t)
                                      + 600 * math.sin(2 * math.pi * 1093*t))
        samples.extend((value, round(value * .83)))
    if sys.byteorder != 'little':
        samples.byteswap()
    return samples.tobytes()


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg unavailable')
class SilencePaddingVerification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.temp_patch = patch.object(mcc, '_temp_dir', return_value=self.root)
        self.temp_patch.start()

    def tearDown(self):
        self.temp_patch.stop()
        self.temp.cleanup()

    def write_audio(self, name, prefix=0, tail=0, tail_kind='silence', rate=8000,
                    seconds=4, silent_body=False, edge_samples=0, prefix_noise_peak=0):
        samples = array('h')
        for i in range(round(tail * rate)):
            value = 0
            if tail_kind in ('audible', 'right-only'):
                value = 8000 if i % 10 < 5 else -8000
            elif tail_kind == 'dc':
                value = 6000
            elif tail_kind == 'near-silence':
                value = 1 if i % 2 else -1
            elif tail_kind == 'high-frequency' and .1 * rate < i < (tail - .1) * rate:
                fade = min(1, (i / rate - .1) / .1, (tail - .1 - i / rate) / .1)
                envelope = .5 * (1 - math.cos(math.pi * fade))
                value = round(2000 * envelope * math.sin(2 * math.pi * 6000 * i / rate))
            elif tail_kind == 'late-click' and i == round(tail * rate) - 100:
                value = 10000
            elif tail_kind == 'boundary-edge' and i < edge_samples:
                value = 10000
            samples.extend((0 if tail_kind == 'right-only' else value, value))
        if sys.byteorder != 'little':
            samples.byteswap()
        path = self.root / name
        prefix_frames = round(prefix * rate)
        if prefix_noise_peak:
            # Low-RMS, high-frequency quantization-scale noise survives native
            # measurement while being suppressed by the 8 kHz alignment cache.
            pattern = array('h')
            for value in [prefix_noise_peak, -prefix_noise_peak] + [1, -1] * 63:
                pattern.extend((value, value))
            if sys.byteorder != 'little':
                pattern.byteswap()
            prefix_data = (pattern.tobytes() * (prefix_frames // 128)
                           + pattern.tobytes()[:4 * (prefix_frames % 128)])
        else:
            prefix_data = b'\0' * (4 * prefix_frames)
        with wave.open(str(path), 'wb') as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(prefix_data
                            + body_samples(rate, seconds, silent_body) + samples.tobytes())
        duration = prefix + seconds + tail
        return mcc.Track(1, path, 1, duration=duration, sample_rate=rate, channels=2,
                         fingerprint=(123456789,) * max(1, round(duration * 8)))

    def verify(self, first, second, shift=0):
        self.assertTrue(hasattr(mcc._PCMIdentityVerifier, 'verify_padding'),
                        'Independent decoded padding probe is missing')
        with mcc._PCMIdentityVerifier() as verifier:
            result = verifier.verify_padding(first, second, (0, 1, 1, shift, 1, 0, 0))
        for key in ('passed', 'method', 'reason', 'alignment_lag_samples',
                    'effective_durations_seconds', 'padding_seconds'):
            self.assertIn(key, result)
        self.assertEqual(result['method'], 'decoded-boundary-silence-v2')
        return result

    def test_ten_and_thirty_second_silent_tails_are_measured_without_changing_audio(self):
        base = self.write_audio('base.wav')
        for tail in (10, 30):
            padded = self.write_audio('padding-%s.wav' % tail, tail=tail)
            for reverse in (False, True):
                first, second = (padded, base) if reverse else (base, padded)
                before = [hashlib.sha256(t.path.read_bytes()).digest() for t in (first, second)]
                tracks_before = [dict(vars(t)) for t in (first, second)]
                with self.subTest(tail=tail, reverse=reverse):
                    result = self.verify(first, second)
                    self.assertTrue(result['passed'], result)
                    self.assertEqual(result['alignment_lag_samples'], 0)
                    self.assertEqual(result['effective_durations_seconds'], [4.0, 4.0])
                    self.assertEqual(result['padding_seconds'], [float(tail), 0.0] if reverse else [0.0, float(tail)])
                    self.assertEqual(before, [hashlib.sha256(t.path.read_bytes()).digest() for t in (first, second)])
                    self.assertEqual(tracks_before, [dict(vars(t)) for t in (first, second)])

    def test_long_silent_prefix_is_verified_in_either_order(self):
        base = self.write_audio('base.wav')
        padded = self.write_audio('prefix.wav', prefix=10)
        for reverse in (False, True):
            first, second = (padded, base) if reverse else (base, padded)
            with self.subTest(reverse=reverse):
                result = self.verify(first, second, 80 if reverse else -80)
                self.assertTrue(result['passed'], result)
                self.assertEqual(result['alignment_lag_samples'], 80000 if reverse else -80000)
                self.assertEqual(result['effective_durations_seconds'], [4.0, 4.0])

    def test_three_minute_prefix_uses_chromaprint_frame_timing(self):
        base=self.write_audio('base-long.wav',seconds=12)
        padded=self.write_audio('prefix-long.wav',prefix=180.059375,seconds=12)
        # Realistic default-Chromaprint counts: duration contains startup delay;
        # duration/fingerprint_count is not the duration of a fingerprint item.
        base.fingerprint=(123456789,)*76
        padded.fingerprint=(0,)*1454+base.fingerprint
        for first,second,shift in [(padded,base,1454),(base,padded,-1454)]:
            with self.subTest(shift=shift):
                result=self.verify(first,second,shift)
                self.assertTrue(result['passed'],result)
                self.assertAlmostEqual(abs(result['alignment_lag_samples'])/8000,180.059375,places=4)
                self.assertLessEqual(abs(result['effective_durations_seconds'][0]-result['effective_durations_seconds'][1]),.0021)
                self.assertEqual(result['effective_durations_seconds'], [12.0, 12.0])

    def test_full_pipeline_routes_illest_metadata_before_three_minute_padding(self):
        # Actual edition/censorship naming, controlled vectors and generated
        # media: this reaches the real router, comparison and native decoder.
        from test_audio_safety import fp
        base = self.write_audio('13 Illest Motherf***** Alive.wav', seconds=12)
        padded = self.write_audio('13 Illest Motherfucker Alive.wav',
                                  prefix=180.059375, seconds=12)
        base.fingerprint = fp(count=76)
        mastered = tuple(value ^ (0x08400000 if i % 10 < 6 else 0)
                         for i, value in enumerate(base.fingerprint))
        padded.fingerprint = (0,) * 1454 + mastered
        base.title, padded.title = 'Illest Motherf***** Alive', 'Illest Motherfucker Alive'
        base.album, padded.album = 'Watch The Throne (Deluxe)', 'Watch the Throne (Deluxe Edition)'
        base.release_id, padded.release_id = 55, 10
        before = [hashlib.sha256(t.path.read_bytes()).digest() for t in (padded, base)]
        with patch.object(mcc, 'FP_SHADOW_SAMPLE_SIZE', 0), \
             patch.object(mcc, '_compare_workers', return_value=1):
            groups, _, _ = mcc.merge_equivalent_tracks([padded, base])
        self.assertEqual(padded.group_id, base.group_id,
                         'Illest must reach native silence normalization through the router')
        self.assertEqual(len(groups), 1)
        self.assertAlmostEqual(padded.identity_duration_seconds, 12, places=3)
        self.assertAlmostEqual(base.identity_duration_seconds, 12, places=3)
        self.assertEqual([padded.duration, base.duration], [192.059375, 12])
        self.assertEqual(before, [hashlib.sha256(t.path.read_bytes()).digest() for t in (padded, base)])
        cd = mcc.Release(10, 'existing', self.root / 'CD',
                         title=padded.album, tracks=[padded], release_type='album',
                         source_medium='CD', has_cue=True, has_rip_log=True)
        web = mcc.Release(55, 'recycle', self.root / 'WEB',
                          title=base.album, tracks=[base], release_type='album',
                          source_medium='Digital Media')
        self.assertEqual(mcc.optimize_collection([cd, web], {}), {10})

    def test_actual_illest_native_measurement_is_near_silent_padding(self):
        fixture = json.loads((ROOT / 'tests/fixtures/illest_native_padding_measurement.json').read_text())
        measured = fixture['padding_verification']['boundary_spans'][0]['native_measurement']['levels']
        self.assertTrue(mcc._padding_levels_are_quiet(measured),
                        'The actual native RMS 1.19 / peak 5 LSB must qualify as near silence')
        self.assertFalse(mcc._padding_levels_are_quiet([{'rms_lsb': 3, 'peak_lsb': 5}]))
        self.assertFalse(mcc._padding_levels_are_quiet([{'rms_lsb': .01, 'peak_lsb': 10000}]))
        self.assertFalse(mcc._padding_levels_are_quiet([]))

    def test_native_quantization_scale_noise_does_not_block_silent_prefix(self):
        base = self.write_audio('base-noise.wav', rate=44100)
        for peak, expected in [(5, True), (9, False)]:
            padded = self.write_audio('noise-%s.wav' % peak, prefix=10,
                                      prefix_noise_peak=peak, rate=44100)
            for first, second, shift in [(padded, base, 80), (base, padded, -80)]:
                with self.subTest(peak=peak, shift=shift):
                    result = self.verify(first, second, shift)
                    self.assertEqual(result['passed'], expected, result)
                    if expected:
                        self.assertLessEqual(abs(result['effective_durations_seconds'][0]
                                                - result['effective_durations_seconds'][1]), .0021)

    def test_full_pipeline_illest_near_silent_prefix_retains_only_cd(self):
        from test_audio_safety import fp
        base = self.write_audio('13 Illest Motherf***** Alive.wav', seconds=12, rate=44100)
        padded = self.write_audio('13 Illest Motherfucker Alive.wav', prefix=180.059375,
                                  seconds=12, rate=44100, prefix_noise_peak=5)
        base.fingerprint = fp(count=76)
        padded.fingerprint = (0,) * 1454 + tuple(value ^ (0x08400000 if i % 10 < 6 else 0)
                                               for i, value in enumerate(base.fingerprint))
        base.title, padded.title = 'Illest Motherf***** Alive', 'Illest Motherfucker Alive'
        base.album, padded.album = 'Watch The Throne (Deluxe)', 'Watch the Throne (Deluxe Edition)'
        base.release_id, padded.release_id = 55, 10
        before = [hashlib.sha256(t.path.read_bytes()).digest() for t in (padded, base)]
        with patch.object(mcc, 'FP_SHADOW_SAMPLE_SIZE', 0), \
             patch.object(mcc, '_compare_workers', return_value=1):
            mcc.merge_equivalent_tracks([padded, base])
        self.assertEqual(padded.group_id, base.group_id, 'Near-silent Illest prefix must normalize')
        self.assertEqual([padded.duration, base.duration], [192.059375, 12])
        self.assertEqual(before, [hashlib.sha256(t.path.read_bytes()).digest() for t in (padded, base)])
        cd = mcc.Release(10, 'existing', self.root / 'CD', title=padded.album, tracks=[padded],
                         release_type='album', source_medium='CD', has_cue=True, has_rip_log=True)
        web = mcc.Release(55, 'recycle', self.root / 'WEB', title=base.album, tracks=[base],
                          release_type='album', source_medium='Digital Media')
        self.assertEqual(mcc.optimize_collection([cd, web], {}), {10})

    def test_proven_prefix_padding_keeps_audible_residual_in_eight_second_rule(self):
        from test_audio_safety import fp
        for tail, same in [(.01, True), (8, True), (8.001, False)]:
            base = self.write_audio('base-residual.wav', seconds=12)
            padded = self.write_audio('residual-%s.wav' % tail, prefix=20,
                                      seconds=12, tail=tail, tail_kind='audible')
            base.title = padded.title = 'Song'
            base.release_id, padded.release_id = 1, 2
            base.fingerprint = fp(count=76)
            padded.fingerprint = (0,) * 162 + base.fingerprint + (0,) * max(1, round(tail * 8))
            with self.subTest(tail=tail), patch.object(mcc, '_compare_workers', return_value=1):
                mcc.merge_equivalent_tracks([base, padded])
                self.assertEqual(base.group_id == padded.group_id, same)
                # The audible tail is retained. Only the proven 20-second
                # prefix is removed, even when the residual exceeds eight.
                self.assertAlmostEqual(padded.identity_duration_seconds, 12 + tail, places=3)
                self.assertEqual(padded.duration, 32 + tail)

    def test_offset_and_silent_ends_preserve_silence_on_the_shared_timeline(self):
        first = self.write_audio('first.wav', prefix=1.25, tail=1.75)
        second = self.write_audio('second.wav', prefix=.5, tail=.25)
        result = self.verify(first, second, 6)
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['alignment_lag_samples'], 6000)
        self.assertEqual(result['padding_seconds'], [2.25, 0.0])
        self.assertEqual(result['effective_durations_seconds'], [4.75, 4.75])

    def test_audible_extra_tail_is_not_padding(self):
        result = self.verify(self.write_audio('base.wav'),
                             self.write_audio('audible.wav', tail=10, tail_kind='audible'))
        self.assertFalse(result['passed'], result)

    def test_audio_in_only_the_right_channel_is_not_padding(self):
        result = self.verify(self.write_audio('base.wav'),
                             self.write_audio('right.wav', tail=10, tail_kind='right-only'))
        self.assertFalse(result['passed'], result)

    def test_an_isolated_late_click_cannot_be_averaged_into_silence(self):
        result = self.verify(self.write_audio('base.wav'),
                             self.write_audio('click.wav', tail=30, tail_kind='late-click'))
        self.assertFalse(result['passed'], result)

    def test_constant_dc_is_not_silence(self):
        result = self.verify(self.write_audio('base.wav'),
                             self.write_audio('dc.wav', tail=10, tail_kind='dc'))
        self.assertFalse(result['passed'], result)

    def test_native_high_frequency_audio_is_not_lost_in_the_alignment_cache(self):
        result = self.verify(self.write_audio('base48.wav', rate=48000),
                             self.write_audio('high48.wav', rate=48000, tail=10,
                                              tail_kind='high-frequency'))
        self.assertFalse(result['passed'], result)
        self.assertIn('native', result['reason'].lower(), result)

    def test_one_lsb_near_silence_is_padding(self):
        result = self.verify(self.write_audio('base.wav'),
                             self.write_audio('near.wav', tail=10, tail_kind='near-silence'))
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['padding_seconds'], [0.0, 10.0])

    def test_missing_audio_fails_closed(self):
        track = mcc.Track(1, self.root / 'missing.wav', 1, duration=100)
        self.assertFalse(self.verify(track, track)['passed'])

    def test_missing_decoder_fails_closed(self):
        base = self.write_audio('base.wav')
        padded = self.write_audio('padding.wav', tail=10)
        with patch.object(mcc, '_locate_ffmpeg_pair', return_value=None):
            result = self.verify(base, padded)
        self.assertFalse(result['passed'], result)

    def test_insufficient_audio_is_not_meaningful_identity(self):
        result = self.verify(self.write_audio('short.wav', seconds=.5),
                             self.write_audio('short-padding.wav', seconds=.5, tail=10))
        self.assertFalse(result['passed'], result)

    def test_implausible_decoded_duration_fails_closed(self):
        base = self.write_audio('base.wav')
        padded = self.write_audio('padding.wav', tail=10)
        padded.duration = 400
        self.assertFalse(self.verify(base, padded)['passed'])

    def test_all_silent_aligned_audio_is_not_meaningful_identity(self):
        result = self.verify(self.write_audio('silent.wav', silent_body=True),
                             self.write_audio('silent-padding.wav', silent_body=True, tail=10))
        self.assertFalse(result['passed'], result)

    def test_mismatched_native_sample_rate_metadata_fails_closed(self):
        base = self.write_audio('base.wav')
        padded = self.write_audio('padding.wav', tail=10)
        padded.sample_rate = 44100
        self.assertFalse(self.verify(base, padded)['passed'])

    def test_unpadded_source_metadata_is_also_checked(self):
        base = self.write_audio('base.wav')
        base.sample_rate = 44100
        self.assertFalse(self.verify(base, self.write_audio('padding.wav', tail=10))['passed'])

    def test_native_rate_below_the_alignment_rate_fails_closed(self):
        base = self.write_audio('base4k.wav', rate=4000)
        base.sample_rate = 0
        self.assertFalse(self.verify(base, self.write_audio('padding.wav', tail=10))['passed'])

    def test_tolerated_two_ms_edge_is_retained_in_effective_duration(self):
        result = self.verify(self.write_audio('base.wav'),
                             self.write_audio('edge.wav', tail=10, tail_kind='boundary-edge',
                                              edge_samples=16))
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['padding_seconds'], [0.0, 9.998])
        self.assertEqual(result['effective_durations_seconds'], [4.0, 4.002])
        self.assertEqual(result['boundary_spans'][-1]['retained_boundary_samples'], 16)

    def test_edge_tolerance_cannot_hide_more_than_two_ms(self):
        result = self.verify(self.write_audio('base.wav'),
                             self.write_audio('edge.wav', tail=10, tail_kind='boundary-edge',
                                              edge_samples=17))
        self.assertFalse(result['passed'], result)

    def test_full_pipeline_uses_real_decoded_padding_and_preserves_raw_duration(self):
        # Controlled fingerprint evidence exercises integration; the waveform
        # padding is verified through real FFmpeg, without a verdict stub.
        base=self.write_audio('base.wav',seconds=12)
        padded=self.write_audio('padding.wav',seconds=12,tail=10)
        base.title=padded.title='Song'
        base.release_id,padded.release_id=1,2
        with patch.object(mcc,'_compare_workers',return_value=1):
            groups,_,_=mcc.merge_equivalent_tracks([base,padded])
        self.assertEqual(base.group_id,padded.group_id)
        self.assertEqual(len(groups),1)
        self.assertEqual([base.duration,padded.duration],[12,22])
        self.assertEqual([base.identity_duration_seconds,padded.identity_duration_seconds],[12,12])

    def test_full_pipeline_retains_audible_version_despite_fingerprint_silence_hint(self):
        base=self.write_audio('base.wav',seconds=12)
        padded=self.write_audio('audible.wav',seconds=12,tail=10,tail_kind='audible')
        base.title=padded.title='Song'
        base.release_id,padded.release_id=1,2
        with patch.object(mcc,'_compare_workers',return_value=1):
            groups,_,_=mcc.merge_equivalent_tracks([base,padded])
        self.assertNotEqual(base.group_id,padded.group_id)
        self.assertEqual(len(groups),2)
        self.assertEqual([base.identity_duration_seconds,padded.identity_duration_seconds],[0,0])


if __name__ == '__main__':
    unittest.main()
