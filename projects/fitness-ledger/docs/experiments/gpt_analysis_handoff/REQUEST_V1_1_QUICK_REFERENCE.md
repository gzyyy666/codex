# AnalysisExportRequest v1.1 Quick Reference

## Top-level shape

```json
{
  "request_version": "1.1",
  "purpose": "short data purpose",
  "datasets": [],
  "raw": false,
  "output": {"formats": ["json", "markdown"]}
}
```

Every Dataset has `dataset_id`, `type`, `time_range`, `filters`, and `fields`.
`dataset_id` values are unique within one Request.

`filters` is always required. Use `"filters": {}` when the Dataset type has
no filters; never omit the property. GPT must output the complete Request, not
a diff or a partial object for local completion.

## Dataset matrix

| Type | Fields | Filters | Time modes | Notes |
|---|---|---|---|---|
| `body` | `date`, `weight_kg`, `bowel_movement`, `training_label`, `cardio_summary` | `{}` | recent / explicit | `daily` |
| `diet` | `date`, `calories_kcal`, `protein_g`, `carbs_g`, `fat_g`, `food_summary` | `{}` | recent / explicit / days before training | `diet` |
| `training` | `date`, `split`, `standardized_summary` | `body_part`, `split` | recent / explicit / latest sessions | `training` |
| `movement_progress` | `date`, `movement_id`, `movement_name`, `body_part`, `variant`, `order`, `sets` | one `movement_selector` | recent / explicit / latest sessions | `movement` |

## Selector and relationship rules

- `movement_selector`: `{ "kind": "movement_id|movement_name|body_part", "value": "..." }`.
- `movement_id` is canonical; `movement_name` is human-readable; `body_part` is an area scope.
- `set_roles` is only `top`, `working`, or `backoff`, and only on `movement_progress`.
- `days_before_target_session` is only a diet Dataset window.
- Its target is exactly one `target_dataset_id` pointing to a training Dataset or an explicit `target_date`.
- `match_mode` is `single_latest_matching_session` or `each_matching_session`.
- `each_matching_session` requires `target_dataset_id`.
- `include_target_session_day` is mandatory and explicit.
- Notes are requested once with Dataset-level `notes_scope`; omit it for no Notes.
- `raw` must always be `false`.

## Missing values

Missing fields stay missing. Do not encode missing as zero or infer an event
from an empty result. The later Bundle reports missing information, warnings,
quality, and provenance.
