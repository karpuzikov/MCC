# Music Collection Cleaner (MCC)

**Version: 0.5.20 - Under construction ⚠️**

Music Collection Cleaner compares existing music releases with new ones, finds the best combination of editions, and helps preserve every wanted unique recording while removing unnecessary redundancy.

## Download and run

**[Music Collection Cleaner v0.5.20.pyw](Music%20Collection%20Cleaner%20v0.5.20.pyw)** - latest single-file Windows Python application. **Under construction ⚠️** until actual Windows WebView2 testing. Earlier v0.5.18 and v0.5.19 remain available unchanged.

Open with Python 3 on Windows 11 (or run from a console with `python "Music Collection Cleaner v0.5.20.pyw"`). The application checks or installs supported dependencies. The GUI uses Microsoft Edge WebView2 through pywebview; it is not a terminal-based replacement.

Source-level regression checks: `python "Music Collection Cleaner v0.5.20.pyw" --ui-self-test`.

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


## v0.5.20 - remembered Remix/Live unusual patterns (Under construction ⚠️)

- **Fix:** In `Unusual track pattern review`, replace the old keep-only checkbox with a compact per-pattern selector: **Skip this run**, **Keep (Personal Picks)**, **Remix (remember)**, and **Live (remember)**.
- Explicit Remix/Live choices persist by normalized pattern key in `Documents\\Karpuzikov Tools\\Music Collection Cleaner\\state\\unusual_pattern_categories.json`. They are omitted from future unresolved-pattern dialogs. The complete pre-analysis classification applies these selections before fingerprinting and optimizer decisions; **Save Remixes / Save Live recordings** determine whether matched files remain eligible. The existing special safeguard for a truly added featured artist on a remix remains; a producer credit alone does not rescue a classified remix.
- **Manage/reverse:** `Personal Picks...` now also contains **Saved Remix / Live classifications**, with category switching and a **Forget** action; forgetting makes an encountered pattern reviewable again. The original positive Personal Picks are preserved independently. **Skip this run** is deliberately not remembered.
- Example: `Wow (JRMX Club)` can be marked Remix once. Subsequent scans skip the prompt for this pattern and apply the Save Remixes setting. An unusual hook may instead be marked Live, if that is the correct user classification.
- A built-in source regression covers both choices, persisted reload, re-prompt after Forget, category-based exclusion and inclusion, producer credit prevention, and separate semantic recording roots. UI control-contract assertions were added.
- **Testing:** GitHub source write/readback and source assertions performed; complete Python `--ui-self-test`/`--self-test`, Windows WebView2 interaction screenshots, actual INNA rescan and Copy/Move/Undo **NOT RUN**. Keep **Under construction ⚠️** until real Windows acceptance. No GitHub Actions changes.

## v0.5.19 - cross-type Album/EP release families (Under construction ⚠️)

- **Fix:** An Album and an EP with >=80% **proven shared wanted acoustic groups** (measured against the smaller release, minimum four shared groups) now belong to the same visual edition family. The same safeguards for distinct artist identities, single releases and recording identity remain in force.
- **INNA regression:** `Inna - Party Never Ends (Part 2) (2013) [WPCR-15062]` (Album) and `2013-03-04 - Party Never Ends, Pt. 2 (Deluxe Editon) [5948204032791]` (EP tag) have six acoustically proven tracks in common out of seven included on the smaller edition (85.7%). `Alright` differs by 39.87 seconds and remains **distinct**; no audio is forcibly merged.
- **Manual correction:** Both Albums and EPs can use **Move to group** to target either an Album or an EP family; **Restore automatic** reverses a manual assignment. Mixed Album/EP families appear together in the Albums map section with an `Album / EP` label while each edition retains its original release type.
- **Optimizer safety:** Mandatory full-album representation remains album-only; an EP display assignment cannot silently split an album-only optimization family. Re-Analyze remains required after manual edits before Copy/Move can operate. Physical audio is never moved by a grouping edit.
- **Validation:** GitHub source readback and static regression-contract checks performed. Complete Python compilation/self-test, actual Windows WebView2 GUI, keyboard/responsive validation, full INNA scan, Copy/Move/Undo are **NOT RUN**. Do not mark stable until the real tests pass. No GitHub Actions modifications.
- **Test:** Run a fresh full analysis using the user's original INNA folders. In Full map, both Part 2 releases should share one album-family card. Then test EP-to-Album and Album-to-EP manual reassignment, Restore automatic and Re-Analyze.

## v0.5.18 - actionable integrity warning and responsive Release Map

