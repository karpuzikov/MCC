# Music Collection Cleaner (MCC)

**Version: 0.5.51 - Under construction ⚠️**

Music Collection Cleaner compares existing music releases with new ones, finds the best combination of editions, and helps preserve every wanted unique recording while removing unnecessary redundancy.

## UI review

For MCC, the user supplies Windows WebView2 screenshots for visual review when ready. Do not ask the user to run Playwright or `tests/visual_qa.py`; no automated visual QA commands are part of the current testing workflow. Functional and acoustic regression checks remain required. Earlier visual-runner notes below are historical, not current instructions.

## Download and run

**[Music Collection Cleaner v0.05.51.pyw](Music%20Collection%20Cleaner%20v0.05.51.pyw)** - latest single-file Windows Python application. **Under construction ⚠️** until actual Windows WebView2 testing. Earlier source versions remain available.

Open with Python 3 on Windows 11 (or run from a console with `python "Music Collection Cleaner v0.05.51.pyw"`). The application checks or installs supported dependencies. The GUI uses Microsoft Edge WebView2 through pywebview; it is not a terminal-based replacement.

Source-level regression checks: `python "Music Collection Cleaner v0.05.51.pyw" --ui-self-test`. `--self-test` additionally requires a packaged standalone EXE.

## What it does

- Analyze two pools: the existing library (OLD) and candidate additions (NEW).
- Identify recordings through acoustic fingerprints, independently of titles; a successful comparison decides identity.
- Preserve unique wanted recordings; apply Remix, Live, Explicit/Clean and Personal Picks rules.
- Compare original, expanded, Deluxe, Special and other editions, including strict acoustic-superset detection.
- Prefer high-quality sources and CD rip logs among truly equivalent choices; use dynamic range only as an eligible final mastering tie-break.
- Optimize retained complete releases and physical track count across the library, not just isolated duplicate pairs.
- Inspect an interactive chronological **Release Map** with connections, per-track coverage, replacement explanations, Ignore/Restore and Re-Analyze.
- Explicitly **Copy OLD + NEW** or **Move OLD + NEW** retained releases into the selected destination; Undo for supported completed moves.
- Log comparisons, validate incomplete/corrupt inputs, choose I/O worker counts with drive awareness, and manage spawned subprocesses.


## v0.5.51 - Reach comparisons across edition and censored names (Under construction ⚠️)

- The fresh v0.5.50 log matches 15 Watch the Throne pairs but never compares Illest. Exact album-slot keys split Deluxe Edition from Deluxe, while the censored Motherf***** spelling defeats the ordinary title fallback. Both editions are retained solely for the resulting two Illest groups.
- Normalize edition suffixes for album-slot candidate routing and add a censored-title safety route, including files without album/track-number metadata. Metadata only schedules comparison; the calibrated 4.02 fingerprint cutoff, inclusive 8-second effective-duration rule and native all-channel silence measurement still decide the result.
- New regressions reproduce the skipped comparison on v0.5.50. The generated-audio pipeline now reaches real fingerprint comparison and native verification of a 180.059375-second silent prefix, merges the pair and retains the CD without changing source media. The actual 684-track log metadata routes all 16 corresponding album slots; real Illest padding still requires a fresh Analyze of the original files.

- All 84 functional tests, the complete UI self-test, compilation and both embedded JavaScript syntax checks passed. Independent review found no remaining issues. Actual Windows acceptance and the original Illest boundary measurement remain pending.

## v0.5.50 - Calibrated mastering fingerprint threshold (Under construction ⚠️)

- The 16 actual Watch the Throne CD/WEB comparisons have a maximum mean Hamming distance of 4.014241 bits per 32-bit item. Rounded upward, the new effective cap is 4.02 for both normal and mastering matches; the former 5.0/7.5 limits cannot bypass it.
- A successful fingerprint comparison receives no later local-window, decoded-audio or metadata veto. Existing duration, inclusion/Ignore and source-safety rules remain. Corrected long-silence alignment timing for the existing duration normalization.
- All 16 recorded fingerprint profiles fit the new cap. Fresh Analyze is required to verify new groups and the long Illest padding against actual media; the log contains neither original audio nor raw fingerprint vectors. UI/Ignore behavior and the optimizer remain unchanged.

- All 79 functional tests, full UI self-test, compilation, both JavaScript syntax checks and independent review passed. Native Windows acceptance and real Illest padding validation await a fresh Analyze.

## v0.5.48 - Highlight the tracks that retain the release (Under construction ⚠️)

