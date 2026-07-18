# Experiments Index

## Custom Daily Metric Pilot

- **Status:** Reviewed / Paused / Not released
- **Goal:** Validate whether a generic Core + Web pipeline can support arbitrary daily single-value numeric metrics without metric-specific business code.

### Verified

- Generic metric definitions, values, placements, and active/inactive/archived states.
- A second metric reuses the same Core, Daily Entry, archive, history, and trend pipeline.
- Daily Entry uses one Parse & Review -> Confirm & Save flow.
- Native records and multiple metric changes are committed atomically, including deletion and `NO_CHANGES` behavior.
- Archive, History, Trend, Analysis Export, and Data Check projections.
- Basic Core / Web responsibility separation and anonymous-fixture failure/rollback coverage.

### Not released

- Pilot feature code is not in `main`.
- Nothing was written back to the formal business directory or formal data.
- No formal Cloud Sync collection, CloudBase upload, automatic sync, or Mini Program display was added.
- UI and product details remain unfinished.

### Recovery pointers

- Final experiment branch: `feat/custom-daily-metric-web`.
- Final experiment Commit: `46b7f485e0e401ab47e7b436eae900819fd6c854`.
- Core ancestor Commit: `5d91ccac20aeff30b081a282c1d0ea01aef39a7c`.
- Reviewed paused Tag: `custom-daily-metric-pilot-reviewed-paused` (peeled Commit `46b7f485e0e401ab47e7b436eae900819fd6c854`).
- Technical note: `docs/maintenance/custom_daily_metric_pilot.md` on the experiment branch.
- Tests: `tools/custom_daily_metric_core_test.py` and `tools/custom_daily_metric_web_test.py` on the experiment branch.

### Recovery rules

1. Do not continue, merge, copy, or depend on this paused experiment without an explicit user request to resume it.
2. Start every future formal task from the then-current `main`, not from the old experiment Worktree.
3. When resumed, read this index, the Tag, the complete experiment Diff, the technical note, and the tests.
4. Produce a compatibility and migration list against that current `main` before changing code.
5. Migrate only still-valid underlying logic into a new Worktree; do not merge the old experiment branch wholesale.
6. Wait for a new user request before making product, input, or UI decisions.
