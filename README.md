# Music Collection Cleaner (MCC)

**Version: 0.5.12 - Under construction ⚠️**

Music Collection Cleaner compares existing music releases with new ones, finds the best combination of editions, and helps preserve every wanted unique recording while removing unnecessary redundancy.

## Download and run

**[Music Collection Cleaner v0.5.12.pyw](Music%20Collection%20Cleaner%20v0.5.12.pyw)** - versioned single-file Windows Python application. **This is a test build, not a stable Windows release.**

Open with Python 3 on Windows 11 (or run from a console with `python "Music Collection Cleaner v0.5.12.pyw"`). The application checks or installs supported dependencies. The GUI uses Microsoft Edge WebView2 through pywebview; it is not a terminal-based replacement.

Source-level regression checks: `python "Music Collection Cleaner v0.5.11.pyw" --ui-self-test`.

## What it does

- Analyze two pools: the existing library (OLD) and candidate additions (NEW).
- Compare recording identity using audio fingerprints, metadata, version-family safeguards and user review when necessary.
- Preserve unique wanted recordings; apply Remix, Live, Explicit/Clean and Personal Picks rules.
- Compare original, expanded, Deluxe, Special and other editions, including strict acoustic-superset detection.
- Prefer high-quality sources and CD rip logs among truly equivalent choices; use dynamic range only as an eligible final mastering tie-break.
- Optimize retained complete releases and physical track count across the library, not just isolated duplicate pairs.
- Inspect an interactive chronological **Release Map** with connections, per-track coverage, replacement explanations, Ignore/Restore and Re-Analyze.
- Explicitly **Copy OLD + NEW** or **Move OLD + NEW** retained releases into the selected destination; Undo for supported completed moves.
- Log comparisons, validate incomplete/corrupt inputs, choose I/O worker counts with drive awareness, and manage spawned subprocesses.


## v0.5.12 - auditable Re-Analyze and persistent Ignore

- **Re-Analyze is selection-only, not a new acoustic scan.** It reruns the complete global release optimizer using already computed recording groups, current track ignores and manual album grouping.
- Once an Ignore/Restore change is committed by **Re-Analyze**, exact release-path exclusions are stored in `state/manual_ignored_releases.json` and applied **during** the next full scan's initial optimization. Pending unconfirmed Ignore changes are not committed.
- Every successful Re-Analyze writes `logs/Music Collection Cleaner Re-Analyze YYYY-MM-DD-HH-MM-SS-ffffff.jsonl` and `state/last_reanalysis_audit.json`: blocked paths, previous/new retained IDs, added/removed releases, per-release reasons and replacement-source availability. If comparison logging was enabled for the original scan, append the new optimizer result and reanalysis event to that **same original JSONL**; old acoustic pair results are not overwritten.
- The Release Map result drawer offers **Open audit log**. Existing Copy/Move gating remains until Re-Analyze completes. `--ui-self-test` now includes isolated audit/persistence assertions.
- Investigation fixture: `Music Collection Cleaner Comparison 2026-10-12-20-53-24.jsonl` (v0.5.11) contains **only the initial optimizer result** (`blocked_releases: 0`). RuTracker 2011 CD `281` was selected, equivalent-looking edition `280` was not; their **No Limit** fingerprints were rejected against each other at ~74.57% good fraction vs 80% mastering threshold despite equal duration. Do not merge solely on title/length. Rerun v0.5.12 with the two ignored releases and inspect the newly written Re-Analyze audit for the actual post-Ignore decision.
- **Testing:** source published/read back; full Python compile, `--ui-self-test`, and actual Windows/WebView2 user workflow **NOT RUN**. Status remains **Under construction ⚠️**. Do not modify GitHub Actions.

## v0.5.11 - duration threshold corrected to strictly over 7 seconds

Only a duration difference **greater than 7.0 seconds** is treated as a separate length-based Version. Differences **7.0 seconds or less** do not create a length badge and do not veto an otherwise valid acoustic duplicate match. Both tracks still need a valid Chromaprint match before MCC treats them as the same recording; equal lengths alone never prove duplicate identity.

In the dark WebView2 Release Map, amber duration badges and delta labels appear only for alternatives whose measured durations differ by more than seven seconds. The 0.6s / 0.8s / 4.23s clutter from the previous release is removed. This also updates acoustic group transitivity and manual-merge safeguards, and preserves comparisons/logging and all other application functions.

