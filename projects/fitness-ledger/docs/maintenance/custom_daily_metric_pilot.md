# Custom Daily Metric Core Pilot (Phase 1)

The pilot is an independent tracker extension. It does not create movements, movement history, growth rows, or dictionary entries.

## Storage

`tracker.json` may contain three optional object maps:

- `custom_metric_definitions[metric_id]`: `metric_id`, `label`, `unit`, `number_format` (`integer` or `decimal`), `decimal_places`, `status` (`active`, `inactive`, `archived`), and non-negative `order`.
- `custom_metric_values[metric_id][YYYY-MM-DD]`: one finite numeric value per metric/date.
- `custom_metric_placements[placement_id]`: `metric_id`, `page`, `slot`, `mode` (`input`, `latest_value`, `frequency`, `trend_30d`), `order`, and `enabled`.

IDs are stable and lowercase (`[a-z][a-z0-9_]*`). Definitions, values, and placements are independent: removing a placement does not remove history, and renaming a label never changes the ID.

## Commands

`LedgerCommandService` exposes `create_custom_metric`, `update_custom_metric`, `set_custom_metric_status`, `set_daily_custom_metric_value`, `remove_daily_custom_metric_value`, `upsert_custom_metric_placement`, and `remove_custom_metric_placement`. They use the normal write lock, paired checkpoint/Undo, atomic tracker write, post-write validation, and rollback. The movement dictionary is not rewritten. Equivalent business content returns `NO_CHANGES` before checkpoint creation.

Active metrics accept new values. Inactive metrics retain readable history but reject new dates. Archived metrics are read-only. Blank, boolean, non-finite, non-numeric, fractional-integer, or over-precision values are rejected.

## Read-only projections

`LedgerViewModels` provides daily-entry, daily-archive, history, placement, and `custom_metrics_export` projections. Corrupt definitions are isolated to that metric; native body/diet/training projections continue to load. Analysis Export includes definition metadata, placements, and date/value rows. The local Cloud Payload dry-run exposes the generic `fl_custom_metrics` collection without changing uploader semantics.

Data Check reports malformed IDs/definitions/values, orphan values and placements, unknown placement locations/modes, archived input placements, and abnormal ordering. It never deletes or repairs data. Cloud Payload and remote sync remain outside this local pilot.
