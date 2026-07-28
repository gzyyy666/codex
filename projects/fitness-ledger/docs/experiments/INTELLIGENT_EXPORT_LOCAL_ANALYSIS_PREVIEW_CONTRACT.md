# Intelligent Export Local Analysis Preview Contract

Milestone route: `Request Gate → legal Analysis Planner → Requirement Mapping → Core Resolution → validated Preview`.

The implementation is a local, read-only service contract. It does not call
`ExportExecutor`, write tracker data, modify the Web server, or grant Raw
permission.

## Model boundary

`RequestGate` calls the existing `DataCatalogBuilder` and
`IntentCompiler.prepare()`. Only `ANALYSIS_REQUEST` reaches the Planner.
Delete/write/sync/planning requests, Raw requests, incomplete dates, and
ambiguous movements become explicit non-model statuses first.

The Planner reuses the existing two-stage Shadow Planner contract and the
versioned `CapabilityRegistryV2` model metadata. The Gate's deterministic
dimensions form a controlled Registry subset for that request. This prevents
optional-capability drift without changing the prompt, schema, Gold labels, or
the deterministic Core.

The model may emit only `AnalysisRequirementSpecV1`. It cannot emit formal
field IDs, record IDs, dates, Notes scope, Raw permission, an ExportPlan, an
output format, or a write/delete/sync action. The model-visible context omits
raw text/date keys and formal data content.

## Service input

```json
{
  "request": "分析最近饮食和训练",
  "budget_mode": "standard",
  "confirmations": {
    "notes_scope": "training"
  }
}
```

`confirmations` is optional. Notes scope is never inferred from the model;
the supplied scope must be one of the deterministic scopes recognized for the
request. Raw confirmation is not grantable by this service.

## Service output

Every response contains:

```json
{
  "schema_version": "fitness-ledger-analysis-preview-service-v1",
  "status": "ready",
  "trace_id": "preview:<stable-hash>",
  "gate": {},
  "planner": {},
  "validation": {},
  "resolution": {},
  "mapping_preview": {},
  "gpt_analysis_package_preview": {},
  "review": {
    "required": true,
    "editable_fields": ["questions_to_answer", "optional_capabilities", "preferred_time_window"]
  },
  "execution": {"allowed": false, "mode": "preview_only", "executor_called": false},
  "trace": {}
}
```

The stable statuses are:

- `ready`: a deterministic plan and GPT package preview passed validation;
- `clarification_required`: target/date/Notes confirmation is insufficient;
- `movement_resolution_required`: the existing resolver needs a user choice;
- `raw_permission_required`: Raw is outside the model and package contract;
- `unsupported_operation`: write/delete/sync/planning request;
- `model_unavailable`: the local transport is unavailable;
- `planner_invalid`: model output fails schema or deterministic scope checks;
- `mapping_unavailable`: Registry/Core mapping or plan validation failed.

## Deterministic ownership

`DataCatalogBuilder`, `IntentCompiler`, `DateRangeResolver`,
`MovementResolver`, `CandidateSummarizer`, and `ExportPlanValidator` retain
ownership of data availability, concrete dates, movement resolution, formal
IDs, fields, records, and the final plan. `GPTAnalysisPackage.build()` is
used only after mapping and confirmation checks. No executor is present in
this service.