Regression fixtures cover 0s, 0.6s, 4.23s, exactly 7.0s, 7.01s, 17.52s, identical audio fingerprints and A/B/C transitive grouping. **The source is published but not Windows-tested.** Re-analyze the library to rebuild recording groups under the corrected rule.

## v0.5.10 - highlight duration differences as separate versions

**Changed rule:** Two tracks with known measured durations differing by **0.5 seconds or more** must remain **different recording Versions**, even if their overlapping Chromaprint fingerprint segments match perfectly. Ignore sub-0.5-second timestamp/codec rounding differences; duration alone still cannot prove recordings are duplicates. Distinct versions retain separate acoustic group IDs and their unique coverage obligations.

**Release Map:** Open any release, inspect its tracklist, and select a track with other Versions. Its duration is highlighted in amber with a `Δ17.5s`-style difference badge. Each alternate Version also shows the relative length difference. The distinction explanation names both durations and the difference. Existing Remix and Live classifications remain separate; no new standalone interface is introduced.

**Safety:** Different-length versions cannot silently reunite via transitive A/B/C fingerprint grouping or a user-approved manual acoustic match. Per-pair JSONL log records the measured delta, matching threshold, length-based rejection, and any transitive group veto. This applies on a new full comparison, not retroactively to saved Release Map snapshots.

New embedded `--ui-self-test` cases cover exact matching fingerprints with different durations, negligible rounding, 17.52-second edits, A/B/C transitivity, manual review, and map UI controls. **Source published, not yet executed or validated on the user's Windows installation.** Cross-volume Move remains under construction.

## v0.5.9 - remove redundant maximum-size album editions

The 2026-10-12 MCC 0.5.8 INNA log shows three selected I Am the Club Rocker albums: the 2011 WEB (ID 4), Japan CD (ID 275), and regular 2011 CD (ID 281). **All 18 eligible tracks from Japan CD are already acoustically covered by other selected releases**. A hard requirement to retain the most-complete album was incorrectly keeping it.

**Corrected retention rule:** Keep at least one eligible ALBUM edition per album family and preserve every wanted recording across the full selected collection. The album with the most tracks is not mandatory. The exact optimizer minimizes total physical tracks first, then release count and quality tie-breaks. A fully covered Japanese/Deluxe edition should be removed if another eligible album in its family survives. A smaller album may stay eligible if its missing bonus recordings have alternate carriers.

**No Limit:** The song exists on all album editions. The 2011 CD copy is rejected by the acoustic fingerprint test against the Japanese CD (near-100% alignment, 74.6% good frames), not absent from other editions. A false negative or alternative mastering is possible; that identity issue remains separate. v0.5.9 does not relax acoustic thresholds or merge tracks based only on titles.

A built-in self-test fixture was added for the Japanese CD being redundant and becoming essential again when its separate bonus carriers are removed. **The new source has been published, but the Windows run and full Python self-test have NOT been executed.** Cross-volume Move recovery is still unresolved.

## v0.5.8 - automatic 80% album matching and manual groups

Music Collection Cleaner now identifies differently titled editions of one album when **80% or more of the smaller album's distinct wanted acoustic recording groups** also appear in the other. At least four groups must be shared. The comparison uses fingerprint-proven recording groups, not matching names, release dates, barcodes or track order. Different known main artists are not automatically grouped. Album-family connections are transitive.

The uploaded v0.5.3 INNA comparison confirmed:
- Hot 2005 vs Hot 2010: **11/11 = 100%**; Hot 2010 vs New Hot Edition: **9/11 = 81.8%**. All three belong to one family.
- Body and the Sun vs Inna (2015): **14/15 = 93.3%**; Body and the Sun vs Japanese edition: **13/15 = 86.7%**. All three belong to one family.

**Manual correction:** After an analysis, open the live Release Map, click an album, select a destination from **Move release into another album group**, and click **Move to group**. To undo that grouping decision, click **Restore automatic**. The assignment survives future scans in the program-specific state/manual_album_groups.json, keyed by full release paths, not temporary scan IDs. Click **Re-Analyze** before applying file operations. Grouping does not move files or merge different recordings.

