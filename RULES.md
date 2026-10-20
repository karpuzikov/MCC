# Discography Torrent Project - Rules

Last updated: 2026-10-20

This file is the project-specific rulebook for the Discography Builder and Duplicate / Edition Analyzer.
The account-wide `SOFTWARE_RULES.md` baseline always applies. This file may add stricter project-specific requirements but must never weaken or override a newer global rule or a newer explicit user instruction. When project rules conflict with the global baseline, the stricter/newer requirement wins.

## MCC v0.5.51 - Candidate routing must reach edition/censored pairs (2026-10-20)

- Do not silently skip an acoustic comparison because album tags say Deluxe Edition versus Deluxe or because the title uses a censorship mask. Album-slot routing uses the existing album-family normalization. The censored-title safety route also works without album/number metadata. Empty or fully masked titles provide no censorship-routing evidence. These are comparison routes only; metadata never establishes a duplicate or satisfies coverage.
- The actual v0.5.50 log has no comparison row for Illest tracks 124/433; all other 15 corresponding Watch the Throne tracks match. Both retained releases list only their separate Illest groups as essential. Metric-profile replay alone cannot verify candidate routing: regressions must begin at the router and exercise comparison, native padding normalization, grouping and CD selection.
- Preserve the v0.5.50 4.02 primary fingerprint policy, <=8-second effective-duration rule, read-only native-rate/all-channel silence measurement, saved recording Ignore, optimizer and retention highlighting. Keep v0.5.51 Under construction. A fresh Analyze is required; uploaded metadata/profiles cannot certify new native measurements against the original files.

## MCC v0.5.50 - Calibrated fingerprint matching is authoritative (2026-10-20)

- Latest explicit user instructions: there should be no rejection after the acoustic fingerprint comparison, then calculate the mastering difference between Watch the Throne CD [US - B0015958-02] and WEB [602458447699] and make it the new threshold. This supersedes the local-window, decoded-identity, unmatched-content, Clean/Explicit identity-veto and negative-pair grouping rules in older sections. Inclusion preferences and recording Ignore remain separate from identity.
- Calibration uses all 16 actual logged CD/WEB comparison profiles. Maximum mean Hamming distance is 4.014241 bits per 32-bit fingerprint item, on That's My Bitch: 4.014241 / 32 * 100 = 12.544503125% bit difference. Round UP to 0.01 bit/item: effective cap 4.02 (12.5625% bit difference). Both normal and mastering score caps must use this value; no older 5.0/7.5 path may bypass it. Preserve the other existing primary comparison quality/minimum-evidence checks.
- A passing primary fingerprint comparison decides identity. Do not add local fingerprint windows, waveform/PCM correlation, metadata tags or another decoded-audio approval afterward. Apply the same decision in direct calls, serial/parallel workers, parent reconciliation, grouping and diagnostics. Accepted links may establish transitive identity; a separate negative pair cannot veto an accepted link.
- Preserve the previously specified inclusive <=8-second effective-duration rule and coherent duration groups. Native all-channel boundary-silence measurement only determines whether long padding can be removed from identity timing; it cannot veto a duration-eligible fingerprint match. Use the default Chromaprint item clock (1365 / 11025 seconds), not total duration / fingerprint count, when converting lag for padding measurement. Keep raw duration, original vectors and audio intact.
- Preserve v0.5.48's exact highlighting rule, live Ignore/Restore synchronization, single-file dark WebView2 interface, CD preference and Copy/Move/Undo. No new controls, dependencies, global mirrored rule changes, Actions changes or automated visual QA. Keep v0.5.50 Under construction until real Windows acceptance. Re-Analyze reuses old groups; fresh Analyze is required for this matching policy.

## MCC v0.5.48 - Highlight the tracks that retain the release (2026-10-20)

- User-approved rule: **Highlight the tracks that are the reason the release is retained.** Tracks covered by another retained release stay unhighlighted. Copies on discarded releases do not cancel highlighting. A discarded duplicate release has no highlighted tracks. This supersedes v0.5.47's all-scanned-song-presence rule and v0.5.46's generic Needed recording status wording.
- Use the actual included wanted coverage supplied only by this release within the retained plan. Excluded, recording-Ignored, manually removed and other-retained-covered rows remain unhighlighted, including stale cached annotations. Metadata listings alone cannot establish coverage. Essential count, Changes retention titles and actual track-row highlight use the same flag.
- Preserve useful Same audio on / Also listed on (audio unverified) / Also on retained release text. Global copy/version information remains informative; it does not veto a retention highlight. Keep Gem's separate global no-copy/no-other-version checks so a necessary recording with copies elsewhere does not become a false Gem.
- Concrete regression: The Life Of Pablo [602547908339] has 15 retention-reason tracks highlighted, four tracks covered by the other retained edition unhighlighted, and zero highlighted rows on its removed duplicate. Test actual generated row CSS and titles, not only counts or wording. Correct prior tests that encoded v0.5.47's rejected meaning rather than merging distinct acoustic groups by metadata.
- Recording Ignore/Restore must update retention row CSS, essential count, Changes text and Gem badges immediately across affected copies. Recompute cached display annotations with the same serializer, then patch only affected DOM rows/metadata in place so scroll and focus remain intact. Optimizer changes still require Re-Analyze.
- Keep this UI correction narrow: no audio matching, optimizer, source operations, saved Ignore, dependencies, new controls, global mirrored rules or Actions changes. v0.5.48 remains Under construction pending native Windows acceptance using user-supplied screenshots only.

## MCC v0.5.47 - Song presence controls yellow highlighting (2026-10-20)

- User rejected v0.5.46: renaming rows Needed recording while keeping shared songs yellow did not implement the request. Supersede v0.5.46's highlight/status interpretation below. Remove the generic label and restore the useful Same audio / Also listed (audio unverified) text.
- Yellow means a song is present only on this scanned release. Use a UI-only song-presence index across all scanned releases, including discarded/excluded listings, based on base song title and primary artist (including known identity aliases). Different acoustic group IDs, mastering or duration do not make a song visually unique. Keep normal, Remix and Live families separate; special families retain their named identity titles. Actual equal-group carriers also prevent a highlight when titles disagree.
- Included eligible rows on a retained release may highlight only if no other song listing or verified acoustic carrier exists elsewhere. Exclusions, recording Ignore, manual release removal and coverage by other retained releases still prevent a highlight. Unique count, Changes track previews, actual row CSS and Gem eligibility must remain consistent. The header labels this count unique, not essential.
- Song-presence metadata is presentation only. Never use it to merge acoustic groups, satisfy coverage, drop a release, bypass the 8-second rule or claim identical audio. Keep all optimizer/audio decisions and source-file operations intact. Same audio status uses actual equal group IDs; other song listings remain explicitly audio unverified.
- No new controls, menus, dependencies, global mirrored rules or Actions changes. Keep v0.5.47 Under construction pending actual Windows acceptance, using user-supplied screenshots only.

## MCC v0.5.46 - Retention track highlights (2026-10-20)

- Latest user definition: highlight tracks that justify retaining the selected release. Keep a single meaning for the track highlight, essential count and status: included wanted recording coverage supplied only by this release within the retained plan. Excluded, recording-Ignored and other-retained-covered tracks are not highlighted, even if a cached annotation is stale.
- Highlighted row status says Needed recording. Do not replace its retention reason with Also listed on ... or Same audio on ... counts across all scanned releases. Those older v0.5.28 status instructions below are superseded. Similar-title/duration listings do not prove duplicate audio; preserve related groups in the existing Versions details without changing matching or optimizer coverage.
- An acoustically distinct required version remains highlighted even if its title/length resembles another edition. A verified copy on another retained release is not highlighted. Copies in discarded releases do not supply the current retained plan. Preserve the separate Gem meaning and accessibility/Ignore/manual-removal behavior.
- Keep this UI correction narrow: no new controls, menus, dependencies, audio writes, global mirrored rule changes or Actions changes. v0.5.46 remains Under construction pending native Windows acceptance.

## MCC v0.5.45 - Equivalent album recordings and Ignore (2026-10-20)

- User authorized fixing all five reported album-selection issues and duplicate hover actions while AFK. Preserve complete-release CD preference, all wanted acoustic recordings, saved Ignore and source-file safety. No title/album whitelist may force a duplicate decision.
- Conclusive fingerprint evidence includes consistent mastering variation: overlap >=.995, mean Hamming distance <=2.5, good fraction >=.995, excellent fraction >=.98, median <=2 and p90 <=4. Require valid local windows with worst score <=min(6,max(2,2.5*mean+.25)). This supersedes the overly strict .25 mean cutoff for unassisted identity; it does not promote every broad strict/mastering candidate. Preserve changed-vocal/instrumental and local-outlier negatives and all rejected-pair grouping vetoes. First resolve coherent groups from conclusive fingerprint edges, then allow weaker decoded edges to join whole groups only under those vetoes and duration bounds; a weaker match must not split a resolved fingerprint group.
- Known Clean/Explicit disagreement under the broader mastering profile requires independent decoded confirmation; effectively carbon-copy fingerprints still override contradictory tags. Apply the same decision in serial workers, the parallel parent and diagnostics.
- Preserve inclusive <=8-second duration protection. Only independently decoded unmatched boundary silence may normalize identity timing: absolute RMS <=2 LSB and peak <=4 LSB, confirmed at native sample rate in every channel, with fail-closed errors and consistency checks. The 8kHz stereo cache locates alignment only; fingerprint silence is only a routing hint. Retain up to 2 ms unverified edge samples in identity timing. Never alter raw duration, fingerprints or source audio. Coherent groups use the same verified duration and retain the <=8-second group-diameter rule.
- Recording Ignore is not a wanted optimizer obligation. Preserve the saved Graduation Big Brother Ignore and its recording-wide propagation. Show one existing Ignore/Restore hover action alongside R/L; remove the duplicate Stop/Skip shortcut while preserving saved Skip patterns, badges and management.
- Log raw/effective durations and decoded padding evidence alongside the unchanged final exclusion/coverage diagnostics. A cached-metric replay cannot prove actual padding or certify the user's audio. Fresh Analyze is needed for new acoustic groups; Re-Analyze reuses old ones. Keep v0.5.45 Under construction pending native Windows acceptance. No global mirrored rules, dependencies, automated visual QA or Actions changes.

## MCC v0.5.44 - Fingerprint identity plus the 8-second rule (2026-10-20)

- Latest explicit user decision: "identical fingerprint, length difference below 8 seconds = dupe". Preserve the existing inclusive boundary: a gap of exactly 8 seconds is allowed; only a greater gap forces a separate version.
- Conclusive near-carbon Chromaprint evidence (`_definitive_acoustic_identity`) with consistent aligned local windows is authoritative within that limit. Unmatched end-frame counts are diagnostic; they must not require zero padding, silence-only ends, or decoded PCM approval. This supersedes v0.5.43's zero-unaligned-frames requirement and any PCM veto of conclusive identity.
- Keep minimum valid fingerprint evidence and local changed-content checks. This is not permission to treat every broad strict/mastering candidate as conclusive; non-conclusive candidates retain independent decoded verification. Duration or titles alone never establish identity.
- Keep known distinct versions, saved inclusion/Ignore rules, source-file safety and coherent grouping constraints. No new controls, dependency, visual-QA workflow or Actions changes. v0.5.44 remains Under construction pending actual Windows collection testing.

## MCC v0.5.43 - Acoustic verification and version preservation (2026-10-20)

- Chromaprint remains the discovery backbone. Titles and descriptors cannot veto acoustic candidates. Whole-track fingerprint similarity is not sufficient for non-carbon identity: use local fingerprint consistency, then independent read-only decoded stereo windows for uncertain candidates. Failed or unavailable confirmation means separate groups, with the exact reason in the comparison log. No new manual review or UI controls.
- Preserve direct negative acoustic evidence through clustering. Rejected A/C cannot join through A/B and B/C. Decode confirmation must include short final fragments and verify unmatched intros/outros are silence; an exact fingerprint fast path must satisfy the same minimum-evidence rules as ordinary comparison.
- A default title-derived Live/Remix exclusion may not make a verified copy unavailable when the exact same acoustic recording has an allowed edition. Reconcile only after acoustic grouping. Explicit saved category exclusions, pattern Skip, Explicit>Clean, and recording-wide Ignore remain effective; update the base exclusion state so Re-Analyze cannot undo the reconciliation.
- Every distinct acoustic group is a separate wanted coverage obligation. The October 15 preservation rule supersedes the October 12 edit-substitution behavior: disable automatic different-length coverage substitution, clear stale coverage aliases, and retain enough whole releases for all wanted versions.
- Count co-primary artists before deciding Compilation. Corroborate joint-act credits using actual track primary credit plus release credit, never ALBUMARTIST alone. Resolve known identity aliases separately from joint guests; an explicit feat./ft. role remains secondary. Preserve the strict >50% foreign-primary threshold and the ordinary various-performer safeguards.
- Log final per-track acoustic/coverage IDs and exclusions after saved Ignore is applied. Include all scanned releases, including blocked/dominated/forced ones, with dominance evidence and selection flags. Verify wanted coverage against the eligible set before dominance pruning.
- Retain **0.5.43 - Under construction ⚠️** until the user verifies a fresh real Windows scan and safe file operations. Linux functional tests and generated audio do not certify the user's actual recordings. No automated visual QA or Actions workflow changes.

## MCC visual-review workflow override - user instruction, 2026-10-20

- **No automated visual QA for MCC.** Do not ask the user to install, run, debug or report results from Playwright, `tests/visual_qa.py`, browser visual snapshots, or automated geometry/screenshot runners. Do not include those commands in future test instructions, continuation prompts, release checklists or required user steps.
- **Screenshots are supplied by the user at their discretion.** User will provide actual Windows WebView2 screenshots for UI review. Review and compare those screenshots when received; do not pressure the user for them or substitute invented visual test results. Until screenshots are reviewed, say UI visual acceptance is pending user screenshots rather than demanding automated tests.
- Functional correctness checks remain necessary: Python compilation, automated functional/self-tests, regression tests, acoustic/optimizer verification, and safe disposable filesystem tests. Do not equate functional testing with visual QA or drop source-data safety requirements.
- This is the user's explicit newer MCC-specific override to earlier visual QA commands/requirements in global and historical project documentation. Do not alter canonical globally mirrored `SOFTWARE_RULES.md` or `UI_UX_RULES.md`, and do not erase historical prior test evidence; this section controls the current MCC workflow.

## MCC acoustic fingerprints are authoritative - mandatory, 2026-10-19

- **Primary identity evidence:** Full-audio Chromaprint/AcoustID-compatible fingerprints are the foundation for discovering and identifying identical recordings across releases. File names, track titles, artist/release tags and descriptors are supplementary hints that may be wrong, contradictory or entirely absent. None may override conclusive acoustic evidence. An AcoustID identifier is not equivalent to a local Chromaprint vector; ensure local acoustic comparison rather than assuming an external lookup took place.
- **Comparison reachability:** A trustworthy acoustic pair must not be dropped solely because title, filename or metadata disagree. Different-version labels such as Live/Studio, Remix, Extended, Freestyle, etc. may inform diagnostics and conservative decisions, but must not prevent evaluating an acoustically promising candidate. Route from acoustic evidence, including poor/missing titles; do not rely solely on same-title/same-track-number fallback. Preserve bounded, efficient indexing rather than a quadratic all-pairs loop.
- **Fingerprint completeness:** Ensure valid fingerprints are generated or verified for readable audio needed to establish identity, including potentially excluded tracks when cross-release identification depends on them. Missing/unreadable/incomplete fingerprints must be explicitly reported, never silently treated as proof of unique or mismatched recordings. Policy exclusions (Save Live/Remix, Skip, Explicit>Clean) govern what is retained, separately from whether recordings match.
- **Positive identity and safety:** High-confidence aligned acoustic evidence must decide whether recordings are actually the same; use duration, coverage and independently measured audio difference safeguards to prevent merging genuinely different edits, live performances or mixes. A live descriptor on one side and absent on the other is not acoustic proof of a different recording. Do not declare the two user files identical without comparing their actual fingerprints.
- **Mandatory regression:** Kanye West: `2008-01-01 - 808s & Heartbreak [602557134230]` track `Pinocchio Story` versus `2008-11-21 - 808s & Heartbreak [JP - UICD-9058]` track `Pinocchio Story (Freestyle Live from Singapore)`. In v0.5.41, `_semantic_version_conflict` can pre-veto this same-base-title pair because only one title says Live; if Save Live is OFF, `configure_exclusions` clears its fingerprint and eliminates it before comparison. Tests must demonstrate the pair reaches **actual acoustic comparison** regardless of differing titles and that the resulting identity verdict follows measured audio, not a title-based override.
- **Status:** Source inspection identifies a reproducible *logic path* only; no user audio files or fingerprint metrics were provided to prove these specific encodes identical. Treat as a pending P0 classifier/candidate-routing regression; retain Under construction ⚠️ until Python self-test, audio fixture parity, Windows native acceptance and source-safe optimization are validated. Do not change GitHub Actions.

## MCC v0.5.41 - Screenshot audit and same-volume Move policy (2026-10-19)

- User supplied 12 screenshots of v0.5.40 (Main Window, Personal Picks, Classify patterns, Release Map Changes/Full map and track details). Address native visual defects: compact idle Activity, readable removed releases/status descriptions, selected-only connection lines by default and optional all-links toggle, adaptive Changes results, distinct Copy/Move, searchable/grouped/editable Personal Picks and single pending-pattern review. Preserve R/L/Ignore track actions.
- **P0 file safety invariant:** Move OLD+NEW must rename folders on the **same filesystem only**, journaling each attempted rename durably *before* changing originals. Rollback reads all journal entries, including a renamed folder whose call raised before appending to completed. Cross-volume preflight/EXDEV/WinError17 must fail closed; NEVER use copytree then rmtree(original) as an implicit cross-volume Move fallback. Offer non-destructive Copy for other drives. Block occupied/overlapping targets.
- Copy is green and leaves sources untouched; Move is amber and states same-drive restriction and relocates originals. These controls must remain distinct even when their destinations match.
- **UI control contract:** A single Review pending (N) action opens review of all unresolved patterns, not misleading row-specific Classify duplicates; saved category Forget/promote remain individual. Personal Picks search is nonmutating; local edits only persist with Save, never change Pattern keys. Full map defaults to selected-release links only, all connections are opt-in. Full track descriptions must wrap without obscuring the hover/focus action grid.
- Native Windows v0.5.40 Python --ui-self-test PASS. v0.5.40 Playwright failed on a stale selector that expected releaseRow in Changes view; the app rendered changeRow. v0.5.41 runner covers both. GitHub readback/JavaScript parser do NOT replace Python compile, full self-test, native WebView2 screenshots/keyboard/zoom and disposable Copy/Move/Undo tests. Until passed, version 0.5.41 is Under construction ⚠️. Do not modify GitHub Actions.

## MCC v0.5.40 - Personal Picks and negative-fixture isolation

