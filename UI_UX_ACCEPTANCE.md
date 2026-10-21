## MCC v0.5.56 - Freeze list arrangement while details are open (2026-10-21)

- Evidence: two user screenshots of real Windows v0.5.55 (1241x2048), open vs closed right-hand details; Full map shrinks but previously 3-column release groups collapse to a single column. Root cause confirmed in CSS category container queries, compounded by automatic row scrolling.
- Scope: preserve current 52%/720px dock and all controls; freeze pre-dock group/category/Changes column arrangement; resize widths only; remove automatic scroll; restore responsiveness on close. No new controls, no data/backend changes.
- Embedded JS V8 syntax check: PASS. Minimal fake-DOM tests of **extracted actual JS functions** for group count preservation on dock and redraw, category grid, Changes and close/reset: PASS. These are not genuine WebView2 visual verification.
- Full `py_compile`, `--ui-self-test`, native Windows WebView2 at user viewport/DPI, screenshot comparison with supplied v0.5.55 images, hover, click, keyboard, tab/focus, scrolling, resize, refresh and Copy/Move/Undo: NOT RUN.
- v0.5.56 - Under construction ⚠️; not visually accepted or stable. No automatic screenshot runner requested.

## MCC v0.5.55 - Stronger positive-only decoded mastering confirmation (2026-10-21)

Backend-only: no visible UI, controls, focus, layout, hover or accessibility changes. v0.5.53 docked layout preserved.
- Original v0.5.54 JSONL Stronger and vocal/instrumental near-score negative control: INSPECTED.
- Standalone synthetic stereo PCM confirmation prototype, both directions; remaster matches, instrumental fails: PASS (Linux prototype only).
- Full application Python compilation, `--ui-self-test`, real audio decode, 684-track re-Analyze, acoustic-group/optimizer verification, Windows native WebView2, Copy/Move/Undo: NOT RUN.
- No automated UI runner requested; no screenshots or visual acceptance of this build. v0.5.55 remains **Under construction ⚠️**.

## MCC v0.5.54 - Alternate mastering fingerprint detection (2026-10-21)

No user-facing controls, panel layout, style, text, focus or pointer actions changed. The existing docked v0.5.53 release details and dark WebView2 UI are preserved. Source-only audio comparison update.
- Provided v0.5.53 JSONL record pairs 275/622 and 622/623 were inspected; their rejection criteria identified. PASS (diagnosis only).
- Independent synthetic fingerprint distribution and JSONL threshold replay: PASS for arithmetic/selection checks only, not a complete runtime/audio test.
- Full source Python compilation, full `--ui-self-test`, Windows scan, live full-length source audio, group/selection result, native rendered UI and Copy/Move/Undo: NOT RUN.
- No automated visual QA was requested or run. Version 0.5.54 remains **Under construction ⚠️**.

## MCC visual review - user-provided screenshots only (2026-10-20)

## v0.5.44 - Fingerprint authority, 2026-10-20

Backend-only correction to the user's conclusive-fingerprint + <=8-second duplicate rule. No controls, layout, text or interaction changes. Functional/self-test acceptance is separate from native Windows acceptance. No automated visual QA or Actions changes. Status: 0.5.44 - Under construction ⚠️.


## v0.5.43 - Functional correction, 2026-10-20

Preserve the current compact dark WebView2 controls. No new control or layout workflow: audio confirmation runs automatically within the existing Analyze progress/activity presentation. Correct the obsolete Explicit>Clean status from "excluded before audio comparison" to "excluded from selection", since excluded copies are fingerprinted. Existing source-contract checks now assert current Same audio wording and selected-links strokes instead of obsolete UI strings. Python functional/self-tests pass on Linux; this is not visual acceptance. Native Windows UI review is pending user-supplied screenshots at their discretion. Do not run/request automated visual QA. Native file operations and actual collection results remain unverified; keep 0.5.43 - Under construction ⚠️.


The user's latest explicit directive supersedes earlier MCC Playwright/automated visual QA instructions: **do not request, schedule, or require `tests/visual_qa.py`, Playwright, automated screenshot/geometry reports, or associated commands.** The user will send actual Windows WebView2 screenshots when ready. Review those manually upon receipt. Retain earlier runner results as historical evidence only; automation is not a current requirement or user action. Functional `py_compile`, `--ui-self-test`, actual acoustic regression evidence, and disposable file-operation safety checks remain required. Pending native screenshots are not a reason to repeat a screenshot request. No UI code changes at this checkpoint.

---

## MCC v0.5.42 - Acoustic-first comparison / unchanged UI (2026-10-20)

**Scope:** No new visible UI controls, styles or layout changes. The existing Main / Personal Picks / Classify / Release Map control contract from v0.5.41 remains in force. Acoustic grouping can now link tracks despite contradictory metadata, including policy-excluded Live/Remix copies. Renderer must present correct acoustic relationship/status while preserving their excluded retention state and existing accessibility.