- Highlight the tracks that are the reason the release is retained. Tracks covered by another retained release stay unhighlighted; copies on discarded releases do not cancel highlights. Discarded duplicate releases have none. This supersedes v0.5.47's all-scanned song-presence interpretation.
- The essential count and Changes retention titles follow those same tracks. Useful audio-copy/version text and separate Gem checks are preserved. Ignore/Restore updates the row, count, Changes text and Gem badges together without reopening the details.
- The saved actual plan now renders exactly 15 highlighted retention reasons and four unhighlighted covered tracks for The Life Of Pablo [602547908339], with zero highlights on its removed duplicate. All 684 rows across 104 releases agree with retained coverage.
- All 71 functional tests, the full UI self-test, Python compilation and both embedded JavaScript syntax checks passed on Linux. Actual Windows visual acceptance remains pending user-supplied screenshots. This is a display correction using logged groups, not a new acoustic measurement.

## v0.5.47 - Remove highlights from shared songs (Under construction ⚠️)

- Yellow track highlighting now means the song is present only on this release in the scanned collection. Another listed version of that song prevents the highlight even if its acoustic group or duration differs. The unique count and Changes track previews use that same flag.
- Restore **Same audio on ...** / **Also listed on ... (audio unverified)** status text. Remove the generic Needed recording label. Only verified equal audio-group IDs support Same audio; title-based song presence does not alter recording identity or optimizer coverage.
- Replay of the new v0.5.46 log shows no highlighted tracks on BULLY and only **OK (feat. Don Toliver)** highlighted on Deluxe. Their 18 shared songs are unhighlighted; Mission Control is also on its discarded single and is unhighlighted. Tests execute the real row HTML producer and check its actual highlight CSS classes.
- Preserve distinct audio versions, selection, saved Ignore, source media and all existing controls. Shared/unknown listings also prevent a false unique Gem badge. All 68 functional tests, full `--ui-self-test`, compilation and embedded JavaScript syntax checks pass on Linux. Native v0.5.47 Windows acceptance remains pending; no automated visual QA or Actions changes.

## v0.5.46 - Track highlights explain retention (Under construction ⚠️)

- Highlight only included recordings needed from this retained release. Verified copies covered by another retained release, exclusions and saved Ignore cannot contribute a highlight or essential count, including stale cached annotations.
- Highlighted rows say **Needed recording**. The old **Also listed on ... (audio unverified)** status came from title/performer/length metadata, not an acoustic duplicate match, and obscured the reason for retention. Related recording groups remain in the existing Versions details.
- Preserve acoustic matching, optimizer selection, source media and controls. Same-title recordings in different audio groups remain required until matching evidence establishes a duplicate. This UI correction does not certify BULLY's standard/Deluxe recordings as identical.
- All 65 functional tests, compilation, both embedded JavaScript syntax checks and the complete `--ui-self-test` pass on Linux. Actual v0.5.46 Windows visual acceptance remains pending user screenshots; no automated visual QA or Actions changes.

## v0.5.45 - Equivalent album recordings and one Ignore action (Under construction ⚠️)

- Recognize consistently aligned mastering differences with a tight global fingerprint profile and a local-window limit relative to the whole-track difference. This fixes the false splits behind the reported 808s, College Dropout, Graduation and MBDTF additions. Resolve coherent fingerprint groups before weaker decoded edges; retain local changed-section checks, direct rejected-pair constraints and independent decoded checks for uncertain evidence, including known Clean/Explicit disagreements.
- Apply the inclusive 8-second rule to identity durations. A larger raw gap can normalize only after read-only decoded boundary checks prove removable silence at the native sample rate in every channel. Keep raw duration and source files intact; audible endings, DC and high-frequency-only content remain distinct.
- Remove the duplicate Stop/Skip hover action. Keep R/L, the existing recording-wide Ignore/Restore, saved Skip classification and its management. Saved Big Brother Ignore still does not create a wanted requirement.
- Replay of the supplied v0.5.44 log reproduces the original 75 releases / 600 tracks, then selects 65 / 469 under the new fingerprint policy, covering all 402 resulting wanted groups. The four redundant WEB albums are omitted and their CD anchors retained. This is a replay of logged metrics, not a fresh scan of the user's audio.
- Late Registration's Gone has a 29.306667-second raw difference and remains separate in that replay. The new decoder check must establish whether its extra boundary is silence; no actual source audio was available here. A passed full-band check allows equivalent copies to merge; audible or unavailable evidence keeps them separate.
- All 63 functional regressions, compilation and the complete `--ui-self-test` pass on Linux. Run a fresh **Analyze** in v0.5.45 to rebuild acoustic groups; Re-Analyze reuses existing groups. Native Windows collection/file-operation acceptance remains pending. No automated visual QA or GitHub Actions changes.

