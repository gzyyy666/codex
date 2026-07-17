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

Return the handoff path and full Commit SHA. Do not merge main, Push, deploy formal files, or perform a real CloudBase upload unless the task explicitly authorizes those actions.
