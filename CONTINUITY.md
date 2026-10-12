# Music Collection Cleaner - Continuity Handoff

Last updated: 2026-10-12
Status: **0.5.16 - Under construction ⚠️** (source migrated; Windows testing pending)


## Latest checkpoint - 2026-10-13, MCC v0.5.16 automatic default Copy/Move destination

- Source: `Music Collection Cleaner v0.5.16.pyw`, `karpuzikov/MCC/main`. **Under construction ⚠️**. Prior 0.5.15 remains available. No GitHub Actions workflow changes.
- User-reported bug: `Copy old + new releases into:` showed a supposed default destination, but **Copy old + new** remained disabled until clicking Browse and selecting an explicit path. Intended default destination is adjacent to NEW source as `<NEW source folder name> - UPDATED`; manual selection must not be necessary.
- Root cause in UI contract: existing `updateExportControls()` disabled buttons when its effective path was empty; missing `defaultExportDestination` state had no fallback. Python live map default derived only from `session.recycle` or computed `sourceRoots.recycle`; it now also checks NEW scan-root snapshots. JavaScript `defaultExportPath()` resolves explicit server default first, then `state.sourceRoots.recycle`, then the NEW node's `sourceRoot`. `selectedExportPath(mode)` always returns user-selected override when present or that default. All visible path/button/open/copy/move operations reuse the same function, preventing discrepancies.
- Copy and Move should be enabled immediately if and only if the Release Map is editable, the resolved destination is nonempty, Re-Analyze is not pending, and the plan is not blocked by integrity errors. Browse changes only the effective destination, not safety state. File operations still require confirmation; Copy remains non-destructive; no rename or folder deletion behavior changed.
- Added source-level UI self-test assertions. Executed the actual embedded JavaScript in an isolated V8 harness: **6/6** default-path/override cases, **4/4** Copy/Move enablement cases (ready, pending, missing root, read-only), and Copy click passed the calculated `D:\\INNA - UPDATED` to the backend without invoking Browse. These are non-GUI tests, **not** real Windows/WebView2 acceptance. Complete Python `--ui-self-test` not run. User should test open live Release Map after Analyze, verify automatic path shown and Copy active without browsing, choose another path, verify override; edit Ignore to force Re-Analyze and confirm Copy disabled until it completes. Cross-volume Move recovery remains a separate blocker.
- If symptom remains with nonempty displayed path, inspect `state.applyEnabled`, `state.dirty`, and `auditIssueCount`; these are independent safety gates and should not be silently bypassed.

## Latest checkpoint - 2026-10-12, MCC v0.5.15 INNA Fool Me replaceable Version optimization

- Canonical source: `Music Collection Cleaner v0.5.15.pyw`, `karpuzikov/MCC/main`. **Under construction ⚠️**. Prior v0.5.14 preserved. Changes affect optimizer coverage, snapshot/UI explanations and logged evidence; no workflows modified.
- User's two candidate albums: `2015-07-24 - Inna [5948204123093]` (ID 27), indispensable for other unique core tracks; `INNA – Body And The Sun [Japan] (2015) [FLAC]` (ID 287), selected alongside ID 27 in Re-Analyze 2026-10-12 23-58-29 audit. Japanese edition had four `Unique to this retained release` claims: Cola Song (matched standalone single ID 15), Take Me Higher (matched ID 19), Good Time (matched ID 16), and Fool Me (different-length audio).
- From v0.5.14 JSONL: Japanese Fool Me index 785 213.333333s vs INNA WEB Fool Me index 163 195.805556s (and Body and the Sun WEB index 146, same audio as index 163): delta 17.527777s; strict/mastering positive acoustic statistics score 4.509301, good .944836, excellent .708146, overlap .999359, median 4, p90 9, acoustic coverage .915981. Hard >8s rule and non-silent unmatched content correctly rejected **exact duplicate** identity. This different-length edit can nevertheless be **substitutable for COLLECTION COVERAGE**, per user's requested Japanese edition removal. Keep actual group IDs separate.
- Additional matching examples: `Cola Song` index 782 vs single 114 is MATCH, `Take Me Higher` 794 vs single 119 MATCH, `Good Time` 795 vs single 115 MATCH. With Japan blocked, the 23-58-10 audit shows these three singles selected and Japanese Fool Me only missing. With Japan restored, 23-58-29 audit selects Japan + Inna and drops singles. Desired result: keep Inna and three singles, not Japanese, unless some other truly unique content is shown after a new full analysis.
- Implementation: Track now includes planning-only `coverage_group_id`. `merge_equivalent_tracks` still assigns physical/acoustic `group_id` under 8s rule, then analyzes rejected length-edit pairs using title, primary artist, semantic root family, strong Chromaprint acceptance and ≥90% aligned acoustic coverage. `_assign_replaceable_version_coverage` sets effective provider groups without mutating actual group IDs, so exact optimizer and Release Map unique coverage both use substitional obligation; original acoustic version distinction stays visible. `replaceable_version_coverage` JSONL rows audit the two true matched Fool Me candidates. The UI flags and labels source as an alternate version.
- Offline read of full user comparison: **127** same-title/artist duration-version-rejected candidate pairs, only **2** meet the strict source-data score/good/overlap/excellent/median/p90/coverage filters, both Fool Me index 785 vs 146/163. New synthetic self-test models Fool Me substitution and a miniature core album + independent single coverage, plus no title-only/extended/weak-audio false positives. This is a regression contract, not a Windows test claim.
- **Next required:** run `Music Collection Cleaner v0.5.15.pyw` for a full INNA OLD+NEW comparison, inspect whether Japanese edition is removed and Inna plus 2014 singles are retained. The 8s version boundary remains unchanged. Re-Analyze alone cannot rebuild version substitutability. Upload new comparison and Re-Analyze audit if result disagrees.
- Validation remaining: full Python compile, --ui-self-test, actual Windows GUI, drag/keyboard/hover, copy/move/undo, cross-volume recovery all NOT RUN. Keep status **Under construction ⚠️**; no GitHub Actions modifications.

## Latest checkpoint - 2026-10-12, MCC v0.5.14 duration threshold 8 seconds

- User explicitly requests 8-second threshold instead of 7. **Supersedes the earlier v0.5.11 strict >7-second rule**, while preserving it as historical documentation.
- Canonical source: `Music Collection Cleaner v0.5.14.pyw` in `karpuzikov/MCC` (`main`); previous version retained. The app constant is 0.5.14 and its status remains **Under construction ⚠️**.
- Effective rule: known measured total duration delta **≤8.0 seconds** is NOT by itself a different Version; **>8.0 seconds** is. Acoustic evidence still required to merge. Shared `DURATION_VERSION_MAX_SAME_SECONDS` changed from 7.0 to 8.0. WebView2 `versionLengthDelta` highlights only delta >8.0000001 seconds. Fingerprint matcher, exact-match fast path, group-diameter bounds, deterministic coherent-duration partitions, manual merges, log decision threshold and UI are aligned.
- Existing INNA Hot log-shaped synthetic regressions adapted: the 210.306667s Days Nights copy differs from 202.812993s by ~7.494s, and 313.293333s Ladies differs from 306.033175s by ~7.260s, so both are **inside** the new 8s window and may join their otherwise acoustically supported component. Keep acoustic graph connectivity and deterministic grouping.
- Regression boundary expectations changed: exactly 8.0s = allowed when audio matches; 8.01s = distinct Version. Tests check direct fingerprints, transitive group veto, synthetic Hot comparisons, and manual review. No unverified assertions of completed execution.
- **Important:** Re-Analyze alone does not rebuild old acoustic groups; Windows user must start an entirely new scan of both source pools to apply this threshold.
- GitHub source written/read back; static source checks only. Python compilation, `--ui-self-test`, actual Windows/WebView2 scan, Copy/Move and Undo **NOT RUN**. Keep `Under construction ⚠️`. No Actions edits.

## Latest checkpoint - 2026-10-12, MCC v0.5.13 Hot edition acoustic transitivity fix

- Canonical GitHub source: `Music Collection Cleaner v0.5.13.pyw` on `karpuzikov/MCC/main`, **Under construction ⚠️**. v0.5.12 remains archived. No GitHub Actions workflow changes.
- User provided comparison `Music Collection Cleaner Comparison 2026-10-12-22-08-12.jsonl` (MCC v0.5.12) plus Re-Analyze audit files ending `22-33-16-546527` and `22-33-29-669838`. After ignoring `2005-07-01 - Hot [191018194277]`, `2005-07-01 - Hot [5037128001775]`, and `Inna - New Hot Edition (2010)`, both `2005-07-01 - Hot [5948204431396]` (ID 2) and `2010 - Hot [RDM110]` (ID 274) were retained, each displaying `Ladies` and `Nights & Days / Days Nights` as allegedly unique.
- **Confirmed from raw logged acoustic comparisons:** ID 2 track 33 `Ladies` 306.033175s vs ID 274 track 644 `Ladies` 307.280000s: `audio_match=true`, good_fraction=1.0, overlap=1.0, score=1.766939, duration delta=1.246825 seconds. ID 2 track 29 `Nights & Days` 206.511678s vs ID 274 track 646 `Days Nights` 202.813333s: `audio_match=true`, good_fraction=1.0, overlap=1.0, score=2.021027, duration delta=3.698345 seconds. Both had `decision=REJECT` and `transitive_duration_version_conflict=true`. Thus NOT an audio fingerprint threshold or a title-spelling problem.
- Root cause: online union of acoustic groups enforced a max-min length window of 7s; different tracks on `Inna - Hot (2009)` (e.g. Ladies 313.293333s and Days Nights 210.306667s) bridged otherwise valid editions, and worker-completion order could vary. The exact same recorded pairs can be split only because other acoustic links were processed earlier. Keep >7.0 seconds a hard version separation; do not merge by title/length alone.
- Implemented `_coherent_duration_audio_groups`: collect all positively fingerprint-matched candidate pairs; build connected acoustic components; dynamic-program over duration-sorted intervals of width ≤7.0 seconds; require internal acoustic graph connectivity; lexicographically minimize group count, maximize real within-group fingerprint matches then group size, with deterministic tie-breaking. No worker-order unions. Unknown duration fallback conservative. After partition, log final `comparison` matches/vetoes plus `grouping_policy` marker rather than premature decisions.
- Offline Python replay of **the actual uploaded match/veto edges** verified that Hot track indices 29/646 and 33/644 join, while >7s outlier 676 (Days Nights 210.306667) and 682 (Ladies 313.293333) do not join the shorter variants. Synthetic regression cases for both bridges and strict 7.0/7.01s rule added to `--ui-self-test`. Real application self-tests and Windows GUI not executed.
- **Next action:** Download v0.5.13, perform a brand-new full scan of the same INNA OLD+NEW folders (Re-Analyze alone cannot recompute stored fingerprint groups), then repeat the ignore list, inspect both Hot album track details, and provide the fresh comparison + Re-Analyze logs if an unexpected duplicate remains. Do not conclude that an album will automatically be removed until entire track coverage/album-family constraints are recalculated. Persisted ignored releases remain active by physical path. Retain existing dark WebView2 UI and no GitHub Actions changes.