## v0.5.44 - Fingerprint identity within 8 seconds (Under construction ⚠️)

- Conclusive near-identical fingerprints with consistent local content and a length difference of 8 seconds or less count as duplicates. Small unmatched ends and decoded PCM differences cannot veto that decision.
- Preserve the changed-interior safeguards and independent PCM checks for non-conclusive candidates; differences greater than 8 seconds remain separate versions.
- Correct the three logged 808s rejection paths and record fingerprint authority explicitly in comparison diagnostics. Broader non-conclusive Graduation matching remains unverified.
- All 31 focused regressions, compilation and the full `--ui-self-test` pass on Linux. Run a fresh Windows Analyze to verify actual collection results; Re-Analyze reuses old groups. No UI or workflow changes.

## v0.5.43 - Comparison-log safety fixes (Under construction ⚠️)

- Keep acoustic candidate discovery independent of titles. Near-identical fingerprints need a local-content check; other promising fingerprint matches require read-only decoded stereo-window confirmation, including short final sections and silence checks on unmatched endings. A directly rejected pair cannot merge through an intermediate match. Unavailable confirmation keeps recordings separate automatically.
- Preserve a CD copy when only its automatic Live/Remix wording conflicts with an allowed, acoustically identical recording. Explicit saved categories, pattern Skip and recording Ignore still take precedence.
- Every distinct acoustic version now remains a mandatory optimizer requirement; older replaceable-edit coverage cannot discard shorter Gone / Jesus Lord versions.
- Recognize joint primary/group credits such as ¥$ and KIDS SEE GHOSTS; resolve Kanye West / Ye through a separate identity-alias relation. Featured artists keep their secondary role.
- Schema 3 logs include decoded-audio verdicts/timing, final per-track Ignore/exclusion state, every scanned release, and dominance evidence. Planning verifies coverage against the pre-dominance wanted set.
- Fix obsolete self-test wording/stroke assertions; `--ui-self-test` and all 26 focused audio-safety tests pass on Linux/Python 3.12.14. The suite covers generated audio, transitive matches, saved exclusions, aliases, and the complete comparison/logging path.
- **Still required:** a fresh Windows scan of the user's actual collection and disposable native Copy/Move/Undo tests. Source media were unavailable here. UI review awaits user-supplied screenshots; no automated visual QA is requested. No GitHub Actions changed.

## v0.5.42 - Acoustic identity before metadata exclusions (Under construction ⚠️)

- **P0 regression:** In the user's v0.5.41 comparison log, `Pinocchio Story` (361.6 s, 2,899 fingerprint frames) and `Pinocchio Story (Freestyle Live from Singapore)` (361.6 s, **0 fingerprint frames**) were **not compared**: Save Live OFF removed the latter from fingerprint analysis. The files' actual acoustic equivalence is **NOT VERIFIED** without their audio.
- All readable files now participate in local full-audio Chromaprint fingerprint generation and bounded acoustic candidate routing, even when excluded from *retention* by Remix/Live/Skip/Explicit>Clean. Version metadata can be logged as disagreement but can no longer veto a candidate before acoustic comparison.
- Full-audio identity groups can include excluded copies; only wanted copies contribute optimizer groups and retention obligations. Original audio, existing policy choices, Copy/Move/Undo, and UI layout remain unchanged.
- New `--ui-self-test` regression exercises a synthetic near-identical remaster with asymmetric Live descriptor, a completely wrong filename/title, and an acoustically different same-title file. Runtime PASS/FAIL is **NOT RUN** on this checkpoint.
- **Required:** Python compile, `--ui-self-test`, Playwright, native Windows WebView2 and disposable file-operation tests. Rescan the two physical Pinocchio audio files and inspect the new JSONL for both populated fingerprints and a verified `MATCH` before claiming they are duplicates. No GitHub Actions changes.

## v0.5.41 - UI audit corrections / safer Move (Under construction ⚠️)