**Evidence:** User v0.5.41 JSONL `Music Collection Cleaner Comparison 2026-10-19-17-30-45.jsonl`: Japanese `Pinocchio Story (Freestyle Live from Singapore)` was Live-excluded with 0 fingerprint frames; same-duration ordinary-title file had 2,899 frames; no acoustic comparison. Neither title difference nor exactly matching duration proves the audio is identical.

**Status and test gates:**
- Source-only static patch structure / GitHub commit: PASS (not executable validation).
- Python compilation / full embedded self-test including Pinocchio synthetic fixture: **NOT RUN**.
- Browser Edge Playwright, screenshots and side-by-side inspection: **NOT RUN** for v0.5.42.
- Native Windows WebView2 at 100%/125%, hover, focus, keyboard, resizing, scrolling and dialogs: **NOT RUN**.
- Real-file fingerprint & acoustic comparison of both Pinocchio files, and controls for wrong labels/false positives: **NOT RUN**.
- Disposable Copy/Move/Undo, crash recovery and cross-volume refusal: **NOT RUN**.

**Acceptance requirement:** After fresh clone in `S:\\test\\MCC`, run `py -m py_compile "Music Collection Cleaner v0.05.42.pyw"`, `py "Music Collection Cleaner v0.05.42.pyw" --ui-self-test`, `py tests\\visual_qa.py --browser edge`. Capture screenshots and inspect `report.json`. Scan both physical 808s & Heartbreak editions with Save Live OFF and ON, inspect populated fingerprints and acoustic verdicts, then inspect Release Map relationship and optimization retention. Never infer MATCH only from duration/title. The latest app remains **v0.5.42 - Under construction ⚠️** until actual Windows verification. Do not modify GitHub Actions.

---

## MCC v0.5.41 - Screenshot audit implementation / Visual QA Gate (2026-10-19)

**Input evidence:** User supplied 12 actual Windows WebView2 screenshot views of v0.5.40, spanning Ready/Activity, Personal Picks (~40 rules), Classify patterns, Changes, Full map, release details across widths, hover actions, multi-version badges, rejected release with missing replacements, and full-size 1280px-width track panel. This is stronger visual evidence than the old mocked browser fixture; however **v0.5.41 has NOT been displayed or visually accepted by user**. The prior v0.5.40 Windows `py "Music Collection Cleaner v0.05.40.pyw" --ui-self-test` **PASSED**. The Playwright run for v0.5.40 **FAILED** with startup check expecting `.releaseRow` during the initial `Changes` view, although the real page rendered and contained `.changeRow`. That is a test-harness defect, not evidence that the GUI failed to render. Native WebView2 use on v0.5.40 is evidenced by screenshots, but no systematic interaction or accessibility tests were provided.

**Control contracts audited before implementation:**

| Workflow / control | Distinct behavior and persistence | Pointer/keyboard and visual states | Failure prevention / validation |
| --- | --- | --- | --- |
| Main paths, Browse, Open folder, Clear | Select separate OLD/NEW roots; Browse changes input; Open folder navigates; Clear affects OLD only | Existing input focus and button states remain; native open and Browse actions unchanged | Invalid / nested roots reject analysis |
| Save Remixes / Live / Audio I/O / Logging | Preserve existing analysis policies, persisted settings; independent toggles | No duplicated action; standard disabled states during scan | No modification of decision logic |
| Analyze / progress / Activity | Run analysis; logs appear after first activity; idle no longer shows an enormous blank log card | Activity auto-expands on run and remains visible with content; footer untouched | Errors still show in activity and dialogs |
| Personal Picks Search / Add phrase / Add exact / Edit / Remove / Save / Cancel / Clear | In-memory editing until Save; filter independent of underlying picks; grouped by mode, stable Pattern keys never edited as free text | Search immediate; Edit text focus/select then Enter or blur to commit, Escape cancel; Save persists entire working set | Blank edit disallowed, duplicate mode/value edit disallowed; Cancel discards pending edits |
| Classify patterns / Review pending (N) / Forget / Personal Picks promote | Category manager preserves 3 types Remix/Live/Skip; single pending-review action loads all unresolved entries; Forget/promote remain per saved pattern | Dedicated review button is visible only if pending; no deceptive per-item buttons | Existing bridge validation/persistence and scan gating preserved |
| Release Map Changes / Full map / filter chips / Show all links | Changes vs Full map; filters do not mutate data; all connections suppressed by default until release selected or Show all links is enabled | Links button only in Full map; toggle aria-pressed; selected-release relation strokes emphasized | No changes to optimizer selections or source files |
| Release details / version buttons / track badges / hover R/L/Ignore / Album group | Keep original actions, pattern persistence and hover/focus, full track explanations wrap instead of clipping; smaller amber highlighting | Preserve grid action column, focus behavior, full status in title, native drawer docking; version and album group expand | Re-Analyze required after classification/ignore; do not modify audio during review |
| Copy vs Move / destinations / confirm / Undo | Copy is non-destructive and green. Move is amber, explicitly destructive, same-volume-only atomic rename, durable pre-rename Undo journal | Separate named actions and existing confirmations; disabled until current plan is applicable | Reject cross-drive before moves, reject EXDEV without copy-delete fallback; collision guard, rollback from **prewritten** entries; no source overwrite |

