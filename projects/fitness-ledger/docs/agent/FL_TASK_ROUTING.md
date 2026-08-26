# Fitness Ledger Agent Task Routing

This document is the routing gate for Codex and other coding agents working on
Fitness Ledger. Classify the task before selecting a research skill, subagent,
worktree, external tool, or release action.

The purpose is to keep small changes short while reserving research-heavy
multi-role work for changes where it reduces real risk.

## Routing rule

Choose the smallest route that safely covers the task. If the scope or risk is
unclear, move up one level. Never downgrade a task because the change looks
small when it touches protected data, a write boundary, a schema, a migration,
or a formal release.

| Route | Use for | Default workflow | Research skill |
| --- | --- | --- | --- |
| **S — Small** | Text, copy, one known CSS value, a local test assertion, or a mechanical edit with no behavior/data-contract change | Worker → focused check → diff review | Skip; no web/community scan |
| **M — Normal** | A bounded change in an existing module, page, route, or test with no schema/migration/formal-data change | Context Navigator → short plan → Worker → focused QA | Lite only when the implementation or context is unfamiliar |
| **L — Substantial** | Parser, save boundary, movement identity/dictionary, cross-surface behavior, architecture, dependency, migration, redesign, or an expensive-to-reverse decision | Role A Operator → Role B Worker → independent review → verification | Full `two-role-community-first` |
| **R3 — Release/Data** | Formal directory, protected data, Cloud Sync/provider, deployment, service restart, or release integration | L route plus Release Gate, protected-data checks, and handoff | Full when the change is substantial; never bypass the release gate |

R3 is an escalation flag and cannot be treated as S. A task may be both L and
R3.

## Route details

### S — Small

Do not invoke `two-role-community-first`, broad web research, parallel agents,
or a new worktree for an S task. Use the existing task Worktree and run only
the checks relevant to the changed file, plus `git diff --check` and a final
diff review.

Use an explicit prompt such as:

```text
S route. Make only the requested mechanical change. Do not browse or run
research-heavy skills. Run the relevant syntax/test check and git diff --check.
```

### M — Normal

Read the project index and the task-relevant source/test map. Produce a short
plan before editing. Use the Lite form of a research skill only when there is
an unfamiliar implementation choice, external dependency, or meaningful
reuse question. Do not turn a bounded familiar change into a Full research
pass.

### L — Substantial

Use the complete two-role boundary:

1. Role A decides how the agent should operate, what context and verification
   are needed, and what user checkpoint is required.
2. Role B independently researches the actual solution and records
   ADOPT/EXTEND/COMPOSE/BUILD before implementation.
3. Independent reviewers check data safety, behavior, visual output, or
   architecture according to the changed surface.

Do not write to the formal directory or protected data during development /
review mode.

### R3 — Release/Data

Before any formal or provider action:

- run `python tools/project_status.py --write --json`;
- derive deployment scope from `git diff --name-status`;
- preserve and compare protected data fingerprints;
- restart affected services after deployed Python backend changes;
- run formal regression and write the task handoff;
- require the explicit `按规范封板` / seal instruction before merge, push,
  formal writeback, or real provider upload.

## Required task brief

For M, L, and R3 tasks, record these fields in the task prompt or a temporary
brief:

- outcome and acceptance evidence;
- route and why it was selected;
- in-scope files/surfaces and explicit non-goals;
- data and deployment boundary;
- required tests, screenshots, or runtime checks;
- rollback/checkpoint plan;
- user approval required, if any.

For S tasks, the prompt itself may be the brief.

## Exit evidence

- **S:** changed-file check, `git diff --check`, and reviewed diff.
- **M:** short plan, focused tests, reviewed diff, and remaining uncertainty.
- **L:** Operator Plan, reuse decision, implementation evidence, independent
  review, and relevant regression/visual checks.
- **R3:** all L evidence plus live status, deployment scope, service state,
  protected-data comparison, and handoff path.

The route is a control on agent machinery, not permission to skip correctness
checks. A small change still needs the smallest relevant verification.
