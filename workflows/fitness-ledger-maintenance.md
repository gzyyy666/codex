# Fitness Ledger Maintenance Workflow

## Start

1. Read `memory/fitness-ledger-state.md`.
2. Read `projects/fitness-ledger/START_HERE.md`.
3. Open `projects/fitness-ledger/docs/INDEX.md`.
4. Read only the task-specific source and documentation.

## Change

1. Protect live `data/` and raw text.
2. Use the shared command service for writes.
3. Keep changes inside the current authoritative program and Web files.
4. Update function indexes or design rules only when durable behavior changes.

## Validate

1. Run syntax checks.
2. Run the minimum regression set.
3. Run smoke tests for parser/save/dictionary changes.
4. Exercise real browser mouse and keyboard interaction for Web controls.
5. Confirm no personal JSON or credentials are staged.

## Checkpoint

1. Sync current source to `projects/fitness-ledger/` without local data, backups, caches, profiles, or intermediate QA images.
2. Update `CHANGELOG.md` and `memory/fitness-ledger-state.md`.
3. Review the diff.
4. Commit and push.
5. Add a Git tag for major stable milestones.

## Recover

Follow `projects/fitness-ledger/docs/maintenance/ROLLBACK.md`. Restore source and personal data separately.
