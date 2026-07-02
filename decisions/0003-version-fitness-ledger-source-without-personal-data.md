# 0003 Version Fitness Ledger Source Without Personal Data

Date: 2026-07-02

Status: Accepted

## Context

Fitness Ledger needs durable GitHub rollback points and recoverable project context. Its local JSON database contains personal body, diet, and training records, while the repository is public.

## Decision

Store a complete non-sensitive source mirror under `projects/fitness-ledger/`, including maintained application code, viewers, visual assets, maintenance documents, and tests. Exclude personal JSON, backups, logs, caches, browser profiles, and spreadsheets. Store project context and recovery instructions separately under `memory/` and `workflows/`.

## Consequences

- Any committed source version can be restored from GitHub.
- Long-term project context can be rebuilt without relying on a single conversation summary.
- Personal data rollback remains a separate local operation using `data/backups/`.
- A source rollback and a data rollback must never be confused or performed as one destructive step.

## Links

- Related memory node: `memory/fitness-ledger-state.md`
- Recovery workflow: `workflows/fitness-ledger-backup-and-rollback.md`

