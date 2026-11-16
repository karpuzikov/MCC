"""Editions with different masters (no shared audio) but the same album tag and track titles form one family."""
from pathlib import Path
import unittest
from unittest.mock import patch

from test_audio_safety import mcc

TITLES = ["Die In 1977", "A Death-Bed Song", "Boys In Cage", "If The Monkey Becomes", "TV Show", "Laugh From The Time"]


def release(rid, kind, album, titles, first_group):
    tracks = [mcc.Track(rid * 100 + i, Path(f"r{rid}/{i}.flac"), i, title=title, album=album,
                        artist="Re-TROS" if rid == 0 else "Rebuilding The Rights of Statues", group_id=first_group + i)
              for i, title in enumerate(titles)]
    return mcc.Release(rid, "recycle", Path(f"r{rid}"), album, release_type=kind, tracks=tracks)


class AlbumTitleFamily(unittest.TestCase):
    def test_same_album_tag_and_track_titles_are_related_without_shared_audio(self):
        ep = release(0, "ep", "CUT OFF!", TITLES, 0)
        album = release(20, "album", "Cut Off!", TITLES + ["A Vision Of Christ"], 36)
        self.assertFalse(mcc._album_editions_related_by_audio(ep, album))
        self.assertTrue(mcc._album_editions_related_by_titles(ep, album))
        with patch.object(mcc, "_manual_album_group_links", return_value={}):
            self.assertEqual(len(mcc._album_clusters([ep, album])), 1)

    def test_same_album_tag_with_different_tracks_is_not_related(self):
        one = release(1, "album", "Greatest Hits", TITLES, 0)
        two = release(2, "album", "Greatest Hits", ["Other %d" % i for i in range(6)], 10)
        self.assertFalse(mcc._album_editions_related_by_titles(one, two))


if __name__ == "__main__":
    unittest.main()
