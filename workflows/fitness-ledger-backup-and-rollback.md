# Fitness Ledger Backup And Rollback

## Purpose

Create durable GitHub source checkpoints while keeping personal fitness records private, and restore either source code or local data without confusing the two.

## Create A Source Checkpoint

1. Work in the canonical Git source/task checkout, not the formal runtime.
2. Select checks from `projects/fitness-ledger/REGRESSION_CHECKLIST.md` according
   to the changed behavior; do not run every desktop/Web suite by default.
3. Inspect the actual diff and scope. Exclude personal data, backups, credentials,
   profiles, caches, temporary files and generated `cloud_sync/out/*.json`.
4. Update only documentation made stale by the change; memory updates require
   the user's request and applicable memory-write policy.
5. Preserve a candidate diff or a meaningful verified source commit. Integrate,
   deploy or Push only within the user's authorization already given.
6. Report the relevant commit/candidate and recovery point; use the project
   closeout guide only when publication is in scope.

`tools/preview-fitness-ledger-mirror.ps1` is a legacy import/reconciliation aid,
not a routine source-refresh step. Use it only for an explicitly requested
formal-to-source recovery/import with reviewed provenance. Preview first and
apply only the accepted source scope; never make formal data a Git input.

## When a checkpoint is useful

A verified change may justify a local source checkpoint in the following
areas. This list does not authorize automatic Push, publication or memory writes:

- stable user-facing functionality or interaction behavior;
- parser, movement dictionary, save, backup, or recovery rules;
- desktop, Web, or mobile architecture and entry points;
- an accepted visual-system milestone that should be recoverable;
- maintenance documentation required to understand or restore the project.

Do not label unaccepted experiments or cosmetic tweaks as accepted release
milestones. A candidate commit is still useful when it preserves reviewable
work. Keep generated QA output, profiles, caches and personal data out of Git;
group related verified changes coherently without requiring Push for each edit.

This document creates no background job. Recurring automation requires a
separately requested, configured automation.

## Restore Source Code

1. Identify the desired commit with `git log -- projects/fitness-ledger`.
2. Preserve a recoverable copy/commit of the affected source at the intended restore target.
3. Restore `projects/fitness-ledger/` from the selected commit into a temporary directory.
4. Restore only the selected source scope into the task checkout. Deploy to the formal application only if that target and operation are explicitly authorized.
5. Do not overwrite the working application's `data/` directory.
6. Run checks relevant to the restored behavior; verify the actual formal entry only when deployment/launch is authorized.

## Restore Personal Data

1. Confirm explicit data-restore scope; stop only processes that can write the affected local data.
2. Copy the current `data/` directory to a new safety folder.
3. Select a paired tracker and movement-dictionary checkpoint from local `data/backups/`.
4. Validate both files as JSON before replacement.
5. Restore them together so movement IDs remain consistent.
6. Launch the desktop application and inspect recent Body, Diet, Training, and Movement records.

## Safety Rules

- Never upload personal tracker data to the public repository.
- Never restore source and data in one unreviewed bulk overwrite.
- Never delete the current local backup until the restored version has passed verification.
- Prefer a new corrective commit over rewriting Git history.
