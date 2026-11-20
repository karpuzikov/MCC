"""Save Remixes / Save Live OFF ignores every remix / live track: no exceptions, no fingerprints."""
from pathlib import Path
import unittest

from test_audio_safety import mcc


def classified(remix_title, remix_artist):
    base = mcc.Track(1, Path("A/01 Song.flac"), 1, title="Song", artist="Band")
    remix = mcc.Track(2, Path(f"B/01 {remix_title}.flac"), 1, title=remix_title, artist=remix_artist)
    releases = [mcc.Release(1, "recycle", Path("A"), "A", tracks=[base]),
                mcc.Release(2, "recycle", Path("B"), "B", tracks=[remix])]
    mcc.configure_exclusions(releases, exclude_remixes=True, exclude_live=False)
    return base, remix


class RemixCredit(unittest.TestCase):
    def test_every_remix_is_ignored_and_not_fingerprinted(self):
        for title, artist in [("Song (Remix)", "Band;Some Remixer"), ("Song (Remix) feat. Guest", "Band"),
                              ("Song (Funkagenda Mix)", "Band feat. Guest"), ("Song (Band Remix)", "Band")]:
            with self.subTest(title=title):
                base, remix = classified(title, artist)
                self.assertTrue(remix.is_remix and remix.exclude_from_coverage)
                self.assertEqual(mcc._fingerprint_identity_candidates([base, remix]), [base])


if __name__ == "__main__":
    unittest.main()
