# Fitness Ledger task startup and handoff

These rules apply to every task under this project.

## Start from live facts

Before reviewing or editing, run:

```powershell
python tools/project_status.py --write --json
```

Use its live Git, formal-directory, Cloud Sync, service, and deployment results as the authority. Prompt SHAs and old chat summaries are expectations only; report and stop on an unexplained mismatch.

An automatically created Codex Worktree may be detached from an older
`origin/main`. If its `HEAD` is not the live local `main` reported by the status
command, do not use it as the development baseline. Create or switch to a
task-specific `codex/<task-name>` branch from the live local `main` first.

Before starting work that touches an existing module, data structure, or architecture extension, inspect `docs/experiments/EXPERIMENTS_INDEX.md`. Unless the user explicitly resumes an experiment, do not continue, merge, copy, or depend on a paused experiment.

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

`D:\FitnessLedger\source\projects\fitness-ledger\.codex\task-handoff.json`

Return the handoff path and full Commit SHA. In Development / review mode, do not merge main, Push, deploy formal files, or perform a real CloudBase upload. Seal / finalise mode is the explicit exception defined below.

## Closure levels

Every task conversation must identify its closure level from the user's wording:

- **Development / review**: work only in the task Worktree; run the relevant tests and leave a clean, reviewable task commit or an explicit uncommitted diff. Do not merge, Push, create Tags, or write to the formal directory.
- **Seal / finalise / 封板**: after review and all required tests pass, the same task conversation may complete the full closeout: Commit the task branch, integrate into `main` using the least invasive allowed Git operation, Push only when authorized, derive the deployment list from Git, precisely write back the formal directory, restart affected local services, re-run formal regression, verify protected data hashes, and run `python tools/project_status.py --write --handoff --json`.

The task does not need to be handed back to a central Git conversation. A specialist Worktree conversation may seal its own work when the user explicitly authorizes sealing. The central conversation remains the preferred place for cross-Worktree integration, unexplained conflicts, broad architecture changes, or a final multi-task audit.

If the user only asks to modify, fix, develop, or prepare a review, treat it as **Development / review**. Do not infer Push or formal writeback. Stop before any closure action when the user has not authorized that level.

Before claiming a sealed task, confirm in the final report: full Commit SHA, `HEAD/main/origin/main`, clean Worktrees, exact deployment files, formal data SHA/size/mtime before and after, test results, and the handoff path.

## Worktree lifecycle

- A sealed task must not leave an unexplained dirty Worktree.
- Preserve valuable uncommitted experimental work on a clearly named
  `archive/<topic>-wip-<date>` branch before cleanup; never merge an archive
  branch into `main` without a new compatibility review.
- Keep generated reports, model traces, formal export artifacts, and
  `tools/test_outputs/` outside Git.
- Clean Worktrees whose branches are already merged may be removed after
  confirming that no active Codex task owns them. Removing a Worktree does not
  require deleting its branch immediately.
- Clean unmerged experiment branches should keep a status document or Tag
  before their Worktrees are removed. Paused experiments remain governed by
  `docs/experiments/EXPERIMENTS_INDEX.md`.
- Do not manually remove `.codex/worktrees/*` while their owning task may still
  be active. Let Codex task lifecycle controls retire those Worktrees.
- After cleanup, run `git worktree list`, verify the remaining Worktrees, and
  run the project status command again.
