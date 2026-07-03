# Fitness Ledger Source Snapshot

This directory is the versioned, non-sensitive source mirror for Fitness Ledger.

Included:

- `stable_app.pyw`, the maintained Windows desktop application.
- `web_desktop/`, the browser-grade local Web interface and visual assets.
- `mobile_viewer/`, the read-only mobile viewer.
- maintenance, architecture, regression, and change-log documents.
- test and migration tools that do not contain personal records.

Excluded deliberately:

- `data/tracker.json`, `data/movement_dictionary.json`, and all personal fitness records.
- backups, logs, browser profiles, caches, temporary files, and spreadsheets.

The source can be restored from any Git commit. Personal JSON data must be restored separately from the application's local `data/backups/` directory.

## Current Verified Platform Checkpoint

- Functional source checkpoint: `4275a7a` (`Add Fitness Ledger shared platform services`).
- Includes shared Web Undo, real Data Check routing, Pre-Workout Reference, Movement Recent 3, Analysis Export, and cloud read-replica dry-run preparation.
- Local pre-change source snapshot: `backups/platform_phase_20260703_180915` in the working application folder.
- Verification: Python compilation, JavaScript syntax, regression test, smoke test, temporary paired Undo test, HTTP route test, payload build, and cloud dry-run all passed on 2026-07-03.

## Current Verified Visual Checkpoint

- Training Records contains five tactile body-area controls directly on its first screen; each opens a matching themed reference scene while Training remains the active navigation item.
- Export uses explicit idle/loading/success/error states and readable Copy Markdown, Download Markdown, and Download JSON actions.
- The visual system uses three controlled depth layers, real material shadows and highlights, and reduced-motion fallbacks documented in `docs/design/STYLE_BIBLE.md`.
- Verification: JavaScript syntax, Python compilation, regression, Web shared-write, smoke, and side-by-side visual QA passed on 2026-07-03.
