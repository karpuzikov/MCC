# Music Collection Cleaner (MCC)

**Version: 0.5.25 - Under construction ⚠️**

Music Collection Cleaner compares existing music releases with new ones, finds the best combination of editions, and helps preserve every wanted unique recording while removing unnecessary redundancy.

## Download and run

**[Music Collection Cleaner v0.05.25.pyw](Music%20Collection%20Cleaner%20v0.05.25.pyw)** - latest single-file Windows Python application. **Under construction ⚠️** until actual Windows WebView2 testing. Earlier source versions remain available.

Open with Python 3 on Windows 11 (or run from a console with `python "Music Collection Cleaner v0.05.25.pyw"`). The application checks or installs supported dependencies. The GUI uses Microsoft Edge WebView2 through pywebview; it is not a terminal-based replacement.

Source-level regression checks: `python "Music Collection Cleaner v0.05.25.pyw" --ui-self-test`. `--self-test` additionally requires a packaged standalone EXE.

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


## v0.5.25 - full GIMS comparison log audit and one-track Remix correction (Under construction ⚠️)

- **Actual attached run:** `Music Collection Cleaner Comparison 2026-10-14-08-17-53.jsonl`, identifies itself as **v0.5.24**, 2026-10-14 08:20-08:21 local log timestamps. Parsed 27,243 valid records: 1,604 tracks across 153 physical releases, 1,508 eligible complete-fingerprint tracks, 96 excluded (86 Explicit/Clean decisions, 10 remix exclusions), 25,569 detailed comparison rows, 8,277 accepted audio match edges, 256 all-rejected shadow pairs. 252 original recording groups; exact optimizer used 250 wanted coverage groups after separate version-coverage substitutions, chose 72 of 146 active releases (7 dominated) totaling 304 retained physical tracks. Zero logged integrity failures, zero eligible incomplete fingerprints, zero logged comparison decision inconsistencies; no blocked releases or late quality tie-break rollback. These statistics do **not** certify exhaustive pair testing or a real filesystem Copy/Move operation.
- **One confirmed classification bug:** Eight different physically single-track releases with a `Remix` name were labeled `EP` (`release_type_source=name`), rather than `Single`. Seven had zero eligible tracks due remix exclusions. Release ID 17 `Sapés comme jamais ... (Remix)` was retained with one legitimate featured-remix exception; the classifier's incorrect EP label did not itself prove wrong retention. Root cause: `infer_release_type()` unconditionally returned `ep/name` for a `Remix` title after explicit release tags. **Fixed generally:** single-track inferred remix packages now return `single/name`; multi-track remix packages still use the established EP fallback, explicitly tagged EP and single releases still take precedence. No title-specific exception.
- **Optimizer audit:** 9 retained Albums (7 OLD/CD/WEB existing and 2 additions), 1 retained former EP (now correctly Single), 62 other Singles; *no retained Single* has a confirmed acoustic MATCH with another retained release in the supplied comparison. The additional `Ceinture noire [3616401604548]` release ID 39 has 2 recordings without a confirmed match to other selected releases (`La nuit c'est fait pour dormir`, `Caméléon`); `Le fléau [3616550229623]` release ID 54 has 2 (`Intro`, `Immortel`). Do not discard these releases solely because another album edition is present.
- **Explicit/Clean audit limitation:** All 86 excluded tracks have an eligible alternate with matching normalized title/artist signature and duration within 8 seconds somewhere in the scan; 13 excluded `Corazón` instances lack such an exact tag-signature match **among selected** tracks because the retained CD credits Lil Wayne/French Montana in the title rather than in `ARTIST`. The old track JSONL omitted the actual `explicit` state and `excluded_by_pattern` for each file, so its pre-fingerprint removal cannot be independently proven acoustically correct. No forced audio merges or destructive changes made. v0.5.25 adds `explicit_state` and `excluded_by_pattern` as additive per-track audit fields for the next scan.
- Embedded classifier regression fixtures reproduce **all eight actual Remix cases**, a multi-track Remix EP, explicit EP precedence, explicit `single;remix` tag priority, and the new Explicit/Clean diagnostic fields. Source published to GitHub; full application Python compile, embedded `--ui-self-test`, Windows WebView2 run, real collection rerun and Copy/Move/Undo **NOT RUN**. Remains **Under construction ⚠️**. No Actions modified.
- **Next:** Run `python -m py_compile "Music Collection Cleaner v0.05.25.pyw"`, then `python "Music Collection Cleaner v0.05.25.pyw" --ui-self-test` on Windows. Reanalyze GIMS and confirm all eight one-track remix entries appear as Singles (including retained release ID 17), selected set preserves four noted unmatched selected-album tracks, and new explicit/exclusion fields explain filtered variants. Test actual UI and Copy/Move/Undo only on disposable music copies.