- **Personal Picks have explicit positive precedence** over Save Remixes/Save Live OFF for tracks whose saved rules match; an unchecked Remix/Live setting does not prohibit user-requested songs. A user-authored Pick must never be silently ignored just to make older negative-only tests pass.
- **Test isolation:** Exclusion regression tests MUST use no Personal Picks or positive overrides. Separately test that explicit Personal Picks retain precisely matched tracks, that nonmatching remixes/live recordings remain excluded, and that removing the Pick restores ordinary exclusions. Never provide a Pick in a negative "all remixes excluded" fixture.
- Dirty Vibe: when no Picks and Save Remixes OFF, all four mixes on each EP must be excluded; OLD can be removed and NEW skipped as appropriate. When `Jack Beats` is deliberately saved as a Personal Pick, its two Re-work versions must remain wanted while six other mixes remain excluded; verify restoring normal exclusions after clearing the Pick.
- Keep audio comparison identity, classification persistence, source safety, export/Undo behavior unchanged while correcting fixture expectations. Every failed `--ui-self-test` is release blocking; the same applies to browser and real Windows WebView2 acceptance. Status remains **Under construction ⚠️**.

## MCC - mandatory Visual QA Gate (2026-10-19)

- All MCC UI edits must comply with the canonical `UI_UX_RULES.md` Visual QA Gate **before** being called fixed: inventory controls, remove redundant content, use shared spacing/icon rules, render the actual UI, run automated geometry and interaction tests, inspect/compare screenshots, then verify native Windows WebView2 at 100%/125%, minimum/normal/large windows with actual representative Noisia data.
- Developer-only runner: `py tests/visual_qa.py --browser edge` (after `py -m pip install playwright`). It loads the embedded current Release Map HTML/JS, adds realistic synthetic edge cases, captures screenshots and checks overlapping or clipped track components, hover/focus accessibility, duplicate controls, keyboard path selection, album-group disclosure and Escape. Never modify real music or enable Apply/Move via the test harness.
- The browser runner **cannot** certify native WebView2 behavior or visually judge glyph optical centering. Human review of its screenshots plus actual Windows WebView2 screenshots/interactions are mandatory. Every unrun or failed item stays **NOT RUN/FAIL** in `UI_UX_ACCEPTANCE.md` and `CONTINUITY.md`, and the software remains **Under construction ⚠️**.
- Tests and artifacts must remain separate from the single-file `.pyw` runtime and isolated from source media. Do not add redundant end-user UI just for testing; do not modify GitHub Actions workflows without explicit permission.

## MCC v0.5.38 - compact Release Map details and track rows

- Main Release Map must provide a minimal, compact details overlay without duplicating the same source path or a selectable path's Copy button. Preserve the folder opener and reliable keyboard/pointer selection of the full visible path; short readable statuses (`Removed · Duplicate`), source medium and actionable integrity warnings replace all-caps status prose and repetitive tutorials.
- Track titles must wrap in their own flex cell. Badges for **saved** categories sit in a dedicated centered icon position and never fall onto the next text row. Hover/focus classification actions occupy a **reserved grid column**, never absolutely overlay a status, duration or title. Every button has equal visual geometry, optical center, accessible name, focus and pointer feedback.
- A saved category badge directly moves its pattern to Personal Picks. Do not add a second hover action with the same saved category; preserve the ability to reclassify into the other two types. With no saved category, direct Remix/Live/Skip actions remain available and first click saves classification.
- Keep distinct Release Keep/Unkeep and Ignore/Restore; keep the Album/EP family reassignment feature but collapse its infrequent controls behind a native keyboard-operable disclosure. Preserve Re-Analyze safety/dirty status, Complete Full Map, alternatives, Ignore recordings, audio equivalence and Copy/Move/Undo.
- Compare with user-supplied Windows reference `image(20261019-092934).png`; actual Windows WebView2 screenshots at multiple dimensions and DPI, mouse/keyboard/focus/hover, long titles and real media workflow remain mandatory before stable. Status **v0.5.38 - Under construction ⚠️**.

## MCC v0.5.37 - external-decoder readiness and no invalid audio map

- Before accepting an audio scan, verify FFmpeg and FFprobe can be spawned and safely supervised under Windows Job restrictions; abort before inspecting media if external subprocess access is denied. Preserve the kill-on-close subprocess lifecycle; do not launch unmanaged fallback children.
- If **all** physical audio files fail full decoding, abort analysis and present one actionable batch failure instead of producing a metadata-only optimization, Release Map or any Copy/Move plan. Partial integrity failures still use existing per-release safety and Apply-blocking behavior.
- Preserve original files, prior snapshots and previous complete source. Verify real Windows access-denied/restricted-launcher behavior and successful recovery scan; run Python compile, `--ui-self-test`, GUI acceptance and disposable Copy/Move/Undo. v0.5.37 remains **Under construction ⚠️** until validated.

## MCC v0.5.36 - first click pattern-mark must classify, not promote

- The 🇷 / 🇱 / 🛑 buttons always **save the chosen Remix / Live / Skip classification** on the first click, even if the track is already automatically identified as a remix/live. Detection alone is **not** proof that the user has saved the category.
- Only clicking an existing *saved* category again, explicitly clicking the existing category badge, or selecting Keep sends the pattern to Personal Picks. Selecting a different category replaces the previous saved category instead of promoting it. Persist results and require fresh Analyze to update source-safe export plans.
- Check the first-click/repeat-click distinction with `Asteroids (Noisia Remix)` in an actual Noisia Release Map, including restart and change-to-Personal Picks.

## MCC 2026-10-19 - positive Keep, persistent categories and correct release types (v0.5.35)

- **Keep release** is distinct from Ignore release and ensures chosen complete release is included in optimized retained output, even if automatic minimization would remove it. Persist explicit pins by canonical source path, not transient release ID. Manual Keep supersedes committed Ignore, and the forced selection must not compromise wanted acoustic group coverage, album anchors or files. Re-Analyze before export; never copy/move using a stale plan.
- The persistent Classify patterns database has exactly three categories: Remix, Live and Skip. Skip is permanent until explicitly forgotten; never re-prompt a resolved Skip in a new scan. Previous app versions' saved patterns stay compatible. Personal Picks are positive overrides, NOT a fourth classification category; moving a pattern to Picks removes its saved negative category, and reclassifying removes the conflicting Pick.
- On track hover/focus, three compact accessible direct-action symbols (🇷 Remix, 🇱 Live, 🛑 ignored pattern) classify the extracted descriptor; when no version descriptor is extractable, scope strictly to an exact full-title key. Existing type/skip badge is directly reversible to Personal Picks. Never infer acoustic identity from matching pattern strings. If newly restored files were skipped before fingerprinting, require a **fresh Analyze** instead of falsely computing missing fingerprints from Re-Analyze.
- **Remixes by the discography artist:** positive explicit remixer credit matching an identifiable scanned discography artist is an inclusion exception even when Save Remixes OFF. Ex: Noisia's own named Remix on another act's track under Noisia's source root. Do not preserve all remixes of Noisia tracks by unrelated remixers.
- **Anthology vs Compilation:** same-primary-artist retrospective or collection evidence -> Anthology; multi-artist compilation -> Compilation. Strictly more than 50% of *all physical tracks* with primary artist credit different from the confidently identified discography artist -> Compilation with a visible NON-BLOCKING metadata warning. Do not infer from ALBUMARTIST alone; preserve album, EP, single and other explicit classification semantics. Soundtrack/DJ Mix context can supersede generic Compilation where authoritative. Keep separate Full Map Anthologies/Compilations sections without new nested menus.
- Any category, Personal Pick, Keep/Ignore or release type UI change must prevent Copy/Move using outdated decisions. On pending work/restart, show safe state and require Re-Analyze or fresh Analyze as needed.
- Mandatory runtime acceptance: clean Python compile and self-tests, real Windows WebView2 buttons/hover/focus/resize/scroll/persist, Noisia own-remixer/foreign-remixer pair, Callout hook skip/restart/forget/promote roundtrip, majority-other-artist and same-artist best-of, Keep of discarded release, recording-wide Ignore parity and disposable Copy/Move/Undo. Until then remain Under construction ⚠️.

## MCC 2026-10-19 - Release Map Changes vs All changes (v0.5.34)

- **Changes** and the old **All changes** chip produced identical visible results. Remove the redundant chip and all references to its UI ID. Keep **Changes (N)** as the single one-click action that displays all change categories and resets any active change-category filter.
- Preserve **Full map** as a distinct view of every analyzed release including unchanged releases. Preserve direct filters Added, Upgraded, Replaced, Removed and Ignored; clicking any category switches to Changes and shows only that category.
- Derived change counts, keyboard/pointer activation, focus, hover, aria-pressed and disabled states must truthfully reflect the current view/filter. Avoid explanatory interface text for obvious views.
- No audio analysis, release selection, historical saved preferences, source files, Copy/Move/Undo or acceptance status may be altered by this UI-only fix. Windows WebView2 acceptance remains mandatory.

## MCC 2026-10-19 - postpone unusual-pattern classification (v0.5.33)

- Pre-analysis unusual-pattern review has a distinct **Later** action. Clicking Later (or Escape) must preserve undecided patterns as pending **before** audio comparison continues. It must not implicitly classify or exclude undecided recordings; unlike per-pattern Skip, undecided audio remains included. Explicit partial Remix/Live/Keep/Skip choices must retain their established meanings.
- Persist grouped pending pattern keys, labels and example context under the isolated MCC state folder; keep the backlog through Windows/application restarts and subsequent scans. Already-deferred keys must not block later scans. Show a single **Classify patterns (N)** control only when pending entries exist; reopen without an audio rescan, allow one-click classifications and partial postponement.
- A late Remix/Live/Keep decision applies to **future analysis**. Do not silently claim it retroactively changed an existing Release Map plan; recompute planning separately before applying newly altered eligibility to an old result. Deferred-mode Skip only dismisses the saved reminder; the same pattern may be offered again on the next fresh scan (not a persistent exclusion).
- **Cancel scan** remains distinct from Later, and available only during initial pre-analysis review. Escape is non-destructive Later for the pattern dialog. Preserve existing separate manual acoustic-review behavior.
- Validate data persistence, no accidental exclusions, no repeated prompt for already-pending patterns, button visibility, keyboard accessibility, error recovery, restart and actual Windows WebView2/Copy/Move/Undo before stable status.

## MCC 2026-10-15 - Ignore recording EVERYWHERE vs Ignore release ONLY (v0.5.32)

- **Track Ignore:** excludes every acoustically confirmed copy of THAT recording from all editions; use current-scan `track.group_id` (NOT the replaceable-edit `coverage_group_id`). The optimizer must not source another copy of the ignored recording from a different release.
- **Release Ignore:** excludes only the selected release, leaving the same recording eligible from other releases. Track Ignore must not invoke release Ignore or implicitly block whole albums.
- Verified counterexample: GIMS Caméléon feat. Quincy 03:27 (log index 1173) acoustically MATCHES editions 312 and 1134, so all three must be ignored together. The separate original Caméléon 04:00 (log index 59) is REJECT and must remain eligible, as must unrelated versions with the same title. Do not infer recording identity from text or guest credits alone.
- Save group-scoped Ignore persistently using exact known fingerprint hashes plus duration and original instance identifiers; resolve saved evidence to the new scan's acoustic groups after comparison. The old instance-specific rules may expand to the new verified group if their source instance still exists. Never promote unrelated versions merely by matching name.
- Restore from any member reverses all overlapping saved rules for that recording, while preserving unrelated rules and pre-existing exclusion options. Pending Ignore/Restore and action labels must update for all copies without closing, scrolling or reflowing the Release Map. Keep Restore possible after Re-Analyze has made a track excluded.
- No new controls; test source, UI, reanalysis, persistence and Copy/Move/Undo. Keep Under construction ⚠️ until Windows testing passes.

## MCC 2026-10-15 - candidate router performance parity

- Do not recompute expensive per-track acoustic version metadata on every one of hundreds of thousands of candidate pairs. Precompute immutable title/root/version evidence once, then use exactly equivalent cached semantic conflicts.
- Candidate routing optimization must preserve the exact-fingerprint bypass, same-base-title and same-album-slot safety nets, far-duration rare-token recovery, deterministic shadow validation, duration-version veto and all acoustic confidence thresholds. Early negative token rejection is valid only when shared token count cannot satisfy ANY strong, weighted or weak route, and must never intercept the title/slot/exact recovery paths.
- Do not store per-pair diagnostic dictionaries and visited tuple sets for rejected duration-neighbor candidates when their eligibility can be established without such allocations. The far-rare branch's strong duration-window veto already serves as the duration visitation exclusion.
- Record actual candidate-routing wall time and candidate diagnostic cache size in JSONL. Real Windows scan plus exact baseline candidate/reason/group parity and file safety must be validated before a performance success or stable status is claimed. The 28-worker I/O selector does not imply multiprocessing of this Python router.
- No change to audio content, existing source media, album optimization, CD priority or UI is authorized by this performance-only update.

## MCC 2026-10-14 - definitive advisory values and transparent status (v0.5.28)

- **ITUNESADVISORY / RTNG / ADVISORY:** numerical `1 = Explicit`; `2 = Clean`; `0 = Unknown/no information`. Zero must not create an Explicit OR Clean classification. Missing/misleading flags must not manufacture a separate recording. `EXPLICIT=0` is a false Boolean flag, not proof of an intentionally edited Clean recording.
- Release Map track labels show a compact **E** or **C** only for known affirmative classification. Unknown has no badge. Badges require readable accessibility labels and normal compact theme; no added clicks or panels.
- When a track is excluded, display its exact named rule: **Explicit > Clean** or a specified Remix/Live/pattern reason. Never use the opaque **"Skipped by active options"** wording. Never say **"Only eligible copy"** to describe a collection that has other physical copies. Distinguish retained coverage from source presence.
- Future comparison logs must retain original advisory tag values so classifications can be audited. The false-positive `Explicit>Clean` problem with GIMS remains P0 until actual data validates the true source and any proven distinct Explicit content.

## New user rule - CD-first album anchor with separately sourced exclusive recordings (2026-10-15)

