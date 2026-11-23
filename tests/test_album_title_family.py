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

    def test_album_and_ep_sharing_audio_are_not_one_family(self):
        album = release(0, "album", "Movement", TITLES, 0)
        ep = release(0, "ep", "Motion", TITLES[:4], 0)
        self.assertFalse(mcc._album_editions_related_by_audio(album, ep))
        self.assertTrue(mcc._album_editions_related_by_audio(album, release(0, "album", "Movement", TITLES, 0)))

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


class MaxiSingleTypeAndGroups(unittest.TestCase):
    def test_remix_packs_are_singles_and_three_song_sessions_are_not_albums(self):
        mixes = ["Blue Skies (Radio Edit)", "Blue Skies (Delphinium Days)", "Blue Skies (Deep Dish Mix)", "Blue Skies (Rabbit Mix)", "Blue Skies (Dub)"]
        self.assertEqual(mcc.infer_release_type("Blue Skies", "Blue Skies", 5, {}, 40 * 60, [], "", mixes)[0], "single")
        sides = ["Love Comes Again (Radio Edit)", "Love Comes Again (Mark Norman Remix)", "Traffic (Original Mix)", "Traffic (Max Walder Remix)"]
        self.assertEqual(mcc.infer_release_type("Love Comes Again", "x", 4, {}, 30 * 60, [], "", sides)[0], "single")
        songs = ["Nocturnal Transmission", "Quark", "Tripping The Light Fantastic", "Flaming June", "Loving You More"]
        self.assertEqual(mcc.infer_release_type("Ima", "Ima", 5, {}, 76 * 60, [], "", songs)[0], "album")
        session = ["Cry To The World", "The Warrior Song", "Da Ka Ne"]
        self.assertEqual(mcc.infer_release_type("The Real World Session", "x", 3, {}, 42 * 60, [], "", session)[0], "ep")

    def test_family_and_title_group_with_one_name_share_one_key(self):
        a, b = release(0, "album", "Movement", TITLES, 0), release(0, "album", "Movement", TITLES, 0)
        c = release(0, "album", "Movement", TITLES[:3], 50)
        nodes = [{"id": r.rid, "releaseType": "album", "name": f"[1999] BT - Movement [{i}]", "path": f"r{i}"}
                 for i, r in enumerate((a, b, c))]
        for i, (node, rel) in enumerate(zip(nodes, (a, b, c))):
            rel.rid = i
        with patch.object(mcc, "_manual_album_group_links", return_value={}):
            mcc._assign_release_map_display_groups(nodes, [a, b, c])
        self.assertEqual(len({node["displayGroupKey"] for node in nodes}), 1)


class SameNameAndLiveRelease(unittest.TestCase):
    def test_editions_with_one_release_name_are_one_family_despite_tags_and_titles(self):
        def edition(rid, folder, album, titles):
            rel = release(rid, "album", album, titles, rid * 50)
            rel.path = Path(folder)
            return rel
        a = edition(1, "[2003] BT - Emotional Technology [AVTCD-95728] 2CD", "Emotional Technology: CD1", TITLES)
        b = edition(2, "[2004] BT - Emotional Technology [VICP-62739-40] 2CD", "Emotional", ["The", "Knowledge", TITLES[0]])
        c = edition(3, "[2009] BT - Emotional Technology [BHCD42PE] WEB", "Emotional Technology (Platinum Edition)", TITLES[:3])
        d = edition(4, "[1995] BT - \u4eca Ima [0630-12345-2] CD", "\u4eca Ima", TITLES[:5])
        e = edition(5, "[1996] BT - \u4eca Ima [9 46356-2] 2CD", "Ima", TITLES)
        with patch.object(mcc, "_manual_album_group_links", return_value={}):
            clusters = mcc._album_clusters([a, b, c, d, e])
        self.assertEqual(sorted(sorted(r.rid for r in cl) for cl in clusters), [[1, 2, 3], [4, 5]])

    def test_live_album_name_marks_every_track_live(self):
        rel = release(0, "album", "Live In Japan", TITLES, 0)
        rel.title = "10cc - 1993 - Live In Japan"
        rel.type_source = "heuristic"
        mcc.configure_exclusions([rel], True, True)
        self.assertTrue(all(t.is_live and t.exclude_from_coverage for t in rel.tracks))
        mcc.refresh_heuristic_release_types([rel])
        self.assertNotEqual(rel.release_type, "single")
        studio = release(1, "album", "The Real World Session", TITLES, 10)
        mcc.configure_exclusions([studio], True, True)
        self.assertFalse(any(t.is_live for t in studio.tracks))


class EditionNamesAndKeepButton(unittest.TestCase):
    def test_extended_and_deluxe_editions_join_the_plain_name_and_take_its_title(self):
        songs = ["Skylarking", "Letting Go", "Tomahawk", "City Life", "Stem The Tides"]
        folders = ["[2013] BT - A Song Across Wires [ARDI3392] WEB", "[2013] BT - A Song Across Wires [ARMA352] CD",
                   "[2013] BT - A Song Across Wires Extended Versions [ARDI3394] WEB",
                   "[2014] BT - A Song Across Wires Deluxe Edition [ARDI3505B] WEB"]
        rels = []
        for rid, folder in enumerate(folders):
            rel = release(rid, "compilation", "A Song Across Wires", songs, rid * 10)
            rel.path = Path(folder)
            rels.append(rel)
        nodes = [{"id": r.rid, "releaseType": "compilation", "name": f, "path": f"r{r.rid}"} for r, f in zip(rels, folders)]
        with patch.object(mcc, "_manual_album_group_links", return_value={}):
            mcc._assign_release_map_display_groups(nodes, rels)
        self.assertEqual({n["displayGroupKey"] for n in nodes}.__len__(), 1)
        self.assertEqual({n["displayGroupTitle"] for n in nodes}, {"A Song Across Wires"})
        unrelated = release(9, "compilation", "A Song", ["Other %d" % i for i in range(5)], 90)
        unrelated.path = Path("A Song")
        self.assertFalse(mcc._album_editions_related_by_titles(rels[0], unrelated))

    def test_group_title_is_the_release_name_not_a_shortened_tag(self):
        a = release(1, "album", "今 Ima", TITLES[:5], 0)
        a.path = Path("[1995] BT - 今 Ima [0630-12345-2] CD")
        b = release(2, "album", "Ima", TITLES, 20)
        b.path = Path("[1996] BT - 今 Ima [9 46356-2] 2CD")
        nodes = [{"id": r.rid, "releaseType": "album", "name": r.title, "path": f"r{r.rid}", "albumTitles": [r.tracks[0].album]} for r in (a, b)]
        with patch.object(mcc, "_manual_album_group_links", return_value={}):
            mcc._assign_release_map_display_groups(nodes, [a, b])
        self.assertEqual({n["displayGroupTitle"] for n in nodes}, {"今 Ima"})

    def test_skipped_release_offers_keep_not_ignore(self):
        source = (Path(mcc.__file__)).read_text(encoding="utf-8-sig")
        self.assertIn('id="ignoreReleaseBtn"', source)
        self.assertIn('Keep', source)
        self.assertIn('Skip', source)
        self.assertIn('"toggleKeepRelease"', source)
