---
id: fitness-ledger-state
type: memory
status: active
updated: 2026-07-02
tags: [fitness-ledger, python, desktop, web, rollback]
source: projects/fitness-ledger
---

# Fitness Ledger State

## Summary

Fitness Ledger is a local-first personal fitness journal with a maintained Tkinter desktop application, a read-only browser-grade desktop viewer, and a read-only mobile viewer. The authoritative local data remains JSON and is intentionally excluded from the public memory repository.

## Durable Architecture

- Maintained desktop entry: `stable_app.pyw`.
- Desktop source of truth: local `data/tracker.json` and `data/movement_dictionary.json`.
- Browser UI: `web_desktop/frontend/`; local read-only service: `web_desktop/backend/server.py`.
- Mobile viewer: `mobile_viewer/`.
- All formal desktop writes use atomic JSON replacement and pre-save checkpoints.
- Raw daily input is preserved; structured records can be repaired without deleting source text.

## Durable Product Behavior

- Daily free-form input is parsed, reviewed, then explicitly saved.
- Movement aliases resolve through a formal movement dictionary.
- Adding an alias scans active historical skipped movements and restores matching sets and notes into the formal movement history.
- Body, Diet, Training, Movement Progress, and Data Check provide record inspection and correction paths.
- Web and mobile viewers remain read-only until their write commands can reuse desktop review, backup, and atomic-save behavior.

## Visual Direction

- Current Web direction: editorial fitness journal, warm paper surfaces, graphite ink, restrained yellow highlight, cinematic fitness imagery, tactile archive slips, and high information density without spreadsheet styling.
- The reusable visual specification lives at `projects/fitness-ledger/docs/design/STYLE_BIBLE.md`.

## Recovery

- Source rollback: use Git commits in `projects/fitness-ledger/`.
- Personal data rollback: use timestamped files in the local application's `data/backups/` directory.
- Never replace current personal data with repository files because the public repository intentionally contains no personal JSON data.

## Review

- Next review: 2026-08-02
- Archive when the project is retired or replaced.

