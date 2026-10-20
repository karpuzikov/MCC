# MCC UI framework test benches

Both standalone demos use **dark theme only**, compact spacing and the same sample release/track data. Neither opens nor modifies music files. These are UI experiments, not replacements for MCC v0.5.42.

## Windows launch

From a fresh MCC clone:

### QFluentWidgets
```powershell
py -m pip install -U PySide6 PySide6-Fluent-Widgets
py "tests\ui-benches\MCC QFluentWidgets Bench.pyw"
```

### Flet
```powershell
py -m pip install -U flet
py "tests\ui-benches\MCC Flet Bench.pyw"
```

Compare density, legibility, keyboard usability, resizing, navigation, release-tree and detail layout. All buttons are explicitly demo-only; no scanning or filesystem changes. Send screenshots when ready; no automated visual QA requested. Dark theme is mandatory for MCC and all future UI implementations unless explicitly overridden by the user.

**Status:** UI prototypes; not run on the user's Windows PC. Dependency versions and framework compatibility are not certified. Keep production MCC unchanged until the user chooses a direction.
