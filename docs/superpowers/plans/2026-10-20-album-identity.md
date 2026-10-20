# MCC album identity correction implementation plan

> For agentic workers: use the executing-plans workflow for matching; the independent hover change is delegated in an isolated branch. User explicitly authorized completing all fixes while AFK.

Goal: retain equivalent CD album anchors, remove falsely added WEB duplicates, preserve genuine distinct versions and saved Ignore, and show one hover Ignore/Restore action.
Architecture: preserve the single-file WebView2 app. Use globally and locally consistent fingerprints for identity, retain all coherent negative evidence during grouping, verify actual silent boundary padding before normalizing identity duration, then run existing full-release optimizer.
Spec: latest user requests and RULES.md; no automated visual QA or workflow changes. Version 0.5.45 remains Under construction.

## Constraints and review focus
- Existing 0.5.44 source and audio originals remain intact; no source write or dependency changes.
- Broader mastering tolerance must retain known instrumental/alternative-vocal/Wolves/internal-section negatives.
- All direct rejected pairs remain separate; fix consistent positive evidence rather than overriding a negative through a transitive path. Duration diameter remains <=8s after verified padding only.
- Long audible edits must remain separate; only independently decoded silence may normalize identity durations.
- Big Brother's persisted Ignore must remain effective; account for normalization only with verified evidence.
- One Ignore/Restore hover action; retain R/L and saved Skip management. Native Windows visual acceptance remains pending.

## Tasks
1. Write/observe failing tests for target log profiles and authoritative Love Lockdown triangle. Implement consistent fingerprint evidence and grouping/logging. Run all safety tests.
2. Write/observe failing PCM fixtures for >8s silent tails versus audible material. Implement read-only padding verification; integrate normalized duration and diagnostics. Re-test genuine distinct edits.
3. Integrate independently tested hover cleanup; preserve Skip category persistence and recording-wide Restore.
4. Replay supplied scan against frozen baseline and new policy, explicitly distinguish cached-metric replay from actual new audio. Verify CD anchors and all wanted group coverage.
5. Run compile, all unittests and built-in self-test; independent whole-change review, fix blockers, update canonical continuity/rules/README, publish through leased GitHub update and verify exact content.

## Ledger
- Baseline 31 tests pass; v0.5.44 replay exactly reproduces 75 releases / 600 tracks / 509 wanted groups.
- UI branch removes duplicate Stop hover action only; Skip still learned in Classify patterns.
- Ruling: authorizing AFK fixes includes isolated work and publication; no additional approval pause.

- Matching and padding integration complete; root integrated independently developed UI/padding patches. Full integrated 60-test suite and --ui-self-test pass; two additional real-decoder pipeline regressions added.
- Production-policy replay: 65 releases / 469 tracks, 402 wanted groups covered, 9 exclusions / 1 manual Ignore. All four redundant WEB albums drop; Gone remains conditional on real decoded proof.
- Whole-change review active; publish only after any blocking findings and final checks are resolved.

- Review reproduced competing evidence splitting an authoritative pair. Fixed by resolving coherent fingerprint units first, then allowing weaker edges to join whole units subject to every direct veto and duration bound; new regression observed failing first.
- Final production-priority replay remains 65/469 with 402 wanted groups covered and no rejected-pair violations. 63 functional regressions and the full self-test pass.

- Final independent review approved source blob `cb7732ff76dd10223f27cdcf0dd6f62ad65ea8c0`, with no remaining findings. All 63 tests and 500 graph invariants independently pass. Compact component recursion fixes the identified scaling cost.
- Publication uses the canonical remote base tree and an expected-SHA lease, preserves historical sources/workflows, then verifies every changed GitHub file against its prepared Git blob. Native Windows/user-audio acceptance remains pending.