- **Safety:** Move OLD+NEW uses same-volume atomic renames only; cross-volume Move is explicitly rejected before modifying sources, with Copy OLD+NEW offered instead. Write-ahead Undo manifest is persisted **before** each rename. Rollback uses all journaled entries, including a move that succeeded just before raising. Includes synthetic EXDEV and post-rename failure regression fixtures; real Windows fault-injection and Move/Undo acceptance remain pending.
- **Copy vs Move:** Preserve separate actions but make Move amber, with same-volume restriction stated in the interface and confirmation. Copy remains non-destructive and green.
- **Release Map:** Text of track statuses wraps instead of truncating; improve contrast for removed releases; reduce overwhelming amber backgrounds; add Full-map-only **Show all links** toggle, defaulting to connections for the selected release; Changes results adapt to wide windows rather than sitting in a narrow strip.
- **Main window:** The empty Activity card disappears when idle, retaining its full progress log during analysis and afterward.
- **Classify patterns:** Replace multiple identical Pending -> Classify buttons with one **Review pending (N)**, without removing the persistent Remix/Live/Skip/Personal Picks controls.
- **Personal Picks:** Search, grouped Phrase/Exact/Pattern sections, and inline editing for phrase/exact picks. Pattern rules retain stable keys; to change their category use Classify patterns.
- **Browser QA runner:** Recognizes native Changes view rows `.changeRow`, captures Changes/Full-map states, and continues into hovered release details. Earlier `v0.5.40` Windows `--ui-self-test` was **PASS**; Playwright failed at an obsolete startup selector despite successful rendering.
- **Checks:** GitHub source readback and JavaScript V8 syntax parse PASS. Python compilation, updated `--ui-self-test`, browser screenshots/geometry, real native Windows WebView2 screenshots and actual Copy/Move/Undo remain **NOT RUN** for v0.5.41. No GitHub Actions changes. Never use valuable originals as test inputs.
- **Test on Windows (fresh checkout):** `git clone https://github.com/karpuzikov/MCC.git`, `cd MCC`, `py -m py_compile "Music Collection Cleaner v0.05.41.pyw"`, `py "Music Collection Cleaner v0.05.41.pyw" --ui-self-test`, `py tests/visual_qa.py --browser edge`. Also send new native WebView2 screenshots for comparison.

## v0.5.40 - Correct contradictory Dirty Vibe and Remix/Live test fixtures (Under construction ⚠️)

- User's Windows 11 / Python 3.14 v0.5.39 compile passed. Its `--ui-self-test` failed with `Dirty Vibe remix self-test failed: remix-only audio kept.` The existing negative remix test passed a `Jack Beats` Personal Pick yet expected the matching remix to be excluded: that contradicted the explicit Personal Picks override feature.
- Split two contradictory fixtures (Dirty Vibe EP and generic Remix/Live) into negative tests with no saved Personal Picks, then positive tests in which an explicit Personal Pick correctly overrides Save Remixes/Live OFF for matching recordings only. Also confirm removing the Pick restores ordinary exclusions. **No audio classification or file-operation behavior changed.**
- The Playwright Visual QA developer script now automatically targets the highest versioned MCC `.pyw` in the checkout, avoiding a stale v0.5.39 test target when new versions are published. Browser report, native WebView2 and screenshot acceptance are still pending.
- **Run on Windows:** `git pull`, `py -m py_compile "Music Collection Cleaner v0.05.40.pyw"`, `py "Music Collection Cleaner v0.05.40.pyw" --ui-self-test`, `py tests/visual_qa.py --browser edge`.
- **NOT RUN:** Full Python runtime self-test, browser visual acceptance, WebView2, real Copy/Move/Undo. `Under construction ⚠️` remains mandatory.

## v0.5.39 - Fix test failures reported on Windows (Under construction ⚠️)

- User's Windows 11 / Python 3.14 test: v0.5.38 `py_compile` passed, but `--ui-self-test` failed on an obsolete `Original release folders relocated.` main-window text assertion. The active Move confirmation is in Release Map. Self-test now checks the current correct Move/Undo warning in the map rather than requiring removed main-window copy.
- The Playwright Visual QA harness timed out during initial Release Map load because its `file://` navigation is incompatible with MCC's `<script type="module">` in Chromium. It now fulfills a local mocked HTTP origin, retaining the genuine module (no external network access) and writes diagnostic screenshots/console errors on initialization failure.
- User's exact command to rerun from repository root: `git pull`, then `py -m py_compile "Music Collection Cleaner v0.05.39.pyw"`, `py "Music Collection Cleaner v0.05.39.pyw" --ui-self-test`, and `py tests/visual_qa.py --browser edge`. Review `report.json` and screenshots if any test fails.
- **NOT RUN:** these updated tests on Windows, native WebView2 hover/keyboard/resize and real-media file-safety regression. Previous Copy/Move/Undo risks remain. Do not mark stable.

## v0.5.38 - Release Map track/details cleanup (Under construction ⚠️)

