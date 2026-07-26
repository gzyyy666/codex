# Fitness Ledger Data Capabilities v1.1

Protocol version: `Analysis Export Request v1.1`

This document describes the data contract available to a future GPT client. It
contains no records and does not authorize Raw access, writes, model calls, or
professional conclusions. GPT generates `AnalysisExportRequest v1.1`; Fitness
Ledger validates it and shows a Preview before any later deterministic export.

## Dataset contract

Every Dataset has a unique stable `dataset_id`. A later Dataset may refer to a
training Dataset by that ID only for the event-before window described below.

| Type | Fields | Filters | Notes scope |
|---|---|---|---|
| `body` | `date`, `weight_kg`, `bowel_movement`, `training_label`, `cardio_summary` | none | `daily` |
| `diet` | `date`, `calories_kcal`, `protein_g`, `carbs_g`, `fat_g`, `food_summary` | none | `diet` |
| `training` | `date`, `split`, `standardized_summary` | `body_part`, `split` | `training` |
| `movement_progress` | `date`, `movement_id`, `movement_name`, `body_part`, `variant`, `order`, `sets` | `movement_selector` | `movement` |

`movement_selector` is one object with exactly one semantic kind:

```json
{"kind": "movement_id", "value": "PRESS_BENCH_01"}
{"kind": "movement_name", "value": "卧推"}
{"kind": "body_part", "value": "chest"}
```

The old combination of separate `movement_id`, `movement_name`, and
`body_part` properties is not part of v1.1. GPT must not invent an ID. A name
or body-part selector may still require deterministic resolution before export.

`movement_progress` may optionally include `set_roles`, using only `top`,
`working`, and `backoff`. The roles describe which registered set groups to
select; they do not create a metric or a conclusion.

## Time modes

| Mode | Allowed Dataset types | Required properties |
|---|---|---|
| `recent_days` | all four | `days` |
| `explicit_range` | all four | ISO `start`, `end` |
| `latest_matching_sessions` | `training`, `movement_progress` only | `sessions` |
| `days_before_target_session` | `diet` only | `days_before`, `match_mode`, `include_target_session_day`, and exactly one target |

For `days_before_target_session`, exactly one of these targets is required:

- `target_dataset_id`: references a Dataset whose type is `training`;
- `target_date`: an explicit ISO date.

`match_mode` is either `single_latest_matching_session` or
`each_matching_session`. The latter is available only with
`target_dataset_id`. `include_target_session_day` is always required and is
normally `false` for a strict preceding-day window. This is the only Dataset
relationship supported in v1.1.

## Notes

Notes scope is expressed once, on the Dataset, with `notes_scope`. There is no
top-level `notes_scope` and no `include_notes` flag in v1.1. Omit
`notes_scope` to explicitly request no Notes. If present, it must match the
Dataset type (`daily`, `diet`, `training`, or `movement`).

## Raw and missing data

`raw` is fixed to `false`. A request containing `raw: true` fails closed with
`RAW_PERMISSION_REQUIRED`; no Raw data is read and no Executor is called.

Missing fields remain missing. They are not converted to zero, interpolated,
or treated as evidence that an event did not happen. Later Bundle output must
report `missing_information`, `warnings`, and its `quality_profile`.

## GPT generation rules

1. Give every Dataset a unique stable `dataset_id`.
2. Select only fields listed for that Dataset type.
3. Use one supported `time_range` per Dataset.
4. Use `target_dataset_id` only when the target is a declared training Dataset.
5. Use one `movement_selector` kind; do not send conflicting selector fields.
6. Use `set_roles` only for movement progress and only for registered roles.
7. Put Notes scope on the Dataset; omit it to exclude Notes.
8. Always emit `raw: false` and valid `output.formats`.
9. If a movement name is ambiguous, preserve the name selector and let
   deterministic resolution request confirmation; do not guess an ID.
10. Do not generate a professional conclusion or an ExportPlan.

The normative request Schema is
`schemas/analysis_export_request_v1.schema.json`. The later package shape is
`schemas/analysis_export_bundle_v1.schema.json`. The Python Validator is a
second implementation of the same v1.1 rules and must not expand them.
