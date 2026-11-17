# Organizer engine tests (ported from Music Library Organizer v0.3.23).
import sys
sys.dont_write_bytecode = True
import shutil
import re
import tempfile
import threading
import unittest
import wave
import zipfile
from pathlib import Path

from test_audio_safety import mcc as mlo


def organize(app, source, dest, fmt):
    """Discover and organize one source folder the way Copy/Move does."""
    groups = [(name, members, source) for name, members in mlo.group_disc_releases(mlo.discover(source))]
    app.organize_groups(groups, dest, fmt, "", {})


class UserExamples20261014(unittest.TestCase):
    def test_release_title_has_no_feature_credit(self):
        self.assertEqual(mlo.clean_release_title("Cola Song (ft. J Balvin)"), "Cola Song")
        self.assertEqual(mlo.release_title_normalize(
            "Good Time (feat. Pitbull)", "Single"), "Good Time - Single")

    def test_single_release_feature_transfers_to_track_not_folder(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "2014-07-15 - Good Time (feat. Pitbull) [075679936356]"
            output = root / "Output"
            source.mkdir()
            (source / "01 Good Time.flac").write_bytes(b"test-copy")
            app = mlo.Organizer()
            app._current_identity = {
                "title": "Good Time", "physical": False,
                "feature_hint": "Pitbull", "metadata_verified": False}
            app._current_release_feature = "Pitbull"
            app._artist_root = "INNA"
            app.encoding_workers = 1
            observed = []
            with patch.object(mlo, "metadata", return_value=("1","Good Time","INNA")), \
                 patch.object(mlo, "probe", return_value={"codec_name":"flac"}), \
                 patch.object(mlo, "_update_copied_track_tags",
                              side_effect=lambda path,title,artist,num: observed.append(
                                  (title,artist,num))):
                app._export_release(source,output,"FLAC","ffmpeg","ffprobe")
            self.assertTrue((output / "01 Good Time (ft. Pitbull).flac").is_file())
            self.assertEqual(observed, [("Good Time (ft. Pitbull)","INNA",1)])
            self.assertEqual(mlo.release_title_normalize(
                "Good Time (feat. Pitbull)", "Single"), "Good Time - Single")

    def test_remix_and_extended_mix_release_case(self):
        self.assertEqual(mlo.release_title_normalize(
            "Déjà Vu (extended mix)", "Single"), "Déjà Vu (Extended Mix) - Single")
        self.assertEqual(mlo.release_title_normalize(
            "Sun Is Up (remix)", "Single"), "Sun Is Up (Remix) - Single")

    def test_legacy_cd_promo_title_cleaning(self):
        self.assertEqual(mlo.clean_release_title(
            "Inna - Déjá Vu (Maxi CD Single) (Promo)", "INNA"), "Déjà Vu")
        self.assertEqual(mlo.clean_release_title(
            "Inna - Party Never Ends (Part 2) (2013) [WPCR-15062]", "INNA"),
            "Party Never Ends (Part 2)")

    def test_diggy_down_filename_and_tag_title_are_same(self):
        title, artist = mlo.normalize_artist_title(
            "Diggy Down (Radio Edit) [ft. Marian Hill]", "INNA")
        self.assertEqual(title, "Diggy Down (ft. Marian Hill) [Radio Edit]")
        self.assertEqual(artist, "INNA")
        self.assertEqual(mlo.track_filename(1, title, ".m4a"),
                         "01 Diggy Down (ft. Marian Hill) [Radio Edit].m4a")
        title2, _ = mlo.normalize_artist_title(
            "Diggy Down (Extended Version) [ft. Marian Hill]", "INNA")
        self.assertEqual(title2,
                         "Diggy Down (ft. Marian Hill) [Extended Version]")

    def test_explicit_feature_removed_from_combined_artist_tag(self):
        title, artist = mlo.normalize_artist_title(
            "Diggy Down (Radio Edit) [ft. Marian Hill]",
            "INNA & Marian Hill", "INNA")
        self.assertEqual(title, "Diggy Down (ft. Marian Hill) [Radio Edit]")
        self.assertEqual(artist, "INNA")
        title2, artist2 = mlo.normalize_artist_title(
            "Diggy Down (Extended Version) [ft. Marian Hill]",
            "INNA, Marian Hill", "INNA")
        self.assertEqual(title2, "Diggy Down (ft. Marian Hill) [Extended Version]")
        self.assertEqual(artist2, "INNA")
        title3, artist3 = mlo.normalize_artist_title(
            "Song (ft. Artist B)", "Artist A & Artist B", "Unrelated")
        self.assertEqual(artist3, "Artist A & Artist B")

    def test_bob_taylor_reverse_credit_requires_consensus(self):
        value = "Deja Vu (Wideboy Stadium Radio Edit) [Bob Taylor ft. INNA]"
        original, artist = mlo.normalize_artist_title(value, "Bob Taylor")
        self.assertEqual(original, "Deja Vu (ft. INNA) [Wideboy Stadium Radio Edit]")
        self.assertEqual(artist, "Bob Taylor")
        consensus = {(
            mlo._song_key(value), frozenset(("inna", "bob taylor"))): "INNA"}
        expected, corrected = mlo.normalize_artist_title(
            value, "Bob Taylor", "INNA", consensus)
        self.assertEqual(corrected, "INNA")
        self.assertEqual(expected,
                         "Deja Vu (ft. Bob Taylor) [Wideboy Stadium Radio Edit]")
        # Different versions MUST retain their authentic titles.
        variant, _ = mlo.normalize_artist_title(
            "Deja Vu (ft. Bob Taylor) [Play & Win Club Mix]", "INNA")
        self.assertEqual(variant, "Deja Vu (ft. Bob Taylor) [Play & Win Club Mix]")

    def test_track_remix_added_credit_order_retained(self):
        t, _ = mlo.normalize_artist_title(
            "Reminder (Remix) [ft. A$AP Rocky & Young Thug]", "The Weeknd")
        self.assertEqual(t, "Reminder (Remix) [ft. A$AP Rocky & Young Thug]")

    def test_exact_discid_filters_two_cd_release(self):
        from unittest.mock import patch
        base = [{"discid": "valid-disc", "tracks": 16}]
        def fake_mb(path, **kwargs):
            if "double" in path:
                return {"media": [{"format":"CD","track-count":16},
                                  {"format":"CD","track-count":9}]}
            if "single" in path:
                return {"id":"single","media":[{"format":"CD","track-count":16,
                                                 "discs":[{"id":"valid-disc"}]}]}
            raise RuntimeError("Unknown release")
        with patch.object(mlo, "mb_json", side_effect=fake_mb):
            matching, rejected = mlo._disc_editions_by_medium(
                ["double", "single"], base)
        self.assertEqual([x["id"] for x in matching], ["single"])
        self.assertEqual(len(rejected), 1)



class OriginalCheckerRegression(unittest.TestCase):




    def test_native_output_parser_real_probabilities_only(self):
        self.assertEqual(mlo._parse_native_aucdtect(
            "This track looks like MPEG with probability 95%"), ("MPEG", 95))
        self.assertEqual(mlo._parse_native_aucdtect(
            "This track looks like CDDA with probability 100%"), ("CDDA", 100))
        with self.assertRaisesRegex(RuntimeError, "no valid"):
            mlo._parse_native_aucdtect("NO_STRONG_CUTOFF")
        with self.assertRaisesRegex(RuntimeError, "invalid probability"):
            mlo._parse_native_aucdtect(
                "This track looks like MPEG with probability 120%")

    def test_exact_fifty_five_track_audiochecker_checksum(self):
        # Verified verbatim against user's original 55-track AudioChecker
        # v2.0 build 457 report: 145533892, Summary 94,76% CDDA.
        titles = [
            "Comme une ombre", "Mets-moi bien", "Te Quiero",
            "Ceci n'est pas du rap", "Pirate", "En secret", "10 - 10",
            "Le prix à payer", "Jasmine", "Dans la cité", "Miami vice",
            "Naïf", "Na Lingui Yo", "Je sais qui t'es", "Reste",
            "VBT (Very Bad Trip)", "Tant pis", "Caméléon", "Fuegolando",
            "La même", "Loup garou", "Entre nous c'est mort",
            "Laissez-moi tranquille", "Mi gna", "Tu reviendras",
            "Nos valeurs", "Tu ne le vois pas", "Merci maman",
            "T'es partie", "Tu m'as dit", "Oulala", "Bonita",
            "Le pire", "Où aller", "Tu m'as mis dans la merde",
            "Anakin", "Malheur, malheur", "Mon cœur meurtri",
            "Gunshot", "La nuit c'est fait pour dormir",
            "Tu me l'avais promis", "Ana fi dar", "Skyfall",
            "Appelez la police", "Ps", "Chien de la casse",
            "Je t'en veux", "Everytime", "La vérité",
            "Les roses ont des épines", "60%", "Je n'ai rien promis",
            "Corazón", "Christophe", "Bella ciao",
        ]
        self.assertEqual(len(titles), 55)
        checked = []
        for idx, title in enumerate(titles, 1):
            category = "MPEG" if idx in (30, 45, 49) else "CDDA"
            prob = 95 if category == "MPEG" else (99 if idx in (7, 19, 20) else 100)
            checked.append((Path(f"{idx:02d} {title}.flac"), category, prob))
        self.assertEqual(mlo._original_checker_checksum(checked), 145533892)
        body = mlo._original_checker_report("New folder", checked)
        self.assertIn("Summary 94,76% CDDA", body)
        self.assertTrue(body.endswith("\r\n145533892\r\n"))
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "audiochecker.log"
            log.write_bytes(body.encode("utf-8"))
            self.assertTrue(mlo._verify_original_checker_report(
                log, [r[0] for r in checked], "New folder"))
            log.write_bytes(log.read_bytes() + b"tampering")
            self.assertFalse(mlo._verify_original_checker_report(
                log, [r[0] for r in checked], "New folder"))

    def test_missing_historical_cue_image_keeps_split_tracks_partial(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "physical"
            dest = Path(tmp) / "sorted"
            source.mkdir()
            for number in (1, 2):
                (source / f"{number:02d} Track {number}.flac").write_bytes(
                    b"source-must-survive-" + str(number).encode())
            (source / "INNA.cue").write_text(
                'FILE "Missing Album Image.wav" WAVE\n'
                '  TRACK 01 AUDIO\n'
                '    TITLE "Track 1"\n'
                '    INDEX 01 00:00:00\n'
                '  TRACK 02 AUDIO\n'
                '    TITLE "Track 2"\n'
                '    INDEX 01 03:00:00\n', encoding="utf-8")
            app = mlo.Organizer()
            app._current_identity = {"physical": True,
                                     "catalog": "", "barcode": "",
                                     "metadata_verified": False}
            app._artist_root = "INNA"
            app._credit_consensus = {}
            app._export_warnings = []
            app.encoding_workers = 1
            def fake_meta(path):
                num = int(Path(path).name[:2])
                return str(num), f"Track {num}", "INNA"
            with patch.object(mlo, "metadata", side_effect=fake_meta), \
                 patch.object(mlo, "probe", return_value={"codec_name": "flac"}), \
                 patch.object(mlo, "_update_copied_track_tags"):
                app._export_release(source, dest, "FLAC", "ffmpeg", "ffprobe")
            self.assertFalse((dest / "INNA.cue").exists())
            self.assertTrue((dest / "Unresolved CUE - INNA.cue").is_file())
            self.assertTrue((dest / "01 Track 1.flac").is_file())
            self.assertTrue((dest / "02 Track 2.flac").is_file())
            self.assertTrue(app._export_warnings)
            self.assertTrue((source / "INNA.cue").is_file())




class UserCorrections20261014(unittest.TestCase):
    def test_picard_english_small_words(self):
        cases = {
            "10 Minutes (Club Mix By Play & Win)": "10 Minutes (Club Mix by Play & Win)",
            "We're Going In The Club": "We're Going in the Club",
            "More Than Friends feat. Daddy Yanke": "More Than Friends (ft. Daddy Yanke)",
            "INNDiA feat. Play&Win": "INNDiA (ft. Play & Win)",
        }
        for supplied, expected in cases.items():
            with self.subTest(supplied=supplied):
                self.assertEqual(mlo.normalized_title(supplied), expected)
                self.assertEqual(mlo.track_filename(13, supplied, ".m4a"),
                                 "13 " + expected + ".m4a")

    def test_deluxe_edition_typo_and_feature_free_release(self):
        title = mlo.release_title_normalize(
            "Party Never Ends, Pt. 2 (Deluxe Editon)", "EP")
        self.assertEqual(title, "Party Never Ends, Pt. 2 (Deluxe Edition) - EP")
        self.assertNotIn("feat.", title.lower())

    def test_source_filename_feature_survives_short_tag(self):
        from unittest.mock import patch
        with patch.object(mlo, "metadata",
                          return_value=("3", "More Than Friends", "INNA")):
            num, title, artist = mlo.extract_number_title(
                Path("03 More Than Friends feat. Daddy Yanke.m4a"), "INNA")
        self.assertEqual((num, title, artist),
                         (3, "More Than Friends (ft. Daddy Yanke)", "INNA"))

    def test_legacy_maxi_cd_single_type_kept_without_online_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            release = Path(td) / "Inna - Déjá Vu (Maxi CD Single) (Promo)"
            release.mkdir()
            (release / "original.cue").write_text(
                'FILE "missing.wav" WAVE\n'
                '  TRACK 01 AUDIO\n'
                '    TITLE "Déjá Vu"\n'
                '    INDEX 01 00:00:00\n', encoding="utf-8")
            info = mlo.release_identity(release, mlo.collect_files(release),
                                        default_artist="INNA", allow_network=False)
            self.assertEqual(info["release_type"], "Single")
            self.assertEqual(mlo.release_folder_target(info), "Déjà Vu - Single")

    def test_unknown_cd_legacy_names_are_cleaned_not_retained(self):
        example = {"folder": "Inna - Déjá Vu (Maxi CD Single) (Promo)",
                   "title": "Inna - Déjá Vu (Maxi CD Single) (Promo)",
                   "date": "", "physical": True, "catalog": "", "barcode": "",
                   "country": "", "root_artist": "INNA", "notes": [],
                   "release_type": ""}
        self.assertEqual(mlo.release_folder_target(example), "Déjà Vu")
        self.assertIn("unverified", " ".join(example["notes"]))
        example = {"folder": "Inna - Party Never Ends (Part 2) (2013) [WPCR-15062]",
                   "title": "Party Never Ends (Part 2): Japan",
                   "date": "2012-01-01", "physical": True,
                   "catalog": "WPCR-15062", "barcode": "",
                   "country": "JP", "root_artist": "INNA", "notes": [],
                   "release_type": "Album", "edition_date": "2013-01-01"}
        target = mlo.release_folder_target(example)
        self.assertIn("Party Never Ends (Part 2)", target)
        self.assertIn("WPCR-15062", target)
        self.assertNotIn(":", target)
        self.assertNotEqual(target, example["folder"])

    def test_verified_web_barcode_does_not_require_catalog(self):
        verified = {"physical": False, "metadata_verified": True,
                    "barcode": "5948204032791", "catalog": "", "notes": []}
        checker = [{"results": 2, "cdda": 2, "mpeg": 0}]
        self.assertEqual(mlo.completion_reasons(verified, [], checker), [])
        self.assertIn("WEB", " ".join(mlo.completion_reasons(
            dict(verified, barcode=""), [], checker)))
        self.assertIn("Original auCDtect report missing",
                      mlo.completion_reasons(verified, [], []))
        self.assertTrue(mlo.completion_reasons(
            dict(verified, physical=True, country_provenance=
                 "MusicBrainz release-territory-fallback (not verified pressing)"),
            [], []))
        # No MusicBrainz match is a note ("No MusicBrainz match"), never a PARTIAL reason.
        self.assertEqual(mlo.completion_reasons(
            dict(verified, metadata_verified=False), [], checker), [])


class RebuildMissingImageCue(unittest.TestCase):
    def test_exact_sixteen_track_image_cue_remaps_to_split_files(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            oldcue = root / "Party Never Ends.cue"
            starts = list(range(0, 16 * 150, 150))
            lines = []
            for n, stamp in enumerate(starts, 1):
                m, rem = divmod(stamp, 75 * 60)
                sec, frame = divmod(rem, 75)
                if n == 1:
                    lines.append('FILE "missing original.wav" WAVE')
                lines.extend([f"  TRACK {n:02d} AUDIO",
                              f'    TITLE "Track {n}"',
                              f"    INDEX 01 {m:02d}:{sec:02d}:{frame:02d}"])
            oldcue.write_text("\n".join(lines), encoding="utf-8")
            parsed = mlo.cue_read(oldcue)
            mapping = {}
            for n in range(1, 17):
                src = root / f"{n:02d} Track {n}.flac"
                dst = root / "New" / f"{n:02d} Track {n}.m4a"
                mapping[src] = dst
            with patch.object(mlo, "_exact_cd_sectors", return_value=150):
                rebuilt, problem = mlo.reconstruct_missing_image_cue(parsed, oldcue, mapping)
            self.assertEqual(problem, "")
            self.assertEqual(rebuilt.count('FILE "'), 16)
            self.assertEqual(rebuilt.count("INDEX 01 00:00:00"), 16)
            self.assertIn('FILE "16 Track 16.m4a" WAVE', rebuilt)
            self.assertTrue(oldcue.exists())


    def test_sector_mismatch_or_index00_remains_unresolved(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cue = root / "old.cue"
            cue.write_text('FILE "missing.wav" WAVE\n'
                           '  TRACK 01 AUDIO\n'
                           '    TITLE "A"\n'
                           '    INDEX 01 00:00:00\n'
                           '  TRACK 02 AUDIO\n'
                           '    TITLE "B"\n'
                           '    INDEX 01 00:02:00\n', encoding="utf-8")
            mapping = {root / "01 A.flac": root / "new" / "01 A.flac",
                       root / "02 B.flac": root / "new" / "02 B.flac"}
            with patch.object(mlo, "_exact_cd_sectors", return_value=149):
                rebuilt, problem = mlo.reconstruct_missing_image_cue(
                    mlo.cue_read(cue), cue, mapping)
            self.assertIsNone(rebuilt)
            self.assertIn("150", problem)
            cue.write_text(cue.read_text() + "    INDEX 00 00:01:70\n")
            with patch.object(mlo, "_exact_cd_sectors", return_value=150):
                rebuilt, problem = mlo.reconstruct_missing_image_cue(
                    mlo.cue_read(cue), cue, mapping)
            self.assertIsNone(rebuilt)
            self.assertIn("INDEX 00", problem)


class NamingRules(unittest.TestCase):
    def test_release_types_and_remix_exception(self):
        self.assertEqual(mlo.release_title_normalize("Good Time", "Single"), "Good Time - Single")
        self.assertEqual(mlo.release_title_normalize("Title - The Remixes EP", "EP"), "Title (The Remixes)")
        self.assertEqual(mlo.release_title_normalize("Plain Jane Remix", "Single"), "Plain Jane (Remix) - Single")
        x = {"folder":"Inna - YO 2019", "title":"YO", "date":"2019-05-01", "catalog":"CAT123", "barcode":"1234", "physical":False, "country":"", "release_type":"Album", "track_count":13, "notes":[]}
        # RULES.md title case: all-caps styling alone is not an acronym ("YO" -> "Yo").
        self.assertEqual(mlo.release_folder_target(x), "2019-05-01 - Yo [CAT123]")

    def test_yo_physical_edition_folder_and_sidecar_identity(self):
        info = {"folder": "Inna - YO 2019", "title": "YO",
                "date": "2019-05-31", "catalog": "GR18186",
                "barcode": "", "physical": True, "country": "RO",
                "release_type": "Album", "track_count": 11, "notes": []}
        self.assertEqual(mlo.release_folder_target(info),
                         "2019-05-31 - Yo [RO - GR18186]")

    def test_release_type_suffix_relocation(self):
        self.assertEqual(mlo.release_title_normalize("Song (EP) (Extended Mix)", "EP"),
                         "Song (Extended Mix) - EP")
        self.assertEqual(mlo.release_title_normalize("Song (Remixes) (Single)", "Single"),
                         "Song (Remixes)")
        # Owner decision 2026-10-14: "(Maxi CD)" and "(Promo)" edition notes are
        # NOT kept in release folder names; only the release-type suffix remains.
        self.assertEqual(mlo.release_title_normalize("Song (Maxi CD Single) (Promo)", "Single"),
                         "Song - Single")

    def test_checker_rejects_fake_report(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "audiochecker.log"
            log.write_text("AudioChecker fake output\\n100", encoding="utf-8")
            self.assertFalse(mlo._verify_original_checker_report(log, [Path("01 Example.flac")], "New folder"))

    def test_cd_reissue_year_suffix_from_concrete_edition(self):
        info = {"folder": "Legacy", "title": "I Am the Club Rocker",
                "date": "2011-09-19", "edition_date": "2012-07-11",
                "catalog": "WPCR-14516", "barcode": "", "physical": True,
                "country": "JP", "release_type": "Album", "notes": []}
        self.assertEqual(mlo.release_folder_target(info),
                         "2011-09-19 - I Am the Club Rocker [JP - WPCR-14516 - 2012]")
        info["edition_date"] = "2011-10-10"
        self.assertEqual(mlo.release_folder_target(info),
                         "2011-09-19 - I Am the Club Rocker [JP - WPCR-14516]")

    def test_digital_reissue_year_suffix_requires_verified_different_edition_year(self):
        info = {"folder": "Legacy", "title": "Get to Heaven (Expanded 10th Anniversary Edition)",
                "date": "2015-05-19", "edition_date": "2025-07-04",
                "catalog": "", "barcode": "196873083926", "physical": False,
                "country": "", "release_type": "Album", "notes": []}
        self.assertEqual(
            mlo.release_folder_target(info),
            "2015-05-19 - Get to Heaven (Expanded 10th Anniversary Edition) [196873083926 - 2025]")
        info["edition_date"] = "2015-06-19"
        self.assertEqual(
            mlo.release_folder_target(info),
            "2015-05-19 - Get to Heaven (Expanded 10th Anniversary Edition) [196873083926]")
        info["edition_date"] = ""
        self.assertEqual(
            mlo.release_folder_target(info),
            "2015-05-19 - Get to Heaven (Expanded 10th Anniversary Edition) [196873083926]")

    def test_cd_does_not_export_existing_web_audiochecker_log(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, dest = root / "CD", root / "Output"
            source.mkdir()
            (source / "01 Track.flac").write_bytes(b"placeholder-audio")
            (source / "original.cue").write_text(
                'FILE "01 Track.flac" WAVE\n  TRACK 01 AUDIO\n'
                '    TITLE "Track"\n    INDEX 01 00:00:00\n',
                encoding="utf-8")
            (source / "original.log").write_text("Exact Audio Copy rip log", encoding="utf-8")
            (source / "playlist.m3u").write_text("01 Track.flac", encoding="utf-8")
            (source / "cover.jpg").write_bytes(b"image")
            checker_source = source / "audiochecker.log"
            checker_source.write_text("historic WEB report", encoding="utf-8")
            app = mlo.Organizer()
            app._current_identity = {"physical": True, "metadata_verified": True,
                                     "catalog": "CAT001", "barcode": ""}
            app.encoding_workers = 1
            with patch.object(mlo, "probe", return_value={"codec_name": "flac"}), \
                 patch.object(mlo, "_update_copied_track_tags"):
                app._export_release(source, dest, "FLAC", "unused-ffmpeg", "unused-ffprobe")
            self.assertFalse((dest / "audiochecker.log").exists())
            self.assertTrue((dest / "CAT001.cue").exists())
            self.assertTrue((dest / "CAT001.log").exists())
            self.assertEqual(sorted(p.name for p in dest.iterdir()), ["01 Track.flac", "CAT001.cue", "CAT001.log"])
            self.assertEqual(checker_source.read_text(encoding="utf-8"), "historic WEB report")
            self.assertEqual((dest / "01 Track.flac").read_bytes(), b"placeholder-audio")

    def test_cue_only_cd_does_not_become_web(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Unknown"
            folder.mkdir()
            cue = folder / "one.cue"
            cue.write_text('FILE "01 Track.flac" WAVE\n'
                           '  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n')
            info = mlo.release_identity(folder, [cue], default_artist="Artist", allow_network=False)
            self.assertTrue(info["physical"])

    def test_zero_padding_exact_one_space(self):
        self.assertEqual(mlo.track_filename(1, "Red Lips (ft. Sam Bruno) [Skrillex Remix]", ".m4a"),
                         "01 Red Lips (ft. Sam Bruno) [Skrillex Remix].m4a")
        self.assertEqual(mlo.track_filename(12, "Example", ".flac"), "12 Example.flac")
        self.assertEqual(mlo.track_filename(101, "Example", ".flac"), "101 Example.flac")

    def test_three_positional_brackets(self):
        original = "C'Mon (Catch 'Em By Surprise) (feat. Busta Rhymes) (Extended Club Mix)"
        self.assertEqual(mlo.normalized_title(original),
                         "C'Mon (Catch 'Em by Surprise) [ft. Busta Rhymes] {Extended Club Mix}")

    def test_original_feature_and_remix_preserved(self):
        self.assertEqual(mlo.normalized_title("Red Lips (ft. Sam Bruno) [Skrillex Remix]"),
                         "Red Lips (ft. Sam Bruno) [Skrillex Remix]")
        self.assertEqual(mlo.normalized_title("Reminder (Remix) [ft. A$AP Rocky & Young Thug]"),
                         "Reminder (Remix) [ft. A$AP Rocky & Young Thug]")

    def test_physical_catalog_and_web_id(self):
        self.assertEqual(mlo.catalog("2007-07-09 - Our Love to Admire [JP - TOCP-66683]"),
                         ("TOCP-66683", True))
        self.assertEqual(mlo.catalog("2002-08-19 - Turn on the Bright Lights [US - OLE 993-2 - 2012]"),
                         ("OLE 993-2", True))
        self.assertEqual(mlo.catalog("2018-02-16 - El Pintor Bonus Tracks [OLE13186]"),
                         ("OLE13186", False))

    def test_source_and_destination_safety(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "Artist ALAC"
            src.mkdir()
            with self.assertRaises(ValueError):
                mlo.check_paths(str(src), str(src), "ALAC")
            with self.assertRaises(ValueError):
                mlo.check_paths(str(src), str(src / "child"), "FLAC")
            with self.assertRaises(ValueError):
                mlo.check_paths(str(src), str(Path(td) / "Other ALAC"), "FLAC")
            # check_paths returns (source, destination).
            source, dest = mlo.check_paths(str(src), str(Path(td) / "Artist FLAC"), "FLAC")
            self.assertEqual(source, src.resolve())
            self.assertEqual(dest.name, "Artist FLAC")


class AutomaticBatch(unittest.TestCase):
    @staticmethod
    def identity(folder, files, default_artist="", **_options):
        name = folder.name
        catalog = mlo.catalog(name)[0]
        title = re.sub(r"^\d{4}-\d\d-\d\d - ", "", name).split(" [")[0]
        return {"folder": name, "title": title, "date": "2020-01-01",
                "catalog": catalog, "barcode": "", "physical": False,
                "country": "", "country_provenance": "", "release_type": "Single",
                "selected_release": "test-only-id", "metadata_verified": True,
                "notes": [], "track_count": 1}

    def test_missing_audiochecker_does_not_block_and_second_run_skips(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "Input"
            output = base / "Output"
            folder = source / "2020-01-01 - Track [ABC123]"
            folder.mkdir(parents=True)
            (folder / "01 Track.flac").write_bytes(b"fixture")
            places = {"DATA": base / "Settings",
                                                                  "REPORT": base / "Settings" / "last-run.json",
                      "UNDO": base / "Settings" / "undo.json",
                      "HISTORY": base / "Settings" / "undo-history"}
            with patch.multiple(mlo, **places):
                app = mlo.Organizer()
                app.source, app.dest, app.fmt = str(source), str(output), "FLAC"
                app._export_release = lambda inp, out, fmt, ff, fp, source_files=None: shutil.copy2(
                    inp / "01 Track.flac", out / "01 Track.flac")
                with patch.object(mlo, "release_identity", side_effect=self.identity), \
                     patch.object(mlo, "ensure_ffmpeg", return_value=("ff", "ffprobe")), \
                     patch.object(mlo, "native_check_web_release", side_effect=RuntimeError("analyzer failed")):
                    organize(app, source, output, "FLAC")
                    self.assertEqual(app.counts["partial"], 1)
                    self.assertEqual(app.counts["done"], 0)
                    self.assertEqual(app.counts["failed"], 0)
                    self.assertIn("REQUIRED AudioChecker not completed", " | ".join(app.results[0]["warnings"]))
                    out_name = mlo.release_folder_target(self.identity(folder, []))
                    self.assertTrue((output / out_name / "01 Track.flac").is_file())
                    organize(app, source, output, "FLAC")
                    self.assertEqual(app.counts["skipped"], 1)
                    self.assertEqual(app.results[-1]["status"], "skipped")

    def test_bad_release_does_not_stop_good_release(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "Input"
            dest = base / "Output"
            folders = [source / "2020-01-01 - A [AAA]", source / "2020-01-01 - B [BBB]"]
            for folder in folders:
                folder.mkdir(parents=True)
                (folder / "01 Audio.flac").write_bytes(b"fixture")
            places = {key: base / "Data" / name for key, name in {
                "DATA":"","UNDO":"undo.json",
                "REPORT":"last-run.json","HISTORY":"undo-history"}.items()}
            with patch.multiple(mlo, **places):
                app = mlo.Organizer()
                app.source, app.dest, app.fmt = str(source), str(dest), "FLAC"
                def export(folder, output, fmt, ff, ffprobe, source_files=None):
                    if folder.name.endswith("[AAA]"):
                        raise ValueError("synthetic unsupported source")
                    shutil.copy2(folder / "01 Audio.flac", output / "01 Audio.flac")
                app._export_release = export
                with patch.object(mlo, "release_identity", side_effect=self.identity), \
                     patch.object(mlo, "ensure_ffmpeg", return_value=("ff", "ffprobe")), \
                     patch.object(mlo, "native_check_web_release", side_effect=RuntimeError("analyzer failed")):
                    organize(app, source, dest, "FLAC")
                self.assertEqual(app.counts["failed"], 1)
                self.assertEqual(app.counts["partial"], 1)
                out_name = mlo.release_folder_target(self.identity(folders[1], []))
                self.assertTrue((dest / out_name / "01 Audio.flac").is_file())

    def test_original_filename_version_survives_shorter_title_tag(self):
        from unittest.mock import patch
        with patch.object(mlo, "metadata", return_value=("1", "OK", "Artist")):
            number, title, _ = mlo.extract_number_title(Path("01 OK (Extended Version).flac"))
            self.assertEqual(number, 1)
            self.assertEqual(title, "OK (Extended Version)")






class NativeEncoderCompliance(unittest.TestCase):
    def test_qaac_and_xiph_provenance(self):
        self.assertEqual(mlo._FLAC_VERSION, "1.5.0")
        self.assertTrue(mlo._FLAC_ZIP_URL.startswith(
            "https://ftp.osuosl.org/pub/xiph/releases/flac/"))
        self.assertTrue(mlo._QAAC_ZIP_URL.startswith(
            "https://github.com/nu774/qaac/releases/download/"))
        self.assertRegex(mlo._QAAC_ZIP_SHA256, r"^[0-9a-f]{64}$")

    def test_encoder_archive_hash_mismatch_is_rejected(self):
        from unittest.mock import patch, MagicMock
        reply = MagicMock()
        reply.__enter__.return_value.read.return_value = b"tampered archive"
        with patch.object(mlo.urllib.request, "urlopen", return_value=reply):
            with self.assertRaisesRegex(RuntimeError, "SHA-256 verification failed"):
                mlo._fetch_official_archive(mlo._QAAC_ZIP_URL, mlo._QAAC_ZIP_SHA256)

    def test_flac_download_falls_back_to_the_second_source(self):
        import hashlib
        from unittest.mock import patch, MagicMock
        good = MagicMock()
        good.__enter__.return_value.read.return_value = b"archive"
        calls = []
        def fake(request, timeout=0):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise OSError("CERTIFICATE_VERIFY_FAILED")
            return good
        with patch.object(mlo.urllib.request, "urlopen", side_effect=fake):
            data = mlo._fetch_official_archive(mlo._FLAC_ZIP_GITHUB_URL, hashlib.sha256(b"archive").hexdigest(), mlo._FLAC_ZIP_URL)
        self.assertEqual(data, b"archive")
        self.assertEqual(calls, [mlo._FLAC_ZIP_GITHUB_URL, mlo._FLAC_ZIP_URL])

    def test_native_encoder_only_no_ffmpeg_encode(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wav = root / "original.wav"
            wav.write_bytes(b"not a real decoder input: faked runner")
            calls = []
            def fake_cmd(argv, timeout=3600):
                calls.append(list(map(str, argv)))
                if argv[0] == "ffmpeg":
                    Path(argv[-1]).write_bytes(b"temporary PCM WAV")
                elif argv[0] in ("refalac64.exe", "flac.exe"):
                    target = argv[argv.index("-o")+1]
                    Path(target).write_bytes(b"native test bitstream")
                return SimpleNamespace(returncode=0, stderr="", stdout="")
            for fmt, ext, encoder in (("ALAC", ".m4a", "refalac64.exe"),
                                      ("FLAC", ".flac", "flac.exe")):
                calls.clear()
                dst = root / ("generated" + ext)
                with patch.object(mlo, "cmd", side_effect=fake_cmd), \
                     patch.object(mlo, "ensure_encoder", return_value=encoder), \
                     patch.object(mlo, "_lossless_pcm_format",
                                  return_value=("pcm_s16le",16,44100)), \
                     patch.object(mlo, "probe",
                                  return_value={"codec_name":fmt.lower(),
                                                "sample_rate":"44100"}), \
                     patch.object(mlo, "pcm_hash", return_value="same"), \
                     patch.object(mlo, "_copy_audio_metadata") as tags, \
                     patch.object(mlo, "DATA", root):
                    mlo.convert("ffmpeg", wav, dst, fmt, ffprobe="ffprobe",
                                title="Test", number=1)
                encodes = [x for x in calls if x[0] in ("flac.exe", "refalac64.exe")]
                self.assertEqual(len(encodes), 1)
                self.assertEqual(encodes[0][0], encoder)
                # ffmpeg may decode to temporary PCM (-c:a pcm_*) but must never
                # encode the final ALAC/FLAC output.
                for argv in calls:
                    if "-c:a" in argv:
                        self.assertTrue(argv[argv.index("-c:a") + 1].startswith("pcm_"), argv)
                tags.assert_called_once()

    def test_no_unsupported_codec_fallback(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "audio.wav"
            src.write_bytes(b"test")
            with patch.object(mlo, "_lossless_pcm_format",
                              return_value=("pcm_s16le",16,44100)), \
                 patch.object(mlo, "ensure_encoder", side_effect=RuntimeError("no refalac64")):
                with self.assertRaisesRegex(RuntimeError, "refalac64"):
                    mlo.convert("ffmpeg", src, Path(td)/"output.m4a", "ALAC",
                                ffprobe="ffprobe")
                self.assertFalse((Path(td)/"output.m4a").exists())

    def test_floating_pcm_and_lossy_sources_refused(self):
        from unittest.mock import patch
        with patch.object(mlo, "probe", return_value={
                "codec_name":"pcm_f32le", "sample_fmt":"flt", "sample_rate":"48000",
                "bits_per_sample":32}):
            with self.assertRaisesRegex(RuntimeError, "Floating-point"):
                mlo._lossless_pcm_format("ffprobe", Path("test.wav"))
        with patch.object(mlo, "probe", return_value={
                "codec_name":"mp3", "sample_fmt":"fltp", "sample_rate":"44100"}):
            with self.assertRaisesRegex(RuntimeError, "Lossy"):
                mlo._lossless_pcm_format("ffprobe", Path("test.mp3"))

    def test_zip_traversal_rejected(self):
        import io
        with tempfile.TemporaryDirectory() as td:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr("../unwanted.exe", b"unsafe")
            with self.assertRaisesRegex(RuntimeError, "Unsafe"):
                mlo._safe_zip_extract(buf.getvalue(), Path(td)/"target")


class DiscIDAndWorkers(unittest.TestCase):
    def test_suggested_output_and_worker_defaults(self):
        self.assertEqual(mlo.suggested_output(r"C:\Music\INNA - UPDATED").replace("\\", "/"),
                         "C:/Music/INNA - UPDATED - Sorted")
        self.assertGreaterEqual(mlo.worker_limit(), 1)
        enc, checking = mlo.worker_defaults()
        self.assertTrue(1 <= enc <= mlo.worker_limit())
        self.assertTrue(1 <= checking <= mlo.worker_limit())

    def test_discid_uses_cue_corrector_sector_algorithm(self):
        import base64, hashlib
        start = [0, 150]
        leadout = 330
        result = mlo._disc_identity(start, leadout)
        payload = "01" + "02" + f"{leadout+150:08X}"
        payload += "".join(f"{n+150:08X}" for n in start) + ("0" * (97*8))
        expected = base64.b64encode(hashlib.sha1(payload.encode("ascii")).digest()).decode("ascii")
        expected = expected.replace("+", ".").replace("/", "_").replace("=", "-")
        self.assertEqual(result["discid"], expected)
        self.assertEqual(result["toc"], "1 2 480 150 300")

    def test_barcode_and_discid_must_agree_on_concrete_edition(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "2007-01-01 - Example [US - 1234567890123]"
            folder.mkdir()
            cue = folder / "rip.cue"
            cue.write_text('FILE "image.wav" WAVE\n  TRACK 01 AUDIO\n    TITLE "A"\n    INDEX 01 00:00:00\n  TRACK 02 AUDIO\n    TITLE "B"\n    INDEX 01 00:02:00\n', encoding="utf8")
            log = folder / "rip.log"
            log.write_text('1 | 0:00.00 | 0:02.00 | 0 | 149\n'
                           '2 | 0:02.00 | 0:02.00 | 150 | 329\n')
            (folder / "image.wav").write_bytes(b"dummy CD audio")
            calls = []
            def fake_mb(path, **kwargs):
                calls.append(path)
                if path.startswith("discid/"):
                    return {"releases": [{"id": "disc-edition"}, {"id": "other-edition"}]}
                if path.startswith("release/?"):
                    return {"releases": [{"id": "disc-edition", "barcode": "1234567890123"}]}
                if path.startswith("release/other-edition"):
                    return {"id": "other-edition", "media": [
                        {"format": "CD", "track-count": 2},
                        {"format": "CD", "track-count": 2}]}
                if path.startswith("release/disc-edition"):
                    return {"id": "disc-edition", "title": "Example",
                            "barcode": "1234567890123", "country": "US",
                            "media": [{"format": "CD", "track-count": 2}],
                            "label-info": [{"catalog-number": "CAT-12"}],
                            "release-group": {"first-release-date": "2006-11-18", "primary-type": "Album"}}
                raise RuntimeError("Unexpected MusicBrainz request " + path)
            with patch.object(mlo, "mb_json", side_effect=fake_mb):
                info = mlo.release_identity(folder, mlo.collect_files(folder), default_artist="Artist")
            self.assertTrue(any(x.startswith("discid/") for x in calls))
            # Barcode agreement is checked on each DiscID candidate's own release record.
            self.assertTrue(any(x.startswith("release/disc-edition") for x in calls))
            self.assertEqual(info["catalog"], "CAT-12")
            self.assertEqual(info["date"], "2006-11-18")
            self.assertEqual(info["selected_release"], "disc-edition")
            self.assertEqual(mlo.release_folder_target(info),
                             "2006-11-18 - Example [US - CAT-12]")

    def test_ambiguous_discid_preserves_original_name(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "2001 - Ambiguous CD [US - none]"
            folder.mkdir()
            (folder / "A.cue").write_text('FILE "album.wav" WAVE\n'
                             '  TRACK 01 AUDIO\n    TITLE "A"\n    INDEX 01 00:00:00\n'
                             '  TRACK 02 AUDIO\n    TITLE "B"\n    INDEX 01 00:01:00\n')
            (folder / "album.wav").write_bytes(b"test")
            (folder / "A.log").write_text('1 | 0:00.00 | 0:01.00 | 0 | 74\n'
                                          '2 | 0:01.00 | 0:01.00 | 75 | 149\n')
            with patch.object(mlo, "mb_json", return_value={
                    "releases": [{"id": "edition1"}, {"id": "edition2"}]}):
                info = mlo.release_identity(folder, mlo.collect_files(folder), default_artist="Artist")
            self.assertFalse(info["metadata_verified"])
            self.assertEqual(mlo.release_folder_target(info), folder.name)

    def test_parallel_original_checker_report_requires_native_verdicts(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tracks = [root / "01 Track.flac", root / "02 Song.flac"]
            for p in tracks:
                p.write_bytes(b"mock PCM input")
            def original_job(path, ff, ffprobe, native, stop):
                return path, "CDDA", 100
            private = root / "aucdtect.exe"
            private.write_bytes(b"fake runner not executed")
            with patch.object(mlo, "_native_aucdtect", return_value=private), \
                 patch.object(mlo.shutil, "which", return_value="ffprobe"), \
                 patch.object(mlo, "_original_checker_job", side_effect=original_job):
                results = mlo.native_check_web_release(
                    root, "ALAC", "ffmpeg", threading.Event(), workers=2,
                    release_name="Actual Album")
            self.assertEqual(results[0]["workers"], 2)
            self.assertEqual(results[0]["results"], 2)
            self.assertIn("Original auCDtect", results[0]["analyzer"])
            log = root / "audiochecker.log"
            self.assertTrue(mlo._verify_original_checker_report(
                log, tracks, "Actual Album"))

    def test_encoding_worker_parallel_copy_and_title_fidelity(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Source"
            dest = Path(td) / "Output"
            source.mkdir()
            for n in range(1, 4):
                (source / f"{n:02d} Track {n}.flac").write_bytes(bytes([n]*20))
            app = mlo.Organizer()
            app.encoding_workers = 3
            with patch.object(mlo, "probe", return_value={"codec_name": "flac"}), \
                 patch.object(mlo, "_update_copied_track_tags"):
                app._export_release(source, dest, "FLAC", "unused", "unused")
            for n in range(1, 4):
                self.assertTrue((dest / f"{n:02d} Track {n}.flac").exists())


class CueAndDiscovery(unittest.TestCase):
    def test_recursive_release_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "Artist ALAC"
            release = base / "Albums" / "2020-05-01 - Example [US - CAT001]"
            disc = release / "CD 1"
            disc.mkdir(parents=True)
            (disc / "01 Example.flac").write_bytes(b"not decoded by discovery")
            self.assertEqual(mlo.discover(base), [release])

    def _cue(self, path, index2="00:01:00", index0=False):
        parts = ['PERFORMER "Example"', 'TITLE "Album"', 'FILE "album.wav" WAVE',
                 '  TRACK 01 AUDIO', '    TITLE "First"', '    INDEX 01 00:00:00',
                 '  TRACK 02 AUDIO', '    TITLE "Second"']
        if index0:
            parts.append('    INDEX 00 00:00:70')
        parts.append("    INDEX 01 " + index2)
        path.write_text("\n".join(parts)+"\n", encoding="utf-8")

    def test_image_cue_track_boundaries(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            (path / "album.wav").write_bytes(b"placeholder")
            cue_path = path / "CAT001.cue"
            self._cue(cue_path)
            cue = mlo.cue_read(cue_path)
            images = mlo.cue_image_plan(cue_path, cue)
            self.assertEqual(len(images), 1)
            self.assertEqual(images[0][2], [0, 75])
            names = {1: ("01 First.flac", 0, 75), 2: ("02 Second.flac", 75, None)}
            rewritten = mlo.image_cue_text(cue, names)
            self.assertIn('FILE "01 First.flac" WAVE', rewritten)
            self.assertIn('FILE "02 Second.flac" WAVE', rewritten)
            self.assertEqual(rewritten.count("INDEX 01 00:00:00"), 2)

    def test_index_00_preserved_during_split(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            (path / "album.wav").write_bytes(b"placeholder")
            cue_path = path / "CAT001.cue"
            self._cue(cue_path, index0=True)
            cue = mlo.cue_read(cue_path)
            plan = mlo.cue_image_plan(cue_path, cue)
            self.assertEqual(plan[0][2], [0, 70])
            names = {1: ("01 First.flac", 0, 70), 2: ("02 Second.flac", 70, None)}
            rewritten = mlo.image_cue_text(cue, names)
            self.assertIn("INDEX 00 00:00:00", rewritten)
            self.assertIn("INDEX 01 00:00:05", rewritten)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
    def test_real_pcm_roundtrip_for_both_output_formats(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "album.wav"
            with wave.open(str(source), "wb") as w:
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(b"\x00\x00\x00\x00" * 88200)
            f = shutil.which("ffmpeg")
            # On non-Windows, exercise official Xiph flac directly.
            # refalac64.exe requires Windows and must not be substituted.
            from unittest.mock import patch
            encoders = [("FLAC", ".flac", shutil.which("flac"))]
            if mlo.IS_WIN:
                encoders.append(("ALAC", ".m4a", None))
            for mode, ext, available in encoders:
                if not mlo.IS_WIN and not available:
                    self.skipTest("The official FLAC CLI is not installed.")
                dst = Path(td) / ("01 Segment" + ext)
                with patch.object(mlo, "ensure_encoder",
                                  return_value=available or mlo.ensure_encoder(mode)), \
                     patch.object(mlo, "DATA", Path(td)):
                    mlo.convert(f, source, dst, mode, 0, 44100, "Segment", 1,
                                ffprobe=shutil.which("ffprobe"))
                self.assertTrue(dst.is_file())
                self.assertEqual(mlo.pcm_hash(f, source, 0, 44100), mlo.pcm_hash(f, dst))



class OptionalProcessingAndDigitalDates(unittest.TestCase):
    def test_january_first_placeholder_only_for_digital(self):
        self.assertEqual(mlo.digital_date_precision("2020-01-01"), "2020")
        self.assertEqual(mlo.digital_date_precision("2020-01-01", True), "2020-01-01")
        self.assertEqual(mlo.digital_date_precision("2020-01-02"), "2020-01-02")
        self.assertEqual(mlo.digital_date_precision("2020-02-01"), "2020-02-01")
        self.assertEqual(mlo.digital_date_precision("2020"), "2020")
        base = {"title": "Example", "date": "2020-01-01",
                "catalog": "", "barcode": "0123456789012",
                "root_artist": "Example", "notes": [],
                "release_type": "Album", "track_count": 11}
        digital = dict(base, physical=False)
        self.assertEqual(mlo.release_folder_target(digital),
                         "2020 - Example [0123456789012]")
        physical = dict(base, physical=True, country="JP",
                        edition_date="", country_provenance="verified-pressing")
        self.assertEqual(mlo.release_folder_target(physical),
                         "2020-01-01 - Example [JP - 0123456789012]")

    def test_audiochecker_optional_no_fabricated_log_requirement(self):
        info = {"metadata_verified": True, "physical": False, "notes": [],
                "barcode": "1234567890123", "catalog": ""}
        self.assertEqual(mlo.completion_reasons(info, [], [],
                                                checker_enabled=False), [])
        self.assertIn("Original auCDtect report missing",
                      mlo.completion_reasons(info, [], [],
                                             checker_enabled=True))
        self.assertNotIn("Original auCDtect report missing",
                         mlo.completion_reasons(
                             dict(info, physical=True, country_provenance="verified-pressing"),
                             [], [], checker_enabled=True))


    def test_whole_cue_image_preserved_when_split_and_encoding_disabled(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Album"
            dest = root / "Dest"
            source.mkdir()
            original = source / "album.flac"
            original.write_bytes(b"faked lossless album image data")
            (source / "album.cue").write_text(
                'FILE "album.flac" WAVE\n'
                '  TRACK 01 AUDIO\n'
                '    TITLE "A"\n'
                '    INDEX 01 00:00:00\n'
                '  TRACK 02 AUDIO\n'
                '    TITLE "B"\n'
                '    INDEX 01 00:02:00\n', encoding="utf-8")
            app = mlo.Organizer()
            app.enable_encoding = False
            app.enable_splitting = False
            app._artist_root = "TEST"
            app._credit_consensus = {}
            app._export_warnings = []
            app._export_notices = []
            app.encoding_workers = 1
            with patch.object(mlo, "probe", return_value={
                    "codec_name": "flac", "sample_rate": 44100}), \
                 patch.object(mlo, "convert") as encode:
                app._export_release(source, dest, "ALAC", "ffmpeg", "ffprobe")
                encode.assert_not_called()
            self.assertEqual((dest / "album.flac").read_bytes(), original.read_bytes())
            self.assertTrue((dest / "album.cue").is_file())
            self.assertFalse((dest / "01 A.m4a").exists())
            self.assertIn('FILE "album.flac" WAVE',
                          (dest / "album.cue").read_text(encoding="utf-8"))

    def test_image_splitting_uses_native_encoder_even_if_ordinary_encoding_off(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Album"
            dest = root / "Dest"
            source.mkdir()
            (source / "album.flac").write_bytes(b"fake audio")
            (source / "album.cue").write_text(
                'FILE "album.flac" WAVE\n'
                '  TRACK 01 AUDIO\n'
                '    TITLE "A"\n'
                '    INDEX 01 00:00:00\n'
                '  TRACK 02 AUDIO\n'
                '    TITLE "B"\n'
                '    INDEX 01 00:02:00\n', encoding="utf-8")
            app = mlo.Organizer()
            app.enable_encoding = False
            app.enable_splitting = True
            app._artist_root = "TEST"
            app._credit_consensus = {}
            app._export_warnings = []
            app._export_notices = []
            app.encoding_workers = 1
            calls = []
            def fake_convert(ff, src, dst, fmt, *args, **kwargs):
                calls.append((dst.name, fmt))
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(b"encoded-test-file")
            with patch.object(mlo, "probe", return_value={
                    "codec_name": "flac", "sample_rate": 44100}), \
                 patch.object(mlo, "convert", side_effect=fake_convert):
                app._export_release(source, dest, "ALAC", "ffmpeg", "ffprobe")
            self.assertEqual(calls, [("01 A.m4a", "ALAC"), ("02 B.m4a", "ALAC")])
            self.assertFalse((dest / "album.flac").exists())
            self.assertIn('FILE "02 B.m4a" WAVE',
                          (dest / "album.cue").read_text(encoding="utf-8"))



class CatalogIdentityAndPerformance20261014(unittest.TestCase):
    def test_catalog_equivalence_with_spaces_and_punctuation(self):
        self.assertEqual(mlo._catalog_key("BETA021"), mlo._catalog_key("BETA 021"))
        self.assertEqual(mlo._catalog_key("MFR001CD"), mlo._catalog_key("MFR-001 CD"))
        self.assertTrue(mlo._matches_catalog(
            {"label-info": [{"catalog-number": "BETA 021"}]}, "BETA021"))
        self.assertFalse(mlo._matches_catalog(
            {"label-info": [{"catalog-number": "BETA 022"}]}, "BETA021"))

    def test_digital_catalog_editions_are_searched_directly(self):
        from unittest.mock import patch
        cases = [
            ("2009-03-13 - Blow (Shock One RMX) - Single [HAB017]",
             "Blow (Shock One RMX)", "HAB017", 2),
            ("2009-03-31 - Get Funky - The Fear - Single [VPRVIP006]",
             "Get Funky / The Fear", "VPRVIP006", 2),
            ("2010-02-22 - Edge of Mind - EP [BETA021]",
             "Edge of Mind EP", "BETA 021", 4),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, mbtitle, mbcatalog, count in cases:
                with self.subTest(catalog=mbcatalog):
                    folder = root / name
                    folder.mkdir()
                    files = []
                    for index in range(1, count + 1):
                        track = folder / f"{index:02d} Track {index}.flac"
                        track.write_bytes(b"mocked audio")
                        files.append(track)
                    calls = []
                    def fake_mb(path, **kwargs):
                        calls.append(path)
                        if path.startswith("release/?"):
                            search = mlo.urllib.parse.parse_qs(
                                mlo.urllib.parse.urlparse(path).query)["query"][0]
                            self.assertIn("catno:", search)
                            return {"releases": [
                                {"id": "vinyl", "title": mbtitle,
                                 "media": [{"format": "12\" Vinyl",
                                            "track-count": count}]},
                                {"id": "digital", "title": mbtitle,
                                 "media": [{"format": "Digital Media",
                                            "track-count": count}]}]}
                        if path.startswith("release/digital?"):
                            return {
                                "id": "digital", "title": mbtitle,
                                "media": [{"format": "Digital Media",
                                           "track-count": count}],
                                "release-group": {
                                    "first-release-date": "2009-03-13",
                                    "primary-type": "EP"},
                                "label-info": [{"catalog-number": mbcatalog}],
                                "date": "2009-03-13",
                            }
                        raise AssertionError("Unexpected request: " + path)
                    with patch.object(mlo, "mb_json", side_effect=fake_mb):
                        identity = mlo.release_identity(
                            folder, files, default_artist="Camo & Krooked")
                    self.assertTrue(identity["metadata_verified"],
                                    str(identity))
                    self.assertEqual(identity["selected_release"], "digital")
                    self.assertEqual(mlo._catalog_key(identity["catalog"]),
                                     mlo._catalog_key(mbcatalog))
                    # Search metadata already identifies the vinyl candidate:
                    # no detail request should be spent on it.
                    self.assertFalse(any("release/vinyl?" in c for c in calls))
                    self.assertEqual(len(calls), 2)
                    self.assertIn("MusicBrainz exact catalog", identity["lookup_sources"])

    def test_spaced_catalog_fallback_search_only_when_needed(self):
        from unittest.mock import patch
        calls = []
        def lookup(path, **kwargs):
            search = mlo.urllib.parse.parse_qs(
                mlo.urllib.parse.urlparse(path).query)["query"][0]
            calls.append(search)
            if '"BETA021"' in search:
                return {"releases": []}
            return {"releases": [{"id": "correct", "title": "Edge of Mind EP"}]}
        with patch.object(mlo, "mb_json", side_effect=lookup):
            found = mlo._mb_catalog_search("BETA021")
        self.assertEqual(len(found), 1)
        self.assertEqual(len(calls), 2)
        self.assertIn('"BETA 021"', calls[1])

    def test_catalog_spaced_search_when_initial_results_are_vinyl_only(self):
        from unittest.mock import patch
        searches = []
        def fake_mb(path, **kwargs):
            query = mlo.urllib.parse.parse_qs(
                mlo.urllib.parse.urlparse(path).query)["query"][0]
            searches.append(query)
            if '"BETA021"' in query:
                return {"releases": [
                    {"id": "vinyl", "title": "Edge of Mind EP",
                     "media": [{"format": "12\" Vinyl", "track-count": 4}]}]}
            return {"releases": [
                {"id": "digital", "title": "Edge of Mind EP",
                 "media": [{"format": "Digital Media", "track-count": 4}]}]}
        with patch.object(mlo, "mb_json", side_effect=fake_mb):
            found = mlo._mb_catalog_search("BETA021", False, 4)
        self.assertEqual({x["id"] for x in found}, {"vinyl", "digital"})
        self.assertEqual(len(searches), 2)

    def test_incomplete_search_result_is_not_prematurely_discarded(self):
        incomplete = {"media": [{"format": "Digital Media"}],
                      "label-info": [{"label": {"name": "Beta Recordings"}}]}
        self.assertFalse(mlo._known_search_medium_conflict(incomplete, False, 4))
        self.assertTrue(mlo._known_search_medium_conflict(
            {"media": [{"format": "12\" Vinyl"}]}, False, 4))
        self.assertFalse(mlo._known_search_medium_conflict(
            {"media": [{"track-count": 4}]}, False, 4))
        self.assertTrue(mlo._known_search_medium_conflict(
            {"media": [{"format": "Digital Media", "track-count": 5}]},
            False, 4))

    def test_count_or_medium_conflict_rejected(self):
        item = {"media": [{"format": "Digital Media", "track-count": 2}]}
        self.assertTrue(mlo._release_medium_matches(item, False, 2))
        self.assertFalse(mlo._release_medium_matches(item, False, 3))
        self.assertFalse(mlo._release_medium_matches(item, True, 2))
        self.assertFalse(mlo._release_medium_matches(
            {"media": [{"format": "12\" Vinyl", "track-count": 2}]}, False, 2))
        self.assertFalse(mlo._release_medium_matches({"media": []}, False, 2))

    def test_source_eu_kept_when_musicbrainz_country_is_gb(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "2011-10-03 - Cross the Line [EU - NHS194CD]"
            folder.mkdir()
            files = []
            for idx in (1, 2):
                fp = folder / f"{idx:02d} Song.flac"
                fp.write_bytes(b"synthetic content")
                files.append(fp)
            def fake_mb(path, **kwargs):
                if path.startswith("release/?"):
                    return {"releases": [{"id": "exact", "title": "Cross the Line",
                                          "media": [{"format": "CD",
                                                     "track-count": 2}]}]}
                return {"id": "exact", "title": "Cross the Line", "country": "GB",
                        "media": [{"format": "CD", "track-count": 2}],
                        "label-info": [{"catalog-number": "NHS194CD"}],
                        "release-group": {"primary-type": "Album",
                                          "first-release-date": "2011-10-03"},
                        "date": "2011-10-03"}
            with patch.object(mlo, "mb_json", side_effect=fake_mb):
                info = mlo.release_identity(folder, files, "Camo & Krooked")
            self.assertTrue(info["metadata_verified"])
            self.assertEqual(info["country"], "EU")
            self.assertEqual(info["source_region"], "EU")
            self.assertEqual(info["musicbrainz_region"], "GB")
            self.assertEqual(info["country_provenance"], "source-supplied-region")
            self.assertEqual(
                mlo.release_folder_target(info),
                "2011-10-03 - Cross the Line [EU - NHS194CD]")
            self.assertEqual(mlo.completion_reasons(
                info, [], [{"results": 2}], checker_enabled=True), [])

    def test_known_destination_skips_musicbrainz_before_network(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "Input"
            dest = base / "Dest"
            source.mkdir()
            dest.mkdir()
            release = source / "2009-03-13 - Blow (Shock One RMX) - Single [HAB017]"
            release.mkdir()
            (release / "01 Blow.flac").write_bytes(b"test")
            (dest / release.name).mkdir()
            app = mlo.Organizer()
            with patch.object(mlo, "discover", return_value=[release]), \
                 patch.object(mlo, "release_identity",
                              side_effect=AssertionError("Unnecessary lookup")):
                organize(app, source, dest, "FLAC")
            self.assertEqual(app.counts["skipped"], 1)
            self.assertEqual(app.counts["failed"], 0)
            self.assertEqual(app.results[0]["status"], "skipped")
            self.assertIn("total_release", app.results[0]["timings_seconds"])




class NumericCatalogMultidiscAndInvalidCue20261015(unittest.TestCase):
    def test_numeric_catalog_is_not_a_barcode(self):
        self.assertFalse(mlo._valid_gtin("88883792232"))
        self.assertTrue(mlo._valid_gtin("888837922326"))
        self.assertFalse(mlo._valid_gtin("888837922327"))
        self.assertTrue(mlo._valid_gtin("0602478746901"))
        self.assertFalse(mlo._valid_gtin("MFR001CD"))

    def test_cue_count_for_two_images_is_total_track_count(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            cues, images = [], []
            for disc, count in ((1, 18), (2, 6)):
                folder = source / ("CD " + str(disc))
                folder.mkdir()
                audio = folder / "disc.flac"
                audio.write_bytes(b"placeholder")
                images.append(audio)
                cue = folder / "disc.cue"
                cue.write_text('FILE "disc.flac" WAVE\n' + "".join(
                    f'  TRACK {i:02d} AUDIO\n'
                    f'    TITLE "Track {i}"\n'
                    f'    INDEX 01 {i - 1:02d}:00:00\n'
                    for i in range(1, count + 1)), encoding="utf-8")
                cues.append(cue)
            counts, total = mlo._source_medium_track_counts(cues, images)
            self.assertEqual(counts, (18, 6))
            self.assertEqual(total, 24)
            correct = {"media": [{"format": "CD", "track-count": 18},
                                 {"format": "CD", "track-count": 6}]}
            wrong = {"media": [{"format": "CD", "track-count": 12},
                               {"format": "CD", "track-count": 12}]}
            self.assertTrue(mlo._release_medium_matches(correct, True, total, counts))
            self.assertFalse(mlo._release_medium_matches(wrong, True, total, counts))
            self.assertFalse(mlo._known_search_medium_conflict(correct, True, total, counts))
            self.assertTrue(mlo._known_search_medium_conflict(wrong, True, total, counts))

    def test_linked_subliminal_edition_selected_by_catalog_and_cue_count(self):
        from unittest.mock import patch
        release_id = "ffa45ff6-45a8-4e3b-bc89-a46e8ff0652c"
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / (
                "2013-05-13 - Subliminal (La face cachée) [EU - 88883792232]")
            folder.mkdir()
            files = []
            for disc, count in ((1, 18), (2, 6)):
                root = folder / f"CD {disc}"
                root.mkdir()
                audio = root / "album.flac"
                audio.write_bytes(b"fake fixture - nonaudio")
                cue = root / "album.cue"
                cue.write_text('FILE "album.flac" WAVE\n' + "".join(
                    f'  TRACK {i:02d} AUDIO\n'
                    f'    TITLE "Track {i}"\n'
                    f'    INDEX 01 {i - 1:02d}:00:00\n'
                    for i in range(1, count + 1)), encoding="utf-8")
                files.extend([audio, cue])
            calls = []
            def fake_mb(path, **kwargs):
                calls.append(path)
                if path.startswith("release/?"):
                    query = mlo.urllib.parse.parse_qs(
                        mlo.urllib.parse.urlparse(path).query)["query"][0]
                    self.assertEqual(query, 'catno:"88883792232"')
                    return {"releases": [{
                        "id": release_id, "title": "Subliminal : La Face cachée",
                        "media": [{"format": "CD", "track-count": 18},
                                  {"format": "CD", "track-count": 6}]}]}
                if path.startswith("release/" + release_id + "?"):
                    return {"id": release_id,
                            "title": "Subliminal : La Face cachée",
                            "barcode": "888837922326",
                            "country": "FR",
                            "media": [{"format": "CD", "track-count": 18},
                                      {"format": "CD", "track-count": 6}],
                            "label-info": [{"catalog-number": "88883792232"}],
                            "date": "2013-12-02",
                            "release-group": {
                                "primary-type": "Album",
                                "first-release-date": "2013-05-13"}}
                raise AssertionError(path)
            with patch.object(mlo, "discid_release_candidates", return_value=([], [])), \
                 patch.object(mlo, "mb_json", side_effect=fake_mb):
                result = mlo.release_identity(folder, files, "GIMS")
            self.assertEqual(result["selected_release"], release_id)
            self.assertTrue(result["metadata_verified"], result)
            self.assertEqual(result["catalog"], "88883792232")
            self.assertEqual(result["barcode"], "888837922326")
            self.assertEqual(result["country"], "EU")
            self.assertEqual(result["source_medium_counts"], [18, 6])
            self.assertEqual(result["track_count"], 24)
            self.assertIn("MusicBrainz exact catalog", result["lookup_sources"])
            self.assertEqual(len(calls), 2)

    def test_invalid_index00_after_01_keeps_whole_image_and_marks_partial(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "2013-05-13 - Subliminal [EU - 88883792232]"
            dest = root / "Destination"
            source.mkdir()
            image = source / "album.flac"
            image.write_bytes(b"test image bytes preserved exactly")
            cue = source / "album.cue"
            cue.write_text('FILE "album.flac" WAVE\n'
                '  TRACK 01 AUDIO\n'
                '    TITLE "First"\n'
                '    INDEX 01 00:00:00\n'
                '  TRACK 02 AUDIO\n'
                '    TITLE "Second"\n'
                '    INDEX 01 01:00:00\n'
                '    INDEX 00 01:01:00\n', encoding="utf-8")
            app = mlo.Organizer()
            app.enable_splitting = True
            app.enable_encoding = True
            app.encoding_workers = 1
            app._artist_root = "GIMS"
            app._credit_consensus = {}
            app._current_release_feature = ""
            app._current_identity = {
                "catalog": "88883792232", "physical": True,
                "metadata_verified": True}
            app._export_warnings = []
            app._export_notices = []
            with patch.object(mlo, "convert") as convert:
                app._export_release(source, dest, "ALAC", "ffmpeg", "ffprobe")
            convert.assert_not_called()
            self.assertEqual((dest / "album.flac").read_bytes(), image.read_bytes())
            self.assertTrue((dest / "88883792232.cue").is_file())
            self.assertIn("INDEX 00 01:01:00",
                          (dest / "88883792232.cue").read_text(encoding="utf-8"))
            self.assertTrue(any("unsafe splitting skipped" in w
                                for w in app._export_warnings))
            info = {"metadata_verified": True, "physical": True,
                    "country": "EU", "catalog": "88883792232",
                    "notes": []}
            self.assertIn("CUE or supporting-file fidelity not fully verified",
                          mlo.completion_reasons(info, app._export_warnings, []))




class PerRunLogging20261015(unittest.TestCase):
    def test_distinct_logs_with_collision_safe_names(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td, patch.object(mlo, "DATA", Path(td)):
            first = mlo._new_log("run")
            second = mlo._new_log("run")
            other = mlo._new_log("undo")
            self.assertEqual(len({first, second, other}), 3)
            self.assertEqual(first.parent, Path(td) / "logs")
            self.assertTrue(all(p.is_file() for p in (first, second, other)))
            self.assertFalse((Path(td) / "activity.log").exists())









class TitlesCueAndSoundtrack20261015(unittest.TestCase):
    def test_user_title_case_examples_folder_track_and_tags(self):
        cases = (
            ("Best life", "Best Life", "2021-09-29", "3616840189842"),
            ("SIN TI", "Sin Ti", "2024-02-15", "5054197975707"),
            ("JOE PESCI", "Joe Pesci", "2024-04-26", "3617387248313"),
        )
        for raw, expected, date, barcode in cases:
            with self.subTest(raw=raw):
                self.assertEqual(mlo.clean_release_title(raw), expected)
                self.assertEqual(mlo.normalized_title(raw), expected)
                self.assertEqual(mlo.track_filename(1, raw, ".m4a"),
                                 "01 " + expected + ".m4a")
                data = {"title": raw, "root_artist": "GIMS",
                        "release_type": "Single", "physical": False,
                        "track_count": 1, "date": date,
                        "barcode": barcode, "catalog": "", "notes": []}
                self.assertEqual(
                    mlo.release_folder_target(data),
                    date + " - " + expected + " - Single [" + barcode + "]")

    def test_casing_preserves_acronyms_mixed_case_feature_and_protected_names(self):
        self.assertEqual(mlo.normalized_title("3OH!3"), "3OH!3")
        self.assertEqual(mlo.normalized_title("G-DRAGON"), "G-DRAGON")
        self.assertEqual(mlo.picard_small_word_case("FIFA and DJ Snake"),
                         "FIFA and DJ Snake")
        self.assertEqual(mlo.picard_small_word_case("iPhone vs. eBay"),
                         "iPhone vs. eBay")
        self.assertEqual(mlo.normalized_title("Good Time (ft. Marian Hill)"),
                         "Good Time (ft. Marian Hill)")
        self.assertEqual(mlo.picard_small_word_case("THE OUTSIDE (OUTSIDERS VERSION)"),
                         "The Outside (Outsiders Version)")
        self.assertEqual(mlo.normalized_title("déjà vu"), "Déjà Vu")

    def test_cross_file_index00_belongs_to_prior_file_and_index01_to_current(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            previous = root / "03 J'me tire.m4a"
            current = root / "04 Freedom (ft. H Magnum).m4a"
            previous.write_bytes(b"audio 03")
            current.write_bytes(b"audio 04")
            cue = root / "88883792232.cue"
            cue.write_text(
                'FILE "03 J\'me tire.m4a" WAVE\n'
                '  TRACK 03 AUDIO\n    TITLE "J\'me tire"\n    INDEX 01 00:00:00\n'
                '  TRACK 04 AUDIO\n    TITLE "Freedom"\n    INDEX 00 04:09:65\n'
                'FILE "04 Freedom (ft. H Magnum).m4a" WAVE\n'
                '    INDEX 01 00:00:00\n', encoding="utf-8")
            parsed = mlo.cue_read(cue)
            self.assertEqual(parsed["records"][1]["file"], current.name)
            self.assertEqual(parsed["records"][1]["index_files"][0], previous.name)
            self.assertEqual(parsed["records"][1]["index_files"][1], current.name)
            self.assertTrue(mlo.cue_index_source_consistent(parsed["records"][1]))
            self.assertEqual(mlo.cue_image_plan(cue, parsed), [])
            refs = {previous.name.casefold(): "03 J'me Tire.m4a",
                    current.name.casefold(): "04 Freedom (ft. H Magnum).m4a"}
            rewritten = mlo.normal_cue_text(parsed, refs)
            self.assertIn("INDEX 00 04:09:65", rewritten)
            self.assertIn('FILE "03 J\'me Tire.m4a" WAVE', rewritten)
            self.assertIn('FILE "04 Freedom (ft. H Magnum).m4a" WAVE', rewritten)
            self.assertEqual(rewritten.count("INDEX 01 00:00:00"), 2)

    def test_same_file_inverted_index00_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "album.flac"
            path.write_bytes(b"placeholder")
            cue = path.with_suffix(".cue")
            cue.write_text('FILE "album.flac" WAVE\n'
                           '  TRACK 01 AUDIO\n    TITLE "A"\n'
                           '    INDEX 01 00:00:00\n'
                           '  TRACK 02 AUDIO\n    TITLE "B"\n'
                           '    INDEX 00 00:10:00\n'
                           '    INDEX 01 00:09:00\n', encoding="utf-8")
            parsed = mlo.cue_read(cue)
            self.assertFalse(mlo.cue_index_source_consistent(parsed["records"][1]))
            with self.assertRaisesRegex(ValueError, "same audio file"):
                mlo.cue_image_plan(cue, parsed)

    def test_cross_file_cue_export_preserves_audio_and_rewrites_index_references(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, out = root / "Release", root / "Output"
            inp.mkdir()
            original = {
                "03 J'me tire.m4a": b"audio track 3",
                "04 Freedom (ft. H Magnum).m4a": b"audio track 4",
            }
            for name, content in original.items():
                (inp / name).write_bytes(content)
            cue = inp / "old.cue"
            cue.write_text(
                'FILE "03 J\'me tire.m4a" WAVE\n'
                '  TRACK 03 AUDIO\n    TITLE "J\'me tire"\n'
                '    INDEX 01 00:00:00\n'
                '  TRACK 04 AUDIO\n    TITLE "Freedom"\n'
                '    INDEX 00 04:09:65\n'
                'FILE "04 Freedom (ft. H Magnum).m4a" WAVE\n'
                '    INDEX 01 00:00:00\n', encoding="utf-8")
            app = mlo.Organizer()
            app._current_identity = {"catalog": "88883792232",
                                     "physical": True,
                                     "metadata_verified": True}
            app._artist_root = "GIMS"
            app._export_warnings, app._export_notices = [], []
            app.enable_encoding = False
            app.enable_splitting = True
            app.encoding_workers = 1
            def meta(path):
                number, name = path.stem.split(" ", 1)
                return number, name, "GIMS"
            with patch.object(mlo, "metadata", side_effect=meta), \
                 patch.object(mlo, "probe", return_value={"codec_name": "alac"}), \
                 patch.object(mlo, "_update_copied_track_tags", return_value=None):
                app._export_release(inp, out, "ALAC", "ffmpeg", "ffprobe")
            expected_three = out / "03 J'me Tire.m4a"
            expected_four = out / "04 Freedom (ft. H Magnum).m4a"
            self.assertEqual(expected_three.read_bytes(), original["03 J'me tire.m4a"])
            self.assertEqual(expected_four.read_bytes(),
                             original["04 Freedom (ft. H Magnum).m4a"])
            result_cue = (out / "88883792232.cue").read_text(encoding="utf-8")
            self.assertIn("INDEX 00 04:09:65", result_cue)
            self.assertIn('FILE "03 J\'me Tire.m4a" WAVE', result_cue)
            self.assertIn('FILE "04 Freedom (ft. H Magnum).m4a" WAVE', result_cue)
            self.assertEqual(app._export_warnings, [])
            self.assertTrue(cue.exists())

    def test_arhbo_barcode_edition_two_track_single_even_with_subtitle_variant(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / (
                "2022-11-19 - Arhbo [Music from the FIFA World Cup Qatar 2022 "
                "Official Soundtrack] [197089993382]")
            folder.mkdir()
            files = [folder / "01 Arhbo.m4a",
                     folder / "02 Arhbo (FIFA Walkout Anthem).m4a"]
            for f in files:
                f.write_bytes(b"audio")
            release_id = "e4fba227-a357-4dda-9982-455b5ab21202"
            search = {"releases": [{
                "id": release_id, "title": "Arhbo",  # Index may omit soundtrack note.
                "barcode": "197089993382",
                "media": [{"format": "Digital Media", "track-count": 2}]}]}
            detail = {"id": release_id,
                      "title": ("Arhbo (music from the FIFA World Cup Qatar 2022 "
                                "Official Soundtrack)"),
                      "barcode": "197089993382", "date": "2022-11-19",
                      "media": [{"format": "Digital Media", "track-count": 2}],
                      "label-info": [],
                      "release-group": {"primary-type": "Single",
                                        "secondary-types": ["Soundtrack"],
                                        "first-release-date": "2022-11-19"}}
            urls = []
            def musicbrainz(path, **kwargs):
                urls.append(path)
                return search if path.startswith("release/?") else detail
            with patch.object(mlo, "mb_json", side_effect=musicbrainz):
                identity = mlo.release_identity(folder, files, "GIMS")
            self.assertEqual(identity["selected_release"], release_id, identity)
            self.assertTrue(identity["metadata_verified"], identity)
            self.assertEqual(identity["release_type"], "Single")
            self.assertEqual(identity["track_count"], 2)
            self.assertEqual(identity["barcode"], "197089993382")
            self.assertEqual(
                mlo.release_folder_target(identity),
                "2022-11-19 - Arhbo (Music from the FIFA World Cup Qatar 2022 "
                "Official Soundtrack) - Single [197089993382]")
            self.assertTrue(any("barcode%3A197089993382" in p for p in urls), urls)
            self.assertFalse(any("catno%3A" in p for p in urls), urls)

    def test_soundtrack_title_match_does_not_ignore_remixes(self):
        self.assertGreaterEqual(mlo._release_title_similarity(
            "Arhbo [Music from the FIFA World Cup Qatar 2022 Official Soundtrack]",
            "Arhbo"), 0.95)
        self.assertEqual(mlo._release_title_similarity(
            "Arhbo (Music from the FIFA World Cup Qatar 2022 Official Soundtrack)",
            "Arhbo [music from the FIFA World Cup Qatar 2022 Official Soundtrack]"),
            1.0)
        self.assertLess(mlo._release_title_similarity(
            "Arhbo (Music from the FIFA World Cup Qatar 2022 Official Soundtrack)",
            "Arhbo (Club Remix)"), 0.82)




class Artwork20261015(unittest.TestCase):
    @staticmethod
    def jpeg_stub():
        # Sufficient for SOF and JPEG magic tests, not a decoded image.
        return (b"\xff\xd8" + b"\xff\xe0\x00\x10" + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" +
                b"\xff\xc0\x00\x11\x08\x0b\xb8\x0b\xb8\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01" +
                b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00" + b"\x00" * 48 + b"\xff\xd9")

    def test_upc_ean_equivalence_and_catalog_rejection(self):
        self.assertEqual(mlo._cover_upcs("886445932034"),
                         ["886445932034", "0886445932034"])
        self.assertEqual(mlo._cover_upcs("0886445932034"),
                         ["0886445932034", "886445932034"])
        self.assertEqual(mlo._cover_upcs("88883792232"), [])
        self.assertEqual(mlo._cover_upcs("ABC123"), [])

    def test_maximum_apple_image_url_and_safe_hosts(self):
        thumb = ("https://is1-ssl.mzstatic.com/image/thumb/Music71/v4/"
                 "fc/2d/f0/fc2df0b6-31db-871b-2cf7-258b06cff487/"
                 "886445932034.jpg/600x600bb.jpg")
        candidates = mlo._cover_apple_urls(thumb)
        self.assertEqual(candidates[0],
                         thumb.replace("600x600bb.jpg", "10000x0w-999.jpg"))
        self.assertEqual(candidates[-1], thumb)
        self.assertEqual(mlo._cover_apple_urls("http://is1-ssl.mzstatic.com/a.jpg/100.jpg"), [])
        self.assertEqual(mlo._cover_apple_urls("https://not-apple.com/a.jpg/100.jpg"), [])

    def test_jpeg_signature_and_image_dimensions_not_png_renamed(self):
        self.assertEqual(mlo._cover_jpeg_size(self.jpeg_stub()), (3000, 3000))
        with self.assertRaisesRegex(ValueError, "JPEG"):
            mlo._cover_jpeg_size(b"\x89PNG\r\n\x1a\n" + b"a" * 200)
        with self.assertRaisesRegex(ValueError, "complete JPEG"):
            mlo._cover_jpeg_size(self.jpeg_stub()[:-2])

    def test_apple_upc_api_and_first_high_resolution_jpeg(self):
        from unittest.mock import patch
        folder = "À Contrecœur (Pilule Violette)"
        body = {"resultCount": 1, "results": [{
            "wrapperType": "collection",
            "collectionName": folder + " - EP",
            "artworkUrl100": ("https://is1-ssl.mzstatic.com/image/thumb/"
                              "Music71/v4/abc/886445932034.jpg/100x100bb.jpg"),
            "collectionViewUrl": "https://music.apple.com/us/album/1234"}]}
        urls = []
        def retrieve(url, hosts, *args):
            urls.append(url)
            return self.jpeg_stub()
        with patch.object(mlo, "_cover_json", return_value=body) as lookup, \
             patch.object(mlo, "_cover_request", side_effect=retrieve):
            cover, notes = mlo._cover_apple("886445932034", folder + " - EP", threading.Event())
        self.assertIsNotNone(cover)
        self.assertEqual(cover["provider"], "Apple Music")
        self.assertEqual(cover["size"], "3000x3000")
        self.assertTrue(urls[0].endswith("/10000x0w-999.jpg"))
        self.assertIn("upc=886445932034", lookup.call_args[0][0])
        self.assertEqual(notes, [])

    def test_apple_provider_miss_still_falls_back_without_guessing(self):
        from unittest.mock import patch
        with patch.object(mlo, "_cover_json", return_value={"resultCount": 0, "results": []}):
            cover, reasons = mlo._cover_apple(
                "886445932034", "À Contrecœur (Pilule Violette)", threading.Event())
        self.assertIsNone(cover)
        self.assertEqual(reasons, [])

    def test_spotify_link_discovery_exact_gtin_via_musicbrainz(self):
        from unittest.mock import patch
        spotify_id = "3jjkjjjjjjjjjjjjjjjjjj"
        album_url = "https://open.spotify.com/album/" + spotify_id
        release_id = "12222222-2222-2222-2222-222222222222"
        def mb(path):
            if path.startswith("release/?"):
                return {"releases": [{"id": release_id, "barcode": "886445932034",
                                      "title": "À Contrecœur (Pilule Violette)"}]}
            if path.startswith("release-group/"):
                return {"relations": [{"url": {"resource": album_url}}]}
            return {"release-group": {"id": "some-group"},
                    "relations": [{"url": {"resource": album_url}}]}
        with patch.object(mlo, "mb_json", side_effect=mb), \
             patch.object(mlo, "_cover_json", return_value={
                 "thumbnail_url": "https://i.scdn.co/image/ab67616d0000b273ABC"}), \
             patch.object(mlo, "_cover_request", return_value=self.jpeg_stub()):
            cover, reasons = mlo._cover_spotify(
                "886445932034", "À Contrecœur (Pilule Violette)", threading.Event())
        self.assertEqual(cover["provider"], "Spotify")
        self.assertEqual(cover["link"], album_url)
        self.assertEqual(cover["size"], "3000x3000")

    def test_atomic_create_only_and_hash_undo(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "2016-08-26 - À Contrecœur (Pilule Violette) - EP [886445932034]"
            folder.mkdir()
            journal = {"root": str(root), "layout": "destination-root", "kind": "artwork", "created": []}
            with patch.object(mlo, "ARTWORK_UNDO", root / "undo.json"):
                art = self.jpeg_stub()
                target, written = mlo._cover_save(root, folder, art, journal)
                self.assertTrue(written)
                self.assertEqual(target, root / (folder.name + ".jpg"))
                self.assertEqual(target.read_bytes(), art)
                same, rewritten = mlo._cover_save(root, folder, b"different", journal)
                self.assertFalse(rewritten)
                self.assertEqual(target.read_bytes(), art)
                app = mlo.Organizer()
                app._undo_artwork(journal)
                self.assertFalse(target.exists())
                self.assertTrue(folder.is_dir())
                self.assertFalse((root / "undo.json").exists())

    def test_undo_refuses_folder_outside_recorded_destination(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            destination = root / "Sorted"
            destination.mkdir()
            unrelated_folder = root / "Unrelated"
            unrelated_folder.mkdir()
            (unrelated_folder / "keep.txt").write_text("user data")
            manifest = {"dest": str(destination), "pending": None, "created": [
                {"path": str(unrelated_folder),
                 "files": {"keep.txt": mlo.sha(unrelated_folder / "keep.txt")}}]}
            with patch.object(mlo, "UNDO", root / "undo.json"):
                app = mlo.Organizer()
                app._undo(manifest)
            self.assertIn("outside its destination", app.status)
            self.assertTrue((unrelated_folder / "keep.txt").is_file())

    def test_undo_refuses_changed_artwork(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "2020-01-01 - Example [1234567890128]"
            folder.mkdir()
            manifest = {"root": str(root), "layout": "destination-root", "created": []}
            with patch.object(mlo, "ARTWORK_UNDO", root / "art-undo.json"):
                image, _ = mlo._cover_save(root, folder, self.jpeg_stub(), manifest)
                image.write_bytes(b"changed")
                app = mlo.Organizer()
                app._undo_artwork(manifest)
                self.assertTrue(image.exists())
                self.assertIn("Undo blocked", app.status)

    def test_artwork_existing_destination_not_overwritten_no_download(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "2016-08-26 - À Contrecœur (Pilule Violette) - EP [886445932034]"
            folder.mkdir()
            (folder / "01 Song.m4a").write_bytes(b"song")
            cover = root / (folder.name + ".jpg")
            cover.write_bytes(b"existing cover")
            app = mlo.Organizer()
            with patch.object(mlo, "ARTWORK_UNDO", root / "art-undo.json"), \
                 patch.object(mlo, "_cover_apple", side_effect=AssertionError("Must skip lookup")), \
                 patch.object(mlo, "_cover_spotify", side_effect=AssertionError("Must skip fallback")):
                app._download_artwork(root, [folder])
                self.assertEqual(app.counts["skipped"], 1)
                self.assertEqual(cover.read_bytes(), b"existing cover")



    def test_cd_catalog_number_resolves_single_verified_barcode(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            release = Path(td) / "2013-05-13 - Subliminal - La Face Cachée [EU - 88883792232]"
            release.mkdir()
            (release / "01 Example.m4a").write_bytes(b"placeholder")
            entry = {"title": "Subliminal (La face cachée)", "id": "cd-one"}
            detail = {"barcode": "888837922326",
                      "label-info": [{"catalog-number": "88883792232"}],
                      "media": [{"format": "CD", "track-count": 18}]}
            with patch.object(mlo, "_mb_catalog_search", return_value=[entry]) as catalog_search, \
                 patch.object(mlo, "mb_json", return_value=detail):
                self.assertEqual(mlo._cover_release_barcode(release), "888837922326")
            catalog_search.assert_called_once()

    def test_artwork_operation_creates_jpg_in_destination_root_without_touching_audio(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "2016-08-26 - À Contrecœur (Pilule Violette) - EP [886445932034]"
            folder.mkdir()
            source = folder / "01 Ma Beauté.m4a"
            source.write_bytes(b"original unchanged audio")
            art = {"bytes": self.jpeg_stub(), "provider": "Apple Music",
                   "size": "3000x3000", "link": "https://music.apple.com/us/album/1234"}
            app = mlo.Organizer()
            with patch.object(mlo, "ARTWORK_UNDO", root / "artwork-undo.json"), \
                 patch.object(mlo, "_cover_apple", return_value=(art, [])), \
                 patch.object(mlo, "_cover_spotify", side_effect=AssertionError("Apple available")):
                app._download_artwork(root, [folder])
                output = root / (folder.name + ".jpg")
                self.assertTrue(output.is_file())
                self.assertEqual(output.read_bytes(), self.jpeg_stub())
                self.assertEqual(source.read_bytes(), b"original unchanged audio")
                self.assertEqual(app.counts["done"], 1)
                self.assertTrue((root / "artwork-undo.json").is_file())
                app._undo_artwork(mlo.read_json(root / "artwork-undo.json", {}))
                self.assertFalse(output.exists())
                self.assertTrue(source.is_file())

    def test_artwork_do_not_guess_ambiguous_cd_barcode_editions(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            release = Path(td) / "2013-05-13 - Subliminal [EU - 88883792232]"
            release.mkdir()
            detail = {"label-info": [{"catalog-number": "88883792232"}],
                      "media": [{"format": "CD"}]}
            with patch.object(mlo, "_mb_catalog_search", return_value=[
                {"id": "one", "title": "Subliminal"},
                {"id": "two", "title": "Subliminal"}]), \
                 patch.object(mlo, "mb_json", side_effect=lambda path: dict(
                     detail, barcode=("888837922326" if "/one?" in path
                                      else "197089993382"))):
                self.assertEqual(mlo._cover_release_barcode(release), "")

    def test_new_artwork_output_does_not_modify_previous_nested_jpg(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            release = root / "2016-08-26 - À Contrecœur (Pilule Violette) - EP [886445932034]"
            release.mkdir()
            (release / "01 Ma Beauté.m4a").write_bytes(b"untouched audio")
            old_nested = release / (release.name + ".jpg")
            old_nested.write_bytes(b"previous v0.3.18 nested cover")
            art = {"bytes": self.jpeg_stub(), "provider": "Apple Music",
                   "size": "3000x3000", "link": "https://music.apple.com/us/album/123"}
            with patch.object(mlo, "ARTWORK_UNDO", root / "cover-journal.json"), \
                 patch.object(mlo, "_cover_apple", return_value=(art, [])):
                app = mlo.Organizer()
                app._download_artwork(root, [release])
                new_flat = root / (release.name + ".jpg")
                self.assertTrue(new_flat.is_file())
                self.assertEqual(new_flat.read_bytes(), self.jpeg_stub())
                self.assertEqual(old_nested.read_bytes(), b"previous v0.3.18 nested cover")
                self.assertEqual(app.counts["done"], 1)

    def test_duplicate_release_folder_names_do_not_choose_wrong_cover(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "Artist A" / "2022-11-19 - Arhbo [197089993382]"
            second = root / "Artist B" / first.name
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            for release in (first, second):
                (release / "01 Test.m4a").write_bytes(b"audio")
            with patch.object(mlo, "ARTWORK_UNDO", root / "art-journal.json"), \
                 patch.object(mlo, "_cover_apple", side_effect=AssertionError(
                     "Must not download ambiguous same-name releases")):
                app = mlo.Organizer()
                app._download_artwork(root, [first, second])
                self.assertEqual(app.counts["partial"], 2)
                self.assertFalse((root / (first.name + ".jpg")).exists())
                self.assertTrue(all("Duplicate release" in x["message"]
                                    for x in app.results))

    def test_legacy_v0318_nested_artwork_undo_still_supported(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            release = root / "2022-11-19 - Arhbo [197089993382]"
            release.mkdir()
            jpeg = self.jpeg_stub()
            old_cover = release / (release.name + ".jpg")
            old_cover.write_bytes(jpeg)
            old_journal = {"root": str(root), "created": [
                {"path": str(old_cover), "sha256": mlo.hashlib.sha256(jpeg).hexdigest()}]}
            with patch.object(mlo, "ARTWORK_UNDO", root / "artwork-undo.json"):
                app = mlo.Organizer()
                app._undo_artwork(old_journal)
            self.assertFalse(old_cover.exists())
            self.assertTrue(release.is_dir())

    def test_new_flat_artwork_undo_rejects_wrong_release_name(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            release = root / "2022-11-19 - Arhbo [197089993382]"
            release.mkdir()
            journal = {"root": str(root), "layout": "destination-root", "created": []}
            with patch.object(mlo, "ARTWORK_UNDO", root / "artwork-undo.json"):
                target, created = mlo._cover_save(root, release, self.jpeg_stub(), journal)
                self.assertTrue(created)
                journal["created"][0]["release_name"] = "Different Album"
                app = mlo.Organizer()
                app._undo_artwork(journal)
                self.assertTrue(target.exists())
                self.assertIn("Undo blocked", app.status)

    def test_v0318_artwork_journal_archived_before_flat_rerun(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            appdata = root / "appdata"
            appdata.mkdir()
            old = appdata / "artwork-undo.json"
            record = {"root": str(root), "created": [
                {"path": "previous-nested-cover.jpg", "sha256": "abc"}]}
            mlo.write_json(old, record)
            with patch.object(mlo, "DATA", appdata), \
                 patch.object(mlo, "ARTWORK_UNDO", old):
                archive = mlo._cover_archive_prior_undo()
                self.assertFalse(old.exists())
                self.assertTrue(archive.is_file())
                self.assertEqual(mlo.read_json(archive, {}), record)
                self.assertEqual(archive.parent.name, "artwork-undo-history")
                self.assertIsNone(mlo._cover_archive_prior_undo())

    def test_artwork_archive_refuses_unreadable_prior_journal(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "artwork-undo.json"
            target.write_bytes(b"invalid")
            with patch.object(mlo, "DATA", root), \
                 patch.object(mlo, "ARTWORK_UNDO", target):
                with self.assertRaisesRegex(ValueError, "unreadable"):
                    mlo._cover_archive_prior_undo()
            self.assertTrue(target.exists())



class EverythingEverything20261030(unittest.TestCase):
    def test_musicbrainz_europe_code_renders_as_eu_not_xe(self):
        info = {"title": "Arc (Deluxe Edition)", "date": "2013-01-11",
                "catalog": "88725473752", "physical": True,
                "country": "XE", "release_type": "Album", "notes": []}
        self.assertEqual(
            mlo.release_folder_target(info),
            "2013-01-11 - Arc (Deluxe Edition) [EU - 88725473752]")
        self.assertEqual(info["country"], "XE")  # Preserve MusicBrainz provenance.
        info["country"] = "EU"
        self.assertEqual(
            mlo.release_folder_target(info),
            "2013-01-11 - Arc (Deluxe Edition) [EU - 88725473752]")

    def test_arc_two_disc_siblings_become_one_release(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            disc1 = root / "2013 - Arc (Deluxe Edition) CD 1"
            disc2 = root / "2013 - Arc (Deluxe Edition) CD 2"
            unrelated = root / "2017.08 - A Fever Dream"
            for folder, count in ((disc1, 13), (disc2, 6), (unrelated, 2)):
                folder.mkdir()
                for number in range(1, count + 1):
                    (folder / f"{number:02d} Song {number}.flac").write_bytes(b"audio")
            grouped = mlo.group_disc_releases(mlo.discover(root))
            self.assertEqual(len(grouped), 2)
            arc = next(x for x in grouped if "Arc" in x[0])
            self.assertEqual(arc[0], "2013 - Arc (Deluxe Edition)")
            self.assertEqual(arc[1], (disc1, disc2))
            self.assertEqual(mlo.source_disc_counts(arc[1]), (13, 6))

    def test_orphan_cd2_is_never_grouped_or_lost(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            disc2 = root / "2013 - Arc (Deluxe Edition) CD 2"
            disc2.mkdir()
            (disc2 / "01 Awe-Arc.flac").write_bytes(b"audio")
            grouped = mlo.group_disc_releases(mlo.discover(root))
            self.assertEqual(grouped, [(disc2.name, (disc2,))])

    def test_incomplete_disc_set_and_digital_disc_labels_not_forced_to_cd(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            names = ("2013 - Arc (Deluxe Edition) CD 1",
                     "2013 - Arc (Deluxe Edition) CD 3",
                     "2020 - Digital Album Disc 1",
                     "2020 - Digital Album Disc 2")
            for name in names:
                folder = root / name
                folder.mkdir()
                (folder / "01 Track.flac").write_bytes(b"audio")
            grouped = mlo.group_disc_releases(mlo.discover(root))
            self.assertEqual(len(grouped), 4)
            self.assertTrue(all(len(members) == 1 for _, members in grouped))

    def test_deeper_sea_date_and_non_rip_log(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "2018.02 - A Deeper Sea - EP"
            folder.mkdir()
            for i in range(1, 5):
                (folder / f"{i:02d} Song.flac").write_bytes(b"audio")
            (folder / "analysis.log").write_text("spectrum scan complete", encoding="utf-8")
            identity = mlo.release_identity(folder, mlo.collect_files(folder),
                                            "Everything Everything", allow_network=False)
            self.assertFalse(identity["physical"])
            self.assertEqual(identity["date"], "2018-02")
            self.assertEqual(identity["title"], "A Deeper Sea - EP")
            self.assertEqual(mlo.release_folder_target(identity),
                             "2018-02 - A Deeper Sea - EP")

    def test_genuine_eac_rip_log_stays_physical(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "2018.02 - A Deeper Sea - EP"
            folder.mkdir()
            (folder / "01 Song.flac").write_bytes(b"audio")
            (folder / "rip.log").write_text(
                "Exact Audio Copy V1.6 from 23. October 2020\nEAC extraction logfile",
                encoding="utf-8")
            identity = mlo.release_identity(folder, mlo.collect_files(folder),
                                            "Everything Everything", allow_network=False)
            self.assertTrue(identity["physical"])

    def test_windows_utf16_eac_rip_log_stays_physical(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "2018.02 - A Deeper Sea - EP"
            folder.mkdir()
            (folder / "01 Song.flac").write_bytes(b"audio")
            (folder / "rip.log").write_bytes(
                "Exact Audio Copy V1.6\r\nEAC extraction logfile".encode("utf-16"))
            identity = mlo.release_identity(
                folder, mlo.collect_files(folder), "Everything Everything",
                allow_network=False)
            self.assertTrue(identity["physical"])

    def test_deeper_sea_searches_base_title_without_ep_suffix(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "2018.02 - A Deeper Sea - EP"
            folder.mkdir()
            for number in range(1, 5):
                (folder / f"{number:02d} Song.flac").write_bytes(b"audio")
            candidate = {"id": "deeper-sea", "title": "A Deeper Sea",
                         "media": [{"format": "Digital Media", "track-count": 4}]}
            detail = dict(candidate, **{
                "label-info": [{"catalog-number": "EVEV-EP"}], "date": "2018-02-27",
                "release-group": {"first-release-date": "2018-02-27", "primary-type": "EP"}})
            searches = []
            def fake_mb(path, **kwargs):
                if path.startswith("release/?"):
                    searches.append(mlo.urllib.parse.parse_qs(
                        path.partition("?")[2]).get("query", [""])[0])
                    return {"releases": [candidate] if
                            'release:"A Deeper Sea"' in searches[-1] else []}
                if path.startswith("release/deeper-sea?"):
                    return detail
                raise AssertionError(path)
            with patch.object(mlo, "mb_json", side_effect=fake_mb):
                identity = mlo.release_identity(
                    folder, mlo.collect_files(folder), "Everything Everything")
            self.assertTrue(identity["metadata_verified"], searches)
            self.assertEqual(identity["release_type"], "EP")
            self.assertEqual(mlo.release_folder_target(identity),
                             "2018-02-27 - A Deeper Sea - EP [EVEV-EP]")

    def test_arc_two_disc_export_keeps_track_names_separate(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Input"
            output = root / "Output"
            for n, count in ((1, 13), (2, 6)):
                disc = source / f"2013 - Arc (Deluxe Edition) CD {n}"
                disc.mkdir(parents=True)
                for num in range(1, count + 1):
                    (disc / f"{num:02d} Song {num}.flac").write_bytes(
                        f"disc{n}-track{num}".encode())
            discs = tuple(sorted(source.iterdir()))
            with patch.object(mlo, "DATA", root / "data"):
                app = mlo.Organizer()
                app.encoding_workers = 2
                app.enable_encoding = False
                app._artist_root = "Everything Everything"
                with patch.object(mlo, "probe", return_value={"codec_name": "flac"}), \
                     patch.object(mlo, "_update_copied_track_tags"):
                    app._export_release(source, output, "FLAC", "ffmpeg", "ffprobe",
                                        source_files=[f for disc in discs
                                                      for f in mlo.collect_files(disc)],
                                        disc_folders=discs)
            self.assertEqual(len(list((output / "CD 1").glob("*.flac"))), 13)
            self.assertEqual(len(list((output / "CD 2").glob("*.flac"))), 6)
            self.assertTrue((output / "CD 1" / "01 Song 1.flac").is_file())
            self.assertTrue((output / "CD 2" / "01 Song 1.flac").is_file())

    def test_grouped_cd_cue_and_log_remain_in_their_own_disc(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Input"
            output = root / "Output"
            for n in (1, 2):
                disc = source / f"Arc Deluxe CD {n}"
                disc.mkdir(parents=True)
                (disc / "01 Song.flac").write_bytes(f"disc {n}".encode())
                (disc / "rip.cue").write_text(
                    'FILE "01 Song.flac" WAVE\n  TRACK 01 AUDIO\n'
                    '    TITLE "Song"\n    INDEX 01 00:00:00\n', encoding="utf-8")
                (disc / "rip.log").write_text(
                    "Exact Audio Copy V1.6\nEAC extraction logfile", encoding="utf-8")
            discs = tuple(sorted(source.iterdir()))
            files = [fp for disc in discs for fp in mlo.collect_files(disc)]
            with patch.object(mlo, "DATA", root / "private"):
                app = mlo.Organizer()
                app.enable_encoding = False
                app.encoding_workers = 2
                app._artist_root = "Everything Everything"
                app._current_identity = {"physical": True, "catalog": "CAT-123",
                                         "metadata_verified": True}
                with patch.object(mlo, "probe", return_value={"codec_name": "flac"}), \
                     patch.object(mlo, "_update_copied_track_tags"):
                    app._export_release(
                        source, output, "FLAC", "ff", "ffprobe",
                        source_files=files, disc_folders=discs)
            for n in (1, 2):
                self.assertTrue((output / f"CD {n}" / "CAT-123.cue").is_file())
                self.assertTrue((output / f"CD {n}" / "CAT-123.log").is_file())
                self.assertIn('FILE "01 Song.flac"',
                              (output / f"CD {n}" / "CAT-123.cue").read_text())

    def test_arc_deluxe_identity_uses_complete_medium_counts(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            source = Path(td)
            discs = []
            for disc_number, count in ((1, 13), (2, 6)):
                disc = source / f"2013 - Arc (Deluxe Edition) CD {disc_number}"
                disc.mkdir()
                for number in range(1, count + 1):
                    (disc / f"{number:02d} Song.flac").write_bytes(b"audio")
                discs.append(disc)
            standard = {"id": "standard", "title": "Arc",
                        "media": [{"format": "CD", "track-count": 13}]}
            # A genuine two-CD deluxe release can be indexed simply as "Arc".
            deluxe = {"id": "deluxe", "title": "Arc",
                      "media": [{"format": "CD", "track-count": 13},
                                {"format": "CD", "track-count": 6}]}
            full_deluxe = dict(deluxe, **{
                "label-info": [{"catalog-number": "88725473752"}],
                "country": "GB", "date": "2013-01-14",
                "barcode": "0887254737520",
                "release-group": {"first-release-date": "2013-01-11",
                                  "primary-type": "Album"}})
            def fake_mb(path, **kwargs):
                if path.startswith("release/?"):
                    return {"releases": [standard, deluxe]}
                if "release/deluxe" in path:
                    return full_deluxe
                if "release/standard" in path:
                    return standard
                raise AssertionError(path)
            with patch.object(mlo, "mb_json", side_effect=fake_mb):
                result = mlo.release_identity(
                    source, [f for disc in discs for f in mlo.collect_files(disc)],
                    "Everything Everything", source_name="2013 - Arc (Deluxe Edition)",
                    disc_folders=tuple(discs))
            self.assertTrue(result["metadata_verified"])
            self.assertEqual(result["selected_release"], "deluxe")
            self.assertEqual(result["source_medium_counts"], [13, 6])
            self.assertEqual(result["catalog"], "88725473752")
            self.assertEqual(mlo.release_folder_target(result),
                             "2013-01-11 - Arc (Deluxe Edition) [GB - 88725473752]")

    def test_organize_arc_siblings_as_one_batch_result(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Everything Everything - UPDATED"
            destination = root / "Sorted"
            for disc_number, count in ((1, 13), (2, 6)):
                disc = source / f"2013 - Arc (Deluxe Edition) CD {disc_number}"
                disc.mkdir(parents=True)
                for number in range(1, count + 1):
                    (disc / f"{number:02d} Song {number}.flac").write_bytes(b"audio")
            metadata = {"title": "Arc (Deluxe Edition)", "date": "2013-01-11",
                        "catalog": "88725473752", "barcode": "",
                        "physical": True, "country": "GB", "edition_date": "",
                        "release_type": "Album", "metadata_verified": True,
                        "notes": [], "root_artist": "Everything Everything",
                        "track_count": 19}
            seen = []
            def verify_identity(folder, files, default_artist, **kwargs):
                seen.append((kwargs.get("source_name"), kwargs.get("disc_folders"),
                             sum(fp.suffix == ".flac" for fp in files)))
                return dict(metadata)
            with patch.object(mlo, "DATA", root / "private"), \
                 patch.object(mlo, "UNDO", root / "undo.json"), \
                 patch.object(mlo, "REPORT", root / "report.json"), \
                 patch.object(mlo, "HISTORY", root / "history"), \
                 patch.object(mlo, "release_identity", side_effect=verify_identity), \
                 patch.object(mlo, "ensure_ffmpeg", return_value=("ff", "ffprobe")), \
                 patch.object(mlo, "probe", return_value={"codec_name": "flac"}), \
                 patch.object(mlo, "_update_copied_track_tags"), \
                 patch.object(mlo, "collection_credit_consensus", return_value={}):
                app = mlo.Organizer()
                app.enable_encoding = False
                app.enable_checker = False
                organize(app, source, destination, "FLAC")
            self.assertEqual(app.counts["total"], 1)
            self.assertEqual(app.counts["done"], 1, app.results)
            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0][0], "2013 - Arc (Deluxe Edition)")
            self.assertEqual(len(seen[0][1]), 2)
            self.assertEqual(seen[0][2], 19)
            album = destination / "2013-01-11 - Arc (Deluxe Edition) [GB - 88725473752]"
            self.assertEqual(len(list((album / "CD 1").glob("*.flac"))), 13)
            self.assertEqual(len(list((album / "CD 2").glob("*.flac"))), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
