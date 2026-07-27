# Analysis Export Next Conversation Plan

Plan status: `AUTHORISED_DISPATCH_PLAN`

This plan is based on the live check performed on 2026-07-27. The requested
anonymous-materialization branch and Worktree were not present or occupied at
that check.

## Current JSON protocol conversation

After this documentation and dispatch commit, this conversation ends and is
archived. It does not continue anonymous materialization, formal-data access,
Web UI work, or local-model work. The protocol is frozen and the accepted
baseline is preserved in:

- Protocol/GPT freeze commit: `91edfba775feb9e46f479e6a7aafa7bc187cd6ef`
- Accepted protocol commit: `0af0914f001c01d8f1e1dc1931e685a4591fb04c`

The dispatch metadata commit that contains this plan is not the materializer
baseline; the materializer starts from the exact freeze/GPT commit above.

## Ordinary GPT analysis conversation

Open it immediately after this handoff is available. Copy only
`docs/experiments/gpt_analysis_handoff/GPT_ANALYSIS_SYSTEM_PROMPT.md` into a
new ordinary GPT conversation. That conversation:

- does not operate Git;
- does not read local files directly;
- decides whether a local Request is needed;
- generates and explains a legal v1.1 Request when needed;
- waits for a validated Bundle before local-data analysis;
- may be tested with real user questions before the Materializer exists, but cannot receive a real Bundle yet.

When the Materializer is accepted, supply the resulting Bundle to this same
GPT analysis conversation. It must analyze only the Bundle and its quality,
missing-information, warning, and provenance sections.

## Next Codex development conversation

Open a new Codex conversation for exactly one task:
`Anonymous Deterministic Materialization`.

- Branch: `feat/analysis-export-anonymous-materialization`
- Worktree: `C:\Users\26087\Documents\github-memory-worktrees\fl-analysis-export-anonymous-materialization`
- Baseline: `91edfba775feb9e46f479e6a7aafa7bc187cd6ef`
- Handoff: `docs/experiments/ANALYSIS_EXPORT_ANONYMOUS_MATERIALIZATION_HANDOFF.md`
- Creation must be performed by that new conversation after rechecking that the branch and path remain unoccupied.

Use a new conversation because the protocol conversation is now a completed
contract review, while Materialization has a separate implementation scope,
fixture evidence, and stopping point. Do not use the old Shadow Planner branch
as a baseline and do not continue this JSON protocol conversation for it.

## Required order and gates

1. Freeze/GPT handoff documentation: complete in this conversation.
2. Ordinary GPT analysis conversation: may start immediately for Request-generation testing.
3. Anonymous Deterministic Materialization: new Codex Worktree from the freeze/GPT commit.
4. `anonymous_materialization_review`: Bundle, JSON, Markdown, missing-data, relation, and safety evidence accepted.
5. Formal read-only validation: a separate Codex conversation and Worktree from the accepted Materializer commit; explicit authorization is required. It may inspect only the formal read-only surface, record hashes before/after, and must not write.
6. `web_integration_review`: only after anonymous materialization and formal read-only validation pass. Start from the then-current Web/main line, introduce the accepted Materializer through a narrow service/provider boundary, and keep the v1.1 Validator authoritative.
7. `release_review`: only after Web review and all safety/regression gates. No Release Tag is created before that review.

## Formal-data read-only validation

Do not create it now. It must be a separate conversation and Worktree after
the anonymous Materializer has an accepted Commit. It validates the same legal
v1.1 Requests against the formal read-only data surface, compares counts and
quality without exposing Raw content, and records protected-data hashes before
and after. It cannot be combined with anonymous Materialization because the
fixture path and formal-data path must remain independently auditable.

## Web UI conversation

Do not start it now. Web UI requires both `anonymous_materialization_review`
and `formal_readonly_validation` to pass. At that time it should branch from
the then-current Web/main integration line, not from this local-analysis
Worktree, and introduce the accepted Materializer through a stable service/API
contract. Reserve a provider boundary for future implementations, but keep
the Validator and deterministic Materializer as the only authority. Starting
Web now would mix an unmaterialized Bundle contract with UI behavior and make
the data-safety review non-isolated.

## Local model Lab

The existing Lab remains independent and non-blocking:

- Branch: `feat/local-semantic-request-interpreter-lab`
- Worktree: `C:\Users\26087\Documents\github-memory-worktrees\fl-local-semantic-request-interpreter-lab`
- It must not be modified by the Materializer task.
- Its future narrow interface is `LocalSemanticModelProvider`, producing an untrusted `RequestDraft` only.
- The Draft must pass the same v1.1 Validator and cannot access Raw, Executor, formal data, or Web directly.
- Lab results may enter Web only after independent model review and the existing Web gates; they never block deterministic export.

## Stop points

- Stop after this documentation/dispatch Commit and archive this conversation.
- Stop the new Materializer conversation after its local Commit and Review package.
- Stop formal read-only validation after hashes and report are reviewed.
- Stop Web integration after preview/API review; do not infer release approval.