**Same album family does not imply keeping just one release:** unique songs or bonus recordings on different editions must still be covered; MCC may retain multiple editions for that reason. The change preserves the full dark WebView2 Release Map and adds regression tests. v0.5.8 also fixes the pending-edit safety gate so toggling Ignore/Restore cannot accidentally re-enable Copy/Move after a manual group change. Windows testing remains outstanding and the cross-volume Move recovery risk remains unresolved.

## v0.5.3 - YO, Unicode and Wow corrections

The actual v0.5.0 INNA log proves WEB `2019-05-31 - YO [810760037075]` and CD `Inna - YO 2019` share exactly **11 fingerprint-based acoustic groups** but differ in track order. The v0.5.3 optimizer now treats complete matched acoustic sets as one album family even when reordered; the CD should be the sole retained album.

Metadata such as `Ð›ÑƒÑ‡ÑˆÐ¸Ðµ Ð¥Ð¸Ñ‚Ñ‹` is recovered as `Лучшие Хиты`, including damage introduced by the old Unicode compatibility normalization. The accented `Sí, Mamá` and unaccented `Si, Mama` now produce identical routing keys.

In `2012-04-26 - Wow (Remixes) [5948204365790]`, `Wow (Beenie Becker Club Edit)` and `Wow (Beenie Becker Radio Edit)` are classified as named-remixer edits. They are excluded when Save Remixes is OFF; a generic `Wow (Radio Edit)` remains ordinary.

The regression cases are bundled in the v0.5.3 source; Windows reanalysis and full self-test execution are not yet verified.

## v0.5.2 remix classification correction

The user-supplied 2026-10-12 INNA comparison log exposed a classification bug: **9 named remixes** on `2017-06-15 - Gimme Gimme (Remixes) [190295779481]` were incorrectly eligible with Save Remixes disabled because MCC interpreted their co-credited **remix producers** as newly featured vocalists. The new classifier ignores secondary ARTIST credits when the title/context identifies a named remixer, unless there is explicit feat./ft. evidence; it retains the existing exception for demonstrably added featured performers.

The release also contains a wanted **Gimme Gimme (Extended Version)**, which is not a remix under the current rules. The same extended audio occurs on `2017-02-01 - Gimme Gimme (The Remixes) [5948204157593]`. Therefore the optimizer may still choose **one** remix-named release to preserve that wanted extended recording; the remix tracks themselves must not justify retention. Re-run with v0.5.3 and compare the new JSONL before claiming the release can be discarded. Built-in regressions cover the ten Gimme track metadata shapes, contextual JRMX Dub/Club credit inheritance, and a genuine newly featured remixed recording. No updated Windows rerun has yet been performed.

## Safety and testing

Analysis does not change source files. File operations require explicit user action. Use **Copy** for initial real-world testing.

**Known blocker:** Cross-volume **Move** is not yet verified safe against failure during source-folder cleanup after a verified copy; its journal may not fully reflect a partially removed source. **Do not use cross-volume Move on important data.** No Windows test of this migrated version has been completed.

Required real-world regression cases include Cross the Line 14 vs 18 tracks, Starboy, Bangarang, Skrillex, destination collisions, worker/process cleanup, and Copy/Move/Undo on disposable test folders.

## Compatibility and migration

This project continues **Duplicate Edition Analyzer Lightweight v0.4.9** from the `dea-lightweight-modern` branch of [karpuzikov/userscripts](https://github.com/karpuzikov/userscripts/tree/dea-lightweight-modern/audio-tools/discography-torrent-project/lightweight). It preserves the full WebView2 interface and analysis flow.

Persistent data uses `Documents\Karpuzikov Tools\Music Collection Cleaner\`. On first run, previous analyzer settings, logs, caches, and state are **copied without deleting or overwriting the old program's data** from `Documents\Karpuzikov Tools\Duplicate Edition Analyzer\`. Program dependencies live under the new program's own directory.

The original production **Duplicate Edition Analyzer v0.22.12** and all previous analyzer releases remain in `karpuzikov/userscripts` and are not modified by this migration. Future MCC standalone updater lookup points only at this repository.

## Development

- [SOFTWARE_RULES.md](SOFTWARE_RULES.md) - exact current account-wide requirements.
- [RULES.md](RULES.md) - inherited complete optimizer and behavior rulebook.
- [CONTINUITY.md](CONTINUITY.md) - authoritative development status, regression contracts, blockers and prior history.

No extra GitHub Actions workflows or unverified EXE downloads are included.
