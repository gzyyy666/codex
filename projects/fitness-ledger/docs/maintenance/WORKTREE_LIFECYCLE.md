# Worktree Lifecycle

This document is the maintenance checklist for Fitness Ledger Worktrees. The
project `AGENTS.md` remains authoritative for task behavior.

## Create

1. Check Git baseline/scope; run live project status when runtime or publication is involved.
2. Use the verified live local `main`, not an older detached
   Worktree or an unverified remote-tracking snapshot.
3. Reuse the task's existing Worktree; create an isolated `codex/<task-name>` Worktree when needed to protect main or concurrent work. Do not nest Worktrees merely for a route label.
4. Read `docs/experiments/EXPERIMENTS_INDEX.md` before reusing any experiment.

## Develop

- Keep the task scope isolated.
- Keep formal data, generated reports, model traces, and exported artifacts
  outside Git.
- Default to Development / review closure unless the user explicitly
  authorizes sealing.

## Seal

Use `CODEX_RELEASE_CLOSEOUT.md` as the authority. The steps below apply only
when relevant and authorized; source-only work needs no formal deployment,
service restart, protected-data scan or shared runtime handoff. Cleanup of
unrelated Worktrees is separate maintenance, not a release gate.

1. Run the scoped tests, syntax checks, `git diff --check`, and actual Diff
   review.
2. Commit the task branch.
3. Integrate using the least invasive operation.
4. Push only with explicit authorization and only after checking remote
   divergence.
5. Deploy the exact Git-derived file list, restart affected services, run
   formal regression, and verify protected-data fingerprints.
6. Generate the shared handoff and report the full Commit SHA.

## Retire

- Remove clean merged Worktrees after confirming that no active task owns them.
- Preserve valuable dirty work on an `archive/<topic>-wip-<date>` branch before
  removing its Worktree.
- Keep paused unmerged experiment branches only when their status or recovery
  pointer is documented.
- Move generated outputs outside Git; do not create archive commits containing
  runtime reports or sensitive traces.
- Do not manually remove active `.codex/worktrees/*`.
- Re-run `git worktree list` and `project_status.py` after cleanup.
