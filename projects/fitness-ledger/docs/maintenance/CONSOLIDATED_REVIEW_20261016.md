# Display, export and Web fluidity consolidation

Status: source-only review candidate, 2026-10-16. No main merge, remote Push,
formal publication, provider operation, or protected-data edit was performed.

## Source and participating work

Baseline: local main `064548c4c1c31681f695e8ede02f1fba13d3d66c`.
Observed origin/main: `aff9b6e36acfa617b020d1b830e4eeb2eaaaf219`;
local main was three commits ahead. No remote refresh or Push claim is made.

Candidate branch: `codex/consolidate-display-export-fluidity`, in
`D:/FitnessLedger/worktrees/consolidate-display-export-fluidity`.

The three original Worktrees were clean at inspection and remain intact:

| Branch | Reviewed tip | Included behavior |
| --- | --- | --- |
| codex/training-display-consistency | 5f873a8 | Complete archives, Web/PWA exact session display, custom theme labels, progress exclusions, raw-only movements and decimal set lines |
| codex/export-conversation-upgrade | 4190a74 | Goal-oriented external-chat initialization, current capability contract, staged comparison guidance, unsupported-field rejection and conversational export |
| codex/web-fluidity-review | fc7624f | Deferred offscreen layout, movement-name indexing, reduced pointer layout work, nonblocking auxiliary hydration, pet texture/load and idle-render fixes |

All eleven unique commits were replayed onto current main. Conflicts in
`app.js` retained the complete archive instead of restoring the fluidity
branch's old 20-record cutoff. The optimized layout/observer code remains.
The combined Web modules have a new entrypoint cache version. PWA resource
versions remain the coherent group supplied by the display branch.

The full-history browser regression now scrolls to deferred cards before
checking rendered text, verifying actual reachability beyond the old limits.
The anonymous review fixture includes a diet record so cross-route pet
verification can exercise both Training and Diet.

## Verification on the combined candidate

Passed:

- `analysis_llm_prompt_test.py`
- `restricted_export_integration_test.py`
- `export_conversation_semantic_test.py`
- `analysis_export_request_protocol_test.py`
- `analysis_export_materializer_test.py`
- `analysis_export_protocol_web_test.py`
- `pwa_static_test.py` and `pwa_production_bundle_test.py`
- `training_display_cloud_test.js` and `training_raw_movement_test.js`
- `web_fluidity_test.mjs` and `web_fluidity_overlay_test.py`
- `training_display_browser_test.py`: Web bilingual labels and exclusions,
  PWA same-day exact sessions and back navigation.
- `web_complete_history_test.py`: 250 records per archive, oldest record
  reachable, sorting/search and complete HTTP reads.
- `export_conversation_browser_test.py`: guidance, confirmation and actual
  downloaded artifact; anonymous ledger hashes unchanged.
- `analysis_llm_intent_eval.py` replay of the retained v4 model responses:
  five bundles, one valid movement-resolution case without export, and two
  clarifications. This is historical response replay, not a new model trial.
- `web_pet_loading_browser_test.py`: deliberately slow model loading does
  not gate the page; textures render, idle/unchanged poses stop drawing,
  navigation precedes the next pose, one visible model, and neutral pose wakes.
  Anonymous training page was ready in about 407 ms in this run; this is not
  a formal-runtime performance benchmark.
- Changed Python/JavaScript syntax, UTF-8/no-BOM/replacement-character checks,
  and `git diff --check`.

Two older broader suites fail on both unchanged main and the candidate:
`archive_navigation_test.py` bans all localStorage despite existing language
and effect preferences; `web_session_effects_test.py` requires a hard-coded
September script version. Their failures are baseline test debt, not passing
coverage or newly introduced regressions. They were not weakened or rewritten.

Local pet artifacts and replay evidence:
`D:/FitnessLedger/task_outputs/consolidated-20261016/`.
No installed-phone, live CDN, CloudBase upload, or formal-runtime acceptance
claim is made by these anonymous local checks.

## Formal state and publication boundary

At inspection, the formal service at port 8766 was unavailable. Formal build
metadata identified display review deployment `155d928`, with
`review_deployment: true` and `push_verified: false`; metadata alone does not
describe all installed file contents. Some display files match the candidate,
but installed files also contain other differences.

In particular, installed `fitness_ledger_core/data_module_engine.py` contains
an extra Chinese negation fallback for text modules, absent from current main
and all three selected branches. No matching commit was found by the focused
all-ref search. Preserve this installed-only behavior pending provenance
review; do not deploy the source tree wholesale. The installed export schema
also predates fields already supported by source main. Other documentation
and tooling differences exist and are outside this consolidation.

Any later formal publication must use an explicitly reviewed file manifest,
preserve installed-only work, restart affected loaded Python services, and
verify the actual target, PWA resources/cache and affected contracts. This
candidate is ready for review; it is not a formal release or final seal.
