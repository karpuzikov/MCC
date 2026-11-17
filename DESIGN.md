# DESIGN.md - VoltAgent

A developer-focused look: one near-black canvas, one electric-green accent, hairline-bordered cards, Inter paired with a mono face.

> Source: an inspired interpretation of VoltAgent's design language from [awesome-design-md](https://github.com/VoltAgent/awesome-design-md/tree/main/design-md/voltagent). Not an official VoltAgent asset; no logo files are included.

## Key characteristics

- **One accent.** `primary` (#00d992) carries every CTA, status pill, live indicator. No second accent.
- **One surface.** `canvas` (#101010) is the only page background. Dark only, no light mode.
- **Hairlines are elevation.** Cards, buttons and inputs get 1px solid `hairline` (#3d3a39). No fills, no shadows.
- **One ornament.** A 1px dashed `divider-dashed` rule between sections.
- **Two faces.** Inter for text; JetBrains Mono (SF Mono substitute) for anything you could type at a terminal: paths, logs, counters, versions.
- **Tight corners.** 6px buttons and inputs, 8px cards, pills only for tags.

## Content

- Sentence case everywhere. Uppercase only in eyebrows (Inter 600, 2.52px tracking).
- Numbers render in mono.

## Colors

| Token | Value | Use |
| --- | --- | --- |
| `primary` | #00d992 | Primary CTAs, live dot, progress fill, NEW, selected border |
| `primary-soft` | #2fd6a1 | Ghost-button labels, focus ring (2px) |
| `primary-deep` | #10b981 | Inline links |
| `on-primary` | #101010 | Text on `primary` |
| `canvas` | #101010 | The only page surface |
| `canvas-soft` | #1a1a1a | Inputs, paths, code, log |
| `canvas-text-soft` | #f5f6f7 | Text inside `canvas-soft` code/paths |
| `ink` | #f2f2f2 | Default text |
| `ink-strong` | #ffffff | High-emphasis text |
| `body` | #bdbdbd | Secondary text |
| `mute` | #8b949e | Captions, fine print |
| `hairline` | #3d3a39 | 1px edge of every card, button, input, row divider |
| `divider-dashed` | rgba(79,93,117,.4) | 1px dashed rule between sections |

No error/warning palette: success uses `primary`, missing or removed states use `mute`.

Contrast on `canvas`: `ink` 17:1, `body` 10.1:1, `mute` 6.2:1, `primary` 10.3:1; `on-primary` on `primary` 10.3:1. `hairline` is 1.7:1: an input also needs its placeholder and the `primary-soft` focus ring to read as a control.

## Typography

- **Inter** 400/500/600/700; **JetBrains Mono** 400/500. Both bundled as woff2 (`@font-face`), never loaded from the system.

| Style | Spec | Use |
| --- | --- | --- |
| `display-lg` | 36/40 400 | Section headlines |
| `display-md` | 24/32 700 | Detail titles |
| `display-sm` | 20/28 600 | Card titles |
| `eyebrow` | 14/20 600, uppercase, 2.52px | Section labels (12/16 for small) |
| `body-md` | 16/26 400 | Paragraphs |
| `body-sm` | 14/20 400 | UI text, inputs |
| `caption` | 12/16 400-500 | Field labels, fine print |
| `button-md` | 16/24 600 | Button labels |
| `code` | 13/18 mono | Paths, log, counters, version, filter pills |

## Layout

- 4px base. Spacing 2, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64.
- Window padding 32px; card padding 24px.
- Buttons and inputs 44px tall (12px padding + 24px line); main footer buttons 48px.

## Radius

`radius-sm` 6px buttons and inputs · `radius-md` 8px cards and dialogs · `radius-pill` 9999px tags, filter chips, OLD/NEW legend only.

## Elevation

Flat. Every card and button: 1px solid `hairline` on `canvas`. A selected item gets a 1px `primary` border. No shadows, no gradients.

## Components

- **Buttons:** primary (green fill, `on-primary` label), outline (canvas + hairline), ghost (`primary-soft` label, no border). `button-md`, 0 16px, 6px radius.
- **Segmented control:** hairline frame, 2px inset, 36px segments; active segment `canvas-soft` + `ink-strong`.
- **Tag / pill:** canvas, hairline, `body-sm`, 4px 12px, pill radius. Live/status dot 6px `primary`.
- **Card:** canvas, 1px hairline, 24px padding, 8px radius.
- **Input / path:** `canvas-soft` fill, hairline, 44px, 6px radius; paths in mono.
- **Checkbox:** 18px, hairline, checked = `primary` fill.
- **Icons:** inline line SVGs (24px grid, 1.8 stroke, `currentColor`), `body` or `ink`; green only for live/status/active. No emoji.

## Release Map change kinds

| Kind | Glyph | Color |
| --- | --- | --- |
| Added | + | `primary` |
| Upgraded | ↑ | `primary-soft` |
| Replaced | ↔ | `ink` |
| Removed | − | `mute`, line-through |
| Ignored | ⊘ | `mute` |

## Do / Don't

**Do** reserve green for CTAs and live status · keep `canvas` the only surface · build cards with hairlines · pair Inter with mono · 6px buttons, 8px cards, pills only for tags · keep all colors as CSS variables in one shared stylesheet.

**Don't** add a light mode · use green as body text · add shadows or gradients · hardcode colors per widget · use emoji as icons.
