# Music Collection Cleaner (MCC)

**Version: 0.5.174 - Under construction ⚠️**

## Download and run

Source: [Music.Collection.Cleaner.v0.05.174.pyw](Music.Collection.Cleaner.v0.05.174.pyw)

Install Python 3.12 and Microsoft Edge WebView2 Runtime, then double-click the `.pyw`.

## Purpose

Keep every wanted unique recording in the smallest practical retained release set, preferring better sources and preserving the originals until an explicit Copy or Move.

- A **single-window** scan and Release Map.
- **Keep / Skip** for release and track decisions; **Remix / Live** can be checked and unchecked in the same track menu.
- **Re-scan** of classification or planning decisions reuses already verified acoustic identities. Use full **Scan** if source media changed or newly included audio lacks a fingerprint.
- During Copy or Move, the destination path and **Open destination** remain accessible.
- Optional lossless encoding, CUE splitting, tagging, cover art, MusicBrainz enrichment, rip-log and AudioChecker integration retain existing rules.
- Move recycles originals only after completed output; use Copy first.

**Status:** Python regression, Node interaction tests and Chromium embedded-map smoke checks pass in CI. Real Windows/WebView2 and full-library end-to-end acceptance are **NOT RUN**; this candidate is **not stable**.

[Changelog](CHANGELOG.md) · [Prior versions](version-history/) · [Control contract](docs/v0.5.174-control-contract.md) · [Development notes](CONTINUITY.md)
