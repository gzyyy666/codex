# Fitness Ledger: Start Here

This is the authoritative source and context entry for Fitness Ledger. It is designed so a future Codex session can resume work without reading the original conversation.

## Five-Minute Restore

1. Read `FITNESS_LEDGER_MAINTENANCE.md` for safety boundaries.
2. Read `PROJECT_BOOTSTRAP.md` for architecture and request routing.
3. Read `docs/INDEX.md` and open only the task-specific references.
4. Read `FUNCTION_INDEX.md` before opening large source files.
5. Select the minimum tests from `REGRESSION_CHECKLIST.md`.

## Current Authority

- Desktop application and parser: `stable_app.pyw`
- Shared safe write boundary: `ledger_commands.py`
- Live local data: local-only `data/tracker.json` and `data/movement_dictionary.json`
- Web service: `web_desktop/backend/server.py`
- Web UI: `web_desktop/frontend/index.html`, `app.js`, `styles.css`, `final-pass.css`
- Mobile read-only viewer: `mobile_viewer/`
- WeChat read-only viewer preparation: `mini_program/`
- Cloud replica review and contract: `cloud_sync/CLOUD_REVIEW.md`, `cloud_sync/CLOUD_DATA_CONTRACT.md`
- Visual authority: `docs/design/STYLE_BIBLE.md`

## Non-Negotiable Rules

- Never upload or replace live personal JSON from this repository.
- Never write JSON directly from a UI layer; use the shared command service.
- Preserve raw daily input during every structured correction.
- Treat the movement dictionary as the naming, alias, body-area, and active-state authority.
- Do not restore historical UI experiments or duplicate main programs.
- Validate before creating a source checkpoint.

## Task Routing

- Desktop UI or parser: `FUNCTION_INDEX.md`, then relevant functions in `stable_app.pyw`
- Web behavior: `web_desktop/ARCHITECTURE.md`, then `web_desktop/frontend/app.js`
- Web visual changes: `docs/design/STYLE_BIBLE.md`, `docs/design/DESIGN_RESOURCES.md`
- Environment or launch issues: `docs/maintenance/ENVIRONMENT.md`
- WeChat or CloudBase preparation: `mini_program/README.md`, `mini_program/docs/`, then `cloud_sync/CLOUD_REVIEW.md`
- Backup or rollback: `docs/maintenance/ROLLBACK.md`
- Why the architecture looks this way: `docs/maintenance/WORKFLOW_LESSONS.md`
- Final visual references: `docs/design/evidence/`

## Recovery Prompt

```text
Restore Fitness Ledger context from this repository.
Read projects/fitness-ledger/START_HERE.md and docs/INDEX.md first.
Then read only the files linked for the current task.
Do not inspect live personal data or rebuild context from old chat transcripts.
Summarize the current architecture, safety boundary, and requested change before editing.
```
