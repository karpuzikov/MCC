# MCC

Design system for Music Collection Cleaner (karpuzikov/MCC). Built on the VoltAgent design language (near-black canvas, hairline edges, Inter + mono) and reshaped through review into a dense, tool-first Windows UI with a teal accent.

Reference mockup (1024×768 and 1920×1080, Main + Release Map): https://claude.ai/artifact/JeQLrRKajL14iEBXzWBqYd

## Rules

1. **Dark only.** `canvas` #101010 is the only surface.
2. **Teal is the accent** (`primary` #2bc4d4): primary buttons, logo, selection, essential tracks, links, star. `primary-soft` #6fd8e3 for the focus ring.
2a. **Warning triangles ⚠︎ are yellow** (`status-warning` #f5c542) wherever the app draws them (release rows, details notices). The title-bar triangle is drawn by Windows and stays monochrome.
3. **Green means "added"** (`status-added` #00d992) and nothing else: `+` / `↑` in the 12px indent left of a release row's folder name, and the Added/Upgraded chips.
4. **One size system, nothing else.** Spacing tokens are `--space-1` 4px, `--space-2` 8px, `--space-3` 12px; the only extra values are `--pad-tight` 2px (Versions/Remixes/Live panel, marker boxes) and `--pad-primary` 5px. Window and panel edges 8px. Siblings 8px apart, items inside one group 4px apart (view buttons, chips, marker boxes). A divider sits centred in the 8px gap.
5. **One control height: 24px** (`--control-height`). Outlined text button = 14px line + 4px padding + 1px border. Primary button = 14px line + 5px padding, no border. Inputs and selects take the same 24px (native inputs ignore small line-heights, so they use the token). Every control in a row is 24px, so rows never jump.
6. **Chips and tag buttons are 18px tall**: 11px/500 text on an 8px line (the cap height), 4px padding on every side, 1px border. This equals one body line, so a track row with a Remixes chip is as tall as one without. Marker boxes in the details panel use the same 11px/8px line with 2px padding.
7. **Every single-line row is the same height** (27px: 18px line + 2×4px padding + 1px divider). Rows always reserve their divider (transparent on the first), so heights never differ by a pixel.
8. **Equal padding on all sides inside every element**, measured from visible glyph edges. Marker boxes carry a per-label horizontal trim (`--mkbox-pad-*`) so the gap to the glyphs is equal on all four sides.
9. **Text buttons are outlined** (1px `hairline`, radius 6px, `button` 14px). **Icon buttons are never outlined**: no border, no padding, SVG viewBox cropped to the drawn shape, all icons 14px tall, 1.5px non-scaling stroke.
10. **Lines go between groups, never around them.** 1px `hairline` vertical line only between functional groups in a row (tabs | chips, Scan | progress); never inside a group (a label and its field, checkboxes, selects). Horizontal line between stacked items. No boxes or fills around content groups.
11. **Every pixel goes to content** (release/track titles, folder names, paths). 8px row gap, 4px gap between track number and title, no decorative spacing.
12. **Never truncate.** No ellipsis, no "…" in labels; long names and paths wrap.
13. **No explanation text.** Guidance comes from layout, step labels and tooltips only.
14. **No Close buttons.** The window's title-bar ✕ closes.
15. **No pill radius on anything with padding** (radius 6px), so equal padding stays visible.

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
| `step-label` | 14/18 | 600 | "Step 1: Select folders", setting labels |
| `tab` | 14/14 | 600 | Tabs, view switches |
| `button` | 14/14 | 600 | Every button label |
| `body` | 14/18 | 400 | Inputs, dropdowns, paths, toggles, folder and album names |
| `row-title` | 14/18 | 600 | Track title, release group title |
| `mono-body` | 14/18 | 400 mono | Durations |
| `mono-log` | 12/16 | 400 mono | Activity log (always visible; a 48px canvas above it shows one animated scene per scan stage) |
| `secondary` | 12/16 | 400 | Artist, dates, card meta, notes |
| `table-header` | 12/12 | 600 caps | Column headers, section labels |
| `secondary-strong` | 12/12 | 700 | Format and meta emphasis |
| `mono-small` | 12/12 | 400 mono | Track numbers, version tag |
| `chip` | 11/8 | 500 | Chips, tag buttons, details marker boxes, Remix/Live notes |
| `marker` | 10/10 | 500 | Row markers WEB/CD/CUE/LOG 100% |
| `status-symbol` | 11/18 | 500 | `+` `↑` `⊘` in the row indent, at least 2px clear of the name |
| `micro` | 10/10 | 400 | Time under date; sparingly |

Buttons use line-height = font-size so the padding reads equal; chips use the 8px cap-height line.

## Layout

**Main window** — top bar (logo, name, version, Under construction) · Step 1: Select folders (rows: ★ | role label 120px | path | Browse icon | Show in Explorer icon | ✕; then + Add folder | centred: Keep Remixes | Keep Live recordings | Keeps and Skips) · Step 2 · Step 3 · stage scene + Activity log · Audio I/O workers | UI size | Logging | Open logs · Step 2: Scan selected folders (Scan + progress) · Step 3: Open the map (teal Release Map → | Undo last export) · Activity log fills the rest. Add folder, Scan, Release Map, Re-scan and Copy/Move share one teal style; Undo last export and Keeps and Skips are outlined. Scan, Add folder, Keeps and Skips and the folder settings are disabled (dimmed to 45%) while a scan runs or the Release Map is open.

**Release Map** — top bar (logo, Release Map, version, Under construction, Search) · toolbar: Step 4: Check the scan result | Changes / Full map / All links | + Added · ↑ Upgraded · ~~Removed~~ · ⊘ Ignored | Re-scan · board · details panel · footer: Step 5: Save results | Copy into/Move into toggle | destination | Browse | Show in Explorer | teal Copy/Move; second row Encode to + format | AudioChecker | Split CUE.

- **Board:** 2 columns at ≤1280px CSS (Albums | Singles + Compilations stacked), 3 columns at ≥1600px. Group title `row-title` 14/600 `ink`; folder rows indented 12px below; 12px between groups; 1px lines between rows; square corners.
- **Release row:** folder name exactly as on disk, starting at the same x on every row. Status symbol (`+` or `↑` green, `⊘` grey) sits in the 12px indent left of the name and adds no width. Skip = `mute` + line-through; Keep = plain `ink`. Right side: markers `WEB/CD/CUE/LOG 100%` (10px/500, no spaces around the slashes, LOG shows the score only when scored); related markers `primary`, unrelated and slashes `mute` at 45%; Skip rows 50% lit / 25% unlit. REPLACE from the engine is shown as Upgrade. Full path in tooltip.
- **Details panel** (360px / 520px): release name + ✕; marker boxes (WEB CD CUE LOG 100%, `canvas-soft`, radius 2px) with Ignore and Move to group (outlined, 24px, dark list) on the right; path (12px, wraps, full width) | Show in Explorer; tracks grouped under DISC N headers, numbers restart per disc; Versions N / Remixes N / Live N outlined buttons open an inline list (title · length · Retained/Available/Ignored); grey Remix/Live note; ⋯ menu (Mark Remix/Live, Ignore, To Personal Picks); essential = teal on `canvas-soft`; gem = essential + teal diamond.

## Scaling

All sizes are CSS px. MCC applies a WebView2 ZoomFactor so 1 CSS px = 0.2645 mm on every monitor (physical size from WMI/EDID, native resolution, Windows scale), clamped 0.75–2.0, recomputed on monitor/DPI change, multiplied by a user "UI size" (80–150%). Unknown display size → Windows scaling and a log warning. Minimum window 1024×720 CSS px.
