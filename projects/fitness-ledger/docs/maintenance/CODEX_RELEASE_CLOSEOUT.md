# Codex release closeout

This document is the mandatory closeout checklist for a Fitness Ledger task that
has reached formal release / sealing. It applies to repositories with a formal
business directory, generated indexes, multiple Worktrees, and optional PWA or
Cloud Sync surfaces.

## Closure level

Classify the task before acting:

- **Development / review:** work only in the task Worktree. Run tests and leave
  a reviewable commit or explicit diff. Do not merge, push, tag, deploy, or
  write the formal directory.
- **Seal / finalise:** continue only after explicit user authorization for
  formal release. Complete every gate below; do not infer authorization from
  “完成”“finish” or a review URL alone.

## Mandatory seal sequence

1. Confirm the live baseline with `python tools/project_status.py --write --json`.
   Record `HEAD`, local `main`, `origin/main`, all Worktrees, and the formal
   directory fingerprint. Stop on an unexplained mismatch.
2. Read `AGENTS.md`, `START_HERE.md`, `PROJECT_CONTEXT.md`,
   `docs/experiments/EXPERIMENTS_INDEX.md`, and the relevant schema/API and PWA
   deployment documents.
3. Derive the candidate scope from `git diff --name-status`. Inspect the actual
   diff, including deleted/renamed files, generated artifacts, and binary assets.
4. Run the relevant unit, contract, browser, export/import, PWA, and formal
   regression tests. Run syntax checks and `git diff --check`.
5. Obtain and record human acceptance of the candidate.
6. Obtain explicit user authorization to seal / publish.
7. Commit the candidate, merge it into `main` using the least invasive allowed
   operation, and push the intended remote branch.
8. If a formal business directory exists, create a recoverable backup point and
   synchronise only the files derived from the reviewed Git diff. Never copy
   formal `data/**` into Git or a Worktree.
9. Restart affected services. Run formal health checks and regression tests;
   verify protected data hashes and expected file fingerprints before/after.
10. Update only documentation made factually stale by the release: this file,
    `START_HERE.md`, `PROJECT_CONTEXT.md`, schema/API docs, `CHANGELOG.md`, and
    the experiments index as applicable. Search for and resolve contradictory
    old instructions; do not mechanically refresh dates.
11. Create the project-required Tag only after formal verification passes.
12. Remove only merged, inactive Worktrees/branches after confirming no active
    task owns them. Preserve valuable unmerged work on an explicit archive
    branch or status document.
13. Re-run `git worktree list` and `python tools/project_status.py --write
    --handoff --json`. Confirm local `main`, `origin/main`, and the production
    baseline match the project's defined identity.

## Required final report

Report the full baseline commit and Tag (if required), `HEAD/main/origin/main`,
clean Worktree status, exact deployment files, formal fingerprints before and
after, test commands/results, rollback point, and the generated handoff path.

## PWA and parallel Worktree gate

Before sealing, enumerate every active Worktree and compare PWA files against
the candidate baseline. Explicitly identify whether a PWA implementation is:

- included in the candidate and tested;
- an older or divergent attempt that must not be copied; or
- intentionally out of scope and documented as such.

Do not merge or copy a second PWA implementation merely because its directory
looks newer. Compare its API contract, data model, session semantics, movement
category mapping, assets, tests, and deployment notes first.