**Changes in GitHub:** `Music Collection Cleaner v0.05.41.pyw` and `tests/visual_qa.py`. No new runtime dependencies; single-file executable architecture and Copy/Move/Undo UI preserved. Added synthetic post-rename failure injection in the `--ui-self-test`; failure should roll back from journaled entries, including a rename not yet marked completed. Browser harness now locates `.changeRow` in Changes view, takes screenshots, switches Full map and locates `.releaseRow`, then tests hovered details at each viewport.

**Acceptance status as of commit:**

| Gate | Result |
| --- | --- |
| User native v0.5.40 UI screenshot review | PASS - screenshot evidence reviewed, issues identified and implemented as v0.5.41 changes |
| GitHub source readback / patch markers | PASS - exact v0.5.41 file, 17 checked source markers |
| Embedded current Release Map JS syntax (V8) | PASS |
| Embedded current Main Window JS syntax (V8) | PASS |
| Python `py_compile` v0.5.41 | NOT RUN |
| Python `--ui-self-test` v0.5.41 (including Move fault injection) | NOT RUN |
| Browser `tests/visual_qa.py --browser edge` with screenshot/geometry tests | NOT RUN |
| Human screenshot comparison of v0.5.41 to user v0.5.40 reference | NOT RUN |
| Native Windows WebView2 v0.5.41 pointer/keyboard/resize/scroll/error/persistence | NOT RUN |
| Real disposable same-drive Move, failure recovery and Undo, plus Copy | NOT RUN |
| Cross-drive Move permission/error handling on Windows test volumes | NOT RUN |

**Known limitation:** Cross-volume Move is intentionally **disabled** rather than risking partial deletion of originals. Use non-destructive Copy when the destination is on another filesystem. This is an explicit temporary safety restriction pending a well-tested transactional cross-drive move design; do not describe it as full cross-volume support. The older unsupported operation was **unsafe** and cannot be grandfathered in. Previous release blockers (cross-volume source safety / full Undo certification, acoustic correctness, native UI acceptance and taxonomy) remain until separately resolved.

**Next user test (fresh folder if the prior clone has been deliberately deleted):** `git clone https://github.com/karpuzikov/MCC.git S:\\test\\MCC`; `cd S:\\test\\MCC`; `py -m py_compile "Music Collection Cleaner v0.05.41.pyw"`; `py "Music Collection Cleaner v0.05.41.pyw" --ui-self-test`; `py tests\\visual_qa.py --browser edge`. Send **native v0.5.41 Release Map with open details at 1280-wide, v0.5.41 Personal Picks with search, v0.5.41 Classify patterns with pending items**, plus browser screenshots/report if generated. Do not use Move on valuable source data pending real Windows acceptance.

--- 

## MCC v0.5.40 - Windows self-test contradiction: Dirty Vibe / Personal Picks (2026-10-19)

**User test evidence:** Windows PowerShell 7.6.7 in `S:\test\MCC`, Python 3.14, fresh Git checkout, `git pull` up to date, `py -m py_compile "Music Collection Cleaner v0.05.39.pyw"` PASS. `py "Music Collection Cleaner v0.05.39.pyw" --ui-self-test` **FAIL** at source line 18248: `RuntimeError: Dirty Vibe remix self-test failed: remix-only audio kept.`. The `py tests\visual_qa.py --browser edge` command was issued, but its output was NOT PROVIDED. Therefore browser visual QA result is **UNKNOWN/NOT VERIFIED**, not PASS or FAIL for that later run.

**Root cause:** The legacy Dirty Vibe *negative* test explicitly supplied `personal_keep_rules=[{"mode":"contains","value":"Jack Beats"}]` then asserted every remix excluded, violating the user-requested Personal Picks positive override. Another negative test supplied `Example Remix` Personal Picks and asserted those same titles excluded. Production `configure_exclusions` appropriately allows Personal Picks to override Save Remixes/Live OFF.

**v0.5.40 correction:** Remove explicit Personal Picks from *negative* remix-only tests (all tracks excluded, remix-only OLD removed and NEW skipped, no release selected). Add separate *positive* tests: Jack Beats two Re-work tracks included while six nonmatching remixes excluded; unrelated albums are not rescued; removal of the preference re-excludes tracks. For generic Remix/Live tests, ensure expected default exclusions and remix-added vocalist exception without Personal Picks, then assert explicitly picked Remix and Live/Remix tracks are kept (not the unrelated live-only track) and revert when preferences are cleared. The production classification algorithm, Release Map UI, audio and file operations were not altered.

**Visual QA runner:** `tests/visual_qa.py` now automatically selects the latest versioned `.pyw` file in a cloned checkout; browser tests do not silently stay on older source versions. Browser runner screenshot/geometry code is unchanged.