- Reworked Release Map tracks into a stable grid with dedicated space for version links, statuses and classification/Ignore actions, preventing overlaps and inconsistent wrapped rows.
- Saved Remix/Live/Skip badges sit in a separate aligned icon cell; when one is saved the hover actions do not duplicate the same category. The existing saved badge still promotes to Personal Picks, and category changes retain first-click semantics.
- Optical centering uses common flex-aligned 28px icon buttons. Exclusion descriptions appear once where the saved badge already identifies Remix/Live; detailed reasoning remains in each row tooltip.
- Removed duplicate root path, redundant Copy path button, track-equivalence tutorial line and all-caps "DUPLICATE / REMOVE" labels; kept the selectable full release path, keyboard Ctrl+A / Ctrl+C and folder opener.
- Infrequent Album/EP family reassignment is under a native "Album group" disclosure (still directly available), while Keep/Ignore remain one-click.
- JS parser and static visual-contract checks passed in development. The real Windows WebView2 hover/click/focus/layout/resizing/screenshots and audio/file safety are **NOT RUN**. This is **not a stable release**.

## v0.5.37 - Fail-fast decoding and Windows Job compatibility (Under construction ⚠️)

- A supplied Noisia v0.5.36 log shows **720/720** audio files failed full decode with `[WinError 5] Access is denied`, **0** usable fingerprints, **0** acoustic comparisons and an invalid Release Map.
- Under compatible Windows Job restrictions, external tools now start with `CREATE_BREAKAWAY_FROM_JOB` and are assigned to MCC's own kill-on-close Job. If subprocess launch or safe Job assignment is denied, the application stops with an actionable error rather than misclassifying audio.
- Before reading media, FFmpeg/FFprobe must both start and return success. A scan where **every physical file** fails full decoding stops before creating false unique-recording decisions.
- Regression fixtures cover WinError 5 preflight refusal and total decoder failure. **NOT RUN:** full Python compile/`--ui-self-test`, native Windows WebView2, real files or disposable Copy/Move/Undo.
- **Next:** On Windows run `py -m py_compile "Music Collection Cleaner v0.05.37.pyw"` and `py "Music Collection Cleaner v0.05.37.pyw" --ui-self-test`, then re-analyze the same Noisia files. **Do not Copy/Move** until decoding and fingerprints work and other file-safety blockers are cleared. Cross-volume Move remains separately unsafe.

## v0.5.36 - Correct first-click pattern classification (Under construction ⚠️)

- On hover/focus in the Release Map, **🇷 Remix**, **🇱 Live**, and **🛑 Skip** now persist their category when first clicked even for automatically detected Remix/Live tracks. An existing saved category can be clicked again to move it into Personal Picks; the compact badge also promotes it directly.
- The same code preserves persistent Skip lists, "Classify patterns" management, Keep release pins, artist-owned Remix exceptions, Compilation (>50% primary-artist outsiders) warnings and single-artist retrospective Anthology classification from v0.5.35.
- Added explicit regression assertions for first click, repeated click, changed category and Keep. Embedded main/Release Map JavaScript syntax checks and independent classification-decision checks passed. **Python compile/full self-tests, Windows visual test and source-safe Copy/Move/Undo NOT RUN**. Status remains Under construction ⚠️.

## v0.5.35 - Keep releases, classify tracks, Anthology/Compilation (Under construction ⚠️)

- **Keep release / Unkeep release:** Release Map permits explicitly pinning any release to the retained set, including an automatically removed duplicate. Keeps persist in `state/manual_kept_releases.json`, override committed Ignore when necessary and constrain the optimizer; Re-Analyze is required to recalculate the export plan. An unapplied map plan is never safe to export. Source media is untouched by classification.
- **Three persistent categories:** `Classify patterns` is always available and lists Remix, Live and Skip sections plus pending review. Skip is remembered between runs (unlike v0.5.34), so `Callout hook` need not be skipped each time. Forget removes a classification; `→ Personal Picks` moves an entry to the persistent Keep exception.
- **Release Map track controls:** Hover/focus a track to use compact 🇷 Remix, 🇱 Live and 🛑 Ignore-as-pattern actions. An existing classification badge is clickable to move the pattern into Personal Picks. Patterns use extracted version descriptors, or an exact track-title key when no descriptor exists; different acoustic recordings are never inferred identical from a pattern name.
- **Safe rescans:** Saved category/Personal Picks changes apply to subsequent analyses; restored excluded audio may require a new fingerprint. The current export plan is disabled until a fresh Analyze, not misleadingly recalculated from missing evidence. Keep/Ignore changes likewise require Re-Analyze before export.
- **Noisia remix exception:** A track explicitly credited with a remix by the identified discography artist (e.g. `Asteroids (Noisia Remix)` under `Noisia ALAC`) remains eligible with Save Remixes off; other artists' remixes continue to obey exclusions unless independently rescued by a valid rule.
- **Release types:** An album-like retrospective with credited tracks all by the same artist and collection evidence becomes **Anthology**. A release with **more than half** of its tracks credited primarily to other artists becomes **Compilation**, with a non-blocking warning, when the discography artist is identifiable from the source root. Anthologies and Compilations have distinct Full Map columns. Unknown/conflicting metadata is not treated as proven fact.
- **Validation:** Code readback, two embedded JavaScript syntax parses and isolated Release Map column classification smoke tests passed. Embedded Python regression tests authored but **NOT RUN**; full Python compilation, Windows WebView2 hover/keyboard/scroll/screenshots, real Noisia scan, persisted rule roundtrip, optimizer/file Copy/Move/Undo testing all **NOT RUN**. Keep Under construction ⚠️.

