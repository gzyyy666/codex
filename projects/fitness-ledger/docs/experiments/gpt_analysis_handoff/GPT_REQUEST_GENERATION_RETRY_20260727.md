# GPT Request Generation Retry Record

Status:

- `GPT_REQUEST_GENERATION_RETRY_ACCEPTED`
- `REQUEST_V1_1_VALIDATOR_ACCEPTED`
- `PREVIEW_ACCEPTED`
- `FORMAL_EXPORT_NOT_YET_EXECUTED`
- `MINIMAL_GPT_END_TO_END_NOT_YET_COMPLETE`

## Evidence

Case: `case-01-fat-loss-training-retention`

External evidence directory:

`C:\Users\26087\Documents\fitness-ledger-e2e-reviews\analysis-export-minimal-gpt-e2e-review\case-01-fat-loss-training-retention`

- First GPT output: `gpt_raw_response.txt`
- Corrected GPT output: `gpt_raw_response_retry_01.txt`
- Validation record: `extracted_instruction.json`
- Validated Request: `normalized_request_v1_1.json`
- Preview: `preview.json`
- Case evidence: `case_evidence.json`

The first complete-looking Request contained `body`, `diet`, and `training`
Datasets, but omitted `filters` on all three. The local Validator returned the
following six errors, two for each Dataset:

```text
MISSING_REQUIRED_PROPERTY at datasets[0].filters: Missing required property: filters
INVALID_TYPE at datasets[0].filters: Expected a filters object
MISSING_REQUIRED_PROPERTY at datasets[1].filters: Missing required property: filters
INVALID_TYPE at datasets[1].filters: Expected a filters object
MISSING_REQUIRED_PROPERTY at datasets[2].filters: Missing required property: filters
INVALID_TYPE at datasets[2].filters: Expected a filters object
```

The feedback to GPT required a complete regenerated Request and explicitly
stated that every Dataset must include `"filters": {}` when no filter applies.
GPT returned `gpt_raw_response_retry_01.txt` with all three empty filter
objects. The corrected Request passed the v1.1 Validator directly, without
local field completion. Its deterministic normalization reported no changes,
and the Preview reported zero errors with unchanged Dataset scope, fields,
Notes, time ranges, movement scope, and output formats.

This is classified as:

`GPT_MACHINE_INSTRUCTION_SCHEMA_OMISSION`

It is a GPT output-instruction omission, not a Schema, Validator, Materializer,
or Bundle semantic defect. The current direct-v1.1 path is retained; no DSL,
RequestDraft, or Compiler is introduced for this single corrected case.

## Required GPT behavior

Every Dataset must contain `dataset_id`, `type`, `time_range`, `filters`, and
`fields`. A Dataset with no filtering capability must still contain
`"filters": {}`. GPT must output the complete Request rather than a diff or a
partial patch. All committed examples are checked against the v1.1 Validator.
