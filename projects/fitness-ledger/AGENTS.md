# Fitness Ledger task startup and handoff

These rules apply to every task under this project.

## Start from live facts

Before reviewing or editing, run:

```powershell
python tools/project_status.py --write --json
```

Use its live Git, formal-directory, Cloud Sync, service, and deployment results as the authority. Prompt SHAs and old chat summaries are expectations only; report and stop on an unexplained mismatch.

Do not copy formal `data/**` into Git or a Worktree. The status file contains hashes and dates only, never training-record content.

## Deployment and service rules

- Derive deployment scope from `git diff --name-status`.
- Preserve formal-only data, Cloud configuration, generated payloads, and runtime state.
- Treat `A`, `M`, `D`, and `R` according to Git status instead of target-file existence alone.
- Normalize LF/CRLF and BOM when comparing text.
- If deployed Python backend or Cloud Sync source changed, restart the formal Web service before browser or upload verification. A running Python process does not reload updated modules automatically.

## Task handoff

After tests and the task commit, run:

```powershell
python tools/project_status.py --write --handoff --json
```

This writes the shared local handoff at:

`C:\Users\26087\Documents\Codex\github-memory\projects\fitness-ledger\.codex\task-handoff.json`

Return the handoff path and full Commit SHA. In Development / review mode, do not merge main, Push, deploy formal files, or perform a real CloudBase upload. Seal / finalise mode is the explicit exception defined below.

## Closure levels

Every task conversation must identify its closure level from the user's wording:

- **Development / review**: work only in the task Worktree; run the relevant tests and leave a clean, reviewable task commit or an explicit uncommitted diff. Do not merge, Push, create Tags, or write to the formal directory.
- **Seal / finalise / 封板**: after review and all required tests pass, the same task conversation may complete the full closeout: Commit the task branch, integrate into `main` using the least invasive allowed Git operation, Push only when authorized, derive the deployment list from Git, precisely write back the formal directory, restart affected local services, re-run formal regression, verify protected data hashes, and run `python tools/project_status.py --write --handoff --json`.

The task does not need to be handed back to a central Git conversation. A specialist Worktree conversation may seal its own work when the user explicitly authorizes sealing. The central conversation remains the preferred place for cross-Worktree integration, unexplained conflicts, broad architecture changes, or a final multi-task audit.

If the user only asks to modify, fix, develop, or prepare a review, treat it as **Development / review**. Do not infer Push or formal writeback. Stop before any closure action when the user has not authorized that level.

Before claiming a sealed task, confirm in the final report: full Commit SHA, `HEAD/main/origin/main`, clean Worktrees, exact deployment files, formal data SHA/size/mtime before and after, test results, and the handoff path.