**Verification status:** GitHub source and test-file checks only. **NOT RUN** in this environment: full Windows `py_compile`, `--ui-self-test`, latest Playwright runner, screenshot comparison and native WebView2 acceptance. Old Windows test failure remains documented, with v0.5.40 retest pending. `Under construction ⚠️` remains active.

**Required Windows commands:** `git pull`; `py -m py_compile "Music Collection Cleaner v0.05.40.pyw"`; `py "Music Collection Cleaner v0.05.40.pyw" --ui-self-test`; `py tests\visual_qa.py --browser edge`. Report first unexpected FAIL and include `report.json` and images if browser test fails. Do not Copy/Move source music until other known safety blockers are cleared.

## MCC v0.5.39 - Windows test failures and QA harness repair (2026-10-19)

**Actual Windows test supplied by user:** Windows PowerShell at `S:\test\MCC`, Python 3.14, Playwright 1.64.0. `git clone` PASS, `py -m pip install playwright` satisfied, `py -m py_compile "Music Collection Cleaner v0.05.38.pyw"` PASS. `py "Music Collection Cleaner v0.05.38.pyw" --ui-self-test` **FAIL** at line 17677 with `RuntimeError: Release Map UPDATED default/Move confirmation UI regression.`. `py tests\visual_qa.py --browser edge` **FAIL** with `TimeoutError: Page.wait_for_function: Timeout 30000ms exceeded`. Neither visual render nor native WebView2 was proven accepted.

**Root causes:**
- The source self-test erroneously searched the **main-window** HTML for an obsolete exact string `Original release folders relocated.`. The currently implemented safety copy appears in Release Map's Move confirmation. v0.5.39 replaces the stale assertion with the current explicit `Undo Last Run can restore moved folders.` in the correct map HTML; other Move safety assertions remain.
- Playwright opened `file://` with `<script type="module">`, so Chromium could prevent module execution because of local-origin/CORS restrictions. v0.5.39 test harness now intercepts `http://mcc-visual.test/release-map` and fulfills the full unchanged module-based HTML from memory. This is entirely local browser request interception; no external server/network and no music access. A startup failure now captures screenshots and JavaScript/console errors rather than only reporting a bare timeout.

**Static verification on GitHub:** readback shows all nine Move-warning assertion tokens now present in Release Map HTML, both embedded JavaScript scripts parse in V8, app version `0.5.39`, test runner points to v0.5.39 and uses local HTTP route. This is **not** a claim that Python/WebView2/browser tests passed.

**Next Windows verification (PENDING):** run `git pull`, `py -m py_compile "Music Collection Cleaner v0.05.39.pyw"`, `py "Music Collection Cleaner v0.05.39.pyw" --ui-self-test`, `py tests\visual_qa.py --browser edge`. Capture updated report and screenshots, triage any further failures. Human inspection of rendered screenshots and actual Windows WebView2 reference comparison remain **NOT RUN**. Copy/Move/Undo against real sources must not proceed while outstanding safety blockers remain. Status **v0.5.39 - Under construction ⚠️**.

## MCC 2026-10-19 - Visual QA Gate implementation (v0.5.38 remains Under construction ⚠️)

- **Global rule:** canonical `karpuzikov/userscripts/SOFTWARE_RULES.md` and `UI_UX_RULES.md` now require a Visual QA Gate for every UI update; MCC mirrors match. No static JS parse, source review, mock UI or screenshot screenshot alone may be called a completed visual acceptance.
- **Executable browser harness:** `tests/visual_qa.py`, a development-only Playwright runner; default `--browser edge` on Windows. It loads MCC's **existing actual Release Map HTML, CSS and JS** through its standalone `.pyw` source import, injects synthetic Noisia release/track data and a mocked desktop bridge, verifies track grid geometry and button containment, catches hover actions crossing status and saved badge/title overlap, inspects focus/duplicate hover category, keyboard Ctrl+A path selection, album-group disclosure and Escape. It saves `-hover.png`, `-album-group.png` and `report.json` for normal 1486×913, minimum 1050×680, large 1700×1000 and 125% CSS zoom. The injected fixture and bridge never touch actual source media.
- **Commands:** `py -m pip install playwright` then `py tests/visual_qa.py --browser edge`. If no Edge, install Playwright Chromium and use `--browser chromium`. Store reports under isolated `Documents/Karpuzikov Tools/Music Collection Cleaner/testing/visual-qa-<timestamp>/`.
- **Tests PASSED:** source test-harness file uploaded to GitHub; mandatory rules mirrored. No browser execution was actually performed against current MCC source during this checkpoint.
- **Tests NOT RUN:** Execute `tests/visual_qa.py` on current MCC code, inspect resulting screenshots against the user-provided 2026-10-19 Noisia screenshot, actual Windows WebView2 native hover/focus/overlap/keyboard/scroll/resize/restart acceptance, actual app audio and Copy/Move/Undo. WebView2 screenshots and persisted state remain mandatory. **No stable/completed UI claim.**
- **Acceptance detail:** 125% CSS zoom is a browser stress test, **not a replacement** for real 125% Windows DPI/text scaling. Automated bounding rectangles cannot prove typographic balance or icon glyph optical centering, requiring human screenshot inspection. Do not upgrade browser-only PASS to native PASS.

