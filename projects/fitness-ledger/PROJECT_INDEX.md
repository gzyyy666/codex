# Fitness Ledger Project Index

- `FUNCTIONAL_REVIEW_BRIEF.md`: Code-free product and workflow description for external functional review.

## Root Files

| Path | Purpose | Status |
| --- | --- | --- |
| `stable_app.pyw` | Current Tkinter desktop application. | Main program |
| `ledger_commands.py` | Shared UI-free Parse/Review/Save service with locking, checkpoints, atomic writes, and rollback. | Core service |
| `FITNESS_LEDGER_MAINTENANCE.md` | Project safety and maintenance rules. | Long-term |
| `PROJECT_BOOTSTRAP.md` | Low-token context restore guide. | Long-term |
| `PROJECT_INDEX.md` | Project file map. | Long-term |
| `FUNCTION_INDEX.md` | Function responsibility map. | Long-term |
| `REGRESSION_CHECKLIST.md` | Minimum tests by change type. | Long-term |
| `CHANGELOG.md` | Durable change history. | Long-term |
| `PROJECT_CONTEXT.md` | Product and architecture context. | Documentation |
| `README.md` | User-facing project overview. | Documentation |

## Folders

| Path | Purpose | Rule |
| --- | --- | --- |
| `data/` | Live local application data. | Protect |
| `data/tracker.json` | Core body, diet, training, movement, and raw text database. | Never clear |
| `data/movement_dictionary.json` | Versioned movement IDs, display names, English names, aliases, and metadata. | Single movement-definition source |
| `data/history_import.json` | Read-only extraction of the original workbook history. | Historical source |
| `data/backups/` | Automatic database backups. | Keep |
| `assets/` | App icon files. | Current assets |
| `tools/` | Extraction and regression utilities. | Auxiliary |
| `cloud_sync/` | Builds and validates the sanitized read-only cloud replica. | Local-to-cloud preparation |
| `mini_program/` | WeChat read-only viewer, cloud-function contract, and setup documentation. | Prepared, not deployed |
| `backups/` | Manual project snapshots before maintenance. | Keep |
| `__pycache__/` | Generated Python bytecode. | Disposable |

## Auxiliary Files

| Path | Purpose |
| --- | --- |
| `tools/extract_history.mjs` | Read the original workbook into `history_import.json`. |
| `tools/smoke_test.py` | Test parser and confirmed-save behavior with temporary data. |
| `tools/regression_test.py` | Test tables, detail windows, Matrix structure, and search. |
| `tools/cloud_payload_test.py` | Validate replica collections, counts, no-network status, and raw-text exclusion. |
| `tools/mini_program_test.py` | Validate the seven registered pages and read-only cloud function. |
| `tools/zh_display_migration.py` | Idempotent migration for Chinese display names and historical Diet main-view conversion. |
| `tools/body_bowel_cardio_migration.py` | One-time/idempotent migration for Body bowel field, recent cardio repair, and polluted display fields cleanup. |
| `tools/training_notes_zh_migration.py` | Safe migration for Chinese structured display fields and recoverable movement notes. |
| `tools/merge_leg_movements.py` | Safe merge for duplicate leg-extension/leg-curl rows and the confirmed 2026-06-25 value swap. |
| `assets/fitness-ledger.ico` | Desktop and window icon. |
| `assets/fitness-ledger.png` | PNG window icon. |

## Not Currently Used

- No runtime `logs/` directory is currently written.
- Documentation is maintained in the root Markdown files.
- There are no alternate or historical main-program files in the project.
- There is no configured cloud provider or real cloud database upload yet.

## Maintenance File Set

- `FITNESS_LEDGER_MAINTENANCE.md`: safety rules and validation commands.
- `PROJECT_BOOTSTRAP.md`: low-token startup context and request routing.
- `PROJECT_INDEX.md`: file and folder map.
- `FUNCTION_INDEX.md`: function responsibility and future-change routing.
- `REGRESSION_CHECKLIST.md`: minimum checks by change type.
- `CHANGELOG.md`: durable maintenance history.

## External Files

| Path | Purpose |
| --- | --- |
| `<USER_DESKTOP>\Fitness Ledger.lnk` | Desktop launcher |
| `<USER_DESKTOP>\fitness_tracker_clean_en.xlsx` | Original historical workbook; do not modify |