## Latest checkpoint - 2026-10-12, v0.5.12 Re-Analyze audit and saved release Ignore

- Canonical source: `Music Collection Cleaner v0.5.12.pyw` (GitHub `karpuzikov/MCC`, `main`), previous versions retained. Versioned filename and app constant both 0.5.12.
- User's `Music Collection Cleaner Comparison 2026-10-12-20-53-24.jsonl` is **v0.5.11 INITIAL ANALYSIS**, not the Re-Analyze result. One `optimizer` record shows `blocked_releases=0`. Releases `2011-09-16 - I Am the Club Rocker [5948204467029]` (ID 4) and `2019-05-30 - The Best of INNA [4741534637626]` (ID 74) were selected before they were manually ignored. RuTracker `Inna - I Am The Club Rocker (2011)` (ID 280) was not selected; `Inna - I Am The Club Rocker (2011) CD` (ID 281) was selected. The two No Limit tracks were REJECT at score ~4.70073 and good-frame ~0.745742, versus a stricter ~0.80 mastering threshold, notwithstanding both lengths = 206.24s. Thus acoustic matching may distinguish alternative mastering; **never merge by title/duration alone**. The original log cannot establish post-ignore optimization decisions.
- Re-Analyze originally ran `optimize_collection(releases,groups,blocked_ids)` and rebuilt decisions/snapshots, but it did **not** append optimizer/comparison results; a new full analysis restarted with `blocked_release_ids=set()`. v0.5.12 fixes both defects.
- At successful Re-Analyze, save ignored **physical release paths** (not temporary IDs) to isolated `Documents/Karpuzikov Tools/Music Collection Cleaner/state/manual_ignored_releases.json`. Pending Ignore/Restore is not saved until Re-Analyze. Full scans apply stored ignores in the initial optimizer, including the manual-review path, with no wasteful second optimizer pass; this preserves fingerprint comparisons among excluded and eligible sources during group construction.
- A full independent planning audit is saved after Re-Analyze: `state/last_reanalysis_audit.json` and timestamped `logs/Music Collection Cleaner Re-Analyze *.jsonl`. It includes blocked IDs/names, prior and current selected IDs, all release actions/reasons, missing replacement sources, and `acoustic_comparisons_repeated=false`. When initial comparison logging is enabled, Re-Analyze also appends an optimizer row and reanalysis event to that original comparison JSONL; never relabel planning as full fingerprint recomparison. Dark Release Map adds **Open audit log** in the result drawer, preserving existing layout.
- Safety gate: assert that a blocked release is never in the Re-Analyze selection, and also validate saved ignores after fresh optimization. Added isolated on-disk persistence/audit regression into `--ui-self-test`. `CONTINUITY.md` and `README.md` updated; global rules are mirrored; no GitHub Actions edits.
- **Validation:** GitHub source written/read back; source-level checks performed. **Python compilation, built-in `--ui-self-test`, end-to-end Windows/WebView2 Ignore > Re-Analyze > close > rescan > Copy/Move/Undo are NOT RUN**; do not call it stable. Known cross-volume Move cleanup blocker remains. Next: run on a copy of the INNA pools, ignore the two named Deezer releases, click Re-Analyze, inspect both retained RuTracker CDs and the new audit file; test reopening/reanalyzing and restart persistence. If both stay, examine per-track No Limit coverage before changing acoustic threshold.

## Latest checkpoint - 2026-10-12, v0.5.11 strict >7s length rule

- User explicitly rejected the v0.5.10 clutter: tracks of length 3:33, 3:38, 3:20 and 3:15 carried unwanted tiny Δ0.7s / Δ0.8s / Δ2.3s / Δ0.6s badges. New immutable requirement: "ONLY IF DIFFERENCE MORE THAN 7 SECONDS, 7 SECONDS AND LESS IS THE SAME SONG."
- Current source **Music Collection Cleaner v0.5.11.pyw** in **karpuzikov/MCC/main**. Switched the common threshold constant to DURATION_VERSION_MAX_SAME_SECONDS = 7.0 and use strict >7.0s (+tiny numeric float tolerance) in both _duration_version_conflict and _duration_group_union; changed Release Map JavaScript versionLengthDelta to >7.0000001. No new UI added.
- Consequences: <=7 seconds **never creates a length-based badge or vetoes a valid acoustic duplicate**, including exactly 7.0 seconds; >7 seconds is a distinct length Version, including exact fingerprint matches. Unknown lengths do not force a version split. Equal/close durations are NOT sufficient by themselves to merge dissimilar audio; Chromaprint must still support duplicate identity.
- Added built-in --ui-self-test regression for differences [0, 0.6, 4.23, 7] accepted, [7.01, 17.52] separated, duration boundary with identical Chromaprint vectors and A/B/C transitive range exactly 7 versus >7.
- GitHub new source publication succeeded. Python compilation, embedded self-test and real Windows/WebView2 collection rerun have **not** been executed. UI JavaScript syntax and repository source checks should be confirmed; do not mark stable. Cross-volume Move remains under construction. No Actions workflows modified.

## Latest checkpoint - 2026-10-12, v0.5.10 length-based Versions and UI

- User requested: "make mcc highlight differences in length so i'm not siting and guessing is it duplicate or not. if there is a length difference it should count as a version". Overrides previous audio-only/metadata-duration-is-diagnostic policy: a significant track length difference is negative identity evidence, even when overlapping audio fingerprint looks the same.
- New canonical source: Music Collection Cleaner v0.5.11.pyw in karpuzikov/MCC/main. Added DURATION_VERSION_MIN_DELTA_SECONDS = 0.5 to tolerate subsecond metadata/encoder timestamp jitter; when both durations are known and delta >= 0.5s, fingerprint_auto_match_values returns not-matched with similarity metrics retained for logging. Also handle_result enforces the veto on fast exact-vector path.
- Added duration-aware UnionFind _duration_group_union with group min/max bounds to prevent transitive A(200.0)/B(200.4)/C(200.8) audio-match chains from merging A+C as one recording. apply_manual_review_merges also uses this guard, preventing manual match approvals from re-merging length variants.
- Release Map existing dark WebView2 track detail durations are highlighted amber when a different-length Version exists; display ΔXs badge beside the source duration and matching delta in alternative Version list. Added raw durationSeconds for snapshot and versionFamilies UI payload; true alternative Versions remain separate recording groups and are not marked duplicates. Track distinction reason now explicitly mentions both measured lengths and delta rather than claiming duration is diagnostic only.
- Comparison JSONL includes duration_version_conflict, duration_version_threshold_seconds, duration_difference_seconds, transitive_duration_version_conflict and rejection explanations; logging header reports duration_used_for_identity=true. The older duration_delta_seconds_diagnostic_only field remains for backward log readers.
- Synthetic --ui-self-test coverage now checks 0.5s threshold, 17.52s Fool Me delta, exact fingerprint but distinct length, missing duration fallback, transitive group prevention, manual review veto and Release Map UI strings.
- This is **Under construction ⚠️**: no full-source Python compilation, no --ui-self-test execution, and no real Windows run yet verified. Re-analyze the same INNA pools (saved old snapshots will not retroactively split audio groups); verify No Limit and Fool Me durations in Release Map. Cross-volume Move cleanup remains an independent blocker; no Actions workflows modified.

## Latest checkpoint - 2026-10-12, MCC v0.5.9

- User corrected the album requirement: at least ONE album release per family is enough, not the most-complete album. The prior maximum-completeness rule wrongly forced extra CD retention.
- Exact user log Music Collection Cleaner Comparison 2026-10-12-20-01-24.jsonl (MCC 0.5.8): selected 2011 WEB release ID 4, Japanese CD release ID 275, and normal 2011 CD release ID 281. **All 18 eligible tracks in Japanese CD ID 275 have carriers in the selected set excluding ID 275**; it is redundant. Two other same-family albums are already retained.
- No Limit exists on EVERY album (including IDs 4, 275, 281). Japanese CD 275 vs 2011 CD 281 comparison: approximately 100% overlap and acoustic coverage, score 5.292757, good_fraction 0.745587; REJECT because stricter good fraction 0.80 criterion not met. Japan No Limit 275 versus WEB 4 MATCH. No Limit 281 may be false-negative matching or alternate mastering; not evidence of absent recording. Do not merge by title/duration alone.
- Current source Music Collection Cleaner v0.5.11.pyw in karpuzikov/MCC main. The exact-global album provider requirement now includes ANY eligible album edition in each family. The final prune protects only the LAST album, not the last most-complete one. Strict subset album domination is applied only when a superset has a mandatory exclusive extra group, preserving smaller albums when missing tracks have independent regular carriers.
- Added real-log-shaped Club Rocker synthetic regression: 2011 WEB carries uniquely short edits, normal 2011 CD carries a separately detected No Limit, Japanese CD's 15 eligible modeled groups are all covered by WEB/CD + other regular release. Expect WEB + 2011 CD + separate carrier, no Japanese CD; without that carrier Japanese bonus content forces it back.
- Previous Starboy, Cross the Line, manual grouping, WebView2 and 80% album-family logic preserved as source contracts. Windows execution and Python --ui-self-test still NOT performed on v0.5.9. Status 0.5.9 - Under construction ⚠️. Known cross-volume Move cleanup blocker still open. Do not modify GitHub Actions.

## Latest checkpoint - 2026-10-12, v0.5.8 Re-Analyze gate correction

- Current canonical version is Music Collection Cleaner v0.5.11.pyw in karpuzikov/MCC main. This supersedes intermediary v0.5.4 through v0.5.7 from today's work, which remain historic versioned source files.
- A manual group move was persisted correctly, but later Ignore/Restore toggle could clear the dirty state if no track/release ignores remained, allowing Copy/Move before re-optimization. Fixed: ReleaseMapBridge tracks the initial manual album-group mapping, includes all differences in _refresh_pending_state, and refreshes this baseline only after Re-Analyze. Returning to the original mapping can safely clear pending state. Added source-level self-test contract for this safety gate.
- Actual Windows execution and complete Python self-test have NOT been performed. Do not mark stable; only GitHub source/readback and log-derived overlap math are verified. Re-run the same v0.5.3 INNA collection with v0.5.8 and test automatic group membership, manual move/reset, the pending gate with Ignore/Restore toggling, persistence and full Copy/Move/Undo on disposable folders. Cross-volume Move recovery remains a known blocker.

## Latest checkpoint - 2026-10-12, v0.5.7 automatic and manual album families