## v0.5.24 - mandatory radical simplicity UI pass (Under construction ⚠️)

- **Rules verified:** On 2026-10-14, both `SOFTWARE_RULES.md` and `UI_UX_RULES.md` in MCC match the newer canonical versions from `karpuzikov/userscripts` exactly. Their newly explicit acceptance gate requires minimum clicks, direct frequent actions, no obvious instructional prose, no duplicate controls, and full function/accessibility/safety retention. The user's personalization instructions reiterate these requirements.
- Removed the duplicate in-page **Music Collection Cleaner / version** header. The Windows title bar remains the canonical, visible application name/version/status. Removed static "Analysis is read-only" tutorial, "Match: Chromaprint (audio only)", and the Activity area's redundant "Working" label. Retained actual progress/status, live activity log and progress percentage.
- Reduced unusual-pattern review to **Classify patterns** plus each distinct context example (no repeated "Variants"/"Examples" labels or repeated variant equal to its heading). Default modal subtitle is empty; failures show an actionable error and multiple unresolved patterns show concise completion count. Existing direct-action **Remix / Live / Keep / Skip**, instant commit after last selection, Escape cancellation, category persistence and keyboard accessibility unchanged.
- **Copy/Move result:** Removed the duplicate **Open destination** footer button while keeping the existing folder button immediately next to the destination path. The distinct actions **Undo move**, **Release Map**, and **Close** are preserved, as are source-file safety messages. Removed a repeated sentence stating the same file-side-effect notice twice.
- Preserved OLD/NEW source selectors, folder-open icons and distinct Browse actions, worker selector, Save Remixes/Live, persistent Personal Picks, logging, Undo, Release Map and all processing/optimizer behavior. No GitHub Actions modifications and no original music was accessed or modified.
- **Validation:** Full GitHub source readback, two embedded JavaScript syntax parses in V8, mock review with examples/auto-submit, and source checks for eliminated duplicates **PASS**. Complete Python compilation, `--ui-self-test`, actual Windows WebView2 UI screenshots/hover/keyboard/resize, persistence/Copy/Move/Undo **NOT RUN**. Remains **Under construction ⚠️**.
- **Next:** On Windows run `python -m py_compile "Music Collection Cleaner v0.05.24.pyw"`, then `python "Music Collection Cleaner v0.05.24.pyw" --ui-self-test`; visually compare against the user's v0.5.21 screenshot at native DPI and different widths; verify JRMX Club choice with one click and no repeat after restart; exercise destination folder button and Undo on disposable data.

## v0.5.23 - one-click unusual-pattern classification (Under construction ⚠️)

- Replaced the user-rejected 4-item dropdown and duplicate bottom **Keep all / Skip all / Save choices & Continue** buttons with **four inline buttons per detected pattern: Remix, Live, Keep, Skip**. The primary requested categories Remix/Live are first. Each classification requires **one click, not a dropdown plus Save**. A detected pattern already collects related track variants, so this review is per *pattern*, not per individual song.
- Remix/Live are remembered in the existing isolated persisted category file and respect Save Remixes / Save Live. Keep remains a persistent Personal Pick. Skip excludes the pattern only for the current scan. The existing backend validates all choices and saves them before resuming, without changing acoustic identity, selection logic, source files or Copy/Move/Undo.
- All pattern rows are visible with short labels, descriptive tooltips, native keyboard-operable buttons, visible focus, `aria-pressed` feedback, wrap on narrow windows, and count feedback when more than one row is pending. One click per pattern; when the last is chosen, **automatically submit and continue**. Only **Cancel scan** remains in the footer. Escape now calls `cancelReview` for this modal instead of leaving the backend in review-pending state.
- UI control contract: `patternChoice` four mutually exclusive per-pattern buttons (36px minimum height, selectable visual state; click, Enter, Space; no destructive file operations), `patternCancel` cancels pending scan without saving staged selections (click/keyboard/Escape); no other modal controls. The existing `Personal Picks` editor is retained for later changes and forgetting remembered Remix/Live.
- **Validation:** GitHub published/read back v0.05.23 source; both extracted embedded JavaScript sections parse in V8; mocked 4-pattern button actions and automatic single-submit PASS, and source contract checks updated. **Python full compilation / `--ui-self-test`, actual Windows WebView2 UI/screenshots/keyboard interaction, settings round trip on Windows and Copy/Move/Undo NOT RUN.** Status remains `Under construction ⚠️`.
- **Windows next action:** `python -m py_compile "Music Collection Cleaner v0.05.23.pyw"`, `python "Music Collection Cleaner v0.05.23.pyw" --ui-self-test`; run the original `Wow (JRMX Club)` scan, click **Remix** once and confirm analysis resumes without Save; repeat scan to verify no prompt; change to Live/Forget in Personal Picks and verify behavior. Capture screenshot and test multi-pattern and Escape cancellation.