- **Integrity/completeness warning:** replaces the unhelpful banner that only counted problems. Now shows each affected release **by name and its exact recorded audit issue(s)** in a focusable button at the top of the map. Clicking it switches from Changes to Full map as needed, selects and scrolls to the affected release, and opens its details, including issue text and release folder. **Copy/Move remain blocked** until source issues are fixed and a new analysis is run; safety checks are not bypassed.
- Screenshot supplied for v0.5.17 shows ⚠️ beside `2015-07-24 - Inna [5948204123093]`. The screenshot itself does **not** reveal the precise file/completeness error, so no specific corruption or missing track may be assumed; the new banner surfaces the scan's actual recorded message.
- **Responsive layout:** Full map keeps Albums / EPs / Singles and all original groupings, links, icons and interactions. At wide widths it allocates category widths according to the square root of the number of distinct release groups (instead of always equal thirds). Each category flows complete release-family groups into **1, 2, or 3 internal columns** via CSS container queries, without splitting a group. At narrower effective board widths (including when release details is open), category sections stack at full width instead of leaving narrow strips. Existing Changes-only view and 15-second Re-Analyze highlights remain unchanged.
- **Validation:** GitHub code and embedded JavaScript re-fetched; embedded JS parsed successfully. Isolated executable JS mocks passed named issue / click-to-release navigation and 27 Albums + 111 EPs + 150 Singles weighted-layout rendering. Linux Chromium/Playwright CSS geometry smoke test at 2048/1600/1300/780px showed responsive 1/2/3-column behavior and no horizontal overflow in a representative miniature page. **Windows WebView2, full Python `--ui-self-test`, source repair, and Copy/Move/Undo NOT RUN.** Status remains `0.5.18 - Under construction ⚠️`. No GitHub Actions changes.

## v0.5.17 - Re-Analyze highlights directly on Release Map

- Removes the bottom **Re-Analyze result** text panel entirely. The back-end's full Re-Analyze audit and JSONL evidence continue to be written to the isolated application log/state folders.
- After every successful Re-Analyze that actually changes the selected release set, the map switches to **Full map** and briefly highlights changed physical release rows: **faint green +** for newly retained releases, **faint red −** for releases dropped from the selection. Highlights last **15 seconds** and then disappear automatically without changing persistent selection/Ignore status.
- Uses exact stable-in-session release **IDs**, not release names, so similarly named editions never get each other's highlight. Automatically scrolls to the first changed release. Highlights survive map redraws and view changes during the 15-second interval, and restart the interval for a subsequent Re-Analyze. Duplicate state callbacks do not restart the timer. No animation/flashing or extra result panel; +/− markers and keyboard/screen-reader accessible labels accompany color.
- The UI still shows the ordinary current KEEP/ADD/REMOVE and ignored states afterward; Copy/Move and safety gates are unchanged. Original Re-Analyze audit remains available through the application's logs.
- Validation: embedded WebView2 JavaScript parsed in V8; isolated lifecycle/timer test passed (added, removed, same-name IDs, auto-expiry, new run, scroll and accessible labels). Windows GUI, full Python `--ui-self-test` and Copy/Move tests **NOT RUN**; **Under construction ⚠️**. No GitHub Actions changes.

## v0.5.16 - Copy/Move default destination immediately usable

- **Bug fixed:** In the Release Map, `Copy old + new releases into:` and `Move old + new releases into:` now default to the computed sibling folder `<NEW source name> - UPDATED`; the Copy and Move buttons become enabled immediately when there is a valid analyzed plan, without clicking Browse first.
- Both buttons, the displayed path, the Open-folder icon, and the final confirmation consume the exact same effective destination. An older/incomplete UI state can derive it from the NEW source root, with a fallback through NEW-release rows. Browse still overrides the destination. Pending Re-Analyze and audit-integrity blockers continue to disable Copy/Move.
- The backend also recovers the root from NEW snapshot scan roots when the live session did not supply it. A built-in source regression checks the default path and enabled-state contract.
- **Testing:** GitHub source and static contract verified. Actual Windows/WebView2 interaction and full Python self-tests NOT RUN; status stays **0.5.16 - Under construction ⚠️**. No GitHub Actions changes.

## v0.5.15 - substitute verified edits without conflating audio

