"""Regression and UI contract checks that used to run inside the app as --ui-self-test."""
import errno
import inspect
import itertools
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import unittest
from pathlib import Path
from typing import Dict, List, Set, Tuple

from test_audio_safety import mcc


def _acoustic_first_identity_regression_self_test() -> None:
    """Pinocchio Story: wrong titles and disabled Live cannot conceal matches."""
    # Deterministic, nonidentical 320-frame Chromaprints with near-perfect
    # acoustic alignment. The low-bit mutations preserve robust token evidence.
    base_fp = tuple(
        ((i * 0x9E3779B9) ^ 0x12345678) & 0xFFFFFFFF for i in range(320)
    )
    remastered_fp = tuple(
        value ^ (1 << (i % 12)) if i % 13 == 0 else value
        for i, value in enumerate(base_fp)
    )
    other_fp = tuple(value ^ 0xFFFFFFFF for value in base_fp)
    base = mcc.Track(
        -4201, Path("12 Pinocchio Story.flac"), 12,
        title="Pinocchio Story", artist="Kanye West", album="808s & Heartbreak",
        duration=361.6, fingerprint=base_fp,
    )
    live_label = mcc.Track(
        -4202, Path("12 Pinocchio Story (Freestyle Live from Singapore).m4a"), 12,
        title="Pinocchio Story (Freestyle Live from Singapore)",
        artist="Kanye West", album="808s & Heartbreak",
        duration=361.6, fingerprint=remastered_fp,
    )
    wrong_title = mcc.Track(
        -4203, Path("unrelated-filename.flac"), 18,
        title="Completely Wrong Title", artist="Unknown", album="Wrong Album",
        duration=361.6, fingerprint=remastered_fp,
    )
    genuinely_different = mcc.Track(
        -4204, Path("another audio.flac"), 19,
        title="Pinocchio Story", artist="Kanye West",
        duration=361.6, fingerprint=other_fp,
    )
    standard = mcc.Release(
        -4201, "recycle", Path("2008-01-01 - 808s & Heartbreak [602557134230]"),
        "808s & Heartbreak", tracks=[base, wrong_title, genuinely_different],
    )
    japanese = mcc.Release(
        -4202, "existing", Path("2008-11-21 - 808s & Heartbreak [JP - UICD-9058]"),
        "808s & Heartbreak", tracks=[live_label],
    )
    mcc.configure_exclusions([standard, japanese], True, True)
    if not live_label.exclude_from_coverage or not live_label.fingerprint:
        raise RuntimeError("Live policy destroyed evidence of recording identity.")
    available = mcc._fingerprint_identity_candidates(
        [base, live_label, wrong_title, genuinely_different]
    )
    if live_label not in available:
        raise RuntimeError("Excluded but readable Live recording omitted from fingerprint scan.")
    tracks = [base, live_label, wrong_title, genuinely_different]
    groups, _notes, _reviews = mcc.merge_equivalent_tracks(tracks)
    if not (
        base.group_id >= 0
        and base.group_id == live_label.group_id == wrong_title.group_id
        and genuinely_different.group_id != base.group_id
    ):
        raise RuntimeError(
            "Pinocchio Story mismatch: acoustically matching versions with "
            "conflicting/missing metadata were not grouped."
        )
    members = groups.get(base.group_id)
    if members != [0, 1, 2] or live_label.exclude_from_coverage:
        raise RuntimeError("Default Live wording defeated an acoustically verified allowed copy.")
    if genuinely_different.group_id == base.group_id:
        raise RuntimeError("Different audio incorrectly merged by matching title.")


