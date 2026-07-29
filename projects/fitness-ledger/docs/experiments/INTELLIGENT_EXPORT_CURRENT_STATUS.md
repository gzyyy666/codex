# Intelligent Export Current Status and Handoff

> Last reviewed: 2026-07-29

This is the current entry point for any new conversation working on Intelligent
Export. Read this file first, then follow the linked protocol, source, and test
documents. Historical experiment documents may describe an earlier stop point;
they are not allowed to override this current status without a newer reviewed
commit.

## Current product status

- The product owner has confirmed that the Intelligent Export UI has been
  published into the formal business application.
- The current local repository snapshot is `main` at
  `0824933f18c6806977360ed3d7fca60e64102777`.
- The local main Worktree is
  `C:\Users\26087\Documents\Codex\github-memory` and was clean at the last
  review.
- This Commit is a normal product/UI follow-up Commit; the effective Web
  Intelligent Export integration was merged earlier in the `c5c2837` review
  merge. Do not treat `5f2c8fc` alone as a model or protocol redesign.
- `origin/main` is a separate remote state and must be checked before any
  push, release, or CI claim. Local verification is not proof of remote
  publication.

The UI publication status and the algorithm acceptance status are separate:
the UI is available for product use, while the local semantic algorithm remains
an optimization and validation track.

## 2026-07-29 deterministic routing and direct-download review

The current formal-business assessment is:

- The bounded read-only export path basically meets the core use case when the
  user gives a Dataset and a time boundary, such as recent body, diet, or
  training records. It is safe, revalidated, and does not write formal data.
- It does not yet behave like an unrestricted “export everything” assistant.
  Full-history requests, open-ended analysis, ambiguous movement names, body-part
  movement discovery, and over-limit batches must remain explicit review states.
- The previous natural-language UI required the user to copy a generated JSON
  Request into the JSON Contract flow. The review branch now removes that extra
  handoff: one natural-language Export action performs local routing, formal
  read-only Preview, final revalidation, and direct JSON Bundle download.
- The natural-language panel no longer contains `QUICK EXAMPLES`. The JSON
  Contract remains available as an advanced/debug entry for protocol review.

This work is currently under review on branch
`codex/deterministic-export-routing`, based on
`main@0824933f18c6806977360ed3d7fca60e64102777`. It has not been merged into
`main` or written back to the formal directory. The protected Tracker and
movement-dictionary fingerprints remain unchanged.

## Authoritative boundaries

The frozen formal request contract remains `AnalysisExportRequest v1.1`:

- Schema: `schemas/analysis_export_request_v1.schema.json`
- Bundle Schema: `schemas/analysis_export_bundle_v1.schema.json`
- Deterministic Validator:
  `fitness_ledger_core/analysis_export_request.py`
- Formal read-only source:
  `fitness_ledger_core/formal_readonly_data_source.py`
- Materializer/export functions:
  `fitness_ledger_core/analysis_export_materializer.py`

The local semantic path is an adapter, not a replacement protocol:

```text
user text
  -> deterministic bounded parser
  -> optional narrow SemanticHint
  -> deterministic Request v1.1 assembly
  -> the same v1.1 Validator
  -> Web Preview state
  -> explicit confirmation and read-only export path
```

Complex open-ended questions should be returned as `planner_required` for the
GPT JSON Planner path. The local model must not invent a formal Request,
ExportPlan, movement identity, date, Notes scope, Raw permission, or execution
action.

The model and provider remain unable to:

- read or expose Raw data;
- choose formal record IDs;
- grant Notes scope;
- silently widen a date or Dataset selection;
- resolve an ambiguous movement by choosing the first candidate;
- write, delete, synchronize, or call the Executor.

Provider failure, timeout, invalid JSON, invalid SemanticHint, and candidate
pool violations fail closed: no final Request, no materialization, no Bundle,
and no cached-result reuse.

## Source map

### Local semantic adapter

- `fitness_ledger_core/formal_local_semantic_hint.py` — narrow, versioned Hint
  contract and validation.
- `fitness_ledger_core/formal_local_semantic_provider.py` — optional llama.cpp
  CLI transport. Runtime/model files stay outside Git.
- `fitness_ledger_core/formal_analysis_request_adapter.py` — deterministic
  mapping from bounded Hint/parser output to complete Request v1.1.
- `fitness_ledger_core/formal_analysis_request_preview_service.py` — preview
  composition and fail-closed status handling.
- `fitness_ledger_core/formal_semantic_hint_prompt.txt` — provider prompt
  boundary; do not tune it against one sentence.

### Web integration

- `web_desktop/backend/analysis_export_protocol.py` — Web-facing validation,
  preview, resolution, export, and artifact composition.
- `web_desktop/backend/server.py` — route wiring.
- `web_desktop/frontend/app.js` — UI request/preview/confirmation behavior.
- `web_desktop/frontend/styles.css` — presentation only.

The relevant API route family is:

- `/api/analysis-export/v1/validate`
- `/api/analysis-export/v1/preview`
- `/api/analysis-export/v1/resolve`
- `/api/analysis-export/v1/export`
- `/api/analysis-export/v1/natural-language/preview`
- `/api/analysis-export/v1/artifact/<id>`

### Tests

- `tools/formal_local_semantic_hint_adapter_test.py`
- `tools/formal_local_semantic_hint_web_test.py`
- `tools/formal_natural_language_runtime_test.py`
- `tools/analysis_export_protocol_web_test.py`
- `tools/analysis_export_request_protocol_test.py`
- `tools/analysis_export_materializer_test.py`
- `tools/analysis_preview_service_test.py`
- `tools/analysis_preview_review_ui_test.py`
- `tools/intent_executor_safety_test.py`

Anonymous fixtures are under:
`tools/fixtures/analysis_export_anonymous/`.

## Current known gaps

These are validation/maintenance gaps, not permission to weaken the formal
boundaries:

1. A formal read-only runtime test has not been run in the current audit because
   the test requires an explicitly supplied `FITNESS_LEDGER_FORMAL_DIR`. Do not
   guess this path or silently fall back to production data. Run it only in a
   separately approved read-only environment and compare Tracker and movement
   dictionary fingerprints before and after.
2. Local `main` and `origin/main` must be compared before any remote release
   statement. A local clean Worktree does not prove that the remote contains the
   same UI or adapter code.
3. An older independent WebUI Worktree may contain uncommitted changes. Do not
   copy or merge its working tree contents. Use the clean `main` snapshot or a
   reviewed Commit only.
4. The repository contains historical Shadow Planner, evidence, and local-model
   experiment assets alongside the formal adapter. Those files are evaluation
   assets unless this document or a newer reviewed document explicitly marks
   them as product-authoritative. Do not revive the legacy planner route.
5. Some historical evidence documents retain pre-Web wording and one older
   document has encoding damage. Use this file as the current status authority;
   repair historical documents only in a separately scoped documentation
   cleanup.

## Algorithm optimization protocol

The next model work is an internal algorithm experiment, not a protocol or UI
rewrite.

### Baseline first

Freeze the current code and run the anonymous adapter/Web matrix before changing
the provider. Record:

- Hint schema validity;
- correct bounded-intent classification;
- Request v1.1 validation rate;
- correct `ready`, `needs_confirmation`, `unsupported`, and `planner_required`
  rate;
- movement ambiguity rejection rate;
- provider call count;
- p50/p95 latency;
- Executor calls and formal writes, both required to be zero in Preview.

### Classify before changing

Every failure must be assigned to one of:

- deterministic input boundary;
- Hint classification;
- grounding/candidate-pool violation;
- adapter mapping;
- formal Validator;
- date or movement resolution;
- provider unavailable/timeout;
- Web serialization or UI state.

Do not fix a model failure by modifying Schema, Validator, Materializer, or
Executor semantics. Do not add a rule for a single sentence. Use a fixed
anonymous set with a holdout set, and make one controlled change per Commit.

### Safe optimization order

1. Improve deterministic routing and abstention where the intent is already
   unambiguous.
2. Measure the narrow SemanticHint provider with fixed decoding and timeout
   settings.
3. Only if the failure is proven to be provider interpretation, evaluate a
   prompt/provider change against the full anonymous set and holdout.
4. Keep complex questions on the GPT JSON Planner path until the local provider
   can express them without widening data scope.
5. Re-run the same safety matrix before considering any Web or formal-data
   change.

The success condition is not merely more `ready` responses. It requires no
unsafe acceptance, no unknown candidate, no silent scope expansion, and no
abnormal latency increase.

## Required handoff rules for a new conversation

1. Start from the current `main` Commit after checking `git status`, `main`, and
   `origin/main`.
2. Read this file, then
   `docs/experiments/ANALYSIS_EXPORT_PROTOCOL_STATUS.md`,
   `docs/experiments/FORMAL_LOCAL_SEMANTIC_HINT_ADAPTER.md`, and the relevant
   source/test files.
3. Do not modify AnalysisExportRequest v1.1 in place.
4. Do not call Ollama, read formal data, read Raw, call Executor, or create a
   Bundle during a Preview/model experiment.
5. Keep model/runtime files, traces containing sensitive content, and formal
   export artifacts outside Git.
6. Use a new branch and Worktree for any algorithm change. Do not work in an
   older dirty WebUI Worktree.
7. End every experiment with a reproducible report, exact Commit, test matrix,
   failure classification, latency, and explicit safety results.

## Current decision

`DETERMINISTIC_ROUTING_AND_DIRECT_DOWNLOAD_REVIEW_PENDING`

The next responsible action is a fixed anonymous baseline and failure
classification for the local semantic adapter. It is not a new Schema, a new
DSL, a Web redesign, or a direct local-model-to-Executor integration.
