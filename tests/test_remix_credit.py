"""A remixer in the ARTIST tag of a plain '(Remix)' is not a featured vocalist."""
from pathlib import Path
import unittest

from test_audio_safety import mcc


def classified(remix_title, remix_artist):
    base = mcc.Track(1, Path("A/01 Song.flac"), 1, title="Song", artist="Band")
    remix = mcc.Track(2, Path(f"B/01 {remix_title}.flac"), 1, title=remix_title, artist=remix_artist)
    releases = [mcc.Release(1, "recycle", Path("A"), "A", tracks=[base]),
                mcc.Release(2, "recycle", Path("B"), "B", tracks=[remix])]
    mcc.configure_exclusions(releases, exclude_remixes=True, exclude_live=False)
    return remix


class RemixCredit(unittest.TestCase):
    def test_remixer_in_artist_tag_is_excluded(self):
        remix = classified("Song (Remix)", "Band;Some Remixer")
        self.assertTrue(remix.is_remix)
        self.assertTrue(remix.exclude_from_coverage)
        self.assertFalse(remix.remix_feature_exception)

    def test_stated_feature_after_remix_wording_is_kept(self):
        remix = classified("Song (Remix) feat. Guest", "Band")
        self.assertTrue(remix.remix_feature_exception)
        self.assertFalse(remix.exclude_from_coverage)


if __name__ == "__main__":
    unittest.main()
