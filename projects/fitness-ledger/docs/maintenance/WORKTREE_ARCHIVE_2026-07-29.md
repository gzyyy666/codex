# Worktree Archive — 2026-07-29

This is the recovery inventory produced by the 2026-07-29 workspace hygiene
closeout. None of these references is a formal product baseline.

## Preserved WIP branches

- `archive/formal-local-semantic-hint-web-ui-wip-20260729`
  - Commit: `82ba7ee196fcb98fa4219ac8b9ee9639d483ddc8`
  - Meaning: superseded natural-language Preview/confirmation UI alternative.
- `archive/intelligent-export-core-mvp-wip-20260729`
  - Commit: `8504da3c83ffa91ecb03c970acade13def70648d`
  - Meaning: legacy local semantic-hints and Planner experiment.

Both branches were pushed to `origin`. They must not be merged into `main`
without a new compatibility review against the current frozen protocol.

## Historical experiment Tags

- `archive/analysis-export-formal-readonly-validation-20260729`
  -> `414b28cbf6785e8607cbdbde76df8e9012e0e168`
- `archive/analysis-export-request-mvp-20260729`
  -> `71d83aed0267f8007f3382081141688aab000e15`
- `archive/formal-local-semantic-hint-adapter-20260729`
  -> `f08f56b3aab0b5ba7b74a145dca791d0a45eb67c`
- `archive/formal-local-semantic-hint-integration-20260729`
  -> `bde19d44ac4d63ab44c9d6e1fb4f7b8e53cd1c26`
- `archive/intelligent-export-core-mvp-20260729`
  -> `c13fd9bbbe87d23b21bcdea611afad21f33c86b6`
- `archive/intelligent-export-registry-convergence-20260729`
  -> `557dbfc68e6bd23798ac6f39c185c66a4547556b`
- `archive/local-semantic-request-interpreter-lab-20260729`
  -> `6e51a27a74d5ba81e677689ea60c8cabb8b3f3cd`

These annotated Tags were pushed before the obsolete local feature branches
were deleted.

## Separately retained paused experiment

`feat/custom-daily-metric-web` remains available locally and on `origin`, with
the existing `custom-daily-metric-pilot-reviewed-paused` Tag. Its recovery rules
remain in `docs/experiments/EXPERIMENTS_INDEX.md`.

## Generated output archive

Two anonymous holdout result files were moved outside Git to:

`C:\Users\26087\Documents\Codex\fitness-ledger-local-archives\2026-07-29-worktree-cleanup`

They were not committed because generated reports and model-evaluation output
are local runtime artifacts.

## Worktree cleanup

Sixteen clean Worktrees under
`C:\Users\26087\Documents\github-memory-worktrees` were removed after their
dirty work had been archived and all remaining Worktrees were verified clean.
Their recoverable history is represented by `main`, the archive branches, the
archive Tags, or the paused Custom Daily Metric branch.

Codex-managed `.codex/worktrees/*` were deliberately not removed because they
may still belong to active or retained Codex tasks.
