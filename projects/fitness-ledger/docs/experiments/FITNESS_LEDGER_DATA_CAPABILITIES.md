# Fitness Ledger Data Capabilities

Protocol version: `Analysis Export Request v1`

This document describes the data contract available to a future GPT client. It
does not contain records and does not authorize a model to read Raw input,
write data, or decide a professional conclusion. The GPT client turns a
user's analysis purpose into a JSON `AnalysisExportRequest`; Fitness Ledger
validates that JSON and shows a Preview before any later deterministic export.

## Available datasets

| Request type | Data role | Requestable fields |
|---|---|---|
| `body` | Daily body-state history | `date`, `weight_kg`, `bowel_movement`, `training_label`, `cardio_summary` |
| `diet` | Daily diet and macro history | `date`, `calories_kcal`, `protein_g`, `carbs_g`, `fat_g`, `food_summary` |
| `training` | Training-session context | `date`, `split`, `standardized_summary` |
| `movement_progress` | Already-resolved movement history | `date`, `movement_id`, `movement_name`, `body_part`, `variant`, `order`, `sets` |

`date` is the record date. `movement_progress` is the only dataset intended
for set-level movement history. A `training` request must not be treated as a
replacement for movement-level load/repetition records.

The current data source also has a Raw-entry module, but Raw is not a
requestable dataset in v1. It is intentionally absent from the dataset enum.

## Time modes

Every dataset must provide exactly one `time_range` object:

| Mode | Meaning | Required properties |
|---|---|---|
| `recent_days` | The latest available calendar window | `days` |
| `explicit_range` | A user-specified calendar interval | ISO `start`, ISO `end` |
| `latest_matching_sessions` | The latest matching training sessions | `sessions` |
| `days_before_target_session` | Days preceding a later target session | `days_before` |

The protocol does not resolve dates or choose a target session. It records the
request. Later deterministic Core code resolves the interval and reports an
empty intersection or missing target rather than silently widening the range.

## Filters

The closed filter vocabulary is:

- `body_part`: a body-part scope;
- `movement_name`: a human-readable movement reference;
- `movement_id`: an already-known canonical movement identifier;
- `split`: a training split.

Unknown filters fail validation. A `movement_name` is not an identity grant:
the later deterministic Movement Resolver must resolve it. If more than one
candidate remains, the Preview must request movement confirmation. GPT must
not invent a `movement_id`.

## Notes

`notes_scope` may contain `daily`, `diet`, `training`, or `movement`. A dataset
must also set `include_notes: true` before the scope can be used. Notes are
scoped evidence, not a general-purpose text search. The request validator
does not expand a Notes scope automatically.

## Raw and safety

`raw` is fixed to `false` in v1. There is no GPT-controlled Raw permission
field. A request containing `raw: true` fails closed with
`RAW_PERMISSION_REQUIRED`; no Raw data is read and no Executor is called.

The request protocol is read-only. It cannot request writes, deletes, sync,
training plans, diet plans, or professional recommendations. It only names
data required for a later analysis.

## Missing data and nulls

The future Bundle reports `missing_information`, `warnings`, and a
`quality_profile`. Missing fields remain missing. They must not be converted
to zero, interpolated, or treated as evidence that an event did not happen.
An empty intersection, unresolved movement, unavailable field, or insufficient
record count must remain explicit in Preview or Bundle output.

## How GPT should generate a request

1. Restate the user's purpose in `purpose` without adding a recommendation.
2. Select only the dataset types needed to answer that purpose.
3. Select explicit fields from the tables above; do not invent fields or IDs.
4. Choose one high-level time mode per dataset.
5. Add only filters stated by the user or already supplied as canonical IDs.
6. Request Notes only with an explicit scope and `include_notes: true`.
7. Always emit `raw: false` and `output.formats`.
8. If the purpose is not answerable as a data request, ask for clarification
   instead of expanding the schema or guessing.

The canonical JSON Schema is
`schemas/analysis_export_request_v1.schema.json`. The later package shape is
`schemas/analysis_export_bundle_v1.schema.json`.