- The user-supplied Music Collection Cleaner Comparison 2026-10-12-11-48-21.jsonl identifies MCC v0.5.3. The 800-track scan found 530 eligible tracks, 241 acoustic groups, 105 selected releases. Source-level regression shapes for v0.5.7 were derived from the actual MATCH pairs.
- Album group Hot: 2005-07-01 - Hot [5037128001775] (ID 1, WEB, 12 eligible groups), 2010 - Hot [RDM110] (ID 274, CD, 11 eligible groups), Inna - New Hot Edition (2010) (ID 283, CD, 13 wanted groups in 14 physical tracks). Audio group overlaps 11/11 (100%) between WEB and CD; 9/11 (81.8%) between CD and New Hot. The direct WEB/New Hot overlap is 9/12 (75%), so transitive album-family grouping is necessary.
- Album group Body and the Sun/Inna: 2015-07-24 - Body and the Sun [5948204067694] (ID 26, WEB, 15 wanted), 2015-07-24 - Inna [5948204123093] (ID 27, WEB, 19 wanted), INNA – Body And The Sun [Japan] (2015) [FLAC] (ID 289, CD, 18 eligible from 19 files). Overlap 14/15 (93.3%) between Body and Inna and 13/15 (86.7%) between Body and Japan. Direct Inna/Japan 14/18 (77.8%) is below threshold; transitive bridge joins three.
- The user requested automatic same-album detection using 80% track overlap and previously asked for manual moving between release groups. Both features are implemented in **Music Collection Cleaner v0.5.11.pyw**, GitHub karpuzikov/MCC main.
- Algorithm: _album_editions_related_by_audio requires >=80% of smaller distinct fingerprint-proven eligible acoustic group set, min 4 shared groups, and compatible majority primary artist. No album names, barcode or track order are required; _album_clusters applies transitive links. Distinct bonus tracks remain separate required acoustic groups in the exact optimizer, so one family can still require several physical editions.
- Persistent manual override: Release Map live details have a destination group select, Move to group, and Restore automatic; WebView2 bridge setAlbumGroup updates source release path -> target release path in Documents/Karpuzikov Tools/Music Collection Cleaner/state/manual_album_groups.json with atomic writes. Manual source detaches from its auto family; both visual grouping and optimizer constraints consume the same group membership; dominance pruning respects a manual separation. Changes disable Apply until explicit Re-Analyze. Stored paths survive rescan with unchanged directory paths. Snapshot-only Release Map remains read-only, and no drag-and-drop implemented.
- Built-in --ui-self-test extended with synthetic 3-edition Hot and Inna/Body/Japan clusters, unrelated lead-artist nonmatching, unique bonus coverage, manual detach/restore and visual/bridge contracts, and dominance safety. No v0.5.7 full Python compilation, built-in self-test execution, or actual Windows scan/UI test yet. DO NOT call the build stable or claim actual optimizer selection on this log. Cross-volume Move recovery remains a blocker.
- Next Windows test: rerun the same INNA collection using v0.5.7. Confirm Hot three editions render as a group, Body and the Sun/Inna/Japan render as another, and inspect retained vs unique group explanations. Test manual grouping, Restore automatic, app restart persistence, and explicit Re-Analyze before Copy; test only on disposable files.

## Latest checkpoint - 2026-10-12, v0.5.3 real INNA log fixes

- User supplied `Music Collection Cleaner Comparison 2026-10-12-10-38-26(1).jsonl`; run identifies itself as MCC **v0.5.0**, NOT a v0.5.2 rerun. Both `2019-05-31 - YO [810760037075]` (release ID 75, WEB, 11 files) and `Inna - YO 2019` (release ID 293, CD, 11 files) are selected. Ten explicit cross-release acoustic MATCH rows and two MATCH rows via a common third track establish their **identical 11-group sets**, but physical order differs: WEB track order [RA, Te Vas, Iguana, La Vida, Locura, Sí Mamá, Sin Ti, Tu Manera, Gitana, Contigo, Fuego], CD order [Te Vas, Tu Manera, Sin Ti, Locura, Fuego, RA, Iguana, Si Mama, Contigo, Gitana, La Vida]. LCS of permutations is only 4 of 11, below the previous album-cluster threshold (7), so the solver treats them as two album obligations and keeps both. Fixed in v0.5.3: full same-set acoustic albums group regardless of order; partial-content overlap still uses LCS.
- The same log includes album tag `Ð›ÑƒÑ‡ÑˆÐ ̧Ðμ Ð¥Ð ̧Ñ‚Ñ‹`, from original `Лучшие Хиты` corrupted by Windows-1252 mojibake then NFKC (SPACE+COMBINING CEDILLA and Greek mu). Updated `repair_mojibake` to restore valid UTF-8 Cyrillic before normalization, including historical NFKC corruption. Updated `normalize_title` to fold Latin accents (`Sí, Mamá` / `Si, Mama`) without dropping non-Latin letters. Never use textual title equality alone to merge recordings.
- Wow `2012-04-26 - Wow (Remixes) [5948204365790]`, release 5, has two misclassified regular tracks: `Wow (Beenie Becker Club Edit)`, track index 73, and `Wow (Beenie Becker Radio Edit)`, track 74, both credited `Inna;Beenie Becker`. Added remix-release-scoped named child-edit recognition to `_contextual_remix_track_ids`; v0.5.2's named remixer-feature guard then correctly eliminates both under Save Remixes OFF. Generic uncredited `Wow (Radio Edit)` remains regular.
- Published **`Music Collection Cleaner v0.5.11.pyw`** in `karpuzikov/MCC`, `main`. Added synthetic `--ui-self-test` fixtures for YO reordered 11-track albums, mojibake before/after NFKC, Cyrillic preservation, accent folding, Wow Beenie Becker edits and generic Radio Edit non-remix. No actual Windows v0.5.3 run or full Python compilation/self-test completed in this checkpoint. The latest uploaded log is *v0.5.0*, so **actual new selection still unverified**. Existing cross-volume Move journaling blocker remains. No new Actions workflows, no EXE; preserve entire WebView2 UI and previous source code.
- Next: run `Music Collection Cleaner v0.5.11.pyw` on exact unchanged INNA pools with Save Remixes OFF and capture new JSONL. Expect only CD `Inna - YO 2019` of the two YO editions, repaired `Лучшие Хиты` metadata, and both Beenie Becker edits eliminated at the first remix filter. Check Gimme Gimme/Starboy/other edition rules for regressions and Windows Copy/Move/Undo separately.

## Latest checkpoint - 2026-10-12, v0.5.2 remix-feature policy fix

- User supplied real MCC **v0.5.0** `Music Collection Cleaner Comparison 2026-10-12-10-38-26.jsonl` (872 total tracks, 712 eligible, 151 featured-remix exceptions). INNA release **2017-06-15 - Gimme Gimme (Remixes) [190295779481]**, release ID 45, was selected with Save Remixes OFF; of 11 tracks, **9 named remixes** were wrongly retained as 'added-feature exceptions' because `ARTIST` tags named remix producers (e.g. `Inna;Sak Noel`, `Inna;Ness`, `Inna;Dj Dark;MD DJ`). The Mert Hakan & Ilkay Sencan Remix had already been excluded. Root cause: `configure_exclusions` promoted `_artist_tag_collaborators` to featured performers even where track title established a named remixer.
- **Current source** `Music Collection Cleaner v0.5.11.pyw` avoids interpreting artist-tag collaborators as added features for explicitly named remixes and contextual remixer edit/club variants; it only accepts explicit feat./ft. credits in such cases, while retaining the generic Remix + demonstrably added feature policy. Added built-in `--ui-self-test` fixtures for all 10 Gimme remixes, JRMX contextual Dub/Club and a genuine remix-added `feat.` after named remix. v0.5.1 was a short intermediate development checkpoint; v0.5.2 supersedes it.
- The same release contains one non-remix **Gimme Gimme (Extended Version)**, ~245.455s versus original ~176.827s (not an acoustic MATCH). The extended recording also appears on release ID 41, `2017-02-01 - Gimme Gimme (The Remixes) [5948204157593]`, with an acoustic MATCH against ID 45. It is wanted under current rules, so MCC may still retain ONE remix-named package as its only carrier; do **not** promise ID 45 must disappear until the solver is rerun and the wanted Extended Version is accounted for.
- Source published in `karpuzikov/MCC`, main, WebView2 preserved, v0.5.2 Under construction ⚠️. Real Windows v0.5.2 rerun, Python full-module compilation, built-in self-tests and optimizer selection with the user's actual data **remain unverified**; do not mark stable. Old DEA reference project remains untouched.
- Exact next check: run v0.5.2 on the **same OLD/NEW INNA collection** with Save Remixes disabled; new JSONL must show 9 previously erroneous named remixes excluded from wanted coverage, while the Extended Version remains eligible, and no other remix false positives remain. Also test Starboy/Weeknd true newly featured cases, Copy/Move/Undo and all previous blockers.

## Current product and canonical repository

- Product: **Music Collection Cleaner** (MCC); repository: `karpuzikov/MCC`, branch `main`.
- Canonical new source: `Music Collection Cleaner v0.5.2.pyw` (WebView2/pywebview, original analyzer logic and interactive Release Map preserved).
- Inherits behavior and rules from `karpuzikov/userscripts`, branch `dea-lightweight-modern`, v0.4.9. Root `RULES.md` is the original complete project rulebook; root `SOFTWARE_RULES.md` is the exact canonical global mirror.
- Separate original production tool `Duplicate Edition Analyzer v0.22.12.pyw` remains **untouched** in `karpuzikov/userscripts`; legacy branch files remain available for reference.
- Version remains `Under construction ⚠️` until Windows testing. Neither a Windows EXE nor a stable release is claimed.
- Data root: redirected `Documents\\Karpuzikov Tools\\Music Collection Cleaner` with first-run non-destructive copy of old analyzer settings/state/cache/logs from `Documents\\Karpuzikov Tools\\Duplicate Edition Analyzer` (new data is isolated; old program retains its own data).
- GitHub updater points to `karpuzikov/MCC` and MCC-only release tags; historic DEA release assets in `userscripts` must never be altered by MCC.
- **Known release blocker:** Cross-volume Move can publish a verified destination but then fail partway through removing the source, leaving its Undo journal incomplete. This must be addressed and verified before marking safe/stable or recommending cross-volume Move. Existing copies and same-volume Move still require real Windows verification.
- Required regressions still unverified in Windows: Camo & Krooked **Cross the Line** original 14 vs Special Edition 18; Starboy CD + bonus remix singles vs Deluxe; Bangarang CD7 vs WEB8; Skrillex data; Copy/Move/Undo, collisions, exception recovery, worker/drive detection and orphan processes. Source-level `--ui-self-test` is available but is not equivalent to a Windows run.
- No new or modified GitHub Actions workflows were authorized. Preserve the full dark WebView2 UI, Release Map SVG links, drag/drop, Personal Picks, logging, sound analysis and explicit Apply / Undo semantics.

## Historical development continuity (from original DEA project)

The complete historical handoff below is kept verbatim as a reference for all prior behavior contracts and regressions. Any stale project path/version in this historical section is superseded by the **Current product and canonical repository** section above.

