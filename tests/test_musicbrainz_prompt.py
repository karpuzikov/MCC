"""Copy asks about unidentified releases and keeps going; answers come back by release."""
import threading
import unittest

from test_audio_safety import mcc


class MusicBrainzPrompt(unittest.TestCase):
    def test_release_id_from_mbid_or_release_link_only(self):
        mbid = "69eb068d-682c-4412-9bc3-210f9b231a59"
        for text in (mbid, "https://musicbrainz.org/release/" + mbid, "https://musicbrainz.org/release/" + mbid + "/edit"):
            self.assertEqual(mcc.musicbrainz_release_id(text), mbid)
        for text in ("https://musicbrainz.org/release-group/" + mbid, "Wiley", ""):
            self.assertEqual(mcc.musicbrainz_release_id(text), "")

    def test_skip_all_answers_every_waiting_release(self):
        engine = mcc.Organizer()
        threading.Timer(0.05, engine.answer_musicbrainz, (0, "skip_all")).start()
        self.assertEqual(engine._wait_for_musicbrainz_answer([3, 5]), 3)
        engine._musicbrainz_answers.pop(3)
        self.assertEqual(engine._wait_for_musicbrainz_answer([5]), 5)
        self.assertEqual(engine._musicbrainz_answers, {5: ("skip", "")})

    def test_retry_reports_right_away(self):
        engine = mcc.Organizer()
        results = iter([{"metadata_verified": False, "notes": ["No compatible edition"]}, {"metadata_verified": True, "notes": []}])
        engine._musicbrainz_lookups[7] = lambda chosen_release="": next(results)
        self.assertEqual(engine.lookup_musicbrainz_now(7), (False, "No compatible edition"))
        self.assertEqual(engine.lookup_musicbrainz_now(7), (True, ""))
        self.assertEqual(engine._musicbrainz_answers[7][0], "found")

    def test_empty_search_is_not_cached_and_retry_skips_cache(self):
        import io, json, tempfile
        from pathlib import Path
        from unittest import mock
        answers = iter([{"releases": []}, {"releases": [{"id": "x"}]}, {"releases": [{"id": "y"}]}])
        def respond(*args, **kwargs):
            return io.BytesIO(json.dumps(next(answers)).encode())
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(mcc, "_MB_CACHE", Path(folder)), \
                mock.patch.object(mcc.urllib.request, "urlopen", respond), \
                mock.patch.object(mcc.time, "sleep", lambda s: None):
            self.assertEqual(mcc.mb_json("release/?query=barcode:1"), {"releases": []})
            self.assertEqual(mcc.mb_json("release/?query=barcode:1"), {"releases": [{"id": "x"}]})
            mcc._MB_FRESH.active = True
            try:
                self.assertEqual(mcc.mb_json("release/?query=barcode:1"), {"releases": [{"id": "y"}]})
            finally:
                mcc._MB_FRESH.active = False

    def test_cancel_stops_waiting(self):
        engine = mcc.Organizer()
        engine.stop.set()
        self.assertIsNone(engine._wait_for_musicbrainz_answer([1]))


if __name__ == "__main__":
    unittest.main()