def _candidate_router_regression_self_test() -> None:
    """Cached metadata and fast token gate must preserve legacy routing."""
    variants = [
        mcc.Track(-1, Path("Base.flac"), 1, title="Song", artist="GIMS"),
        mcc.Track(-2, Path("Radio.flac"), 1, title="Song (Radio Edit)", artist="GIMS"),
        mcc.Track(-3, Path("Extended.flac"), 1, title="Song (Extended Mix)", artist="GIMS"),
        mcc.Track(-4, Path("Remix.flac"), 1, title="Song (Remix)", artist="GIMS"),
        mcc.Track(-5, Path("Live.flac"), 1, title="Song (Live)", is_live=True),
        mcc.Track(-6, Path("Mode.flac"), 1, title="Song (Lunar Mode)", artist="GIMS"),
        mcc.Track(-7, Path("Instrumental.flac"), 1, title="Song (Instrumental)"),
        mcc.Track(-8, Path("Album.flac"), 1, title="Song", album="Extended Versions"),
        mcc.Track(-9, Path("Feat.flac"), 1, title="Song", artist="GIMS;Quincy"),
    ]
    positions = list(range(len(variants)))
    roots, hard = mcc._candidate_semantic_profiles(variants, positions)
    for a, b in itertools.combinations(positions, 2):
        if (mcc._candidate_semantic_conflict(a, b, roots, hard)
                != mcc._semantic_version_conflict(variants[a], variants[b])):
            raise RuntimeError(f"Candidate semantic cache changed routing of {a}:{b}.")
    bound = min(
        mcc.FP_CANDIDATE_STRONG_SHARED_TOKENS,
        mcc.FP_CANDIDATE_WEAK_SHARED_TOKENS,
        max(12, mcc.FP_CANDIDATE_WEAK_SHARED_TOKENS // 2),
    )
    if bound <= 0:
        raise RuntimeError("Candidate shared token bound invalid.")
    for shared in range(bound):
        if (
            shared >= mcc.FP_CANDIDATE_STRONG_SHARED_TOKENS
            or shared >= mcc.FP_CANDIDATE_WEAK_SHARED_TOKENS
            or shared >= max(12, mcc.FP_CANDIDATE_WEAK_SHARED_TOKENS // 2)
        ):
            raise RuntimeError("Candidate router would discard a viable route.")
    # Any pair visited in the duration stage falls inside the same 45-sec
    # gate already imposed in the far-rare route; the former per-pair
    # considered_pairs set therefore was strictly redundant.
    for delta in (0.0, 8.0, 15.0, 45.0, 45.001, 120.0):
        visited = delta <= mcc.FP_CANDIDATE_STRONG_DURATION_WINDOW
        far_rare_allows = delta > mcc.FP_CANDIDATE_STRONG_DURATION_WINDOW
        if visited == far_rare_allows:
            raise RuntimeError("Far-rare duration safeguard changed.")


def _classification_and_release_keep_regression_self_test() -> None:
    """Persistent Skip, Personal Picks, main-artist remix, release type and pin rules."""
    # 2026-10-25 Kanye West comparison JSONL (v0.5.58): releases from
    # guest/duo artists in a Kanye discography were falsely called VA
    # compilations simply because no track listed Kanye as primary artist.
    # Each edition has consistent physical track credits and explicit tags.
    for title, folder, artists, tags, expected in (
        ("Selfish", "2004-01-01 - Selfish [724354850752]",
         ["Slum Village"], {"album_artist": "Slum Village", "RELEASETYPE": "single"},
         ("single", "tag")),
        ("Forever", "2009-01-01 - Forever [602527212609]",
         ["Drake"], {"album_artist": "Drake", "RELEASETYPE": "single"},
         ("single", "tag")),
        ("Alors On Danse", "2010-01-01 - Alors On Danse [602527529240]",
         ["Stromae"], {"album_artist": "Stromae", "RELEASETYPE": "single;remix"},
         ("single", "tag")),
        ("KIDS SEE GHOSTS", "2018-06-08 - KIDS SEE GHOSTS [602567803911]",
         ["KIDS SEE GHOSTS"] * 7,
         {"album_artist": "KIDS SEE GHOSTS", "RELEASETYPE": "album"},
         ("album", "tag")),
        ("Kids See Ghosts", "2018-09-28 - Kids See Ghosts [US - B0028759-02]",
         ["Kanye West & Kid Cudi"] * 7,
         {"album_artist": "Kanye West & Kid Cudi", "MusicBrainz Album Type": "album"},
         ("album", "tag")),
    ):
        actual = mcc.infer_release_type(
            title, folder, len(artists), tags, 0.0, artists,
            discography_artist="kanyewest",
        )
        if actual != expected:
            raise RuntimeError(
                f"2026-10-25 release category regression: {folder}: {actual} != {expected}"
            )
    # Two-track collaborations and different guest features do not by
    # themselves constitute a collection of independent performing acts.
    if mcc.infer_release_type(
        "Collaborative", "Collaborative", 2,
        {"RELEASETYPE": "ep", "album_artist": "Joint Act"}, 0,
        ["Joint Act", "Second Act"], "kanyewest",
    ) != ("ep", "tag"):
        raise RuntimeError("Two-track guest EP was misclassified as Compilation.")
    # A detected but not persistently classified remix must be marked as
    # Remix on first 🇷 click, not inadvertently put in Personal Picks.
    for kind in ("remix", "live", "skip"):
        if mcc._promote_pattern_choice(kind, ""):
            raise RuntimeError("First pattern-mark click incorrectly promoted to Personal Picks.")
        if not mcc._promote_pattern_choice(kind, kind):
            raise RuntimeError("Re-clicking a saved classification failed to promote it.")
    if not mcc._promote_pattern_choice("keep", ""):
        raise RuntimeError("Explicit Keep failed to promote the track.")
    if mcc._promote_pattern_choice("skip", "remix"):
        raise RuntimeError("Changing a saved category was mistaken for promotion.")
    original_state = vars(mcc)["_state_dir"]
    try:
        with tempfile.TemporaryDirectory(prefix="mcc-classification-") as root:
            vars(mcc)["_state_dir"] = lambda: Path(root) / "state"
            track = mcc.Track(
                -9301, Path("01 Asteroids (Noisia Remix).flac"), 1,
                title="Asteroids (Noisia Remix)", artist="Other Artist", is_remix=True,
            )
            release = mcc.Release(
                -9301, "recycle", Path(root) / "Asteroids", "Asteroids",
                tracks=[track], scan_root=Path(root) / "Noisia" / "Noisia ALAC",
            )
            if mcc._discography_artist_from_release(release) != "noisia":
                raise RuntimeError("Could not identify the explicitly named Noisia source root.")
            if not mcc._main_artist_remix(track, "noisia") or mcc._main_artist_remix(track, "skrillex"):
                raise RuntimeError("Main-artist remixer decision is not discriminating.")
            mcc.configure_exclusions([release], True, False, [], {})
            if track.exclude_from_coverage:
                raise RuntimeError("Main artist's own Remix was excluded.")
            key, label = mcc._classify_track_pattern(track, "remix")
            if not key or not label:
                raise RuntimeError("No pattern extracted for map classification.")
            categories = {key: {"kind": "skip", "label": label}}
            mcc._save_pattern_categories(categories)
            if mcc._load_pattern_categories() != categories:
                raise RuntimeError("Skip category did not survive reload.")
            mcc.configure_exclusions([release], False, False, [], categories)
            mcc.apply_pattern_exclusions([release], {key})
            if not track.exclude_from_coverage:
                raise RuntimeError("Skip did not eliminate the pattern.")
            picks: List[Dict[str, str]] = []
            mcc._add_personal_pattern_rule(picks, key, label)
            if not mcc._personal_pick_match(track, picks):
                raise RuntimeError("Promoting pattern to Personal Picks does not match.")
            mcc.configure_exclusions([release], True, False, picks, {})
            if track.exclude_from_coverage:
                raise RuntimeError("Personal Picks did not override remix exclusion.")
            if mcc.infer_release_type("Best of Noisia", "Best of Noisia", 4, {},
                                  track_artists=["Noisia"] * 4,
                                  discography_artist="noisia")[0] != "anthology":
                raise RuntimeError("Same-artist retrospective not classified Anthology.")
            if mcc.infer_release_type("Sampler", "Sampler", 5,
                                  {"releasetype": "Album", "ALBUMARTIST": "Noisia"},
                                  track_artists=["Noisia", "Other A", "Other B", "Other C", "Other D"],
                                  discography_artist="noisia") != ("compilation", "majority-other-artist"):
                raise RuntimeError("Strict majority of other performers not Compilation.")
            if mcc._other_artist_majority(["Noisia", "Other", "Other", "Noisia"], "noisia"):
                raise RuntimeError("Half of the credits was incorrectly a majority.")
            # Bastille's VS. EP is co-credited with collaborators using "vs.";
            # these are Bastille recordings, not a Various Artists compilation.
            vs_artists = [
                "Bastille vs. the Gemma Sharples Quartet", "Bastille vs. HAIM",
                "Bastille vs. MNEK", "Bastille",
                "Bastille vs. Tyde vs. Rationale", "Bastille vs. GRADES",
                "Bastille vs. GRADES vs. Lizzo",
                "Bastille vs. Angel Haze vs. F*U*G*Z vs. Braque",
                "Bastille vs. Rag'n'Bone Man vs. Skunk Anansie",
            ]
            vs_release = mcc.Release(
                -9302, "recycle", Path(root) / "VS. (Other People's Heartache, Pt. III)",
                "VS. (Other People's Heartache, Pt. III)",
                scan_root=Path(root) / "Bastille" / "Bastille ALAC",
                tracks=[mcc.Track(
                    -9302, Path(f"{i:02d} Track.m4a"), i,
                    title=f"Track {i}", artist=artist,
                    album="VS. (Other People's Heartache, Pt. III)",
                    tags={"ALBUMARTIST": "Bastille", "MusicBrainz Album Type":
                          "mixtape/street" if i in {1, 4, 9} else "ep"},
                ) for i, artist in enumerate(vs_artists, 1)],
            )
            mcc.finalize_release_metadata([vs_release])
            if (vs_release.release_type, vs_release.type_source) != ("ep", "tag"):
                raise RuntimeError("Bastille VS. collaborator EP misclassified as Compilation/Album.")
            saved_path = mcc._manual_album_group_path_key(release.path)
            mcc._save_manual_kept_release_paths({saved_path})
            if saved_path not in mcc._load_manual_kept_release_paths():
                raise RuntimeError("Keep release was not persisted.")
            if mcc._committed_kept_paths_for_plan([release], set()):
                raise RuntimeError("Unkeep did not clear its stored pin.")
    finally:
        vars(mcc)["_state_dir"] = original_state


def _coherent_duration_regression_self_test() -> None:
    """Real INNA Hot comparison-log-shaped regression for acoustic bridges."""
    def fixture(durations: List[float], pairs: List[Tuple[int, int]]) -> mcc.UnionFind:
        sample = [
            mcc.Track(-14000 - index, Path(f"hot-{index}.flac"), index,
                  title="Test", duration=duration, fingerprint=(index + 1,))
            for index, duration in enumerate(durations)
        ]
        return mcc._coherent_duration_audio_groups(
            sample, list(range(len(sample))), pairs
        )

    # Hot [5948204431396] "Nights & Days" 206.51s and CD [RDM110]
    # "Days Nights" 202.81s share strong fingerprints. A 210.30s carrier
    # must not annex the bridging 206.51s recording and split the two albums.
    days = fixture(
        [202.812993, 202.812993, 202.813333, 206.511678,
         206.511678, 208.266667, 210.306667],
        [(0, 1), (0, 2), (1, 2), (3, 4), (2, 3), (2, 4),
         (0, 3), (0, 4), (1, 3), (1, 4), (2, 5),
         (3, 5), (4, 5), (5, 6), (3, 6), (4, 6)],
    )
    if days.find(2) != days.find(4) or days.find(2) != days.find(6):
        raise RuntimeError("Hot Nights & Days / Days Nights eight-second grouping regression.")

    # Hot WEB 306.03s and Hot CD 307.28s are a stronger coherent
    # edition match; the 313.29s copy is now within the 8-second window.
    ladies = fixture(
        [306.033175, 306.033175, 307.28, 307.28, 311.253333, 313.293333],
        [(0, 1), (2, 3), (0, 2), (0, 3), (1, 2), (1, 3),
         (0, 4), (1, 4), (2, 4), (3, 4), (2, 5), (3, 5), (4, 5)],
    )
    if ladies.find(1) != ladies.find(3) or ladies.find(0) != ladies.find(5):
        raise RuntimeError("Hot Ladies eight-second grouping regression.")

    separated = fixture([200.0, 208.0], [])
    if separated.find(0) == separated.find(1):
        raise RuntimeError("Duration-only match created an acoustic duplicate.")
    direct = fixture([200.0, 208.0], [(0, 1)])
    if direct.find(0) != direct.find(1):
        raise RuntimeError("Exactly eight seconds rejected a verified acoustic match.")
    longer = fixture([200.0, 208.01], [(0, 1)])
    if longer.find(0) == longer.find(1):
        raise RuntimeError("More than eight seconds merged distinct Versions.")


def _decoded_mastering_rescue_regression_self_test() -> None:
    """Exercise the Stronger/instrumental negative-control distinction."""
    from array import array
    sample_fp = (0x55AA33CC,) * 2502
    strong = (6.279023, 0.900320, 1.0, -1, 0.417534, 6.0, 10)
    instrumental = (6.287454, 0.920593, 1.0, 0, 0.429328, 6.0, 10)
    for profile in (strong, instrumental):
        if not mcc._fingerprint_pcm_rescue_candidate(
                sample_fp, 311.946667, sample_fp, 312.373333, profile):
            raise RuntimeError("A borderline mastering or instrumental was skipped before PCM.")
        if mcc._fingerprint_profile_identity(
                profile, fingerprint_items=len(sample_fp), acoustic_coverage=1.0):
            raise RuntimeError("A borderline fingerprint bypassed PCM proof.")
        if mcc._fingerprint_pcm_rescue_candidate(
                sample_fp, 311.946667, sample_fp, 320.0, profile):
            raise RuntimeError("PCM rescue bypassed the 8-second version bound.")
    positive = {"passed": True, "method": "decoded-positive-mastering-v1",
                "reason": "Waveform consistency confirmed"}
    negative = {**positive, "passed": False}
    for verdict, expected in ((positive, True), (negative, False)):
        result = mcc._comparison_decision_details(
            sample_fp, 311.946667, sample_fp, 312.373333, expected, strong,
            pcm_verification=verdict)
        if (result["derived_final_match"] != expected
                or result["decision_consistent"] is not True
                or result["decoded_mastering_confirmed"] != expected):
            raise RuntimeError("Decoded mastering audit disagrees with positive-only evidence.")

    # Deterministic stereo PCM fixtures. Different gain/EQ/dynamics must pass;
    # removing an independently audible lead performance must not.
    if sys.byteorder != "little":
        return
    with tempfile.TemporaryDirectory(prefix="mcc-pcm-mastering-test-") as work:
        files = {name: Path(work) / (name + ".pcm")
                 for name in ("song", "master", "instrumental")}
        buffers = {name: array("h") for name in files}
        previous = 0.0
        for i in range(14 * 8000):
            t = i / 8000.0
            backing = (0.25 * math.sin(2 * math.pi * 170 * t)
                       + 0.20 * math.sin(2 * math.pi * 360 * t)
                       + 0.12 * math.sin(2 * math.pi * 690 * t))
            lead = (0.32 * math.sin(2 * math.pi * (560 * t + 15 * t * t))
                    if math.sin(2 * math.pi * 0.14 * t) > -0.3 else 0.0)
            song = backing + lead
            equalized = 0.90 * 0.82 * song + 0.10 * 0.82 * previous
            master = math.tanh(equalized * 1.3) / 1.3
            previous = song
            for name, value in (("song", song), ("master", master),
                                ("instrumental", backing)):
                quantized = max(-32768, min(32767, round(value * 20000)))
                buffers[name].extend((quantized, quantized))
        for name, path in files.items():
            with path.open("wb") as handle:
                buffers[name].tofile(handle)

        class FixtureVerifier(mcc._PCMIdentityVerifier):
            def _decode(self, track, _pinned):
                return files[track.path.stem]

        verifier = FixtureVerifier()
        song = mcc.Track(-9501, Path("song.flac"), 1, duration=14.0)
        master = mcc.Track(-9502, Path("master.flac"), 1, duration=14.0)
        instrumental_track = mcc.Track(-9503, Path("instrumental.flac"), 1, duration=14.0)
        simulated_alignment = (6.279023, 0.900320, 1.0, 0, 0.417534, 6.0, 10)
        for a, b, expected in (
                (song, master, True), (master, song, True),
                (song, instrumental_track, False),
                (instrumental_track, song, False)):
            result = verifier.verify_mastering(a, b, simulated_alignment)
            if result["passed"] != expected:
                raise RuntimeError(
                    "Decoded mastering regression failed for "
                    + a.path.stem + "/" + b.path.stem + ": "
                    + str(result.get("reason"))
                )


def _deferred_patterns_regression_self_test() -> None:
    """Pending classification survives restart without changing skip/include rules."""
    original_state = vars(mcc)["_state_dir"]
    try:
        with tempfile.TemporaryDirectory(prefix="mcc-pending-patterns-") as root:
            vars(mcc)["_state_dir"] = lambda: Path(root) / "state"
            rows = [
                {"key": "callout hook", "label": "Callout hook", "count": 2,
                 "variants": ["Straight Hook"], "examples": ["Song (Straight Hook)"]},
                {"key": "club sound", "label": "Club Sound", "count": 1,
                 "variants": [], "examples": ["Club Sound"]},
            ]
            mcc._save_pending_pattern_reviews(rows)
            loaded = mcc._load_pending_pattern_reviews()
            if len(loaded) != 2 or {r["key"] for r in loaded} != {"callout hook", "club sound"}:
                raise RuntimeError("Deferred pattern review was lost after persistence.")
            if len(mcc._unresolved_track_patterns(loaded, [
                {"mode": "pattern", "key": "club sound", "value": "Club Sound"}])) != 1:
                raise RuntimeError("Pending review repeats a remembered Personal Pick.")
            if len(mcc._unresolved_track_patterns(loaded, [], {
                "callout hook": {"kind": "remix", "label": "Callout hook"}
            })) != 1:
                raise RuntimeError("Pending review repeats a classified Remix pattern.")
            mcc._save_pending_pattern_reviews([])
            if mcc._load_pending_pattern_reviews():
                raise RuntimeError("Resolved pending patterns could not be cleared.")
    finally:
        vars(mcc)["_state_dir"] = original_state


def _external_audio_preflight_regression_self_test() -> None:
    """No metadata-only plan when external analysis or all decoding fails."""
    original_run = vars(mcc)["run_hidden"]
    original_verify = vars(mcc)["_verify_audio_file"]
    try:
        def denied(*_args, **_kwargs):
            raise OSError(5, "Access is denied")
        vars(mcc)["run_hidden"] = denied
        try:
            mcc._verify_external_audio_tools("ffmpeg.exe", "ffprobe.exe")
        except RuntimeError as exc:
            if "before reading media" not in str(exc):
                raise RuntimeError("External decoder preflight omitted failure context.")
        else:
            raise RuntimeError("External decoder access denial did not stop the scan.")

        vars(mcc)["_verify_audio_file"] = lambda _ffmpeg, _path: (
            "Full decode failed: [WinError 5] Access is denied."
        )
        fixture = mcc.Track(-9401, Path("test_denied.wav"), 1, title="Unscannable")
        try:
            mcc.verify_audio_integrity("ffmpeg.exe", [fixture], 1, lambda *_: None)
        except RuntimeError as exc:
            if "All 1 audio files failed" not in str(exc):
                raise RuntimeError("Total audio-decode failure was not reported.")
        else:
            raise RuntimeError("All failed decodes incorrectly produced an optimization plan.")
    finally:
        vars(mcc)["run_hidden"] = original_run
        vars(mcc)["_verify_audio_file"] = original_verify


def _high_overlap_mastering_regression_self_test() -> None:
    """Reproduce the October 21 mastering-like fingerprint distributions."""
    count = 1600
    original = tuple(
        ((i * 0x9E3779B9) ^ 0x76543210) & 0xffffffff
        for i in range(count)
    )
    # Distances approximate measured SLIDE: ~5.82 bits, ~94% good,
    # ~49.6% excellent, median 6 and p90 10. They are synthetic,
    # not a claim that the user's audio files were decoded here.
    distances = [3] * 400 + [4] * 394 + [6] * 200 + [8] * 400 + [10] * 112 + [11] * 94
    remastered = tuple(
        value ^ (((1 << distances[(i * 853) % count]) - 1)
                  << ((i * 13) % (33 - distances[(i * 853) % count])))
        for i, value in enumerate(original)
    )
    for a, b in ((original, remastered), (remastered, original)):
        matched, sim = mcc.fingerprint_auto_match_values(a, 197.777778, b, 198.060408)
        if not matched or sim is None or not (5.7 < sim[0] < 6.0):
            raise RuntimeError("High-overlap mastering fingerprint was not recovered in both orders.")
        report = mcc._comparison_decision_details(a, 197.777778, b, 198.060408, matched, sim)
        if (report["strict_pass"] or report["mastering_pass"]
                or not report["high_overlap_mastering_pass"]
                or not report["decision_consistent"] or not report["derived_final_match"]):
            raise RuntimeError("High-overlap mastering audit disagrees with its matcher.")
        if mcc.fingerprint_auto_match_values(a, 197.777778, b, 205.779)[0]:
            raise RuntimeError("High-overlap mastering bypassed the existing 8-second rule.")
    previous = mcc._COMPARE_TRACK_DATA
    try:
        mcc._init_compare_worker([(original, 197.777778), (remastered, 198.060408)])
        rows = mcc._compare_pair_batch_worker([(1, 0, 1), (2, 1, 0)])
        if len(rows) != 2 or any(not matched for _, _, _, matched, _ in rows):
            raise RuntimeError("Parallel worker disagrees with serial mastering classification.")
    finally:
        mcc._init_compare_worker(previous)
    evidence = (5.819162, 0.939721, 1.0, 0, 0.496827, 6.0, 10)
    if not mcc._fingerprint_profile_identity(
            evidence, fingerprint_items=1576, acoustic_coverage=0.998733):
        raise RuntimeError("Actual logged SLIDE statistics were rejected.")
    for offset, changed in ((0, 6.001), (1, 0.929), (2, 0.994),
                            (4, 0.489), (5, 6.1), (6, 11)):
        invalid = list(evidence)
        invalid[offset] = changed
        if mcc._fingerprint_profile_identity(
                tuple(invalid), fingerprint_items=1576, acoustic_coverage=0.998733):
            raise RuntimeError("High-overlap mastering accepted a weakened fingerprint.")
    if mcc._fingerprint_profile_identity(
            evidence, fingerprint_items=119, acoustic_coverage=0.998733):
        raise RuntimeError("High-overlap mastering accepted a too-short fingerprint.")
    if mcc._fingerprint_profile_identity(
            evidence, fingerprint_items=1576, acoustic_coverage=0.994):
        raise RuntimeError("High-overlap mastering accepted missing musical content.")


def _reanalysis_regression_self_test() -> None:
    """Filesystem-isolated Ignore persistence and truthful planning audit."""
    previous_state_dir = vars(mcc)["_state_dir"]
    previous_logs_dir = vars(mcc)["_logs_dir"]
    try:
        with tempfile.TemporaryDirectory(prefix="mcc-reanalysis-contract-") as root:
            vars(mcc)["_state_dir"] = lambda: Path(root) / "state"
            vars(mcc)["_logs_dir"] = lambda: Path(root) / "logs"
            a = mcc.Release(-7101, "existing", Path(root) / "Edition A", "A")
            b = mcc.Release(-7102, "recycle", Path(root) / "Edition B", "B")
            ignored = mcc._committed_ignore_paths_for_plan([a, b], {a.rid})
            mcc._save_manual_ignored_release_paths(ignored)
            if mcc._manual_album_group_path_key(a.path) not in mcc._load_manual_ignored_release_paths():
                raise RuntimeError("Re-Analyze ignored release was not persisted.")
            if mcc._manual_album_group_path_key(b.path) in mcc._load_manual_ignored_release_paths():
                raise RuntimeError("Re-Analyze persisted an unignored release.")
            mcc._save_manual_ignored_release_paths(
                mcc._committed_ignore_paths_for_plan([a, b], set())
            )
            if mcc._load_manual_ignored_release_paths():
                raise RuntimeError("Re-Analyze Restore did not remove persistent Ignore.")
            audit = mcc._write_reanalysis_audit({
                "blocked_release_ids": [a.rid],
                "selected_release_ids": [b.rid],
            })
            saved = json.loads(audit.read_text(encoding="utf-8"))
            if saved.get("record_type") != "reanalysis" or saved.get("acoustic_comparisons_repeated") is not False:
                raise RuntimeError("Re-Analyze audit wrongly claims fresh fingerprint comparisons.")
            if not (mcc._state_dir() / "last_reanalysis_audit.json").is_file():
                raise RuntimeError("Re-Analyze audit snapshot was not persisted.")
    finally:
        vars(mcc)["_state_dir"] = previous_state_dir
        vars(mcc)["_logs_dir"] = previous_logs_dir


def _recording_ignore_regression_self_test() -> None:
    """Ignore track = matched recording everywhere; release Ignore unchanged.

    Regression: GIMS Caméléon 03:27 (feat. Quincy) versus the unrelated
    ordinary 04:00 recording, with acoustic copies on other releases.
    """
    original_dir = vars(mcc)["_state_dir"]
    original_migrate = vars(mcc)["_migrate_legacy_app_data"]
    try:
        with tempfile.TemporaryDirectory(prefix="mcc-ignore-recording-") as root:
            vars(mcc)["_state_dir"] = lambda: Path(root) / "state"
            vars(mcc)["_migrate_legacy_app_data"] = lambda: None

            def make(rid, name, gid, duration, fp_value, artist):
                return mcc.Track(
                    rid, Path(root) / name, rid,
                    title="Caméléon", artist=artist,
                    duration=duration, group_id=gid,
                    fingerprint=tuple([fp_value] * 96),
                    base_excluded_from_coverage=False,
                )
            cd = make(300, "CD Caméléon.flac", 700, 239.866667, 111, "GIMS")
            guest_a = make(301, "Bonus Caméléon feat Quincy.flac", 701, 207.04, 222, "GIMS;Quincy")
            guest_b = make(302, "Album Caméléon feat Quincy.flac", 701, 207.04, 333, "GIMS;Quincy")
            guest_c = make(303, "WEB Caméléon feat Quincy.flac", 701, 207.04, 222, "GIMS;Quincy")
            extended = make(304, "Caméléon extended.flac", 702, 255.0, 444, "GIMS")
            tracks = [cd, guest_a, guest_b, guest_c, extended]

            # Existing saved v2 exact-file rule now expands to verified
            # acoustic copies but MUST NOT use the same song title broadly.
            mcc._save_manual_track_skip_rules([{
                "id": "legacy-instance-only",
                "schema": 2,
                "instance_keys": [mcc._track_instance_key(guest_a)],
            }])
            if mcc.apply_persistent_track_skips(tracks) != 3:
                raise RuntimeError("Legacy instance Ignore did not expand to its acoustic group.")
            if any(item.manual_skip_rule for item in (cd, extended)):
                raise RuntimeError("Legacy Ignore excluded a different Caméléon recording.")
            mcc.remove_persistent_track_skip("legacy-instance-only", tracks)
            if any(item.manual_skip_rule for item in tracks):
                raise RuntimeError("Legacy recording Restore left orphaned skips.")

            # Fresh click anywhere in group is one persistent recording rule.
            mcc.add_persistent_track_skip(guest_c, tracks)
            if mcc.apply_persistent_track_skips(tracks) != 3:
                raise RuntimeError("Ignoring a 03:27 copy did not Ignore every matching edition.")
            if any(item.manual_skip_rule for item in (cd, extended)):
                raise RuntimeError("Ignore feat. Quincy also excluded original/Extended Version.")
            rules = mcc._load_manual_track_skip_rules()
            if (
                len(rules) != 1
                or rules[0].get("scope") != "recording"
                or len(rules[0].get("fingerprint_evidence", [])) < 2
            ):
                raise RuntimeError("Cross-edition Ignore persistence evidence is incomplete.")

            # Next scan: source path, group ID and first selected copy changed.
            rescanned_guest = make(
                991, "New folder/Caméléon feat Quincy.flac",
                9901, 207.04, 333, "GIMS;Quincy",
            )
            rescanned_original = make(
                992, "New folder/Caméléon original.flac",
                9902, 239.866667, 111, "GIMS",
            )
            same_fp_long_version = make(
                993, "New folder/Caméléon 04.10.flac",
                9903, 250.0, 333, "GIMS;Quincy",
            )
            renewed = [rescanned_guest, rescanned_original, same_fp_long_version]
            if mcc.apply_persistent_track_skips(renewed) != 1:
                raise RuntimeError("Recorded Ignore was lost after rescan/rename/new group IDs.")
            if (not rescanned_guest.manual_skip_rule
                    or rescanned_original.manual_skip_rule
                    or same_fp_long_version.manual_skip_rule):
                raise RuntimeError("Saved Ignore confused a different-length or original Version.")
            mcc.remove_persistent_track_skip(rescanned_guest.manual_skip_rule, renewed)
            if any(item.manual_skip_rule for item in renewed) or mcc._load_manual_track_skip_rules():
                raise RuntimeError("Restore from another edition failed to clear saved Ignore.")
            if any(item.exclude_from_coverage for item in renewed):
                raise RuntimeError("Restoring a recording did not restore its eligible copies.")

            # Previously separate persisted rules for individual group copies
            # must all clear when any one is restored.
            mcc._save_manual_track_skip_rules([
                {"id": "old-a", "schema": 2, "instance_keys": [mcc._track_instance_key(guest_a)]},
                {"id": "old-b", "schema": 2, "instance_keys": [mcc._track_instance_key(guest_b)]},
            ])
            mcc.apply_persistent_track_skips(tracks)
            mcc.remove_persistent_track_skip(guest_b.manual_skip_rule, tracks)
            if mcc._load_manual_track_skip_rules() or any(item.manual_skip_rule for item in tracks):
                raise RuntimeError("Restore retained a second overlapping Ignore rule.")
    finally:
        vars(mcc)["_state_dir"] = original_dir
        vars(mcc)["_migrate_legacy_app_data"] = original_migrate


def _remembered_pattern_categories_regression_self_test() -> None:
    """Persistent category is recognized, reversible, and respects inclusion toggles."""
    from tempfile import TemporaryDirectory
    old_state_dir = mcc._state_dir
    try:
        with TemporaryDirectory(prefix="mcc-pattern-category-") as root:
            mcc._state_dir = lambda: Path(root) / "state"
            remix_track = mcc.Track(
                990020, Path("01 Wow (JRMX Club).flac"), 1,
                title="Wow (JRMX Club)", artist="INNA;JRMX",
            )
            live_track = mcc.Track(
                990021, Path("01 Wow (Suggested Callout Research Hook).flac"), 2,
                title="Wow (Suggested Callout Research Hook)", artist="INNA",
            )
            remix_key = mcc.canonical_track_pattern("JRMX Club")
            live_key = mcc.canonical_track_pattern("Suggested Callout Research Hook")
            if remix_key not in mcc.track_pattern_keys(remix_track):
                raise RuntimeError("JRMX Club cannot be classified from the reviewed track.")
            if live_key not in mcc.track_pattern_keys(live_track):
                raise RuntimeError("Test fixture missing unusual callout-hook pattern.")
            review_rows = [{"key": remix_key, "label": "JRMX Club"},
                           {"key": live_key, "label": "Suggested Callout Research Hook"}]
            categories = {
                remix_key: {"kind": "remix", "label": "JRMX Club"},
                live_key: {"kind": "live", "label": "Suggested Callout Research Hook"},
            }
            mcc._save_pattern_categories(categories)
            reloaded = mcc._load_pattern_categories()
            if reloaded != categories or mcc._unresolved_track_patterns(review_rows, [], reloaded):
                raise RuntimeError("Persistent categorization did not bypass future review.")
            release = mcc.Release(990022, "recycle", Path("Classified"), "Wow",
                              tracks=[remix_track, live_track])
            mcc.configure_exclusions([release], True, True, [], reloaded)
            if (not remix_track.is_remix or not remix_track.exclude_from_coverage
                or remix_track.remix_feature_exception or not live_track.is_live
                or not live_track.exclude_from_coverage):
                raise RuntimeError("Save Remixes/Live OFF ignored saved pattern categories.")
            if (mcc._unique_recording_root_family(remix_track) != "remix"
                or mcc._unique_recording_root_family(live_track) != "live"):
                raise RuntimeError("Saved category lost semantic recording-root protection.")
            mcc.configure_exclusions([release], False, False, [], reloaded)
            if remix_track.exclude_from_coverage or live_track.exclude_from_coverage:
                raise RuntimeError("Save Remixes/Live ON failed to include classified tracks.")
            mcc._save_pattern_categories({})
            if (len(mcc._unresolved_track_patterns(review_rows, [], mcc._load_pattern_categories()))
                != len(review_rows)):
                raise RuntimeError("Forgetting a saved category did not restore review.")
            # Wrong/unknown category data may never be silently applied.
            if mcc._normalize_pattern_categories({"bad": {"kind": "arbitrary"}}):
                raise RuntimeError("Unsupported pattern category accepted.")
    finally:
        mcc._state_dir = old_state_dir


def _replaceable_version_coverage_regression_self_test() -> None:
    """2026-10-12 INNA 195.81s/213.33s Fool Me + independent singles."""
    short = mcc.Track(-51001, Path("Inna Fool Me.flac"), 1, title="Fool Me",
                  artist="INNA", duration=195.805556,
                  fingerprint=tuple([0x01234567]*1560), group_id=710001)
    long = mcc.Track(-51002, Path("Japan Fool Me.flac"), 1, title="Fool Me",
                 artist="Inna", duration=213.333333,
                 fingerprint=tuple([0x76543210]*1702), group_id=710002)
    # The actual comparison log's 2026-10-12 Fool Me statistics:
    evidence = (4.509301, 0.944836, 0.999359, -143, 0.708146, 4.0, 9)
    if not _replaceable_version_acoustic_evidence(short, long, evidence):
        raise RuntimeError("INNA Fool Me edit substitution was not recognized.")
    if _replaceable_version_acoustic_evidence(
        short, mcc.Track(-51003, Path("Extended.flac"), 1,
                     title="Fool Me (Extended Version)", artist="Inna",
                     duration=213.333333, fingerprint=long.fingerprint,
                     group_id=710003), evidence
    ):
        raise RuntimeError("Extended root incorrectly marked replaceable.")
    if _replaceable_version_acoustic_evidence(
        short, mcc.Track(-51004, Path("Different.flac"), 1,
                     title="Different Song", artist="INNA",
                     duration=213.333333, fingerprint=long.fingerprint,
                     group_id=710004), evidence
    ):
        raise RuntimeError("Different title incorrectly marked replaceable.")
    if _replaceable_version_acoustic_evidence(
        short, long, (4.509301, 0.60, 0.999359, -143, 0.50, 4.0, 9)
    ):
        raise RuntimeError("Weak acoustic evidence incorrectly substitutes a Version.")

    # Ceinture noire: Caméléon (GIMS) is NOT the same version as
    # Caméléon feat. Quincy, even when the feature is only in ARTIST.
    original = mcc.Track(
        -51005, Path("Caméléon.flac"), 1, title="Caméléon",
        artist="GIMS", duration=239.866667,
        fingerprint=short.fingerprint, group_id=710005,
    )
    guest_artist = mcc.Track(
        -51006, Path("Caméléon WEB.flac"), 1, title="Caméléon",
        artist="GIMS;Quincy", duration=207.04,
        fingerprint=long.fingerprint, group_id=710006,
    )
    guest_title = mcc.Track(
        -51007, Path("Caméléon Bonus.flac"), 1,
        title="Caméléon (feat. Quincy)", artist="GIMS",
        duration=207.04, fingerprint=long.fingerprint, group_id=710007,
    )
    if (
        _track_guest_signature(guest_artist) != {"quincy"}
        or _track_guest_signature(guest_title) != {"quincy"}
        or _track_guest_signature(original)
    ):
        raise RuntimeError("Guest performer from ARTIST/TITLE was lost.")
    strong_edit = (0.0, 1.0, 1.0, -143, 1.0, 0.0, 0)
    for guest in (guest_artist, guest_title):
        if _replaceable_version_acoustic_evidence(original, guest, strong_edit):
            raise RuntimeError("Caméléon feat. Quincy substituted for ordinary Caméléon.")
        if mcc._assign_replaceable_version_coverage(
            [original, guest], [(1, 0, 1, False, strong_edit)]
        ):
            raise RuntimeError("Featured recording coverage was incorrectly merged.")
    matches = mcc._assign_replaceable_version_coverage(
        [short, long], [(1, 0, 1, False, evidence)]
    )
    if (matches
        or short.group_id == long.group_id
        or mcc._track_coverage_gid(short) == mcc._track_coverage_gid(long)):
        raise RuntimeError("Different-length Fool Me versions lost separate obligations.")

    # The newer preservation rule requires both genuine edits. Independent
    # singles cannot replace the Japanese album's exclusive longer Fool Me.
    def t(rid, gid, name):
        return mcc.Track(rid, Path(f"{rid}-{gid}.flac"), gid, title=name,
                     artist="INNA", group_id=gid)
    shared = [800000 + k for k in range(15)]
    inna = mcc.Release(
        -51010, "recycle", Path("2015-07-24 - Inna [5948204123093]"),
        "Inna", release_type="album", source_medium="WEB",
        tracks=[t(-51010, gid, f"Album Song {gid}") for gid in shared]
               + [t(-51010, gid, f"Unique {gid}") for gid in (800100,800101,800102)]
               + [short]
    )
    japan = mcc.Release(
        -51011, "recycle", Path("INNA - Body And The Sun [Japan]"),
        "Body and the Sun", release_type="album", source_medium="CD",
        tracks=[t(-51011, gid, f"Album Song {gid}") for gid in shared]
               + [t(-51011, gid, name) for gid, name in (
                   (800201, "Cola Song"), (800202, "Take Me Higher"),
                   (800203, "Good Time"))]
               + [long]
    )
    singles = [
        mcc.Release(-51020-i, "recycle", Path(f"Single {i}"), f"Single {i}",
                release_type="single",
                tracks=[t(-51020-i, 800201+i, f"Single {i}")])
        for i in range(3)
    ]
    album_pool = [inna, japan] + singles
    solved, _ = mcc.exact_global_collection_minimize(album_pool, set())
    if inna.rid not in solved or japan.rid not in solved:
        raise RuntimeError(
            "Distinct Fool Me version lost despite its exclusive album carrier."
        )


def _restricted_windows_job_regression_self_test() -> None:
    """A Windows cleanup-Job error must not stop runnable FFmpeg children."""
    from types import SimpleNamespace

    class DeniedJobAssignment:
        def __call__(self, *_args):
            return 0  # AssignProcessToJobObject failed: WinError 87

    original_os = vars(mcc)["os"]
    original_ctypes = vars(mcc)["ctypes"]
    original_subprocess = vars(mcc)["subprocess"]
    original_job = vars(mcc)["_windows_job"]
    fake_os = SimpleNamespace(**vars(original_os))
    fake_os.name = "nt"
    fake_ctypes = SimpleNamespace(**vars(original_ctypes))
    fake_ctypes.WinDLL = lambda *_args, **_kwargs: SimpleNamespace(
        AssignProcessToJobObject=DeniedJobAssignment()
    )
    fake_ctypes.get_last_error = lambda: 87
    fake_ctypes.WinError = lambda code: OSError(code, "The parameter is incorrect")
    fake_subprocess = SimpleNamespace(**vars(original_subprocess))
    breakaway_rejections = []
    def launch_test_process(*args, **kwargs):
        if kwargs.get("creationflags", 0) & 0x01000000:
            breakaway_rejections.append(True)
            raise OSError(87, "The parameter is incorrect")
        process = original_subprocess.Popen(*args, **kwargs)
        if not hasattr(process, "_handle"):
            process._handle = 1  # Windows Popen exposes a real process handle.
        return process
    fake_subprocess.Popen = launch_test_process
    fake_subprocess.CREATE_NO_WINDOW = 0
    fake_subprocess.CREATE_BREAKAWAY_FROM_JOB = 0
    vars(mcc)["os"] = fake_os
    vars(mcc)["ctypes"] = fake_ctypes
    vars(mcc)["subprocess"] = fake_subprocess
    vars(mcc)["_windows_job"] = lambda: 1
    try:
        result = mcc.run_hidden(
            [sys.executable, "-c", "import time;time.sleep(.35);print('ffmpeg-ok')"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, check=True, timeout=10,
        )
        if result.stdout.strip() != "ffmpeg-ok":
            raise RuntimeError("Windows restricted-Job fallback did not run the decoder.")
        if vars(mcc)["_CHILD_PROCESSES"]:
            raise RuntimeError("A finished decoder remained in the active process registry.")

        fake_subprocess.CREATE_BREAKAWAY_FROM_JOB = 0x01000000
        fallback = mcc.run_hidden(
            [sys.executable, "-c", "print('no-breakaway-ok')"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, check=True, timeout=10,
        )
        if fallback.stdout.strip() != "no-breakaway-ok" or len(breakaway_rejections) != 1:
            raise RuntimeError("Windows restricted-breakaway launch fallback failed.")
        fake_subprocess.CREATE_BREAKAWAY_FROM_JOB = 0

        # When a process cannot be assigned to a Windows Job, closing MCC
        # still must terminate that exact tracked child, without touching
        # unrelated processes.
        finished = threading.Event()
        def slow_decode():
            try:
                mcc.run_hidden([sys.executable, "-c", "import time;time.sleep(20)"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=30)
            finally:
                finished.set()
        worker = threading.Thread(target=slow_decode, daemon=True)
        worker.start()
        deadline = time.monotonic() + 5
        running = []
        while time.monotonic() < deadline:
            with mcc._CHILD_LOCK:
                running = [p for p in vars(mcc)["_CHILD_PROCESSES"] if p.poll() is None]
            if running:
                break
            time.sleep(.01)
        if not running:
            raise RuntimeError("A restricted-Job decoder was never tracked.")
        mcc._end_app_children()
        worker.join(timeout=5)
        if worker.is_alive() or any(p.poll() is None for p in running):
            raise RuntimeError("Closing MCC left a restricted-Job decoder running.")
    finally:
        vars(mcc)["os"] = original_os
        vars(mcc)["ctypes"] = original_ctypes
        vars(mcc)["subprocess"] = original_subprocess
        vars(mcc)["_windows_job"] = original_job
        mcc._CHILD_SHUTDOWN.clear()


def _ui_contract_self_test() -> None:
    _high_overlap_mastering_regression_self_test()
    _decoded_mastering_rescue_regression_self_test()
    # A successful whole-track comparison is final under the user policy.
    # A local changed section cannot introduce another identity veto.
    identity_fp = tuple(((i*0x9E3779B9)^0x12345678)&0xffffffff for i in range(1000))
    changed_fp = tuple(value ^ (0xffffffff if 400<=i<490 else 0)
                       for i,value in enumerate(identity_fp))
    if not mcc.fingerprint_auto_match_values(identity_fp,126.0,changed_fp,126.0)[0]:
        raise RuntimeError("A passing fingerprint comparison was vetoed by an internal section.")
    for end_frames,delta in ((1,.133333),(4,.426667),(10,1.24),(10,8.0)):
        padded_fp = identity_fp + tuple(range(end_frames))
        if not mcc.fingerprint_auto_match_values(identity_fp,126.0,padded_fp,126.0+delta)[0]:
            raise RuntimeError("Conclusive fingerprint identity was vetoed by unmatched ends within 8 seconds.")
    if mcc.fingerprint_auto_match_values(identity_fp,126.0,identity_fp,134.001)[0]:
        raise RuntimeError("Fingerprint identity bypassed the greater-than-8-second version rule.")
    _external_audio_preflight_regression_self_test()
    _restricted_windows_job_regression_self_test()
    _classification_and_release_keep_regression_self_test()
    _deferred_patterns_regression_self_test()
    _recording_ignore_regression_self_test()
    _candidate_router_regression_self_test()
    _acoustic_first_identity_regression_self_test()
    _remembered_pattern_categories_regression_self_test()
    _reanalysis_regression_self_test()
    _coherent_duration_regression_self_test()
    _replaceable_version_coverage_regression_self_test()
    class _BridgeExposeProbe:
        def __init__(self):
            self.exposed = []

        def expose(self, *functions):
            self.exposed.extend(getattr(func, "__name__", "") for func in functions)

    class _BridgeMethodProbe:
        def getState(self):
            return "{}"

        def browseFolder(self, kind):
            return kind

    _probe_window = _BridgeExposeProbe()
    _probe_bridge = _BridgeMethodProbe()
    _probe_names = mcc._expose_bridge_methods(
        _probe_window,
        _probe_bridge,
        ("getState", "browseFolder"),
    )
    if _probe_names != ("getState", "browseFolder") or _probe_window.exposed != ["getState", "browseFolder"]:
        raise RuntimeError("Explicit WebView2 bridge exposure self-test failed.")

    main_map_html = mcc._webview_main_html()
    if (
        'function patternReview(data)' not in main_map_html
        or 'class="patternChoice"' not in main_map_html
        or '["remix","Remix"' not in main_map_html
        or '["live","Live"' not in main_map_html
        or '["keep","Keep"' not in main_map_html
        or '["skip","Skip"' not in main_map_html
        or 'role="group" aria-labelledby="patternLabel' not in main_map_html
        or 'aria-pressed="false"' not in main_map_html
        or 'bridge.submitPatternReview(JSON.stringify(selected))' not in main_map_html
        or 'id="patternLater"' not in main_map_html
        or 'bridge.deferPatternReview(JSON.stringify(selected))' not in main_map_html
        or 'id="pendingPatterns">Classify patterns' not in main_map_html
        or 'bridge.getPatternManager(patternManagerModal)' not in main_map_html
        or 'id="patternsAll"' in main_map_html
        or 'id="patternsNone"' in main_map_html
        or 'id="patternContinue"' in main_map_html
        or '<select class="patternAction"' in main_map_html
        or 'function renderPickRows()' not in main_map_html
        or 'rules:localPicks' not in main_map_html
        or 'function renderCategoryRows()' in main_map_html
    ):
        raise RuntimeError("Single-click Remix/Live pattern-review UI contract failed.")

    # The Changes view itself replaces the former duplicate "All changes" filter.
    map_ui = mcc._webview_release_map_html()
    if (
        'id="changesViewBtn"' not in map_ui
        or 'id="fullViewBtn"' not in map_ui
        or 'setViewMode("changes","all")' not in map_ui
        or 'changesBtn.textContent=(state&&state.standaloneMode)?"No changes":"Changes "+total;' not in map_ui
        or 'id="changesAllBtn"' in map_ui
        or '["changesAllBtn"' in map_ui
        or 'id="changesAddedBtn"' not in map_ui
        or 'id="changesRemovedBtn"' not in map_ui
    ):
        raise RuntimeError("Release Map Changes/Full map and category filter controls regressed.")

    map_html = mcc._webview_release_map_html()
    main_html = mcc._webview_main_html()
    if (
        'id="keepReleaseBtn"' not in map_html
        or 'bridge.toggleReleaseKeep(Number(n.id),receiveState)' not in map_html
        or 'class="patternMark"' not in map_html
        or 'class="patternBadge"' not in map_html
        or 'bridge.markTrackPattern(' not in map_html
        or 'state.requiresFreshScan' not in map_html
        or 'kind:"remix"' in map_html
        or 'id="pendingPatterns">Classify patterns' not in main_html
        or 'function patternManagerModal(raw)' not in main_html
        or '["remix","Remix"],["live","Live"],["skip","Skip"]' not in main_html
    ):
        raise RuntimeError("Classification and Keep UI contract failed.")

    # Release Map visual-contract regression: no overlapping hover row
    # controls, repeated copy action or redundant uppercase plan status.
    if (
        'id="copyPathBtn"' in map_html
        or 'DUPLICATE / ' in map_html
        or 'position:absolute;right:8px;top:4px' in map_html
        or 'class="titleCell"' not in map_html
        or 'width:100%; align-self:center; justify-self:end; visibility:hidden' not in map_html
        or 'kind!==t.patternKind' not in map_html
        or '<details class="albumGroupActions">' not in map_html
        or 'role="textbox" aria-readonly="true"' not in map_html
        or 'Track = exact audio group' in map_html
    ):
        raise RuntimeError("Release Map compact track/details layout contract regressed.")

    if mcc.WEBVIEW_PRIVATE_MODE is not True:
        raise RuntimeError(
            "Lightweight WebView2 restart self-test failed: browser profile persistence must remain disabled."
        )

    # v0.22.9 global software compliance gate: path controls and basic
    # keyboard/accessibility semantics are release-blocking invariants.
    main_html = mcc._webview_main_html()
    map_html = mcc._webview_release_map_html()
    ui_checks = [
        (
            main_html.find('id="openExistingPath"') < main_html.find('id="existingPath"'),
            "Existing discography path opener must be immediately before its path.",
        ),
        (
            main_html.find('id="openRecyclePath"') < main_html.find('id="recyclePath"'),
            "New/update path opener must be immediately before its path.",
        ),
        (
            'id="openDupPathInline"' in main_html,
            "Completed-result duplicates path must have an inline opener.",
        ),
        (
            map_html.find('id="openFolderBtn"') < map_html.find('id="releasePath"'),
            "Release Map path opener must be immediately before the release path.",
        ),
        (
            'role="progressbar"' in main_html and 'role="log"' in main_html,
            "Main UI progress/activity accessibility semantics are missing.",
        ),
        (
            'role="dialog"' in main_html and 'aria-modal="true"' in main_html,
            "Main UI modal accessibility semantics are missing.",
        ),
        (
            'aria-label="Find release or track"' in map_html,
            "Release Map search requires an accessible label.",
        ),
        (
            'row.setAttribute("role","button")' in map_html and 'row.tabIndex=0' in map_html,
            "Release Map rows must be keyboard-operable.",
        ),
        (
            'role="button" tabindex="0" aria-label="Inspect track ' in map_html,
            "Release Map track rows must be keyboard-operable.",
        ),
        (
            'id="copyAllBtn" disabled>Copy old + new</button>' in map_html
            and 'id="copyNewBtn" disabled>Move old + new</button>' in map_html
            and 'id="allDestination"' in map_html
            and 'id="newDestination"' in map_html
            and 'function copyPlan(mode)' in map_html,
            "Release Map must provide non-destructive Copy and explicitly confirmed Move OLD+NEW.",
        ),
        (
            'sourceLegendPill' in map_html and 'originOld' in map_html and 'originNew' in map_html,
            "Release Map must preserve OLD/NEW source distinction without per-row badges.",
        ),
        (
            'return {symbol:"⬆️",cls:"upgrade",label:"Upgrade"}' in map_html
            and '{symbol:"+",cls:"add",label:"New addition"}' in map_html
            and '{symbol:"✓",cls:"keep",label:"Retained in proposed selection"}' in map_html
            and 'return {symbol:"✓",cls:"keep",label:"Current / old release stays"}' in map_html
            and 'changesReplacedBtn' in map_html,
            "Release-group headers must use + for additions, ✓ for OLD-stays and ⬆️ for real upgrades.",
        ),
        (
            'source folders will not be moved, deleted, or modified' in map_html,
            "Release Map copy workflow must state that source folders are non-destructive.",
        ),
        (
            'function messageBodyWithPaths(message)' in main_html
            and 'class="iconBtn msgPathOpen"' in main_html,
            "Main error/info messages must automatically add open-location controls for displayed paths.",
        ),
        (
            ("Live / remix " + "phrase " + "review") not in main_html
            and ("phrase" + "Review") not in main_html
            and ("submit" + "Phrase" + "Review") not in main_html,
            "Obsolete automatic live/remix prompt must not exist.",
        ),
        (
            '<svg id="connections"></svg>' in map_html
            and 'function drawConnections()' in map_html,
            "Release Map SVG relationship links/connections are missing.",
        ),
        (
            'id="changeBar"' in map_html
            and 'let viewMode="changes"' in map_html
            and 'function changeKind(n)' in map_html
            and 'function renderChangesBoard(nodes)' in map_html
            and 'function renderFullBoard(nodes)' in map_html
            and '{key:"album",label:"Albums"}' in map_html
            and '{key:"ep",label:"EPs"}' in map_html
            and '{key:"single",label:"Singles"}' in map_html,
            "Release Map must default to a compact Changes view while retaining the full Albums / EPs / Singles map.",
        ),
        (
            'function groupKeyForNode(n)' in map_html
            and 'className="releaseGroup"' in map_html
            and 'className="releaseGroups"' in map_html
            and 'container-name:release-category' in map_html
            and '@container release-map-viewport (max-width:1750px)' in map_html
            and 'const categoryGrid=weights.map(' in map_html,
            "Release Map same-release-family grouping is missing.",
        ),
        (
            'displayGroupKey' in map_html
            and 'displayGroupTitle' in map_html,
            "Release Map must consume backend-prepared display grouping fields.",
        ),
        (
            'function addCurveBatch(svg,d,color,width,opacity,dash)' in map_html
            and 'svg.replaceChildren();' in map_html
            and 'function buildRowCenters()' in map_html,
            "Release Map connections must be batched instead of creating one SVG DOM node per edge.",
        ),
        (
            'white-space:nowrap; flex:0 0 auto;' in map_html
            and '@media (max-width:1100px)' in map_html,
            "Release Map toolbar must keep action-button labels inside their buttons at minimum width.",
        ),
        (
            'overflow-x:hidden' in map_html
            and 'width:max-content' not in map_html,
            "Release Map must not create a horizontally scrollable blank area.",
        ),
        (
            'function versionsForTrack' in map_html
            and 'function remixesForTrack' in map_html
            and 'function liveForTrack' in map_html,
            "Release Map Versions/Remixes/Live family navigation is missing.",
        ),
        (
            'id="reanalyzeBtn"' in map_html
            and 'function acceptReanalyzeHighlights()' in map_html
            and 'REANALYZE_HIGHLIGHT_MS=15000' in map_html
            and 'function paintReanalyzeHighlight(row,id)' in map_html
            and 'id="resultDrawer"' not in map_html
            and 'function render'+'Result()' not in map_html,
            "Release Map must highlight Re-Analyze additions/removals for 15 seconds, without a text result drawer.",
        ),
        (
            'function createLightBridge()' in map_html
            and 'function createLightMainBridge()' in main_html,
            "Lightweight WebView2 JavaScript bridge is missing.",
        ),
        (
            'bridge=createLightMainBridge();' in main_html
            and 'function waitForPywebviewMethod(name,timeoutMs)' in main_html
            and 'bridge.getState(renderState).catch(function(){});' in main_html,
            "Main UI bridge must initialize immediately and wait for the requested pywebview method, not just the api object.",
        ),
        (
            'bridge=createLightBridge();' in map_html
            and 'function waitForPywebviewMethod(name,timeoutMs)' in map_html
            and 'bridge.getState(receiveState).catch(function(){});' in map_html,
            "Release Map bridge must initialize immediately and wait for the requested pywebview method, not just the api object.",
        ),
        (
            'if(api){resolve(api);return;}' not in main_html
            and 'if(api){resolve(api);return;}' not in map_html
            and 'const fn=api&&api[name];' in main_html
            and 'const fn=api&&api[name];' in map_html,
            "WebView2 bridge readiness must wait for the requested method; api-object-only readiness causes dead buttons.",
        ),
    ]

    # Real GIMS release 3 and 39: "La même" is physically present
    # in both retained albums, but the WEB copy is excluded before fpcalc.
    # Its existence is display metadata, NOT an acoustic duplicate claim.
    decade = mcc.Release(
        rid=-5101, root_kind="existing", path=Path("Ceinture noire (Décennie) EU CD"),
        title="Ceinture noire (Décennie)", release_type="album",
    )
    web = mcc.Release(
        rid=-5102, root_kind="recycle", path=Path("Ceinture noire WEB"),
        title="Ceinture noire", release_type="album",
    )
    cd_song = mcc.Track(
        -5101, Path("CD 1/05 La même.m4a"), 5, title="La même",
        artist="GIMS & Vianney", duration=200.04, group_id=5101,
    )
    web_song = mcc.Track(
        -5102, Path("05 La même.flac"), 5, title="La même",
        artist="GIMS;Vianney", duration=200.04, group_id=-1,
        exclude_from_coverage=True,
    )
    web_extra = mcc.Track(
        -5102, Path("Extra.flac"), 6, title="Extra",
        artist="GIMS", duration=180.0, group_id=5102,
    )
    decade.tracks = [cd_song]
    web.tracks = [web_song, web_extra]
    sample_decisions = [
        mcc.ReleaseDecision(-5101, "KEEP", "fixture"),
        mcc.ReleaseDecision(-5102, "ADD", "fixture"),
    ]
    sample_snapshot = mcc.build_decision_snapshot(
        [decade, web], [cd_song, web_song, web_extra],
        {-5101, -5102}, sample_decisions,
    )
    cd_row = next(row for row in sample_snapshot if row["release_id"] == -5101)["tracklist"][0]
    web_row = next(row for row in sample_snapshot if row["release_id"] == -5102)["tracklist"][0]
    if not cd_row["unique_to_release"] or cd_row["excluded_counterparts"] != ["Ceinture noire WEB"]:
        raise RuntimeError("Excluded retained edition incorrectly labeled a physically unique song.")
    if not web_row["excluded"] or web_row["group_id"] != -1 or web_row["excluded_counterparts"]:
        raise RuntimeError("Excluded song was falsely treated as a proven acoustic match.")
    ui_snapshot = mcc._release_map_state_for_ui(
        sample_snapshot, [cd_song, web_song, web_extra],
        set(), set(), set(), False, False, False, False,
    )
    ui_song = next(node for node in ui_snapshot["nodes"] if node["id"] == -5101)["tracks"][0]
    if ui_song["excludedCounterparts"] != ["Ceinture noire WEB"]:
        raise RuntimeError("Excluded edition evidence disappeared from Release Map.")
    if cd_row["audio_match_editions"] != 0 or cd_row["unverified_editions"] != 1:
        raise RuntimeError("Excluded physical edition was not counted as unverified.")
    if ui_song["audioMatchEditions"] != 0 or ui_song["unverifiedEditions"] != 1:
        raise RuntimeError("Release Map lost physical edition confidence fields.")

    # An acoustic copy on an unselected edition still exists physically.
    other_disc = mcc.Release(
        rid=-5103, root_kind="recycle", path=Path("Other Décennie"),
        title="Ceinture noire", release_type="album",
    )
    matched_song = mcc.Track(
        -5103, Path("Other/05 La même.flac"), 5, title="La même",
        artist="GIMS;Vianney", duration=200.04, group_id=5101,
    )
    other_disc.tracks = [matched_song]
    extended_snapshot = mcc.build_decision_snapshot(
        [decade, web, other_disc],
        [cd_song, web_song, web_extra, matched_song],
        {-5101, -5102},
        sample_decisions + [mcc.ReleaseDecision(-5103, "REMOVE", "duplicate")],
    )
    extended_row = next(
        row for row in extended_snapshot if row["release_id"] == -5101
    )["tracklist"][0]
    if extended_row["audio_match_editions"] != 1 or extended_row["unverified_editions"] != 1:
        raise RuntimeError("Unselected acoustic edition disappeared from copy status.")
    if not web_song.exclude_from_coverage or web_song.group_id != -1:
        raise RuntimeError("Unverified edition was promoted to an acoustic duplicate.")
    if (
        "Also listed on " not in mcc._webview_release_map_html()
        or "Needed recording" in mcc._webview_release_map_html()
        or "Only eligible copy" in mcc._webview_release_map_html()
        or "Skipped by active options" in mcc._webview_release_map_html()
    ):
        raise RuntimeError("Release Map confuses optimizer coverage with source uniqueness.")

    # v0.5.56: dock shrinks column WIDTHS, not group column counts/order;
    # preserve board scroll; closing restores responsive CSS.
    # Repeated row clicks still inspect the release without dismissing details.
    stable_map_html = mcc._webview_release_map_html()
    if (
        "flex:0 0 52%; max-width:720px;" not in stable_map_html
        or "#details.open { display:flex; }" not in stable_map_html
        or "function freezeBoardLayout()" not in stable_map_html
        or "function applyFrozenBoardLayout()" not in stable_map_html
        or "function releaseFrozenBoardLayout()" not in stable_map_html
        or 'if(flow && count)flow.style.columnCount=String(count);' not in stable_map_html
        or 'applyFrozenBoardLayout();\n  updateRowHighlights();scheduleConnections();' not in stable_map_html
        or 'freezeBoardLayout();\n  aside.classList.add("open");' not in stable_map_html
        or 'if(opening) requestAnimationFrame(scheduleConnections);' not in stable_map_html
        or 'if(row) row.scrollIntoView({block:"nearest",inline:"nearest",behavior:"auto"});' in stable_map_html
        or "dockDetailsAwayFromRelease(n);" in stable_map_html
        or "#details.dockLeft" in stable_map_html
        or "if(selectedId!=null && Number(selectedId)===Number(n.id) && details.classList.contains(\"open\")){" not in stable_map_html
        or "      closeDetails();\n      return;" in stable_map_html
    ):
        raise RuntimeError("Release details must dock beside the board without click-to-dismiss.")


    # 2026-10-14 real comparison JSONL: release 43 Disciple 02 was falsely
    # selected as an artist album despite 22 various-performer recordings.
    disciple_artists = [
        "BARELY ALIVE", "Dodge & Fuski", "Astronaut;Far Too Loud",
        "Virtual Riot", "BARELY ALIVE;Datsik", "Diamond Eyes", "Astronaut",
        "BARELY ALIVE;Jeff Sontag", "Dodge & Fuski;Nick Thayer",
        "Megalodon", "Jonas Minor;Virtual Riot",
        "Astronaut;Black Tiger Sex Machine", "BARELY ALIVE;Coppa",
        "Virtual Riot", "BARELY ALIVE", "Dodge & Fuski",
        "Christina Grimmie;Diamond Eyes", "Astronaut;BARELY ALIVE",
        "Boy Kid Cloud;Tisoki", "BARELY ALIVE;Dodge & Fuski",
        "BARELY ALIVE", "Virtual Riot;Autodrive;Splitbreed",
    ]
    if mcc.infer_release_type(
        "Disciple 02: The Second Coming",
        "2015-05-18 - Disciple 02_ The Second Coming [3614592021540]",
        len(disciple_artists), {"releasetype": "Album", "albumartist": "Datsik"},
        90 * 60, disciple_artists,
    ) != ("compilation", "track-artists"):
        raise RuntimeError("Disciple 02 22-track Various Artists compilation was misclassified.")
    # Real release IDs 31 (WEB) and 3 (CD/library): Texx Mars has two
    # Datsik songs and the filename explicitly identifies it as an EP.
    for tag_case in (
        {"releasetype": "Album", "compilation": "1", "albumartist": "Various Artists"},
        {"releasetype": "EP", "secondaryreleasetype": "Compilation"},
        {"releasetype": "Compilation", "itunescompilation": "true"},
    ):
        if mcc.infer_release_type(
            "Texx Mars EP",
            "2009-01-14 - Texx Mars EP [190374272483]",
            2, tag_case, 613.86,
            ["Datsik", "Datsik;12th Planet"],
        )[0] != "ep":
            raise RuntimeError("Texx Mars EP erroneously promoted to Compilation.")
    # Real 2026-10-14 GIMS log: eight physically single-track remixes
    # must be Singles, never EPs merely because "Remix" appears in a name.
    for remix_title, remix_folder in (
        ("Sapés comme jamais (feat. Alonzo, Gradur, KeBlack & Awa Imani) (Remix)", "2016-11-25 - Sapés comme jamais (feat. Alonzo, Gradur, KeBlack & Awa Imani) (Remix) [886446259321]"),
        ("Mi Gna (Maître Gims Remix)", "2018-01-19 - Mi Gna (Maître Gims Remix) [5200121935129]"),
        ("Hola Señorita (Robin Schulz Remix)", "2019-07-05 - Hola Señorita (Robin Schulz Remix) [3617393671167]"),
        ("Medusa (West Indies Remix)", "2021-08-27 - Medusa (West Indies Remix) [3616559225350]"),
        ("Fazum Vuk Vuk (Teto Espelhado) (French Remix)", "2024-07-12 - Fazum Vuk Vuk (Teto Espelhado) [feat. Dj Nk Da Serra, Mc Magrinho] (French Remix) [5021732420763]"),
        ("CIEL (Showtek remix)", "2024-10-18 - CIEL (Showtek remix) [3617394227042]"),
        ("Bella (Remix)", "2025-05-08 - Bella (Remix) [5059801188399]"),
        ("Poz (Remix)", "2026-08-28 - Poz (Remix) [7333595126217]"),
    ):
        result = mcc.infer_release_type(remix_title, remix_folder, 1, {}, 240.0)
        if result != ("single", "name"):
            raise RuntimeError(f"One-track remix classified incorrectly: {remix_folder} -> {result}.")
    if mcc.infer_release_type("Example (Remixes)", "Example (Remixes)", 4, {}, 900.0)[0] != "ep":
        raise RuntimeError("Multi-track remix package lost existing EP fallback.")
    if mcc.infer_release_type("Example EP (Remix)", "Example EP (Remix)", 1, {}, 200.0)[0] != "ep":
        raise RuntimeError("Explicit EP metadata must outrank single-track remix fallback.")
    if mcc.infer_release_type(
        "Single (Remix)", "Single (Remix)", 1,
        {"releasetype": "single;remix"}, 200.0,
    ) != ("single", "tag"):
        raise RuntimeError("Explicit Single release-type tag was ignored.")
    exclusion_log_track = mcc.Track(
        -991, Path("Example (Clean).flac"), 1,
        title="Example", artist="GIMS", explicit="clean",
        excluded_by_pattern="Explicit>Clean", exclude_from_coverage=True,
    )
    exclusion_log_row = mcc._comparison_track_log_data(exclusion_log_track)
    if (
        exclusion_log_row.get("explicit_state") != "clean"
        or exclusion_log_row.get("excluded_by_pattern") != "Explicit>Clean"
    ):
        raise RuntimeError("Explicit/Clean exclusion audit evidence is missing.")
    if mcc.infer_release_type(
        "Vitamin D", "2012-05-22 - Vitamin D [DM264]",
        12, {"releasetype": "Album"}, 45 * 60,
        ["Datsik"] * 8 + [
            "Datsik;Downlink", "Datsik;Downlink",
            "Datsik;Infected Mushroom", "Datsik;Z-Trip",
        ],
    )[0] != "album":
        raise RuntimeError("Datsik album with collaborator credits was classified as VA.")
    if mcc.infer_release_type(
        "Small artist release", "Small artist release",
        2, {"releasetype": "Album", "compilation": "1"}, 700,
        ["Solo Artist", "Solo Artist"],
    )[0] != "compilation":
        raise RuntimeError("Uncontested compilation metadata was ignored.")
    if mcc.infer_release_type(
        "Various Sampler", "Various Sampler", 8, {"releasetype": "Album"},
        45 * 60, [f"Artist {i}" for i in range(8)],
    )[0] != "compilation":
        raise RuntimeError("Independent artist diversity compilation regression.")
    # Release-type regression: track-count-only classification incorrectly
    # called the 5-track / 76.49-minute 1995 BT album "今 Ima" an EP.
    ima_type, ima_source = mcc.infer_release_type(
        "今 Ima",
        "[1995] BT - 今 Ima [0630-12345-2] CD",
        5,
        {},
        4589.266666,
    )
    if (ima_type, ima_source) != ("album", "heuristic"):
        raise RuntimeError(
            f"Release type self-test failed: 今 Ima classified as {ima_type}/{ima_source}."
        )
    short_ep_type, _ = mcc.infer_release_type(
        "Test Release",
        "Test Release",
        5,
        {},
        20.0 * 60.0,
    )
    if short_ep_type != "ep":
        raise RuntimeError("Release type self-test failed: short 5-track release should remain EP.")
    explicit_ep_type, explicit_ep_source = mcc.infer_release_type(
        "Named EP",
        "Named EP",
        8,
        {},
        60.0 * 60.0,
    )
    if (explicit_ep_type, explicit_ep_source) != ("ep", "name"):
        raise RuntimeError("Release type self-test failed: explicit EP name must override duration.")

    for kinds, expected in [
        (["hdd", "ssd"], (2, "HDD")),
        (["ssd", "ssd"], (min(8, mcc._logical_cpu_count()), "SSD")),
        (["network", "ssd"], (2, "Network")),
        (["unknown", "ssd"], (2, "Unknown storage (HDD-safe)")),
    ]:
        detected = mcc._io_worker_plan(Path("old"), Path("new"), "auto",
            classify=lambda p, kinds=kinds: kinds[0] if p.name == "new" else kinds[1])
        if detected != expected:
            raise RuntimeError(f"Drive type worker count regression: {kinds} {detected}")
    for n in (1, 2, 14, 32):
        if mcc._io_worker_plan(None, Path("new"), str(n))[0] != n:
            raise RuntimeError("Manual worker selector regression.")
    for invalid in ("0", "33", "abc"):
        try:
            mcc._io_worker_plan(None, Path("new"), invalid)
        except ValueError:
            pass
        else:
            raise RuntimeError("Out-of-range worker selector accepted.")
    if ('id="ioWorkers"' not in main_html or
        'bridge.setIoWorkers(this.value,renderState)' not in main_html or
        '"setIoWorkers"' not in inspect.getsource(mcc._webview_main_app)):
        raise RuntimeError("Worker selector bridge regression.")
    probe = mcc.run_hidden([sys.executable, "-c", "print('tracked-child-ok')"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    if probe.stdout.strip() != "tracked-child-ok":
        raise RuntimeError("Tracked subprocess regression.")

    # v0.4.7: metadata completeness is declared per-disc, never inferred
    # merely from raw file count when the tags do not expose an expected count.
    def _audited_rel(rid, specs):
        return mcc.Release(
            rid=rid, root_kind="recycle", path=Path(f"Album {rid}"),
            title="Audit Album", tracks=[
                mcc.Track(
                    release_id=rid, path=Path(filename), index=i,
                    tags=tags, title=f"Song {i}",
                )
                for i, (filename, tags) in enumerate(specs, 1)
            ],
        )

    incomplete_release = _audited_rel(73001, [
        ("01.flac", {"TRACKNUMBER": "1", "TRACKTOTAL": "3"}),
        ("03.flac", {"TRACKNUMBER": "3", "TOTALTRACKS": "3"}),
    ])
    unknown_total_release = _audited_rel(73002, [
        ("01.flac", {"TRACKNUMBER": "1"}),
        ("02.flac", {"TRACKNUMBER": "2"}),
    ])
    complete_release = _audited_rel(73003, [
        ("01.flac", {"TRACKNUMBER": "1/2"}),
        ("02.flac", {"TRACKNUMBER": "2/2"}),
    ])
    conflicting_release = _audited_rel(73004, [
        ("01.flac", {"TRACKNUMBER": "1", "TRACKTOTAL": "2", "TOTALTRACKS": "3"}),
        ("02.flac", {"TRACKNUMBER": "2", "TRACKTOTAL": "2"}),
    ])
    mcc.validate_release_track_totals([
        incomplete_release, unknown_total_release, complete_release,
        conflicting_release,
    ])
    if not any("missing number(s): 2" in issue for issue in incomplete_release.validation_issues):
        raise RuntimeError("Missing TRACKTOTAL track was not detected.")
    if unknown_total_release.validation_issues or complete_release.validation_issues:
        raise RuntimeError("Unknown/complete tracktotal misclassified as incomplete.")
    if not any("conflicting" in issue for issue in conflicting_release.validation_issues):
        raise RuntimeError("Contradictory TRACKTOTAL/TOTALTRACKS tags not flagged.")
    if mcc._tag_positive_number("6/6") != 6 or mcc._tag_positive_number("garbage") is not None:
        raise RuntimeError("Invalid TRACKNUMBER/TOTALTRACKS parsing.")

    # A release with missing TRACKNUMBER tags is still complete when its
    # unambiguous filenames provide every declared track number.
    numbered_files = _audited_rel(73007, [
        (f"{number:02d} Of the Night.flac", {"TRACKTOTAL": "5"})
        for number in range(1, 6)
    ])
    filename_gap = _audited_rel(73008, [
        ("01 First.flac", {"TRACKTOTAL": "3"}),
        ("03 Third.flac", {"TRACKTOTAL": "3"}),
    ])
    unnumbered_files = _audited_rel(73009, [
        ("First.flac", {"TRACKTOTAL": "2"}),
        ("Second.flac", {"TRACKTOTAL": "2"}),
    ])
    mcc.validate_release_track_totals([numbered_files, filename_gap, unnumbered_files])
    if numbered_files.validation_issues:
        raise RuntimeError("Numbered filename fallback rejected a complete release.")
    if not any("missing number(s): 2" in issue for issue in filename_gap.validation_issues):
        raise RuntimeError("Filename fallback hid a missing track.")
    if not any("no usable TRACKNUMBER" in issue for issue in unnumbered_files.validation_issues):
        raise RuntimeError("Unnumbered release bypassed metadata validation.")

    # Per-CD totals are independent; do not mistakenly expect all tracks
    # in a multi-disc release to have the sum of per-disc TRACKTOTAL values.
    multiple_discs = _audited_rel(73005, [
        ("CD1/01.flac", {"DISCNUMBER": "1", "TRACKNUMBER": "1", "TRACKTOTAL": "2"}),
        ("CD1/02.flac", {"DISCNUMBER": "1", "TRACKNUMBER": "2", "TRACKTOTAL": "2"}),
        ("CD2/01.flac", {"DISCNUMBER": "2", "TRACKNUMBER": "1", "TOTALTRACKS": "1"}),
    ])
    mcc.validate_release_track_totals([multiple_discs])
    if multiple_discs.validation_issues:
        raise RuntimeError("Complete per-disc TRACKTOTAL flagged a false issue.")

    # v0.4.8 JPEGMAFIA Director's Cut regression, real 2026-10-10 log:
    # 28 physical tracks split into 21 consecutive CD1 + 7 consecutive CD2.
    # Deezer tags report album-wide TRACKTOTAL=28 on both discs. This is NOT
    # 7 missing on CD1 and 21 missing on CD2.
    def director_release(rid, expected, cd1=21, cd2=7, variant="album"):
        items = []
        for disc, count in ((1, cd1), (2, cd2)):
            for number in range(1, count + 1):
                total = str(expected if variant == "album" else 21 if disc == 1 else 7)
                items.append((
                    f"CD{disc}/{number:02d}.flac",
                    {
                        "DISCNUMBER": f"{disc}/2",
                        "TRACKNUMBER": str(number),
                        "TRACKTOTAL": total,
                    },
                ))
        return _audited_rel(rid, items)

    director_complete = director_release(73006, 28)
    director_incomplete = director_release(73007, 28, cd1=20, cd2=7)
    perdisc_complete = director_release(73008, 28, variant="disc")
    perdisc_missing = director_release(73009, 28, cd1=20, variant="disc")
    mcc.validate_release_track_totals([
        director_complete, director_incomplete, perdisc_complete, perdisc_missing
    ])
    if director_complete.validation_issues:
        raise RuntimeError(
            "Director's Cut album-wide TRACKTOTAL 28, 21+7 regression: "
            + "; ".join(director_complete.validation_issues)
        )
    if not any("Release-wide" in issue and "found 27" in issue
               for issue in director_incomplete.validation_issues):
        raise RuntimeError("Album-wide TRACKTOTAL 28 did not detect missing 28th file.")
    if perdisc_complete.validation_issues:
        raise RuntimeError(
            "Complete per-disc track totals 21+7 misidentified: "
            + "; ".join(perdisc_complete.validation_issues)
        )
    if not perdisc_missing.validation_issues:
        raise RuntimeError("Missing CD1 track overlooked under per-disc totals.")

    # Numbering can be global across discs as well: CD1 1..21, CD2 22..28.
    sequential = _audited_rel(73010, [
        (f"CD{1 if n <= 21 else 2}/{n:02d}.flac",
         {"DISCNUMBER": str(1 if n <= 21 else 2), "TRACKNUMBER": str(n),
          "TOTALTRACKS": "28"})
        for n in range(1, 29)
    ])
    mcc.validate_release_track_totals([sequential])
    if sequential.validation_issues:
        raise RuntimeError(
            "Release-wide sequential multi-disc numbering incorrectly rejected: "
            + "; ".join(sequential.validation_issues)
        )

    # Full FFmpeg decoding must be mandatory; header-only FFprobe success
    # cannot clear malformed audio. Validate failure and healthy pathways.
    original_audio_run = vars(mcc)["run_hidden"]
    audio_seen = []
    def _audit_fake_run(args, **kw):
        audio_seen.append(list(args))
        if "-xerror" not in args or "-err_detect" not in args or "null" not in args:
            raise RuntimeError("Integrity check did not request exhaustive decoding.")
        bad = "broken.flac" in str(args)
        return subprocess.CompletedProcess(args, 1 if bad else 0, "",
                                           "Corrupt FLAC frame CRC" if bad else "")
    vars(mcc)["run_hidden"] = _audit_fake_run
    try:
        if mcc._verify_audio_file("ffmpeg-test", Path("healthy.flac")):
            raise RuntimeError("Healthy fully decoded track was flagged as corrupt.")
        if "CRC" not in mcc._verify_audio_file("ffmpeg-test", Path("broken.flac")):
            raise RuntimeError("Corrupt FLAC full decode was not flagged.")
    finally:
        vars(mcc)["run_hidden"] = original_audio_run
    if len(audio_seen) != 2:
        raise RuntimeError("Full-audio integrity regression not executed.")

    # Standalone release-map output carries an explicit no-OLD baseline flag,
    # audit warnings and scanned source counts. This is a selection, not +Added.
    map_states = mcc._release_map_state_for_ui(
        [
            {"release_id": 90001, "name": "Stand-alone test", "action": "ADD",
             "root_kind": "recycle", "tracklist": [], "audit_issues": ["missing 2"],
             "included_tracks": 0}
        ],
        None, set(), set(), set(), False, False, False, False,
    )
    if not map_states.get("standaloneMode") or map_states.get("auditIssueCount") != 1:
        raise RuntimeError("Standalone Release Map state lost baseline/validation warning.")
    if map_states.get("scannedCounts", {}).get("releases") != 1:
        raise RuntimeError("Standalone release count was computed from only selected rows.")
    if 'if(state&&state.standaloneMode)return "";' not in map_html:
        raise RuntimeError("Standalone Changes board still falsely counts Additions.")
    if 'Proposed retained: ' not in map_html or 'renderAuditBanner()' not in map_html:
        raise RuntimeError("Standalone proposal or audit banner is absent.")

    # Manual-review acceptance is not allowed to override a length-based
    # version distinction; otherwise a later confirmation could merge it back.
    review_a = mcc.Track(-9910, Path("same_song_a.flac"), 1, title="Same Song",
                     duration=200.0, group_id=0)
    review_b = mcc.Track(-9911, Path("same_song_b.flac"), 1, title="Same Song",
                     duration=217.5, group_id=1)
    manual_merge = mcc.apply_manual_review_merges(
        [review_a, review_b], {0: [0], 1: [1]},
        [{"key": "duration-version", "track_a_index": 0, "track_b_index": 1}],
        {"duration-version"},
    )
    if len(manual_merge) != 2:
        raise RuntimeError("Manual review merged two different-length versions.")

    # MCC v0.5.14: differences of 8 seconds or LESS are not Versions.
    # Preserve the meaningful-length check exclusively ABOVE 8 seconds.
    for delta in (0.0, 0.6, 4.23, 7.0, 7.01, 8.0):
        if mcc._duration_version_conflict(200.0, 200.0 + delta):
            raise RuntimeError(f"Duration delta {delta}s <=8s incorrectly became a Version.")
    for delta in (8.01, 17.52):
        if not mcc._duration_version_conflict(200.0, 200.0 + delta):
            raise RuntimeError(f"Duration delta {delta}s >8s missed a distinct Version.")
    if mcc._duration_version_conflict(0, 205):
        raise RuntimeError("Unknown track duration incorrectly vetoed a fingerprint.")
    identical_fp = tuple(range(440))
    within_limit, _ = mcc.fingerprint_auto_match_values(
        identical_fp, 200.0, identical_fp, 208.0
    )
    above_limit, sim = mcc.fingerprint_auto_match_values(
        identical_fp, 200.0, identical_fp, 208.01
    )
    if not within_limit or above_limit or sim is None:
        raise RuntimeError("8-second duration boundary failed on identical fingerprints.")
    report = mcc._comparison_decision_details(
        identical_fp, 200.0, identical_fp, 217.52, False, sim
    )
    if (not report["duration_version_conflict"]
            or report["derived_final_match"]
            or not any("separate version" in x for x in report["rejection_reasons"])):
        raise RuntimeError("Above-8-second length rejection missing from log details.")
    allowed = mcc.UnionFind(3)
    allowed_bounds = [(200.0, 200.0), (204.0, 204.0), (208.0, 208.0)]
    if (not mcc._duration_group_union(allowed, allowed_bounds, 0, 1)
            or not mcc._duration_group_union(allowed, allowed_bounds, 1, 2)):
        raise RuntimeError("Eight-second transitive group incorrectly split.")
    veto = mcc.UnionFind(3)
    veto_bounds = [(200.0, 200.0), (204.1, 204.1), (208.01, 208.01)]
    if not mcc._duration_group_union(veto, veto_bounds, 0, 1):
        raise RuntimeError("Allowed short duration gap was incorrectly split.")
    if mcc._duration_group_union(veto, veto_bounds, 1, 2):
        raise RuntimeError("Transitive acoustic group exceeded eight-second length limit.")
    if veto.find(0) == veto.find(2):
        raise RuntimeError("Different-length Versions were merged transitively.")

    for required in (
        "function versionLengthDelta(t,other)",
        "function lengthDeltaText(seconds)",
        "differentLength",
        "altLengthDelta",
        "durationSeconds",
    ):
        if required not in map_html:
            raise RuntimeError("Release Map missing length-difference UI: " + required)

    # Real 2026-10-10 Privilege regression. The two versions report the
    # same 170.573-second duration, but one fpcalc vector covered only 10.8407%
    # of the track. Never bypass the unmatched-content gate; recover the full
    # fingerprint from decoded PCM instead. Do not re-decode healthy files.
    if not mcc._chromaprint_fingerprint_incomplete(49, 170.573333):
        raise RuntimeError("Privilege truncated 10.84%-coverage fingerprint was missed.")
    if mcc._chromaprint_fingerprint_incomplete(440, 170.573333):
        raise RuntimeError("Full-length Privilege fingerprint was wrongly rejected.")
    if mcc._chromaprint_fingerprint_incomplete(4, 3.0):
        raise RuntimeError("Very short audio should not trigger full-decode recovery.")
    if mcc._chromaprint_fingerprint_incomplete(300, 110.0):
        raise RuntimeError("Normal short track fingerprint would be reprocessed.")

    # Test the real recovery control path with fake ffmpeg/fpcalc process outputs.
    # Both success and failure must dispose temporary files without touching source.
    original_hidden = vars(mcc)["run_hidden"]
    original_pair = vars(mcc)["_locate_ffmpeg_pair"]
    original_temp = vars(mcc)["_temp_dir"]
    with tempfile.TemporaryDirectory(prefix="dea-fp-regression-") as regression_root:
        root = Path(regression_root)
        source = root / "Privilege.m4a"
        source.write_bytes(b"audio-original-not-modified")
        fake_calls = []
        def fake_hidden(cmd, **kwargs):
            fake_calls.append(list(cmd))
            if str(cmd[0]) == "ffmpeg-test":
                Path(cmd[-1]).write_bytes(b"normalized-pcm")
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if str(cmd[0]) == "fpcalc-test":
                recovered = str(cmd[-1]).endswith("normalized.wav")
                fp = [1] * (440 if recovered else 49)
                return subprocess.CompletedProcess(cmd, 0, json.dumps({
                    "fingerprint": fp, "duration": 170.573333}), "")
            raise RuntimeError(f"Unexpected subprocess in regression: {cmd!r}")
        vars(mcc)["run_hidden"] = fake_hidden
        vars(mcc)["_locate_ffmpeg_pair"] = lambda: ("ffmpeg-test", "ffprobe-test")
        vars(mcc)["_temp_dir"] = lambda: root / "temp"
        try:
            t = mcc.Track(9000, source, 0, title="Privilege", duration=170.573333)
            fp, duration = mcc.chromaprint_fingerprint("fpcalc-test", t)
            if len(fp) != 440 or abs(duration - 170.573333) > 0.001 or not t.fingerprint_repaired:
                raise RuntimeError("Incomplete Privilege fingerprint did not recover.")
            if len(fake_calls) != 3 or [c[0] for c in fake_calls] != [
                "fpcalc-test", "ffmpeg-test", "fpcalc-test"]:
                raise RuntimeError("Privilege recovery command sequencing regression.")
            if list((root / "temp" / "fingerprint_recovery").glob("fp-*")):
                raise RuntimeError("Fingerprint recovery leaked a temporary directory.")
            if source.read_bytes() != b"audio-original-not-modified":
                raise RuntimeError("Fingerprint recovery modified the original source.")

            # Retrying with still-truncated PCM must fail closed, not merge.
            fake_calls.clear()
            def still_truncated(cmd, **kwargs):
                result = fake_hidden(cmd, **kwargs)
                if str(cmd[0]) == "fpcalc-test":
                    result.stdout = json.dumps({"fingerprint": [1] * 49, "duration": 170.573333})
                return result
            vars(mcc)["run_hidden"] = still_truncated
            try:
                mcc.chromaprint_fingerprint("fpcalc-test", mcc.Track(
                    9001, source, 0, title="Privilege", duration=170.573333))
            except RuntimeError as exc:
                if "No speculative audio merge" not in str(exc):
                    raise
            else:
                raise RuntimeError("Unrepaired fingerprint was treated as reliable.")
            if list((root / "temp" / "fingerprint_recovery").glob("fp-*")):
                raise RuntimeError("Failed fingerprint recovery left temporary PCM.")
        finally:
            vars(mcc)["run_hidden"] = original_hidden
            vars(mcc)["_locate_ffmpeg_pair"] = original_pair
            vars(mcc)["_temp_dir"] = original_temp

    # MCC v0.5.6: real 2026-10-12 INNA retitled-album regression.
    # Match releases through >=80% of the SMALLER wanted acoustic group set.
    # Transitive family links cover retitled editions without requiring names,
    # matching track order, or identical bonus content.
    def _retitled_fixture(rid, label, group_ids, artist="INNA"):
        return mcc.Release(
            rid, "recycle", Path(label), label, release_type="album",
            source_medium="WEB",
            tracks=[
                mcc.Track(rid, Path(f"{rid}-{index}.flac"), index, title=f"Track {gid}",
                      artist=artist, group_id=gid)
                for index, gid in enumerate(group_ids, 1)
            ],
        )

    hot_web = _retitled_fixture(9831, "2005-07-01 - Hot [5037128001775]", range(1, 13))
    hot_cd = _retitled_fixture(9832, "2010 - Hot [RDM110]", range(1, 12))
    hot_new = _retitled_fixture(
        9833, "Inna - New Hot Edition (2010)", list(range(1, 10)) + list(range(30, 34)),
    )
    if not mcc._album_editions_related_by_audio(hot_web, hot_cd):
        raise RuntimeError("Hot WEB/CD 11 of 11 group overlap missed.")
    if not mcc._album_editions_related_by_audio(hot_cd, hot_new):
        raise RuntimeError("Hot/New Hot 9 of 11 >=80% group overlap missed.")
    if mcc._album_editions_related_by_audio(hot_web, hot_new):
        raise RuntimeError("Hot 9 of 12 (<80%) incorrectly linked directly.")
    if len(mcc._album_clusters([hot_web, hot_cd, hot_new])) != 1:
        raise RuntimeError("Retitled Hot album family was split despite overlap chain.")

    body_original = _retitled_fixture(
        9841, "2015-07-24 - Body and the Sun", range(101, 116)
    )
    body_inna = _retitled_fixture(
        9842, "2015-07-24 - Inna [5948204123093]",
        list(range(101, 115)) + list(range(130, 135)),
    )
    body_japan = _retitled_fixture(
        9843, "INNA - Body And The Sun [Japan] (2015) [FLAC]",
        list(range(101, 114)) + list(range(140, 145)),
    )
    if not mcc._album_editions_related_by_audio(body_original, body_inna):
        raise RuntimeError("Body and the Sun / Inna 14 of 15 overlap missed.")
    if not mcc._album_editions_related_by_audio(body_original, body_japan):
        raise RuntimeError("Body and the Sun / Japan 13 of 15 overlap missed.")
    if mcc._album_editions_related_by_audio(body_inna, body_japan):
        raise RuntimeError("Inna / Japan 13 of 18 (<80%) misrepresented.")
    if len(mcc._album_clusters([body_original, body_inna, body_japan])) != 1:
        raise RuntimeError("Body and the Sun / Inna / Japanese edition family split.")

    # Do not erase unique songs while forming a shared ALBUM family:
    # an alternate edition's extra group is still a wanted recording.
    wanted_groups = set().union(*(r.groups for r in [body_original, body_inna, body_japan]))
    if len(wanted_groups) != 25:
        raise RuntimeError("Alternate Japanese/Inna bonus-group regression.")
    if mcc._album_editions_related_by_audio(
        hot_web, _retitled_fixture(9844, "Unrelated album", range(1, 13), "Unrelated Artist")
    ):
        raise RuntimeError("Shared soundtrack across different lead artists merged albums.")


    # v0.5.19: exact INNA Part 2 Album/EP metadata mismatch (Oct 14 log).
    # Six real audio groups match; separate Alright remains a distinct recording.
    party_web = _retitled_fixture(9845,
        "2013-03-04 - Party Never Ends, Pt. 2 (Deluxe Editon) [5948204032791]",
        list(range(9001, 9007)) + [9010, 9011, 9012])
    party_web.release_type = "ep"
    party_cd = _retitled_fixture(9846,
        "Inna - Party Never Ends (Part 2) (2013) [WPCR-15062]",
        list(range(9001, 9007)) + [9020, 9021])
    party_cd.tracks[-1].exclude_from_coverage = True
    if (len(set(mcc._included_group_sequence(party_web))
            & set(mcc._included_group_sequence(party_cd))) != 6
        or not mcc._album_editions_related_by_audio(party_web, party_cd)
        or len(mcc._album_clusters([party_web, party_cd])) != 1):
        raise RuntimeError("INNA Part 2 Album/EP 6-of-7 overlap family regression.")
    party_nodes = [
        {"id": r.rid, "name": r.path.name, "releaseType": r.release_type,
         "path": str(r.path), "albumTitles": [r.title]}
        for r in (party_web, party_cd)
    ]
    mcc._assign_release_map_display_groups(party_nodes, [party_web, party_cd])
    if (party_nodes[0]["displayGroupKey"] != party_nodes[1]["displayGroupKey"]
        or any(n.get("displayGroupKind") != "album" for n in party_nodes)
        or [party_web.release_type, party_cd.release_type] != ["ep", "album"]
        or 9020 in party_web.groups):
        raise RuntimeError("Mixed Album/EP map grouping or distinct audio regression.")
    insufficient = _retitled_fixture(9847, "Insufficient overlap",
        list(range(9001, 9006)) + [9030, 9031])
    if mcc._album_editions_related_by_audio(party_web, insufficient):
        raise RuntimeError("Below-80-percent overlap was incorrectly grouped.")
    unrelated = _retitled_fixture(9848, "Different artist",
        list(range(9001, 9008)), "Different Artist")
    if mcc._album_editions_related_by_audio(party_web, unrelated):
        raise RuntimeError("Different-artist Album/EP incorrectly grouped.")
    unrelated.release_type = "single"
    if mcc._album_editions_related_by_audio(party_web, unrelated):
        raise RuntimeError("Single incorrectly joined an Album/EP family.")

    # The manual operation moves ONE release between auto families while keeping
    # a reversible link keyed to its path rather than transient scan release IDs.
    previously_loaded = mcc._MANUAL_ALBUM_GROUP_LINKS
    try:
        mcc._MANUAL_ALBUM_GROUP_LINKS = {}
        matching_a = _retitled_fixture(9851, "Manual Album A", range(501, 511))
        matching_b = _retitled_fixture(9852, "Manual Album B", range(501, 511))
        destination = _retitled_fixture(9853, "Different album group", range(601, 611))
        if len(mcc._album_clusters([matching_a, matching_b, destination])) != 2:
            raise RuntimeError("Manual grouping baseline cluster count wrong.")
        mcc._MANUAL_ALBUM_GROUP_LINKS = {
            mcc._manual_album_group_path_key(matching_a.path):
            mcc._manual_album_group_path_key(destination.path)
        }
        families = [
            {r.rid for r in family}
            for family in mcc._album_clusters([matching_a, matching_b, destination])
        ]
        if {matching_a.rid, destination.rid} not in families or {matching_b.rid} not in families:
            raise RuntimeError("Manual group move failed to detach source from original album.")
        display_rows = [
            {"id": r.rid, "name": r.path.name, "releaseType": "album",
             "path": str(r.path), "albumTitles": [r.title]}
            for r in (matching_a, matching_b, destination)
        ]
        if (matching_a.rid in mcc.find_dominated_releases([matching_a, matching_b, destination])
            or matching_b.rid in mcc.find_dominated_releases([matching_a, matching_b, destination])):
            raise RuntimeError("Dominance ignored explicit separation of manually moved album.")
        mcc._assign_release_map_display_groups(display_rows, [matching_a, matching_b, destination])
        display_by_id = {int(row["id"]): row for row in display_rows}
        if (display_by_id[matching_a.rid]["displayGroupKey"] !=
            display_by_id[destination.rid]["displayGroupKey"] or
            display_by_id[matching_a.rid]["displayGroupKey"] ==
            display_by_id[matching_b.rid]["displayGroupKey"] or
            not display_by_id[matching_a.rid]["manualGroupAssigned"]):
            raise RuntimeError("Manual Release Map grouping display was not updated.")
        mcc._MANUAL_ALBUM_GROUP_LINKS = {}
        if len(mcc._album_clusters([matching_a, matching_b, destination])) != 2:
            raise RuntimeError("Restoring automatic album grouping failed.")
        unrelated_ep = _retitled_fixture(9854, "Unrelated EP", range(701, 709))
        unrelated_ep.release_type = "ep"
        for source, target in ((unrelated_ep, matching_a), (matching_a, unrelated_ep)):
            mcc._MANUAL_ALBUM_GROUP_LINKS = {
                mcc._manual_album_group_path_key(source.path):
                mcc._manual_album_group_path_key(target.path)
            }
            if len(mcc._album_clusters([matching_a, matching_b])) != 1:
                raise RuntimeError("EP map override modified the album-only optimization families.")
            families = mcc._album_clusters([matching_a, matching_b, unrelated_ep])
            # EP -> A joins existing A+B, while A -> EP detaches A from B.
            expected_clusters = 1 if source is unrelated_ep else 2
            if len(families) != expected_clusters or not any(
                {source.rid, target.rid} <= {r.rid for r in family}
                for family in families
            ):
                raise RuntimeError("Manual Album/EP target family assignment failed.")
            ui_rows = [
                {"id": r.rid, "name": r.path.name, "releaseType": r.release_type,
                 "path": str(r.path), "albumTitles": [r.title]}
                for r in (matching_a, matching_b, unrelated_ep)
            ]
            mcc._assign_release_map_display_groups(ui_rows, [matching_a, matching_b, unrelated_ep])
            by_id = {row["id"]: row for row in ui_rows}
            if (by_id[source.rid]["displayGroupKey"] != by_id[target.rid]["displayGroupKey"]
                or by_id[source.rid].get("displayGroupKind") != "album"
                or not by_id[source.rid]["manualGroupAssigned"]):
                raise RuntimeError("Manual Album/EP family rendered in separate map columns.")
        mcc._MANUAL_ALBUM_GROUP_LINKS = {}
    finally:
        mcc._MANUAL_ALBUM_GROUP_LINKS = previously_loaded

    if (
        "_manual_album_group_links() != self.initial_manual_album_group_links"
        not in inspect.getsource(mcc.launch_webview_release_map)
        or "self._refresh_pending_state()" not in inspect.getsource(mcc.launch_webview_release_map)
    ):
        raise RuntimeError("Manual group edits can bypass pending Re-Analyze gating.")

    if (
        'id="albumGroupSelect"' not in map_html
        or 'id="assignAlbumGroupBtn"' not in map_html
        or 'id="resetAlbumGroupBtn"' not in map_html
        or "bridge.setAlbumGroup(Number(n.id),dest,receiveState)" not in map_html
        or '"setAlbumGroup"' not in inspect.getsource(mcc.launch_webview_release_map)
        or '["album","ep"].includes(String(n.releaseType||"").toLowerCase())' not in map_html
        or '["album","ep"].includes(String(other.releaseType||"").toLowerCase())' not in map_html
        or 'n.displayGroupKind||n.releaseType' not in map_html
    ):
        raise RuntimeError("Manual Album/EP family UI/bridge contract regression.")

    # MCC v0.5.3: real INNA/YO and Wow + Cyrillic comparison-log regressions.
    # YO WEB and CD contain precisely the same 11 wanted acoustic groups,
    # but radically different physical track orders. CD alone should survive.
    yo_order_web = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    yo_order_cd = [2, 8, 7, 5, 11, 1, 3, 6, 10, 9, 4]
    def _yo_test_album(rid, order, source, folder):
        return mcc.Release(
            rid, "recycle", Path(folder), "YO", release_type="album",
            source_medium=source,
            tracks=[mcc.Track(rid, Path(f"YO-{k}.flac"), i, title=f"YO Track {k}",
                          album="YO", artist="Inna", group_id=99000+k)
                    for i, k in enumerate(order, 1)]
        )
    yo_web = _yo_test_album(9900, yo_order_web, "WEB", "2019-05-31 - YO [810760037075]")
    yo_cd = _yo_test_album(9901, yo_order_cd, "CD", "Inna - YO 2019")
    if _lcs_length(mcc._included_group_sequence(yo_web), mcc._included_group_sequence(yo_cd)) >= 7:
        raise RuntimeError("YO regression lost its distinct-order fixture.")
    if not mcc._album_editions_related_by_audio(yo_web, yo_cd):
        raise RuntimeError("YO reordered audio-identical editions were split.")
    if len(mcc._album_clusters([yo_web, yo_cd])) != 1:
        raise RuntimeError("YO equivalent albums formed multiple families.")
    yo_result = mcc.optimize_collection([yo_web, yo_cd], {})
    if yo_result != {yo_cd.rid}:
        raise RuntimeError(f"YO full-track equivalence kept wrong editions: {sorted(yo_result)}")

    if mcc.normalize_title("Sí, Mamá") != mcc.normalize_title("Si, Mama"):
        raise RuntimeError("YO accented title was not normalized correctly.")
    if mcc.normalize_title("Лучшие Хиты") != "лучшие хиты":
        raise RuntimeError("Unicode title normalization discarded Cyrillic.")
    clean_cyrillic = "Лучшие Хиты"
    bad_cp1252 = clean_cyrillic.encode("utf-8").decode("cp1252")
    bad_nfkc = unicodedata.normalize("NFKC", bad_cp1252)
    if mcc.clean_metadata_text(bad_cp1252) != clean_cyrillic or mcc.clean_metadata_text(bad_nfkc) != clean_cyrillic:
        raise RuntimeError("Russian compilation title UTF-8 mojibake repair failed.")

    wow_regular = mcc.Track(9920, Path("Wow.flac"), 1, title="Wow", artist="INNA")
    wow_club = mcc.Track(9921, Path("Wow (Beenie Becker Club Edit).flac"), 2,
                     title="Wow (Beenie Becker Club Edit)", artist="Inna;Beenie Becker")
    wow_radio = mcc.Track(9921, Path("Wow (Beenie Becker Radio Edit).flac"), 3,
                      title="Wow (Beenie Becker Radio Edit)", artist="INNA;Beenie Becker")
    wow_original_radio = mcc.Track(9921, Path("Wow (Radio Edit).flac"), 4,
                               title="Wow (Radio Edit)", artist="INNA")
    wow_test = [
        mcc.Release(9920, "existing", Path("Wow base"), "Wow", tracks=[wow_regular]),
        mcc.Release(9921, "recycle", Path("Wow Remixes"), "Wow (Remixes)",
                tracks=[wow_club, wow_radio, wow_original_radio]),
    ]
    mcc.configure_exclusions(wow_test, True, True)
    if any(not t.is_remix or t.remix_feature_exception or not t.exclude_from_coverage
           for t in (wow_club, wow_radio)):
        raise RuntimeError("Wow Beenie Becker Club/Radio Edit failed remixer classification.")
    if wow_original_radio.is_remix or wow_original_radio.exclude_from_coverage:
        raise RuntimeError("Uncredited Wow original Radio Edit was treated as a remix.")

    # MCC v0.5.2: INNA/Gimme Gimme [190295779481] real 2026-10-12
    # regression. Remixer ARTIST tags must NOT create featured-remix
    # exceptions when Save Remixes is off, even if a bad tag lists the
    # remixer of ANOTHER track (Andros Remix -> Inna;Sak Noel).
    gimme_names = [
        ("Gimme Gimme (Andros Remix)", "Inna;Sak Noel"),
        ("Gimme Gimme (Armageddon Turk Says No Mix)", "Inna;Armageddon Turk"),
        ("Gimme Gimme (DJ Dark & MD DJ Remix)", "Inna;Dj Dark;MD DJ"),
        ("Gimme Gimme (Ness Remix)", "Inna;Ness"),
        ("Gimme Gimme (Sak Noel Remix)", "Inna;Sak Noel"),
        ("Gimme Gimme (Dirty Nano Remix)", "Inna;Dirty Nano"),
        ("Gimme Gimme (Timmy Rise & Barrington Lawrence Remix)", "INNA;Barrington Lawrence;Timmy Rise"),
        ("Gimme Gmme (Mert Hakan & Ilkay Sencan Remix)", "Inna;Mert Hakan;Ilkay Sencan"),
        ("Gimme Gimme (Criminal Sounds & Tadeo Fernandez Remix)", "INNA;Criminal Sounds;Tadeo Fernandez"),
        ("Gimme Gimme (Electric Bodgea Remix)", "Inna;Electric Bodgea"),
    ]
    gimme_regular = mcc.Track(-9650, Path("01 Gimme Gimme.flac"), 0,
                          title="Gimme Gimme", artist="Inna")
    gimme_extended = mcc.Track(-9651, Path("01 Gimme Gimme (Extended Version).flac"), 0,
                           title="Gimme Gimme (Extended Version)", artist="Inna")
    gimme_tracks = [
        mcc.Track(-9652, Path(f"{i:02d} {title}.flac"), i,
              title=title, artist=credit)
        for i, (title, credit) in enumerate(gimme_names, 2)
    ]
    gimme_test = [
        mcc.Release(-9650, "existing", Path("Gimme original"), "Gimme Gimme",
                tracks=[gimme_regular]),
        mcc.Release(-9652, "recycle", Path("Gimme Gimme Remixes"), "Gimme Gimme (Remixes)",
                tracks=[gimme_extended] + gimme_tracks),
    ]
    mcc.configure_exclusions(gimme_test, True, True)
    if any(not track.is_remix or track.remix_feature_exception
           or not track.exclude_from_coverage for track in gimme_tracks):
        raise RuntimeError(
            "Gimme Gimme: remixer credits leaked into featured-remix exception."
        )
    if gimme_extended.is_remix or gimme_extended.exclude_from_coverage:
        raise RuntimeError("Gimme Gimme: genuine Extended Version wrongly excluded.")

    # v0.5.61: a trailing dash-named REMIXER is not a new featured singer.
    # Reproduce the exact Everything Everything v0.5.59 JSONL misclassification.
    rutledge = mcc.Track(
        -9660, Path("02 MY KZ, YR BF – James Rutledge Remix.flac"), 2,
        title="MY KZ, YR BF – James Rutledge Remix",
        artist="Everything Everything;James Rutledge",
    )
    ordinary_song = mcc.Track(
        -9661, Path("Song.flac"), 1, title="Song",
        artist="Everything Everything;Existing Singer",
    )
    same_singer = mcc.Track(
        -9661, Path("Song - DJ Example Remix (feat. Existing Singer).flac"), 2,
        title="Song - DJ Example Remix (feat. Existing Singer)",
        artist="Everything Everything;DJ Example;Existing Singer",
    )
    new_singer = mcc.Track(
        -9661, Path("Song - DJ Example Remix (feat. New Singer).flac"), 3,
        title="Song - DJ Example Remix (feat. New Singer)",
        artist="Everything Everything;DJ Example;New Singer",
    )
    filename_only = mcc.Track(
        -9662, Path("Everything Everything - Another Song - DJ Example Remix.flac"), 1,
        title="Another Song", artist="Everything Everything;DJ Example",
    )
    artist_prefix_only = mcc.Track(
        -9662, Path("Everything Everything - Song Remix.flac"), 2,
        title="Song Remix", artist="Everything Everything;New Singer",
    )
    if mcc._named_remixer_suffix(artist_prefix_only)[0]:
        raise RuntimeError("Filename artist prefix was mistaken for remixer credit.")
    mcc.configure_exclusions([
        mcc.Release(-9660, "recycle", Path("MY KZ remix"), "MY KZ, UR BF",
                tracks=[rutledge]),
        mcc.Release(-9661, "existing", Path("Ordinary and mixes"), "Song",
                tracks=[ordinary_song, same_singer, new_singer]),
        mcc.Release(-9662, "recycle", Path("Filename remixes"), "Other",
                tracks=[filename_only]),
    ], True, False)
    for candidate in (rutledge, same_singer, filename_only):
        if not candidate.is_remix or candidate.remix_feature_exception or not candidate.exclude_from_coverage:
            raise RuntimeError("Named dash-remixer was mistaken for a new featured performer.")
    if new_singer.exclude_from_coverage or not new_singer.remix_feature_exception:
        raise RuntimeError("New singer genuinely attached to a named remix was lost.")

    # Named remixer children such as JRMX Club have no literal 'Remix'
    # suffix but are inferred by their companion JRMX Dub. Do not promote
    # their ARTIST co-credit to a FEATURE either.
    wow_plain = mcc.Track(-9655, Path("Wow.flac"), 0, title="Wow", artist="Inna")
    wow_dub = mcc.Track(-9656, Path("Wow (JRMX Dub).flac"), 1,
                    title="Wow (JRMX Dub)", artist="Inna;JRMX")
    wow_club = mcc.Track(-9657, Path("Wow (JRMX Club).flac"), 2,
                     title="Wow (JRMX Club)", artist="Inna;JRMX")
    mcc.configure_exclusions([
        mcc.Release(-9655, "existing", Path("Wow original"), "Wow", tracks=[wow_plain]),
        mcc.Release(-9656, "recycle", Path("Wow remixes"), "Wow (Remixes)",
                tracks=[wow_dub, wow_club]),
    ], True, True)
    if any(not track.is_remix or track.remix_feature_exception
           or not track.exclude_from_coverage for track in (wow_dub, wow_club)):
        raise RuntimeError("Contextual named-remixer ARTIST tag was wrongly retained.")

    # The genuine additional FEATURE exception must still survive even when
    # the title also names a remixer. It must not rely on a remixer ARTIST tag.
    feature_base = mcc.Track(-9653, Path("Reminder.flac"), 0,
                         title="Reminder", artist="The Weeknd")
    feature_bonus = mcc.Track(-9654, Path("Reminder (DJ Example Remix feat. A$AP Rocky).flac"), 1,
                          title="Reminder (DJ Example Remix feat. A$AP Rocky)",
                          artist="The Weeknd;DJ Example;A$AP Rocky")
    mcc.configure_exclusions([
        mcc.Release(-9653, "existing", Path("Reminder base"), "Reminder",
                tracks=[feature_base]),
        mcc.Release(-9654, "recycle", Path("Reminder remix"), "Reminder (Remix)",
                tracks=[feature_bonus]),
    ], True, True)
    if not feature_bonus.is_remix or feature_bonus.exclude_from_coverage or not feature_bonus.remix_feature_exception:
        raise RuntimeError("Genuine remix-added feat. artist no longer survives.")

    # Weeknd 2026-10-10 log regressions: 659 tracks, 566 fingerprinted.
    # Unchecked Remix/Live must not erase tagged collaborator remixes.
    if mcc.extract_track_patterns("Call Out My Name") or "suggested callout" in mcc.track_pattern_keys(
        mcc.Track(-9000, Path("01 Call Out My Name.m4a"), 1, title="Call Out My Name")
    ):
        raise RuntimeError("Normal Call Out My Name title was incorrectly excluded as callout hook.")
    if "suggested callout" not in {key for key, _ in mcc.extract_track_patterns("Suggested Call Out Research Hook")}:
        raise RuntimeError("Genuine suggested callout grouping was lost.")
    if not mcc.is_remix_text("K-POP (Chopped & Screwed)") or mcc.is_remix_text("Chopped and Screwed Dreams"):
        raise RuntimeError("Chopped & Screwed remix classification regression.")
    for artist_tag, primary in [
        ("The Weeknd & Ariana Grande", "The Weeknd"),
        ("The Weeknd with ROSALÍA", "The Weeknd"),
        ("Maluma & The Weeknd", "Maluma"),
        ("The Weeknd;Ariana Grande", "The Weeknd"),
    ]:
        original_track = mcc.Track(-9001, Path("plain.m4a"), 1, title="Song", artist=primary)
        remix_track = mcc.Track(-9002, Path("remix.m4a"), 2, title="Song (Remix)", artist=artist_tag)
        source = [
            mcc.Release(-9001, "existing", Path("old"), "plain", tracks=[original_track]),
            mcc.Release(-9002, "recycle", Path("new"), "remix", tracks=[remix_track]),
        ]
        mcc.configure_exclusions(source, True, True)
        if remix_track.exclude_from_coverage or not remix_track.remix_feature_exception:
            raise RuntimeError("ARTIST-tag remix featured performer regression: " + artist_tag)
    no_added = mcc.Track(-9003, Path("remix.m4a"), 3, title="Song (Remix)", artist="The Weeknd;Ariana Grande")
    normal = mcc.Track(-9004, Path("normal.m4a"), 4, title="Song", artist="The Weeknd;Ariana Grande")
    mcc.configure_exclusions([
        mcc.Release(-9003, "existing", Path("same-remix"), "remix", tracks=[no_added]),
        mcc.Release(-9004, "existing", Path("same-normal"), "normal", tracks=[normal]),
    ], True, True)
    if not no_added.exclude_from_coverage:
        raise RuntimeError("Remix without an ADDED feature should stay excluded.")
    if mcc.infer_release_type("The Highlights (Deluxe)", "The Highlights (Deluxe)", 36, {"releasetype": "Album"})[0] != "compilation":
        raise RuntimeError("The Highlights compilation was mistaken for a standalone album.")
    if mcc.infer_release_type("Trilogy", "Trilogy", 30, {"releasetype": "Album"})[0] != "compilation":
        raise RuntimeError("Thirty-track Trilogy compilation metadata regression.")

    cd_track = mcc.Track(-9100, Path("CD"), 0, title="Only song", group_id=9300)
    web_track = mcc.Track(-9101, Path("WEB"), 1, title="Only song", group_id=9300)
    cd_compilation = mcc.Release(-9100, "existing", Path("CD Trilogy"), "Trilogy",
                             release_type="compilation", source_medium="CD", tracks=[cd_track])
    web_album = mcc.Release(-9101, "recycle", Path("WEB album"), "Album",
                        release_type="album", source_medium="WEB", tracks=[web_track])
    if mcc.apply_compilation_policy([cd_compilation, web_album]) or cd_track.exclude_from_coverage:
        raise RuntimeError("Compilation coverage was permanently removed.")
    initial_plan = mcc.optimize_collection([cd_compilation, web_album], {9300: [0, 1]})
    if initial_plan != {-9101}:
        raise RuntimeError("Regular source should replace CD compilation while eligible.")
    reversed_plan = mcc.optimize_collection([cd_compilation, web_album], {9300: [0, 1]},
                                        blocked_release_ids={-9101})
    if reversed_plan != {-9100}:
        raise RuntimeError("Re-Analyze lost unique coverage after manually blocked album.")
    version_fp = tuple((i * 2654435761) & 0xffffffff for i in range(1000))
    single = mcc.Track(-9200, Path("edit"), 0, title="Open Hearts (Single Version)",
                   duration=211.148, fingerprint=version_fp)
    album_track = mcc.Track(-9201, Path("original"), 1, title="Open Hearts",
                        duration=234.933, fingerprint=version_fp)
    if mcc.fingerprint_auto_match(single,album_track)[0]:
        raise RuntimeError("Shortened Open Hearts Single Version merged into album recording.")
    album_track.duration = single.duration+8.0
    if not mcc.fingerprint_auto_match(single,album_track)[0]:
        raise RuntimeError("Version wording vetoed acoustic identity within the duration limit.")

    copy_contract_source = mcc.copy_retained_plan.__doc__ or ""
    if "without modifying either source collection" not in copy_contract_source:
        raise RuntimeError("Copy workflow self-test failed: non-destructive export contract is missing.")

    # v0.4.3: test default path, safe copy, OLD+NEW move,
    # source removal, Undo and collision refusal on disposable directories.
    with tempfile.TemporaryDirectory(prefix="dea-export-contract-") as tmp_root:
        temp = Path(tmp_root)
        old_root = temp / "OLD"
        new_root = temp / "Metro Boomin"
        output = mcc.default_updated_destination(new_root)
        if output != temp / "Metro Boomin - UPDATED":
            raise RuntimeError("Default UPDATED destination regression.")
        if mcc.default_updated_destination(Path("C:/!deemix Music/Metro Boomin")).name != "Metro Boomin - UPDATED":
            raise RuntimeError("Windows-shaped UPDATED destination regression.")
        old_release = old_root / "Albums" / "Edition A"
        new_release = new_root / "EPs" / "Edition B"
        old_release.mkdir(parents=True)
        new_release.mkdir(parents=True)
        skipped_release = new_root / "EPs" / "Excluded Remix"
        skipped_release.mkdir(parents=True)
        (skipped_release / "not-selected.m4a").write_bytes(b"skip")
        (old_release / "01 old.flac").write_bytes(b"test old audio")
        (new_release / "01 new.m4a").write_bytes(b"test new audio")
        old_obj = mcc.Release(9100, "existing", old_release, "Edition A", scan_root=old_root)
        new_obj = mcc.Release(9101, "recycle", new_release, "Edition B", scan_root=new_root)
        skipped_obj = mcc.Release(9102, "recycle", skipped_release, "Excluded Remix", scan_root=new_root)
        sample_releases = [old_obj, new_obj, skipped_obj]
        decisions = [
            mcc.ReleaseDecision(9100, "KEEP", "Retained OLD"),
            mcc.ReleaseDecision(9101, "ADD", "Retained NEW"),
            mcc.ReleaseDecision(9102, "SKIP", "Excluded"),
        ]
        # Redirect Undo only inside the test; never touch real program state.
        original_manifest_accessor = vars(mcc)["_last_manifest_path"]
        test_manifest = temp / "test_undo.json"
        vars(mcc)["_last_manifest_path"] = lambda: test_manifest
        try:
            report = mcc.copy_retained_plan(
                old_root, new_root, output, sample_releases,
                decisions, "all",
            )
            if report["source_folders_modified"] or not old_release.exists() or not new_release.exists():
                raise RuntimeError("Copy contract failed: source folder was modified.")
            if not (output / "Albums" / "Edition A" / "01 old.flac").is_file():
                raise RuntimeError("Copy contract failed: OLD release not copied.")
            if not (output / "EPs" / "Edition B" / "01 new.m4a").is_file():
                raise RuntimeError("Copy contract failed: NEW release not copied.")
            try:
                mcc.move_retained_plan(old_root, new_root, output, sample_releases, decisions)
            except RuntimeError:
                pass
            else:
                raise RuntimeError("Move regression: preexisting destination not rejected.")
            shutil.rmtree(output)
            report = mcc.move_retained_plan(old_root, new_root, output, sample_releases, decisions)
            if not report.get("source_folders_modified") or not report.get("undo_available"):
                raise RuntimeError("Move result not marked as destructive/undoable.")
            if old_release.exists() or new_release.exists():
                raise RuntimeError("Move contract failed: source folders still present.")
            if not (output / "Albums" / "Edition A" / "01 old.flac").is_file():
                raise RuntimeError("Move contract failed: OLD content missing.")
            if not (output / "EPs" / "Edition B" / "01 new.m4a").is_file():
                raise RuntimeError("Move contract failed: NEW content missing.")
            if not (skipped_release / "not-selected.m4a").is_file():
                raise RuntimeError("Move contract failed: SKIP source was touched.")
            restored, conflicts = mcc.undo_last_run()
            if restored != 2 or conflicts or not old_release.exists() or not new_release.exists():
                raise RuntimeError("Move Undo contract failed.")
            # Simulate rename succeeded but the caller raised before recording
            # success. The pre-journaled entry must support full rollback.
            from unittest import mock
            original_safe_move = mcc._verified_release_directory_move
            failure_fired = [False]
            def injected_after_rename(src, dst):
                original_safe_move(src, dst)
                if Path(src) == old_release and not failure_fired[0]:
                    failure_fired[0] = True
                    raise RuntimeError("Injected failure after rename")
            with mock.patch.dict(vars(mcc), {"_verified_release_directory_move": injected_after_rename}):
                try:
                    mcc.move_retained_plan(old_root, new_root, output, sample_releases, decisions)
                except RuntimeError as exc:
                    if "Injected failure" not in str(exc):
                        raise
                else:
                    raise RuntimeError("Injected post-rename failure was not reported.")
            if not failure_fired[0] or not old_release.is_dir() or not new_release.is_dir():
                raise RuntimeError("Write-ahead Move rollback did not restore source releases.")
            if (output / "Albums" / "Edition A").exists() or test_manifest.exists():
                raise RuntimeError("Write-ahead Move rollback left an unjournaled moved release.")
            # Simulate EXDEV, even on same-volume CI. It must fail closed;
            # the source stays intact and no target is published.
            from unittest import mock
            cross_source = temp / "cross-volume-source"
            cross_target = temp / "cross-volume-target"
            cross_source.mkdir()
            (cross_source / "content.flac").write_bytes(b"checked transfer")
            native_rename = os.rename

            def simulate_cross_volume(a, b):
                if Path(a) == cross_source and Path(b) == cross_target:
                    raise OSError(errno.EXDEV, "Cross-device link")
                return native_rename(a, b)

            with mock.patch.object(os, "rename", side_effect=simulate_cross_volume):
                try:
                    mcc._verified_release_directory_move(cross_source, cross_target)
                except RuntimeError as exc:
                    if "Cross-volume Move is disabled" not in str(exc):
                        raise
                else:
                    raise RuntimeError("Cross-volume Move incorrectly copied/deleted sources.")
            if not (cross_source / "content.flac").is_file() or cross_target.exists():
                raise RuntimeError("Cross-volume denial altered music files.")

            locked_source = temp / "locked-source"
            locked_target = temp / "locked-target"
            locked_source.mkdir()
            (locked_source / "keep.flac").write_bytes(b"original")
            def simulate_sharing_denied(a, b):
                if Path(a) == locked_source and Path(b) == locked_target:
                    raise PermissionError(errno.EACCES, "Sharing violation")
                return native_rename(a, b)
            with mock.patch.object(os, "rename", side_effect=simulate_sharing_denied):
                try:
                    mcc._verified_release_directory_move(locked_source, locked_target)
                except PermissionError:
                    pass
                else:
                    raise RuntimeError("Permission failure incorrectly triggered a destructive fallback.")
            if not (locked_source / "keep.flac").is_file() or locked_target.exists():
                raise RuntimeError("Failed rename modified the original or destination.")

            nested_old = old_root / "Collision"
            nested_new = new_root / "Collision" / "Child"
            nested_old.mkdir(parents=True)
            nested_new.mkdir(parents=True)
            (nested_old / "one.flac").write_bytes(b"old")
            (nested_new / "two.flac").write_bytes(b"new")
            overlap_releases = [
                mcc.Release(9200, "existing", nested_old, "Collision", scan_root=old_root),
                mcc.Release(9201, "recycle", nested_new, "Child", scan_root=new_root),
            ]
            overlap_decisions = [
                mcc.ReleaseDecision(9200, "KEEP", "OLD"),
                mcc.ReleaseDecision(9201, "ADD", "NEW"),
            ]
            overlap_output = temp / "Overlap Output"
            overlap_operations = (
                lambda: mcc.copy_retained_plan(old_root, new_root, overlap_output,
                                           overlap_releases, overlap_decisions, "all"),
                lambda: mcc.move_retained_plan(old_root, new_root, overlap_output,
                                           overlap_releases, overlap_decisions),
            )
            for operation in overlap_operations:
                try:
                    operation()
                except RuntimeError as exc:
                    if "Overlapping destination" not in str(exc):
                        raise
                else:
                    raise RuntimeError("Nested OLD/NEW destination collision was not blocked.")
            if overlap_output.exists() or not nested_old.exists() or not nested_new.exists():
                raise RuntimeError("Nested destination preflight mutated source or output.")

            ghost_original = temp / "missing-original"
            ghost_saved = temp / "missing-moved"
            test_manifest.write_text(json.dumps({"moves": [{
                "move_type": "retained_release",
                "original": str(ghost_original),
                "moved_to": str(ghost_saved),
            }]}), encoding="utf-8")
            restored, conflicts = mcc.undo_last_run()
            if restored or len(conflicts) != 1 or not test_manifest.is_file():
                raise RuntimeError("Missing-folder Undo must preserve its manifest and report a conflict.")
        finally:
            vars(mcc)["_last_manifest_path"] = original_manifest_accessor

    if (
        'defaultExportDestination' not in map_html
        or 'function defaultExportPath()' not in map_html
        or 'function selectedExportPath(mode)' not in map_html
        or 'const path=selectedExportPath(mode);' not in map_html
        or 'const path=selectedExportPath("all")' not in map_html
        or 'const path=selectedExportPath("new")' not in map_html
        or 'Move old + new releases into:' not in map_html
        or 'Same-volume Move only; cross-volume transfers are blocked.' not in map_html
        or 'Undo Last Run can restore moved folders.' not in map_html
    ):
        raise RuntimeError("Release Map UPDATED default/Move confirmation UI regression.")

    # The auto-derived destination enables both actions without requiring Browse.
    if (
        'const path=selectedExportPath(mode);' not in map_html
        or 'copyBtn.disabled=!enabled||!path||!!state.dirty||!state.applyEnabled;' not in map_html
        or 'const supplied=String(state.defaultExportDestination||"").trim();' not in map_html
        or 'return source+" - UPDATED";' not in map_html
    ):
        raise RuntimeError("Default Copy/Move destination is not immediately actionable.")

    grouping_probe = [
        {"id": 1, "releaseType": "album", "name": "2002 - Let Go (Japan Tour Special Limited Version) [JP - BVCA-21138 - 2005]"},
        {"id": 2, "releaseType": "album", "name": "2002 - Let Go (Limited Edition) [AU - 82876-52937-2] CD 1"},
        {"id": 3, "releaseType": "album", "name": "2002 - Let Go (Sketch Book) [US - ARCD-4740]"},
        {"id": 4, "releaseType": "album", "name": "2002 - Let Go (Special Bonus Edition) [JP - BVCA-27031 - 2004]"},
        {"id": 5, "releaseType": "album", "name": "2002 - Let Go [EU - 74321962052]"},
        {"id": 6, "releaseType": "album", "name": "2007 - The Best Damn Thing (Limited Edition) [TW - 88697-20338-2] -clean-"},
        {"id": 7, "releaseType": "album", "name": "2007 - The Best Damn Thing [EU - 83697 03774 2] -clean-"},
        {"id": 8, "releaseType": "album", "name": "2007 - The Best Damn Thing [JP - BVCP-28105 - 2008]"},
        {"id": 9, "releaseType": "album", "name": "2013 - Avril Lavigne (Exclusive Edition) [US - 888837 7198 2]"},
        {"id": 10, "releaseType": "album", "name": "2013 - Avril Lavigne [JP - EICP-1588]"},
        {"id": 11, "releaseType": "album", "name": "2019 - Head Above Water (Instrumentals) [WEB]"},
        {"id": 12, "releaseType": "album", "name": "2019 - Head Above Water [WEB]"},
        {
            "id": 13,
            "releaseType": "album",
            "name": "2010-01-31 - These Hopeful Machines [8715197006125]",
            "albumTitles": ["These Hopeful Machines"],
        },
        {
            "id": 14,
            "releaseType": "album",
            "name": "BT - These Hopeful Machines (2010) [FLAC] {NEWCD9070}",
            "albumTitles": ["These Hopeful Machines"],
        },
        {
            "id": 15,
            "releaseType": "album",
            "name": "[2010] BT - These Hopeful Machines [0 6700 30849 2 5] 2CD",
            "albumTitles": ["These Hopeful Machines: CD1", "These Hopeful Machines: CD2"],
        },
        {
            "id": 16,
            "releaseType": "album",
            "name": "[2010] BT - These Hopeful Machines [067003576758] WEB",
            "albumTitles": ["These Hopeful Machines"],
        },
        {
            "id": 17,
            "releaseType": "album",
            "name": "[2010] BT - These Hopeful Machines [ПР3 CD28862] 2CD",
            "albumTitles": ["These Hopeful Machines: CD1", "These Hopeful Machines: CD2"],
        },
        {"id": 18, "releaseType": "ep", "name": "old", "albumTitles": ["More Monsters and Sprites - EP"]},
        {"id": 19, "releaseType": "ep", "name": "new", "albumTitles": ["More Monsters and Sprites EP"]},
        {"id": 20, "releaseType": "ep", "name": "old", "albumTitles": ["Bangarang - EP"]},
        {"id": 21, "releaseType": "ep", "name": "new", "albumTitles": ["Bangarang EP"]},
        {"id": 22, "releaseType": "ep", "name": "old", "albumTitles": ["Kora - EP"]},
        {"id": 23, "releaseType": "ep", "name": "new", "albumTitles": ["Kora"]},
        {"id": 24, "releaseType": "single", "name": "old", "albumTitles": ["Burial - Single"]},
        {"id": 25, "releaseType": "single", "name": "new", "albumTitles": ["Burial (feat. Pusha T, Moody Good, TrollPhace)"]},
        {"id": 26, "releaseType": "single", "name": "old", "albumTitles": ["Bun Up the Dance - Single"]},
        {"id": 27, "releaseType": "single", "name": "new", "albumTitles": ["Bun Up the Dance"]},
        {"id": 28, "releaseType": "single", "name": "old", "albumTitles": ["Squad Out! - Single"]},
        {"id": 29, "releaseType": "single", "name": "new", "albumTitles": ["SQUAD OUT! (feat. Fatman Scoop)"]},
        {"id": 30, "releaseType": "single", "name": "old", "albumTitles": ["Working for It - Single"]},
        {"id": 31, "releaseType": "single", "name": "new", "albumTitles": ["Working For It"]},
        {"id": 32, "releaseType": "single", "name": "old", "albumTitles": ["No Chill - Single"]},
        {"id": 33, "releaseType": "single", "name": "new", "albumTitles": ["No Chill"]},
        {"id": 34, "releaseType": "single", "name": "old", "albumTitles": ["Purple Lamborghini - Single"]},
        {"id": 35, "releaseType": "single", "name": "new", "albumTitles": ["Purple Lamborghini"]},
        {"id": 36, "releaseType": "single", "name": "old", "albumTitles": ["Slam Dunk - Single"]},
        {"id": 37, "releaseType": "single", "name": "new", "albumTitles": ["Slam Dunk"]},
        {"id": 38, "releaseType": "single", "name": "old", "albumTitles": ["Waiting - Single"]},
        {"id": 39, "releaseType": "single", "name": "new", "albumTitles": ["Waiting"]},
        {"id": 40, "releaseType": "single", "name": "old", "albumTitles": ["Would You Ever - Single"]},
        {"id": 41, "releaseType": "single", "name": "new", "albumTitles": ["Would You Ever"]},
    ]
    mcc._assign_release_map_display_groups(grouping_probe)

    def _probe_keys(ids: Set[int]) -> Set[str]:
        return {
            str(row.get("displayGroupKey", ""))
            for row in grouping_probe
            if int(row.get("id", -1)) in ids
        }

    if len(_probe_keys({1, 2, 3, 4, 5})) != 1:
        raise RuntimeError("Release Map grouping self-test failed: Let Go editions split.")
    if len(_probe_keys({6, 7, 8})) != 1:
        raise RuntimeError("Release Map grouping self-test failed: The Best Damn Thing clean/limited editions split.")
    if len(_probe_keys({9, 10})) != 1:
        raise RuntimeError("Release Map grouping self-test failed: Avril Lavigne editions split.")
    if len(_probe_keys({11, 12})) != 1:
        raise RuntimeError("Release Map grouping self-test failed: Head Above Water instrumental/base editions split.")
    if len(_probe_keys({13, 14, 15, 16, 17})) != 1:
        raise RuntimeError("Release Map grouping self-test failed: These Hopeful Machines folder variants split.")
    for ids, label in [
        ({18, 19}, "More Monsters and Sprites"),
        ({20, 21}, "Bangarang"),
        ({22, 23}, "Kora"),
        ({24, 25}, "Burial"),
        ({26, 27}, "Bun Up the Dance"),
        ({28, 29}, "Squad Out"),
        ({30, 31}, "Working for It"),
        ({32, 33}, "No Chill"),
        ({34, 35}, "Purple Lamborghini"),
        ({36, 37}, "Slam Dunk"),
        ({38, 39}, "Waiting"),
        ({40, 41}, "Would You Ever"),
    ]:
        if len(_probe_keys(ids)) != 1:
            raise RuntimeError(f"Release Map grouping self-test failed: {label} source-title variants split.")

    soma_old = mcc.Release(
        rid=5001,
        root_kind="existing",
        path=Path("OLD SOMA"),
        title="SOMA",
        release_type="album",
        family="soma",
        source_medium="WEB",
        tracks=[
            mcc.Track(release_id=5001, path=Path("old1.m4a"), index=1, title="Soma", group_id=7001),
            mcc.Track(release_id=5001, path=Path("old2.m4a"), index=2, title="Thistle", group_id=7002),
        ],
    )
    soma_new = mcc.Release(
        rid=5002,
        root_kind="recycle",
        path=Path("NEW SOMA"),
        title="SOMA",
        release_type="album",
        family="soma",
        source_medium="WEB",
        tracks=[
            mcc.Track(release_id=5002, path=Path("new1.flac"), index=3, title="Soma", group_id=7001),
            mcc.Track(release_id=5002, path=Path("new2.flac"), index=4, title="Thistle", group_id=7002),
        ],
    )
    soma_selected = mcc.prefer_existing_equivalent_releases([soma_old, soma_new], {soma_new.rid})
    if soma_selected != {soma_old.rid}:
        raise RuntimeError("Existing-preference self-test failed: same-content WEB must not become WEB -> WEB upgrade.")
    if mcc._release_upgrade_reason(soma_new, soma_old):
        raise RuntimeError("Upgrade-label self-test failed: same-content WEB -> WEB must not be called an upgrade.")

    # v0.3.5: provider release-type tags must not churn exact-equivalent audio.
    soma_new.release_type = "ep"
    soma_selected = mcc.prefer_existing_equivalent_releases([soma_old, soma_new], {soma_new.rid})
    if soma_selected != {soma_old.rid}:
        raise RuntimeError("Existing-preference self-test failed: Album/EP metadata mismatch caused churn.")

    # v0.3.7: real Skrillex regression - OLD tagged EP, NEW tagged Album,
    # 11 physically carried tracks, 7 wanted acoustically identical groups.
    # The old physical release must satisfy the album representation instead
    # of triggering a false churn or a fatal album completeness assertion.
    def scary_edition(rid: int, root: str, kind: str, suffix: str) -> mcc.Release:
        title = "Scary Monsters and Nice Sprites (Deluxe Tour Edition)" + suffix
        song_tracks = [
            mcc.Track(
                release_id=rid,
                path=Path(f"{rid}-song-{i}.m4a"),
                index=rid * 100 + i,
                title=f"Matched song {i}",
                album=title,
                group_id=7100 + i,
            )
            for i in range(7)
        ]
        remix_tracks = [
            mcc.Track(
                release_id=rid,
                path=Path(f"{rid}-remix-{i}.m4a"),
                index=rid * 100 + 7 + i,
                title=f"Excluded remix {i}",
                album=title,
                exclude_from_coverage=True,
            )
            for i in range(4)
        ]
        return mcc.Release(
            rid=rid, root_kind=root, path=Path(f"Scary {root}"),
            title=title, release_type=kind, source_medium="WEB",
            tracks=song_tracks + remix_tracks,
        )

    scary_old = scary_edition(5601, "existing", "ep", " - EP")
    scary_new = scary_edition(5602, "recycle", "album", "")
    scary_aliases = mcc._album_requirement_provider_ids([scary_new], [scary_old, scary_new])
    if scary_aliases != {scary_old.rid, scary_new.rid}:
        raise RuntimeError(
            f"Album/EP source alias self-test failed: {sorted(scary_aliases)}"
        )
    scary_result = mcc.optimize_collection(
        [scary_old, scary_new], {},
    )
    if scary_result != {scary_old.rid}:
        raise RuntimeError(
            f"Scary Monsters no-churn self-test failed: {sorted(scary_result)}"
        )
    # A shorter unrelated EP cannot stand in for a complete album edition.
    scary_partial = scary_edition(5603, "existing", "ep", " - EP")
    scary_partial.tracks = scary_partial.tracks[:-5]
    if scary_partial.rid in mcc._album_requirement_provider_ids(
        [scary_new], [scary_partial, scary_new]
    ):
        raise RuntimeError("Album alias self-test failed: accepted incomplete EP.")


    # v0.4.5 real Weeknd log shape, 2026-10-10 05:54:
    # CD Starboy: 19 files, 18 wanted core groups, best physical source;
    # WEB Deluxe: 21 files, same 18 groups + two wanted featured remixes,
    #             plus one unwanted Kygo remix;
    # Reminder single: one physical file; Die for You single: four.
    # Both remix singles were independently proven acoustic MATCH to Deluxe.
    starboy_core_ids = list(range(41000, 41018))
    bonus_reminder, bonus_die, remix_unwanted = 41018, 41019, 41020

    def _starboy_release(rid, root, name, source, groups, bonus_tracks=None):
        tracks = [
            mcc.Track(rid, Path(f"{rid:03d}-{i:02d}.flac"), i, title=f"Core {i}",
                  group_id=gid)
            for i, gid in enumerate(groups, 1)
        ]
        tracks.extend(bonus_tracks or [])
        return mcc.Release(
            rid, root, Path(name), "Starboy" + (" (Deluxe)" if "Deluxe" in name else ""),
            release_type="album", source_medium=source, tracks=tracks,
        )

    cd_starboy = _starboy_release(
        410, "existing", "2016-11-28 - Starboy [US - B0026150-02]",
        "CD", starboy_core_ids,
        [mcc.Track(410, Path("CD-unwanted-live"), 19, title="Live",
               group_id=remix_unwanted, is_live=True,
               exclude_from_coverage=True)]
    )
    reminder_bonus = mcc.Track(
        411, Path("21 Reminder Remix"), 21, title="Reminder (Remix)",
        group_id=bonus_reminder, is_remix=True, remix_feature_exception=True,
    )
    die_bonus = mcc.Track(
        411, Path("19 Die for You Remix"), 19, title="Die for You (Remix)",
        group_id=bonus_die, is_remix=True, remix_feature_exception=True,
    )
    kygo_bonus = mcc.Track(
        411, Path("20 Kygo Remix"), 20, title="Starboy (Kygo Remix)",
        group_id=remix_unwanted, is_remix=True, exclude_from_coverage=True,
    )
    web_deluxe = _starboy_release(
        411, "recycle", "2016-11-24 - Starboy (Deluxe) [602455499851]",
        "Digital Media", starboy_core_ids,
        [die_bonus, kygo_bonus, reminder_bonus],
    )
    reminder_single = mcc.Release(
        412, "existing", Path("2017-08-01 - Reminder (Remix) - Single"),
        "Reminder (Remix)", release_type="single", source_medium="WEB",
        tracks=[mcc.Track(412, Path("Reminder Remix single"), 1,
                      title="Reminder (Remix)", group_id=bonus_reminder)],
    )
    die_single = mcc.Release(
        413, "existing", Path("2023-02-24 - Die for You (Remix) - Single"),
        "Die for You (Remix)", release_type="single", source_medium="WEB",
        tracks=[
            mcc.Track(413, Path(f"Die for You single {i}"), i, title=f"Die for You {i}",
                  group_id=gid)
            for i, gid in enumerate((bonus_die, 41030, 41031, 41032), 1)
        ],
    )
    starboy_pool = [cd_starboy, web_deluxe, reminder_single, die_single]
    if {len(r.tracks) for r in (cd_starboy, web_deluxe)} != {19, 21}:
        raise RuntimeError("Starboy log shape was not preserved.")
    if not _album_core_with_separate_remix_bonuses(cd_starboy, web_deluxe, starboy_pool):
        raise RuntimeError("Starboy full CD core was rejected for independent remix bonuses.")
    if cd_starboy.rid not in mcc._album_requirement_provider_ids(
        [cd_starboy, web_deluxe], starboy_pool
    ):
        raise RuntimeError("Starboy album family failed to accept the complete CD core.")
    if cd_starboy.rid in mcc.find_dominated_releases(starboy_pool):
        raise RuntimeError("Starboy CD core was incorrectly pruned by WEB Deluxe.")
    expected = {cd_starboy.rid, reminder_single.rid, die_single.rid}
    result = mcc.optimize_collection(starboy_pool, {})
    if result != expected:
        raise RuntimeError(
            f"Starboy CD+Singles regression: got {sorted(result)}, expected {sorted(expected)}."
        )
    if sum(r.track_count for r in starboy_pool if r.rid in result) != 24:
        raise RuntimeError("Starboy minimum-track solution should retain exactly 24 physical files.")
    if set().union(*(r.groups for r in starboy_pool if r.rid in result)) != set().union(
        *(r.groups for r in starboy_pool)
    ):
        raise RuntimeError("Starboy collection lost wanted audio groups.")


    # 2026-10-15 CD-first Ceinture noire regression: 57-track EU CD
    # completely covers a 55-track WEB, but the smaller edition used to
    # win solely by physical track count. A bonus album holds a genuine
    # GIMS+Quincy performance not present on the CD.
    cd_core_gids = list(range(620000, 620057))
    def _gims_album(rid, name, medium, gids, extra_guest=False):
        items = [
            mcc.Track(rid, Path(f"{rid}-{i}.flac"), i,
                  title=f"Core song {gid}", artist="GIMS", group_id=gid)
            for i, gid in enumerate(gids, 1)
        ]
        if extra_guest:
            items.extend((
                mcc.Track(
                    rid, Path(f"{rid}-Caméléon-feat-Quincy.flac"), len(items)+1,
                    title="Caméléon", artist="GIMS;Quincy", duration=207.04,
                    group_id=620500,
                ),
                mcc.Track(
                    rid, Path(f"{rid}-La-nuit-edit.flac"), len(items)+2,
                    title="La nuit c'est fait pour dormir",
                    artist="GIMS;Orelsan;H Magnum", duration=251.44,
                    group_id=620501,
                ),
            ))
        return mcc.Release(
            rid, "existing" if medium == "CD" else "recycle",
            Path(name), "Ceinture noire", release_type="album",
            source_medium=medium, tracks=items,
        )
    gims_cd = _gims_album(
        6201, "Ceinture noire (Décennie) [EU - 19439710432 - 2019]",
        "CD", cd_core_gids,
    )
    gims_web = _gims_album(
        6202, "Ceinture noire (Décennie) [3616402785413]",
        "WEB", cd_core_gids[:55],
    )
    gims_bonus = _gims_album(
        6203, "Ceinture noire [3615930950287]", "WEB",
        cd_core_gids[:39], extra_guest=True,
    )
    gims_pool = [gims_cd, gims_web, gims_bonus]
    if mcc._album_requirement_provider_ids(gims_pool, gims_pool) != {gims_cd.rid}:
        raise RuntimeError("Ceinture noire CD was not the mandatory album-family anchor.")
    gims_solution = mcc.optimize_collection(gims_pool, {})
    if gims_solution != {gims_cd.rid, gims_bonus.rid}:
        raise RuntimeError(
            f"Ceinture noire CD + guest recording not preserved: {sorted(gims_solution)}"
        )
    featured_single = mcc.Release(
        6204, "recycle", Path("Caméléon feat Quincy - Single"),
        "Caméléon (feat. Quincy)", release_type="single",
        source_medium="WEB", tracks=[
            mcc.Track(6204, Path("Caméléon Quincy Single.flac"), 1,
                  title="Caméléon (feat. Quincy)", artist="GIMS;Quincy",
                  group_id=620500)
        ],
    )
    gims_with_one_single = mcc.optimize_collection(gims_pool + [featured_single], {})
    if gims_with_one_single != {gims_cd.rid, gims_bonus.rid}:
        raise RuntimeError(
            "A single external guest copy cannot erase the album-only La nuit version."
        )
    night_single = mcc.Release(
        6205, "recycle", Path("La nuit - Single"),
        "La nuit c'est fait pour dormir", release_type="single",
        source_medium="WEB", tracks=[
            mcc.Track(6205, Path("La nuit edit single.flac"), 1,
                  title="La nuit c'est fait pour dormir",
                  artist="GIMS;Orelsan;H Magnum", group_id=620501)
        ],
    )
    gims_with_both_singles = mcc.optimize_collection(
        gims_pool + [featured_single, night_single], {}
    )
    if gims_with_both_singles != {gims_cd.rid, featured_single.rid, night_single.rid}:
        raise RuntimeError(
            "All exclusive recordings sourced separately should leave CD as "
            f"only family album: {sorted(gims_with_both_singles)}"
        )

    blocked_reminder = mcc.optimize_collection(
        starboy_pool, {}, blocked_release_ids={reminder_single.rid}
    )
    if web_deluxe.rid not in blocked_reminder or cd_starboy.rid in blocked_reminder:
        raise RuntimeError("Without Reminder single, the Deluxe covers CD without retaining CD.")

    # Camo & Krooked: incomplete 14-track CD cannot displace an 18-track
    # full WEB Deluxe whose four bonus groups have no outside-family source.
    ck_cd = _gims_album(6301, "Cross the Line [CD]", "CD", list(range(630000,630014)))
    ck_web = _gims_album(6302, "Cross the Line (Special Edition)", "WEB", list(range(630000,630018)))
    ck_pool = [ck_cd, ck_web]
    if mcc._album_requirement_provider_ids(ck_pool, ck_pool) != {ck_cd.rid,ck_web.rid}:
        raise RuntimeError("CD priority forced an incomplete edition without bonus sources.")
    ck_solution = mcc.optimize_collection(ck_pool, {})
    if ck_solution != {ck_web.rid}:
        raise RuntimeError("CD anchor stole the unique WEB Deluxe bonus tracks.")

    # Ordinary album bonuses must remain covered, but need not come from
    # the largest album if a separate eligible carrier already has them.
    ordinary_bonus = mcc.Track(
        411, Path("22 Exclusive Bonus"), 22, title="Exclusive album song",
        group_id=41033,
    )
    web_deluxe.tracks.append(ordinary_bonus)
    ordinary_single = mcc.Release(
        414, "existing", Path("Exclusive single"), "Exclusive",
        release_type="single", source_medium="WEB",
        tracks=[mcc.Track(414, Path("Exclusive audio"), 1,
                      title="Exclusive album song", group_id=41033)],
    )
    if _album_core_with_separate_remix_bonuses(
        cd_starboy, web_deluxe, starboy_pool + [ordinary_single]
    ):
        raise RuntimeError("Regular bonus song incorrectly treated as a standalone remix.")
    if cd_starboy.rid not in mcc._album_requirement_provider_ids(
        [cd_starboy, web_deluxe], starboy_pool + [ordinary_single]
    ):
        raise RuntimeError("A smaller album no longer fulfills its family requirement.")
    if 41033 not in ordinary_single.groups:
        raise RuntimeError("Ordinary bonus recording must remain eligible for coverage.")
    web_deluxe.tracks.pop()

    # Even a featured remix bonus cannot be treated as standalone when its
    # external source is blocked or absent from the eligible pool.
    if _album_core_with_separate_remix_bonuses(
        cd_starboy, web_deluxe, [cd_starboy, web_deluxe, die_single]
    ):
        raise RuntimeError("Album core accepted despite unavailable Reminder single.")
    # Weaker-source smaller core is never licensed by a better-source deluxe.
    cd_starboy.source_medium = "WEB"
    web_deluxe.source_medium = "CD"
    if _album_core_with_separate_remix_bonuses(
        cd_starboy, web_deluxe, starboy_pool
    ):
        raise RuntimeError("Weaker-source album improperly displaced a higher-source deluxe.")

    # MCC v0.5.9 - INNA I Am the Club Rocker real-log-shaped test.
    # Short WEB edits and CD No Limit are separately wanted under the
    # existing fingerprint decisions. Japanese CD audio is covered by other
    # selected releases and must not be kept only for maximum track count.
    def _club_album(rid, name, gids, medium="CD", kind="album"):
        return mcc.Release(
            rid, "recycle", Path(name), name, release_type=kind,
            source_medium=medium, tracks=[
                mcc.Track(rid, Path(f"{rid}-{i}.flac"), i, title=f"Track {gid}",
                      artist="INNA", group_id=gid)
                for i, gid in enumerate(gids, 1)
            ],
        )
    club_common = list(range(1, 11))
    club_web = _club_album(99011, "Club Rocker 2011 WEB",
                           club_common + [11, 12], "WEB")
    club_cd = _club_album(99012, "Club Rocker 2011 CD",
                          club_common + [13])
    club_japan = _club_album(99013, "Club Rocker Japan CD",
                             club_common + [14, 15, 16, 17, 18])
    other_issued = _club_album(99014, "Other available songs",
                               [14, 15, 16, 17, 18], "WEB", "ep")
    club_family = [club_web, club_cd, club_japan]
    choices = mcc._album_requirement_provider_ids(club_family, club_family + [other_issued])
    if choices != {club_web.rid, club_cd.rid, club_japan.rid}:
        raise RuntimeError(
            "Unrelated Japanese CD incorrectly forced despite not covering the "
            f"largest WEB edition: {sorted(choices)}"
        )
    if len(mcc._album_clusters(club_family)) != 1:
        raise RuntimeError("Club Rocker alternate albums split into different families.")
    proposed = mcc.optimize_collection(club_family + [other_issued], {})
    expected = {club_web.rid, club_cd.rid, other_issued.rid}
    if proposed != expected:
        raise RuntimeError("Redundant Japanese CD unexpectedly retained: " + str(sorted(proposed)))
    all_wanted = set().union(*(r.groups for r in club_family + [other_issued]))
    covered = set().union(*(r.groups for r in club_family + [other_issued] if r.rid in proposed))
    if covered != all_wanted:
        raise RuntimeError("Dropping the Japanese CD lost wanted audio.")
    if club_japan.rid not in mcc.optimize_collection(club_family, {}):
        raise RuntimeError("Unique Japanese bonus audio was lost with no alternative carrier.")

    # Real Cross the Line log (2026-10-11): the existing CD album has 14
    # wanted fingerprint groups. Incoming 18-track WEB Special Edition contains
    # those same 14 + four unique bonus recordings with no other carrier.
    # A strict superset MUST win, even when its source rank is lower than CD.
    cross_cd = mcc.Release(
        rid=8401, root_kind="existing",
        path=Path("2011-10-03 - Cross the Line [EU - NHS194CD]"),
        title="Cross the Line", release_type="album", source_medium="CD",
        tracks=[
            mcc.Track(8401, Path(f"CD {i}.m4a"), i, title=f"Cross track {i}", group_id=84000+i)
            for i in range(1, 15)
        ],
    )
    cross_special = mcc.Release(
        rid=8402, root_kind="recycle",
        path=Path("2011-10-03 - Cross the Line (Special Edition) [3617056553892]"),
        title="Cross the Line (Special Edition)",
        release_type="album", source_medium="Digital Media",
        tracks=[
            mcc.Track(8402, Path(f"WEB {i}.flac"), i, title=f"Cross track {i}", group_id=84000+i)
            for i in range(1, 19)
        ],
    )
    if not mcc._release_covers(cross_special, cross_cd) or mcc._release_covers(cross_cd, cross_special):
        raise RuntimeError("Cross the Line acoustic subset relationship failed.")
    if cross_cd.rid not in mcc.find_dominated_releases([cross_cd, cross_special]):
        raise RuntimeError("Superset did not dominate lower-track CD original.")
    if mcc.optimize_collection([cross_cd, cross_special], {}) != {cross_special.rid}:
        raise RuntimeError("Cross the Line must keep 18-track WEB Special Edition ONLY.")

    # Exact FULL duplicates are different: preserve the original/better CD.
    cross_web_duplicate = mcc.Release(
        rid=8403, root_kind="recycle", path=Path("Cross the Line 14-track WEB"),
        title="Cross the Line", release_type="album", source_medium="WEB",
        tracks=[
            mcc.Track(8403, Path(f"WEBdup {i}.flac"), i, title=f"Cross track {i}", group_id=84000+i)
            for i in range(1, 15)
        ],
    )
    if mcc.optimize_collection([cross_cd, cross_web_duplicate], {}) != {cross_cd.rid}:
        raise RuntimeError("CD must win a complete audio-identical duplicate.")

    # v0.3.8 regression from the real Skrillex Dirty Vibe v0.3.7 log.
    # Both "Jack Beats Re-work" files were retained by mistake; all other
    # three remix tracks on each edition were already excluded.
    samples = [
        "Dirty Vibe (ft. G-Dragon & CL) [Jack Beats re-work]",
        "Dirty Vibe (with Diplo, G-Dragon, and CL) (Jack Beats Re-work)",
        "Dirty Vibe (Jack Beats Rework)",
        "Dirty Vibe (Jack Beats Reworked)",
        "Dirty Vibe - Jack Beats Re-work",
    ]
    if not all(mcc.is_remix_text(title) for title in samples):
        raise RuntimeError("Dirty Vibe remix self-test failed: Re-work not recognized.")
    if any(mcc.is_remix_text(title) for title in (
        "Rework Your Life", "How to Rework Your Workflow", "My Reworked World"
    )):
        raise RuntimeError("Dirty Vibe remix self-test failed: false-positive ordinary title.")

    def dirty_vibe_edition(rid, root, prefix, bracket):
        variants = [
            "DJ Snake & Aazar Remix", "Habstrakt Remix",
            "Jack Beats re-work", "Ricky Remedy Remix",
        ]
        tracks = [
            mcc.Track(
                release_id=rid,
                path=Path(f"{i:02d} Dirty Vibe ({variant}).m4a"),
                index=rid * 100 + i,
                title=f"{prefix} {bracket[0]}{variant}{bracket[1]}",
                album="Dirty Vibe (Remixes)",
                artist="Skrillex with Diplo, G-Dragon and CL",
            )
            for i, variant in enumerate(variants, start=1)
        ]
        return mcc.Release(
            rid=rid, root_kind=root, path=Path(f"Dirty Vibe {rid}"),
            title="Dirty Vibe (Remixes)", release_type="ep", source_medium="WEB",
            tracks=tracks,
        )

    old_dirty = dirty_vibe_edition(
        6012, "existing", "Dirty Vibe (ft. G-Dragon & CL)", "[]"
    )
    new_dirty = dirty_vibe_edition(
        6074, "recycle", "Dirty Vibe (with Diplo, G-Dragon, and CL)", "()"
    )
    # No Personal Picks: with Save Remixes OFF, every ordinary remix on
    # these editions must be excluded. Do not put a positive Keep override
    # in a fixture that expects all remixes to be removed.
    mcc.configure_exclusions(
        [old_dirty, new_dirty], exclude_remixes=True, exclude_live=True,
    )
    dirty_tracks = old_dirty.tracks + new_dirty.tracks
    if not all(
        track.is_remix and track.exclude_from_coverage
        and not track.remix_feature_exception for track in dirty_tracks
    ):
        raise RuntimeError("Dirty Vibe remix self-test failed: remix-only audio kept.")
    if not old_dirty.excluded_only or not new_dirty.excluded_only:
        raise RuntimeError("Dirty Vibe remix self-test failed: remix-only EP still wanted.")
    if mcc.optimize_collection([old_dirty, new_dirty], {}) != set():
        raise RuntimeError("Dirty Vibe remix self-test failed: remix-only EP retained.")

    # v0.3.9: excluded OLD remix-only EPs must show in Changes > Removed
    # and remain inspectable in Full Map. Excluded NEW EPs are SKIP.
    dirty_decisions = mcc.build_release_decisions(
        [old_dirty, new_dirty], dirty_tracks, selected=set(), reviews=[],
    )
    dirty_by_id = {decision.release_id: decision for decision in dirty_decisions}
    if dirty_by_id[old_dirty.rid].action != "REMOVE":
        raise RuntimeError("Excluded-remix map self-test failed: OLD not REMOVE.")
    if dirty_by_id[new_dirty.rid].action != "SKIP":
        raise RuntimeError("Excluded-remix map self-test failed: NEW not SKIP.")
    if dirty_by_id[old_dirty.rid].reason != "All 4 tracks excluded (Save Remixes OFF).":
        raise RuntimeError("Excluded-remix map self-test failed: missing reason.")
    dirty_snapshots = mcc.build_decision_snapshot(
        [old_dirty, new_dirty], dirty_tracks, set(), dirty_decisions,
    )
    dirty_map = mcc._release_map_state_for_ui(
        dirty_snapshots, dirty_tracks, set(), set(), set(),
        editable=True, dirty=False, apply_enabled=True, apply_highlighted=False,
    )
    dirty_nodes = {node["id"]: node for node in dirty_map["nodes"]}
    if set(dirty_nodes) != {old_dirty.rid, new_dirty.rid}:
        raise RuntimeError("Excluded-remix map self-test failed: hidden analyzed EP.")
    if (
        dirty_nodes[old_dirty.rid]["rootKind"] != "existing"
        or dirty_nodes[old_dirty.rid]["action"] != "REMOVE"
        or dirty_nodes[old_dirty.rid]["kind"] != "duplicate"
        or len(dirty_nodes[old_dirty.rid]["tracks"]) != 4
        or any(row["included"] for row in dirty_nodes[old_dirty.rid]["tracks"])
    ):
        raise RuntimeError("Excluded-remix map self-test failed: OLD not visible/removable.")
    if dirty_nodes[new_dirty.rid]["action"] != "SKIP":
        raise RuntimeError("Excluded-remix map self-test failed: NEW not SKIP.")
    if dirty_map["planCounts"]["result"] != {"releases": 0, "tracks": 0}:
        raise RuntimeError("Excluded-remix map self-test failed: SKIP affects plan counts.")
    if 'if(root==="existing"&&action!=="KEEP"&&n.kind==="duplicate") return "removed";' not in map_html:
        raise RuntimeError("Excluded-remix map self-test failed: Removed routing missing.")

    mcc.configure_exclusions([old_dirty, new_dirty], exclude_remixes=False, exclude_live=True)
    if any(track.exclude_from_coverage for track in dirty_tracks):
        raise RuntimeError("Dirty Vibe remix self-test failed: Save Remixes ON removed tracks.")

    # Personal Picks intentionally OVERRIDE Save Remixes OFF. A saved
    # "Jack Beats" preference rescues only those two Re-work tracks; it
    # must not silently rescue the other three mixes on either edition.
    mcc.configure_exclusions(
        [old_dirty, new_dirty], exclude_remixes=True, exclude_live=True,
        personal_keep_rules=[{"mode": "contains", "value": "Jack Beats"}],
    )
    picked_dirty = [t for t in dirty_tracks if "jack beats" in t.display_title.casefold()]
    other_dirty = [t for t in dirty_tracks if "jack beats" not in t.display_title.casefold()]
    if (
        len(picked_dirty) != 2 or len(other_dirty) != 6
        or any(t.exclude_from_coverage or t.personal_keep_rule != "Jack Beats"
               for t in picked_dirty)
        or any(not t.exclude_from_coverage or t.personal_keep_rule for t in other_dirty)
        or old_dirty.excluded_only or new_dirty.excluded_only
    ):
        raise RuntimeError("Dirty Vibe Personal Picks self-test failed: saved Re-work override lost or leaked.")

    # Disabling the explicit preference must restore the original
    # remix-only exclusions with no sticky temporary Keep rule.
    mcc.configure_exclusions([old_dirty, new_dirty], exclude_remixes=True, exclude_live=True)
    if not all(t.exclude_from_coverage and not t.personal_keep_rule for t in dirty_tracks):
        raise RuntimeError("Dirty Vibe Personal Picks self-test failed: clearing preference did not re-exclude tracks.")

    feature_track = mcc.Track(
        release_id=6013,
        path=Path("Dirty Vibe (Jack Beats Re-work ft. New Singer).m4a"),
        index=1,
        title="Dirty Vibe (Jack Beats Re-work ft. New Singer)",
        album="Dirty Vibe (Remixes)",
        artist="Skrillex",
    )
    feature_release = mcc.Release(
        rid=6013, root_kind="recycle", path=Path("Dirty Vibe ft new guest"),
        title="Dirty Vibe (Remixes)", release_type="ep", tracks=[feature_track],
    )
    mcc.configure_exclusions([feature_release], exclude_remixes=True, exclude_live=False)
    if (not feature_track.is_remix or not feature_track.remix_feature_exception
            or feature_track.exclude_from_coverage):
        raise RuntimeError("Dirty Vibe remix self-test failed: added-feature exception lost.")

    # New rule: a WEB strict audio superset with a wanted bonus may replace
    # its shorter CD original. Only FULL duplicate editions prefer CD.
    cd_common = mcc.Release(
        rid=5101,
        root_kind="existing",
        path=Path("OLD CD"),
        title="Bangarang",
        release_type="ep",
        source_medium="CD",
        tracks=[
            mcc.Track(release_id=5101, path=Path(f"CD {i}.flac"), index=5200+i, title=f"Song {i}", group_id=5300+i)
            for i in range(1, 8)
        ],
    )
    web_superset = mcc.Release(
        rid=5102,
        root_kind="recycle",
        path=Path("NEW WEB"),
        title="Bangarang",
        release_type="ep",
        source_medium="WEB",
        tracks=[
            mcc.Track(release_id=5102, path=Path(f"WEB {i}.flac"), index=5400+i, title=f"Song {i}", group_id=5300+i)
            for i in range(1, 8)
        ] + [
            mcc.Track(release_id=5102, path=Path("Bonus.flac"), index=5499, title="Bonus", group_id=5399)
        ],
    )
    source_kept = mcc.optimize_collection([cd_common, web_superset], {})
    if source_kept != {web_superset.rid}:
        raise RuntimeError("Superset EP must not retain a redundant CD: " + str(source_kept))

    # Same album + same numbered slot must route even when provider wording differs.
    slot_old = mcc.Track(
        release_id=5501,
        path=Path("11 Warped Tour '05 (ft. pete WENTZ).m4a"),
        index=1,
        title="Warped Tour '05 (ft. pete WENTZ)",
        album="Quest for Fire",
    )
    slot_new = mcc.Track(
        release_id=5502,
        path=Path("11 Warped Tour ’05 with pete WENTZ.flac"),
        index=2,
        title="Warped Tour ’05 with pete WENTZ",
        album="Quest For Fire",
    )
    if mcc._album_track_slot_route_key(slot_old) != mcc._album_track_slot_route_key(slot_new):
        raise RuntimeError("Album-slot routing self-test failed for Quest for Fire provider naming.")

    # v0.3.6: valid acoustic group zero stays visible in the Release Map.
    if mcc._release_map_group_id({"group_id": 0}) != 0 or mcc._release_map_group_id({"group_id": None}) != -1:
        raise RuntimeError("Release Map self-test failed: acoustic group ID conversion.")
    zero_snapshot = {
        "release_id": 5901, "name": "Group Zero", "release_type": "single",
        "root_kind": "existing", "action": "KEEP",
        "tracklist": [{"title": "First", "group_id": 0, "included": True, "excluded": False}],
    }
    zero_map = mcc._release_map_state_for_ui(
        [zero_snapshot], None, set(), set(), set(), False, False, False, False,
    )
    if len(zero_map["nodes"]) != 1 or zero_map["nodes"][0]["tracks"][0]["groupId"] != 0:
        raise RuntimeError("Release Map self-test failed: group zero lost from visible map.")

    # Source quality is a tie-break: the full WEB superset alone covers all
    # wanted recordings without a redundant CD original.
    def make_cover(rid, medium, gids, root):
        return mcc.Release(
            rid=rid, root_kind=root, path=Path(f"Source {rid}"),
            title=f"Source {rid}", release_type="ep", source_medium=medium,
            tracks=[
                mcc.Track(rid, Path(f"{rid}-{gid}.flac"), gid, title=f"Song {gid}", group_id=gid)
                for gid in gids
            ],
        )
    cd_all = make_cover(5911, "CD", (1, 2, 3, 4), "existing")
    cd_half_a = make_cover(5912, "CD", (1, 2), "existing")
    cd_half_b = make_cover(5913, "CD", (3, 4), "existing")
    web_bonus = make_cover(5914, "WEB", (1, 2, 3, 4, 5), "recycle")
    cover_result, cover_stats = mcc.exact_global_collection_minimize(
        [cd_all, cd_half_a, cd_half_b, web_bonus], {web_bonus.rid},
    )
    if cover_result != {web_bonus.rid} or cover_stats.get("source_floor_requirements") != 0 or cover_stats.get("requirements") != 5:
        raise RuntimeError(
            f"Optimizer self-test failed: minimum-file source-tiebreak plan {sorted(cover_result)}."
        )
    # v0.5.62: 17/17 acoustically matching OLD Get to Heaven CD groups
    # are inside the selected 22-group NEW Expanded edition. Its title and
    # folder-derived album-family key differ; this remains ONE actual upgrade.
    def _upgrade_probe(rid: int, kind: str, name: str, gids: range,
                       artist: str = "Everything Everything") -> mcc.Release:
        return mcc.Release(
            rid, kind, Path(name), name, release_type="album",
            family=mcc.album_family(name), source_medium="CD" if kind=="existing" else "WEB",
            tracks=[
                mcc.Track(rid, Path(f"track-{rid}-{gid}.flac"), gid,
                      title=f"Track {gid}", artist=artist, group_id=gid)
                for gid in gids
            ],
        )
    old_expanded = _upgrade_probe(
        59701, "existing", "Get to Heaven (Deluxe Edition)", range(1, 18))
    new_expanded = _upgrade_probe(
        59702, "recycle", "Get to Heaven (Expanded 10th Anniversary Edition)",
        range(1, 23))
    if old_expanded.family == new_expanded.family:
        raise RuntimeError("Upgrade regression fixture must have different family keys.")
    if not mcc._related_replacement_release(new_expanded, old_expanded):
        raise RuntimeError("Audio-proven expanded edition was not recognized as a replacement.")
    upgrade_decisions = {
        d.release_id: d
        for d in mcc.build_release_decisions(
            [old_expanded, new_expanded], [],
            {new_expanded.rid}, {}
        )
    }
    if (
        upgrade_decisions[new_expanded.rid].action != "REPLACE"
        or upgrade_decisions[new_expanded.rid].related_release_ids != [old_expanded.rid]
        or "+5 recording(s)" not in upgrade_decisions[new_expanded.rid].reason
    ):
        raise RuntimeError("Get to Heaven 17/22 upgrade was mislabeled as ADD.")
    unrelated = _upgrade_probe(
        59703, "existing", "Completely Different Record", range(1, 18),
        artist="Other Artist")
    if mcc._related_replacement_release(new_expanded, unrelated):
        raise RuntimeError("Different-artist album falsely classified as upgrade.")
    unrelated_audio = _upgrade_probe(
        59704, "existing", "Unrelated Album", range(100, 117))
    if mcc._related_replacement_release(new_expanded, unrelated_audio):
        raise RuntimeError("Unmatched audio falsely classified as upgrade.")
    if not (
        'const old=byId.get(Number(ref.releaseId));' in map_html
        and 'if(oldToTarget.has(oldId))return;' in map_html
        and 'changeKind(n)==="upgraded"' in map_html
    ):
        raise RuntimeError("Release Map upgrade counter or source pairing regression.")

    if not (
        "let replacementCache=null;" in map_html
        and "if(replacementCache)return replacementCache;" in map_html
        and "![...a].every(function(gid){return b.has(gid);})" in map_html
    ):
        raise RuntimeError("Release Map self-test failed: replacement coverage/cache guard missing.")

    # Current selected-links contract supersedes the old all-links opacity
    # constants. This is a source contract, not a claim of visual acceptance.
    expected_strokes = (
        'border-top:2px solid #303947',
        'if(showAllConnections)addCurveBatch(svg,dupNormal,"#758296",1.3,0.12)',
        'addCurveBatch(svg,dupTouch,"#91b7e6",2.8,0.84)',
        'addCurveBatch(svg,versions,"#f3c969",3.0,0.90',
        'addCurveBatch(svg,remixes,"#b989ef",2.65,0.76',
        'addCurveBatch(svg,live,"#6ee7b7",2.65,0.78',
        'addCurveBatch(svg,carriers,"#55d7ff",3.6,0.95)',
    )
    if not all(part in map_html for part in expected_strokes):
        raise RuntimeError("Release Map self-test failed: v0.4.0 line legibility regression.")

    failed_ui_checks = [message for ok, message in ui_checks if not ok]
    if failed_ui_checks:
        raise RuntimeError("Global UI compliance self-test failed: " + " | ".join(failed_ui_checks))


def _album_core_with_separate_remix_bonuses(
    core: mcc.Release,
    deluxe: mcc.Release,
    releases: List[mcc.Release],
) -> bool:
    """Can the full core album represent its family without a bonus-remix deluxe?

    Narrow exception: the larger edition adds ONLY included, independently
    available featured remixes, and every added acoustic group is also available
    on a separate Single/EP in the currently eligible pool. Original songs,
    exclusive versions, missing singles, and weaker-source core albums do not
    qualify. Group IDs come only from previously accepted audio comparisons.
    """
    if core.rid == deluxe.rid or core.release_type != "album" or deluxe.release_type != "album":
        return False
    if core.excluded_only or deluxe.excluded_only:
        return False
    core_name = mcc.normalize_title(mcc._release_map_family_base(core.title, core.release_type))
    deluxe_name = mcc.normalize_title(mcc._release_map_family_base(deluxe.title, deluxe.release_type))
    if not core_name or core_name != deluxe_name:
        return False
    if not mcc._album_editions_related_by_audio(core, deluxe):
        return False
    if not mcc._release_covers(deluxe, core) or mcc._release_covers(core, deluxe):
        return False
    if mcc.source_rank(core) < mcc.source_rank(deluxe):
        return False

    missing = deluxe.groups - core.groups
    if not missing:
        return False
    for gid in missing:
        added_tracks = [
            t for t in deluxe.tracks
            if mcc._track_coverage_gid(t) == gid and not t.exclude_from_coverage
        ]
        if not added_tracks or not all(
            t.is_remix and t.remix_feature_exception for t in added_tracks
        ):
            return False
        # A different, eligible SINGLE/EP must actually supply this recording.
        # An unrelated compilation or album is not a substitute for core music.
        if not any(
            rel.rid not in {core.rid, deluxe.rid}
            and rel.release_type in {"single", "ep"}
            and not rel.excluded_only
            and gid in rel.groups
            for rel in releases
        ):
            return False
    return True


def _replaceable_version_acoustic_evidence(a: mcc.Track, b: mcc.Track, sim) -> bool:
    """A length-distinct edit can substitute for its parent, not become identical.

    Conservative gate: same recording root/title and performer, near-complete
    positive Chromaprint alignment, no remixes/extended/instrumental/etc.
    Significant duration remains visible as a distinct Version.
    """
    if not sim or not a.fingerprint or not b.fingerprint:
        return False
    if not mcc._duration_version_conflict(a.duration, b.duration):
        return False
    if a.exclude_from_coverage or b.exclude_from_coverage:
        return False
    if a.is_remix or b.is_remix or a.is_live or b.is_live:
        return False
    if mcc._unique_recording_root_family(a) or mcc._unique_recording_root_family(b):
        return False
    if mcc._semantic_version_conflict(a, b):
        return False
    # The guest's name may be in TITLE or only in ARTIST. A featured
    # performance is not a replaceable Edit of the original recording.
    if _track_guest_signature(a) != _track_guest_signature(b):
        return False
    title_a, title_b = mcc._base_title_identity(a.display_title), mcc._base_title_identity(b.display_title)
    if not title_a or title_a != title_b:
        return False
    primary_a, primary_b = mcc._primary_artist_key(a), mcc._primary_artist_key(b)
    if not primary_a or not primary_b or primary_a != primary_b:
        return False
    score, good, overlap, shift, excellent, median, p90 = sim
    if not (
        overlap >= 0.98 and score <= 5.0 and good >= 0.90
        and excellent >= 0.65 and median <= 5.0 and p90 <= 10
    ):
        return False
    start_a, start_b = max(int(shift), 0), max(-int(shift), 0)
    aligned = max(0, min(len(a.fingerprint)-start_a, len(b.fingerprint)-start_b))
    return aligned / max(1, len(a.fingerprint), len(b.fingerprint)) >= 0.90


def _lcs_length(a: List[int], b: List[int]) -> int:
    if not a or not b:
        return 0
    if len(a) > len(b):
        a, b = b, a
    prev = [0] * (len(a) + 1)
    for value_b in b:
        cur = [0]
        for j, value_a in enumerate(a, 1):
            if value_a == value_b:
                cur.append(prev[j - 1] + 1)
            else:
                cur.append(max(cur[-1], prev[j]))
        prev = cur
    return prev[-1]


def _track_guest_signature(track: mcc.Track) -> Set[str]:
    """Guest credits found in either TITLE or ARTIST; no acoustic identity claim."""
    return mcc._featured_credit_signature(track.display_title) | mcc._artist_tag_collaborators(track)


class UiSelfTest(unittest.TestCase):
    def test_ui_parity_contract_passes(self):
        _ui_contract_self_test()


if __name__ == '__main__':
    unittest.main()
