# Fitness Ledger Source Snapshot

This directory is the versioned, non-sensitive source mirror for Fitness Ledger.

> Historical snapshot notice: this document records an early platform checkpoint. It is not the current Git/deployment authority. Use `START_HERE.md`, `AGENTS.md`, and `python tools/project_status.py --write --json` for the live baseline.

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

## Historical Verified Platform Checkpoint (2026-07-03)

- Functional source checkpoint: `4275a7a` (`Add Fitness Ledger shared platform services`), retained here only as the historical checkpoint described by this snapshot.
- Includes shared Web Undo, real Data Check routing, Pre-Workout Reference, Movement Recent 3, Analysis Export, and cloud read-replica dry-run preparation.
- Local pre-change source snapshot: `backups/platform_phase_20260703_180915` in the working application folder.
- Verification: Python compilation, JavaScript syntax, regression test, smoke test, temporary paired Undo test, HTTP route test, payload build, and cloud dry-run all passed on 2026-07-03.

## Historical Verified Visual Checkpoint (2026-07-03 to 2026-07-05)

- Training Records contains five tactile body-area controls directly on its first screen. Each sets an in-page theme state and preserves the `#training` route.
- Shoulder, chest, back, legs, and arms themes synchronize title, atmosphere, live counts, browser-only record filtering, card accents, and the right-side focus panel.
- The previous Before You Train home action, independent reference route, and dark launcher banner are no longer part of the active frontend flow.
- Export uses explicit idle/loading/success/error states and readable Copy Markdown, Download Markdown, and Download JSON actions.
- The visual system uses three controlled depth layers, real material shadows and highlights, and reduced-motion fallbacks documented in `docs/design/STYLE_BIBLE.md`.
- Verification: JavaScript syntax, Python compilation, regression, Web shared-write, smoke, and side-by-side visual QA passed on 2026-07-03.

## Historical Daily Material Workbench Checkpoint

- Daily Entry now uses a raised notebook slab, tactile primary action, floating Today receipt, layered Recent Saved slips, and a restrained local-first readiness surface.
- Training retains the previously approved compact horizontal rectangular body-area theme cards from checkpoint `67b0688`.
- The connected circular Training control experiment was explicitly rejected and removed before this checkpoint.
- No parser, shared-write, data model, desktop application, or personal JSON data changed.
- Verification: JavaScript syntax, Python compilation, regression, Web shared-write, and smoke tests passed on 2026-07-03.
- Local source rollback before this material pass: `backups/material_workbench_20260703_234308`.
