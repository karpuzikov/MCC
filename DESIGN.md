# MCC

Design system for Music Collection Cleaner (karpuzikov/MCC). Built on the VoltAgent design language (near-black canvas, hairline edges, Inter + mono) and reshaped through review into a dense, tool-first Windows UI with a teal accent.

Reference mockup (1024×768 and 1920×1080, Main + Release Map): https://claude.ai/artifact/JeQLrRKajL14iEBXzWBqYd

## Rules

1. **Dark only.** `canvas` #101010 is the only surface.
2. **Teal is the accent** (`primary` #2bc4d4): primary buttons, logo, selection, essential tracks, links, star. `primary-soft` #6fd8e3 for the focus ring.
3. **Green means "added"** (`status-added` #00d992) and nothing else: `+` / `↑` at the end of a release row and the Added/Upgraded chips.
4. **Equal padding on all sides inside every element.** Buttons, chips, inputs, selects, paths 4px; primary buttons 5px; bars and panels 8px; release board 4px. Line-height = font-size on buttons and fields so the padding reads equal. No fixed control heights: height = content + padding.
5. **Text buttons are outlined** (1px `hairline`, radius 6px, `button` 14px). **Icon buttons are never outlined**: no border, no padding, SVG viewBox cropped to the drawn shape, all icons 14px tall, 1.5px non-scaling stroke.
6. **Lines go between elements, never around them.** 1px `hairline` vertical line between neighbours in a row, horizontal line between stacked items. No line on icon buttons, none beside flex spacers. No boxes or fills around content groups.
7. **Every pixel goes to content** (release/track titles, folder names, paths). 8px row gap, 4px gap between track number and title, no decorative spacing.
8. **Never truncate.** No ellipsis, no "…" in labels; long names and paths wrap.
9. **No explanation text.** Guidance comes from layout, step labels and tooltips only.
10. **No Close buttons.** The window's title-bar ✕ closes.
11. **No pill radius on anything with padding** (radius 6px), so equal padding stays visible.

## Colors

| Role | Token |
| --- | --- |
| Surface | `canvas` #101010 · `canvas-soft` #1a1a1a (inputs, paths, menus, panels, essential highlight) |
| Lines | `hairline` #3d3a39 |
| Text | `ink` #f2f2f2 · `body` #bdbdbd (paths, secondary) · `mute` #8b949e (labels, skipped) |
| Accent | `primary` #2bc4d4 · `primary-soft` #6fd8e3 · `on-primary` #101010 |
| Status | `status-added` #00d992 |

## Typography

Inter (bundled woff2) for everything; JetBrains Mono for durations, activity log, track numbers and version tag. Base size is **14px**; secondary is **12px**.

| Style | Size / line | Weight | Use |
| --- | --- | --- | --- |
| `app-title` | 36/36 | 700 | App name on a home screen |
| `page-title` | 24/24 | 700 | Window title (Release Map, Settings) |
| `card-title-lg` | 18/18 | 700 | Large card title |
| `card-title` | 16/16 | 600 | Panel title (details release name) |
| `subtitle` | 16/22 | 400 | Page subtitle |
| `step-label` | 14/14 | 600 | "Step 1: Select folders", setting labels |
| `tab` | 14/14 | 600 | Tabs, view switches |
| `button` | 14/14 | 600 | Every button label |
| `body` | 14/20 | 400 | Inputs, dropdowns, paths, toggles, folder and album names |
| `row-title` | 14/18 | 600 | Track title, release group title |
| `mono-body` | 14/18 | 400 mono | Durations, activity log |
| `secondary` | 12/16 | 400 | Artist, dates, card meta, notes |
| `table-header` | 12/12 | 600 caps | Column headers, section labels |
| `secondary-strong` | 12/12 | 700 | Format and meta emphasis |
| `mono-small` | 12/12 | 400 mono | Track numbers, version tag |
| `chip` | 11/11 | 500 | Chips, filter pills, Remix/Live notes |
| `micro` | 10/10 | 400 | Time under date; sparingly |

Buttons, chips and inputs use line-height = font-size so the 4px equal padding reads equal on all sides.

## Layout

**Main window** — top bar (logo, name, version, Under construction) · Step 1: Select folders (rows: ★ | role label 120px | path | Browse icon | Show in Explorer icon | ✕; then + Add folder | Remixes | Live recordings | Keeps and Skips | Advanced ▸) · Step 2: Scan selected folders (Scan + progress) · Step 3: Open the map (teal Release Map → | Undo last export) · Activity log fills the rest. The next step's button is the teal one.

**Release Map** — top bar (logo, Release Map, version, Under construction, Search) · toolbar: Step 4: Check the scan result | Changes / Full map / All links | + Added · ↑ Upgraded · ↔ Replaced · ~~Removed~~ · ⊘ Ignored | Re-scan · board · details panel · footer: Step 5: Save results | Copy into/Move into toggle | destination | Browse | Show in Explorer | teal Copy/Move; second row Encode to + format | AudioChecker | Split CUE.

- **Board:** 2 columns at ≤1280px CSS (Albums | Singles + Compilations stacked), 3 columns at ≥1600px. Group title `row-title` 14/600 `ink`; folder rows indented 12px below; 12px between groups; 1px lines between rows; square corners.
- **Release row:** folder name exactly as on disk. Skip = `mute` + line-through; Keep = plain `ink`; Add = `ink` + green `+` at end; Upgrade = green `↑`; Replace = white `↔`. Full path in tooltip.
- **Details panel** (360px / 520px): release name + ✕; path | Show in Explorer | Ignore; tracks grouped under DISC N headers, numbers restart per disc; Versions N / Remixes N / Live N outlined buttons open an inline list (title · length · Retained/Available/Ignored); grey Remix/Live note; ⋯ menu (Mark Remix/Live, Ignore, To Personal Picks); essential = teal on `canvas-soft`; gem = essential + teal diamond.

## Scaling

All sizes are CSS px. MCC applies a WebView2 ZoomFactor so 1 CSS px = 0.2645 mm on every monitor (physical size from WMI/EDID, native resolution, Windows scale), clamped 0.75–2.0, recomputed on monitor/DPI change, multiplied by a user "UI size" (80–150%) in Advanced. Unknown display size → Windows scaling and a log warning. Minimum window 1024×720 CSS px.