## MCC v0.5.38 - Release Map track/details visual contract (2026-10-19)

**Reference:** User screenshot `image(20261019-092934).png` (1486×913, native Windows WebView2, version 0.5.37): 2017-06-09 `Outer Edges (Noisia Remixes) [VSN030]`, OLD Noisia. Visible problems: all-caps `DUPLICATE / REMOVE`, repeated OLD root plus full release path, redundant Copy path, repetitive Remix badges/Exclusion text, wrapped badge on its own line, and absolutely placed hover actions covering status text. Large Album/EP family chooser obscures track context.

**Purpose/state/control contract (all Release Map details controls; pointer, keyboard and recoverability preserved):**

| Control / region | Unique action and state | Layout, keyboard and safety acceptance |
| --- | --- | --- |
| Release title, status, source | Show release identity and useful plan reason once; compact `Removed · Duplicate`, `OLD · WEB` with no repeated source root | No all-caps status wall, zero-count noise or redundant explanatory labels; title wraps without clipping |
| Keep / Unkeep release | Persist complete-release override; alternate between keep/unkeep | One click; visible focus; triggers dirty plan and forces Re-Analyze before export |
| Ignore / Restore release | Persistent source-release exclusion without affecting other acoustic copies | Separate from Keep; click/Tab/Enter/Space; no plan applied until Re-Analyze |
| Album group disclosure (summary) | Reveal infrequent reassignment action; retains select, Move to group and Restore automatic | Collapsed by default, Enter/Space toggles; selection and reset preserve previous behavior; no direct audio identity change |
| Folder opener and path | Open the release directory; path is selectable without an extra Copy path control | Readable wrapped selectable text, keyboard focus and Ctrl+A/Ctrl+C; folder icon remains distinct and functional |
| Track row | Inspect/highlight verified acoustic group across editions | Row title, duration, versions, status and actions in fixed columns; Enter/Space selects; 100%/125% zoom and long names cannot overlap |
| Saved Remix / Live / Skip badge | Persisted label and direct promotion into Personal Picks | One aligned 24px badge outside wrapping title; focus/Enter/Space; title-independent baseline; badge re-click promotes |
| Hover/focus classification actions | Remix, Live and Skip; replaces different saved category | Direct buttons with min 28px visual footprint, consistent centering, reserved non-overlay action column; if category saved, no duplicate hover action for same category; hover/focus visible; aria-label, click and keyboard |
| Recording-wide Ignore / Restore | Ignore verified acoustic group or restore it, independently of classification | Shares dedicated actions column without collision, labels and source-safe dirty/Re-Analyze guards preserved |
| Versions / Remixes / Live links | Expand alternatives for the specific track | Individual focusable buttons; wrapped within their own reserved column; alternatives and connections unchanged |
| Track status | Explain exceptions and acoustic replacement; default exclusions do not repeat saved badge meaning | Visible status never covered by hover icons; complete reason available in title/tooltip, no loss of warnings |
| Close details, Escape | Close overlay without moving map columns or resetting board scroll | Keyboard and pointer; no reflow or shifted geometry; focus and active states still work |

**Source checks:** The two embedded HTML/JS scripts parse in V8. Static UI contract added to `--ui-self-test` to reject old Copy path, all-caps duplicate prefix, absolute action overlap, missing badge title cell and missing album group disclosure. No acoustic, optimizer, persistent state or file-operation source logic changed.

**NOT RUN / release blocking:** `py_compile` and full `--ui-self-test`; real Windows WebView2 at 100%, 125%, smaller 1050×680 and larger 1500×920 windows, hover/focus/Tab/Enter/Space/Escape, review long multiline titles, path selection/copy, category first/repeated clicks, Ignore/Restore and group reassignment, dark UI screenshots, Copy/Move/Undo disposable. Compare directly with supplied v0.5.37 screenshot. Status **v0.5.38 - Under construction ⚠️**, not accepted.

## MCC v0.5.37 - Decoder startup failure and invalid-map prevention (2026-10-19)

- **Reproduction:** On user's Windows Noisia scan of v0.5.36, all 720 tracks had `[WinError 5] Access is denied`, 0 durations, 0 fingerprints and 0 acoustic comparisons, yet Release Map displayed 87 optimizer-retained releases with thousands of characters of repeated diagnostic text. A plan produced without proven recording identity is invalid and cannot be offered for Copy/Move.
- **v0.5.37 UX contract:** During dependency validation, each external tool must launch successfully under the application's own cleanup Job or fail visibly once with tool name, Windows failure and actionable restricted-launcher guidance. Do not launch the Release Map, show meaningless optimized selections, or enable Copy/Move when execution fails. If 100% of physical files fail decoding even after a successful executable preflight, show one concise batch-level failure (including first affected file) rather than 720 repeated map-row errors.
- **Tests written, NOT RUN:** Synthetic access-denied preflight and total decode failure fixture through `--ui-self-test`. Verify actual Windows blocked-job path, external executable versus source-file ACL errors, error dialog readability, Cancel/Close, source preservation, app restart, subsequent recovery and successful real audio scan before stable. Real Windows visual/interaction acceptance and screenshot comparison NOT RUN. Maintain `Under construction ⚠️`.

