# Fitness Ledger task routing

Choose the smallest useful workflow. Judge three questions independently:
**What knowledge is missing? What behavior/data can change? What publication
has the user authorized?** Complexity, file count, and release work alone do
not require community research, multiple roles, or parallel agents.

## Start with local evidence

Read the relevant source/index and existing tests; reproduce a reported issue
when practical. Explain only decisions that matter, not a separate task brief
for every small change. For source-only work, identify HEAD/main/origin/main
and the changed scope. Use the live project status for runtime diagnosis,
formal deployment, data/provider actions, or an unexplained baseline mismatch.
An unrelated documented runtime drift does not block source-only documentation
work; never overwrite it or claim it resolved.

## Research: based on the knowledge gap

- **None:** existing code and evidence explain a familiar implementation/fix.
- **Targeted:** an unfamiliar API, unresolved runtime failure, or meaningful
  external implementation choice can change the next step. Use the targeted
  mode of `two-role-community-first`.
- **Deep:** targeted work exposes competing consequential approaches, or the
  user asks for a broad study. Add an operator role only if agent operation
  itself is an unresolved question.

New features do not automatically require research. High-risk fixes can need
strict local verification with no web research. Stop searching when the next
action and its verification are clear; report unresolved facts honestly.

## Verification: based on the affected behavior

Use `REGRESSION_CHECKLIST.md` as the single test-selection entry.
A changed file does not automatically require all tests for its directory.

| Impact | Default approach |
| --- | --- |
| Documentation, copy, known isolated CSS | Diff/link or syntax check; inspect visible result if applicable |
| Bounded existing interaction or logic | Focused tests and the actual affected user action |
| Shared save/parser/identity/schema/auth/recovery contract | Relevant contract, adverse-case and rollback tests; independent review when uncertainty or consequence justifies it |
| PWA/cache/cloud/provider | The changed contract plus the relevant resource, cache, authentication or provider readback checks |

Select independent review for meaningful residual risk, not merely because a
file lives in Core. Use subagents only when authorized and when an independent
question or separable work justifies the overhead. A reviewer can be a separate
human review; do not claim independence for the same pass reviewing its own work.

For runtime-only failures, consider `local-program-debugging` when available:
trace the actual launcher/process/resources and user action. Do not invoke it
for an understood copy edit.

Use Product Design skills for an actual UX/design audit or substantial visual
work, not ordinary source review or a known button fix. Existing-project fixes
should preserve the established UI and use the actual rendered result; do not
add design research, image generation or external redesign tools by default.
Firecrawl/XCrawl are retrieval options when research needs them, not additional
mandatory research passes. Codex repair, workbook, video and artifact skills
apply to their named tasks, not ordinary Fitness Ledger source maintenance.

## Closure: based on publication scope

Use `docs/maintenance/CODEX_RELEASE_CLOSEOUT.md` for authorized publication.

- **Source-only closeout:** relevant checks, reviewed diff, candidate/commit.
  No formal health, data hashes, restart, upload, or shared runtime handoff.
- **Quick Seal:** known bounded local publication; baseline/scope, focused
  checks, rollback, exact deployment, actual changed behavior, concise receipt.
- **Full Seal:** consequential contract/data/security/cloud/cache changes or
  unresolved deployment provenance. Add only the relevant risk checks.

Formal publication, protected data, provider upload, and remote Push retain
their explicit authorization boundaries. Reuse authorization already given in
the conversation; do not ask again for the same scope. Review Deployment and
final sealing remain separate permissions. Formal publication does not imply
all-L research.

## Compatibility with older prompts

S/M/L are optional scope labels, not execution machinery:
S = isolated mechanical; M = bounded behavior; L = wider contract/uncertainty.
R3 is a publication/data modifier, not a requirement to perform all L work.
Legacy labels must not override the independent research/verification/closure
decisions above. Resolve material uncertainty with a targeted inspection
before choosing additional steps; do not automatically escalate a whole route.

Historical memory, old chat summaries and prior release reports are evidence
of earlier work, not current workflow mandates. Read the current task rules
before reusing their former Full Seal, research or testing requirements.

Use an existing task Worktree. Create an isolated one when needed to protect
main or separate concurrent edits; no nested Worktree solely because a route
label says so. Read the experiments index when related implementations might
reuse a paused experiment.

## Evidence to return

For small work: what changed, focused checks, and candidate/published status.
For higher impact: add remaining uncertainty, relevant adverse-case evidence
and the deployment receipt. Keep reports proportional; do not manufacture
research registries, plans, screenshots, or tests that add no decision value.
