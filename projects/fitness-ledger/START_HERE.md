# Fitness Ledger: Start Here

This is the authoritative source and context entry for Fitness Ledger. It is designed so a future Codex session can resume work without reading the original conversation.

## User-facing workflow

You can work in any dedicated long-running specialist conversation. At the start of every task, that conversation reads the live project status; you do not need to provide the latest SHA or copy files between conversations.

Use one of these two phrases when the desired stopping point matters:

- **“先开发/先让我验收”**: the conversation changes only its task Worktree, runs focused tests, and stops for review. It does not Push, Tag, merge, or write to the formal directory.
- **“按规范封板”**: after tests and review pass, the conversation may finish the full closeout itself: Commit, integrate and Push when authorized, precisely update the formal directory, verify protected data, restart affected services, and update `.codex/task-handoff.json`.

You do not have to return a sealed task to this central conversation. Return it here only when several Worktrees must be coordinated, a conflict is unexplained, or you want a final cross-task audit.

If no closure phrase is given, default to **先开发/先让我验收**. This prevents a normal small fix from unexpectedly changing `main` or the formal environment.

## Five-Minute Restore

1. Run `python tools/project_status.py --write --json` and use the live result instead of an old prompt SHA.
2. Read `FITNESS_LEDGER_MAINTENANCE.md` for safety boundaries.
3. Read `PROJECT_BOOTSTRAP.md` for architecture and request routing.
4. Read `docs/INDEX.md` and open only the task-specific references.
5. Read `FUNCTION_INDEX.md` before opening large source files.
6. Select the minimum tests from `REGRESSION_CHECKLIST.md`.

## Current Authority

- Desktop application and parser: `stable_app.pyw`
- Shared safe write boundary: `ledger_commands.py`
- Live local data: local-only `data/tracker.json` and `data/movement_dictionary.json`
- Web service: `web_desktop/backend/server.py`
- Web UI: `web_desktop/frontend/index.html`, `app.js`, `styles.css`, `final-pass.css`
- Mobile read-only viewer: `mobile_viewer/`
- WeChat read-only gym reference client: `mini_program/`
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
- WeChat or CloudBase maintenance: `mini_program/README.md`, `mini_program/docs/`, `../../workflows/fitness-ledger-wechat-readonly-release.md`, then `cloud_sync/CLOUD_REVIEW.md`
- Backup or rollback: `docs/maintenance/ROLLBACK.md`
- Why the architecture looks this way: `docs/maintenance/WORKFLOW_LESSONS.md`
- Final visual references: `docs/design/evidence/`

## Recovery Prompt

```text
Restore Fitness Ledger context from this repository.
Run python tools/project_status.py --write --json first.
Then read projects/fitness-ledger/START_HERE.md and docs/INDEX.md.
Then read only the files linked for the current task.
Do not inspect live personal data or rebuild context from old chat transcripts.
Summarize the current architecture, safety boundary, and requested change before editing.
```