---

# Duplicate Edition Analyzer - Continuity Handoff

Last updated: 2026-10-09
Status: Under construction ⚠️

## Purpose

Duplicate Edition Analyzer (DEA) compares an existing discography with incoming/new releases, identifies exact acoustic duplicates and distinct versions, optimizes which releases should be retained, lets the user inspect and override the proposed plan in Release Map, and only changes files after explicit Apply. Undo must remain available after applying changes.

This file is the authoritative handoff for DEA development. Read it before changing DEA. Update it whenever implementation state, versions, behavior, architecture, build flow, known issues, or next steps change.

## Canonical implementations and versions

- Production/reference implementation:
  - Source: `audio-tools/discography-torrent-project/tools/Duplicate Edition Analyzer v0.22.12.pyw`
  - Version: `0.22.12 - Under construction ⚠️`
  - GitHub release asset: `Duplicate.Edition.Analyzer.0.22.12.exe`
  - This is the current functional specification for all replacement/rewrite work.
- Failed native prototype:
  - Branch: `dea-native-light-test`
  - Source root: `audio-tools/discography-torrent-project/native-light/`
  - Last prototype version: `0.1.2`
  - User tested it and rejected it because it did not preserve 100% of regular DEA functionality.
  - Do not use the native prototype as the functional specification.
- New lightweight/fast/modern rewrite:
  - Branch: `dea-lightweight-modern`
  - Source: `audio-tools/discography-torrent-project/lightweight/Duplicate Edition Analyzer Lightweight v0.4.9.pyw`
  - Version: `0.4.9 - Under construction ⚠️`
  - Separate from the failed native prototype.
  - Functional baseline is production/reference DEA 0.22.12.
  - No production feature may disappear merely to reduce EXE size or complexity.

## Non-negotiable rewrite contract

The new lightweight implementation must provide 100% user-visible and behavioral functionality of the regular DEA before it can replace or be presented as equivalent to the regular version.

Parity means:
- same analysis behavior and selection rules;
- same pre-analysis unusual-pattern review behavior;
- same Personal Picks behavior;
- same Save Remixes / Save Live behavior and exceptions;
- same acoustic duplicate identity behavior;
- same Release Map information, links/connections and interaction model;
- same track/release ignore, restore and Re-Analyze behavior;
- same Apply/Undo behavior;
- same search, track highlighting and cross-release navigation;
- same Versions/Remixes/Live family inspection;
- same replacement-source explanations;
- same result/change summary behavior;
- same filesystem path open controls;
- same logging, crash reporting and persistent settings behavior;
- same dependency behavior or a stricter compatible implementation;
- same versioned-download and GitHub status rules.

No feature may be removed, stubbed, hidden, or replaced with a simplified approximation unless the user explicitly approves that exact change.

## Why the old native prototype failed

The Win32/C++ prototype was small and fast, but it simplified the product and therefore violated the parity requirement. Specific missing/incomplete areas included:
- Release Map was a simplified list/details window rather than the full graph-style chronological release board.
- Missing/insufficient visual relationship links/connections on the map.
- Missing full cross-release track highlighting/navigation.
- Missing full Versions / Remixes / Live alternative-family panels and navigation.
- Missing full replacement-source and retained-copy detail behavior.
- Missing the complete regular Release Map search/navigation behavior.
- Missing or simplified result drawer / IF -> THEN re-analysis explanation flow.
- Missing the full regular UI/interaction richness and several parity behaviors around ignore/restore/re-analysis.
- Its engine also diverged from the production Python behavior instead of sharing the exact production logic.

Do not repeat this approach by implementing a smaller subset first and calling it equivalent.

## Target architecture for the new lightweight implementation

Preferred direction as of 2026-10-07:
- Preserve the production Python analysis/optimization logic as the behavioral authority rather than manually reimplementing the algorithms in C++.
- Remove the heavyweight PySide6 + Qt WebEngine runtime from the application UI.
- Use the Microsoft Edge WebView2 runtime for the modern HTML/CSS/JavaScript UI. Microsoft documents the Evergreen WebView2 runtime as preinstalled on Windows 11 and automatically updated; the program must still detect/runtime-check it and bootstrap/install it when unavailable.
- Keep the existing modern DEA HTML/CSS/JavaScript interaction design as the starting point, especially the full Release Map, and adapt the host bridge rather than rewriting/reducing the map.
- Keep long-running analysis off the UI thread.
- Prefer one user-facing EXE; runtime dependencies may live under the program-owned dependency directory if required by the global software rules.
- Do not bundle a 100-250+ MB fixed WebView2 runtime when the Evergreen runtime is available.
- Do not bundle Qt/PySide6 in the lightweight build.
- External audio helpers follow the global dependency rules and live under the program-owned data/dependencies path when app-local copies are required. The lightweight frozen build resolves FFmpeg/FFprobe and fpcalc externally at runtime instead of requiring them inside the EXE.

Reason for this architecture: it preserves the exact proven Python decision engine while removing the largest UI/runtime weight source and retaining a modern web-rendered Release Map.

## Current production UI behavior that must be preserved

### Main window
- Modern dark UI.
- Existing discography path is optional.
- New / update releases path is required.
- Folder/open-location button immediately before every displayed path.
- Save Remixes.
- Save Live recordings.
- Personal Picks.
- Logging and logs-folder opener.
- Match label: Chromaprint (audio only).
- Current stage, progress percent/bar, processed/total count and elapsed time.
- Activity/log panel.
- Analyze.
- Undo last run.
- Release Map.
- Close.
- Analysis and export are separate; analysis never modifies either source folder. Copy actions in Release Map create curated output copies only.

### Unusual track pattern review
- Only genuinely unknown/non-standard version-like patterns are reviewed.
- Ordinary known Remix/Live/Radio/Extended/Acoustic/Instrumental/Acapella/etc. structures do not appear as unusual patterns.
- Callout aliases are one semantic pattern:
  - Suggested Callout Hook
  - Call Out Hook
  - Suggested Call Out Research Hook
  - all resolve to the stable key `suggested callout` and one UI row, currently labeled `Callout hook`.
- Only unresolved unusual patterns appear in this review. A Pattern already saved in Personal Picks is a resolved persistent keep decision and must not be shown or re-confirmed on later analyses.
- Checked unusual pattern is kept and saved to Personal Picks.
- Unchecked pattern is skipped for that run.
- Removing a Pattern from Personal Picks makes it eligible for review again if that pattern is encountered later.
- Check all / Uncheck all / Cancel / Continue behavior is preserved.

### Personal Picks
- Supports Phrase, Exact title and Pattern entries.
- Pattern entries remain persistent until removed.
- Pattern rules are not treated as normal phrase matching.
- Personal Picks must never resurrect a globally disabled Remix or Live category.
- UI supports add/remove, clear, copy all, save/cancel.

### Acoustic identity and classification
- Chromaprint acoustic evidence is the duplicate-identity authority.
- External database identifiers are not duplicate-identity authority.
- Duration is candidate routing/diagnostic evidence, not identity authority.
- Definitive exact acoustic match is automatic; no manual identity choice for the proven same recording case.
- Weak/near-threshold non-match stays separate automatically.
- Fingerprint failures remain conservative singleton/unique recordings.
- CUE image rips are recognized as virtual tracks.
- Explicit supersedes corresponding Clean before fingerprint grouping.
- Remix, Live, Extended, Instrumental, Acapella/A Cappella and Acoustic root/version semantics must retain the production rules.
- Radio/Edit-style variants remain acoustically comparable where the production semantic gate allows it.
- Featured-artist Remix exception behavior from 0.22.x must be preserved exactly.
- Compilation duplicate policy must be preserved.

### Optimization
- Strict same-album wanted-content supersets dominate subsets before global optimization.
- Every album family is represented by a maximum-completeness edition.
- Outside singles/EPs cannot generally rescue a less-complete album edition; since v0.4.5, the narrow exception is a same-family equal-or-better-source full core with *only* independently issued added-featured-remix bonuses.
- After wanted/album coverage:
  1. minimize total retained tracks;
  2. then minimize retained release count;
  3. then source/rip-quality / Existing-vs-Incoming tie-breakers;
  4. DR/mastering analysis only for final interchangeable ties.
- CD rip quality threshold behavior must remain compatible with production.

### Release Map - full parity required
The regular 0.22.12 Release Map is the UI/behavioral reference. Preserve:
- chronological release board;
- release columns/rows;
- SVG relationship curves/links/connections;
- Initial and Result release/track counters;
- signed deltas;
- pending Re-Analyze state;
- release search and Enter cycling;
- current-release selection;
- right-side details pane;
- keyboard activation and visible focus;
- release path opener + copy path;
- release Ignore / Restore;
- exact-instance track Ignore / Restore;
- ignored release remains visible and inspectable;
- pending ignore/restore visual and textual states;
- Re-Analyze required before Copy after pending changes;
- Copy actions disabled while dirty;
- Copy actions require destination + explicit confirmation;
- result drawer with causes, THEN added/removed changes and replacement sources;
- replacement source and alternate retained-copy details;
- per-track statuses;
- exact audio-group cross-release highlighting;
- relationship connections for active track carriers;
- Versions button/panel;
- Remixes button/panel;
- Live button/panel;
- alternative-version highlighting/navigation to its carrier release;
- no loss of track status wording or distinction explanations;
- responsive/reflow behavior;
- Escape closes details without losing map state.

### Copy output and legacy Undo
- File changes occur only after explicit Apply from Release Map.
- Destructive/move plan is confirmed before execution.
- Undo last run restores the previous applied move set where possible.
- Existing filesystem conflict handling must remain conservative and visible.

## Persistent data and paths

Global path rule applies everywhere: every displayed filesystem path has an adjacent open-location control.

