# MCC

Design system for Music Collection Cleaner (karpuzikov/MCC). Built on the VoltAgent design language (near-black canvas, hairline edges, Inter + mono) and reshaped through review into a dense, tool-first Windows UI with a teal accent.

Reference mockup (1024×768 and 1920×1080, Main + Release Map): https://claude.ai/artifact/JeQLrRKajL14iEBXzWBqYd

## Rules

1. **Dark only.** `canvas` #101010 is the only surface.
2. **Teal is the accent** (`primary` #2bc4d4): primary buttons, logo, selection, essential tracks, links, star. `primary-soft` #6fd8e3 for the focus ring.
3. **Green means "added"** (`status-added` #00d992) and nothing else: `+` / `↑` at the end of a release row and the Added/Upgraded chips.
4. **Equal padding on all sides inside every element.** Buttons, chips, inputs, selects, paths 4px; primary buttons 5px; bars and panels 8px; release board 4px. Line-height = font-size on buttons and fields so the padding reads equal. No fixed control heights: height = content + padding.
5. **Text buttons are outlined** (1px `hairline`, radius 6px, 600 14px). **Icon buttons are never outlined**: no border, no padding, SVG viewBox cropped to the drawn shape, all icons 14px tall, 1.5px non-scaling stroke.
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

- **Inter** (bundled woff2) for everything; **JetBrains Mono** only for the activity log, version tag and track numbers.
- Step labels 14/14 600 `ink`; buttons 14/14 600; chips 13/13 500; body 14/20; paths Inter 13/13 `body`; section labels 12px 600 uppercase 2px tracking `body`.

## Layout

**Main window** — top bar (logo, name, version, Under construction) · Step 1: Select folders (rows: ★ | role label 120px | path | Browse icon | Show in Explorer icon | ✕; then + Add folder | Remixes | Live recordings | Keeps and Skips | Advanced ▸) · Step 2: Scan selected folders (Scan + progress) · Step 3: Open the map (teal Release Map → | Undo last export) · Activity log fills the rest. The next step's button is the teal one.

**Release Map** — top bar (logo, Release Map, version, Under construction, Search) · toolbar: Step 4: Check the scan result | Changes / Full map / All links | + Added · ↑ Upgraded · ↔ Replaced · ~~Removed~~ · ⊘ Ignored | Re-scan · board · details panel · footer: Step 5: Save results | Copy into/Move into toggle | destination | Browse | Show in Explorer | teal Copy/Move; second row Encode to + format | AudioChecker | Split CUE.

- **Board:** 2 columns at ≤1280px CSS (Albums | Singles + Compilations stacked), 3 columns at ≥1600px. Group title 13/600 `ink`; folder rows indented 12px below; 12px between groups; 1px lines between rows; square corners.
- **Release row:** folder name exactly as on disk. Skip = `mute` + line-through; Keep = plain `ink`; Add = `ink` + green `+` at end; Upgrade = green `↑`; Replace = white `↔`. Full path in tooltip.
- **Details panel** (360px / 520px): release name + ✕; path | Show in Explorer | Ignore; tracks grouped under DISC N headers, numbers restart per disc; Versions N / Remixes N / Live N outlined buttons open an inline list (title · length · Retained/Available/Ignored); grey Remix/Live note; ⋯ menu (Mark Remix/Live, Ignore, To Personal Picks); essential = teal on `canvas-soft`; gem = essential + teal diamond.

## Scaling

All sizes are CSS px. MCC applies a WebView2 ZoomFactor so 1 CSS px = 0.2645 mm on every monitor (physical size from WMI/EDID, native resolution, Windows scale), clamped 0.75–2.0, recomputed on monitor/DPI change, multiplied by a user "UI size" (80–150%) in Advanced. Unknown display size → Windows scaling and a log warning. Minimum window 1024×720 CSS px.

## Tokens

Source: `project/tokens.json` of the MCC design system. In the app every token is a CSS variable in `APP_STYLE_CSS` `:root`.

| Token | Value |
| --- | --- |
| `primary` | #2bc4d4 |
| `primary-soft` | #6fd8e3 |
| `primary-deep` | #2bc4d4 |
| `on-primary` | #101010 |
| `canvas` | #101010 |
| `canvas-soft` | #1a1a1a |
| `canvas-text-soft` | #f5f6f7 |
| `ink` | #f2f2f2 |
| `ink-strong` | #ffffff |
| `body` | #bdbdbd |
| `mute` | #8b949e |
| `hairline` | #3d3a39 |
| `status-added` | #00d992 |

| Type style | Spec |
| --- | --- |
| `step-label` | Inter 600 14px/14px |
| `button-md` | Inter 600 14px/14px |
| `caption-strong` (chips) | Inter 500 13px/13px |
| body | Inter 400 14px/20px |
| path | Inter 400 13px/13px |
| section label | Inter 600 12px/18px, uppercase, 2px tracking |
| `code` | JetBrains Mono 400 14px/20px |

| Spacing | Value | Use |
| --- | --- | --- |
| `space-xs` | 4px | Control padding, board padding |
| (primary) | 5px | Primary button padding |
| `space-sm` | 8px | Bar/panel padding, row gap |
| `space-md` | 12px | Group gap, row indent |

| Radius | Value |
| --- | --- |
| `radius-sm` | 6px (buttons, inputs, chips, paths) |
