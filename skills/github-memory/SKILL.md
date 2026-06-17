---
name: github-memory
description: Manage durable Markdown memory nodes in a GitHub-backed repository. Use when Codex needs to create, update, review, archive, or reference personal/project memory files, decision records, workflow notes, or reusable context stored under memory/, decisions/, workflows/, templates/, or skills/.
---

# GitHub Memory

## Overview

Use the repository as a versioned memory layer. Prefer updating existing nodes over creating duplicates, and keep durable memory separate from temporary chat notes.

## Workflow

1. Locate the memory repository root. Look for `memory/`, `decisions/`, `workflows/`, and `templates/`.
2. Read relevant existing nodes before writing new ones.
3. Decide whether the request needs:
   - a memory node in `memory/`
   - a decision record in `decisions/`
   - a reusable process in `workflows/`
   - a template in `templates/`
4. Update the smallest relevant file set.
5. Use YAML frontmatter for memory nodes.
6. Avoid secrets, credentials, private keys, tokens, and sensitive personal data.
7. Summarize what changed and why.

## Memory Nodes

Use `templates/memory-node.md` when creating a new node. Required fields:

- `id`: stable kebab-case identifier
- `type`: usually `memory`
- `status`: `active` or `archived`
- `updated`: ISO date
- `tags`: short searchable tags

Keep nodes short. If a node grows beyond one focused topic, split it.

## Decisions

Use `templates/adr.md` for choices that affect future behavior. Create a decision record when a change would be useful to review later, such as adopting a tool, changing a workflow, or rejecting an alternative.

## Maintenance Rules

- Prefer explicit dates over relative dates.
- Mark superseded information as archived instead of deleting it.
- Link related memory, decisions, issues, and workflows when helpful.
- Keep wording factual; do not store unverified assumptions as facts.
- If a user asks for GitHub Issues, use `templates/github-issue.md` as the shape.

## Optional Reference

Read `references/node-taxonomy.md` when choosing where a new piece of context should live.

