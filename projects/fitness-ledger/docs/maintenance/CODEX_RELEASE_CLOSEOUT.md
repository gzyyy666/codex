# Proportionate release closeout

Choose closure from the actual diff, affected behavior, and authorization.
Use one common short path, then add risk-specific checks. Research is governed
by `../agent/FL_TASK_ROUTING.md`; sealing does not activate it.

## Authorization

- **Development / review:** prepare and verify a candidate in the task
  Worktree. A reviewable diff or commit is sufficient; no implicit merge,
  Push, Tag, formal deployment, service restart, data change, or cloud upload.
- **Review Deployment:** an explicit request permits scoped reversible
  publication to the named target before final acceptance. Keep a rollback
  point and verify the actual target. It does not authorize final integration,
  remote Push, unrelated files, protected-data mutation, or provider changes.
- **Seal / finalise / 封板:** the user's authorization permits the named
  integration/publication scope. Honor acceptance already given; do not add
  a second approval ceremony or repeat permission questions. Push, data
  changes and provider uploads must be covered by the actual authorization.

A request to finish implementation is not publication authorization. Conversely,
do not demand an exact phrase when the intended publication scope is explicit.

## Source-only closeout

For docs/tests or an unpublished implementation candidate:
review scope and the actual diff, run relevant checks and `git diff --check`,
then report the diff/commit and its location. Only update documentation made
stale by the change. Skip runtime/data status, formal service checks, deployment
backups, release Tags, and shared runtime handoff. They cannot verify a
documentation-only edit. Preserve a useful candidate; do not require commit
or integration when an explicit uncommitted diff is the agreed output.

## Quick Seal: bounded local publication

Use when source and target provenance are clear, the change is isolated, and
there is no consequential change to saving, identity, schema, migration,
recovery, security, cloud/provider state, cache lifecycle, or cross-surface
contract. File location alone is not a risk category: a Core wording change or
PWA copy change is not automatically a data-contract release.

1. **Confirm once:** live status, source baseline, authorized target, reviewed
   Git-derived A/M/D/R file list, and rollback point. Stop only for unexplained
   drift that could affect this publication; do not overwrite unrelated
   candidates or clean their Worktrees.
2. **Check the change:** focused syntax/test and actual diff review; reuse
   passing evidence for the same candidate. Re-run when code, candidate
   identity, runtime, or relevant assumptions changed.
3. **Publish the reviewed scope:** integrate/Push only as authorized; back up
   changed deployed files, apply precisely that list, and restart only an
   affected loaded service. Source-only files need no application writeback.
4. **Verify and receipt:** check actual changed behavior/resources on the named
   formal entry and relevant runtime health. Compare protected data only when
   deployment/test paths can touch it. Produce the concise receipt below.

Do not audit unrelated Worktrees, run unrelated suites, clean the repository,
refresh every document, create a Tag, or repeat a full baseline scan by default.

## Full Seal: add checks for the actual risk

Use for consequential boundary changes or unclear provenance. It means the
common publication path plus the applicable checks below, not every row.

| Changed boundary | Additional evidence |
| --- | --- |
| Parser/save/movement identity/shared data contract | Relevant contract/adverse-case regressions; temporary data for writes; preserve raw input and identity; data fingerprints for affected formal verification |
| Schema/migration/import/export/recovery | Reviewed source/target mapping, checkpoint, fixture replay, rejection/rollback, recovery verification; explicit formal-data authorization |
| Security/authentication | Allowed and rejected access, reviewed permissions; no unrelated rule/provider changes |
| Loaded Python backend | Restart the named service after deployment; verify actual process/build and affected behavior |
| Cloud Sync/provider | Explicit provider scope, payload/state comparison and provider readback; an upload exit code alone is insufficient; local SYNCED is not device proof |
| PWA/static resource/cache changes | Coherent entry/import/manifest/Service Worker versions when relevant; deployment preflight, live version/hash readback and actual upgrade/cache behavior for the change |
| Cross-surface contract | Relevant desktop/Web/PWA/Mini consumers and compatible behavior; identify unverified surfaces |
| Combining divergent candidates | Inspect the specific participating diffs and baselines; exclude unrelated active work |

A pure PWA copy/CSS release may use Quick Seal, but must retain the relevant
asset version group, preflight and live-resource/cache verification. A cache,
read/write contract or authentication change uses Full Seal.

If risk cannot be bounded, investigate the uncertainty and expand verification.
Do not shorten essential checks to meet an arbitrary time limit. Document
non-blocking limits without expanding the accepted change into unrelated fixes.

## Concise release receipt

Report: source commit/candidate; exact published target/scope; relevant checks
and live evidence; rollback point; any unverified boundary. Include remote
state only when integration/Push is part of the task. Include data results only
when data could be affected. Tags are optional unless project runtime identity
or the user requires one.

Run `python tools/project_status.py --write --handoff --json` after a formal
application release or cross-task integration that needs the shared runtime
handoff. A normal source-only change does not rewrite that shared handoff.

Worktree cleanup is separate maintenance unless this task's own retirement is
needed. Preserve active/unmerged work; follow `WORKTREE_LIFECYCLE.md`.
