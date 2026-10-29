# Music Collection Cleaner (MCC)

**Version: 0.5.60 - Under construction ⚠️**

Music Collection Cleaner compares existing music releases with new ones, finds the best combination of editions, and helps preserve every wanted unique recording while removing unnecessary redundancy.

## Download and run

**[Music Collection Cleaner v0.05.60.pyw](Music%20Collection%20Cleaner%20v0.05.60.pyw)** - latest single-file Windows Python application. **Under construction ⚠️** until actual Windows WebView2 testing. Earlier source versions remain available.

Open with Python 3 on Windows 11 (or run from a console with `python "Music Collection Cleaner v0.05.60.pyw"`). The application checks or installs supported dependencies. The GUI uses Microsoft Edge WebView2 through pywebview; it is not a terminal-based replacement.

Source-level regression checks: `python "Music Collection Cleaner v0.05.60.pyw" --ui-self-test`. `--self-test` additionally requires a packaged standalone EXE.

[Previous versions](archive/) · [Version history](CHANGELOG.md)

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