- **Goal:** For a proven acoustic album family, retain the best complete CD/physical edition as the **primary album representative** in preference to equivalent WEB editions, even when the WEB selection would save a few physical files. A CD should not lose solely because the optimizer minimizes retained track count before source quality. This supersedes older minimum-track-first wording when selecting that album family's anchor, without reducing wanted recording preservation.
- **Examine all editions of the family.** A WEB edition whose entire eligible acoustic content is present on the chosen CD is redundant and must not be retained just for those duplicate recordings. Equivalent tracks must be proven by acoustic comparison, not title/barcode.
- **Preserve genuine additional recordings/versions** from other editions. First find an acoustically verified copy on an *independently available* release **outside** this album family (e.g. Single, EP, other original release), and keep the smallest suitable provider(s) where the full collection's coverage and album constraints are preserved. Treat differing-length or otherwise distinct acoustic versions as real distinct audio, even if an older planning substitution considers them replaceable.
- **One album in the family is conditional on coverage:** Keep the chosen CD as the only release from that album family **only if** every wanted exclusive recording from other editions is preserved by such outside-family sources, or by a separately user-approved, source-safe extras workflow. Never silently discard distinct audio to force one retained album.
- If an extra exists only in another album edition and no safe external carrier exists, **do not silently discard it or automatically create loose tracks**. Until a user chooses whether to allow an isolated, reversible extras-copy workflow, keep enough additional complete releases to preserve those recordings and clearly explain why a one-CD outcome is not yet possible. Do not download from the Internet implicitly or modify original source folders.
- **Correction from user: `Caméléon` and `Caméléon (feat. Quincy)` are different recordings, NOT mere alternate-duration edits.** In the actual scan CD track 59 `Caméléon` (GIMS, 239.866667s) and track 1134 `Caméléon` (GIMS;Quincy, 207.04s) were compared acoustically and rejected as a match (32.826667s difference; score 7.264994, good fraction 0.629131). The featured recording appears explicitly titled `Caméléon (feat. Quincy)` in the Bonus Track Version (track 312), but WEB 3615930950287 encodes the featuring artist only in the ARTIST tag. **Artist-tag featuring credits must count, even when a track's TITLE omits `feat.`**. Neither title normalization nor same-base-title association may convert this unique featured recording into a substitute for the original. Preserve both distinct audio groups.
- **Current regression, `Music Collection Cleaner Comparison 2026-10-14-23-52-46.jsonl` (v0.5.29):** `Ceinture noire (Décennie) [3616402785413]` WEB, 55 included tracks, is completely acoustically covered by the 57-track existing `Ceinture noire (Décennie) [EU - 19439710432 - 2019]` CD. Another WEB album `Ceinture noire [3615930950287]` contains the **additional featured recording** `Caméléon (feat. Quincy)` (207.04s), unlike the CD's ordinary `Caméléon` (239.87s). Also present are distinct-length `La nuit c'est fait pour dormir` (251.44s vs CD 264.71s) and `Hola Señorita` (218.55s vs CD 206.85s) editions. Do not call these audio-identical or assume they are replaceable without additional verified evidence. None of these three has a verified acoustic MATCH from a release outside this album family in the supplied log.
- **Featured-credit safety regression required:** same base title but additional featured performer in TITLE or ARTIST must never silently collapse into base recording, nor be treated as a replaceable version by a weak semantic/duration rule. Verify actual source audio and log whether each distinct featured version is covered; do not invent an artist attribution or an alternate version from length alone.
- **Implementation remains pending:** design and test CD-anchor priority as a release-selection constraint, clarify whether automatically making isolated copies of album-only extras is allowed, and ensure the global optimizer preserves all versions/album requirements without invalid Copy/Move/Undo behavior. Full Python, real Windows WebView2 and filesystem tests are mandatory before marking stable.

## MCC 2026-10-14 - release details overlay must not reflow the map (v0.5.29)

- The Release Map board maintains **identical width, category column geometry, and scroll position** when details are opened or closed. The details pane uses an overlay, not a flex sidebar that shrinks the board and triggers container-query reflow.
- Position the details overlay away from the clicked release where possible. Preserve its selected highlight. Re-clicking the selected release must **not** dismiss details; Close (×) and Escape dismiss. Preserve keyboard navigation, focus, reduced-motion and independent panel scrolling; don't add clicks or unnecessary UI.
- Verify actual Windows WebView2 at original and reduced window sizes, opening multiple releases and closing by X/Escape, changes/full view, highlighting and scroll anchoring before marking stable.

## MCC 2026-10-14 - full-scan evidence takes priority over plan-only uniqueness (v0.5.27)

- A track essential to the optimizer's *retained plan* must not be called physically or acoustically unique when matching physical copies occur in discarded/excluded editions. The user identified this as a recent Release Map status regression.
- Show full-library cross-edition evidence using verified identical acoustic group ID for "Audio match on N other editions". For title/performer/duration-consistent files that were excluded before fingerprinting, or have no verified acoustic match, say "Also listed on N editions (audio unverified)". Never claim those untested files are identical; never let a metadata-only match alter the optimizer or recording groups.
- Actual v0.5.26 GIMS JSONL from 2026-10-14 09:22:38: La même 19 copies (CD+single verified MATCH; 17 pre-excluded as Explicit>Clean), Laissez-moi tranquille 13 copies (12 MATCH other editions). A genuine explicit audio variant is **NOT proven**; one single has explicit metadata, not confirmed explicit content.
- Status changes must not add new controls or required clicks; preserve full audio safety and all version/album constraints. This newest wording rule supersedes any older text prescribing "Only eligible copy". v0.5.27 remains Under construction ⚠️. The upstream premature Explicit>Clean exclusion stays a P0 blocker.

## MCC 2026-10-14 - unresolved La même Explicit/Clean classification: no invented Explicit edition

- The user states that **no Explicit recording/version of "La même" exists**. Do NOT contradict this by inventing an Explicit edition or claim the supplied v0.5.24 JSONL established one. It did NOT log the per-track `explicit_state`, `excluded_by_pattern`, raw `ITUNESADVISORY`/`RTNG`/`EXPLICIT` tags, or matching Explicit counterpart identities.
- Verified in uploaded `Music Collection Cleaner Comparison 2026-10-14-08-17-53.jsonl`: CD track index 61 and Single track index 280 of "La même" have full fingerprints and are eligible; WEB index 1147 and many other same-title copies across Ceinture noire editions are pre-fingerprint excluded, with zero fingerprint frames. Run aggregate counts 86 `pattern:Explicit>Clean` exclusions, but this alone does **not** prove why a particular "La même" was excluded. Previous assertion that "La même" has an Explicit version was unsupported and must not be repeated.
- Source audit: `explicit_state()` treats tag `ITUNESADVISORY=0/2` as clean and `1` as explicit (also `RTNG`, `ADVISORY`, `EXPLICIT`, and titles/file/album text); `apply_explicit_over_clean_policy()` excludes `clean` tracks from analysis before acoustic fingerprinting when another `explicit` track has the same normalized title and artist signature. Therefore a mis-tagged track or mistaken classification could eliminate legitimate audio without proof of distinct Explicit content.
- **P0 investigation before any stable release:** reproduce with original file tags from GIMS `La même` across retained CDs/WEB releases and the Single. Log each track's explicit state **and the exact matched counterpart causing each Explicit>Clean exclusion**, including advisory source/raw value. Confirm whether there is any genuine track-level Explicit/Clean difference via audio, not tag/title similarity. Correct wrong classification/exclusion conservatively without changing known-good versions, acoustic identity rules, or original files; test all Ceinture noire variants and unrelated genuine Explicit/Clean pairs. Do not silently infer a missing Explicit version.
- v0.5.26 is **Under construction ⚠️** with this blocker unresolved. Its display-only `Only eligible copy; also listed on excluded edition` label correction does NOT repair possible upstream exclusion and cannot count as resolution. No code patch is authorized solely by this handoff rule.

## MCC 2026-10-14 - never conflate physical presence with eligible recording coverage

- The Release Map may call an included audio group **essential/only eligible copy in the retained plan** if all other selected releases' copies are excluded, but MUST NOT call the song physically unique if the same song title appears elsewhere. Example: `2018-03-23 - Ceinture noire (Décennie) [EU - 19439710432 - 2019]` and `2018-03-23 - Ceinture noire [3616401604548]` both physically include `La même`; the latter's file was excluded before fingerprinting.
- For informative physical references, use **exact normalized title + performer signature + near-identical duration** to note another selected edition's excluded track, explicitly qualified as excluded/unverified. This is a display-only association. No matching fingerprints, merging acoustic groups, relaxing differences, or declaring identical audio from metadata; no changing selected releases, original files, Copy/Move/Undo or release-level obligations.
- The user-facing labels `Unique to this retained release` / `N unique` / `Adds unique recordings` are misleading if their technical test is only final-plan eligible coverage. Say `Only eligible copy`, `N essential`, `Adds needed recordings`, respectively. Preserve keyboard and pointer behavior and no extra UI controls. Test both positive excluded-edition metadata evidence and negative dissimilar-artist/duration cases.

## MCC 2026-10-14 - single-click unusual-pattern classification UI

- User explicitly rejected the nested four-item dropdown, redundant Keep all / Skip all controls, and separate Save choices & Continue. The review displays **exactly four inline per-pattern actions: Remix, Live, Keep, Skip**. Classify with one mouse click or keyboard activation per unresolved pattern; Remix/Live appear first. The final choice must automatically submit the full validated set and resume analysis, without an extra save/confirm control.
- Keep persists in Personal Picks; Remix/Live persist and follow the two Save category switches; Skip excludes only for this run. A displayed pattern represents its aggregated variants, **never require reviewing each song individually**. Saved decisions suppress future identical prompts. Preserve the existing reversible Personal Picks settings and never touch audio files during classification.
- **Cancel scan** is the only review footer action; Escape must also cancel the backend pending review, without silently committing staged answers or leaving the scan hung. For multiple patterns show selection feedback and permit changing a staged answer until the final selection. Expose all choices as labeled, keyboard-operable buttons with visible focus and responsive layout. Any persistence failure must be reported and allow retry.
- Do not introduce dropdowns, batch controls, extra confirmation buttons, or duplicate actions for this workflow unless the user explicitly requests them. Keep the dark compact WebView2 design and all existing optimizer/file safety behavior; actual Windows UI acceptance remains mandatory and construction status stays until verified.

## MCC 2026-10-14 - correct compilation classification using complete artist credits

- Release classification must account for **full physical track-artist diversity before remixes, live recordings, user patterns and exclusion checkboxes**. A coherent long-form release of many independently credited performers must be classified **Compilation** even when `RELEASETYPE=Album`, `ALBUMARTIST`, or parent folder suggests one performer. Use conservative, demonstrable multi-artist evidence rather than inventing unsupported metadata.
- Explicitly titled/primary-tagged **EP** or **Single** releases must not become a compilation based only on an inherited/inaccurate general-purpose `COMPILATION=1` or `Various Artists` tag when the credits don't support independence. Clearly named compilations and demonstrably diverse compilations remain compilations, including multi-artist EPs when evidence is strong.
- Regression pair from actual 2026-10-14 MCC Datsik JSONL: `2015-05-18 - Disciple 02_ The Second Coming [3614592021540]` (22 tracks, many independent acts) = Compilation; `2009-01-14 - Texx Mars EP [190374272483]` (2 recordings including Datsik both times) = EP. Do not misclassify Datsik regular albums with collaborators/featured artists. Preserve long-form BT Ima duration case, Trilogy/Highlights compilation cases, audio fingerprints and artist identity safeguards.
- Compilation must not force an ordinary album representative. It is a **last-resort wanted-recording carrier**, retained only when the user would otherwise lose distinct wanted music. Never silently delete such music merely because a release is a compilation.
- No changes to UI control inventory, file operations or destructive behavior are authorized by this classifier fix. Keep the active version `Under construction ⚠️` until real Windows and self-test acceptance; never claim unexecuted tests have passed.

## MCC 2026-10-14 - persistent unknown-pattern Remix/Live decisions

- The Unusual track pattern review must let the user choose for each new canonical pattern: **Skip this run** (temporary exclusion), **Keep / Personal Picks** (positive persisted keep), **Remix** (remember category), or **Live** (remember category). Do not require repeat confirmation for saved positive or category decisions.
- Store a category selection as a persistent, normalized, reversible rule scoped to that exact unusual-pattern key. A category decision is NOT an acoustic duplicate decision. Apply it at early per-track classification before fingerprint/optimization, using Save Remixes and Save Live global switches. Classifications survive application restarts/scans and settings saves.
- A previously classified Remix must not survive Save Remixes OFF merely because a remixer/producer appears as a secondary ARTIST; keep only the project's tightly proven added-feature exception. Save Remixes/Live ON must include the category normally. Separate semantic recording roots remain protected.
- Allow reassigning Remix ↔ Live and forgetting a category from the existing Personal Picks modal, without damaging existing Personal Picks entries or audio files. Forget restores review eligibility. Errors saving a classification must be shown, never silently reported as saved.
- Regression example: `Wow (JRMX Club)`, a repeatedly prompted unusual pattern, can be marked Remix once. The next scan must start without this review prompt, while other genuinely unresolved patterns still prompt.
- Reuse the compact dark WebView2 modal/button design, not the rejected select/dropdown, and implement accessible keyboard controls, labels and visible focus. Keep v0.5.19 Album/EP and all optimizer, copy/move/undo behavior unchanged.

## MCC 2026-10-14 - Album/EP edition families and manual reassignment

- A verified long-form edition may carry an incorrect `EP` tag. Album/EP classification differences alone MUST NOT prevent **family display grouping** when their included acoustic-group sets have >=80% overlap (denominator: smaller release; at least four shared acoustic groups), consistent with the original artist safeguards.
- Show mixed Album/EP editions inside one Release Map group and category, retaining the real individual release-type metadata. Do not conflate family membership with acoustic-track identity, recording-version roots, complete album representation or file moves.
- Both an Album and an EP can be manually assigned to a different **Album/EP** family, with an accessible, reversible Restore automatic action, saved using stable release paths. Manual edits require Re-Analyze and must not bypass Copy/Move integrity gates.
- **Preserve album constraints:** full-album representation stays album-only; when a manual target is an EP outside the album-only clustering set, the detached source album must not be split from its mandatory album-optimization family.
- Regression: `Inna - Party Never Ends (Part 2) (2013) [WPCR-15062]` and `2013-03-04 - Party Never Ends, Pt. 2 (Deluxe Editon) [5948204032791]` share six proven recordings of seven included CD tracks (85.7%). These should be shown together. `Alright` differs by 39.87 seconds and retains a separate acoustic group. Cover negative cases (below 80%, different primary artist, Singles), both manual directions, undo, and GUI states.
- Do not change standalone Singles/EP retention or the existing 8-second acoustic-version rule as a side effect of this UI/family feature.

## Shared semantic glossary for MCC and TRRNT - 2026-10-13

The canonical **cross-tool music terminology and track-file naming vocabulary** is maintained in [TRRNT MUSIC_GLOSSARY.md](https://github.com/karpuzikov/TRRNT-project/blob/main/MUSIC_GLOSSARY.md). It draws on the detailed classification below and is shared by MCC, Duplicate Edition Analyzer, Discography Builder, and the planned ALAC track filename organizer.

- In both projects, `01 Plain Jane (Remix) [ft. Nicki Minaj].m4a` denotes an **individual Remix recording with a separate featured-artist credit**, not merely a different format for the feature on a base recording.
- A genuine remix-**added** featured performer requires proof using the existing MCC original/remix comparison (or explicit remix-attached credit) rules; a bracketed credit alone does not establish that it is new. Remixer and featured artist remain different roles.
- MCC's `canonical_featured_title()` reformats featured credits only for normalized **matching keys** and does **not** prescribe how filenames must be written on disk. The shared glossary is not an instruction to change MCC's existing acoustic/semantic analysis or UI.
- The precise filename renderer beyond explicitly approved examples is not yet implemented; all future naming stages must preserve recording descriptors **and** credit metadata.

## Current MCC rule - 2026-10-13: actionable integrity diagnostics and adaptive map columns

Do not show an anonymous `Integrity / completeness: N issue(s)` warning requiring users to hunt manually. Each affected release must be named in the map's warning banner, accompanied by the exact non-invented issue text provided by the scanner. A keyboard- and pointer-accessible action must open that release's details and scroll to the row, even when filtered out of Changes view. Preserve safety: Copy and Move stay disabled until file-integrity/completeness blockers are addressed and the collection is reanalyzed.

Albums, EPs, and Singles must use available window space adaptively. Keep release-family items grouped and chronological within their flowing columns, allow up to three internal columns per category when room permits, and adapt automatically when resizing the window or showing the detail panel. Avoid horizontal overflow or truncated interaction targets and preserve curved relationships, selection, search, manual Ignore/Re-Analyze and 15-second feedback. Keep density/legibility balanced rather than forcing three equal-width one-column strips.

## Current MCC rule - 2026-10-13: 15-second map feedback after Re-Analyze

The Release Map displays new Re-Analyze selection changes **on the map itself**, without a separate textual result panel. Each newly selected release is highlighted faint green with a +; each deselected release faint red with a −. Indicators automatically clear after **15 seconds** without altering the actual selection. The map should show the actual affected release IDs rather than name-based guesses, including releases with duplicate names; bring changes into view and keep markers correct through redraws. A fresh Re-Analyze starts a fresh timer; repeated state fetches do not. For accessibility, indicators cannot rely on color alone; preserve keyboard and screen-reader text and no flashing. Continue to save technical Re-Analyze logs/audits separately from the UI feedback.

## Current MCC rule - 2026-10-13: default export destination must be actionable

A valid live Release Map must calculate `<NEW source folder> - UPDATED` automatically beside the NEW source. When the analyzed plan is ready and has no pending decisions or integrity blockers, both **Copy old + new** and **Move old + new** must be enabled without a Browse click. The displayed destination, Open-folder control, enabled/disabled state, and execution confirmation must all use the same effective destination. Browse remains an optional override; it must never be a prerequisite. When the destination cannot be inferred, require an explicit path rather than guessing. Preserve existing Copy non-destructiveness, Move/Undo safety, and approval confirmation.

## Current MCC rule - 2026-10-12: verified replaceable edit coverage

The stricter **>8.0s length threshold** still denotes a separate acoustic Version; it never proves identical audio. Nevertheless, a short/long **replaceable edit of the same recording root** is permitted to fulfill the same **collection coverage** obligation, distinct from acoustically identical grouping, if the shared real audio evidence is strong enough. Both physical tracks must retain their distinct audio-group IDs and their visible length/version differences. Extended, Acoustic, Instrumental, Remix, Live and other distinct roots cannot substitute merely through overlapping audio. The optimizer must not retain an entire edition only to preserve a non-mandatory edit when the base recording is retained elsewhere and its other songs are covered by matching singles. Conversely, missing genuine unique recording roots must never be discarded.

The user-confirmed example is the 2015 INNA WEB album `2015-07-24 - Inna [5948204123093]` plus 2014 independent singles versus the Japanese `INNA – Body And The Sun [Japan] (2015) [FLAC]`: Japanese Fool Me 213.33s vs WEB Fool Me 195.81s is not an identical acoustic file, but may substitute for coverage with exceptional fingerprint similarity (score 4.5093, good 94.48%, overlap 99.94%, acoustic coverage 91.60%). Mark it **"Covered by alternate version"**, not **"identical duplicate"**. Source must log both the real audio distinction and the substitution decision. Testing requires a new full analysis.

## Current MCC rule - 2026-10-12: duration-version threshold 8 seconds

**Newest explicit user instruction supersedes the historical 7-second rule below.** MCC uses a measured duration difference of **strictly greater than 8.0 seconds** to distinguish length-based Versions. Differences of **exactly 8.0 seconds or less** do not veto an otherwise valid fingerprint match or create a length-based badge. This does NOT permit duplicate merging based on equal or similar duration alone; audio matching remains mandatory.

Apply identically to ordinary acoustic decisions, byte-identical fingerprints, transitive grouping, manual accepted matches, and Release Map length badges. Test 8.0s (allowed) and 8.01s (separate), including transitive groups. Changes to this threshold require a new full analysis; Re-Analyze alone reuses previously computed groups.

## 1. Core objective

Build the most complete practical discography while minimizing unnecessary retained tracks.

Current priority order:

1. Preserve every wanted unique song/recording/version.
2. Keep every album represented.
3. Apply Save Remixes / Save Live at the first classification stage. Unchecked material leaves the analysis pipeline immediately. The sole Save-Remixes exception is a featured performer genuinely added by the remix; a vocalist already present on the normal version of the same song is not a remix exception.
4. Explicit supersedes the corresponding Clean track before fingerprint analysis.
5. Explicitly incompatible stated Version families are unique. A hard semantic skip is allowed only when both sides explicitly state disjoint version families (for example Radio Edit vs Extended Mix). An unlabeled title is not evidence of a base/different version and must remain eligible for acoustic comparison. Exact identical Chromaprint fingerprints always override semantic wording.
6. Prefer CD/physical over equivalent WEB.
7. For CD alternatives, hey-bro-check-log is the rip-quality authority. 80 is the acceptable-score threshold; a better comparable log is preferred for otherwise equivalent CD choices.
8. Minimize total retained track count. Every track physically carried by a retained release counts, including Remix/Live tracks excluded from analysis.
9. Prefer the already processed Existing copy over Recycle/update when every earlier non-DR criterion is tied.
10. DR/mastering is the final unresolved quality tie-break only: measure it only when every non-DR criterion is already equal, then any measurable better score wins.
11. Compilations are below regular Album/EP/Single releases and are retained only for wanted song/version coverage unavailable on regular releases.
12. Duplicate identity is fully automatic: accepted acoustic matches merge automatically regardless of title/artist naming differences; non-accepted matches stay separate automatically. No acoustic manual review.

## 2. Albums and editions

Every album must remain represented, but not every edition of an album must be kept.

Album-family selection order is absolute:

1. Group editions of the same album by proven included-audio overlap/order.
2. Count the distinct included wanted recording groups carried by each edition.
3. At least one edition with the **highest unique wanted-track count** must represent that album family, except when a no-weaker-source full core edition differs only by independently available, acoustically matched, added-featured-artist remixes issued as Singles/EPs (v0.4.5).
4. A strict same-album superset dominates the subset regardless of source rank, except for the separate featured-remix Singles/EPs exception.
5. Outside singles/EPs do not generally rescue an incomplete album edition. The only exception is **independently issued featured-remix bonus tracks**, already present on the eligible Singles/EPs and absent from the otherwise full, equal-or-better-source core album.
6. After every album has a valid full-edition representative (or qualified full core plus standalone featured remixes), minimize the **total retained physical track count** across the collection.
7. If total retained track count ties, minimize the **total retained release count**.
8. Source/rip quality, Existing/Recycle preference, and DR/mastering are later tie-breaks only.

"Most complete" means the greatest number of distinct currently included wanted recording groups, not the largest raw folder/file count. Tracks excluded by active Remix/Live/manual rules do not make an edition more complete.

### Example - Let Go

If `Let Go (Limited Edition)` contains every wanted track from `Let Go (Sketch Book)` plus `Get Over It` and `Why`, the Limited Edition represents the album and Sketch Book is dominated immediately.

It does not matter that `Get Over It` or `Why` also exist on singles/EPs. They are ordinary album bonus songs, not independently issued featured-remix bonuses. Outside singles/EPs may still be removed or retained by the later global optimizer, but they cannot make the less-complete Sketch Book edition represent `Let Go`.

If two maximum-completeness editions contain different wanted material but the same number of unique groups, either can satisfy the album-representation requirement; the global minimum-track/minimum-release solution then decides while still preserving every wanted group.

## 3. Singles and EPs

Singles/EPs are not automatically kept.

A single/EP can be removed when every recording/version it contains is already preserved elsewhere.

A single/EP should be kept when it contains at least one unique recording/version that would otherwise be lost.

When several singles/EPs overlap:

- prefer the smallest combination of releases that covers all unique recordings;
- if one release is a complete superset of another, the subset release is redundant unless it has a meaningful release-specific reason to keep;
- if a 3-track release contains the unique song plus two songs also issued as separate one-track singles, prefer the 3-track release and remove the redundant one-track singles when the recordings are the same.

## 4. Remixes

- `Save Remixes` is a direct inclusion switch. Checked: remixes participate normally. Unchecked: remixes are skipped completely by release comparison, coverage, counting, optimization, and tie-breaks.
- `Save Live recordings` follows the same rule for live-performance material.
- The only exception to an unchecked `Save Remixes` option is a featured performer genuinely added by that remix. A feature already present on a normal non-remix version of the same song does not rescue the remix.

Before fingerprint comparison, the analyzer may show only unusual/non-standard non-remix/non-live descriptor families that normal rules do not already classify. Examples include `The Matrix Mix`, `Tom Lord-Alge Mix`, and the grouped callout family (`Suggested Call Out Research Hook`, `Suggested Callout Hook`, etc.). Ordinary known patterns such as `Acoustic`, `Instrumental`, `Instrumental Excerpt`, language versions (`German Version`, `Japanese Version`, `Mandarin Version`, etc.), `Radio Edit`, any `Extended Mix` including named forms, `Original Mix`, any `VIP Mix` including named forms, `Clean Edition`, `Single Version`, and similar standard variants must not appear. Remix/live remain controlled only by `Save Remixes` and `Save Live recordings`. Pattern choices affect included coverage only and never duplicate identity.

Rules:

- explicit `Remix`, `Remixes`, `Remixed`, `Rmx`, or `Dub` markers classify remix material;
- a named/credited person, DJ, producer, or act `Mix` also classifies remix material;
- a child variant such as `<Remixer> Radio Edit`, `<Remixer> Edit`, or another named variant inherits Remix status when a sibling of the same base song explicitly establishes that remixer credit;
- the word `Mix` by itself is NOT enough;
- functional/original labels such as `Original Mix`, ordinary `Extended Mix`, `12" Mix`, `7" Mix`, and similar non-credited version labels remain included versions unless remixer context proves otherwise;
- `Club Mix` / `Club Mixes` are remix material;
- `Instrumental` and `A Capella` / `Acapella` are included distinct unique recording roots, not replaceable Versions and not remixes;
- a release named `Remixes` does NOT automatically make every track inside it ignored; classify the tracks individually;
- the presence of remix tracks does NOT make the entire release ignored;
- compare the release again after removing only explicitly identified remix tracks from included coverage;
- a mixed release can still be retained when it contains included non-remix material;
- if a redundant release contains explicit remix material, or is itself explicitly titled as a remix package, move the whole redundant release folder under `<artist>_duplicates/!Remixes/`;
- do not delete remix releases permanently; archive them in `!Remixes`.

### Equivalent album-source tie-break

When two editions provide equivalent included non-remix album content:

1. ignore explicitly identified remix tracks;
2. compare the remaining included recording/version coverage;
3. prefer CD / physical media over WEB;
4. prefer the existing processed ALAC copy when source class is otherwise equivalent;
5. only then use duplicated included-track/file count as the tie-break.

A CD edition must not lose to a WEB edition merely because the CD contains extra ignored remix tracks.

Example:

- `Want (Deluxe Edition)` - CD + LOG/CUE, core album tracks plus remix extras
- `WANT` - WEB, same included core album tracks

After remix tracks are ignored, if included coverage is equivalent, keep the CD edition and move the WEB edition to duplicates.

### Analyzer exclusion checkboxes

The analyzer provides two persistent affirmative checkboxes:

- `Save Remixes`
- `Save Live recordings`

Both are unchecked by default. Checked means the category participates normally in release comparison and selection. Unchecked means the category is skipped completely by comparison, coverage, counting, optimization, source/log tie-breaks, and clean/explicit tie-breaks. These options never create duplicate identity; track identity still requires a high-confidence audio match.

## 5. Explicit vs clean - active absolute preference

Explicit > Clean.

If an Explicit counterpart for the same normalized title/version/artist identity exists, the corresponding Clean track is excluded before fingerprint analysis.

- The Clean file does not need to fingerprint-match the Explicit file.
- The Clean track creates no coverage obligation when its Explicit counterpart exists.
- If only Clean exists, keep it normally.
- Explicit/Clean wording itself does not create a separate Version family.

## 6. Unique recording/version definition

A **Version** is a replaceable variation of the same underlying recording root. The word `Version`, `Edit`, or `Mix` by itself does not decide this.

Examples:
- `Girlfriend` and `Girlfriend (Radio Edit)` are eligible to be treated as the same replaceable recording family after acoustic comparison.
- `Girlfriend (Extended Version)` is a **new unique recording root**, not a replaceable Version of the base recording.
- `Girlfriend (Instrumental)` is a new unique recording root.
- `Girlfriend (Acapella)` is a new unique recording root.
- `Push` and `Push (Acoustic)` are separate unique recording roots.
- `Girlfriend (MTV Unplugged)` is a separate unique Live recording root.
- `Girlfriend (MTV Unplugged) [Edit]` is a Version of that Live recording root.
- `Girlfriend (Dr. Luke Remix) [ft. Lil Mama]` is a separate unique Remix recording root.
- `Girlfriend (Dr. Luke Remix) [ft. Lil Mama] (Extended Version)` is a Version of that Remix recording root.

### Parent-root rule

The unique parent recording category wins over a later edit/version suffix:

- Remix + Radio/Edit/Extended -> still the same Remix root.
- Live/Unplugged + Edit/Extended -> still the same Live root.
- Acoustic + Edit/Extended -> still the same Acoustic root.
- Instrumental/Acapella + Edit/Extended -> still that Instrumental/Acapella root.
- Base recording + Extended -> Extended is its own unique root.

### Acoustic identity

Acoustic fingerprinting remains the duplicate authority for tracks that are eligible to be compared.

- Exact identical Chromaprint fingerprints always override conflicting wording.
- Radio/Edit/Main/Single/Album-style variants of the same base root may reach acoustic comparison and merge when accepted.
- Base vs Extended, Instrumental, Acapella, Acoustic, Live/Unplugged, or Remix is semantically protected as different recording roots and is not merged merely because the audio overlaps.
- Tracks inside the same unique parent root still use acoustic comparison to determine whether they are replaceable variants or genuinely different recordings.
- External database recording identifiers are not required for duplicate identity.
- Reported duration is routing/diagnostic only.
- Alignment may compensate for leading/trailing silence or padding.
- Substantial unmatched non-silent content remains distinct.
- No acoustic identity decision is delegated to the user.

## 7. Source preference

For equivalent wanted content:

1. CD/physical beats WEB.
2. For CD alternatives, hey-bro-check-log is the rip-quality authority.
3. Comparable score 80 is the acceptable threshold.
4. A below-80 CD choice loses to a compliant at/above-80 alternative when both preserve the required coverage.
5. Between otherwise equivalent CD rips, prefer the better comparable log.
6. No external rip-database confidence is used.

CD detection:
- CUE + real rip LOG is CD evidence;
- a real EAC/XLD rip LOG can also establish a track-based CD rip without CUE;
- audiochecker.log alone does not make a release CD;
- explicit medium metadata may also establish CD.

Source preference never removes a unique wanted recording/version.

## Existing discography precedence

Existing is a late tie-break, not a hard quality floor.

For otherwise interchangeable choices:
- source class decides first;
- CD-log quality decides next where applicable;
- lower total retained track count decides before Existing precedence;
- the already processed Existing copy wins an otherwise complete non-DR tie;
- DR/mastering is measured only if Existing/Recycle status and every other non-DR criterion are also tied;
- DR therefore never causes a Recycle copy to replace an otherwise-equivalent Existing copy merely because its measured dynamics are higher.

### Optional existing-discography mode

The Existing discography folder is optional.

- If Existing is provided, compare Existing + Recycle together using all normal source/preference rules.
- If Existing is blank, analyze and optimize Recycle against itself only.
- Recycle-only mode must still remove redundant editions/singles/remix-only releases according to the same rules.
- An empty Existing path is valid and must not trigger a folder-selection error.
- The saved Existing path can be cleared and must remain cleared across launches until the user selects one again.

## 8. Existing discography vs recycle/update

Existing and Recycle are analyzed together when Existing is supplied.

- Existing is not presumed optimal.
- Recycle may add unique material, replace inferior equivalent material, or become redundant.
- Release/container names never prove duplicate identity.
- Included coverage is based on confirmed acoustic recording groups.
- Existing preference is applied after source, CD-log quality and total-track-count rules tie, and before DR/mastering.
- DR/mastering is only consulted when the alternatives are still exactly tied after Existing/Recycle preference and every other non-DR rule.
- Multi-disc folders belonging to one release remain one logical release.
- Remix-only/Live-only releases eliminated at step 1 never participate in later comparison or optimization; they remain only for final Apply bookkeeping.

## 9. Optimization model

Hard requirements:

1. Preserve every active wanted recording root/group.
2. Keep every active album family represented.
3. The album representative must carry the **maximum number of distinct included wanted groups** in that family, unless it is an equal-or-better-source full core edition whose only additional Deluxe groups are featured remixes each separately covered by an eligible Single/EP.
4. A strict same-album superset dominates even a higher-source CD subset, except for the independent featured-remix Single/EP exception. CD preference applies to full duplicates.
5. Ignored releases cannot provide coverage.
6. Ignored tracks and step-1 excluded Remix/Live/Clean material create no coverage obligation.

Global objective after those hard requirements:

1. Minimize **total retained track count**.
2. Minimize **total retained release count**.
3. Prefer better source/CD-rip quality when the first two totals tie.
4. Prefer Existing over Recycle/update when otherwise tied.
5. Use stable deterministic ordering.
6. Use DR/mastering only for the final exact tie.

Singles/EPs/compilations may satisfy wanted recording coverage, but they cannot substitute an incomplete core album for its required album representative. The full-core featured-remix exception permits standalone Singles/EPs to cover only the omitted *added-featured-remix* recordings; all regular core songs and ordinary bonus songs still require the complete edition.

CUE image layout receives no special one-file optimization bonus. Logical track count is what matters.

After the exact solve, an exact-equivalent better CD rip may replace the chosen copy only when doing so does not violate the higher-priority album/track/release rules.

## 10. Decision states

Final filesystem-plan states:
- KEEP
- REDUNDANT
- REPLACE
- NEW

There is no acoustic REVIEW state.

Duplicate identity is automatic:
- accepted acoustic evidence merges the pair;
- anything below automatic acceptance remains separate;
- different naming never turns an accepted acoustic match into a user choice.

Every REDUNDANT/REPLACE result must explain which retained release/track covers it.

## 11. Confidence

Automatic duplicate identity requires high-confidence acoustic evidence.

- same-title eligible tracks can merge only after passing active acoustic thresholds;
- alignment may compensate for silence/padding;
- substantial unmatched non-silent content blocks a merge;
- only two explicitly stated, disjoint Version families may be filtered before expensive cross-version matching; unlabeled-vs-labeled pairs remain eligible, and exact identical Chromaprint always overrides wording;
- different-title strong matches merge automatically when the acoustic matcher accepts them;
- narrow near-threshold non-matches remain separate automatically;
- everything outside automatic acceptance remains separate without asking the user.

External database recording identifiers are not part of this analyzer.

## 12. Title normalization for comparison

Comparison may use normalized titles, but normalization must never erase version meaning.

Use the shared Picard rules in:
`picard-tools/scripts/`

Relevant rules include:

- English_Title_Capitalization
- Move_Featured_Artists_to_Title
- Format_Multiple_Artists
- Unicode_to_ASCII

Normalization can standardize spelling/case/punctuation/featured-artist placement.

It must preserve semantic qualifiers such as:
`Remix`, `Live`, `Acoustic`, `Radio Edit`, `Extended`, `Instrumental`, `A Capella`, `Dub`, etc.

## 13. Album example: Queen of Time

Given:

- `2018 - Queen of Time (Limited Edition) [EU - NB 4126-0]`
  - common album tracks
  - unique bonus `As Mountains Crumble`
  - unique bonus `Brother and Sister`

- `2018 - Queen of Time [JP - GQCS-90570]`
  - same common album tracks
  - unique bonus `Honeyflow (ft. Akira Takasaki)`

If `Honeyflow` exists nowhere else, both editions may be required.

If the same `Honeyflow` exists on a single, prefer keeping:
- the Limited Edition album
- the single containing `Honeyflow`

and remove the Japanese album edition, because the album remains represented and all unique songs remain covered with fewer retained tracks.


### Release container and move integrity\n\n- Release folders may be nested under organizational folders such as `Albums`, `Other`, `Singles`, or per-title grouping folders. Discovery must recurse through those containers and identify the actual release folders. Multi-disc subfolders such as `CD1`, `CD 2`, `Disc 1`, etc. belong to one parent release and must not be treated as separate releases.

- Each direct child folder of the selected artist/recycle root is one release container.
- Audio may be stored recursively inside that release container, including `CD1`, `CD2`, `Disc 1`, etc.; those disc subfolders are not separate releases.
- Automatic filtering moves the complete top-level release container, never only an internal disc subfolder.
- A planned move may never be silently skipped.
- Every move must be verified: source gone, destination present.
- If any move fails, report the exact source/target and roll back moves already completed in that run.

## 14. Automatic filtering / safety

The analyzer must do the filtering itself. It must not require the user to inspect release rows or make line-by-line duplicate decisions.

Normal flow:

1. Scan both folders.
2. Compare tracks automatically.
3. Optimize the retained release set automatically.
4. Show one global confirmation with only summary counts.
5. Move redundant release folders automatically.
6. Leave required recycle releases in place for the next workflow stage.
7. Show only a short completion summary.

Safety rules:

- Do not permanently delete release folders.
- Move redundant folders as-is; never rename release folders while archiving them.
- The archive folder is named `<original recycle artist folder>_duplicates`, e.g. `3OH!3_duplicates`.
- Create `<artist>_duplicates` as a sibling of the selected artist folder. Example: `...\!recycle\3OH!3` -> `...\!recycle\3OH!3_duplicates`.
- Redundant releases containing remix material go under `<artist>_duplicates/!Remixes/`.
- Non-remix redundant releases go directly under `<artist>_duplicates/`.
- Reuse the same duplicates folder across runs; do not create timestamped archive folder names.
- Provide Undo for the last run.
- A single global confirmation before moving folders is sufficient; do not require per-release approval.
- If equivalence is uncertain, retain the material automatically.
- If an archive destination already exists, abort instead of renaming or overwriting folders.
- If folder structure makes an automatic move unsafe, abort the apply operation without changing anything.

## 15. Current 3OH!3-specific test case

The historical 3OH!3 dataset remains a regression dataset, but current v0.22.2 rules apply:

- preserve unique wanted non-remix songs/versions;
- remove unchecked Remix/Live material at step 1;
- Explicit supersedes corresponding Clean before fingerprinting;
- keep all albums represented;
- CD/WEB, CD-log threshold/quality, total retained track count, then Existing precedence apply before any DR/mastering tie-break;
- acoustic duplicate identity requires zero manual input: accepted matches merge automatically; all others remain separate.

## Persistent user data

This project follows the general software persistence rule:

- Any repeatable user-supplied data should be saved and reused automatically across launches and versions.
- This includes credentials/tokens, paths and folders, last-used locations, selected options, preferences, and other recurring inputs.
- Use one common application-data location under the user's dynamically resolved Windows Documents library so redirected/moved Documents folders are handled correctly.
- Updates must reuse the same stored data rather than making the user enter it again.
- Sensitive values such as credentials/tokens must be protected appropriately, e.g. Windows DPAPI.
- Ordinary non-sensitive settings such as folder paths can be stored as normal settings data.
- For Duplicate / Edition Analyzer specifically, remember at minimum:
  - Existing discography (ALAC)
  - Recycle / update folder


## English capitalization and label naming

These are the canonical English capitalization rules for album titles, track titles, artist/band names, and label names.

### Title capitalization

Use standard mixed case.

Capitalize:
- nouns;
- verbs, including `be`, `been`, `am`, `are`, `is`, `was`, `were`;
- adverbs;
- subordinating conjunctions;
- adjectives;
- pronouns;
- the first and last word of every title or major title segment.

Normally lowercase internal:
- articles: `a`, `an`, `the`;
- coordinating conjunctions: `and`, `but`, `or`, `nor`, `for`, `yet`, `so`;
- short prepositions: `as`, `at`, `by`, `for`, `in`, `of`, `on`, `to`, `from`;
- `versus`, `vs.`, `v.`;
- `etc.` when meaning "and so on/and so forth";
- `to` when forming an infinitive.

Grammar exceptions:
- capitalize `but` when it functions as an adverb ("Life Is But a Dream");
- capitalize `so` when adjectival ("You Are So Beautiful");
- capitalize `as` when functioning as a subordinating conjunction;
- capitalize a preposition when it is part of a phrasal verb ("Get Out of This Country").

Major punctuation starts a new title segment. After a colon, question mark, exclamation mark, dash used as a major separator, parentheses, or quotes, capitalize the first and last word of the segment.

For hyphenated compounds, capitalize each component according to the same title rules.

Only preserve all-caps where common usage is genuinely acronym/abbreviation capitalization. All-uppercase/all-lowercase artwork styling alone is not an artistic-capitalization exception.

Contractions and slang follow the same rules. Keep forms such as internal `o'` ("Will o' the Wisp") and `'n'` ("Rock 'n' Roll") lowercase where they stand for lowercase words.

