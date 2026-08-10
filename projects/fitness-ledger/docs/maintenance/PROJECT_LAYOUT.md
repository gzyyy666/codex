# Fitness Ledger Standard Project Layout

This document is the operating contract for future Codex tasks. It separates
versioned source, the formal local application, protected personal data, and
recoverable historical material.

## Authority

For this standardized installation, the current desktop launcher was treated
as the latest business baseline. The resulting paths are:

| Role | Path | Git policy |
| --- | --- | --- |
| Git workspace | `D:\FitnessLedger\source` | Versioned, branchable, reviewable |
| FL source | `D:\FitnessLedger\source\projects\fitness-ledger` | Versioned except ignored local state |
| Formal runtime | `D:\FitnessLedger\app` | Local runtime; not a Git worktree |
| Protected data | `D:\FitnessLedger\app\data` | Never commit, clear, rebuild, or replace casually |
| Automatic data backups | `D:\FitnessLedger\app\data\backups` | Keep with the formal data set |
| Manual project backups | `D:\FitnessLedger\app\backups` | Keep until the new installation is verified |
| Historical/QA archive | `D:\FitnessLedger\archive` | Recoverable but not active source |
| Temporary review output | `D:\FitnessLedger\work` | Disposable after review |

The live environment variable `FITNESS_LEDGER_FORMAL_DIR` and the desktop
shortcut must resolve to `D:\FitnessLedger\app`.

## What belongs in Git

Keep maintained Python, JavaScript, WXML/WXSS, HTML/CSS, source assets,
fixtures, tests, contracts, and durable operating documentation in Git.

Never put these in Git:

- `app\data\`, `app\data\backups\`, or any personal JSON;
- Cloud Sync payloads, reports, local provider configuration, or credentials;
- WeChat private project configuration and local environment files;
- browser profiles, QA work copies, Python bytecode, logs, temporary files;
- original spreadsheets and generated screenshots that are not accepted design
  evidence.

## Task startup

From `D:\FitnessLedger\source\projects\fitness-ledger`:

```powershell
python tools/project_status.py --write --json
```

The live status result is authoritative for Git, the formal directory,
Cloud Sync, and the Web service. A future task must stop on an unexplained
baseline mismatch rather than silently copying one side over the other.

For a source change:

1. Create or use a task branch under `codex/`.
2. Read `START_HERE.md`, `docs/INDEX.md`, the relevant function map, and the
   relevant regression checklist section.
3. Use anonymous fixtures or temporary directories for tests.
4. Derive deployment scope from `git diff --name-status`.
5. Run focused tests, `git diff --check`, and inspect the final diff.

For a formal runtime change:

1. Close the desktop app, Web service, and browser profile first.
2. Back up `app\data\` before any save or migration operation.
3. Change only the required formal source files; never bulk-overwrite `data`.
4. Restart the Web service after Python backend changes.
5. Compare protected data hashes before and after.

## Rollback boundary

Git restores source. `app\data\backups` restores personal state. The two must
be restored independently. Do not use a Git checkout to recover personal
JSON, and do not use a personal-data backup to roll back source code.

## Current cleanup policy

The active source tree contains only confirmed maintained resources. Historical
QA material and unreferenced visual variants live under `D:\FitnessLedger\archive`
with the migration date. The archive is recoverable and is not loaded by the
runtime.