## v0.5.34 - Remove redundant Release Map control (Under construction ⚠️)

- Removed duplicate **All changes** category chip. **Changes (N)** is now the single way to reset category filters and show all changes; **Full map** remains the view for all analyzed releases, including unchanged releases.
- The five category filters (Added, Upgraded, Replaced, Removed, Ignored) retain their behavior. The Release Map view counts, aria-pressed states and active-button styles remain aligned with selection.
- Deleted obsolete hint text and spacing. No selection, audio matching, optimizer, Ignore/Restore, Copy/Move or Undo semantics changed.
- Embedded UI-contract assertions plus JavaScript syntax and mocked interaction tests passed. Full Python and actual Windows WebView2/scan/file operations **NOT RUN**; status remains Under construction ⚠️.

## v0.5.33 - Classify unusual patterns later (Under construction ⚠️)

- Pattern review now has **Later**: preserves unresolved patterns in app state, includes unclassified tracks in the continuing scan, and does not cancel analysis. Escape is equivalent to Later; Cancel scan stays explicit.
- After scan or restart, **Classify patterns (N)** reopens the saved list without rescanning media. Partial classifications may be saved; remembered Remix/Live/Keep choices apply to future analyses and are not retroactively applied to an already-computed Release Map.
- Pending entries are not re-prompted during later scans. Per-pattern Skip still excludes only that one scan; deferred Skip dismisses the pending reminder until a future scan.
- Embedded regression fixture and JavaScript syntax checks added. Full Python tests and Windows WebView2/scan/filesystem acceptance **NOT RUN**. Remains Under construction ⚠️.

## v0.5.32 - Ignore this recording everywhere (Under construction ⚠️)

- **Track-level Ignore** now excludes every acoustically verified copy sharing its true `group_id` across all releases, not just the clicked filename. These copies are unavailable to collection-wide optimization after Re-Analyze. **Release-level Ignore** still excludes only that one source release, allowing alternate sources for its tracks.
- Verified GIMS user example: clicking Ignore on `Caméléon` 03:27 from `Ceinture noire [3616401604548]`, with ARTIST `GIMS;Quincy`, must also ignore acoustic MATCH peers on Bonus Track Version and `Ceinture noire [3615930950287]`, while preserving the ordinary `Caméléon` 04:00 (GIMS), which the uploaded log explicitly REJECTED as acoustically distinct.
- Saved audio-group rules schema v3 include source-instance keys and fingerprint+duration evidence for every matched copy, so renamed/moved tracks and new group IDs may be recognized after future scans without matching titles alone. Legacy v2 exact-instance Ignore rules expand to their verified group when the source is present. Restore from any ignored copy reverses the whole group, including overlapping old rules; underlying Remix/Live/other base exclusions remain intact.
- Release Map patches all affected track rows immediately without shifting/re-rendering the drawer. After Re-Analyze, ignored tracks retain the Restore button, even though their analysis exclusion is true. Compact action remains the same; accessible names clarify recording-wide scope.
- New `_recording_ignore_regression_self_test` covers multiple copies, feature versus original/Extended, legacy rule, rescan path/group changes, duration-sensitive fingerprint evidence, restoring from another edition and overlapping old rules. **Not yet run:** complete Python compile, embedded `--ui-self-test`, actual Windows WebView2, GIMS re-analysis and Copy/Move/Undo safety. Keep Under construction ⚠️.

## v0.5.31 - accelerated Finding audio candidates (Under construction ⚠️)

