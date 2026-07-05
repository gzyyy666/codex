---
id: 0004-canonical-fitness-ledger-source-and-memory
type: decision
status: active
updated: 2026-07-05
tags: [fitness-ledger, source, memory, backup, cleanup]
---

# Canonical Fitness Ledger Source And Memory

## Decision

Use `projects/fitness-ledger/` in `gzyyy666/codex` as the durable source checkpoint and documentation authority. Keep live personal JSON only in the local working application.

Use one canonical local clone at `%USERPROFILE%\Documents\Codex\github-memory`.

## Consequences

- Git commits and tags replace copied full-project source backups.
- Local `data/backups/` remains the personal-data recovery mechanism.
- Intermediate QA screenshots, browser profiles, caches, and bytecode are disposable.
- Future conversations recover context from indexed Markdown rather than raw chat or compressed conversation memory.
- Every stable source checkpoint must pass documented validation before push.

## Rejected Alternative

Keeping many dated full-project folders was rejected because it duplicated hundreds of megabytes, mixed source with private/runtime artifacts, and made the correct rollback point unclear.
