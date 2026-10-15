# Rule and methodology scope

Use this map when a document's role is unclear, not as an extra required read
before every task. Current user scope and project AGENTS govern execution.

## Read each kind of document for its purpose

| Kind | Current entry | How it affects work |
| --- | --- | --- |
| Task execution | `../../AGENTS.md`, `FL_TASK_ROUTING.md` | Knowledge-gap research, risk-based verification and authorization |
| Test selection | `../../REGRESSION_CHECKLIST.md` | Select meaningful checks for the changed behavior |
| Publication/recovery | `../maintenance/CODEX_RELEASE_CLOSEOUT.md`, `../maintenance/ROLLBACK.md` | Only when the named operation is authorized |
| Data and API contract | `../maintenance/NOTES_INPUT_STANDARD.md`, `../../web_desktop/ARCHITECTURE.md`, relevant cloud/Mini contracts | Preserve raw text, identity, transaction and access semantics; do not relax them for speed |
| Visual identity | `../design/STYLE_BIBLE.md` and the affected recipe | Reuse product identity; dated screenshots are examples, not immutable layouts or all-width test quotas |
| Environment | `../maintenance/PROJECT_LAYOUT.md`, `../maintenance/ENVIRONMENT.md` | Source/runtime/data separation; operational state still needs appropriate live evidence |
| Historical status/evidence | `../CURRENT_STATUS.md`, dated QA/audit/release reports, old ADRs | Explain past choices, not today's SHA/configuration or mandatory work |
| Candidate methods | `../maintenance/REFACTORING_PLAN.md`, paused experiments | Hypotheses/proposals; no automatic refactor, cleanup, migration or deployment |
| Generic repository workflows | `../../../../workflows/README.md` | Selected by the requested task, not added to every FL change |

An old document's “current”, “must”, fixed version or successful test result
does not turn its historical context into a live fact. Check scope and date
before adopting a requirement. If a contract's actual meaning is disputed,
inspect its owning source/tests rather than treating a stale feature summary
as proof that the behavior is missing or complete.

## Reusable operating method

1. **Locate ownership:** source, formal runtime, data and remote replicas are
   distinct. Develop in source; do not mirror formal app back by default.
2. **Bound the question:** locate/reproduce the actual task before external
   research, architecture changes or specialist skills.
3. **Select evidence:** validate the changed user path and meaningful adverse
   cases. Add widths/platforms/contract suites only where impact justifies them.
4. **Reuse valid evidence:** candidate, runtime and assumptions unchanged means
   no automatic rerun. A related change or failure invalidates relevant evidence.
5. **Close proportionately:** unpublished source, bounded publication and
   consequential boundary changes use different evidence, not all workflows.

Do not use a methods document to overrule explicit user scope, infer standing
cloud/Push/data permission, or add an approval pause where no user decision is
needed. Keep uncertainty visible without expanding unrelated work.

## Preserve these boundaries

- Formal personal records and credentials stay outside Git and public artifacts.
- Ledger writes use the shared command/lock/checkpoint/atomic/rollback boundary.
- Raw input and movement identity are preserved under the product contract.
- Source rollback and paired personal-data recovery remain separate operations.
- Replica clients stay read-only for formal ledger data; optional text inbox
  writes do not grant a formal-ledger write path.
- Cloud timestamp/CLI success, source fixture success and device evidence are
  different claims; only report what was actually verified.

These are relevant correctness constraints, not an all-task verification list.
