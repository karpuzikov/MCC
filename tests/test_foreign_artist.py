"""A track without the scanned artist folder in its artist or album artist tag is skipped."""
from pathlib import Path
import unittest

from test_audio_safety import mcc


def release(rid, artist, album_artist):
    track = mcc.Track(rid, Path(f"Wiley/R{rid}/01 Song {rid}.flac"), rid, title=f"Song {rid}", artist=artist,
                      tags={"artist": artist, "albumartist": album_artist})
    return mcc.Release(rid, "recycle", Path(f"Wiley/R{rid}"), f"R{rid}", tracks=[track], scan_root="Wiley")


class ForeignArtist(unittest.TestCase):
    def test_track_without_scanned_artist_is_skipped(self):
        releases = [release(1, "Wiley", "Wiley"), release(2, "Wiley feat. Skepta", "Wiley"),
                    release(3, "Lickle Jay;Riko Dan", "Lickle Jay")]
        mcc._mark_foreign_artist_tracks(releases)
        mcc.configure_exclusions(releases, exclude_remixes=True, exclude_live=True)
        skipped = [r.tracks[0].excluded_by_pattern == "Different artist" for r in releases]
        self.assertEqual(skipped, [False, False, True])


if __name__ == "__main__":
    unittest.main()
