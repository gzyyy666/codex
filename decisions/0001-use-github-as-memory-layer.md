# 0001 Use GitHub As Memory Layer

Date: 2026-06-17

Status: Accepted

## Context

Codex conversations are useful for immediate work, but durable preferences, workflows, and project background need a stable place that can be reviewed, versioned, and shared across tasks.

## Decision

Use a GitHub repository as the durable memory layer. Store long-term context as Markdown files, grouped by purpose:

- `memory/` for durable context
- `decisions/` for decision records
- `workflows/` for repeatable procedures
- `skills/` for Codex Skill definitions
- `templates/` for reusable node formats

## Consequences

- Memory changes become reviewable through Git history.
- Important context can be referenced from issues, pull requests, and Codex sessions.
- Sensitive data must be deliberately excluded.
- Old or superseded memory should be archived instead of silently overwritten.

