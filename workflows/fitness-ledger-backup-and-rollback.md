# Fitness Ledger Backup And Rollback

## Purpose

Create durable GitHub source checkpoints while keeping personal fitness records private, and restore either source code or local data without confusing the two.

## Create A Source Checkpoint

1. Run syntax, regression, smoke, and Web tests in the working application folder.
2. Refresh `projects/fitness-ledger/` from the working folder.
3. Exclude `data/`, `backups/`, logs, caches, browser profiles, spreadsheets, and temporary files.
   Also exclude generated `cloud_sync/out/*.json`, because the read-replica payload contains personal fitness data.
4. Update `memory/fitness-ledger-state.md` when architecture or durable behavior changes.
5. Update the source mirror `CHANGELOG.md` and design documentation.
6. Review `git diff --stat` and confirm that no personal JSON or credentials are present.
7. Commit with a concrete checkpoint message and push to `origin/main`.
8. Record the commit hash in the user-facing recovery document.

## Automatic Checkpoint Triggers

During an active Codex maintenance turn, create and push a source checkpoint without waiting for a separate reminder when a verified change materially affects one or more of these areas:

- stable user-facing functionality or interaction behavior;
- parser, movement dictionary, save, backup, or recovery rules;
- desktop, Web, or mobile architecture and entry points;
- an accepted visual-system milestone that should be recoverable;
- maintenance documentation required to understand or restore the project.

Do not create a checkpoint for unverified experiments, minor cosmetic tweaks, generated QA screenshots, browser profiles, caches, local personal data changes, or work that the user has not accepted as stable. When several related changes are in progress, group them into one coherent checkpoint after verification instead of pushing every small edit.

This automation applies only while Codex is actively handling a request. It is not a background service and cannot run after the conversation or computer session has ended.

## Restore Source Code

1. Identify the desired commit with `git log -- projects/fitness-ledger`.
2. Create a safety copy of the current working application folder.
3. Restore `projects/fitness-ledger/` from the selected commit into a temporary directory.
4. Copy only source, viewer, asset, documentation, and tool files into the working application folder.
5. Do not overwrite the working application's `data/` directory.
6. Run syntax, regression, smoke, and Web tests before launching normally.

## Restore Personal Data

1. Close all Fitness Ledger desktop, Web, and mobile viewer processes.
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
