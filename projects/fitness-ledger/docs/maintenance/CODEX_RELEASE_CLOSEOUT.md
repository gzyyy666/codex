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
  formal release. Select Quick Seal only when every eligibility condition below
  is satisfied; otherwise complete the Full Seal gates. Do not infer
  authorization from “完成”“finish” or a review URL alone.

## Quick Seal for source-clear, low-risk changes

Quick Seal is intended for small fixes whose source, behavior, and deployment
scope are already clear (for example, a localized UI interaction or copy fix).
It avoids repeating broad audits that cannot change the release decision.

Every condition must be true:

- The live baseline is understood, `main` and the intended remote baseline have
  no unexplained divergence, and the task Worktree is clean apart from this
  reviewed change.
- The diff is small, isolated, and limited to a known UI/client behavior,
  wording, test, or documentation scope. The exact source-to-formal file map is
  known before writeback.
- No protected data, data model/schema, API contract, parser/save boundary,
  migration, import/export/recovery behavior, security/auth, Cloud Sync,
  provider, PWA/mobile viewport/service worker, or cross-surface contract is
  changed.
- Focused automated/browser tests and relevant syntax checks pass; the diff is
  reviewed and `git diff --check` passes.

Quick Seal still requires explicit release authorization. Its sequence is:

1. Run `python tools/project_status.py --write --json`; confirm live Git,
   formal deployment, protected-data fingerprints, and service state. Stop on
   unexplained drift.
2. Review `git diff --name-status` and the full diff. Confirm no data, PWA,
   Cloud, or unrelated files are included. This scoped proof replaces an
   exhaustive comparison of unrelated Worktrees; do not merge, clean, or stop
   their work.
3. Run only the focused tests, syntax checks, and `git diff --check` relevant
   to this change. Record the results.
4. After explicit authorization, commit and integrate the reviewed change
   using the least invasive operation. Push only when authorized. Create a
   release tag only when required by the runtime identity or explicitly
   requested; the commit remains the source of truth either way.
5. If the change is source-only (docs/tests), do not write to the formal app.
   Otherwise create a recoverable backup of only the changed deployed files,
   then deploy only those files. Restart only the affected service when needed.
6. Verify formal health and the changed behavior on the formal entry point;
   confirm deployment status and protected-data fingerprints are unchanged.
   Do not perform Cloud or PWA uploads unless they are explicitly in scope and
   separately authorized.
7. Run `python tools/project_status.py --write --handoff --json`, confirm the
   task Worktree is clean and `HEAD/main/origin/main` are understood, then
   report the commit, exact scope, focused test results, rollback point,
   protected-data result, and handoff path.

If any eligibility condition fails or new risk appears, stop the Quick Seal
route and use Full Seal. Quick Seal must not be used to shorten verification
for a change that touches the excluded boundaries above.

## Full Seal: mandatory sequence

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
