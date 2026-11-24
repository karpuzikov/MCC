# Music Collection Cleaner (MCC)

**Version: 0.5.184**

## Download and run

Download [Music Collection Cleaner v0.05.184.pyw](https://raw.githubusercontent.com/karpuzikov/MCC/main/Music%20Collection%20Cleaner%20v0.05.184.pyw) and double click it.

## What it does

**Main idea:** keep each unique song while keeping the total file count as low as possible.

- Keeps the best edition of each album
- Preserves unique songs
- Keeps the total file count as low as possible
- Preserving remixes and live versions is an option
- You can manually pick which songs to keep
- Star a folder (**Mark as main folder**) to keep it as the base; other folders are compared against it
- Copy and Move also name folders by MusicBrainz, tag, encode to ALAC or FLAC, split CUE images and write AudioChecker logs (options: Encode, Format, AudioChecker, Split CUE are in the Release Map)

When the same songs exist in several versions, MCC prefers the better source, best first:

1. CD: 100% - Log - Cue
2. CD: 100% - Log
3. CD: <100% - Log
4. WEB/Digital

## Safety

Scanning never changes your files. Copy and Move run only when you click them. Use **Copy** first. Move sends originals to the Recycle Bin.

[Changelog](CHANGELOG.md) · [Previous versions](version-history/)
