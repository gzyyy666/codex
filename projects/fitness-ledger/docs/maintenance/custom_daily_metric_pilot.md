# Custom Daily Metric Core + Web Pilot (Reviewed / Paused)

This is a reviewed but unreleased local Core + Web experiment. It is paused pending a future product and UI decision. It must not be treated as a mainline feature, copied into the formal business directory, or continued from an old Worktree without an explicit restart review.

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

`LedgerViewModels` provides daily-entry, daily-archive, history, placement, and `custom_metrics_export` projections. Corrupt definitions are isolated to that metric; native body/diet/training projections continue to load. Analysis Export includes definition metadata, placements, and date/value rows. The final Web experiment does not add a Cloud Sync collection or uploader behavior; Cloud Payload and remote sync remain outside this pilot.

Data Check reports malformed IDs/definitions/values, orphan values and placements, unknown placement locations/modes, archived input placements, and abnormal ordering. It never deletes or repairs data. Cloud Payload and remote sync remain outside this local pilot.

## Validated boundary

- Core and Web use one generic definition/value/placement pipeline; a second numeric metric does not require a new route or metric-specific business branch.
- Daily Entry uses the existing Parse & Review → Confirm & Save flow. Native records and custom metric changes are committed as one atomic tracker transaction, including deletion and `NO_CHANGES` behavior.
- The Web layer is a thin adapter over Core Commands and ViewModels. It does not own metric validation, status transitions, JSON writes, checkpoints, Undo, trend calculations, or placement rules.
- Automatic Review and anonymous-fixture Web Review covered two metrics, history, archive, trend, placements, status transitions, Analysis Export, Data Check, and failure/rollback behavior.

## Explicitly out of scope

The experiment does not include a formal Cloud Sync manifest or upload change, CloudBase collections, Mini Program display, automatic sync, formal-directory deployment, or formal data migration. UI and product details remain unfinished.

## Recovery pointers

- Core branch: `feat/custom-daily-metric-core` at `5d91ccac20aeff30b081a282c1d0ea01aef39a7c`.
- Web experiment branch: `feat/custom-daily-metric-web`, whose functional candidate parent is `4d1f170a633a71a18740b1b362d37cbd9e5f36e9`.
- The final recovery Commit is the tip of this branch after this documentation-only correction; resolve it with `git rev-parse feat/custom-daily-metric-web`.
- Recovery Tag: `custom-daily-metric-pilot-reviewed-paused`.
- Core test: `tools/custom_daily_metric_core_test.py`.
- Web test: `tools/custom_daily_metric_web_test.py`.

Future restart must begin from the then-current `main`: read the experiment index, this note, the Tag, the complete Diff, and the tests; produce a compatibility/migration list; and migrate only still-valid underlying logic into a new Worktree. Do not resume the old Worktree or merge the old experiment branch wholesale. New input syntax, UI, and product decisions require a new user request.
