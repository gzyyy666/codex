# Codex Task: Anonymous Deterministic Materialization

Copy this entire document into a new Codex conversation. It is the complete
initial task prompt for the next implementation stage.

You are responsible for the next Fitness Ledger stage: `Anonymous
Deterministic Materialization`.

## Exact baseline and workspace

- Git Worktree root: `C:\Users\26087\Documents\github-memory-worktrees\fl-analysis-export-anonymous-materialization`
- New branch: `feat/analysis-export-anonymous-materialization`
- Exact baseline Commit: `91edfba775feb9e46f479e6a7aafa7bc187cd6ef`
- Current protocol branch (reference only): `feat/analysis-export-request-mvp`
- Current protocol Worktree (read-only reference only): `C:\Users\26087\Documents\github-memory-worktrees\fl-intelligent-export-local-analysis-pipeline`
- Accepted protocol Commit: `0af0914f001c01d8f1e1dc1931e685a4591fb04c`
- Protocol freeze/GPT handoff Commit: `91edfba775feb9e46f479e6a7aafa7bc187cd6ef`
- `main`: `0a189162d42cb2b95903d64e9a1d614df00cfe16`
- `origin/main`: `0a189162d42cb2b95903d64e9a1d614df00cfe16`
- GPT handoff: `projects/fitness-ledger/docs/experiments/FITNESS_LEDGER_GPT_ANALYSIS_HANDOFF.md`
- Protocol status: `projects/fitness-ledger/docs/experiments/ANALYSIS_EXPORT_PROTOCOL_STATUS.md`

Before creating or changing anything, verify the live branch, HEAD, status,
main/origin/main, all Worktrees, the requested branch/path, and the project
authority documents. Do not reset, clean, overwrite, or copy uncommitted files.
The requested branch and Worktree were unoccupied at the time this prompt was
generated; recheck them now.

## Single objective

Implement and review this deterministic, anonymous pipeline only:

```text
legal AnalysisExportRequest v1.1
    -> deterministic anonymous-fixture resolution
    -> AnalysisExportBundle
    -> JSON and Markdown export
```

The v1.1 Request Schema and Validator are frozen. Do not modify their semantics
or silently add compatibility fields. The existing Validator remains the
authority; every Request must pass it before materialization.

## Allowed scope

Implement only the minimum deterministic materialization needed to:

- select anonymous `body`, `diet`, `training`, and `movement_progress` Datasets;
- resolve `recent_days`, `explicit_range`, `latest_matching_sessions`, and the diet-only `days_before_target_session` relation;
- resolve Dataset references, target training Datasets, and target dates from fixture metadata;
- resolve movement selectors using fixture-only deterministic data;
- apply `top`, `working`, and `backoff` set roles;
- apply Dataset-level Notes scopes;
- preserve missing values as missing and report them explicitly;
- generate Bundle `manifest`, selected Datasets, records, field definitions, quality profile, missing information, warnings, provenance, and safety flags;
- export the Bundle to JSON and Markdown without changing the source fixture.

Use the existing v1.1 schemas and request validator. Reuse existing safe,
read-only concepts only when they directly serve this pipeline. Keep the
Materializer version explicit in the Bundle and keep Request Schema version
explicit.

## Strict prohibitions

Do not:

- modify v1.1 Schema, Validator, protocol semantics, or accepted protocol files;
- call GPT, qwen, another local model, or Ollama;
- read `tracker.json`, `movement_dictionary.json`, Raw records, or any formal data;
- call Executor or create an ExportPlan;
- write, delete, synchronize, or modify Fitness Ledger business data;
- connect Web UI, Cloud, Mini Program, or a provider;
- restore Legacy Planner, Shadow Planner, Task Registry, Metric Registry, or Claim Registry;
- invent professional analysis conclusions;
- use real personal data in fixtures, snapshots, outputs, or ZIP evidence;
- create a second branch or Worktree;
- Merge, Push, Tag, or write back the formal directory.

## Anonymous fixtures

Create small committed fixtures under the task project only. Fixtures must be
synthetic and visibly anonymous, with no real Notes, personal dates, movement
dictionary text, or copied formal records. Include enough deterministic data to
cover:

1. body recent-days weight trend;
2. diet recent-days macros;
3. latest three chest training sessions;
4. known movement selector and movement progress;
5. diet three days before each matching training session;
6. target-date diet window with explicit include/exclude target day;
7. top/working/backoff set roles;
8. body + diet + training combination with Dataset-level Notes;
9. missing field and empty intersection behavior;
10. illegal Raw and unsupported-operation requests rejected before materialization.

Do not use a fixture to relax or reinterpret the frozen Validator.

## Required outputs

Produce an internal, deterministic Bundle contract and a local Review package
containing:

- per-case candidate/validated/materialized/exported counts;
- anonymous input Request;
- standardized Request;
- Bundle JSON;
- Markdown export;
- missing-information and warnings evidence;
- provenance and safety flags;
- case matrix and gap report;
- hashes for package artifacts, excluding any self-referential manifest hash;
- explicit proof that formal data, Raw, model, Ollama, and Executor were not accessed.

## Tests and checks

Run the existing v1.1 protocol and safety tests without changing their cases,
then add only materializer-specific anonymous tests:

- every committed Request fixture passes the frozen Validator;
- Dataset type/field/time/filter/Notes boundaries remain fail-closed;
- all four time modes and the event-before relation resolve deterministically;
- movement selector and set-role results are deterministic;
- missing values are not converted to zero;
- empty selection is explicit;
- Bundle Schema fields and version metadata are present;
- JSON and Markdown exports are reproducible;
- formal data/Raw/Executor/model access is absent;
- Python compile and `git diff --check` pass.

Do not run model benchmarks, Web tests, full historical acceptance suites, or
formal-data tests in this task.

## Review and stopping point

The task is complete only after:

- the anonymous materialization tests pass;
- the Review package is generated outside the repository or in an explicitly safe evidence location;
- no formal data or runtime state was modified;
- the Worktree is clean;
- one local Candidate Commit is created;
- the full Commit SHA and Review package path are reported.

Stop immediately after that Commit and wait for human Review. Do not create the
formal read-only validation Worktree or start Web UI in this task.

## Final response format

Report only:

1. branch, Worktree, baseline, and full Commit;
2. modified files and anonymous fixture count;
3. Bundle/JSON/Markdown materialization results;
4. test results;
5. data/model/Raw/Executor/Web safety confirmation;
6. Review package path;
7. whether the next gate is `anonymous_materialization_review`;
8. stop status.
