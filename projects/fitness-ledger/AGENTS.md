# Fitness Ledger task startup and handoff

These rules apply to every task under this project.

## Start from live facts

For source-only work, check Git scope and `HEAD/main/origin/main` once. Before
runtime diagnosis, formal publication, or data/provider work, run:

```powershell
python tools/project_status.py --write --json
```

Use live facts as authority. Stop actions affected by unexplained baseline or
deployment drift; unrelated runtime drift does not block source-only work.
Do not repeat an unchanged full scan for each phase of a small task.

An automatically created Codex Worktree may be detached from an older
`origin/main`. If its `HEAD` is not the verified live local `main`, do not use
it as the development baseline. Create or switch to a
task-specific `codex/<task-name>` branch from the live local `main` first.

Before starting work that touches an existing module, data structure, or architecture extension, inspect `docs/experiments/EXPERIMENTS_INDEX.md`. Unless the user explicitly resumes an experiment, do not continue, merge, copy, or depend on a paused experiment.

Do not copy formal `data/**` into Git or a Worktree. The status file contains hashes and dates only, never training-record content.

## Task routing before skill invocation

Use `docs/agent/FL_TASK_ROUTING.md` to judge knowledge gaps, verification risk,
and authorized publication separately. Familiar work skips community research;
a concrete gap uses targeted research. Complexity, L/R3 labels, or sealing
alone never require two roles, broad research, or parallel agents. Investigate
material uncertainty with a targeted check instead of escalating the whole
workflow. Use `REGRESSION_CHECKLIST.md` to select affected checks.

## Deployment and service rules

- Derive deployment scope from `git diff --name-status`.
- Preserve formal-only data, Cloud configuration, generated payloads, and runtime state.
- Treat `A`, `M`, `D`, and `R` according to Git status instead of target-file existence alone.
- Normalize LF/CRLF and BOM when comparing text.
- If deployed Python backend or Cloud Sync source changed, restart the formal Web service before browser or upload verification. A running Python process does not reload updated modules automatically.

## Task handoff

After formal application publication or cross-task integration needing a
shared runtime handoff, run:

```powershell
python tools/project_status.py --write --handoff --json
```

This writes the shared local handoff at:

`D:\FitnessLedger\source\projects\fitness-ledger\.codex\task-handoff.json`

Return the handoff path and Commit SHA when applicable. Source-only work may
end with a reviewed diff or commit and does not require this runtime handoff.
Development / review does not itself authorize publication.

## Closure levels

For the executable sealing checklist, read
`docs/maintenance/CODEX_RELEASE_CLOSEOUT.md` before any Seal / finalise action.
Use source-only closeout for unpublished work, **Quick Seal** for a known
bounded local publication, and **Full Seal** for consequential boundaries or
unclear provenance. Full Seal adds only risk-relevant checks. A file being in
Core or PWA does not alone require a heavier route. The closeout guide is the
single authority for check selection; do not recreate a second checklist here.

Every task conversation must identify its closure level from the user's wording:

- **Development / review**: work only in the task Worktree; run the relevant tests and leave a clean, reviewable task commit or an explicit uncommitted diff. Do not merge, Push, create Tags, or write to the formal directory unless the user separately authorizes a Review Deployment.
- **Review Deployment / temporary release**: when the user explicitly asks to publish for review, or the surface cannot be fully reviewed without the formal runtime/device (notably an installed phone PWA), publish the review candidate before final acceptance. The user accepts that review feedback may require rework. This permission covers only the named target and reviewed files. Preserve a recoverable copy/rollback point, run the scoped preflight and checks, publish with coherent asset versions, and verify the actual formal URL/device-facing resources. Do not treat this as human acceptance or Seal / finalise; do not merge, Push, Tag, alter protected data, change Cloud Sync/provider state, or deploy unrelated files unless separately authorized. After review, continue development or wait for explicit seal authorization.
- **Seal / finalise / 封板**: after review and relevant checks pass, complete the applicable source-only, Quick, or Full closeout. Integrate and Push only as authorized; deploy only reviewed files and run only affected runtime/data checks. Reuse acceptance and authorization already given; do not ask again for the same scope.

The task does not need to be handed back to a central Git conversation. A specialist Worktree conversation may seal its own work when the user explicitly authorizes sealing. The central conversation remains the preferred place for cross-Worktree integration, unexplained conflicts, broad architecture changes, or a final multi-task audit.

If the user only asks to modify, fix, develop, or prepare a review, treat it as **Development / review**. Do not infer publication. A request such as “先发布供我 review，接受返工” explicitly authorizes only a **Review Deployment**; it does not authorize Seal / finalise.

Report the change, relevant checks, and candidate/published status. Add commit,
deployment scope, rollback, formal/data evidence and handoff only when relevant
to the actual work. Follow the concise receipt in the closeout guide.

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
