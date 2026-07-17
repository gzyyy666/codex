# Rollback Guide

Source and personal data use separate recovery systems. Never restore them as one bulk operation.

## Source Rollback

1. Open the GitHub memory repository.
2. Review commits affecting `projects/fitness-ledger/`.
3. Create a temporary branch or export the desired commit.
4. Copy source, assets, documentation, and tools into the local working project.
5. Do not copy a repository `data/` directory; none should exist.
6. Run compilation, regression, and smoke tests.
7. Launch Desktop and Web and inspect recent records without saving.

Do not hard-code a stable tag in a task prompt. List tags in the live repository (`git tag --list --sort=-creatordate`), confirm the requested tag or full Commit, and use `project_status.py` before restoring. The 2026-07-05 web tag is historical, not the default current baseline.

## Personal Data Rollback

1. Close Desktop, Web, and mobile processes.
2. Copy the current local `data/` directory to a temporary safety location.
3. Select a paired tracker and movement-dictionary checkpoint from `data/backups/`.
4. Validate both JSON files.
5. Restore both files together.
6. Launch the desktop app and inspect Body, Diet, Training, Movement Progress, and raw entries.

## Why Old Full-Project Backups Are Not Needed

- Source history is versioned by Git commits and tags.
- Live data is protected by timestamped local JSON backups.
- A full copied project mixes source, personal data, caches, browser profiles, and generated images, making rollback less clear and consuming hundreds of megabytes.

## Emergency Prompt

```text
Recover Fitness Ledger from GitHub without touching personal data.
Read projects/fitness-ledger/START_HERE.md and docs/maintenance/ROLLBACK.md.
Identify the requested Git commit or tag, restore source only, and run the documented validation suite before launch.
```
