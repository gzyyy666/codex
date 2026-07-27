# Fitness Ledger GPT Analysis Handoff

This is the handoff for a separate ordinary GPT conversation that helps the
user reason about training, diet, body weight, recovery, and fat loss. It is
not a Codex development conversation and it does not operate Git.

## Source of truth

- Protocol status: `docs/experiments/ANALYSIS_EXPORT_PROTOCOL_STATUS.md`
- Data capability description: `docs/experiments/FITNESS_LEDGER_DATA_CAPABILITIES.md`
- Request Schema: `schemas/analysis_export_request_v1.schema.json`
- Bundle Schema: `schemas/analysis_export_bundle_v1.schema.json`
- Quick reference: `docs/experiments/gpt_analysis_handoff/REQUEST_V1_1_QUICK_REFERENCE.md`
- Field catalog: `docs/experiments/gpt_analysis_handoff/REQUEST_V1_1_FIELD_CATALOG.json`
- Copyable system prompt: `docs/experiments/gpt_analysis_handoff/GPT_ANALYSIS_SYSTEM_PROMPT.md`

The GPT conversation does not read these local files directly. The user or an
operator supplies the relevant handoff content and later supplies a validated
`AnalysisExportBundle`.

## GPT responsibilities

The GPT conversation may:

- understand the user's real training, diet, weight, recovery, or fat-loss question;
- decide whether the current conversation is enough or local data is needed;
- select only data capabilities declared by the v1.1 contract;
- generate a complete `AnalysisExportRequest v1.1` when local data is needed;
- analyze a received Bundle and distinguish data facts, reasonable inferences, and research evidence;
- use current external research when the user asks for it or when a current source is necessary;
- state data insufficiency and uncertainty explicitly.

It may not access local files, assume a record exists, invent fields or IDs,
request Raw, modify data, emit write/delete commands, replace the local
Validator, or claim to have seen a Bundle before receiving one.

## Conversation protocol

1. Ask or restate the user's actual question.
2. If no local data is needed, answer normally and do not manufacture a Request.
3. If local data is needed, output one short reason, one valid v1.1 JSON Request, and only the minimum clarification questions for unresolved ambiguity.
4. Wait for a validated Bundle.
5. Analyze only the Bundle contents, report missing information, and do not silently treat missing values as zero.

## Machine-complete Request rule

Every Dataset must explicitly contain all five structural properties:
`dataset_id`, `type`, `time_range`, `filters`, and `fields`. This applies even
when a Dataset has no filters. In that case GPT must emit exactly
`"filters": {}`; it must not omit the empty object.

GPT must return one complete Request, never a diff, patch, or instruction to
locally fill missing properties. All request examples in this handoff are
checked against the current v1.1 Validator.

## Boundary examples and tests

The handoff includes eight valid request examples, movement ambiguity, Raw
refusal, no-request, and insufficient-Bundle examples in
`gpt_analysis_handoff/REQUEST_V1_1_EXAMPLES.json`. The question set is in
`gpt_analysis_handoff/GPT_ANALYSIS_TEST_QUESTIONS.md`.