- Fixes exact INNA regression in `Music Collection Cleaner Comparison 2026-10-12-23-52-28(1).jsonl` and Re-Analyze audit at `23-58-29`: `INNA – Body And The Sun [Japan] (2015) [FLAC]` (ID 287) was retained solely because of a **17.527777-second-longer Fool Me** (213.333333s vs 195.805556s). The other three supposed unique songs already have fingerprint-matched 2014 singles: Cola Song, Take Me Higher, Good Time. The Japanese Fool Me is an acoustically supported edit of the shorter recording, not an identical track, and it remains a separate actual audio-group ID.
- `Track.coverage_group_id` is a **planning-only substitute family**; actual `group_id` and Release Map version/length differences are preserved. A length-distinct base-track edit may be substituted ONLY with matching normalized song/primary artist and very strong positive audio evidence: ≥98% fingerprint overlap, ≥90% good fraction, ≥65% excellent, score ≤5, median ≤5, p90 ≤10, and ≥90% aligned acoustic coverage. Protect Remix, Live, Extended, Instrumental, Acoustic and other distinct roots; never merge by title or duration alone.
- For the supplied INNA log, **only two Fool Me comparisons** among 127 same-title/artist different-length candidates pass this strict substitute test. The global optimizer now treats these two different audio groups as one **replaceable coverage obligation**, so it can select the required full INNA album plus the three individual singles without retaining the Japanese compilation/edition solely for Fool Me. Exact audio identities remain separate and are not relabeled as identical.
- Release Map track status distinguishes **"Covered by alternate version"** from a true identical recording. JSONL logs `replaceable_version_coverage` records with concrete pair indices/length differences; source includes a regression fixture modeling the INNA Japanese edition and three singles.
- **Run a NEW FULL ANALYSIS** to compute new version substitutions. Re-Analyze alone reuses old audio groups and cannot repair prior results.
- GitHub source changes/readback verification only: Python compilation, `--ui-self-test`, Windows WebView2 full run, Copy/Move/Undo are **NOT RUN**. Remains **0.5.15 - Under construction ⚠️**. No GitHub Actions changes.

## v0.5.14 - eight-second duration-version threshold

- At **8.0 seconds or less**, duration difference alone does not separate an otherwise fingerprint-matched recording. Only a duration difference **strictly greater than 8.0 seconds** denotes a different length-based Version.
- Changed the shared comparison, exact-fingerprint, transitive-group, manual-review, and diagnostic threshold to 8.0 seconds. Release Map duration badges use the same **>8.0s** rule.
- Updated synthetic boundary tests for exact 8.0 vs 8.01 seconds, and refreshed INNA Hot duration-bridge expectations; known acoustic matches spanning 7.3-7.5 seconds may now be in one recording group.
- **Requires a new full audio analysis**: Re-Analyze only recomputes release optimization using existing acoustic groups.
- GitHub source verified, but Python compilation, bundled self-test, and real Windows/WebView2 analysis remain **NOT RUN**. Status: **0.5.14 - Under construction ⚠️**. No GitHub Actions changes.

## v0.5.13 - deterministic duration-aware acoustic groups

- Fixes real INNA Hot album false-unique track groups: `Nights & Days` (WEB ID 2, 206.511678s) vs `Days Nights` (CD ID 274, 202.813333s), and `Ladies` (WEB ID 2, 306.033175s) vs `Ladies` (CD ID 274, 307.280000s). Both pairs already **passed** high-confidence Chromaprint tests, but v0.5.12 grouped them separately because other tracks formed transitive group spans greater than seven seconds.
- Instead of making permanent merges in arbitrary worker-completion order, collect verified acoustic matches and choose deterministic **connected duration-constrained partitions**. Minimize number of recording groups while enforcing the established strict **>7.0-second** version boundary, then maximize verified internal acoustic links and supported membership. Different titles and equal durations alone still never create acoustic identity.
- Comparison JSONL is now logged with the **final, globally resolved acoustic grouping**, not temporary rejection decisions; a `grouping_policy` row records the new behavior. Preserve all quality thresholds, release Ignore persistence, Re-Analyze and Copy/Move workflow.
- The supplied INNA comparison and two Re-Analyze audits were examined; offline replay of actual matched-audio pair data demonstrates both Hot fixes. Built-in `--ui-self-test` includes both Hot bridge cases and 7.0/7.01-second boundary checks.
- **A NEW FULL ANALYSIS IS REQUIRED.** Release Map **Re-Analyze alone reuses old audio group IDs** and will not correct prior false splits.
- Source published and read back. Python compile, app `--ui-self-test`, real Windows/WebView2 and Copy/Move/Undo **NOT RUN**. `0.5.13 - Under construction ⚠️`; cross-volume Move safety remains unverified.

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
