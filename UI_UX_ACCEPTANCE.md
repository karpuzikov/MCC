## MCC v0.5.26 - eligible coverage vs physical presence (2026-10-14)

- **User-reported case:** The 2018-03-23 Ceinture noire Décennie EU CD and WEB [3616401604548] are both selected and physically carry "La même". In the actual uploaded October 14 v0.5.24 comparison JSONL, the EU CD physical track 61 has 1594 fingerprint frames and is included; WEB physical track 1147 was excluded pre-fingerprint, so has zero acoustic evidence. The separate non-selected La même Single 280 is an acoustic MATCH to CD 61 (score 0.144291; good fraction 1). Therefore a "Unique to this retained release" badge is an **incorrect physical-presence claim**, even though the selected CD is the only eligible provider in the final coverage plan.
- **Control inventory:** Existing Release Map track rows/status/tooltip, Details metadata and Changes view explanation only. No new controls, buttons, menus or clicks. Changed track status to **Only eligible copy; also listed on excluded edition: [release name]** when exact metadata name + normalized performer set + duration within 1s appear on a separate selected-but-excluded physical file. All otherwise essential selected tracks say **Only eligible copy in retained releases**. The release Details counter now labels these tracks **essential**, not "unique"; Changes view says "Adds needed recordings" instead of "Adds unique recordings". Backend decision explanation likewise specifies eligibility; this is not a different optimizer choice.
- **Safety:** Excluded counterpart is *metadata evidence only*. No acoustic matching performed or implied, and its `group_id`, fingerprint, exclusion or optimizer participation must not change. Retained audio is not modified, deleted or moved by this change. Existing keyboard semantics, focus, responsive map, comparison/fingerprint integrity and Copy/Move/Undo unchanged.
- **Tests authored:** Synthetic retained-CD + retained-WEB paired release where "La même" signatures `GIMS & Vianney`/`GIMS;Vianney` normalize identically, CD copy included and WEB copy excluded/ungrouped. Embedded self-test inspects snapshot counterpart evidence and Release Map field propagation. Static GitHub readback + isolated status V8 invocation (including Gem precedence) PASS. **NOT RUN:** full Python `py_compile`, embedded `--ui-self-test`, Windows WebView2 rendering/keyboard/hover/screenshot comparisons, real GIMS rerun, persistence and source-safe Copy/Move/Undo. Status **v0.5.26 - Under construction ⚠️**.

## MCC v0.5.25 - GIMS log regression audit (2026-10-14)

- **Scope:** no new or modified UI controls. Single-file Python classifier now returns **Single** rather than **EP** for one-track Remix releases without explicit conflicting release-type metadata. Existing Release Map type labels automatically reflect the corrected source value. No change to four direct unusual-pattern buttons, keyboard access, cancellation, WebView2 layout, file operations or state/settings.
- **Verified old log:** uploaded `Music Collection Cleaner Comparison 2026-10-14-08-17-53.jsonl` is a valid v0.5.24 run with 1,604 tracks (1,508 eligible), 153 physical releases, 72 retained releases and 304 retained physical audio tracks. Eight one-track remixes mislabeled EP; seven excluded, one selected due added featured performers. Included tracks have complete fingerprints, zero recorded integrity errors and zero logged comparison consistency mismatches. 13 pre-fingerprint excluded `Corazón` variants lack an exact normalized title+artist signature in the selected set due inconsistent featured credit placement, so acoustic safety still needs examination; two new selected albums have wanted candidates not matched in the retained set.
- **Added tests:** eight real-log-shaped classifier regression fixtures plus explicit EP and explicit Single priority and multi-track remix EP cases. Future comparison JSONL gets additive `explicit_state` and `excluded_by_pattern` for auditability; prior log lacked this evidence.
- **Static PASS:** source created on GitHub, classifiers/fields/test fixture strings present, no new UI controls; all global and UI rules mirrors still current. **NOT RUN:** complete Python compilation, `--ui-self-test`, live Windows WebView2 scan and screenshot comparison, actual classification at runtime, saved category restart, full Copy/Move/Undo on test folders. Status remains **v0.5.25 - Under construction ⚠️**.

## MCC v0.5.24 - radical simplicity acceptance (2026-10-14)

