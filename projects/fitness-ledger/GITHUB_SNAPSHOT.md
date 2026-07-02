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

