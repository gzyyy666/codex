# Analysis Export Request Protocol v1.1 Closure

## Changes from v1

- Added required unique `dataset_id` to every Dataset.
- Added `target_dataset_id` or explicit `target_date` for event-before diet
  windows, plus `match_mode` and `include_target_session_day`.
- Restricted `latest_matching_sessions` to `training` and `movement_progress`.
- Replaced separate movement filters with one `movement_selector` object.
- Added optional movement `set_roles`: `top`, `working`, `backoff`.
- Replaced top-level `notes_scope` plus Dataset `include_notes` with one
  Dataset-level `notes_scope` property.
- Converted Dataset fields and filters to typed, dataset-specific Schema
  definitions.
- Kept Raw fixed to `false`; no model, data, Executor, or materialization path
  was added.

## Deliberately not added

- Task, Metric, or Claim Registry;
- professional analysis semantics;
- general query language;
- relation types other than event-before diet-to-training;
- local model or Ollama integration;
- formal data access or anonymous materialization.