Proper nouns keep their proper capitalization.

### Artistic-intent exceptions

Preserve genuinely intentional nonstandard capitalization used by the artist/release, e.g. `k.d. lang`, `Yellow mY skYcaptain`, or intentional lowercase `tourette's`.

Do not infer artistic intent merely because cover art prints an entire artist/title/tracklist in uppercase or lowercase.

The Picard capitalization script must not blindly title-case artist names. Artist/album-artist capitalization should come from the authoritative metadata/current artist name unless an explicit normalization rule says otherwise.

### Picard implementation

Source of truth:
- `picard-tools/scripts/English_Title_Capitalization.txt`

The script applies the deterministic title rules to both track `title` and `album`, including:
- articles/conjunctions/prepositions;
- first/last-word behavior;
- major punctuation divisions;
- common phrasal-verb exceptions;
- `vs.` / `v.` / `etc.`;
- slang forms such as `o'` and `'n'`.

Grammar-dependent and artistic-intent exceptions remain governed by this rulebook if a simple Picard script cannot infer them perfectly.

### Record label capitalization

Preferred forms:

- A&M Records
- Atlantic
- Arista Records
- ATO Records
- Below Par Records (or Below Par where source usage supports it)
- Brightside
- Casablanca Music
- Central Station Records
- Dance Pool
- Data Records
- Decaydance Records
- Decca
- DGC
- Dreamworks
- Eleven: A Music Company
- EMI
- EPIC
- Griffen Records
- Hussle Recordings
- Interscope Records
- Jive Records
- Lava Records
- Mercury Records
- Nettwerk
- Octone Records
- Rhino Records
- Radioactive Records
- Roadrunner Records
- Shock Records
- Sony
- Universal
- Virgin Records
- Wah Wah Music
- Walt Disney Records
- Warner
- WEA
- Wind Up
- Zoomba Recordings