- Cache per-track semantic recording-root/version evidence once before candidate routing, instead of repeatedly parsing metadata for hundreds of thousands of potential pairs.
- Skip heavy pair metrics whenever the duration-neighbor fingerprint-token intersection cannot satisfy any unchanged strong/weighted/weak route. Keep diagnostics only for routed comparison/safety pairs; remove redundant visited-pair tuple storage because the far-rare branch already enforces the same 45-second boundary.
- Preserve same-title, same-album-slot, exact-Chromaprint, far-rare and deterministic shadow rescue routes and original acoustic thresholds. No media or interface changes.
- New comparison log run/summary fields: candidate_routing_seconds and candidate_diagnostic_pairs_cached. User's GIMS baseline v0.5.29: 1,604 tracks, 846,840 duration-neighbor pairs, 801,294 token rejections, 48,066 candidate pairs.
- Embedded routing regression fixture added (not executed yet); real baseline log inspection and isolated synthetic semantic benchmark completed. Full Python compile, embedded self-tests, Windows re-scan/timing, WebView2 and Copy/Move/Undo not yet executed. Under construction ⚠️.

## v0.5.30 - CD-first album anchor and featured-track preservation (Under construction ⚠️)

- When an eligible CD acoustically covers the largest WEB edition of its album family (or its missing larger-edition groups are all independently available outside the family), the exact optimizer now requires a CD as the family's album representative **before** minimizing retained physical track count. WEB albums wholly acoustically covered by the CD no longer beat it solely because they have fewer files. All wanted acoustic groups and family representation remain mandatory.
- If the CD and another album carry genuinely distinct recordings, the second complete release must remain unless every extra has a verified independent carrier elsewhere. **MCC does not automatically extract tracks, download audio, delete files or touch source folders.** A WEB Deluxe whose exclusive wanted bonus tracks have no independent sources still supersedes an incomplete CD. A Japanese CD with different core tracks that does not cover the largest WEB edition is not automatically forced solely because it has more songs.
- Featured-artist additions in either TITLE or ARTIST are not interchangeable with the base track in the weak replaceable-Version acoustic coverage pathway. Real GIMS example: ordinary `Caméléon` (4:00) versus `Caméléon (feat. Quincy)` (3:27, sometimes feat only in ARTIST). They are separate wanted recordings.
- CD-priority album selections now explain the CD anchor in Release Map details. Source and optimizer decisions preserve the v0.5.29 stable-overlay layout, v0.5.28 iTunes advisory mapping, E/C badges and per-track exclusion reasons.
- **Validation:** GitHub source readback and focused code/logic inspection passed. Embedded self-tests now contain GIMS CD57/WEB55 + two independently wanted bonus recordings, both available/unavailable separately, Camo & Krooked incomplete CD, and featured credit in title/artist. A separate Python logic-only model of album-provider selection passed. Full Python compilation, embedded `--ui-self-test`, full Windows GIMS re-analysis and WebView2/Copy/Move/Undo integration **NOT RUN**. Keep construction status.
- The previously deferred single-threaded "Finding audio candidates" performance issue remains open for a separately benchmarked optimizer update.

## v0.5.29 - stable Release Map layout (Under construction ⚠️)

- The details panel is now an **absolute overlay**, not a flex sibling that subtracts 52vw from the map and crosses container query breakpoints. The full release board retains the same width, category columns, and vertical scroll position when details open/close.
- The drawer is positioned opposite the selected release where possible, so the selected row stays visible, with its existing selected highlight. Clicking the same release a second time leaves its details open; use the existing Close (×) or Escape key. No extra controls or confirmation clicks.
- Responsive panel dimensions, keyboard focus, pointer behavior and reduced-motion behavior remain supported; no changes to comparison, optimization, original files, Copy/Move/Undo.
- JavaScript syntax and deterministic left/right placement smoke tests passed. Actual Windows WebView2 screenshots, resizing/scrolling/hover/keyboard/manual tests and full Python compile/self-test still required before stability.

## v0.5.28 - iTunes advisory mapping and explicit exclusion reasons

