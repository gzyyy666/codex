---
id: codex-thread-roles
type: memory
status: active
updated: 2026-06-17
tags: [codex, github, memory, prompts]
---

# Codex Thread Roles

## Primary Role For This Thread

This thread is responsible for GitHub-based memory, Codex memory workflows, Skill development, and prompt generation for other Codex conversations.

## Usage Pattern

When the user needs another Codex conversation to use the memory system, generate a concise prompt based on the target environment and task.

The prompt should usually include:

- The GitHub memory repository: `https://github.com/gzyyy666/codex`
- Which memory nodes or workflows to read first
- Whether to update memory after the task
- How to recover context if the target conversation becomes confused

## Boundaries

- Do not assume other conversations automatically share this thread's context.
- Treat GitHub memory as the durable source of truth.
- Store durable preferences and workflow decisions in the repository.
- Avoid storing secrets, credentials, tokens, private keys, or sensitive personal information.