Specific preferred forms:
- `EPIC`, not `Epic` or `EPIC recordings`;
- `Roadrunner Records`, not `roadrunner records pty. ltd.`;
- `Sony`, not `Sony Music`;
- `Universal`, not `Universal Music`;
- `Warner`, not `Warner Music`;
- `WEA`, not `Warner Elektra Atlantic`;
- `Wind Up`, not `Wind Up Records`.

Where a label officially ends in `Records`, keep `Records` except for the explicit preferred-form exceptions above.

Multiple-label formatting is not fully standardized yet; keep the source labels rather than inventing a destructive normalization.

## CD rip log quality hierarchy - implemented

Duplicate Edition Analyzer uses `ligh7s/hey-bro-check-log` v1.3.2 (Apache-2.0) as an automatically managed runtime dependency for supported EAC/XLD rip logs.

Rules:
- ignore `audiochecker.log` for rip-quality scoring;
- rip-log score is never duplicate evidence;
- compare log quality only after two CD releases are proven exact-equivalent in release/content/source structure;
- require all relevant rip logs for a release to be recognized before assigning a comparable quality key;
- unsupported or unrecognized logs remain neutral;
- multi-disc comparison uses worst-disc score first, then average score, then flagged status;
- a higher-scoring exact-equivalent CD rip may replace an Existing lower-scoring rip;
- when log quality ties or is unavailable, Existing-copy precedence remains;
- Explicit/Clean remains the absolute final tie-break after CD rip-log quality.

Do not rank CD rips by filenames or guessed ripper text; parse and score the actual log contents.

- `Original Mix` is an original-version label and must NOT be classified as a remix merely because it contains the word `Mix`.

### Album-edition clustering

Alternate album editions are grouped primarily from audio-derived included-track overlap and track order, not edition/folder names. Strong ordered overlap between fingerprint groups identifies related editions even when labels such as Limited, Special Bonus, Sketch Book, regional names, or other edition wording differ.

### Duplicate archive structure

Redundant folders must preserve their source-relative hierarchy under `<artist>_duplicates`. Example: `Singles/Title/Edition` moves to `<artist>_duplicates/Singles/Title/Edition`. Remix-bucket moves preserve the same hierarchy under `<artist>_duplicates/!Remixes/`.

Do not flatten release folders into the duplicate root. After successful moves, remove organizational directories that became empty.

- After the main optimizer, run a final selected-set redundancy prune. A non-album release that contributes no included audio beyond other retained releases must be removed when equal-or-better source copies remain. Album releases may be pruned only when another retained release still represents the same audio-derived album cluster.

- When the unusual-pattern classifier changes materially, stale review choices from older classifier generations must not be reused; start the new classifier generation with clean defaults while preserving new choices thereafter.

### Structural standard-pattern recognition

- The unusual-pattern review must classify ordinary version families structurally rather than by exact full-label whitelist. Artist/remixer/source prefixes do not make a standard family unusual (for example `BT Radio Edit`, `Adam Beyer Instrumental`, `Dan's Bedroom Demo`, `Deezer Session`, `Junkie XL Vocal Mix`, or `Eric Kupper 12\" Mix`).
- Named/ambiguous plain `Mix` labels remain review candidates when they do not match a known standard family, e.g. `The Matrix Mix` and `Tom Lord-Alge Mix`.
- Normalize common mojibake in displayed/tag-derived pattern text before classification.

### Named `Mix` remix rule

- A `Mix` credited/named after a person, DJ, producer, or act is remix material even when the literal word `Remix` is absent. Examples: `Ferry Corsten Mix`, `Tom Lord-Alge Mix`, `Madlib's Mix`, `Timo Maas Mix`.
- Ordinary functional/style labels such as `Original Mix`, `Extended Mix`, `VIP Mix`, `Radio Mix`, `Vocal Mix`, `Instrumental Mix`, `12\" Mix`, etc. remain normal version labels unless another remix rule applies.
- Named-person `Mix` tracks are controlled by `Save Remixes` and must not appear in the unusual-pattern review.

### Pattern-review refinement

- Standard suffix/type recognition must work regardless of any artist/remixer/source prefix.
- Year-only fragments extracted from compound labels are not review patterns.
- Bare `hook` belongs to the same review family as Suggested Call Out / Callout Hook.
- `Mix by <name>` and handle-style credited mixes such as `only4Erol Mix` are remix material and follow `Save Remixes`.
- UI examples should repair common UTF-8/Windows mojibake before display.

### Remaining standard-form normalization

- Treat Big Mix, New Mix, Smooth Mix, Low Gain Mix, OG Version, Chillout/genre Version, Special DJ Version, regional code Version labels (US/UK/etc.), and 7-inch/12-inch Version forms as ordinary patterns.
- Slash compounds consisting only of ordinary components, such as `Single Version / 2008`, must produce no unusual-pattern entry.
- A style/genre suffix such as `Pop Version` remains ordinary even when preceded by an artist/act credit.

### Intra-release duplicate-file rule

- Retained releases may contain redundant audio files. Clean them conservatively only when duplicate identity is already proven by the high-confidence audio group after the metadata safety gate and the files also represent the same logical track position/title within the same physical disc/folder.
- The title/track-position check is a safety gate only; it must never create duplicate identity by itself.
- Prefer the technically better survivor (lossless over lossy, then sample rate/bit depth/channels, then deterministic codec/container preference). Move redundant files to `!Duplicate Files`; never delete them.
- Do not automatically remove files from CUE-based releases because exact filenames can be referenced by the CUE sheet.
- Treat `Rmx` as a remix alias equivalent to `Remix` for Save Remixes handling and `!Remixes` routing.

### ITUNESADVISORY clean/explicit rule

- `ITUNESADVISORY=0` means clean; `ITUNESADVISORY=1` means explicit.
- Advisory state must not create or block duplicate identity and must not affect normal coverage, source selection, or track-count minimization.
- Apply advisory preference only as the absolute final release-selection tie-break.
- A clean release may be replaced by an explicit release only when they are otherwise exact equivalents: same release identity after advisory wording is stripped, same release type, same source class, same total/included track count, same included track order, and the same audio-group multiset.
- When that exact-equivalence test passes, retain explicit and move clean.
- If clean and explicit audio differs, preserve both as distinct material.

### Intra-release dedupe tag-fallback rule

- Fingerprint all audio files even when they are excluded from included coverage; exclusions affect optimization, not the ability to prove duplicate files inside a retained release.
- For intra-release cleanup, duplicate identity still requires the same high-confidence audio group.
- Same-track safety requires the same physical folder and compatible track position, but title agreement may come from either the embedded title or normalized filename. A bad TITLE tag must not block cleanup when the filename and audio identity agree.

### CD rip log quality rule

- Use `ligh7s/hey-bro-check-log` (Apache-2.0) to score supported EAC/XLD rip logs; ignore `audiochecker.log` for this purpose.
- Rip-log score is never duplicate evidence and must never merge recordings/releases by itself.
- Apply log quality only between otherwise exact-equivalent CD rips: same release identity/type/source class, same total/included track count, same included audio-group order, and the same included audio-group multiset.
- Require all non-AudioChecker rip logs belonging to a release to be recognized before that release receives a comparable log-quality key. Unsupported/unrecognized logs are neutral, not automatically bad.
- For multi-disc releases compare worst-disc score first, then average score; unflagged wins an otherwise equal tie.
- A higher log score may replace an already-processed existing CD rip when the rips are exact equivalents. If log quality ties or is unavailable, existing-copy precedence remains.
- Clean/explicit preference remains the absolute final tie-break after CD-rip log quality.

### Absolute Save Remixes / Save Live rule

- When `Save Remixes` is unchecked, every remix is completely invisible to release selection and track counting except a remix that genuinely adds a featured performer not already credited on a normal version of the same song.
- When `Save Live recordings` is unchecked, live-performance material is completely invisible to release selection and track counting. Treat explicit `Live`, `Session`/`Sessions`, and `Unplugged` labels as live-performance material.
- Excluded tracks must not affect included track count, release-type heuristics, edition/superset comparison, minimum-track optimization, source/existing tie-breaks, CD-rip-log exact-equivalence checks, or clean/explicit exact-equivalence checks.
- Excluded tracks may remain physically in a retained mixed release; they simply cannot help or hurt that release during selection.

### Direct checkbox inclusion rule

- Use direct include/skip checkbox semantics only.
- `Save Remixes` checked: remixes participate normally in all release-selection logic. Unchecked: remixes are skipped completely.
- `Save Live recordings` checked: live recordings participate normally in all release-selection logic. Unchecked: live recordings are skipped completely.
- A skipped track contributes nothing to release coverage, counts, edition comparison, optimization, CD-log quality comparison, existing-vs-recycle precedence, or clean/explicit tie-breaks.
- Skipped tracks may physically remain inside a mixed release that is retained for other included tracks.

### Exact global minimum-track rule

- Preserve all active wanted groups and album obligations first.
- Apply source/CD-log quality only as a later tie-break, after required coverage, full album representation, physical track count and release count.
- Minimize total retained track count, counting excluded extras carried inside kept releases.
- Then minimize retained release count.
- Then minimize Recycle/update release count; Existing therefore wins only a complete later tie.
- CUE image layout receives no special physical-file discount.
- Re-Analyze after Ignore/Restore reuses existing fingerprints/groups.

### Tempo/effect remix rule

- Treat `Sped Up` / `Speed Up`, `Slowed` / `Slowed Down`, and `Reverb` / `Reverbed` variants as remix material.
- These variants follow `Save Remixes` exactly: checked means they participate normally; unchecked means they are skipped completely.
- Redundant releases/packages identified by these labels route under `!Remixes` just like explicit remix releases.

### Personal Picks rule

- Personal Picks are the single persistent home for explicit user keep choices created by phrase/title rules and by **Unusual track pattern review**.
- Phrase/exact-title Personal Picks do not override an unchecked `Save Remixes` or `Save Live recordings` switch.
- An unusual track pattern explicitly checked in **Unusual track pattern review** is kept for that run and immediately added to Personal Picks as a persistent Pattern rule.
- New unusual patterns start unchecked. A Pattern already saved in **Personal Picks** is a resolved persistent keep decision and must not appear in **Unusual track pattern review** again. It remains active until removed from **Personal Picks**; after removal, the pattern becomes eligible for review again if encountered.
- Unchecked unusual patterns are skipped for the current run and are not stored as separate negative preferences. The legacy hidden `unusual_pattern_preferences_v5` map is obsolete; positive legacy choices migrate into Personal Picks.
- The only exception to early remix elimination is a featured performer genuinely added by the remix. An ordinary song vocalist repeated in remix metadata is not an exception.
- Personal Picks never create duplicate identity. Duplicate identity remains acoustic-fingerprint based.
- Phrase rules match normalized track title/filename text case- and punctuation-insensitively; exact-title rules require normalized full-title equality. Pattern rules match the analyzer's canonical unusual-pattern key.

### Automatic review model - current

Duplicate Edition Analyzer has exactly one automatic naming-review stage: **Unusual track pattern review**.

An **Unusual track pattern** is a title/filename descriptor that appears to describe a version/edition/performance form, but the analyzer cannot confidently classify it using its known semantic rules.

Known descriptors are classified automatically and must **not** enter this review. Examples include:

- Remix / named Mix / Dub / Redux;
- Radio Edit / Radio Version / Single Edit / Album Edit / Main Version;
- Extended Version / Extended Mix;
- Live / Unplugged;
- Acoustic;
- Instrumental;
- Acapella / A Cappella;
- Sped Up / Slowed / Reverb;
- ordinary `Artist - Title` or `Artist: Title` separators.

Examples that may enter the review are genuinely unknown version-like descriptors such as `Suggested Callout`, `Special Performance 2007`, or another recurring descriptor shape whose meaning is not yet known.

Rule:

> Known meaning -> classify automatically. Unknown version-like descriptor -> Unusual track pattern review.

There is **no automatic Live/Remix phrase review, phrase detector review, or category reconfirmation stage**. Save Remixes and Save Live recordings are the authoritative global category switches. Personal Picks remain the persistent home for explicit user choices and Unusual-pattern choices.

### Per-program persistent-data rule

- Every program must own its own folder under the dynamically resolved Windows Documents library: `Documents\\Karpuzikov Tools\\<Program Name>\\`.
- Duplicate Edition Analyzer uses `Documents\\Karpuzikov Tools\\Duplicate Edition Analyzer\\`.
- Keep `settings.json`, dependencies, logs, temporary working files, caches, comparison data, undo/state data, and every other analyzer-owned persistent/working file inside that program folder.
- Use the standard subfolders `dependencies`, `logs`, `temp`, `cache`, and `state` when those categories exist.
- Do not place analyzer-owned files directly in the shared `Documents\\Karpuzikov Tools` root.
- Preserve and migrate older shared-root/LocalAppData state automatically where practical instead of making the user recreate it.
- System-wide dependencies installed by Windows/WinGet may remain in their normal system locations; any dependency files downloaded and owned by this program must live under its own `dependencies` folder.

### Unusual-track-pattern rule

- An Unusual track pattern is **unknown version-like naming**, not a second Remix/Live review.
- If the analyzer already understands the descriptor, classify it automatically and do not ask the user.
- Only genuinely unknown/ambiguous descriptor shapes may enter **Unusual track pattern review**.
- Never treat an ordinary `Artist - Title` or `Artist: Title` separator as a pattern boundary merely because the song title contains words such as `Club`, `Live`, `Edit`, or `Mix`.
- A trailing separator segment may enter review only when it itself looks like a version/performance descriptor whose semantic meaning is not already known.
- Clear song titles with no actual version/performance descriptor must never appear.

### CD image rip rule

- Support lossless CD rips stored as one audio image plus CUE, including FLAC, APE, WavPack and WAV images.
- Detect image mode only when multiple `TRACK ... AUDIO` entries in a CUE reference the same physical audio file. A normal split-file CUE must remain a split-file release.
- Fingerprint the actual CUE audio segment, not the whole image file, so image rips can match split-track rips track-by-track.
- Temporary extracted segments are working files only and must be deleted after fingerprinting; they are never part of the collection.
- The physical CD image, CUE, LOG and companion files remain one indivisible release for move/rollback purposes. Never move or delete individual tracks from a CUE image.
- CD image tracks participate in the same Save Remixes, Save Live recordings, Personal Picks, collection-wide minimum-track, source-preference, and CD-quality rules as ordinary tracks.



### Mandatory software-development rule

- Apply the user's newest stored software-development standards as a required preflight before every software/program/script change. They are requirements, not optional defaults.
- Newer explicit rules override older conflicting rules.
- GUI software is dark-theme by default unless explicitly overridden.
- Prefer one complete double-clickable `.pyw` file and the minimum practical file count.
- Bootstrap/check WinGet before dependency setup. Install missing dependencies automatically and check installed dependencies for updates without requiring manual setup.
- App-managed dependencies must use the program's own `dependencies` folder.
- Keep update behavior and documentation framed as an in-place update for existing installations.
- New/unfinished GitHub software uses the status label `Under construction ⚠️`.
- Preserve existing settings and migrate legacy storage when paths/layouts change.
- Prefer immutable version/commit-pinned external download sources over mutable branch archives.
- Update implementation and documentation together in the same version.
- Cache-busting rules apply to web/userscript delivery; they are not applicable to this native `.pyw` tool.
- Credential rules are not currently applicable because Duplicate Edition Analyzer stores no authentication secrets.

### Decision explanation rule

- Every analyzed release must have a user-visible explanation of why it is retained or marked duplicate.
- The explanation must be available visually in the application; the user must not be required to inspect a text/JSONL comparison log.
- Show the Decision Map before proposed filesystem moves are applied so the user can inspect the reasoning first.
- The Decision Map must support every release in the run, including KEEP, ADD, REPLACE, SKIP, REMOVE, conservative fallback, and excluded-only outcomes.
- For retained releases, show the direct reason and, when applicable, unique/essential recording versions, required album representation, Personal Picks, source/rip-quality context, and releases it replaces.
- For duplicate releases, show which retained releases cover its included fingerprint groups, how many groups each covers, representative track titles, and any preferred-existing relationship.
- Show remix/live/pattern exclusions separately so skipped material is visibly distinguished from duplicate audio coverage.
- Same-coverage/related-release metadata is explanatory context only; it must never be presented as the evidence that created duplicate identity. Duplicate identity remains audio-based.
- Persist the latest compact Decision Map snapshot as program state under the analyzer's own `state` folder so it can be reopened without enabling detailed comparison logging.
- During the live post-analysis Decision Map, every release must expose the other releases that share its included audio groups, and those release nodes must be directly navigable.
- A retained release may be manually excluded from the current plan. This is a reversible planning constraint only until Apply; it must not move/delete files immediately.
- Manual exclusion must re-run only collection optimization against the already-computed fingerprint groups. Do not rescan folders, re-probe files, regenerate Chromaprint fingerprints, or repeat pairwise audio comparison.
- Re-optimization must apply the same album/source/existing/minimum-track rules to the remaining eligible releases and automatically select alternate carriers where available.
- The selected release must expose its full track list. If a manually excluded release contains an included recording group with no non-blocked carrier anywhere else in the analyzed collection, highlight that track clearly in red as unique/unavailable elsewhere.
- Applying a plan that would lose such manually orphaned included audio requires an explicit second confirmation that identifies the affected recordings. Never hide or silently accept this loss.
- Manual exclusions may be undone before Apply. Saved Decision Map snapshots may be reopened read-only when the in-memory analysis objects are no longer available.
- The visual graph is release-only. Do not place Factor, Reason, Track, or other non-release nodes in the network. Detailed reasoning belongs in the selected-release details panel and is collapsed by default.
- Do not pair a permanent side list with the graph. Navigation is by release nodes plus a compact search/jump control.
- The release details area must contain a large high-contrast track table and use a draggable pane/sash so the user can increase or decrease track-list height.
- The selected release path must be selectable/copyable and have an Open folder action.
- The Release Map must be a normal resizable/maximizable top-level window without transient/modal grab behavior so Windows window managers such as FancyZones can position it.
- A live Release Map must expose obvious Apply plan, Analyze again, and Close actions. Do not show disabled/confusing text such as "Re-optimization available only immediately after Analyze"; when editing context is unavailable, simply omit edit controls and present the saved map read-only.
- Optimizer/source factors are secondary detail and must be hidden behind an expandable More details control by default.

### Persistent manual track skip

- In the live Release Map the user may select a track and choose Skip track. This is a preference to exclude that proven recording group from coverage/optimization, not a duplicate-identity assertion.
- Save track-skip preferences under the Duplicate Edition Analyzer program state folder, never in the shared Karpuzikov Tools root.
- Skipping a track must immediately re-run only collection optimization; do not rescan/re-probe/re-fingerprint audio.
- The user must be able to Restore track, which removes the saved preference and recomputes the plan.
- Manual track skips must remain visibly distinct from Save Remixes / Save Live / unusual-pattern exclusions.



