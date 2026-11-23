# MCC release selection rules

Review draft for v0.5.177. [UI and workflows](UI_AND_WORKFLOWS.md)

**Goal.** Cover the wanted recordings with the fewest physical tracks, then the fewest releases, subject to the rules below. A track is a file or a region in a disc image. A recording can have equivalent copies on several releases.

## Selection rules

**Scan order**

1. Load saved choices and settings.
2. Inventory folder and file attributes by path.
3. Apply known Skip choices.
4. Apply the Keep Remixes and Keep Live settings independently.
5. Apply saved classifications and Personal Picks.
6. Set aside skipped material before integrity checks, acoustic IDs, or comparison.
7. Reuse valid analysis for unchanged eligible releases on a later Scan.
8. Analyze the eligible contents of a changed release as a whole. A file addition, deletion, replacement, or tag edit invalidates that release's analysis.
9. Compare eligible audio where current evidence is missing.
10. Review unfamiliar patterns after acoustic work.
11. Apply the review choices to the existing evidence.
12. Select releases.
13. Save folder and file attributes and reusable analysis.

Full rescan bypasses saved scan analysis. Manual choices and Remix/Live exclusions still apply. The reference star affects comparison and selection, while discovery and audio preparation use the same rules for all sources.

1. **Filter.** Apply Remix and Live settings, saved classifications, Personal Picks, and manual Skip choices. Exclude skipped material from selection, review, and expensive audio checks as early as possible. An all-remix release contributes no wanted recordings or missing-track warnings when remixes are excluded.
2. **Classify releases.** Explicit EP wording or tags take precedence over anthology heuristics. Preserve source metadata when online evidence is ambiguous.
3. **Match audio.** Use titles and track positions to find candidates. Require acoustic evidence to merge them. The current limit is eight seconds across an entire group after accounting for verified silent padding. If 100 s matches 108 s, 108 s cannot bring 116 s into the same group. Keep uncertain matches and distinct versions separate.
4. **Cover wanted recordings.** Prefer a regular release wherever one can supply the recording. A compilation can supply it when no eligible regular release can. Preserve compilation evidence so it can become a fallback after an override.
5. **Preserve album families.** Supply each eligible family with a valid complete or permitted core edition. The current build allows certain featured-remix bonuses to come from separate singles.
6. **Choose the smallest valid plan.** Minimize physical tracks, then releases. Break ties by source and CD-rip quality, then favor the reference. The current build can use measured dynamic range as a final quality tie-break.
7. **Apply overrides.** Keep pins a release. Skip makes it ineligible. Auto clears the override. Recalculate affected releases and reuse valid evidence. Analyze newly eligible audio where evidence is missing.

## Decisions to settle

| Rule | What needs a decision |
|---|---|
| Track Skip scope | Older written rules say one file or cue track. The current map can Skip every verified copy. Which scope is intended? |
| Track Skip during Copy | The Organizer exports whole selected releases, with separate duplicate filtering. Should Skip also omit the track from Copy, including when it is inside a disc image? |
| Release Skip with unique audio | The current plan can stop requiring a recording when Skip removes its last eligible copy. What should MCC do in that case? |
| Explicit versus clean | The current scan can exclude a clean track before proving audio equivalence. Should advisory tags affect selection? |
| Complete editions and quality | When a fuller edition, better source, and smaller collection point to different choices, which wins? Do featured-remix bonuses still need their own exception? |
| Anthology versus compilation | The current fallback rule checks Compilation. Should Anthology follow it too? |
| Manual Keep | The current build can add a forced release after optimizing. Should Keep also let that release replace a redundant automatic selection? |

Use one concrete case to test each disputed rule. Exact acoustic acceptance criteria, release-type boundaries, and source-quality rankings still need examples for a reproducible rebuild.

Update this file and its examples when selection behavior changes.
