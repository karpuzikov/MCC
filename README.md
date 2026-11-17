# Music Collection Cleaner (MCC)

**Version: 0.5.123**

## Download and run

1. Run once in a terminal (installs Python and WebView2; MCC downloads the rest by itself on first start):

```
winget install -e --id Python.Python.3.12 && winget install -e --id Microsoft.EdgeWebView2Runtime
```

2. Download the `.pyw` file from the **[latest release](https://github.com/karpuzikov/MCC/releases/latest)**.
3. Double-click it.

## What it does

**Main idea:** keep each unique song while keeping the total file count as low as possible.

- Keeps the best edition of each album
- Preserves unique songs
- Keeps the total file count as low as possible
- Preserving remixes and live versions is an option
- You can manually pick which songs to keep

When the same songs exist in several versions, MCC prefers the better source, best first:

1. CD: 100% - Log - Cue
2. CD: 100% - Log
3. CD: <100% - Log
4. WEB/Digital

## Safety

Analysis never changes your files. Copy and Move run only when you click them. Use **Copy** first.

[Changelog](CHANGELOG.md) · [Previous versions](version-history/) · [Development notes](CONTINUITY.md)
