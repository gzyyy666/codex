# Fitness Ledger Safe Maintenance

Use these rules only for the local Fitness Ledger desktop tool.

## Project Boundary

- Project: `C:\Users\26087\Documents\Codex\2026-06-16\vs-code-ai\work\fitness_tracker_app`
- Main program: `stable_app.pyw`
- Core database: `data/tracker.json`
- Movement dictionary: `data/movement_dictionary.json`
- Historical import: `data/history_import.json`
- Desktop launcher: `C:\Users\26087\Desktop\Fitness Ledger.lnk`

## Safety Rules

1. Never clear, rebuild, or replace `data/tracker.json`.
2. Preserve every `raw_entries[*].text` value.
3. Back up the database before saving user changes.
4. Keep JSON writes atomic through `write_json`.
5. Do not generate alternate main programs such as `stable_app_new.pyw`.
6. Do not modify the original Excel source.
7. Do not add AI analysis, cloud sync, or EXE packaging unless explicitly requested.
8. UI columns may change, but existing database fields must remain compatible.
9. Display-invalid records may be skipped in the UI but must not be deleted.
10. Before changing save, parser, or migration behavior, decide whether a manual project/database backup is needed.
11. Do not default to AI diet analysis or training advice. The tool records user-provided data unless a future task explicitly asks for analysis.
12. Do not create alternate main-program copies. Modify only `stable_app.pyw` unless the request is documentation, tests, or data dictionary maintenance.

## Current Functional Model

- Quick Entry parses body, diet, training, movements, loads, sets, reps, and cardio.
- The confirmation window supports limited field correction and movement decisions while preserving the raw input.
- Body shows primary personal tracking fields only.
- Diet and Training provide wide tables and double-click detail windows.
- Movement Progress is a date-by-movement matrix sourced from movement history.
- Movement IDs, display names, English names, aliases, and metadata come only from `movement_dictionary.json`.
- Movement Matrix and Movement Search resolve tracker records through permanent `movement_id` values.
- Movement Matrix cells can edit structured history records; dictionary controls can rename or explicitly delete a whole movement row.
- Movement Progress opens a separate term-only dictionary manager for rename, aliases, active state, and deletion; it must not display training history.
- Inactive definitions retain aliases and history and can still receive newly recognized records, but are hidden from desktop/Web Movement Progress and excluded from new-entry mapping choices.
- Desktop and Web confirmed daily saves must pass through `ledger_commands.py`; direct Web JSON writes are forbidden.
- Desktop and Web movement-dictionary mutations must pass through `ledger_commands.py`; aliases and metadata must never be written directly by a request handler.
- Web Body/Diet/Training and movement-history edits must pass through `ledger_commands.py`; request handlers may only expose the maintained desktop field sets.
- Desktop close must not rewrite stale in-memory data after Web writes.
- A confirmed whole-movement delete may remove that dictionary entry and its structured movement history, but must never delete raw daily input text.
- There is currently no Excel export feature. A future export must use dictionary `display_name` values.

## Project Goals

- Record body data.
- Record diet and user-provided macro totals.
- Preserve raw training text.
- Parse training movements and set/load details.
- Maintain Movement Matrix.
- Support future new-movement recognition and review-before-save workflows.

## Validation

Always run:

```text
python -m py_compile stable_app.pyw
python tools/regression_test.py
```

For parser or save changes, also run:

```text
python tools/smoke_test.py
```

Do not write test records into the real database.
