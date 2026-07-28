# Formal Local SemanticHint Adapter

## Status

- **Status:** Integration candidate / stop before Web / not released
- **Base:** `414b28cbf6785e8607cbdbde76df8e9012e0e168`
- **Branch:** `feat/formal-local-semantic-hint-adapter`
- **Formal protocol:** Analysis Export Request v1.1 remains authoritative and unchanged.
- **Lab source:** design was selectively reimplemented; the frozen Lab branch was not
  merged or cherry-picked.

## Boundary

The candidate ends at a validated, read-only Request preview:

```text
user text
  -> deterministic parser and capability boundary
  -> optional narrow SemanticHint
  -> deterministic Request v1.1 assembly
  -> formal validate_request()
  -> Preview DTO
```

It does not import a Web route or frontend, read formal data, construct a Bundle,
materialize an export, invoke an Executor, write files, or grant Raw. The Preview
DTO always reports execution as disallowed and `raw_allowed=false`.

`FormalAnalysisRequestPreviewService.from_runtime_config(path)` is the intended
future backend composition point. A Web route may call only `preview(user_text)`.
It must not chain the returned Request into materialization or execution without
the existing explicit preview/confirmation/authorized execution flow.

## Routing

- Clear bounded requests use deterministic parsing and skip the Provider.
- A narrow multi-Dataset field-selection ambiguity uses `SemanticHint`.
- Open-ended analysis questions route to the existing GPT JSON Planner contract.
- Missing date, Notes scope, or other required information returns
  `needs_confirmation`.
- Raw, writes, deletion, synchronization, and training-plan generation return
  `unsupported`.

The two planning paths must converge on the same formal Request v1.1 schema and
Validator. Neither path controls the formal data source or Executor.

## SemanticHint authority

The model receives only:

- the user text;
- a request-scoped canonical requested-information candidate;
- evidence strings already present in the user text;
- allowed and protected dimensions.

It may map broad comparison language to the sealed
`cross_dataset_analysis` candidate or report ambiguity. The deterministic
assembler then expands that candidate into the formal per-Dataset field profiles.
It cannot decide or modify dataset identity, dataset ID, time range, filters,
Notes scope, status, Raw, output format, execution, movement identity, or formal
dates. The strict validator rejects unknown dimensions, values outside the pool,
ungrounded evidence, duplicate fields/candidates, invalid confidence, and missing
required dimensions. Invalid or unavailable model output produces no Request.

## Runtime candidate

The example configuration keeps all machine-specific values external:

- Qwen2.5 0.5B Instruct Q4_K_M GGUF
- llama.cpp CLI, CUDA, GPU layers `99`
- threads `4`, threads_batch `2`
- context `4096`, n_predict `640`
- temperature `0`, top_k `1`
- timeout `60s`

The runtime, model, grammar tool, cache, temporary grammar, and model output stay
outside Git on the isolated D-drive runtime directory. Temporary schema and
grammar files are removed after success or failure. No Ollama endpoint is used.

## Failure behavior

- Invalid external configuration: deterministic requests still work; the narrow
  model route falls back to confirmation/GPT Planner with no Request.
- Process start failure, timeout, nonzero exit, empty/non-JSON output, or invalid
  Hint: no final Request, no formal Validator success, no compile/materialization,
  and no cached prior result.
- Formal Request validation failure: no ready Request.

## Verified pre-Web acceptance

- Deterministic, date/range, latest sessions, relative pre-session diet,
  movement-name/body-part, Notes, capability, and dual-route contracts.
- Provider configuration, CUDA/CPU consistency, Windows paths with spaces,
  timeout, temporary-file cleanup, strict JSON, evidence, and candidate sealing.
- A real 0.5B CUDA smoke for `分析最近一个月训练和饮食` returned a legal Hint,
  the exact `cross_dataset_analysis` candidate, a valid formal Request, and
  `ready` in 3.90 seconds.
- Existing formal protocol, materialization, export, preview, compiler, and safety
  regressions remain the release gate.

## Remaining Web step

The next change should be a separate reviewed commit that:

1. injects `FormalAnalysisRequestPreviewService` into the backend;
2. adds one preview-only route and DTO serialization;
3. renders ready/confirmation/unsupported/planner-required states in Web UI;
4. keeps Preview unable to reach materialization or Executor;
5. adds route-level tests proving Executor and formal writes remain zero.

Do not expose local filesystem paths or Provider stderr/stdout in Web responses.
Do not treat this candidate or the independent Lab Gold score as formal product
acceptance.

## Formal read-only runtime configuration

The Web runtime connects the accepted formal read-only source only when one of
these explicit configurations is present before process startup:

- `FITNESS_LEDGER_FORMAL_DIR`, pointing to the formal application directory or
  directly to its `data` directory; or
- both `FITNESS_LEDGER_FORMAL_TRACKER_PATH` and
  `FITNESS_LEDGER_FORMAL_MOVEMENT_DICTIONARY_PATH`.

Missing, incomplete, or invalid configuration remains fail-closed and is exposed
through `/api/capabilities` as `analysis_export_formal_source=false` plus a
non-sensitive status. Environment changes require a server restart because the
semantic Preview service and formal read-only snapshot are assembled once at
process startup.