### Release Map UI architecture

- **Full map** mode must show all analyzed releases at the same time in one graph. The default presentation may be a compact Changes-first delta view, but Full map must remain one direct action away and must preserve the complete release/relationship context. Never replace Full map with a selected-release subgraph, neighborhood-only view, drill-down graph, or other partial graph.
- The graph contains release nodes only. Selecting a release may highlight/dim relationships, but must not remove other release nodes from the map.
- **Duplicate releases appear on the Release Map only as secondary duplicate rows connected to the retained release(s) that cover them.** They must be visually distinct from retained releases and must never be mistaken for retained output.
- **Remix-only releases must not appear on the graph when Save Remixes is unchecked.** A release whose only relevant/included material is excluded by the remix setting is omitted from the graph.
- **Live-only releases must not appear on the graph when Save Live recordings is unchecked.** A release whose only relevant/included material is excluded by the live setting is omitted from the graph.
- These are visibility rules for the graph, not deletion rules. Hidden duplicate/remix/live releases remain part of the analyzed result/state where needed for re-optimization, explanations, undo, and future setting changes.
- A release that contains at least one currently included non-remix/non-live recording may still appear even if some of its tracks are excluded by Remix/Live settings. The node represents the release's currently included material only.

- No nested navigation: no release list + map pairing, no menus within menus, no sub-maps, and no multi-level drill-down navigation. A release click opens one direct details surface for that release while the full graph remains visible.
- The Release Map UI must no longer use Tkinter/ttk. Use a modern GPU/web-rendered UI stack suitable for a large interactive graph and normal Windows window management.
- Preferred architecture: **PySide6 / Qt 6** as the Windows desktop shell with **Qt WebEngine** rendering a custom HTML/CSS/SVG release board. Python remains the analyzer/backend and communicates with the UI through a direct Qt bridge. A force-directed node library is not required for the chronological board.
- The Release Map must support smooth scrolling, search-to-release, click selection, connected-line highlighting, and track-carrier highlighting while all currently relevant release rows remain loaded in the same board.
- Selecting a release must not navigate away from the graph. Show release/track details in a single flat side or bottom panel; closing/changing selection returns focus to the same full graph state.

### Release Map changes-first presentation - v0.3.4 authoritative

This section supersedes older wording that required the complete chronological board to be the default visible surface.

- Release Map opens in **Changes** view by default. Its primary purpose is to show what differs between the current OLD discography and the proposed improved result.
- The default Changes view is compact and must not reserve Albums/EPs/Singles columns or large blank regions.
- Provide direct, clickable filters for **All changes**, **+ Added**, **⬆️ Upgraded**, **- Removed**, and **🚫 Ignored**.
- A retained NEW release that is a genuine new addition uses the **+** symbol. This marker is mandatory and must not be replaced by color alone.
- Changes view hides unchanged retained OLD releases and rejected NEW duplicate candidates unless the user searches for them. Full map remains the complete inspection surface.
- Every change row gives an immediate short reason: new addition, replacement/upgrade source and reason, OLD release removal reason, or manual ignore state.
- Search must still find every analyzed release/track. Search is not restricted to the currently visible change set.
- Track-carrier mode and alternative Version/Remix/Live navigation may automatically switch to Full map when complete cross-release context is required.
- Full map keeps the chronological Albums/EPs/Singles organization and all SVG relationships. Entirely empty release-type columns must not consume width.
- Re-Analyze results use a compact result drawer. Added/removed release items in the drawer are directly clickable and navigate to the affected release.
- The changes-first presentation is a view/filter layer only. It must not alter optimizer decisions, retained coverage, ignore state, search data, Copy output, or analysis results.

### Release Map interaction workflow

- Release nodes must be rendered as compact **rectangular release cards**, not circles/bubbles. The release name is the primary visible content of the card.
- The red/yellow/green unique-track indicator is a **small badge attached to the release card**, never the entire release node.
- Release-card text must be high-contrast light text on a dark card. Black/dark text on the dark graph background is prohibited.
- Relationship edges between releases must remain visibly distinguishable on the dark background at the default fitted view. Use clear mid/high-contrast lines; selecting a release strengthens its connected edges while unrelated edges may dim but must not disappear completely.
- Layout spacing must account for card dimensions so release cards do not collapse into an unreadable pile at the default view.
- Do not overload release rows with permanent OLD/NEW/KEEP/SKIP/DUP/unique-count chip clutter. Keep release names primary and use compact semantic change symbols plus details-on-demand. Unique-track information remains available in release details.
- Clicking a release does not navigate away from the full graph. Its details panel unfolds in place while **all visible releases remain on the same map**.
- The details panel must show the full currently relevant track list. Tracks that are unique to the selected retained release are visually highlighted.
- Hovering a track exposes a compact **Ignore** action for that track. Do not permanently show Ignore buttons on every row.
- In a live editable map, the release-level **Ignore release** action must be a prominent high-contrast destructive button at the top of the selected release details panel. It must not be hidden inside secondary details or a nested menu.
- Track-row **Ignore** must become clearly visible on hover with destructive/high-contrast styling. It may be hidden when not hovering, but it must not be obscured by the status text.
- Closing and reopening the Release Map after analysis must preserve the live editable analysis context until Apply or a new Analyze starts. Reopening must not silently downgrade to a read-only snapshot and remove Ignore/Re-Analyze/Apply actions.

- Clicking **Ignore** on a track excludes only that exact physical track instance from optimization and adds only that instance to the persistent track-ignore list. It must never expand through acoustic group ID, fingerprint equality, base title, or another release carrying the same recording. The current graph does **not** silently mutate into a final state yet; instead, the global **Re-Analyze** button becomes visually highlighted/enabled to show there are unapplied analysis changes.
- Track Ignore means: only the clicked physical file/CUE track stops contributing coverage, uniqueness, or release-retention value during the next re-analysis. Other copies of the same recording and other tracks in the same release continue to follow normal rules.
- Clicking **Ignore** on a release is a separate operation from track Ignore. It excludes **only that exact release** as a source candidate for the next optimization pass. It does **not** ignore or blacklist the recordings inside that release; those recordings remain eligible to be supplied by any other release according to normal matching/selection rules.
- Any pending track-ignore or release-ignore change highlights/enables **Re-Analyze**. Re-Analyze must use the already-computed scan/probe/fingerprint/comparison data whenever possible and re-run the collection-selection logic with the new ignore constraints; do not unnecessarily rescan or re-fingerprint unchanged audio.
- Re-Analyze must reconsider releases that were previously classified as duplicate/hidden, because they may become necessary replacement sources after a track or release is ignored.
- After Re-Analyze, unfold one bottom **result drawer** showing the exact cause/effect delta from the previous plan. Keep the full release graph visible above it.
- Result-drawer wording must be concrete, for example:
  - `IF track: "Hot (Riffs & Rays Radio Edit)" ignored, THEN release: "2008 - Hot - Single [GB - none]" removed`.
  - `IF release: "2014-10-23 - Лучшие Хиты [191018022853]" ignored, THEN releases: "2013-12-05 - In Your Eyes [5948204031992]", "2014-04-15 - Cola Song (feat. J Balvin) [075679940926]" added`.
- The result drawer must list all release additions/removals caused by the pending ignore change, not only the first one.
- After a successful Re-Analyze that changes the plan, **Apply** becomes visually highlighted/enabled.
- **Apply** is the only action that commits the current proposed filesystem move plan. Ignore and Re-Analyze are planning operations only.
- If Re-Analyze produces no plan change, say so explicitly in the result drawer and do not falsely highlight Apply as if there were new filesystem actions.
- The graph after Re-Analyze still follows graph visibility rules: duplicate/redundant releases, remix-only releases when remixes are disabled, and live-only releases when live is disabled stay hidden unless they become retained/otherwise visible under the new plan.
- Unique-track badges, unique-track highlighting, release details, and result-drawer deltas must all refresh from the same newly computed plan so the UI never shows stale pre-analysis values.

### Chronological folder-board layout and connection semantics

- The Release Map is a chronological **folder-style release board**, not a force-directed bubble/circle graph.
- Sort all visible release rows by the date prefix in the release folder name (`YYYY-MM-DD`, then `YYYY-MM`, then `YYYY`; undated rows last). Preserve ascending chronological order across columns.
- Lay releases out in compact vertical columns resembling Windows Explorer folder rows. The release folder name is the primary text; do not use oversized cards or circular nodes.
- Retained releases use normal high-contrast rows. Duplicate/redundant releases use visually secondary rows marked `DUP`.
- The small red/yellow/green unique-track badge remains only on retained rows. Duplicate rows use a neutral duplicate marker instead.
- Default connection lines have exactly one meaning: **duplicate release -> retained release(s) that cover its included recording groups**. Do not draw generic connections merely because two retained releases share some audio.
- Duplicate connection lines must be clearly visible but visually secondary. Selecting a release strengthens only the duplicate relationships touching that release.
- Clicking a track in release details activates **track-carrier mode**. Every visible release containing that exact recording group is highlighted, all other release rows dim, and bright connection lines run from the selected release to every other visible carrier.
- Track-carrier mode includes duplicate releases, so the user can immediately see previously rejected/duplicate releases that contain the same recording.
- The UI must state how many visible releases contain the selected track and provide one direct `Clear track highlight` action.
- Clicking another release clears track-carrier mode unless the user selects a track again. The full chronological board remains present at all times; there is never a sub-map.

### Personal Picks phrase extraction and review

- Personal Picks phrase detection must extract the version/remixer descriptor, not the base song title. For `Club Rocker (Play & Win Remix)`, the reusable candidate is `Play & Win Remix`; the full title must not also appear as a phrase candidate.
- The same applies to `Gimme Gimme (Ness Remix)` and `Gimme, Gimme (Dirty Nano Remix)`: use the bracketed remix descriptor only.
- A full-title fallback is permitted only when the input is genuinely a descriptor string rather than a complete track title.
- Personal Picks Review must provide direct clipboard access: each detected candidate has a Copy action and the review has Copy all review text. The persistent Personal Picks list must support Ctrl+C for selected rows and a Copy all action.


### Permanent track-family taxonomy

This taxonomy is a standing rule for all future Duplicate Edition Analyzer work.

- **Version** means a replaceable edit/variation of an already-defined recording root, such as Radio Edit/Version, Single Edit/Version, Album Edit/Version, Main Version, or a comparable short/edit form.
- **Extended Version / Extended Mix of the base recording is a unique recording root**, not a replaceable Version of the base.
- **Instrumental**, **Acapella/A Cappella**, and **Acoustic** are unique recording roots, not replaceable Versions of the base.
- **Remix** is a unique recording root. A Radio/Edit/Extended form of that same Remix is a Version of the Remix root.
- **Live/Unplugged** is a unique recording root. An Edit/Extended form of that same Live recording is a Version of the Live root.
- Classification follows semantic parentage, not the literal presence of words such as `Version`, `Edit`, or `Mix`.
- **Parent-root precedence:** Remix, Live/Unplugged, Acoustic, Instrumental, and Acapella identity is established before a later Edit/Radio/Extended suffix is interpreted.
- Release Map alternative-family UI, connection logic, counts, and Gem calculations must respect unique roots independently.
- For Gem logic, "has another Version" means another replaceable variation of the same recording root only. A different unique root does not disqualify it.

### Initial vs Result plan counters

- Release Map must always show **Initial** and **Result** counters side-by-side for both retained releases and counted tracks.
- **Initial** is captured from the first completed Analyze plan and stays unchanged for the entire live analysis session, including repeated Ignore/Re-Analyze cycles and closing/reopening that live map.
- **Result** represents the latest completed Analyze/Re-Analyze plan and shows signed cumulative differences from Initial for both releases and tracks.
- When Ignore changes are pending but Re-Analyze has not run, do not predict counts. Keep the last computed Result and visibly mark it as pending Re-Analyze.
- A brand-new Analyze resets Initial and starts a new comparison baseline.
- Track count means tracks currently participating in coverage inside retained releases; tracks skipped by active options or the manual ignore list are not included in this counter.
- The Re-Analyze result drawer must repeat the cumulative Initial -> Result release/track totals so the impact remains visible alongside the concrete release additions/removals.
- The main window must provide a compact folder control immediately beside Logging that opens this program's isolated `Documents\\Karpuzikov Tools\\Duplicate Edition Analyzer\\logs` directory.


### Main UI technology

- The active Duplicate Edition Analyzer main window uses the same PySide6 + Qt WebEngine + HTML/CSS/JavaScript UI stack as Release Map.
- Keep the main window and Release Map visually unified: same dark palette, Segoe UI hierarchy, compact controls, border/radius language, status/progress treatment, and interaction density.
- Do not revert the active main window to Tkinter in future updates unless the user explicitly requests it.
- Keep long-running work off the WebEngine/UI thread; progress and activity must remain live through the Qt bridge.

### Ignored-release inspect and restore workflow

- A release ignored from Release Map must **never disappear from the map** merely because it is ignored. Keep it in its chronological position and visibly mark it `IGNORED BY YOU`.
- Before Re-Analyze, show explicit `PENDING IGNORE` / `PENDING RESTORE` states. Do not pretend replacement sourcing has already changed.
- After Re-Analyze, keep the ignored release selected/open when possible so the user can immediately inspect the consequence of the decision.
- Every included track in an ignored release must state where that exact recording is retained instead. Show a deterministic primary retained source and, when applicable, the number of additional retained copies.
- If an ignored release contains an included exact recording that no retained release supplies, show a prominent red `NO REPLACEMENT` warning for that track. Do not silently substitute an alternate Version, Remix, or Live recording.
- Re-Analyze result details must repeat the track-by-track replacement sourcing for ignored releases, not only the release-level added/removed list.
- An ignored release must always expose an obvious `Restore release` control. Restoring changes the planning constraint and requires Re-Analyze; it does not require a new full audio scan.
- Ignore/Restore/Re-Analyze remain planning operations. No files are moved until Apply.


## Dynamic-range/mastering-quality rule - current

Dynamic range is mastering-quality preference only, never duplicate evidence.

- Measure integrated LUFS, LRA, true peak, RMS/crest-style contrast and a derived dynamics score with bundled FFmpeg.
- Cache measurements.
- Do not measure DR merely because releases look like duplicate candidates.
- First finish coverage, source, CD-log quality, total-track-count/release-count, Existing/Recycle, Explicit/Clean and every other non-DR decision.
- Measure DR only for exact interchangeable releases that remain unresolved after all of those rules tie.
- Any measurable higher dynamics score wins inside that final tie; there is no material-difference threshold.
- If DR also ties, use the stable deterministic fallback.
- DR never causes different stated Versions to merge.

## UI filesystem-path rule - mandatory and release-blocking

The repository-wide filesystem-path invariant applies to Duplicate Edition Analyzer without exception.

Any local filesystem path shown in an interactive DEA UI must have a folder/open-location control immediately before it.

Behavior:

- directory path -> open that directory in Windows Explorer;
- file path -> open Explorer with that file selected when possible;
- the control belongs directly before the path it controls;
- apply the rule everywhere a path is visible, including main UI, Release Map, review screens, diagnostics, errors, logs, planned actions/results, dependency/status views, and future UI;
- do not require copying the path or navigating manually;
- use the shared path-opening helper/component rather than one-off implementations where practical;
- existing controls are not grandfathered;
- missing path controls are a release-blocking bug;
- if the target no longer exists, fail gracefully and keep the displayed path unchanged.

## Fingerprint comparison execution - v0.21.0

- Candidate identity rules and acoustic thresholds are unchanged.
- Expensive full fingerprint comparisons run in small bounded process batches instead of giant ordered chunks.
- Identical fingerprint vectors are accepted directly as definitive acoustic identity.
- Once two tracks are already in the same validated acoustic Union-Find component, another candidate comparison between them is skipped because it cannot alter the final grouping.
- These execution shortcuts must not weaken the existing metadata safety gate or introduce metadata-based duplicate identity.
- Progress must update continuously and expose comparisons/sec and ETA for long runs.


## Early remix/live elimination rule

When `Save Remixes` is OFF, tracks classified as remixes are eliminated at the first classification stage, **except when the remix genuinely adds a featured performer not already present on a normal non-remix version of the same song**. Repeating the song's ordinary vocalist in title/filename/ARTIST metadata does not preserve the remix.

When `Save Live recordings` is OFF, tracks classified as live recordings are eliminated at the first classification stage.

Eliminated remix/live tracks must not participate in any later analytical stage. In particular they must not be:

- fingerprinted;
- added to fingerprint-token indexes;
- acoustically compared;
- placed into recording groups;
- used for dynamic-range/mastering analysis;
- used for coverage calculations;
- used by the global optimizer;
- used for release-quality tie-breaks;
- used to influence keep/remove decisions for wanted audio.

The analyzer keeps only the filesystem/release bookkeeping needed so those excluded files or releases can be moved at the final Apply stage.

If the corresponding Save option is ON, those tracks remain in the normal analysis pipeline.

Featured-remix exception:
- applies only when the remix introduces at least one featured performer absent from the normal non-remix version of that same song/primary artist;
- such tracks are not early-discarded when `Save Remixes` is OFF;
- a featured vocalist already present on the normal song does not qualify;
- if no normal counterpart exists, artist-tag or filename-prefix feat./ft./featuring is not enough to preserve the remix; only a feature explicitly attached to the remix/version wording itself is an exception;
- they are fingerprinted, compared, grouped, coverage-counted, dynamically analyzed when otherwise eligible, and optimized like normal wanted audio;
- the exception does not apply to ordinary remixer naming such as `Artist Remix` or `Artist Mix`.


### v0.21.1 implementation note

- Early Remix/Live elimination is implemented in the executable pipeline.
- Eliminated tracks are not fingerprinted, indexed, acoustically compared, grouped, dynamically analyzed, or optimized.
- A remix with `feat.`/`ft.`/`featuring` is an exception only when the performer is proven new relative to a normal version of the same song/primary artist, or when the feature is explicitly attached to the remix/version wording itself. Artist-credit prefixes alone never prove a remix-added feature.
- A featured remix that is also Live still obeys `Save Live recordings`.
- Detailed comparison logs record eligible-track count, early-eliminated count, and featured-remix exception count.


## v0.22.0 authoritative corrections

This section supersedes older historical wording elsewhere in this file.

- External database recording IDs are not read or used.
- No external rip-database confidence/verifier is used.
- Version = unique song/version, but unlabeled metadata is not proof of a different/base version. Only explicitly incompatible disjoint Version families are hard-skipped; exact identical Chromaprint always wins over wording.
- Different-title accepted acoustic matches merge automatically; near-threshold non-matches remain separate automatically. No acoustic manual review.
- Explicit > Clean before fingerprinting.
- Compilations are lower than regular Album/EP/Single and survive only for wanted groups unavailable on regular releases.
- CD rip log threshold is 80, with hey-bro-check-log as the authority.
- Optimize total retained track count, not physical file count; CUE images receive no one-file discount.
- DR has no material threshold: when earlier rules tie, any measurable better DR score wins.
- Existing is only the later tie when source/log/track-count/DR all tie.