## v0.5.22 - classification evidence and compilation test correction (Under construction ⚠️)

- **Verified original log (v0.5.20):** Release 43 Disciple 02 was mislabeled Album and selected; it has 22 physical tracks, eight excluded remixes and 14 eligible recordings. None of the 14 has a confirmed cross-release MATCH in the supplied comparison JSONL. Release 31 Texx Mars EP was mislabeled Compilation and not selected; the alternate release 3 was correctly EP and selected.
- **v0.5.21 classification correction retained:** Full physical artist distribution identifies Disciple as a multi-artist compilation; explicit EP evidence protects the two-track Texx release. The optimizer still retains a genuine compilation **when necessary to preserve unique wanted audio**. Classification alone must not silently delete the 14 distinct wanted recordings.
- **New evidence:** Comparison track records now include `release_classification_tags`, preserving every original tag with release-type relevance for each track (`RELEASETYPE`, `MUSICBRAINZ_ALBUMTYPE`, `COMPILATION`, `ITUNESCOMPILATION`, `ALBUMARTIST`, etc.). Optimizer `release_source_catalog` entries include `release_type_source`. The old JSONL did not include raw classification tags; its exact inherited compilation-flag trigger cannot be established retroactively.
- **Regression fix:** Updated outdated `--ui-self-test` policy expectations that contradicted the already nondestructive `apply_compilation_policy()`. Added an assertion for original tag diagnostics. No change to the acoustic grouping, optimizer algorithm, Copy/Move/Undo, UI controls or GitHub Actions.
- **Validation:** Re-parsed the actual 947-record comparison log. Independent log-based Python assertions **PASS** for Disciple, both Texx editions and Datsik albums, including unmatched wanted-coverage evidence. GitHub source readback/static checks **PASS**. Complete Python compilation, application's `--ui-self-test`, standalone EXE `--self-test`, real Windows WebView2 interactions, end-to-end scan and Copy/Move/Undo are **NOT RUN**.
- **Next action:** Run `python "Music Collection Cleaner v0.05.22.pyw" --ui-self-test` and `python -m py_compile "Music Collection Cleaner v0.05.22.pyw"` on Windows; rescan Datsik and verify Disciple=Compilation, both Texx=EP. Confirm whether its 14 eligible recordings should remain in the wanted collection. Do not mark stable without real GUI/filesystem safety tests.

## v0.5.21 - compilation classification from the full tracklist (Under construction ⚠️)

- **Disciple 02 false negative fixed:** In the user's `Music Collection Cleaner Comparison 2026-10-14-05-36-10.jsonl`, release ID 43 `2015-05-18 - Disciple 02_ The Second Coming [3614592021540]` was classified **Album**, with all 22 physical tracks but only 14 counted after eight remixes were excluded. It is a multi-artist compilation; the recorded artist signatures include 19 distinct performers, and even the most frequent appears on just 8 of 22 tracks. The classifier now uses the **complete release tracklist before remix/live exclusion** to recognize this independent-performer anthology even when ALBUM or folder location says otherwise.
- **Texx Mars false positive fixed:** Release ID 31 `2009-01-14 - Texx Mars EP [190374272483]` was classified **Compilation**, though both tracks credit Datsik. An explicit EP name or EP primary type now takes priority over a conflicting weak/general `COMPILATION=1`/Various Artists flag when the release lacks strong independent-performer evidence. A genuine various-artists EP with sufficient diversity can still classify as Compilation.
- Preserve direct compilation indicators such as `Best Of`, `Greatest Hits`, and collection titles, plus the existing Trilogy and Highlights long-form exceptions. Standalone albums with several guest artists remain Album when a common principal artist is present. No changes to fingerprinting, track identity, releases' physical files, or Copy/Move/Undo algorithms.
- **Optimizer behavior:** Compilations remain **last-resort carriers** for wanted recordings not otherwise represented; reclassification removes mistaken ordinary-album status but does **not** categorically delete a compilation that uniquely contains wanted music.
- **Validation:** Real JSONL track-artist signatures were evaluated in an isolated deterministic regression calculation (Disciple 02 true; Texx Mars and Datsik artist albums false). Embedded app self-test cases added but **full Python compilation, --ui-self-test, --self-test, Windows GUI, full scan and Copy/Move/Undo NOT RUN**. Retain **Under construction ⚠️** until end-to-end Windows verification.
- **Next action:** Run `python "Music Collection Cleaner v0.05.21.pyw" --ui-self-test`, `python "Music Collection Cleaner v0.05.21.pyw" --self-test`, then rescan the user's Datsik folders; confirm Disciple 02 is Compilation and both Texx Mars EPs are EP. Verify any final compilation retention is justified solely by unique wanted audio and not an ordinary album-family constraint.

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