## MCC v0.5.35 - Keep release and pattern classification acceptance (2026-10-19)

- **Keep release button:** each release details panel offers direct Keep release or Unkeep release in addition to distinct Ignore/Restore, including a removed duplicate. Keyboard Enter/Space, hover/focus feedback and enabled states must work. Clicking Keep persists a pinned source path but disables stale Copy/Move; after Re-Analyze, the release remains selected and no wanted recording is lost. Keep on a previously ignored release must reconcile Ignore persistence.
- **Track controls:** on hover or keyboard focus, 🇷 Remix, 🇱 Live, 🛑 Ignore appear on each track. Click applies one saved pattern classification without changing audio identity or moving music. A marked or excluded track shows a small badge, clickable to promote to Personal Picks; removal must clear its saved negative rule. Ensure 40px rows still usable at 100%, 125% and reduced window width, with sensible tooltips/aria labels and no accidental track selection.
- **Pattern manager:** Classify patterns is the only editor for Remix/Live/Skip, with no duplicate under Personal Picks. Button always visible, with three saved groups Remix/Live/Skip and pending items. Saved Skip survives restart and stops asking every time. Forget removes the rule; → Personal Picks restores eligibility after fresh Analyze. Verify immediate main-app state synchronization after closing Release Map. Classification changes invalidate prior export plans, including after window X.
- **Release typing:** Noisia Remix by Noisia kept even Save Remixes off; foreign artist remix excluded normally. More than half primary performers distinct from discography root -> Compilation with non-blocking warning; exactly half does NOT trigger. Same-artist best-of -> Anthology. Explicit album, EP, single preserve priority when no stronger opposing evidence. Full Map separate Anthologies/Compilations.
- **Run status:** JavaScript syntax/static/source checks completed. Python compile, embedded runtime regressions and native WebView2/Windows Copy/Move/Undo visual and interaction tests **NOT RUN**. Do not mark stable.

## MCC v0.5.32 - track Ignore scope correction (2026-10-15)

- **Reproduction:** in `Ceinture noire [3616401604548]`, user clicked Ignore for Caméléon 03:27 (credited GIMS;Quincy) and expected every acoustic copy of this recording to be ignored. MCC instead treated only that physical track as ignored and sourced another album's copy. In v0.5.31 `add_persistent_track_skip` stored one `instance_key`; `apply_persistent_track_skips` matched exact paths only.
- **Uploaded v0.5.30 log:** track index 1173 is MATCH (exact audio fingerprints) with indices 312 and 1134. Index 59, Caméléon GIMS 239.866667s versus feat Quincy 207.04s is REJECT at +32.826667s. No reanalysis event in uploaded file; user reports the GUI behavior, root cause proven by source.
- **v0.5.32 logic:** Ignoring any member adds one saved schema-3 group rule (all current group member paths, SHA256 fingerprints and actual durations). Re-analysis and future scans use exact evidence to discover current groups, then ignore all members by `track.group_id`. Legacy v2 path-only rules expand only if their exact instance is present. Restore clears overlapping group rules. Same-title versions and separate featured performances retain independent coverage. Ignoring a release still applies only `blocked_release_ids`.
- **v0.5.32 UI:** `toggleTrack` returns all affected indices; JS patches all corresponding release nodes and active DOM rows without reset of scroll/focus. The visible action remains Ignore/Restore with accessible recording-wide description; statuses indicate global scope and Re-Analyze requirement. Restore is available after reanalysis even when a manual skip has set track excluded.
- **Tests written:** regression under isolated temp state covers three GIMS guest copies, original and Extended, old v2 rule, path/group-ID change between scans, duration guard for same fingerprint, group Restore, overlapping old rules; wired into `--ui-self-test`.
- **Not run:** whole Python compile, embedded `--ui-self-test`, actual Windows WebView2 interactions, real GIMS reanalysis, safe Copy/Move/Undo. Under construction ⚠️.

## MCC v0.5.31 - candidate discovery performance and parity (2026-10-15)

