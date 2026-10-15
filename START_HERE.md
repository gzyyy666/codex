# START HERE

Use this file when starting a new Codex conversation or recovering from a confused conversation state.

## Fast Project Recovery

For Fitness Ledger work, start from current project rules and read only the
task-relevant context:

1. `AGENTS.md`, then `projects/fitness-ledger/AGENTS.md`
2. `projects/fitness-ledger/START_HERE.md` when restoring project context
3. `projects/fitness-ledger/docs/INDEX.md` to locate task-specific references
4. A relevant memory/decision only when a historical choice needs explanation

For WeChat or CloudBase operations, use the current runtime/provider evidence
required by the task. Memory and dated reports explain previous work; they do
not establish today's deployment, configuration or sync state.

The public repository contains source and documentation, but never the user's live `data/` directory.

## Default Startup Prompt

```text
Please restore my working context from my GitHub memory repository:
https://github.com/gzyyy666/codex

Read the current AGENTS.md and the target project's entry/index.
Read only the memory, decision or workflow relevant to this request.
Continue authorized work from verified facts; ask only for material missing
information. Do not require a separate recovery confirmation or scan entire
memory/decisions/workflows directories for an ordinary task.
Do not update memory or publish issues merely because work produced a useful
lesson. Those actions require the user's request and applicable permissions.
```

## Recovery Prompt

```text
State recovery instruction:

Your current understanding may be off. Do not continue repairing previous reasoning.
Recheck disputed or stale assumptions while preserving the user's explicit
scope, constraints and authorization already given in this conversation.

Restore context from:
https://github.com/gzyyy666/codex

Read current project instructions and the relevant source/index first.
Use historical memory only where it explains the disputed context.
Continue independent authorized work; ask about unresolved facts only when
their answer changes the next action. Do not insert a mandatory approval pause.
```

## Prompt Request Pattern

When asking the dedicated GitHub/Codex memory thread for a prompt, provide:

- Target conversation purpose
- Relevant project or repository
- Whether the target conversation should only read memory or also update it
- Any constraints, such as language, output format, or risk level

