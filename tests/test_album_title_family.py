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
    def test_same_type_editions_are_related_without_shared_audio(self):
        first = release(0, "album", "CUT OFF!", TITLES, 0)
        second = release(20, "album", "Cut Off!", TITLES + ["A Vision Of Christ"], 36)
        self.assertFalse(mcc._album_editions_related_by_audio(first, second))
        self.assertTrue(mcc._album_editions_related_by_titles(first, second))
        with patch.object(mcc, "_manual_album_group_links", return_value={}):
            self.assertEqual(len(mcc._album_clusters([first, second])), 1)

    def test_ep_and_album_are_never_grouped_together(self):
        ep = release(0, "ep", "CUT OFF!", TITLES, 0)
        album = release(20, "album", "Cut Off!", TITLES + ["A Vision Of Christ"], 36)
        self.assertFalse(mcc._album_editions_related_by_titles(ep, album))
        with patch.object(mcc, "_manual_album_group_links", return_value={}):
            self.assertEqual(len(mcc._album_clusters([ep, album])), 2)

    def test_manual_move_puts_a_single_into_an_album_group_and_column(self):
        album = {"id": 1, "path": "C:/m/Album", "releaseType": "album", "name": "Album", "displayGroupKind": "album"}
        single = {"id": 2, "path": "C:/m/Single", "releaseType": "single", "name": "Single"}
        links = {mcc._manual_album_group_path_key(Path("C:/m/Single")): mcc._manual_album_group_path_key(Path("C:/m/Album"))}
        with patch.object(mcc, "_manual_album_group_links", return_value=links):
            mcc._assign_release_map_display_groups([album, single])
        self.assertEqual(single["displayGroupKey"], album["displayGroupKey"])
        self.assertEqual(single["displayGroupKind"], "album")

    def test_same_album_tag_with_different_tracks_is_not_related(self):
        one = release(1, "album", "Greatest Hits", TITLES, 0)
        two = release(2, "album", "Greatest Hits", ["Other %d" % i for i in range(6)], 10)
        self.assertFalse(mcc._album_editions_related_by_titles(one, two))

    def test_same_title_and_slot_alternate_masters_match_only_within_8_seconds(self):
        fingerprint = tuple(range(200))
        logged_pairs = {  # sims logged for the Cut Off! editions
            "Laugh From The Time": (7.739669, 0.889348, 1.0, 0, 0.16483, 8.0, 11),
            "TV Show": (6.220067, 0.9414, 1.0, 0, 0.420742, 6.0, 10),
            "Boys In Cage": (8.054377, 0.828249, 1.0, 0, 0.154509, 8.0, 12),
            "If The Monkey Becomes": (9.562859, 0.618894, 1.0, 0, 0.1, 10.0, 13),
        }
        for title, sim in logged_pairs.items():
            with self.subTest(title=title):
                self.assertTrue(mcc._fingerprint_album_context_match(fingerprint, 280.0, fingerprint, 282.0, sim))
        sim = logged_pairs["TV Show"]
        self.assertFalse(mcc._fingerprint_album_context_match(fingerprint, 294.0, fingerprint, 310.0, sim))
        self.assertFalse(mcc._fingerprint_album_context_match(
            fingerprint, 280.0, fingerprint, 282.0, (11.295396, 0.396419, 1.0, 0, 0.0, 11.0, 16)))

    def test_heuristic_types_of_one_album_edition_pair_are_harmonized(self):
        ep = release(0, "ep", "CUT OFF!", TITLES, 0)
        album = release(20, "album", "Cut Off!", TITLES + ["A Vision Of Christ"], 36)
        other = release(30, "ep", "Another Record", ["X%d" % i for i in range(5)], 60)
        for rel in (ep, album, other):
            rel.type_source = "heuristic"
        mcc._harmonize_heuristic_album_types([ep, album, other])
        self.assertEqual((ep.release_type, album.release_type, other.release_type), ("album", "album", "ep"))
        ep.release_type, ep.type_source = "ep", "tag"
        album.release_type = "album"
        mcc._harmonize_heuristic_album_types([ep, album])
        self.assertEqual(ep.release_type, "ep")


if __name__ == "__main__":
    unittest.main()
