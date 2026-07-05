# START HERE

Use this file when starting a new Codex conversation or recovering from a confused conversation state.

## Fast Project Recovery

For Fitness Ledger work, do not reconstruct context from chat history. Read in this order:

1. `memory/fitness-ledger-state.md`
2. `projects/fitness-ledger/START_HERE.md`
3. `projects/fitness-ledger/docs/INDEX.md`
4. The task-specific file linked by that index

The public repository contains source and documentation, but never the user's live `data/` directory.

## Default Startup Prompt

```text
Please restore my working context from my GitHub memory repository:
https://github.com/gzyyy666/codex

Read these first:
- memory/preferences.md
- memory/projects.md
- memory/people-and-context.md
- memory/codex-thread-roles.md
- decisions/
- workflows/

Then summarize the restored context in 5 bullets or fewer before continuing.
If this task creates durable preferences, decisions, or reusable workflows, ask whether they should be added back to the memory repository.
```

## Recovery Prompt

```text
State recovery instruction:

Your current understanding may be off. Do not continue repairing previous reasoning.
Discard assumptions from this conversation that I have not explicitly confirmed.

Restore context from:
https://github.com/gzyyy666/codex

Read memory/, decisions/, and workflows/ first.
Then briefly restate the recovered working state and wait for confirmation before taking action.
```

## Prompt Request Pattern

When asking the dedicated GitHub/Codex memory thread for a prompt, provide:

- Target conversation purpose
- Relevant project or repository
- Whether the target conversation should only read memory or also update it
- Any constraints, such as language, output format, or risk level