## v0.22.1 zero-manual-input acoustic identity

This section supersedes every older manual-acoustic-review rule.

- The analyzer must never ask the user whether two tracks are the same recording.
- If the acoustic matcher accepts a pair, the pair is the same recording automatically.
- Different title spelling, alternate title, typo, artist-credit difference, featured-credit difference, or release context must not downgrade an accepted acoustic match to REVIEW.
- If the acoustic matcher does not accept a pair, keep both recordings separate automatically.
- Near-threshold/ambiguous non-matches are preserved, not reviewed.
- Only strong, explicitly incompatible semantic families may pre-block comparison. Weak/named Edit/Mix wording such as `BT Edit`, `Album Edit`, `Single Mix`, or `American Radio Edit` must remain acoustically comparable unless another strong family conflict exists.
- The goal is zero manual duplicate-identity input while remaining conservative when audio evidence is insufficient.

Regression case:
- `Voigt Kampff Test - BT & Nick Phoenix` vs `Voigt Kamff Test - BT`;
- score about 0.1152, overlap 100%, good 100%, definitive acoustic identity true;
- required result: automatic MATCH and no user prompt.


## v0.22.2 candidate-routing, DR and logging corrections

This section supersedes older candidate-routing, DR-order and detailed-log wording.

- Expensive acoustic comparison must no longer approach all-pairs behavior merely because common Chromaprint tokens collide.
- Same-base-title pairs and identical fingerprint vectors remain safety routes and are acoustically resolved regardless of reported duration.
- Different-title candidates are routed with bounded duration neighborhoods plus normalized fingerprint-token containment; duration remains routing-only and never becomes identity evidence.
- Token evidence is weighted by rarity. Very common tokens are suppressed from far-distance candidate expansion.
- High-confidence candidates are processed before weak candidates so validated Union-Find components can eliminate redundant later work transitively.
- A deterministic shadow-validation sample is run against router rejects. A sampled acoustic false negative is recovered into the recording group and explicitly logged.
- Semantic Version detection includes named `... Mode` descriptors such as `Lunar Mode` and explicit release-level families such as `Extended Versions`.
- Common mojibake and harmless unmatched tag-edge quotation garbage are normalized before semantic routing; normalization must not strip legitimate leading/trailing apostrophes.
- Wanted tracks whose fingerprint generation fails remain conservative singleton recording groups; a fingerprint failure must never erase wanted coverage.
- Comparison logging uses normalized per-track catalog records plus compact pair references. Full pair details are kept for matches, content-gate cases, near-threshold cases, shadow recoveries and a deterministic reject sample; ordinary rejects are aggregated into funnel/route/duration counters.
- DR/mastering runs only after the normal optimizer and all non-DR preference passes. Only exact interchangeable releases that remain fully tied are measured.
- Existing/Recycle status is part of the pre-DR tie signature. DR cannot override Existing with an otherwise-equivalent Recycle copy.
- Re-Analyze uses the same final-tie-only DR rule without rescanning/re-fingerprinting unchanged audio.


## v0.22.4 semantic-version false-unique correction

This section supersedes every older rule that treated one labeled side and one unlabeled side as automatically different recordings.

- An unlabeled title does not mean "base/original version". It means the version is unspecified.
- Therefore pairs such as `Four (Original Mix)` vs `Four`, `Tomahawk (Original Mix Edit)` vs `Tomahawk`, `Always (Radio Edit)` vs `Always`, and equivalent cases must reach acoustic comparison when candidate evidence permits.
- Same-base-title routing remains a safety route for these pairs.
- Exact identical Chromaprint fingerprints bypass semantic-version conflict completely and merge automatically.
- If both sides explicitly state version families, a hard semantic skip is allowed only when their declared families are disjoint. Shared family/release context means audio gets the final say.
- Explicitly incompatible examples such as `Radio Edit` vs `Extended Mix` remain safely separated before expensive comparison unless their fingerprints are literally identical.


## v0.22.5 remix exclusion and weak-version-gate correction

This section supersedes older featured-remix, contextual-remix, and generic Edit/Mix conflict wording.

- The featured-remix exception is about a performer added by the remix, not the song's ordinary featured vocalist repeated in remix metadata.
- Determine ordinary featured performers from non-remix/non-live versions of the same base song and primary artist across the analyzed collection.
- If a remix carries only those ordinary feature credits, it is excluded when Save Remixes is OFF.
- If the remix adds a new explicit featured performer, it remains the sole Save-Remixes exception.
- If no normal counterpart exists, a feature in the artist credit or filename artist prefix is not preserved automatically; only remix-specific feature wording can create the exception.
- Parent-family Remix inheritance is release-title independent and collection-wide, scoped by base song + primary artist. Explicit remixer evidence on one release can classify the same remixer's child edit/version on another release.
- Examples that must classify as Remix when remixer evidence exists anywhere in the analyzed collection include `Mood II Swing Radio Edit`, `Mantronik Electrohippy Formula`, `Dave Aude Radio Edit`, `Loverush UK! Radio Edit`, `Lucid Mix Edit`, and comparable named child variants.
- A confident non-primary two-word possessive remixer descriptor such as `Simon Hale's Orchestrata` is Remix even without a literal Mix/Remix word.
- Weak labels such as `BT Edit`, `Album Edit`, `Single Mix`, and generic/named edits are not strong enough to veto acoustic comparison.
- Regression pairs that must reach the acoustic matcher include `Godspeed (Radio Edit)` vs `Godspeed (BT Edit)`, `Remember (American Radio Edit)` vs `Remember (Album Edit)`, and `Remember (Edit)` vs `Remember (Single Mix)`.
- Strong structural conflicts such as Radio vs Extended or Acoustic vs Instrumental remain eligible for semantic pre-blocking unless exact identical Chromaprint overrides the wording.


## v0.4.9 strict superset before source preference - authoritative

- **New user rule:** Prefer the original CD/physical edition only when the alternative has fully equivalent included wanted audio. If an acoustically proven Special/Deluxe Edition has *all* wanted tracks of the original and **at least one more wanted bonus recording** (particularly one unavailable on any other release), the **complete Special/Deluxe** replaces the original regardless of source class. It is not correct to keep the smaller CD as a second release just to preserve CD quality for the shared recordings. Release titles alone do not prove audio identity; use accepted fingerprint groups.
- **Confirmed Camo & Krooked regression:** OLD `2011-10-03 - Cross the Line [EU - NHS194CD]` is 14-track CD; NEW `2011-10-03 - Cross the Line (Special Edition) [3617056553892]` is 18-track Digital Media. All 14 original songs are matched acoustically; the Special Edition additionally contains four wanted songs: `Cryptkeeper`, `Change Me`, `Portal`, `Menace`, with no alternate bonus-track sources. Correct result: retain **WEB Special Edition 18 tracks only**, not 14-track CD plus 18-track WEB.
- For full duplicate edition coverage, prefer CD/physical or the higher quality verified rip, then Existing when earlier objectives tie. Lower source quality does not negate a strict acoustic superset.
- Hard requirements are wanted acoustic groups, regular-release preference over compilation where an eligible regular source exists, and a most-complete valid album-family representative. Then minimize total physical tracks, then retained releases, then compare CD/source quality, Existing, DR in that order. No hard best-source-carrier requirement per acoustic group.
- Preserve the v0.4.5 **independently issued featured-remix single** exception: if the complete CD core plus eligible featured-remix singles is a smaller valid collection than the WEB Deluxe and meets all family/coverage rules, retain CD plus singles. If separate remix sources disappear, Deluxe must represent the album and redundant CD must not remain.
- Prior v0.3.5/v0.3.6 wording that required redundant shared-CD preservation is expressly superseded. Keep all existing corruption, TRACKTOTAL, WebView2 Release Map, Re-Analyze, Undo and Copy/Move safeguards.
- v0.4.9 must pass tests for the exact Cross the Line 14/18 split, exact equivalent 14/14 CD vs WEB preferring CD, Bangarang superset and Starboy remix exception. Windows file operations remain unverified, status Under construction ⚠️.

## v0.4.8 album-wide vs per-disc TRACKTOTAL scope - authoritative

- `TRACKTOTAL` and `TOTALTRACKS` can describe either the entire multi-disc release or the individual disc, depending on tagger/provider. Do **not** assume all totals are disc-local, and do not require the declared release-wide number on each separate disc. Inference is based on physical disc grouping, track number sequences, and declared totals; title, barcode and folder name are not sufficient to infer a missing recording.
- **Confirmed user regression:** JPEGMAFIA `2024-08-01 - I LAY DOWN MY LIFE FOR YOU_ DIRECTOR'S CUT [199066832615]` with 28 physical audio tracks, CD1 numbered 1..21 and CD2 numbered 1..7. The user confirms that `TRACKTOTAL=28` means **21+7 across the release**. The v0.4.7 validator wrongly expected 28 per disc and raised false incompleteness warnings, blocking valid Copy/Move. The uploaded `Duplicate Edition Analyzer Comparison 2026-10-10-07-46-43.jsonl` (app v0.4.7) establishes the exact 28-file split but does not serialize the underlying total tags.
- In a multi-disc release with one distinct declared positive total, if the number exceeds each disc's own physical count *and* highest individual track index, treat it as a **release-wide total**. Also recognize continuous global numbering across discs (e.g. CD1 1..21, CD2 22..28). Compare summed physical track count against the declared release-wide total and check gaps/duplicates in each disc's numbering. For independent disc-restart numbering, do not require 1..28 on both discs.
- If discs declare their own totals, e.g. CD1=21 and CD2=7, retain the per-disc expectations and flag a missing file on either disc. If album-wide total is 28 and combined files are 27, flag missing one release-wide even if no individual disc's last track number can be inferred. Conflicting declared tags, duplicate indices and numbering gaps remain validation failures. Missing/unparsable total metadata alone is not evidence of an incomplete release.
- Fail-safe file operation blocking remains only for actual observed corrupt/invalid/incomplete cases. Do not block correctly complete multi-disc releases due to an incorrect total scope. Regression tests must exercise both scopes and missing-file cases. Full dark WebView2 map, all other warnings, duplicate optimization, and Copy/Move safety must remain intact.
- v0.4.8 CI `https://github.com/karpuzikov/userscripts/actions/runs/38025613096` PASSED including multi-disc 21+7 and missing-file self-tests. No real Windows source-rescan or destructive operations tested. Status Under construction ⚠️.

## v0.4.7 standalone semantics, media integrity, release completeness - authoritative

- **Standalone source mode is not an import:** When the Existing discography path is empty and only New/update is provided, the Release Map must not call the optimizer's selected releases Added/UPGRADE to another collection. Initial Changes must be zero; map defaults to Full map with `Scanned` counts and `Proposed retained` counts (no +/- deltas). Retained release rows are labeled RETAIN or ✓, not + ADD; hide the absent OLD legend. This must not change the underlying automatic duplicate selection or the actual file operations requested explicitly later.
- **Actual corrupt audio detection:** FFprobe's metadata and Chromaprint similarity are insufficient to validate whole-file integrity. During analysis, fully decode each distinct physical audio source, including the final frames, with FFmpeg `-xerror -err_detect explode -f null -`. Fail/decoder diagnostics must identify the exact path and prevent the file from providing positive fingerprint duplication evidence. CUE image source is decoded once rather than once per virtual track. Never remove or repair user audio automatically. A missing/failed fingerprint is not evidence of corruption by itself; use full decode.
- **No unsafe Apply:** If any scanned release has corrupt/unreadable audio or confirmed metadata incompleteness/inconsistency, keep the user-visible plan provisional and block Copy/Move operations on the full analyzed collection. The warning must show affected release and decoded issue, including path and source counts. Fixes require re-analysis; no silent overriding this guard via Re-Analyze or front-end controls.
- **Incomplete releases:** Respect case-insensitive `TRACKTOTAL`, `TOTALTRACKS`, `TRACKNUMBER`, `DISCNUMBER`, plus `TRACKNUMBER=6/6` when explicit totals are absent. Verify each disc independently, including physical disc directories and virtual CUE tracks, for missing numbers, duplicate track numbers, contradictory declared totals and indices above the declared maximum. Do not infer a release is incomplete merely because the total tag is absent: that state is unknown.
- Preserve full existing dark WebView2 map; annotate affected rows and details, use warning text plus icon, avoid false addition and actual-change labels, and preserve all Existing+New behavior unchanged. Follow UXDT wording, system feedback and error prevention.
- v0.4.7 CI self-test: missing 2 of 3, complete 1/2 + 2/2, conflicting totals, unknown totals, correctly complete multi-disc; mocked full-decode corruption; standalone map-state and labels. Actual Windows source folders and full FFmpeg decoding remain user validation work. Status stays Under construction ⚠️.

## v0.4.6 incomplete acoustic fingerprint detection and PCM recovery - authoritative

- `fpcalc` can produce misleadingly short fingerprint vectors while reporting the full media duration. Do not count a nonempty JSON fingerprint as complete by default. Example: v0.4.5 real `Privilege` ALAC vs FLAC, both 170.573333 seconds; comparison score 0, 100% overlap against the shorter fingerprint, but only 10.8407% of the longer fingerprint aligned. The 94% unmatched-content gate MUST reject this pair until a complete acoustic fingerprint has been recovered; never lower thresholds or merge by matching title/duration.
- Identify clearly truncated fingerprint frame counts using Chromaprint's approximate 11025/4096 frames/second and conservative startup/tolerance margin. On those files alone, re-decode via FFmpeg into app-local temporary 11025 Hz mono PCM WAV, then recalculate full Chromaprint and delete PCM after the attempt.
- If the regenerated fingerprint is still incomplete or decoding fails, record an explicit error and leave the track as a conservative unmatched singleton. Do not fabricate acoustic identity. Always preserve the source file. Temporary files belong inside the program-specific `Documents\\Karpuzikov Tools\\...\\temp` path.
- `fpcalc` and FFmpeg remain application-owned child subprocesses under the Windows kill-on-close Job Object. The recovery pipeline obeys the same HDD/SSD I/O worker count as the initial fingerprinting stage.
- The comparison JSONL must expose frame counts and whether automatic PCM repair occurred for each track. Include a synthetic root-cause reproduction, recovered-vs-unrecovered tests, validation of cleanup, and preserve full WebView2 GUI/previous matching rules. Hardware behavior must still be tested before stable release.

## v0.4.5 full CD core versus independently issued featured-remix bonuses - authoritative

- **User regression (The Weeknd 2026-10-10):** OLD 19-track CD `Starboy [US - B0026150-02]` provides 18 wanted core recording groups; NEW 21-track WEB `Starboy (Deluxe) [602455499851]` contains those same 18 plus `Reminder (Remix)` and `Die for You (Remix)` (with one excluded Kygo remix). Both included remix groups have proven acoustic MATCH to independently issued Singles. The 1-track `Reminder (Remix)` single and 4-track `Die for You (Remix)` single cover all the Deluxe-only wanted material.
- A full core Album edition may satisfy the family obligation rather than the highest-group-count Deluxe edition **only if all** of the following are true: it is in the same audio-derived album family and same normalized album title, its entire wanted acoustic-group multiset is contained in the Deluxe edition, its source rank is no worse than the Deluxe, every missing Deluxe group is an included remix with a genuinely newly featured performer, and every such group is independently carried by an **available/unblocked, included Single/EP** in the same optimization pool. Every wanted acoustic group remains a hard requirement; source rank is a later tie-break. Missing one qualifying single revokes the exception and requires the Deluxe.
- The optimizer must not pre-prune the full core album as dominated when this exception applies, even for equal-source copies. It must evaluate both complete Deluxe and full-core-plus-Singles plans by physical retained track count and then release count, with source quality only as a late tie-break. This is NOT a blanket relaxation for ordinary songs, unique versions, Extended/Instrumental additions, compilations, or an incomplete core album.
- Target result in the real Starboy scenario: keep the 19-file CD core + 1-file Reminder Single + 4-file Die for You Single = **24 physical files**, not CD + 21-file Deluxe + existing 4-file Die for You Single = **44 files**, while keeping every wanted acoustic group without a hard source floor.
- The provider rule, equivalent-edition prepruning, exact-cover album constraint and late-plan validation must share this same exception logic. Automatic decisions must label the omitted WEB Deluxe as covered and keep the standalone Reminder single if it is the chosen carrier.
- Keep full GUI WebView2, never switch to the rejected ASCII prototype. Status remains Under construction ⚠️ until the actual Windows dataset and Move/Undo are tested.

## v0.4.4 compilation fallbacks and featured-remix correction - authoritative

- Compilation tracks must NEVER be permanently excluded merely because a regular release currently covers their acoustic groups. Group identity survives manual Ignore/Restore and Re-Analyze. The exact optimizer ranks regular releases ahead of compilations *per wanted group*, uses compilations for groups with no unblocked regular providers, and uses the best CD/source class as a late tie-break among otherwise eligible providers. Re-Analyze with all replacement sources manually removed must be able to bring the original compilation back rather than losing wanted material. Manual exclusions must be respected, never automatically undone.
- Recognize `The Highlights` anthology (including Deluxe) and 25+ track `Trilogy` collections as compilations even if tags report Album. Distinguish them from legitimate albums. Only keep a compilation if at least one wanted recording remains unavailable through eligible regular releases.
- Remixes with newly credited performers in ARTIST metadata (e.g. separated with `;`, `&`, `with`) must be preserved under Save Remixes OFF when the additional featured artist was not credited on the normal source. When no ordinary comparison source is available, two-person collabs can count as explicit new-artist evidence, but an ambiguous 3+ artist credit alone must not rescue established remix-only packages such as Dirty Vibe.
- `Call Out My Name` is a normal song title, not a Callout Hook review pattern. Match only explicit Suggested Callout / research / Hook descriptor forms. Old excluded phrase choices must not suppress the song.
- `Chopped & Screwed` inside a bracketed or trailing version descriptor is remix material. The ordinary title `Chopped and Screwed Dreams` must not be misclassified.
- An explicitly identified shortened Single Version with significant length difference and nonidentical acoustics must not be merged into its album recording simply because the comparison's unmatched-fingerprint segment is classified as silence. Identical fingerprint vectors remain definitive.
- Preserve the graphical WebView2 application and all previous parity requirements. Add realistic regression fixtures and keep Under construction until real-folder reruns, Move/Undo and Windows UI testing pass.

## v0.4.3 fingerprint worker ownership and storage-aware concurrency - authoritative