- Problem: user reports the Finding audio candidates stage remains CPU/SSD underutilized with 28 I/O workers. Prior actual GIMS v0.5.29 JSONL: 1,604 tracks, 1,594 fingerprinted, 846,840 duration-neighbor pairs, 801,294 rejected on token evidence, 48,066 routed candidates.
- New algorithm: cache immutable semantic roots and hard version families per track; use exactly equivalent per-pair cache-based semantic conflict. Fast-reject duration-neighbor pairs that cannot satisfy any current strong/weak/weighted shared-token threshold. Do not cache metrics for rejected pairs; remove redundant visited-pair tuples whose sole subsequent purpose is guaranteed by the far-rare duration boundary.
- Safety routes preserved: exact fingerprint, same base title, same album slot, rare far-duration tokens, deterministic shadow sampling. No changes to audio thresholds, selected releases, GUI, original media or Copy/Move/Undo.
- Instrumentation: new JSONL run and summary candidate_routing_seconds, candidate_diagnostic_pairs_cached, and candidate funnel profile/fast-reject counts.
- Regression code authored and hooked into --ui-self-test: semantic-cache parity against previous function, route-token minimum mathematical gate, far-rare duration check. Static source/readback and front-end JavaScript syntax PASS. From old JSONL no token-routed comparison row fell below the 12-token threshold. A separate synthetic benchmark showed faster cached semantic lookups but is NOT a real MCC runtime measurement.
- Release blockers NOT RUN: full Python py_compile, the embedded test, Windows GIMS re-analysis with before/after candidate-group parity and elapsed time, GUI interaction, filesystem Copy/Move/Undo. v0.5.31 - Under construction ⚠️.

## MCC v0.5.30 - CD-first album representation / guest safety (2026-10-15)

- **Goal:** retain fully eligible EU CD `Ceinture noire (Décennie) [EU - 19439710432 - 2019]` in preference to its smaller WEB sibling `[3616402785413]` when all WEB wanted audio is already on the CD. Enforce as an exact solver album-provider requirement, not a loose source score at the end.
- **Grounding:** user-supplied v0.5.29 `Music Collection Cleaner Comparison 2026-10-14-23-52-46.jsonl` includes 1604 tracks; CD release 3 has 57 eligible unique acoustic recordings, WEB Décennie release 27 has 55, all 55 groups matched CD. WEB Ceinture noire release 38 has 40 physical tracks/39 recording groups, including additional wanted `Caméléon` credited `GIMS;Quincy` (3:27, feat sometimes only in ARTIST) and `La nuit c'est fait pour dormir` 4:11. Their presence means CD-only in that family is NOT yet justified without other audio-verified providers.
- **New source behavior:** require CD album anchor when its audio covers a maximal-count WEB edition of that family, or it is a smaller complete core with all maximal-edition extras independently provided outside the family. Avoid CD forcing when a larger Japanese CD does not cover the largest WEB's wanted core tracks. Global acoustic groups remain individually mandatory; a second album remains if it alone provides wanted bonus/featured material. A WEB Deluxe with no standalone extras can still displace an incomplete CD. Features in TITLE/ARTIST cannot be swapped for original tracks in the weaker different-length version-substitution path.
- **UI/control inventory:** zero new buttons, menus, clicks or panels. Existing Release Map details `reason`/decision factors show “CD-priority album anchor”; existing disclosure controls, focus, hover, pointer/keyboard behaviors and fixed overlay remain unchanged. Source media and Copy/Move/Undo unchanged.
- **Tests authored:** actual GIMS-shaped 57CD/55WEB/40WEB fixture with distinct Quincy + La nuit versions; require CD+WEB when both extras album-only, CD+WEB when only Quincy has standalone single, CD+two independent singles when both have sources; 14CD/18WEB Deluxe with unavailable bonus tracks must keep WEB only; GIMS feature in ARTIST vs TITLE must never be a replaceable Version, even with strong fabricated similarity. Existing Starboy CD+Singles and blocked Single, INNA Japan, INNA Club Rocker 2011 WEB/CD/Japanese CD and Skrillex no-churn fixtures remain in place.
- **Executed:** GitHub write/readback verification and local logic-only Python model (CD versus WEB subset; complete and incomplete CD and Starboy missing single provider) PASS. **NOT executed:** real complete Python file `py_compile`, embedded `--ui-self-test`, Windows GUI visual/interaction tests, real acoustic rerun, Copy/Move/Undo. No stability claim. Keep **v0.5.30 - Under construction ⚠️**.

## MCC v0.5.29 - stable map geometry on details open/close (2026-10-14)

- **User evidence:** in normal Release Map the release columns occupy the whole board, but opening the old 52vw flex sibling narrowed board viewport, triggering `@container release-map-viewport (max-width:1750px)` and reflowing columns; closing or clicking same release again reversed the reflow and lost visual context.
- **UI correction:** details now position:absolute overlay in the `#main` relative viewport; `#boardViewport` remains flex:1 at constant width. The drawer docks away from the selected release row based on current bounds and drawer width. Repeated click on selected release does not close panel; Close × / Escape remain functional. Existing selected row remains highlighted. No new controls, clicks, workflows or data changes.
- **Automated checks executed:** complete extracted Release Map JS syntax parsed (PASS); mocked 1920px board confirms right-side release -> left-docked drawer and left-side release -> right drawer (PASS); GitHub source file readback matches (PASS).
- **Release blockers NOT RUN:** real Windows WebView2 rendered screenshots, interactive resize/hover/focus/keyboard/scroll/retained selection checks, Python compilation, embedded `--ui-self-test`, genuine audio scan, Copy/Move/Undo. Under construction ⚠️.

