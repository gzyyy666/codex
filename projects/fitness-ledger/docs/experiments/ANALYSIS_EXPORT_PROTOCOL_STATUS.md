# Analysis Export Request Protocol Status

Status: `ACCEPTED / FROZEN`

## Accepted baseline

- Protocol: `AnalysisExportRequest`
- Version: `1.1`
- Accepted Commit: `0af0914f001c01d8f1e1dc1931e685a4591fb04c`
- Branch: `feat/analysis-export-request-mvp`
- Worktree: `C:\Users\26087\Documents\github-memory-worktrees\fl-intelligent-export-local-analysis-pipeline`
- Review: `40 PASS`, `0 FAIL`, `0 PARTIAL`, `0 NOT_EXPRESSIBLE`, `0 AMBIGUOUS`
- Closure regressions: `7 PASS`
- P0 / P1 / P2: `0 / 0 / 0`
- Decision: `REQUEST_PROTOCOL_ACCEPTED`
- Review evidence: `EVIDENCE_CLOSURE_ACCEPTED`
- Review ZIP: `C:\Users\26087\Documents\github-memory\analysis-export-request-protocol-review\v1.1-review-closure-20260727T091847\ANALYSIS_EXPORT_REQUEST_PROTOCOL_REVIEW_RESULTS_V1_1.zip`

No formal tracker, movement dictionary, Raw record, model, Ollama, or
Executor was used to establish this protocol status.

## Request capabilities

The request can select these Dataset types:

| Dataset | Fields | Filters / selector | Notes scope |
|---|---|---|---|
| `body` | `date`, `weight_kg`, `bowel_movement`, `training_label`, `cardio_summary` | none | `daily` |
| `diet` | `date`, `calories_kcal`, `protein_g`, `carbs_g`, `fat_g`, `food_summary` | none | `diet` |
| `training` | `date`, `split`, `standardized_summary` | `body_part`, `split` | `training` |
| `movement_progress` | `date`, `movement_id`, `movement_name`, `body_part`, `variant`, `order`, `sets` | one `movement_selector` | `movement` |

Every Dataset has a unique `dataset_id`. The only supported Dataset relation is
a diet `days_before_target_session` window referencing a declared training
Dataset through `target_dataset_id`.

## Time and relationship contract

- `recent_days`: calendar window of the requested number of days; all Dataset types.
- `explicit_range`: inclusive ISO `start` and `end`; all Dataset types.
- `latest_matching_sessions`: latest matching sessions; only `training` and `movement_progress`.
- `days_before_target_session`: only `diet`; requires `days_before`, `match_mode`, `include_target_session_day`, and exactly one of `target_dataset_id` or `target_date`.
- `match_mode`: `single_latest_matching_session` or `each_matching_session`.
- `each_matching_session` requires `target_dataset_id` and applies the window to every matching training session.
- `include_target_session_day` explicitly controls whether the target training day is included.
- `target_date` is an explicit ISO date and is not a Dataset reference.

## Movement, Notes, output, and safety

- `movement_selector` is one object with `kind` `movement_id`, `movement_name`, or `body_part` and one `value`.
- `movement_id` is a canonical identifier supplied by an existing trusted source; GPT must not invent one.
- `movement_name` is a human-readable selector and may require deterministic resolution or confirmation.
- `body_part` is an area scope; it is not a specific movement identity.
- `set_roles` is optional and only supports `top`, `working`, and `backoff`.
- Notes are requested only by Dataset-level `notes_scope`; there is no top-level `notes_scope` or `include_notes`.
- Output formats are `json` and `markdown`.
- `raw` is fixed to `false`; Raw is not a requestable Dataset or permission.
- Missing fields remain missing. They must not be converted to zero or silently inferred.

## Authority relationship

`schemas/analysis_export_request_v1.schema.json` is the normative structural
Schema. `fitness_ledger_core/analysis_export_request.py` is the deterministic
second validator and must implement the same v1.1 policy, including the
cross-Dataset uniqueness and target-type checks. Neither GPT nor a local model
may bypass the Validator or turn a Request directly into an ExportPlan.

The later `AnalysisExportBundle` must record the Request Schema version. A
future Materializer must record its own implementation version.

## Version discipline

1. v1.1 semantics must not be changed in place.
2. New backward-compatible fields require a minor-version increment.
3. Removing, renaming, or changing field semantics requires a major-version increment.
4. Existing v1.1 Requests must remain identifiable and interpretable.
5. Every later Bundle records the Request Schema version.
6. Every later Materializer records its own version.
7. A local model `RequestDraft` is not a formal `AnalysisExportRequest`.
8. Local model output must pass the same Validator.
9. Do not create a formal Release Tag before release approval.
10. Later experiments must not silently overwrite v1.1 files.

## Known non-blocking boundaries

- This document defines a data request, not professional metrics, claims, recommendations, or an ExportPlan.
- The protocol does not resolve a movement name to a real movement ID; deterministic resolution remains a later step.
- The protocol does not read records or materialize a Bundle.
- Web UI and local model integration are downstream gates, not part of the frozen protocol.

## Next stage

`Anonymous Deterministic Materialization`: validate a legal v1.1 Request,
resolve it against anonymous fixtures, produce an `AnalysisExportBundle`, and
export JSON/Markdown without touching formal data or calling a model.