Production program data root:
`Documents\Karpuzikov Tools\Duplicate Edition Analyzer\`

Keep program data isolated under the program's own directory. Dependencies, logs, temp, settings, caches, decision snapshots and manifests belong under that product directory, not directly under `Documents\Karpuzikov Tools`.

Do not create a second incompatible settings universe for the lightweight rewrite without migration/compatibility. The goal is to reuse production DEA settings and state when safe.

## UI/UX contract

Mandatory global UXDT baseline applies. Relevant current guidance rechecked on 2026-10-07:
- clear hierarchy and logically organized content;
- descriptive labels and validation;
- full keyboard operation where applicable;
- visible focus states;
- high contrast;
- no reliance on color alone for state;
- responsive/reflow-safe layout;
- clear system feedback and progress;
- efficient task flow and search;
- predictable reusable interaction patterns.

DEA family typography:
- Segoe UI 9 normal text;
- Segoe UI 10 bold section headings;
- Segoe UI 15 bold major headings;
- Cascadia Mono 9 for activity/log text.

Modern UI may improve visual polish, spacing, hierarchy, responsiveness and animation, but must not remove information or controls.

## Dependency rules

- WinGet-first where applicable; check/install/update dependencies rather than asking the user to reinstall the app.
- Check/repair WinGet if missing before relying on it.
- FFmpeg/FFprobe and Chromaprint/fpcalc must be located/installed/updated through the shared dependency strategy.
- hey-bro-check-log integration must remain compatible with production behavior.
- Lightweight UI target must not require PySide6/Qt WebEngine.
- WebView2 runtime must be detected at startup; use Evergreen/shared runtime instead of bundling a fixed Chromium runtime unless a future explicit requirement changes this.
- Long-running dependency setup must show progress/activity.

## Version/status rules

- Every new or updated test build shows its real version plus `Under construction ⚠️`.
- Status never replaces the version.
- Keep `Under construction ⚠️` until the user explicitly confirms testing is complete.
- Every downloadable build must include its version in the physical filename.
- Do not present unversioned current downloads.

## Build/release rules

- Do not modify or add files under `.github/workflows/` unless the user explicitly asks for that exact workflow or explicitly asks to modify an existing workflow.
- Do not give commit links to the user.
- Verify build/output before offering a download.
- Keep production/reference DEA intact while the new lightweight implementation is under construction unless the user explicitly requests replacement.
- New lightweight builds must not overwrite the production release tag/assets until parity is proven.

## Validation gates for lightweight rewrite

A lightweight build is not parity-complete until all of these pass:
1. Production 0.22.12 self-tests/behavioral regression tests pass unchanged or through a shared core.
2. Callout alias grouping regression passes.
3. Main UI feature checklist matches production.
4. Release Map feature checklist matches production, including visible SVG links/connections.
5. Ignore/restore exact-instance track behavior matches production.
6. Ignore/restore release + Re-Analyze + Copy gating works with both non-destructive export modes.
7. Version/Remix/Live panels and navigation match production.
8. Replacement-source/result-drawer behavior matches production.
9. Filesystem-path opener invariant passes on every visible path.
10. Keyboard/focus/accessibility/reflow checks pass.
11. Dependency/bootstrap and persistent-data rules pass.
12. No PySide6/Qt WebEngine dependency is present in the lightweight build.
13. Performance and package size are measured against production; lightweight must be materially smaller/faster without dropping functionality.
14. Real-folder comparison against production produces equivalent analysis/release-selection output before user testing.

## Current work state

- User rejected Native Test 0.1.2 for missing functionality.
- Production/reference DEA 0.22.12 remains the authority.
- New request: create a separate lightweight, fast implementation with a modern UI and zero functional loss from production.
- Architecture implemented at source level: production Python core + pywebview 6.2.1 + Microsoft Edge WebView2 host, with the production main HTML UI and full Release Map HTML/JS retained. Legacy Qt/PySide6 and dormant Tk/Tcl UI code have been removed from the lightweight source.
- WebView2 detection uses Microsoft-documented runtime registry keys and WinGet package `Microsoft.EdgeWebView2Runtime` when installation is required.
- The v0.4.1 core on branch `dea-lightweight-modern` retains the established optimizer and Release Map. The Skrillex comparison log exposed both UI and optimizer bugs. CD/source quality is now preserved for shared recordings even when a lower-source WEB superset must remain for a unique bonus track; provider release-type metadata cannot cause churn for otherwise exact-equivalent containers; and same album + same track slot is an acoustic-routing safety path for provider naming drift such as Quest for Fire `Warped Tour '05 (ft. pete WENTZ)` vs `Warped Tour ’05 with pete WENTZ`. Changes view now has `↔ Replaced`, pairs OLD->NEW replacements, names unique recordings for real additions, resets stale SVG scroll extent, and uses line-separated compact Full-map groups/rows.
- v0.3.6 fixes acoustic group 0 disappearance in the Release Map, narrows ↔ Replaced to verified whole-release wanted coverage in one same-family NEW release, and caches replacement-pair calculation per state.
- **Historical v0.3.6 behavior, superseded by v0.4.9:** The former hard per-recording CD/WEB source-class floor had forced keeping redundant CD subsets along with full WEB supersets. From v0.4.9 the exact optimizer preserves all wanted recordings and max-complete albums while minimizing tracks/releases first; CD/rip quality is only a late tie-break for otherwise equivalent choices. Source-addition remains prohibited.
- v0.3.6 has GitHub source-level patch/static checks, with additional `--ui-self-test` regressions for acoustic group 0 and source-safe minimum-release selection. The Python self-test, actual Windows/WebView2 UI and exact Skrillex folder test have **not been run** here. Do not claim they passed.
- Current source: `audio-tools/discography-torrent-project/lightweight/Duplicate Edition Analyzer Lightweight v0.4.9.pyw`.
- Real Skrillex v0.3.6 run (2026-10-08; user's screenshot and `Duplicate Edition Analyzer Comparison 2026-10-08-04-13-13.jsonl`) reached all 66 exact optimization components, then failed with `Optimizer lost a most-complete album edition after quality tie-breaks.` Log includes 470 track rows, 360 eligible tracks, 191 acoustic groups, and a final DR pass with zero tie groups. OLD Scary Monsters (11 physical tracks, 7 wanted) was EP-tagged, while the otherwise audio-identical NEW release was Album-tagged; 7 wanted OLD/NEW matches were acoustically verified.
- v0.3.7 introduces `_album_requirement_provider_ids`, permitting an otherwise truly identical EP/Single/Album physical edition of the same title and audio sequence to satisfy maximum-completeness album representation. This also fixes short 2-track album editions split by the broader album clustering heuristic. An incomplete single/EP never qualifies. The exact solver, Existing-copy late-substitution veto and final album audit now use the same eligibility contract.
- If a subsequent CD/Existing/DR tie-break unexpectedly breaks a solver requirement, v0.3.7 falls back to the proven exact selection with an explicit error diagnostic; the exact plan is revalidated before use.
- CI validation passed for v0.3.7: Python compilation, `--ui-self-test` (including Skrillex-shaped 11-track EP/Album no-churn and short-album regressions), undefined-name checks, embedded JS validation and bridge contract. Workflow run: https://github.com/karpuzikov/userscripts/actions/runs/37712322914.
- User's uploaded **`Duplicate Edition Analyzer Comparison 2026-10-08-04-21-58.jsonl`** (analyzed with 0.3.7) shows OLD Dirty Vibe (Remixes) release ID 12 (barcode 075679931368) selected, NEW ID 74 not selected. Both have three tracks correctly marked Remix/excluded and third track **Jack Beats Re-work** incorrectly marked `is_remix=false`, `excluded_from_coverage=false`. Save Remixes OFF was active.
- v0.3.8 recognizes Re-work/Rework/Reworked as bracketed/parenthesized or trailing delimited remix descriptors in `is_remix_text`, adds the descriptor to remix-base-title handling and remix-added-feature recognition. Ordinary titles containing "rework" are not inherently remixes.
- Added a v0.3.8 `--ui-self-test` covering the two real Dirty Vibe title shapes, Save Remixes OFF/ON, Personal Picks not overriding excluded remixes, remix-only releases not selected, added-feature exception, and negative unrelated-song controls.
- GitHub Actions workflow [37812280044](https://github.com/karpuzikov/userscripts/actions/runs/37812280044) passed on the v0.3.8 source (compile, built-in UI regression tests, undefined-name checks, embedded JavaScript checks and bridge contract).
- **Pending:** rerun the same Skrillex folders on v0.3.8. Check both Dirty Vibe (Remixes) releases are excluded/removed, verify unrelated releases are unaffected, inspect Release Map and logs. Do not claim a real-folder test has passed.
- User's v0.3.8 screenshot and `Duplicate Edition Analyzer Comparison 2026-10-08-19-57-51.jsonl` confirm all four tracks of OLD `2014-07-07 - Recess (Remixes) [075679936790]` and OLD `2014-12-14 - Dirty Vibe (Remixes) [075679931368]` excluded with Save Remixes OFF. Decision engine correctly assigned REMOVE, but Release Map `_release_map_state_for_ui()` hid them because it only included releases with wanted acoustic groups or manual removals. Hence Removed initially showed only two other releases.
- v0.3.9 map state includes every analyzed snapshot. OLD excluded-only `REMOVE` is shown under Changes > Removed and in Full Map; NEW `SKIP` remains visible in Full Map but does not count as a Change. The decision reason now identifies the excluded track count and explicit Save Remixes OFF / Save Live OFF causes for applicable pure-category exclusions.
- Added end-to-end v0.3.9 regression across `build_release_decisions`, `build_decision_snapshot`, `_release_map_state_for_ui`, and Changes routing, using paired OLD/NEW four-track Dirty Vibe releases, with no retained material and correct plan counts.
- GitHub Actions validation PASSED on v0.3.9 source: [workflow 37814161743](https://github.com/karpuzikov/userscripts/actions/runs/37814161743). Real user Windows/WebView2 rerun has not been completed.
- Actual Windows rerun on v0.3.7 and Release Map inspection remain unfinished.
- v0.4.0 (2026-10-09) is the graphical WebView2 successor to 0.3.9 on `dea-lightweight-modern`, not the separate abandoned ASCII v0.4.0 prototype. Changed only Full Map release dividers (2 px `#303947`) and thicker SVG relationship connection paths (idle duplicate 1.65 px, active duplicate 2.8 px, Versions 3.0 px, Remixes/Live 2.65 px, selected carrier 3.6 px). Added static regression checks for line legibility; core acoustic matching/optimizer/release decisions/file copying are unchanged.
- The `dea-lightweight-ascii-ui-test` branch is historical/rejected; DO NOT merge its terminal/Textual work into graphical DEA.
- v0.4.0 GitHub CI PASSED on the graphical source: [workflow 37871448332](https://github.com/karpuzikov/userscripts/actions/runs/37871448332), covering Python compilation, `--ui-self-test`, Ruff F821, embedded JavaScript and bridge regression contracts. Real Windows WebView2 rendering and full Skrillex rerun still need verification.
- Superseded graphical v0.4.0 was followed by v0.4.1. Current versioned download is on the branch below; do not use an outdated v0.4.0 source.
- v0.4.1 adds automatic `<recycle root> - UPDATED` sibling destination to both Release Map export actions (shown by default; Browse remains optional). Example NEW `C:\!deemix Music\Metro Boomin` => `C:\!deemix Music\Metro Boomin - UPDATED`.
- The former NEW-only copy button is **replaced** with **Move old + new releases into** and **Move old + new** action. It now physically moves retained OLD and NEW release folders after an explicit destructive confirmation, leaves SKIP/REMOVE source releases untouched, forbids destination collisions and nesting within input trees, journals each folder move for Undo, and preserves previous Undo journal backups.
- Retained cross-device folder moves use checked copy with per-file SHA-256 before source deletion. Same-device moves use direct rename. Reverse-order rollback is attempted on failure. Successful move invalidates cached Release Map snapshots and offers an Undo button in its completion dialog. Unmodified Copy old + new remains non-destructive.
- `--ui-self-test` now includes temporary filesystem tests: both OLD+NEW copy, both OLD+NEW move, excluded NEW unchanged, existing destination refusal, full Undo, and simulated cross-volume copy verification.
- **2026-10-09 previous checkpoint:** v0.4.1 graphical WebView2 source is available as a versioned branch file: `https://raw.githubusercontent.com/karpuzikov/userscripts/dea-lightweight-modern/audio-tools/discography-torrent-project/lightweight/Duplicate%20Edition%20Analyzer%20Lightweight%20v0.4.1.pyw`. Repository audio-tools menu and lightweight README display `0.4.1 - Under construction ⚠️`; no ASCII/Textual code was merged.
- **CI validation succeeded** on v0.4.1: [GitHub Actions run 37872841539](https://github.com/karpuzikov/userscripts/actions/runs/37872841539) (source compile, `--ui-self-test` including temporary-folder Copy/Move/Undo and simulated cross-volume verification, Ruff F821, embedded JavaScript syntax, bridge/UI contracts). Earlier intermediate CI failure [37872411545](https://github.com/karpuzikov/userscripts/actions/runs/37872411545) was superseded by passing follow-up runs. Automated tests **do not** confirm real Windows WebView2 behavior, real mass-storage transfer performance, actual user folders or full parity with production v0.22.12.
- **Distribution scope:** v0.4.1 is published as a downloadable GitHub branch `.pyw`, **not** as a formally created GitHub Releases entry/asset: `duplicate-edition-analyzer-lightweight-v0.4.1` returned 404 at handoff. Do not tell the user that a formal GitHub Release exists.
- **Next test for new behavior:** with NEW root `C:\!deemix Music\Metro Boomin`, both actions should propose `C:\!deemix Music\Metro Boomin - UPDATED` before Browse. **Copy old + new** should preserve both original trees; **Move old + new** requires confirmation, transfers only retained OLD+NEW folders, leaves skipped/removed folders in place, and enables Undo to restore original paths. Repeat with a preexisting destination and invalid nesting to verify refusal; test multi-disc, collision and cross-volume cases using sacrificial data, never irreplaceable originals. A successful move invalidates cached map/selection and requires rescanning.
- **Remaining release/parity blockers:** complete end-to-end Windows/Skrillex run and copy/move/undo UI walkthrough; verify details, focus, keyboard/reflow, default destination paths, Copy vs Move wording, retained/removed release counts, and safe rollback. Keep status `0.4.1 - Under construction ⚠️`; do not claim parity, final release or Windows testing passed.
- **2026-10-09 v0.4.2 safety checkpoint:** A source-only audit of the v0.4.1 export/Undo path found (1) missing nested destination-target collision preflight, (2) same-volume permission errors taking the cross-device copy/delete path, (3) partially copied final-named release folders on Copy failure, (4) silent removal of Undo journal when moved and original paths were both missing, and (5) default UPDATED destination open-location buttons ignoring their fallback displayed path. v0.4.2 fixes those cases while preserving WebView2 and the original optimizer. New Python self-tests cover nested OLD/NEW targets, PermissionError, missing Undo data, and default opener markup. The source is `audio-tools/discography-torrent-project/lightweight/Duplicate Edition Analyzer Lightweight v0.4.2.pyw`. Existing v0.4.1 remains available for rollback reference; do not label v0.4.2 Windows-tested.
- **CI validation PASSED for v0.4.2:** [GitHub Actions run 37906576608](https://github.com/karpuzikov/userscripts/actions/runs/37906576608), with Python compilation, `--ui-self-test` (including nested destinations, rejected permission fallback and missing-folder Undo), Ruff F821, embedded Main UI + Release Map JS syntax, and bridge contract. CI used Linux and is not real Windows/WebView2/Skrillex validation.
- **Unresolved recovery risk:** if checked cross-volume copy successfully publishes a destination but source deletion fails partway (for example, a locked file), manual recovery may be needed; full transactional handling and Windows fault injection remain a blocker before moving valuable real folders. Do not run Move on the real Skrillex originals until this is closed and tested.
- **2026-10-09 v0.4.3 concurrency/process-lifetime checkpoint:** User Task Manager screenshot shows many `fpcalc.exe` processes surviving closure of v0.4.2; user observed 14 concurrent reads overwhelmed their HDD. The cause is `run_hidden` launching unowned subprocesses using `subprocess.run` and I/O worker counts derived entirely from logical CPU count (up to 32). Fixed with the Windows application-scoped Job Object (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) covering `run_hidden` children: close button, X/window closed callback, and `atexit` close the Job Object. Replaced default ffprobe/fpcalc I/O limits with `_io_worker_plan` for both source roots: HDD/network/unknown 2, SSD up to 8; manual override 1-32 in preserved graphical WebView2 UI. Windows `StorageDeviceSeekPenaltyProperty` via `DeviceIoControl` classifies fixed disks without requiring administrator privileges; unknown classification defaults conservatively. Setting is persistent and Activity shows count and storage type. Acoustic comparison CPU worker count stays separate. Front-page text no longer falsely says Release Map always copies only.
- **v0.4.3 automated validation PASSED on final source:** [GitHub Actions run 37936414635](https://github.com/karpuzikov/userscripts/actions/runs/37936414635) (compile, built-in self-test including worker selection and subprocess probe, Ruff F821, embedded JS syntax and WebView2 bridge contract). This also covers the subsequent UI wording change. CI runs Linux and does not verify real Windows Job Object or seek-penalty behavior.
- **Immediate Windows verification:** First close all remaining orphan `fpcalc.exe` from the former version (the new app intentionally only owns its own children). Use a disposable HDD test tree with new v0.4.3, select Auto, verify Activity logs 2 (HDD), confirm no excess `fpcalc.exe` read load, close during fingerprinting and verify child exit. Then manual limits 1 and 4; verify selection persists after reopening. Repeat on SSD / mixed HDD+SSD and WebView2 focus/keyboard if possible. Report the auto media label shown in Activity: if unknown, investigate Windows IOCTL seek penalty on the user's storage stack.
- **2026-10-10 Weeknd findings and v0.4.4 fixes:** Two user-uploaded comparison logs `Duplicate Edition Analyzer Comparison 2026-10-10-03-15-13.jsonl` and `(1).jsonl` have identical SHA-256 `cd4ceacf5c948499a6958524e1a0531c661cc183066bfcc7e838396dd75c3fe8`. Therefore there is no uploaded post-Re-Analyze log. Initial run v0.4.3 has 659 tracks, 566 fingerprints, 93 early excluded, 265 recording groups; optimizer selected 52 releases. OLD CD 30-track `Trilogy [US - B0017732-02]` source was declared compilation but every track was permanently eliminated from included coverage via `apply_compilation_policy`; NEW 30-track WEB Trilogy was declared Album and selected alongside three original mixtapes. 36-track `The Highlights (Deluxe)` was also erroneously tagged Album and forced selected, although many examples are acoustically matched (I Was Never There and Pray for Me are MATCH, not missed). `Call Out My Name` on multiple releases was excluded through the too-broad `CALLOUT_PATTERN_RE` matching the ordinary words 'call out'. Artist tags on the four remix examples contain secondary performer but no literal feat. marker: `Maluma & The Weeknd`, `The Weeknd with ROSALÍA`, `The Weeknd & Ariana Grande`. K-POP (Chopped & Screwed) was considered normal. Open Hearts (Single Version) was *included* but acoustic matched to base 23.79-second-longer Open Hearts via `unmatched_is_silence=True`, despite non-identical fingerprints.
- **v0.4.4 implementation:** Stop permanently setting compilation tracks excluded. Exact group-provider selection prefers available/unblocked non-compilation sources, then falls back to compilation if no regular source exists; quality-floor verification uses the identical provider contract. The previously blocked CD Trilogy can return on Re-Analyze when the three original mixtapes and WEB Trilogy are manually blocked. Provider Album label is overridden for 25+ track Trilogy and The Highlights (Deluxe) 12+ track anthologies. ARTIST-tag secondary collaborators recognized in featured-remix policy, with a conservative fallback for exactly one secondary artist if no baseline exists (protecting Skrillex Dirty Vibe 3+ act regression). Callout regex requires explicit Suggested/Research/Hook markers. Version descriptor Chopped & Screwed is a remix; ordinary song wording isn't. Significantly shorter explicit Single Version with non-identical fingerprints stays separate; exact fingerprints still merge.
- **v0.4.4 CI:** GitHub Actions `https://github.com/karpuzikov/userscripts/actions/runs/38010097527` PASS after narrowing an initial permissive remix-tag regression (earlier failures are superseded). Includes Python source compilation, `--ui-self-test` with synthetic Weeknd-shaped cases and all existing regressions, Ruff F821, embedded WebView2 JavaScript syntax and bridge checks. This does NOT reproduce the full 659-track Weeknd scan or test Windows actual data changes.
- **2026-10-10 v0.4.5 Starboy album exception (implemented, CI passed):** The uploaded `Duplicate Edition Analyzer Comparison 2026-10-10-05-54-42.jsonl` is version 0.4.4, has 660 tracks (589 fingerprinted) and selected CD `2016-11-28 - Starboy [US - B0026150-02]` (19 physical/18 included groups), WEB `2016-11-24 - Starboy (Deluxe) [602455499851]` (21 physical/20 included groups), existing `2023-02-24 - Die for You (Remix) - Single [602455483133]` (4 physical), while removing existing `2017-08-01 - Reminder (Remix) - Single [00602557936223]` (1 physical). A union of the log's accepted acoustic matches shows **exactly 18 shared wanted groups**, and only two Deluxe extras: Reminder (Remix), acoustically MATCH to the standalone 1-file single, and Die for You (Remix), MATCH to the standalone 4-file single. `_album_requirement_provider_ids` formerly restricted the album family to maximum wanted-group edition regardless of separately published bonus remixes, forcing the unneeded WEB Deluxe. v0.4.5 adds `_album_core_with_separate_remix_bonuses`, which permits the CD full core as an album representative ONLY when every missing Deluxe group is a wanted newly featured remix, present on an eligible separate Single/EP, the family title/audio overlaps, the edition is a fully contained core, and the source rank is no weaker. The method is used by album provider selection, superset prepruning (so CD or equal-source core remains eligible), exact solver and late validation. Regular album bonus tracks, absent/blocked independent singles and weaker-source core albums do NOT qualify. Synthetic real-log-shaped regression expects {CD 19 + Reminder 1 + Die for You Single 4} = **24 physical files**, not {CD 19 + WEB Deluxe 21 + Die for You Single 4} = 44. Every wanted group and CD source floor remains mandatory. [GitHub Actions run 38020343636](https://github.com/karpuzikov/userscripts/actions/runs/38020343636) passed all compile, self-test, Ruff F821, embedded JS and bridge checks. No real Windows execution or full actual optimizer replay has yet validated v0.4.5 outcomes.
- **2026-10-10 v0.4.6 Privilege fingerprint completeness fix:** Uploaded real Weeknd `Duplicate Edition Analyzer Comparison 2026-10-10-06-42-27.jsonl` from **v0.4.5** reveals two editions of `My Dear Melancholy,`: OLD 2018-04-13 EP (track index 127; source `06 Privilege.m4a`) and NEW 2018-03-30 WEB (index 422; source `06 Privilege.flac`). Both report identical 170.573333-second duration, normalized title `privilege`, same artist/album/track number. Their actual comparison at pair_index 610 is REJECT, even though score=0, good=1, excellent=1, overlap=1, shift=0, strict_pass=True and mastering_pass=True, **because acoustic_coverage=0.108407 and unmatched non-silence**. Candidate was routed with same title + same album/slot + weighted tokens, so routing was NOT the cause. The root cause is an implausibly short fpcalc vector from one source despite reported full duration (and fpcalc command `-length 0`). Neither file may be asserted an acoustic duplicate until complete fingerprints exist; the rejection threshold must not be relaxed. New `_chromaprint_fingerprint_incomplete` catches obvious under-length vectors for >=30s durations; `_recover_short_chromaprint` decodes only suspicious files to temporary mono 11025Hz PCM via FFmpeg then reruns fpcalc in the existing subprocess-owned I/O-limited stage. If restoration fails/incomplete, a user-visible error is recorded and conservative singleton treatment remains. Temporary WAV lives in the tool's `temp/fingerprint_recovery` subfolder and is deleted. The Track comparison JSONL now includes `fingerprint_frames`, `fingerprint_repaired`, `fingerprint_incomplete`, allowing actual diagnosis. Built-in UI regression tests include mocked truncate/recover/cleanup/fail-closed subprocess cases and source immutability. **CI PASSED** https://github.com/karpuzikov/userscripts/actions/runs/38021833055 (compile, --ui-self-test, Ruff F821, embedded JS, bridge). No real Windows decode has been executed, nor has the exact original ALAC audio been available in this environment.
- **2026-10-10 v0.4.7 follow-up (IMPLEMENTED; CI PASSED):** User confirmed earlier v0.4.5 `Privilege` acoustic REJECT was correct, because the incoming WEB `2018-03-30 - My Dear Melancholy, [602577858994]\\06 Privilege.flac` is **corrupt**. Do not reinterpret partial perfect similarity as whole-file identity or overrule the original reject. Implemented full decode verification of every distinct physical file (including entire shared CUE image once) via `FFmpeg -v error -xerror -err_detect explode -map 0:a:0 -f null -` during preflight with the existing drive-aware read-worker limit and progress UI. `Track.integrity_error` records exact decoder problem/path; corrupt tracks are not submitted to fpcalc and remain conservative singleton wanted groups. `Release.validation_issues` records album completion and metadata discrepancies. Full file decode is not the same as the old v0.4.6 short-fingerprint PCM recovery; recovery is still used only for truncated fingerprints on healthy files.
- **Release completeness rules added:** `validate_release_track_totals` inspects `TRACKTOTAL`, `TOTALTRACKS`, `TRACKNUMBER=n/total`, `DISCNUMBER`, and disc folder names; audits separate discs; reports missing numbers, duplicate numbers, conflicting declared totals, and out-of-range indices. No tagged total means UNKNOWN, never infer incomplete solely from incomplete filesystem cardinality.
- **Standalone Release Map fix:** The user's uploaded `Duplicate Edition Analyzer Comparison 2026-10-10-07-34-33.jsonl` is **v0.4.5**, with 1,211 tracks total, 1,208 fingerprinted and optimizer 46 proposed retained releases. User provided *only* New/update; former Release Map incorrectly showed `+ Added 46`, though no Existing baseline and no actual file modifications. v0.4.7 state has `standaloneMode` and full scanned count. JS defaults to Full map, labels `Scanned`, `Proposed retained`, `RETAIN`, ✓; shows zero initial Adds/Upgrades/Removes; only manual Ignore appears as a change. Dual-folder Existing+New behavior unchanged.
- **Safety/UI:** Map shows global `auditBanner` and per-release ⚠️ icon/details for corrupt/unreadable/incomplete releases, and server-side Copy/Move operations are blocked while any validation issues remain. Re-Analyze and UI patches cannot override the blocker. Preflight notes explain affected paths and still allow viewing the provisional plan; user must correct files and rescan. No auto-repair/delete/move.
- **Tests/CI:** Added `--ui-self-test` for missing track 2/3, unknown totals, valid `TRACKNUMBER=1/2`, contradictory `TRACKTOTAL`/`TOTALTRACKS`, multi-disc completeness, mocked full FFmpeg decoder errors, standalone map baseline/issue count and changed labels; old regressions remain. Two initial CI failures fixed: group-icon static check needed standalone alternative; track-total regex was double-backslash escaped and therefore invalid. Final source commit `9b4cb207b575e0047aa45fb2b61bfad11050bdfc` validated **PASS** GitHub Actions `https://github.com/karpuzikov/userscripts/actions/runs/38025032743`. No user-owned actual Windows 1,211-track media data was decoded or file moved here; status **Under construction ⚠️**.
- **New immediate Windows test:** Start v0.4.7 on the same single New/update folder. Confirm Full map initially shows 46 *proposed retained* not +46 additions, and there are zero changes until explicit manual operations. Confirm corrupt `06 Privilege.flac` is flagged as an affected release, source remains untouched, Copy/Move blocked until fixed; verify absence/presence of TRACKTOTAL/TOTALTRACKS for any reported incomplete disc by inspecting actual tags. Then test against OLD+NEW and validate that actual additions/replacements remain meaningful. Do not use Move/Apply on the primary collection until every warning is resolved and disposable Undo is verified.
- **2026-10-10 v0.4.8 album-wide vs disc-local TRACKTOTAL correction:** User uploaded `Duplicate Edition Analyzer Comparison 2026-10-10-07-46-43.jsonl` generated by v0.4.7 (370 tracks total; 366 fingerprinted). Actual 28 `track` rows for JPEGMAFIA release_id=35 named `2024-08-01 - I LAY DOWN MY LIFE FOR YOU_ DIRECTOR'S CUT [199066832615]`: 21 physical FLAC under `CD1` indexed 01..21 and 7 under `CD2` indexed 01..07. User explicitly states that a declared `TRACKTOTAL=28` refers to the RELEASE as a whole (21+7), not each disc. JSONL does not include raw TRACKTOTAL fields; tag scope is user-verified, path/count from the log. v0.4.7 `validate_release_track_totals()` assumed every declared total was per disc and thus invented 7 missing on CD1 and 21 missing on CD2, raising false warnings that block Copy/Move.
- **v0.4.8 code:** Replaced the old per-disc-only track-total validation. For a multi-disc release with one distinct positive declared total that exceeds each disc's physical file count and its largest numbered index, select release-wide scope; also accept globally continuous numbering across discs. When scoped album-wide, test sum of all physical tracks against total, missing/duplicate indices within each numbered disc (or across the globally continuous sequence), conflicting tags and out-of-range numbers. Distinct separate totals such as CD1=21 + CD2=7 remain disc-local and must each meet their declared count. Absence of valid total means completeness unknown, not missing. Integrates unchanged with existing release.validation_issues and per-release warning banner/Apply guard; no optimizer or interface replacement.
- **Regression tests/validation:** Added synthetic real-log-shape 21+7 with repeated TRACKTOTAL=28 (no error), 20+7 against album-wide 28 (must report combined 27), per-disc 21+7 (no error), per-disc CD1 missing one (must warn), CD1 globally numbered 1..21 / CD2 22..28 with TOTALTRACKS=28 (no error). An initial regression fixture incorrectly set expected CD1 total equal to its truncated observed track count 20 and was fixed to keep declared 21. Final CI **PASS** `https://github.com/karpuzikov/userscripts/actions/runs/38025613096` (commit `20ecf6c3ad1ce76f8850f154794ae91e063cc7dc`) including all existing WebView2/optimizer/audio regressions. Source: `audio-tools/discography-torrent-project/lightweight/Duplicate Edition Analyzer Lightweight v0.4.8.pyw`; status **Under construction ⚠️**, no full Windows user source re-analysis after the fix.
- **Next real Windows verification:** Analyze the identical JPEGMAFIA folder on v0.4.8, verify the Director's Cut 28 (21+7) no longer produces a false incomplete/metadata warning and does not block Copy/Move by itself. Confirm true one-disc missing-track and corrupt FLAC cases still warn. Note any other independent audit warnings can continue to block Apply; do not treat no warning for this release as validation for every scanned release.
- **2026-10-11 v0.4.9 authoritative user policy correction (IMPLEMENTED; CI PASS):** User clarified that **the original/CD is preferred only when there is a full audio duplicate**. If a Special Edition acoustically contains every wanted track of the original PLUS one or more unique wanted bonuses, especially with NO OTHER sources for those bonuses, retain the complete Special Edition alone regardless of CD-vs-WEB quality. A higher-quality CD is not a reason to retain an otherwise redundant original and inflate the retained physical track count. Rule priorities: preserve all wanted recording groups and valid max-complete album-family representative; minimize total physical retained tracks; minimize releases; then CD/rip/Existing/DR only as late tie-breaks for coverage-equivalent plans. v0.4.5's verified independently issued newly featured remix bonus singles exception remains intact (Starboy 19 CD +1 Reminder single+4 Die for You single preferred to larger Deluxe package when all conditions hold).
- **Real log evidence:** `/mnt/data/Duplicate Edition Analyzer Comparison 2026-10-11-05-52-24.jsonl` (user-supplied v0.4.8; 192 scanned, 178 fingerprinted, 30 logged comparisons) has OLD `2011-10-03 - Cross the Line [EU - NHS194CD]` (release 8, 14 wanted audio, source CD) and NEW `2011-10-03 - Cross the Line (Special Edition) [3617056553892]` (release 24, 18 wanted, Digital Media). All **14 cross-release acoustic pairs MATCH**, plus 4 only-in-Special wanted bonus recordings: `Cryptkeeper`, `Change Me`, `Portal`, `Menace`. Another incoming Cross the Line EP (release 25, 5 physical, 3 wanted) exists but the bonus tracks are not otherwise covered. Earlier v0.4.8 optimizer selected BOTH 14 CD and 18 WEB, violating current priorities and resulting in 32 files. Desired v0.4.9 outcome: WEB Special Edition 18, original CD redundant; no wanted material lost.
- **Code:** New versioned source `audio-tools/discography-torrent-project/lightweight/Duplicate Edition Analyzer Lightweight v0.4.9.pyw` on `dea-lightweight-modern`. `find_dominated_releases` now prunes strict same-album acoustic subsets regardless of source rank except the existing independent featured-remix singles exception. `prune_redundant_selected` no longer insists on equivalent/higher-source carrier for each shared acoustic group. `exact_global_collection_minimize` removes the per-group source-floor provider restriction, admits all regular carriers, and evaluates cost by total physical tracks then releases then source/rip quality/Existing. `optimize_collection` late verifier checks eligible wanted coverage and album obligation without vetoing a smaller plan merely because CD class no longer represented. Removed unused obsolete `enforce_source_quality_floor`. Optimizer log now reports `source_floor_requirements: 0`, `source_floor_enforced_in_exact_solver: false`, `source_quality_tie_break_only: true`.
- **Tests:** New built-in `--ui-self-test` proves synthetic real-log-shape OLD CD14 vs NEW WEB18 chooses **only 18 WEB**, and full acoustic/container duplicate CD14 vs WEB14 chooses **CD**. Updated old `Bangarang` EP superset test (now WEB8 only) and component exact-source-floor test (WEB superset only). Updated Starboy missing-Reminder-single case now requires Deluxe without retaining redundant CD; original valid separate-remix Starboy CD+singles test still passes. GitHub Actions complete [CI run 38107417253](https://github.com/karpuzikov/userscripts/actions/runs/38107417253) **PASS** (Python compilation, static checks, built-in UI regression and embedded JS/bridge). The attached real 192-track dataset was NOT run through new Windows v0.4.9; source-only synthetic regression demonstrates policy behavior. There is no real filesystem Copy/Move/Undo verification. Status remains `0.4.9 - Under construction ⚠️`.
- **Immediate Windows test:** Analyze unchanged Camo & Krooked OLD and NEW folder roots in v0.4.9 with logging enabled; confirm original CD `Cross the Line [EU - NHS194CD]` is marked REMOVE and 18-track `Cross the Line (Special Edition) [3617056553892]` is REPLACE/retained with four bonus tracks, not a phantom extra CD KEEP. Verify neighboring EPs, other albums, actual changes counts and final source paths before using Apply. Check that Starboy still selects original core plus separate feature remixes and that exact full duplicates prefer CD. Update GitHub documentation if future local tests reveal unforeseen differences.
- **Next v0.4.9 verification:** Analyze the unchanged two Weeknd folders with logging enabled and inspect `Privilege` in both releases and `fingerprint_frames`/`fingerprint_repaired` in the new comparison JSONL. If repaired successfully and acoustically identical, only one release should be credited with exclusive coverage; if not, the error must state why. Verify all other grouping and retained releases, particularly Starboy, before any Move/Apply on actual data.
- **Immediate user verification:** Run v0.4.9 Analyze on unchanged Weeknd OLD/NEW folders. Verify CD Starboy and standalone Reminder and Die for You singles are retained; WEB Deluxe should be omitted unless some other independently verified wanted or album-completeness exception requires it. Review all other album decisions (especially Let Go, Trilogy, Highlights) to detect regression. Do not Move/Apply important originals before comparing the complete plan and validating Undo on disposable folders.
- **Next direct test:** Open v0.4.9 on the exact same The Weeknd OLD/NEW roots, rerun analysis with Save Remixes OFF, inspect CD Trilogy vs both WEB Trilogy/original mixtapes and compilation priorities, then manually Ignore all three mixtapes plus WEB Trilogy and Re-Analyze. Verify CD Trilogy returns KEEP, no wanted group is orphaned, Highlights Deluxe is not retained absent a genuine unique recording; verify Call Out My Name, four artist-tag remix tracks, Chopped & Screwed, and the shorter Open Hearts Single Version. Upload both initial and **new post-Re-Analyze** logs/decision snapshots if any discrepancy. Keep Move/Apply disabled as a user procedure for important originals until real outcome and cross-device Undo safety checked.
- **Windows-specific validation not done here:** Windows kernel Job Object creation/assignment, HDD/SSD detection, abrupt-kill cleanup, actual live Skrillex analysis, and Move/Undo have not been tested on user's PC. Do not declare stable. Existing cross-volume source-cleanup recovery risk from v0.4.2 remains open. Keep `0.4.9 - Under construction ⚠️` until user tests and confirms.
- No new lightweight build has yet been declared parity-complete.
- Do not send another "native/light" test merely because it launches. Complete the parity checklist first.

- **2026-10-11 v0.4.9 direct source/CI audit (NO WINDOWS EXECUTION):** Fetched actual `lightweight/Duplicate Edition Analyzer Lightweight v0.4.9.pyw` on `dea-lightweight-modern` (blob `cdf903ffa68d6f737c344b132f2ee0431ed948a3`). Confirmed built-in Cross the Line 14 CD / 18 WEB Special subset and CD-vs-WEB 14/14 full-equivalence expectations, the Bangarang EP strict WEB superset expectation, and Starboy CD + separate eligible remix singles / unavailable-single fallback. Verified GitHub Actions [run 38107417253](https://github.com/karpuzikov/userscripts/actions/runs/38107417253): success on **ubuntu-latest** for compilation, UI regression self-test, undefined names, embedded JavaScript and bridge checks. This is NOT a run on the user's actual Windows audio files, WebView2, HDD/SSD worker/process cleanup, or real Copy/Move/Undo. Safety finding: `_verified_release_directory_move` publishes a cross-volume destination before `shutil.rmtree(source)`; an exception or partial failure during source cleanup occurs before `move_retained_plan` appends/journals that move, so automatic rollback/Undo cannot reliably account for it. This is an **unresolved cross-volume Move blocker**: avoid Move across volumes until recovery/journaling is corrected and Windows tested; use Copy only after verifying the proposed plan. Same-volume Copy/Move/Undo remain Windows-unverified. The live user datasets and v0.4.9 comparison log were not supplied in this conversation; do not claim the real result has passed.

## Exact next steps

1. On Windows, first analyze the unchanged Camo & Krooked OLD+NEW Cross the Line folders in v0.4.9 with comparison logging, verify 14/18 acoustic subset and Special-only 18-file selection, then verify The Weeknd analysis/Re-Analyze and source preservation, then HDD/SSD I/O limits, process cleanup on Close and X, then test the default UPDATED destination and both Copy/Move actions on disposable OLD/NEW folders, including confirmation, collision refusal, Undo and rescan; then rerun the user's exact Skrillex OLD/NEW comparison on 0.4.9. Verify: Scary Monsters exact-equivalent Existing no longer churns; the Bangarang strict WEB 8-track wanted-audio superset replaces the fully covered 7-track CD in the current synthetic regression; the CD wins only for full-equivalent coverage or if independently required by another hard obligation; Make It Bun Dem is shown as one `↔ Replaced` OLD->NEW change; Quest for Fire provider wording routes the 11th track acoustically and does not create a false WEB addition if the audio matches; Changes filters cannot scroll into Full-map-sized empty space; Full map uses line-separated compact groups/rows.
2. Run syntax/static checks and source-mode launch checks.
3. Compare main-window controls and behaviors against production 0.22.12.
4. Compare full Release Map behavior against production 0.22.12, especially SVG links, cross-release highlighting, alternative-family panels, ignore/restore, Re-Analyze and result drawer.
5. Verify the implemented bridge API used by the current Release Map:
   - getState
   - toggleTrack
   - toggleRelease
   - reanalyze
   - openFolder
   - copyPath
   - apply
   - closeMap
   plus the main-window bridge API.
6. Preserve the exact Release Map SVG connection rendering and all details/alternative panels.
7. Keep the production application untouched and independently runnable.
8. Add/update direct regression checks for parity-critical bridge actions and UI contracts.
9. Measure executable/dependency footprint and startup time.
10. Only after parity validation, publish a versioned `Under construction ⚠️` test build for user verification.

## Rejected approaches

- Raw Win32/C++ lightweight rewrite that independently reimplements/simplifies the production engine: rejected by user after Native Test 0.1.2 because functionality was lost.
- Simplified Release Map list/detail view: rejected; full visual map links and interactions are mandatory.
- Calling a build equivalent before feature parity has been audited: forbidden.

## Rule sources to read before work

- Repository global rules: `/SOFTWARE_RULES.md`
- This file: `audio-tools/discography-torrent-project/CONTINUITY.md`
- DEA project history/specification: `audio-tools/discography-torrent-project/PROJECT.md`
- Current functional source: `audio-tools/discography-torrent-project/tools/Duplicate Edition Analyzer v0.22.12.pyw`


## Planned migration to Music Collection Cleaner (2026-10-11)

- User chose the standalone product name **Music Collection Cleaner** and explicitly requested moving the graphical lightweight DEA application to its own repository. Target GitHub repository: `karpuzikov/music-collection-cleaner` (new separate repository, not a branch or subdirectory in `userscripts`). The product is still `0.4.9 - Under construction ⚠️` until the actual versioned rename/migration is implemented and checked; do not claim the rename or move has been published.
- Migration is **not executed**: as of this checkpoint the target repository returned GitHub 404 and the connected GitHub write integration has no repository-creation action. Do not delete the source, create fake repository links, or mark the migration done. The only manual prerequisite is creating an empty `karpuzikov/music-collection-cleaner` repo with sufficient connector access.
- After the repository is created, mirror the **full byte-for-byte** canonical `SOFTWARE_RULES.md` from `karpuzikov/userscripts` at the new repository root **before other source changes**. Move/adapt the authoritative app-specific `RULES.md` and `CONTINUITY.md` to the new repo root; preserve all functional rules and unresolved tests/defects. Keep source as one versioned `.pyw`, preserve dark WebView2/pywebview GUI, Release Map, comparator, logging, dependencies, drive-aware workers, Copy/Move/Undo, and existing regressions. Do not incorporate rejected Textual/ASCII prototype.
- On implementation, use a **new version number** and new filename `Music Collection Cleaner v<version>.pyw` matching `APP_NAME`/`APP_VERSION` and UI. Update embedded HTML titles, release/update identifiers, `GITHUB_REPOSITORY`, release tag and asset names, User-Agent where applicable, and README. Explicitly migrate existing settings/caches/logs/undo state from `Documents\\Karpuzikov Tools\\Duplicate Edition Analyzer` into the isolated `Documents\\Karpuzikov Tools\\Music Collection Cleaner` location without data loss; in particular do not strand the last-move Undo journal or silently reset Personal Picks. Preserve old application data until verified.
- Keep separate production/reference `Duplicate Edition Analyzer v0.22.12.pyw`, its release/assets, and other discography tools untouched in `userscripts`. The former lightweight source and historical v0.4.x versions may remain as a read-only historical reference until destination source, documentation, import, and tests have been verified; afterwards make source-of-truth and README pointers unambiguous. Never disrupt the production analyzer's updater/tags while redirecting only the new product.
- Migration acceptance requires: repository and files exist and GitHub content can be read back; Python syntax and embedded `--ui-self-test` pass; GitHub updater targets the new repo; full UI/feature contracts maintained; Windows real-dataset Cross the Line, Starboy, Bangarang, Skrillex comparisons remain pending and `Under construction ⚠️` remains. **Existing blocker:** cross-volume Move can publish target and partially fail during source deletion without a complete journal; fix and regression-test before claiming Move safe/stable. Do not create or modify GitHub Actions workflows without explicit permission.