## MCC v0.5.28 - advisory correction and explicit reasons (2026-10-14)

- Mapping: `ITUNESADVISORY`/RTNG/ADVISORY `0=Unknown`, `1=Explicit`, `2=Clean`; `EXPLICIT=0` also not proof of Clean. Positive content and explicit descriptors may still positively classify. E/C markers are placed beside track titles, Unknown has no marker; accessible title and ARIA label indicate classification based on metadata.
- Exclusion status now reveals `Explicit > Clean - excluded before audio comparison` rather than "Skipped by active options". Other cases identify Remix, Live or stored pattern. Replaced "Only eligible copy" / "Only eligible source" prose with accurate source/coverage distinctions.
- Added embedded classification, no-info vs confirmed Clean, explicit rule and front-end contract tests. JavaScript smoke test passed for status mapping; embedded Python `--ui-self-test` and actual Windows UI are pending. Old comparison log contains final classification but not raw field value; new log adds `explicit_advisory_tags`.
- Crucially `Explicit>Clean` is still applied pre-fingerprint for positively classified records. Its separate false-positive P0 investigation has NOT been declared solved.

## MCC v0.5.27 - full-scan edition status regression (2026-10-14)

- **Affected control:** existing Release Map per-track status text only (including its existing tooltip); no additional button, panel, menu or click. Existing keyboard and pointer semantics unchanged.
- **Verified data source:** user's attached `Music Collection Cleaner Comparison 2026-10-14-09-22-38.jsonl` produced by v0.5.26: 19 La même tracks, 17 excluded as `Explicit>Clean` before fingerprinting; CD 61 and Single 280 have acoustic MATCH; WEB 1147 was excluded. Laissez-moi tranquille has 13 eligible copies and 12 confirmed MATCH comparisons from CD 64.
- **Behavior:** count other scanned release IDs on equal normalized track title/performer and duration within 1 second. Promote an edition into "Audio match" only when both tracks are eligible and share actual acoustic `group_id`; show excluded/different-group metadata references as "audio unverified". Read counts across ALL releases, not just selected. Track's status no longer asserts "Only eligible copy" because its optimizer coverage is essential. Do not change `unique_to_release` calculations or the optimizer.
- **Regression fixtures authored:** selected CD and selected excluded WEB, plus unselected same-acoustic-group version, assert one unverified and one audio-confirmed other edition; prevent excluded audio from acquiring a group; assert data propagates to Release Map. Separate analysis against supplied v0.5.26 JSONL PASS (La même: 1 verified + 17 unverified; Laissez-moi tranquille: 12 verified + 0 unverified).
- **Not run:** embedded `--ui-self-test`, complete Python `py_compile`, Windows WebView2 visual and keyboard testing, real fresh GIMS scan, persistence, Copy/Move/Undo. These remain release gates. Explicit>Clean false exclusions are still a separate P0 problem. **v0.5.27 - Under construction ⚠️**.

## MCC v0.5.26 - closeout BLOCKER: La même Explicit/Clean cannot be assumed (2026-10-14)

- **User correction:** "there is no La même explicit version in existance". Earlier assistant attribution to a real Explicit `La même` was unsupported; retract it. The attached v0.5.24 comparison log does not contain per-track `explicit_state`, `excluded_by_pattern`, or raw advisory tag values to prove the cause. Do not claim an actual Explicit version exists.
- **Observed:** 19 logged tracks titled `La même` across GIMS releases; 17 have `excluded_from_coverage=true` and zero fingerprint frames; 2 are eligible with 1,594 frames (retained Décennie EU CD and non-retained single). The separate retained WEB Ceinture noire album's track is excluded before comparison. Aggregate 86 `pattern:Explicit>Clean` exclusions in run, but not individually linked; this aggregate is NOT per-track proof for `La même`. Consequently the current eligible-only UI status could be produced by a faulty underlying filter and must not be called the correct music-library outcome.
- **Source risk:** `explicit_state` infers from ffprobe advisory tags plus track/file/album text, and `apply_explicit_over_clean_policy` removes same normalized title/artist Clean copies before audio matching if ANY track is marked Explicit. Incorrect/mismatched advisory metadata may falsely imply a separate Explicit recording and discard original-copy evidence.
- **Required acceptance:** inspect original advisory tag values on `La même` from all relevant releases, identify exact exclusion trigger and alleged Explicit counterpart, avoid speculative identity claims and premature exclusion, add negative false-Explicit regression and positive genuine Explicit/Clean regression, rerun on Windows and confirm no acoustic coverage lost. This is a release blocker. UI label polish is not resolution. Full Python, Windows WebView2 and Copy/Move/Undo tests **NOT RUN**; current version **0.5.26 - Under construction ⚠️**.

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