- `fpcalc.exe`, `ffprobe.exe`, CUE extraction `ffmpeg.exe` and other subprocesses launched through the common hidden-process runner must be owned by the application on Windows using a kill-on-close Job Object. Close, X and normal/abnormal process termination must not leave those spawned analysis subprocesses running. Never mass-kill unrelated `fpcalc.exe` processes.
- Auto audio I/O worker selection must inspect both OLD and NEW storage, choosing a conservative limit when either drive is rotating, network, or unidentifiable. Windows storage seek-penalty descriptor determines SSD versus HDD when accessible. HDD/network/unknown: 2; both SSD: up to 8. Do not equate CPU threads to safe disk concurrency.
- Expose a labeled, keyboard-accessible graphical WebView2 audio I/O worker selector with Auto and manual 1-32, persist it in program-local settings and report the actual I/O limit in Activity. Cap `ffprobe` and `fpcalc` concurrent invocations; acoustic comparison parallelism is independently CPU-bound.
- UI source-folders text must distinguish read-only analysis from destructive Move export. Never replace the graphical Release Map with the rejected ASCII prototype.
- Include regression tests for auto/mixed-media and manual count selection, bridge availability, and tracked subprocess behavior. Windows-specific Job Object / physical-media detection still require hands-on runtime verification. Keep status Under construction ⚠️.

## v0.4.2 copy/move collision and Undo safety - authoritative

- Both OLD+NEW export modes must preflight **nested/ancestor** destination targets in addition to exact collisions; reject overlapping release folder targets before any source/destination modifications.
- Copy must stage each retained release inside the destination volume and publish its output folder only when the copy completes; failed copies must not leave a partial final-named release folder.
- Same-volume rename permission/sharing violations are fatal and must never be treated as cross-volume errors. Only actual EXDEV / Windows ERROR_NOT_SAME_DEVICE may trigger checked copy-before-delete fallback.
- Undo must not silently drop entries when neither original nor moved-to path exists. Keep the manifest on conflicts, continue processing independently recoverable entries, and report the unresolved paths.
- Visible default export paths must have operative folder-opener controls before the user selects a custom location.
- v0.4.2 retains the full graphical WebView2/pywebview interface and all v0.4.1 Copy/Move/Undo behavior. Actual Windows and full Skrillex folder testing remain mandatory; no stable/parity claims.

## v0.4.1 default UPDATED destination and independent Copy/Move - authoritative

- Both export actions must default to a sibling `<New / update releases root> - UPDATED` folder. Example: `C:\!deemix Music\Metro Boomin` => `C:\!deemix Music\Metro Boomin - UPDATED`. Show the complete default next to a folder-opener immediately, and retain a Browse override per action.
- **Copy old + new releases into:** copies retained OLD + NEW source material non-destructively, never changes either scanned source.
- **Move old + new releases into:** replaces the old `Copy new releases into`; it is not a rename of a NEW-only copy! It must physically relocate retained OLD + NEW release folders, leave rejected/non-retained releases at source, and require a clear confirmation explicitly warning that selected originals leave their folders.
- Fail closed on destination collisions, overlapping paths or output trees within either source tree; never merge/overwrite release folders. Copy/move must preserve original folder structure and filenames.
- Cross-volume moves must verify copied release data before deleting originals, keep Undo/restoration journal, and roll back completed transfers if a later move fails. Do not silently overwrite previous Undo history. After Move, invalidate release decisions with obsolete source paths and request a fresh analysis.
- Both actions are disabled during pending manual Ignore/Restore decisions until Re-Analyze completes. Under construction remains until Windows runtime testing confirms behavior.

## v0.4.0 graphical Release Map line readability - authoritative

- This version continues the full-featured WebView2 + pywebview desktop interface. The isolated ASCII/Textual experiment is rejected and must not be merged or substituted for the graphical release.
- Full Map release-row separators must be clearly discernible at default Windows scale: 2 px solid `#303947`, while preserving compact rows, group headings, and normal hover/selection styles.
- Relationship paths must have visibly pronounced but differentiated stroke weight: idle duplicates 1.65 px, selected duplicates 2.8 px, Versions 3.0 px, Remixes/Live 2.65 px, active-track carriers 3.6 px. Preserve their opacity hierarchy and dash patterns.
- These are strictly presentation changes. Do not modify acoustic identity, recording groups, retained release selection, Release Map relationship membership, Apply, undo, file copying, or analysis performance to achieve thicker lines.
- Keep `0.4.0 - Under construction ⚠️` until the user's exact Skrillex rerun and Windows GUI inspection pass.

## v0.3.9 Release Map excluded-only visibility - authoritative

- **Every analyzed release** must remain inspectable in **Full Map**, including zero-wanted-track releases excluded at the first classification stage. Never use membership in an acoustic recording group as a prerequisite for showing an analyzed release.
- Existing-folder releases whose entire tracklist was excluded by Save Remixes OFF / Save Live OFF / Personal Picks pattern decisions retain backend `REMOVE` actions and MUST appear under Changes > `- Removed` with a clear count and cause. Example: `All 4 tracks excluded (Save Remixes OFF).`.
- NEW/update-folder excluded-only releases remain `SKIP`; keep them in Full Map for transparency but do NOT classify them as OLD removals or new additions in Changes.
- Rendering visibility must not alter coverage, the exact optimizer's selected set, Apply/Undo behavior, or retained release/track plan totals.
- End-to-end regression: four-track Recess (Remixes) and Dirty Vibe (Remixes) OLD sources are removed rather than silently hidden; the paired NEW remix-only releases remain skipped, and the OLD/NEW Dirty Vibe decisions/snapshots/UI nodes preserve their tracklists and exclusion reasons.

## v0.3.8 Re-work remix classification - authoritative

- A parenthesized, bracketed, or separated trailing remix descriptor written `Re-work`, `Rework`, `Reworked` (including a credited act such as `Jack Beats Re-work`) is Remix material, subject to **Save Remixes** in the very first classification stage. It must not reach the acoustic matcher or the optimizer when Save Remixes is OFF unless it has a genuinely remix-added featured artist.
- A word appearing in an unrelated standalone song title such as `Rework Your Life` must NOT automatically be deemed a remix; identify descriptor syntax.
- The only Save Remixes OFF exception continues to be a *feature added by the remix*, not an ordinary featured performer repeated on the normal song. Re-work credits use the same exception.
- Personal Picks cannot resurrect excluded remixes. An EP containing only excluded remixes must not be retained merely because its album/folder name says `Remixes`.
- Regression dataset: OLD `2014-12-14 - Dirty Vibe (Remixes) [075679931368]` (release 12) and NEW `2014-12-15 - Dirty Vibe (Remixes) [075679931351]` (release 74); their third tracks `Jack Beats re-work` were falsely classified as normal wanted audio in v0.3.7. With Save Remixes OFF and no remix-added feature, all four tracks of each must be excluded and neither release retained.
- Keep Save Remixes ON behavior, metadata-independent audio identity for wanted material, and genuine remix-added feature exceptions intact.

## v0.3.7 album completeness and provider-type aliases - authoritative

- Provider release-type labels (Album/EP/Single) are not proof that two physically identical, acoustically equivalent copies are different editions. An EP/Single-tagged OLD copy may fulfill a maximum-completeness Album obligation only when its release-family title matches and its entire physical track count, included acoustic group sequence and multiplicities match a maximum-completeness Album edition.
- This exception must never permit an incomplete EP, different release family, compilation, missing wanted recording, or larger/different physical container to substitute for a maximally complete Album.
- The exact solver must allow those truly equivalent providers BEFORE late Existing/NEW tie-breakers; source preference and Existing no-churn rules apply normally.
- Every late release substitution must preserve acoustic coverage, valid album representation and the minimum-track/minimum-release objective. If a late tie-break somehow violates these invariants, restore the last valid exact optimizer selection with an explicit logged diagnostic; do not crash or silently degrade the plan.
- Regression: Skrillex Scary Monsters OLD tagged EP, NEW tagged Album, 11 physical tracks including seven wanted acoustically matched groups, must retain OLD without album-completeness failure when both are otherwise interchangeable.

## v0.3.6 source-safe optimization and Release Map correctness - historical (hard source floor superseded v0.4.9)

- **Superseded v0.4.9:** All eligible non-compilation acoustic-group carriers can satisfy recording coverage. CD and CD rip log quality are late tie-breakers, not a separate per-group best-source-floor obligation.
- **Superseded v0.4.9:** Source preservation is not a hard coverage constraint. Do not add redundant higher-source CD copies after exact minimum-track solving.
- Equivalent-edition pruning prefers better-source fully duplicate editions; strict superset pruning ignores CD/WEB source rank. Late CD-log/DR changes may not increase physical track count or violate wanted recording/album constraints.
- The Release Map must preserve valid acoustic group ID `0` in all visible nodes, relationship links and alternate-version catalogs.
- A coverage/duplicate link does not prove a replacement. Show `↔ Replaced` only if one NEW release completely covers the included wanted acoustic groups of a removed OLD release and both are recognized as the same release family; otherwise report separate add/remove with actual partial coverage.
- Cache Release Map replacement pairing per state and invalidate it after updates. Do not rebuild every pair for every displayed row or filter.
- v0.3.6 remains `Under construction ⚠️` until exact Skrillex and Windows/WebView2 runtime testing pass.

## v0.3.5 source preservation and Release Map delta correction - authoritative

This section is HISTORICAL. Its per-recording hard source-floor requirement is superseded by the user's newest v0.4.9 complete-edition selection rule; keep the separate acoustic routing/Release Map fixes.

### CD / source quality preservation

- **Superseded v0.4.9:** Source preference breaks ties among complete-equivalent release solutions and is NOT a per-recording mandate to keep redundant physical releases.
- **Superseded v0.4.9:** A lower-source complete WEB Special Edition supersedes a higher-source CD subset when it contains the entire included wanted original plus wanted bonus tracks.
- **Superseded v0.4.9:** Do not keep an extra CD solely to preserve the source of shared audio already contained by the complete WEB edition.
- **Superseded v0.4.9:** An audio-proven same-album strict superset dominates its CD subset regardless of source rank, except the dedicated independently issued featured-remix singles exception.
- Among competing source-preservation candidates, prefer higher source rank, then better comparable CD-log quality, then Existing, then the smaller container/stable order.
- A below-threshold CD still follows the existing CD-log rules; this correction does not turn metadata into duplicate identity.
- Exact-equivalent Existing preference is based on proven included audio/container shape. Provider Album/EP/Single metadata disagreement alone must not create churn.

### Candidate-routing correction

- Same album + same track number/slot is a permitted **routing-only** safety path to acoustic comparison across releases.
- This is specifically intended for provider naming drift such as `Warped Tour '05 (ft. pete WENTZ)` vs `Warped Tour ’05 with pete WENTZ`.
- Album/slot metadata never proves identity. Chromaprint/audio acceptance remains mandatory.

### Changes view pairing and density

- When an OLD release is removed because one retained NEW release covers it, show that cause/effect as one **↔ Replaced** change whenever it is a replacement relationship. Do not force the user to correlate an unrelated-looking `+ Added` row with a separate `- Removed` row elsewhere.
- A true **+ Added** row must explain what new/unique wanted recording(s) it contributes when that information is available.
- Paired replacement-source OLD rows do not also count as independent Removed changes in the default Changes summary.
- Changes/Added/Replaced/Removed/Ignored views must size their scrollable content to their own visible rows. A stale Full-map SVG/board height must never create scrollable empty space.
- Full map uses compact line-separated release groups and compact line-separated rows; padded card-inside-card group containers are prohibited because they waste vertical space.

## v0.22.6 Release Map track-ignore and responsiveness correction

- Track-level `Ignore` / `Restore` is exact-instance only. It must affect only the clicked physical file or virtual CUE track.
- Acoustic-group identity, identical fingerprint, same base title, and same recording on another release must never cause a second track row to inherit the click.
- Legacy pre-v0.22.6 broad manual-skip rules based on fingerprint groups/base titles are not reapplied because their original physical target cannot be recovered safely.
- Ignore/Restore clicks update the visible row and dirty/Re-Analyze state immediately without rebuilding the complete Release Map or rerunning optimization.
- Expensive plan/map reconstruction happens on explicit `Re-Analyze`, not on every click.
- Full track titles in Release Map details wrap to multiple lines instead of permanent ellipsis truncation; the complete title is also available as a native hover tooltip.


## MCC v0.5.3 audio-equivalence, Unicode and remix-edit rules - authoritative

- **Full acoustic album equivalence is independent of track order.** If two album releases each contain at least five distinct wanted audio groups and the sets of all their included acoustic group IDs are identical, they are editions of one album family irrespective of track order or folder naming. Require proven fingerprint-derived recording groups, never metadata/title alone. Original/WEB or CD/rip quality and complete physical track counts then select exactly one optimal representative. For partial-overlap/different-content albums, preserve conservative LCS/order safeguards and all album-completeness/superset rules. The real INNA YO 2019 WEB11/CD11 permutation must select only the better-source CD when all 11 groups match.
- **Unicode/encoding safety:** Preserve Cyrillic and other non-Latin metadata for display and comparison. Repair validated UTF-8-encoded Cyrillic that was erroneously decoded as Windows-1252 (e.g. `Ð›ÑƒÑ‡ÑˆÐ¸Ðµ Ð¥Ð¸Ñ‚Ñ‹` -> `Лучшие Хиты`) *before* lossy NFKC or symbol replacement, and also repair earlier NFKC damage (the 0xB8 cedilla and 0xB5 micro-sign cases) where unambiguous. Do not change normal Cyrillic or ordinary Latin tags. Accent-fold the routing key so `Sí, Mamá` and `Si, Mama` can be acoustically compared. No textual normalization creates duplicate identity on its own.
- **Named remixer Radio/Club Edits:** In an explicitly labeled remix release, `Song (Beenie Becker Club Edit)` and `Song (Beenie Becker Radio Edit)` are remixes when the named remixer is corroborated by an ARTIST co-credit or an explicit multiword named descriptor. Exclude them immediately when Save Remixes is off unless a genuinely added, explicitly verified featured performer satisfies the narrow exception. Ordinary `Song (Radio Edit)` remains eligible. A remixer's own ARTIST credit never counts as a featured performer.
- **Testing:** Keep permanent real-log-shaped regression fixtures for the full reversed-order INNA YO equivalence, Unicode tags before/after NFKC, and both Beenie Becker edits; rerun genuine featured-remix exceptions and the full pre-existing suite.


## MCC v0.5.7 - album-family grouping (mandatory)

- Albums, regardless of release title, date, barcode and track order, belong to the same album family when their eligible fingerprint-proven acoustic group sets overlap by at least **80% of the smaller set**, with a minimum of four distinct smaller-set recordings and four shared groups. Do not automatically join albums when their known main artists differ. Link album families transitively.
- Album-family equivalence NEVER establishes track/acoustic duplicate identity. Preserve all unique audio groups, including distinct bonus tracks in overlapping editions, as mandatory wanted coverage. An album family may legitimately require retaining more than one edition.
- In the live editable Release Map, provide the clearly labeled Move to group choice and Restore automatic action, with source-path-based durable persistence in this application's own state/manual_album_groups.json. A manually moved source release detaches from its old automatically determined family; optimizer, dominance pruning and map must honor the same assignments.
- A manual grouping operation is metadata-only; it must never physically move or delete a release, and Copy/Move must remain disabled until explicit Re-Analyze. Avoid extra uncontrolled UI controls or disruption of the original Release Map/keyboard support.
- Include regression coverage for Hot 2005/2010/New Hot (11/11 and 9/11), Body and the Sun/Inna/Japan (14/15 and 13/15), transitive connections, unique bonus groups, unrelated lead artists, manual move and reset, saved path identity, and existing album-selection policies.


- **Manual grouping export lock:** A manual group state remains pending even if Ignore/Restore switches are toggled or toggled back. Release Map Copy/Move must not re-enable until the currently saved manual group mapping equals the reoptimized baseline or Re-Analyze explicitly updates the plan.


## MCC v0.5.9 - mandatory minimum-one-album invariant

- For every album family, the retained collection must include AT LEAST ONE eligible full album edition. The edition with the largest number of distinct tracks is NOT mandatory. Choosing the largest edition as an optimizer seed is allowed, but final retention MUST follow the at-least-one-album rule.
- Every wanted audio group must still be represented by at least one retained carrier. Unique alternate recordings and bonus tracks are protected by fingerprint-derived group coverage and must never be merged by names alone.
- A maximum-size Japanese/Deluxe album must be removed if all its eligible audio groups are already carried by other selected releases AND one other eligible album from the same family remains. Smaller album editions must not be pruned merely because a larger edition includes additional tracks that can be obtained elsewhere.
- Regression: 2026-10-12 INNA I Am the Club Rocker log ID 275 is selected redundantly beside album IDs 4 and 281; all 18 Japanese wanted tracks are already covered. No Limit exists on all versions, but the 2011 CD fingerprint comparison is below mastering threshold. That suspected audio false-negative is a separate investigation; it does not excuse retaining the redundant Japanese CD.


## MCC v0.5.10 - track-length distinctions and visible Versions

- Different known measured audio durations of at least 0.5s MUST be treated as different Versions and separate wanted recording groups. This is a negative identity veto only; equal durations do NOT establish a duplicate. Tolerate smaller differences as container/codec timestamp noise. Do not discard a valid longer Version merely because its shared fingerprint excerpt exactly matches the shorter edit, even when the remainder is digital silence.
- Apply the veto consistently to ordinary fingerprint comparison, fast exact-fingerprint matches, transitive acoustic group unions, and accepted manual reviews. Group duration minima and maxima must never exceed the threshold, even if A/B and B/C individually align.
- In the existing dark WebView2 Release Map, color-highlight the track's duration when another normal Version has a different known length and show an explicit Δseconds badge. Alternate Version entries must display their own duration and signed/absolute comparison delta. Do not mislabel or incorrectly save Live or Remix material when Save Live/Save Remixes are disabled.
- Preserve the per-track JSONL measured lengths, acceptance thresholds, rejection reasons and transitive-veto details. Keep duration-based candidate routing and audio evidence for positive identity.
- Include regression tests for identical Chromaprint vectors with >=0.5s duration difference, <0.5s encoder jitter, unknown length, 17.52s Fool Me variation, multi-edge transitivity, explicit manual review, and GUI version highlights. Do not claim stable until full Windows tests pass.


## MCC v0.5.11 - newest duration identity rule, overrides v0.5.10

- A duration difference of **EXACTLY 7.0 seconds or LESS is NOT a duration-based Version**, and must never, by itself, create an amber duration badge or force separation of an otherwise accepted acoustic match.
- ONLY a known measured audio-duration difference **STRICTLY GREATER THAN 7.0 seconds** creates a distinct length-based Version. The rule applies equally to fingerprint matching, fast identical-fingerprint paths, transitive acoustic-group boundaries, accepted manual review, comparison logs, and Release Map badges.
- The new positive-identity principle remains: matching or close duration alone NEVER proves that two recordings are duplicates. Acoustic matching still decides identity within the seven-second tolerance. A separate recording with incompatible audio may remain distinct even with identical length.
- Keep the UI free of amber duration-difference badges when all normal alternative versions have duration differences <=7 seconds. Do not alter Remix/Live exclusion behavior or overwrite other project requirements.
- Tests must explicitly distinguish 7.0s (allowed) from 7.01s (Version), plus 0.6s, 4.23s, 17.52s, identical fingerprints, transitive groups, missing duration and manual review.

