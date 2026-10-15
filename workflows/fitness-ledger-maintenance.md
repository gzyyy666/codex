# Fitness Ledger Maintenance Workflow

Project task routing, test selection and publication rules are maintained in
`projects/fitness-ledger/AGENTS.md`, `docs/agent/FL_TASK_ROUTING.md`,
`REGRESSION_CHECKLIST.md` and `docs/maintenance/CODEX_RELEASE_CLOSEOUT.md`
(paths after AGENTS are relative to the project). They override this older
summary. Read only the references relevant to the actual change.

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

1. Review the diff and relevant checks; preserve a candidate diff or commit.
2. Update only documentation made stale by the change. Memory changes require
   the user's explicit request; do not update memory as routine closeout.
3. Integrate, publish or Push only within authorization already given.
4. Use the applicable closeout route; Tags and broad cleanup are not routine
   requirements for small fixes. Do not copy formal data into source.

## Recover

Follow `projects/fitness-ledger/docs/maintenance/ROLLBACK.md`. Restore source and personal data separately.