- **Corrected advisory states:** `ITUNESADVISORY/RTNG/ADVISORY=0` means **Unknown / no information**; `1` means **Explicit**; `2` means **Clean**. A Boolean `EXPLICIT=0` also does not by itself mean Clean. Independent `EXPLICIT=1` or explicit text labels may still positively classify a track.
- Release Map now shows compact **E**/**C** indicators beside track titles, including accessible labels, and instead of opaque "Skipped by active options" gives **"Explicit > Clean - excluded before audio comparison"** or a named Remix/Live/pattern reason. Removed incorrect "Only eligible copy" wording. Original advisory tags are emitted into future JSONL comparison logs for audit.
- Tests added for 0/1/2, true Clean vs Explicit pairs, 0 not skipped when another Explicit exists, absence of old status strings, E/C and exclusion status plumbing. Only JavaScript/source checks have run; Python/Windows acceptance remains open.

## v0.5.27 - correct other-edition status across complete scan (Under construction ⚠️)

- Actual GIMS v0.5.26 comparison log (2026-10-14 09:22:38): La même has 19 physical editions, of which one retained CD and one unselected single were fingerprinted/acoustically matched; 17 album copies were pre-excluded by Explicit>Clean (0 fingerprint frames). Laissez-moi tranquille has 13 physical editions; the 12 outside the retained plan have actual MATCH comparisons against the retained CD track. Prior UI called both "Only eligible copy" based on the selected coverage plan, not full scan.
- The Release Map now reports full-scan physical evidence, distinguishing verified acoustic duplicates (equal acoustic group IDs) from title/artist/duration-consistent but unverified editions. Expected: La même: "Audio match on 1 other edition; Also listed on 17 editions (audio unverified)"; Laissez-moi tranquille: "Audio match on 12 other editions". Exact number depends on the current scan. No new controls, clicks or dialogs.
- No changes to selection, fingerprint grouping, Explicit>Clean filtering, Copy/Move/Undo, source files or audio identity. The 17 premature exclusions are still an independent **P0 unresolved bug**, not "fixed" by wording. The single has `explicit_state=explicit` in the scan; this is metadata, not evidence that an actual Explicit La même audio version exists. Identify raw advisory source/counterpart before revising the policy.
- Static GitHub source inspection and a separate JSONL comparison-count regression PASS. Embedded Python `--ui-self-test`, Python compilation, Windows WebView2 screenshots, full fresh scan and Copy/Move/Undo are **NOT RUN**. Do not mark stable.

## v0.5.26 - display physically present but excluded copies (Under construction ⚠️)

- **User-confirmed misleading text:** `2018-03-23 - Ceinture noire (Décennie) [EU - 19439710432 - 2019]` (retained release ID 3) and `2018-03-23 - Ceinture noire [3616401604548]` (also retained, ID 39) both physically contain `La même`. Previous Release Map called the CD track **"Unique to this retained release"**. In the genuine October 14 v0.5.24 JSONL, CD `La même` is track 61, eligible, 200.04 seconds, credited `GIMS & Vianney`; WEB `La même` is track 1147, also 200.04 seconds and credited `GIMS;Vianney`, but excluded before fingerprinting (0 fingerprint frames). The scan also has independently eligible single track 280 with **real acoustic MATCH** to CD track 61 (score 0.144291, good fraction 1.0); the single is *not selected*. This establishes a **unique eligible selected provider**, NOT proof that the CD track exists on only one physical retained release.
- **Fix:** Build a display-only index of excluded physical tracks on retained releases. When an eligible selected track is essential to collection coverage, show **"Only eligible copy; also listed on excluded edition: [name]"** if another retained release contains an excluded metadata match (same normalized song title and normalized artist set, duration difference <= 1 second). Otherwise say **"Only eligible copy in retained releases"**, not a categorical physical uniqueness claim. The Release Map snapshot/UI state stores `excluded_counterparts` / `excludedCounterparts`. Disclose source edition name via the existing track status/tooltip, without new buttons, dialogs or clicks.
- **Safety:** This index is explanatory only. Similar title, artists and duration **do not prove acoustic identity**. Never populate fingerprint groups or mark skipped audio as covered from metadata. Optimizer decisions, album constraints, Copy/Move/Undo, file contents and prior classifications unchanged. The exclusion's actual reason was not present in the older v0.5.24 log; v0.5.25+ logging adds it for subsequent scans.
- **Tests:** Added embedded `--ui-self-test` synthetic paired-release fixture for the GIMS case: two selected albums, CD copy eligible, WEB copy excluded and un-fingerprinted, exact normalized performers. Tests ensure the map receives the excluded source and no acoustic match is invented. GitHub source published and read back, extracted status JS syntax and isolated status output **PASS**. Full Python compilation, embedded self-tests, actual Windows GUI/keyboard/screenshot, rescanning the real GIMS collection and filesystem Copy/Move/Undo **NOT RUN**. Keep construction status.
- **Next:** On Windows run `python -m py_compile "Music Collection Cleaner v0.05.36.pyw"`, `python "Music Collection Cleaner v0.05.36.pyw" --ui-self-test`, then rescan the same GIMS releases with logging. Confirm CD `La même` explicitly points to the excluded WEB edition without declaring a proven fingerprint duplicate. Validate retained-set optimization and Copy/Move/Undo on disposable files.

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