**Policy check:** Current `SOFTWARE_RULES.md` and `UI_UX_RULES.md` in MCC exactly match canonical `karpuzikov/userscripts` at 2026-10-14. Personalization also requires minimum-click, compact, no redundant helper text. Reassessed affected main window, review dialog, and post-Copy/Move result against [UXDT efficiency](https://www.uxdt.nic.in/guidelines/understanding-ux/efficiency-and-intuitiveness/) and [Fluent 2 layout](https://fluent2.microsoft.design/layout).

| Affected workflow/control | Minimal UI requirement / function retained | Desktop acceptance |
| --- | --- | --- |
| Main app chrome | Native Windows titlebar owns name, version and construction status; redundant 58px in-page title/header removed; leave native close and app Close action. | Source check PASS; Windows visual NOT RUN |
| Source folders | Existing and New paths, labels, open-folder icons, Browse, Clear retain distinct purposes. Removed long introductory tutorial and obsolete matcher text. No extra clicks. | Source check PASS; real pick/open NOT RUN |
| Progress / Activity | Keep progress status, percentage, detail, accessible live log; remove only redundant `Working` hint. | Source check PASS; running UI NOT RUN |
| Pattern review | Direct Remix/Live/Keep/Skip per aggregate pattern, 1 click each; single click auto-submits when only one; no save footer, dropdown or new controls. Remove visible instructional paragraph and redundant variant metadata; retain track examples, descriptive accessible button names, focus/pressed states, cancel/Escape and save error recovery. | JS parse/mock PASS; Windows keyboard/hover/error NOT RUN |
| Completed Copy/Move | Keep destination path with adjacent functional folder icon, Undo/Release Map/Close; remove duplicate Open destination footer action and repeated success description. Preserve safety summary. | Source check PASS; destination open & Undo NOT RUN |

**Measured action budget:** One classification click per unresolved aggregate pattern; no additional Save/Continue. One destination-folder click rather than two alternative identical destination open controls. Distinct open-path and Browse remain separate and uncollapsed because they perform different operations. No previously requested functionality removed.

**Verification matrix:** GitHub source readback PASS; two extracted embedded WebView2 JavaScript sections parse via V8 PASS; mocked two-pattern selection and submit PASS; static duplicate-control scan PASS. **Python compile NOT RUN; built-in --ui-self-test NOT RUN; actual Windows WebView2 launch/screenshots/default-small-large DPI NOT RUN; focus/hover/Tab/Enter/Space/Escape NOT RUN; persistence roundtrip NOT RUN; real Copy/Move/Undo NOT RUN.** No Windows screenshots were generated and no real visual acceptance can be claimed. Status remains **v0.5.24 - Under construction ⚠️**.

## MCC v0.5.23 - one-click unusual pattern review (2026-10-14)

Reference: actual user-supplied v0.5.21 screenshot (1287x1055) with one JRMX Club dropdown and redundant Keep all, Skip all, Cancel, Save choices & Continue. UI requirement: classify each **pattern** with ONE click and remember Remix/Live, no redundant actions. UXDT efficiency/clarity and Fluent 2 button/keyboard/accessibility consulted.

| Control | Unique action / saved effect | Pointer / keyboard / visual & error behavior | Validation |
| --- | --- | --- | --- |
| `patternChoice[data-choice=remix]` | Remember the aggregate pattern as Remix; respects Save Remixes. | One click or focused Enter/Space; visible `aria-pressed` selection, 36px height, responsive; staged until all rows chosen, then validated backend saves. | Source check + mocked action PASS; Windows NOT RUN |
| `patternChoice[data-choice=live]` | Remember as Live; respects Save Live recordings. | Same accessible direct choice; mutually exclusive with other row choices, selected styling. | Source check + mocked action PASS; Windows NOT RUN |
| `patternChoice[data-choice=keep]` | Save canonical pattern in Personal Picks. | Direct action, same focus/feedback; can later delete via existing Personal Picks screen. | Source check + mocked action PASS; Windows NOT RUN |
| `patternChoice[data-choice=skip]` | Exclude for this scan only; future scans may ask again. | Direct action, no persistent rule, same focus/feedback. | Source check + mocked action PASS; Windows NOT RUN |
| `patternCancel` / Escape | Cancel pending scan without committing staged answers. | Click, keyboard activation or Escape; closes modal and calls backend `cancelReview`. | Source check PASS; Windows NOT RUN |
| Automatic final-selection submit | Last selection sends all exact keys to existing validating bridge and resumes scan. | No separate Save/Continue or bulk actions. If persistence fails, backend reopens modal with error. | Four-pattern V8 mock PASS; real persistence NOT RUN |

**Removed:** per-pattern dropdown `patternAction`, Keep all, Skip all, Save choices & Continue. Retained existing Personal Picks editor for correction/Forget (no modification to its controls). No changes to audio operations.

**Test results:** GitHub published/readback PASS, both embedded HTML script bodies parse in V8 PASS, isolated 4-row event/auto-submit mock PASS. **NOT RUN:** Python compilation, built-in UI self-test, real Windows WebView2 screenshots compared to reference, hover/focus/Tab/Enter/Space/Escape, small/large window DPI, persisted category after restart, cancellation recovery, end-to-end copy/move/undo. Status: **v0.5.23 - Under construction ⚠️**.

## MCC v0.5.22 - release classification evidence (2026-10-14)

- No GUI controls, icons, layout, interaction routes or persistent settings were changed. Existing Release Map classification labels and optimizer explanations now have richer JSONL diagnostic evidence only.
- **Log audit PASS (independent Python):** 947-record v0.5.20 Datsik JSONL, Disciple 02 release 43 = false Album / selected; 22 tracks with 8 excluded remix rows and 14 eligible, zero confirmed cross-release audio MATCH edges for those 14; Texx Mars release 31 = false Compilation / not selected, alternate release 3 = EP / selected. Datsik artist albums remain independent negative controls.
- **Source readback/static PASS:** `APP_VERSION=0.5.22`; raw `release_classification_tags` per track; `release_type_source` per optimizer release; outdated destructive compilation self-test expectation removed. Retains v0.5.21 full-tracklist inference and nondestructive optimizer semantics.
- **NOT RUN:** full Python compilation, embedded `--ui-self-test`, standalone packaged EXE `--self-test`, Windows WebView2 startup/screenshots/hover/keyboard/resizing, actual Datsik rerun, original tags examination, Copy/Move/Undo end-to-end, cross-volume Move recovery.
- **Acceptance:** verify Disciple displays Compilation and is retained **only if wanted unique audio still needs it**; both Texx releases display EP. Read comparison JSONL's newly exposed raw fields to identify contradictory metadata track by track. Test with disposable library/output paths. Status remains `0.5.22 - Under construction ⚠️`.

## MCC v0.5.21 - release-type evidence in existing Release Map (2026-10-14)

- No new controls. Existing Albums / EPs / Singles / Compilations category labels and release details must reflect **Disciple 02 = Compilation**, **Texx Mars = EP** following reanalysis; do not change keyboard, pointer, scroll, focus and highlight rules.
- Compilation remains a last-resort selected release only when otherwise unique wanted recordings need a carrier; no disappearing tracks or hidden album-family mandate. Existing Copy/Move integrity gates unchanged.
- On Windows verify full 22-track Disciple 02 (8 excluded remixes), both Texx versions, prior INNA Album/EP manual pairing, and normal Datsik album collaboration cases. **Windows GUI/full regression NOT RUN** and version is `0.5.21 - Under construction ⚠️`.

# UI/UX Acceptance Register

**Policy:** [UI_UX_RULES.md](UI_UX_RULES.md) and [SOFTWARE_RULES.md](SOFTWARE_RULES.md) are mandatory for every user-facing screen, panel, modal, widget, context menu, installer, browser toolbar, and interactive console prompt in this repository.

**Status as of 2026-10-12:** **NOT VERIFIED - Under construction ⚠️ for UI acceptance.** This is a documentation and source-inventory checkpoint, NOT a claim that existing applications have been retested or that published stable version labels were changed. No Windows/browser interactive visual run or reference-screenshot comparison has been performed in this audit. Existing stable releases are not silently altered.

Before ANY UI modification, record a control contract for the affected workflows: **control name/ID, unique purpose, click/right-click/hover/keyboard behavior, selection, side effects, persisted data, cancel/error handling, disabled/focus/active states, icon and target geometry**. Eliminate duplicate actions; share design tokens/components.

### Required acceptance process for EACH UI application

1. Run **the actual application**, on its target OS/browser/Picard host, with its real GUI renderer (not mocks).
2. Screenshot each screen and critical state, using at least minimum/default/large viewport and relevant DPI scaling; record image paths and viewport.
3. Compare screenshots to named reference/source UI. Check content hierarchy, alignment, 4px-based spacing, sizing, icon strokes, buttons, image loading, scroll/overlay, accessible labels, and platform expectations.
4. Click/hover/right-click every control; test tab/Enter/Space/Escape, selection/multi-select, focus, resize, scroll, navigation, settings persistence, confirmation/cancel and failure recovery.
5. Include representative end-to-end tasks, empty/large data, missing images/network, interrupted processing, and safe restart. Test any file-changing/destructive action against disposable fixtures.
6. Record **PASS / FAIL / NOT RUN** separately for real rendering, interaction, reference comparison and workflow validation; never equate syntax tests or mocked widgets with a real PASS. Fix all FAIL, complete all NOT RUN before marking UI verified.

| Universal acceptance gate | Status |
| --- | --- |
| UI rules present and required before implementation | PASS - repository-level rule installed |
| Control-by-control inventory and no duplicate actions | NOT RUN |
| Real UI launch with screenshots and reference comparison | NOT RUN |
| Hover, click, keyboard, selection, scroll, resize | NOT RUN |
| Error, cancellation, persistence, restart, recovery | NOT RUN |
| Real host/OS end-to-end workflow and final acceptance | NOT RUN |

## MCC v0.5.20 - unusual pattern review classification controls

| Control | Purpose / interaction / state / persistence | Acceptance |
| --- | --- | --- |
| `patternAction` for each review item | Explicit choice of Skip this run, Keep, Remix (remember), Live (remember). Semantic select with label bound to pattern title, pointer and Tab/arrow support, visible focus. Skip is temporary, other selections persist; no files moved. | Source inspected; Windows UI/keyboard NOT RUN |
| `patternsAll` / `patternsNone` | Select Keep for all / Skip this run for all, no hidden side effect until Save choices & Continue. | Static check PASS; Windows interaction NOT RUN |
| `patternContinue` | Save explicit classifications atomically and resume preflight analysis. Error on persistence failure; avoid falsely claiming saved choice. | Static check PASS; persistence on Windows NOT RUN |
| `categoryKind` / `categoryRemove` in Personal Picks | Existing modal's Saved Remix / Live classifications list. Change category or Forget to re-enable later review; Save commits, Cancel discards; accessible control names, responsive rows. | Static check PASS; Windows interaction NOT RUN |
| Save Remixes / Save Live toggles | Existing global switches control inclusion for newly classified patterns before fingerprint and optimization; no track file mutation or acoustic re-identification. | Source check PASS; real files NOT RUN |

**On-device test requirement:** Compare v0.5.19 screenshot of repeated `JRMX Club` prompt with v0.5.20; confirm dropdown, no clipping at 880px and larger, Tab/arrows/Enter/Escape, Save/Cancel, persistence through restart and second scan, editing/Forgetting, category toggle behavior and safe error. All actual Windows screenshot/interaction acceptance remains **NOT RUN**, so v0.5.20 stays **Under construction ⚠️**.

## MCC v0.5.19 - Album/EP group control contract, 2026-10-14

Affected view: dark WebView2 Release Map, selected release detail panel and full map. No new duplicate controls; existing buttons/select reused.

| Control/state | Purpose, interactions and side effects | Verification |
| --- | --- | --- |
| `albumGroupSelect` | For editable Album **and EP** rows: choose another Album/EP family; keyboard Tab/Arrow keys; displays a disabled explicit empty state if none. A choice alone does not change state. | Source check PASS; real Windows interaction NOT RUN |
| `assignAlbumGroupBtn` | Pointer click or keyboard activation applies path-based family override; updates Release Map grouping immediately; persists only family relation; no audio move; marks state dirty and disables Copy/Move until Re-Analyze. Existing dark button, focus outline and geometry reused. | Source check PASS; real Windows interaction NOT RUN |
| `resetAlbumGroupBtn` | Shown only for user-assigned family; Restore automatic reverses assignment, persists reversal, requires Re-Analyze. | Source check PASS; real Windows interaction NOT RUN |
| Album / EP family card and column | Fingerprint-supported mixed family renders once in Albums section, marked `Album / EP`; original type in release details unchanged. Full map responsive/keyboard/scroll and curved links must remain usable. | Source check PASS; screen/resizing NOT RUN |
| `reanalyze`, `copyPlan`, pending banner | No change to acoustic identity; reanalysis after manual family assignment; Copy/Move remain disabled while dirty or integrity-blocked. | Source contract PASS; actual filesystem safety NOT RUN |

**Required on-device tests:** Run full INNA example scan; inspect grouped cards and `Alright` distinct-track details, tab through both directions, click Restore automatic, Re-Analyze, test dirty-state Copy/Move, resize narrow/wide and capture screenshots. Confirm no non-target file operations. All actual Windows UX acceptance **NOT RUN**; status remains `Under construction ⚠️`.

## UI surfaces: monorepo

**Desktop Python GUI utilities:** Corrupt Image Verifier (`image-tools/corrupt-image-verifier/`); Duplicate Edition Analyzer (latest of versioned `.pyw` sources under `audio-tools/discography-torrent-project/tools/`); ALAC Conversion Automation; AudioChecker Automation; CUE Corrector; Folder Structure Scanner; CUE LOG; DriveV AutoInstaller; Priorities. Treat older versioned files as historical; audit the latest active version of each and applicable active development branches.

**Browser and MusicBrainz userscript UI:** Instagram Full Quality, Spotify Hidden Releases, Genius Lyrics Copier, RuTracker Digital Release Linker, SimpCity Media Link Parser, Beatport - MusicBrainz Importer, MusicBrainz Toolbox, Harmony Toolbox, Apple Music Composition/Lyrics Importer and any other scripts that insert controls, overlays, menus or dialogs. Browser Debug Bridge's `popup.html` and related CSS is in scope. Inspect remaining scripts for controls before excluding them.

**Interactive console/host scripts:** ArchiveMedia, Windows backup/install/requirements tools if they present menus, confirmations, progress or paths; Photoshop scripts if they present dialogs.

### Source audit findings (actual files inspected)

- **FAIL - framework policy:** `Corrupt Image Verifier v1.1.7 NATIVE TEST.pyw`, `Priorities v0.1.0.pyw`, `ALAC Conversion Automation v0.2.pyw`, `AudioChecker Automation v0.1.pyw`, `CUE Corrector - MusicBrainz DiscID 1.3.1.pyw`, `Duplicate Edition Analyzer v0.22.12.pyw` (contains both Qt and Tkinter code), `Folder Structure Scanner.pyw`, `CUE LOG 4.1.pyw`, and `DriveV_AutoInstaller.pyw` still contain Tkinter references. New GUI work must **not** add Tkinter; migration is required to satisfy the no-Tkinter policy. Preserve behavior during migration; no blind framework replacement without rendering and interaction verification.
- **NOT RUN:** Actual Windows/UI reference and real operation tests for every application.

### Project-specific acceptance focus

- **Corrupt Image Verifier:** multiple folders, drag/drop, drive-aware workers, cancellation/child cleanup, image classification and confirmation, preserve relative paths, Undo; visually compare compact native reference.
- **Analyzer:** interactive Release Map, filtering, worker selection/detection, preflight safety, overlays, progress, Copy/Move/Undo and collision/restart scenarios.
- **Media/audio:** file/path picker with folder icon before path, job queue/parallelism, error feedback, dependency bootstrap and process cleanup.
- **MusicBrainz/Beatport/Harmony:** no duplicate import actions, responsive edit-relationships controls, ISRC/barcode selection and warnings, keyboard and retry behavior, unchanged stored links.
- **Browser popups/userscripts:** injected controls in real host DOM, overlay stacking, conflicts with existing site controls, tooltips, focus and responsive behavior. Test real browser + Tampermonkey, not an isolated HTML mock.

## Next action

Fill the control contract and real-world screenshot/interaction matrix for every UI surface above. Fix all FAIL and NOT RUN before declaring UI verified. Preserve software behavior and target-platform compatibility.
