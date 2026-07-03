---
id: fitness-ledger-state
type: memory
status: active
updated: 2026-07-03
tags: [fitness-ledger, python, desktop, web, rollback]
source: projects/fitness-ledger
---

# Fitness Ledger State

## Summary

Fitness Ledger is a local-first personal fitness journal with a maintained Tkinter desktop application, a browser-grade Web application with shared daily Parse/Review/Save, and a read-only mobile viewer. The authoritative local data remains JSON and is intentionally excluded from the public memory repository.

## Durable Architecture

- Maintained desktop entry: `stable_app.pyw`.
- Desktop source of truth: local `data/tracker.json` and `data/movement_dictionary.json`.
- Shared write boundary: `ledger_commands.py` provides UI-free Parse/Review/Save and Movement Dictionary administration, cross-process locking, paired checkpoints, atomic writes, and rollback.
- Shared read-only projection boundary: `fitness_ledger_core/shared_view_models.py` powers training reference, movement insight, exports, and cloud payload preparation from the same local snapshots.
- Browser UI: `web_desktop/frontend/`; local command/read service: `web_desktop/backend/server.py`.
- Mobile viewer: `mobile_viewer/`.
- Desktop and Web confirmed daily saves use the same command service and desktop parser.
- Raw daily input is preserved; structured records can be repaired without deleting source text.

## Durable Product Behavior

- Daily free-form input is parsed, reviewed, then explicitly saved.
- Movement aliases resolve through a formal movement dictionary.
- Adding an alias scans active historical skipped movements and restores matching sets and notes into the formal movement history.
- Disabling a movement preserves aliases and history and still permits matching records to be stored, while hiding that movement from desktop/Web Movement Progress and active mapping choices.
- Body, Diet, Training, Movement Progress, and Data Check provide record inspection and correction paths.
- Web daily entry supports editable Review, duplicate-date modes, movement add/map/skip decisions, and paired database/dictionary Undo through the shared command service.
- Web Data Check now uses the desktop rule set, existing acknowledgement state, and direct repair routes instead of sample issues.
- Training includes a read-only Pre-Workout Reference based only on the user's recent matching sessions; it does not generate plans or advice.
- Movement detail includes Recent 3 performance metrics and changes.
- Analysis Export produces local Markdown/JSON for 7/14/30-day or custom ranges, excluding full raw text by default.
- `cloud_sync/` prepares and dry-runs a disposable read-only cloud replica. No provider, credentials, or network write are configured.
- Web Movement Dictionary supports create, rename, aliases, muscle-group/category/equipment metadata, enable/disable, and confirmed deletion.
- Web Body, Diet, and Training records are editable through the same maintained field sets as desktop; movement-history rows support structured set/order/cardio/note edits by permanent IDs.
- Dictionary uses a professional five-column functional grid; aliases and extended metadata remain available in its editor rather than occupying the main directory.
- Dictionary edits from desktop and Web use the same command service. Desktop shutdown does not rewrite stale in-memory JSON over newer Web changes.
- Duplicate dates never save silently: overwrite replaces that date's structured Body/Diet/Training and movement history while superseding old raw entries; append-training adds only another training session; cancel writes nothing.

## Visual Direction

- Current Web direction: editorial fitness journal, warm paper surfaces, graphite ink, restrained yellow highlight, cinematic fitness imagery, tactile archive slips, and high information density without spreadsheet styling.
- The reusable visual specification lives at `projects/fitness-ledger/docs/design/STYLE_BIBLE.md`.

## Recovery

- Source rollback: use Git commits in `projects/fitness-ledger/`.
- Local pre-change source snapshot for the 2026-07-03 platform phase: `work/fitness_tracker_app/backups/platform_phase_20260703_180915` (not uploaded because it may contain local-only artifacts).
- Personal data rollback: use timestamped files in the local application's `data/backups/` directory.
- Never replace current personal data with repository files because the public repository intentionally contains no personal JSON data.

## Review

- Next review: 2026-08-02
- Archive when the project is retired or replaced.
