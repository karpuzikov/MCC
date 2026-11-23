# MCC UI and workflows

Review draft for v0.5.177. [Release selection rules](RELEASE_SELECTION_RULES.md)

| Workflow | Behavior |
|---|---|
| Set up | Add or remove source folders. Optionally star folders as the reference. Before audio comparison, check folder paths and scan all sources by the same rules. Set Keep Remixes and Keep Live. Several disc folders can form one release. |
| Scan | Scan attributes first. Apply known exclusions before acoustic work. Reuse valid analysis for unchanged eligible releases. Full rescan rebuilds eligible audio analysis. Leave sources untouched. Show the current stage and progress. Record warnings, failures, and outcomes in Activity. |
| Review a track pattern | After acoustic analysis, choose Keep, Skip, Remix, or Live. Apply the choices before selecting releases and remember them for later scans. Deferred patterns stay available for review. |
| View results | Switch between Folders and Release Map using shared navigation. View the full collection or changes. Search by release or track. Open a release to see its source, tracks, warnings, and the reason for the result. |
| Compare recordings | Click a track to highlight other copies of the verified recording. Click again to clear. Versions sorts by name, then duration, and shows duration differences. Identify links based on metadata alone as unverified audio. |

## Decisions and warnings

- **Auto / Keep / Skip.** Show all three and indicate the active choice. In Auto, connect it to the current Keep or Skip result. A manual choice removes the connection. Auto clears the override and restores the automatic result.
- **Track actions.** Use Keep and Skip consistently. Set or clear Remix and Live in the same menu.
- **Updates.** Apply choices automatically. Keep details usable and show progress or failure. Reuse valid evidence. Request a fresh scan if source files changed.
- **Warning review.** Show unresolved warnings in the release details and review list. Keep or Skip resolves the warning for export. Auto can bring it back. Excluded items stay out of review. Pending changes and unresolved warnings block export.

## Export and Undo

| Operation | Behavior |
|---|---|
| Copy or Move | Require a current, nonempty selection and a destination outside the source trees. Never overwrite existing output silently. Apply the selected ALAC or FLAC encoding, CUE splitting, audio check, MusicBrainz, and artwork options. Report the result and problems per release. |
| Copy | Preserve source files. Keep Release Map accessible. Show the destination and current release target when available, with a way to open the destination. |
| Move | Write the output first. Recycle source folders only for successful releases. Report any recycle failure and what already moved. |
| Undo | Remove only Copy outputs that still match the file journal and intended destination. Block Undo if output changed, is missing, or has an unresolved interrupted write. Recover Move sources through the Recycle Bin. |

Preserve the source date, barcode, and catalog number when online metadata is ambiguous. Search for artwork by barcode. If there is no barcode in the tags or folder name, look up the catalog number in MusicBrainz and use the confirmed barcode. Report artwork as found or unavailable. For *A Million Stars*, preserve the year 2011 and use BH383-0 as the catalog number.

**Still open.** Which decode warnings should block export? Which files and formats should each export option produce by default? The Organizer still has an internal partial artwork status. Native Scan → edit → Copy and output verification are pending.

Update this file with changes to user actions, feedback, or file operations.
