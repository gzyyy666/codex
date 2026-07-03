# Fitness Ledger Regression Checklist

Always run:

```text
python -m py_compile stable_app.pyw
python tools/regression_test.py
```

For web desktop changes, also run:

```text
python -m py_compile web_desktop/launcher.pyw web_desktop/backend/server.py
python tools/web_desktop_test.py
node --check web_desktop/frontend/app.js
```

Web write commands must be explicitly routed through `LedgerCommandService`. Tests must use temporary tracker/dictionary files and must never write to the formal database.

## Shared Web Review And Save

- Parse calls the maintained desktop parser and preserves the exact raw input.
- Review exposes editable Body, Diet, Training, movement notes, and movement decisions.
- Save rejects a changed review identity or raw input.
- Only allowed Review fields are merged; movement sets/order/raw cannot be forged through the Web payload.
- Duplicate dates return `409` until overwrite or append-training is explicitly selected.
- Saving creates paired tracker/dictionary checkpoints before writing.
- A failed write preserves or restores the original files.
- Inactive movements remain recognizable and recordable but are absent from desktop/Web Movement Progress and active mapping options.
- `python tools/web_desktop_test.py` must print `FITNESS_LEDGER_WEB_SHARED_WRITE_OK`.

## Shared Movement Dictionary

- Web can list active and inactive dictionary terms and their history counts.
- Create and edit reject blank names and aliases owned by another formal movement.
- Rename preserves the previous display name as an alias.
- Alias edits reconcile matching CUSTOM rows and previously skipped raw movements without changing raw text.
- Disable hides the movement from desktop/Web Movement Progress and mapping choices.
- An inactive movement remains recognizable and can receive newly recorded history.
- Enable restores the movement to both Movement Progress views.
- Delete requires the exact display name, removes structured history, and preserves every raw entry.
- Desktop shutdown must not overwrite newer Web changes with stale in-memory state.

## Shared Existing Record Editing

- Body editing supports Date, Weight, Bowel Movement, Training, Cardio, and Notes.
- Diet editing supports Date, Calories, Protein, Carbs, Fat, Food Summary, and Notes.
- Training editing supports Date, Split, Raw Record, Standardized Summary, and Notes.
- Numeric fields reject non-numeric values and Date requires ISO format.
- Movement history editing locates the exact row by movement ID and history ID.
- Movement history supports order, set lines, cardio values, notes, and raw movement detail.
- Every edit creates paired checkpoints and leaves raw daily entries unchanged.

## Review Popup Changes

- `Parse & review` opens `Review parsed entry`.
- `Confirm & save` is visible at the bottom of the popup.
- `Cancel` is visible at the bottom of the popup.
- Long parsed content scrolls without pushing the buttons out of view.
- `Cancel` closes the popup without saving.
- `Confirm & save` calls the existing `commit_pending` flow.
- Parser output and database structure are unchanged.
- Body fields Date, Weight, Bowel Movement, Training split, Cardio, and Notes are editable.
- Diet macros, Food Summary, and Notes are editable.
- Training Split, Standardized Summary, and Training Notes are editable.
- Raw Record remains unchanged.
- Movement rows show original name, standard name, movement ID, sets, notes, and new status.
- New movements support add, map, raw-only skip, and cancel-save decisions.
- Mapping adds the raw name as an alias of the selected existing movement.
- Review warnings report missing fields, missing sets, new movements, duplicate dates, and suspicious section pollution.
- Final summary shows date, weight, bowel, macros, training split, movement count, new count, cardio, and note presence.
- Valid field edits refresh the final summary.
- Auto-generated movement summary continues following movement edits; manually edited summary remains respected.

## Quick Entry Overview

- Startup shows the latest saved date status.
- Status reports Weight, Bowel, Macros, Food, Training, Cardio, CUSTOM movement count, and High issue count.
- Explicit `none` cardio displays as no cardio rather than missing.
- Empty cardio plus cardio keywords in raw text displays possibly missing.
- Recent records show the latest three distinct dates.
- Body, Diet, and Training shortcuts reuse existing editors.
- Missing record buttons are disabled.
- Raw input opens read-only and Undo reuses the existing restore flow.

## Duplicate Dates

- A duplicate date offers overwrite, same-day additional training, and cancel.
- Overwrite leaves one Body, one Diet, and one replacement Training record for that date.
- Overwrite removes the replaced date's movement histories before adding replacements.
- Replaced raw entries remain present and are marked `superseded`.
- Same-day additional training does not duplicate Body or Diet.
- Same-day additional training receives a new Training No. and `save_mode=append_training`.
- Cancel writes nothing.

## Undo Last Save

- Each user save creates paired tracker and movement-dictionary checkpoints.
- Undo asks for confirmation.
- Undo restores both files, refreshes all pages, and marks the consumed backups `undone` without deleting them.
- A pre-undo backup preserves the state being replaced.
- No available checkpoint produces an informative message.

## Data Check

- Page lists Severity, Date, Area, Issue, and Suggested Action.
- Checks missing Body/Diet fields, missing sets, skipped movements, duplicate dates, long polluted fields, system notes, CUSTOM count, and same-movement same-date duplicates.
- Historical missing bowel records are not reported.
- Pull-up / 引体向上 records are treated as bodyweight work and do not trigger missing-sets warnings solely because no load was parsed.
- Opening or refreshing Data Check never writes data.
- Clicking `确认并隐藏` writes only `data/data_check_state.json` and removes the selected issue from the current list.
- Clicking `恢复全部已确认` brings hidden issues back without changing `tracker.json`.
- Locatable issues show Open and can launch Body, Diet, Training, Movement, Raw, or Dictionary views.
- Issues without a reliable target remain informational and cannot auto-open anything.

## Movement Editing

- Selecting a movement row can open its dictionary editor.
- Renaming updates dictionary `display_name`, preserves the old name as an alias, and updates the matrix row.
- Conflicting names are rejected.
- Double-clicking a nonempty date cell opens the movement history editor.
- Order, sets, notes, raw detail, and cardio metrics can be edited.
- Invalid set or numeric formats do not save.
- Every edit creates a paired undo checkpoint.
- Deleting a movement requires confirmation and removes its dictionary entry, matrix row, and all structured movement history.
- Deleting a movement does not delete `raw_entries` text.
- Undo Last Save can restore a movement rename, record edit, or whole-row deletion.

## Movement Dictionary Manager

- Movement Progress has one `动作词典管理` entry instead of scattered dictionary buttons.
- The manager shows only term metadata and never displays dates, sets, weights, or history.
- Search covers standard name, English name, and aliases.
- Filters show all, active-only, or inactive-only definitions.
- Alias management can add/remove aliases but cannot remove the standard display name.
- Disable preserves history and alias recognition.
- Disabled definitions are excluded from Review's existing-movement mapping choices.
- Enable/disable, alias save, rename, and delete each create an undo checkpoint.
- Saving a new alias scans non-superseded `raw_entries.skipped_movements` and restores matching parsed sets/notes to the selected formal movement.
- Alias reconciliation preserves raw text, avoids duplicate history fingerprints, and never automatically absorbs another formal movement ID.
- Matching `CUSTOM_*` rows may be absorbed into the selected formal definition; conflicting formal aliases remain rejected.

## Quick Entry / Parser Changes

- Standard input can parse date, body weight, calories, protein, carbs, fat, and training.
- A movement name on its own line can be recognized.
- Multiple set/load lines under a movement can be recognized.
- A number on its own line followed by a movement name is recognized.
- Subsequent unnumbered movement names followed by set lines are recognized as separate movements.
- Top-level `cardio:`, `diet:`, and `notes:` sections never become strength movement candidates.
- Diet text is not treated as movement text.
- Notes text is not treated as movement text.
- Run `python tools/smoke_test.py` when parser or save behavior changes.

## New Movement Recognition Changes

- Review preview marks an undefined movement as new.
- Confirm save asks before an undefined movement enters the dictionary and Movement Matrix.
- `Yes` approves the movement, `No` keeps the raw record but skips Movement Matrix insertion, and `Cancel` aborts the save.
- Confirm save adds the new movement once.
- Later same-name entries do not duplicate the movement.
- Movement Matrix adds or reuses the correct movement row.

## Movement Notes

- An indented `notes:` line remains attached to its numbered movement.
- Review preview displays the movement note.
- Confirm save preserves the note in movement history.
- Training-day Notes aggregates movement names and their notes in movement order.
- Global notes remain Body notes and are not duplicated as movement notes.

## Body Table Changes

- Columns are `Date, Weight, Bowel Movement, Training, Cardio, Notes`.
- Existing body-fat, waist, sleep, and steps remain in JSON.
- Existing Context remains in JSON/details but is not shown in the main Body table.
- A record with neither Date nor Weight is hidden, not deleted.
- Missing optional fields do not create a garbage row or crash.
- Training column only shows the training split.
- Cardio column only shows the cardio summary.
- Notes column only shows global notes.
- Horizontal scrolling remains available.
- Long fields use compact previews.
- Double-click opens the Body record editor.

## Bowel Movement Parsing

- `排便：有` saves `Bowel Movement = 有`.
- `排便：无` saves `Bowel Movement = 无`.
- `排便：正常` saves `Bowel Movement = 正常`.
- `bowel: yes` saves `Bowel Movement = 有`.
- No bowel input leaves `Bowel Movement` blank.
- Bowel Movement does not absorb raw text.

## Recent Cardio Fix

- 2026-06-25 Body `Cardio = 跑步机爬坡`.
- 2026-06-26 Body `Cardio = 跑步机爬坡`.
- Recent Body `Notes` do not contain full training or diet sections.

## Record Editing

- Body row opens an editor.
- Diet row opens an editor.
- Training row opens an editor.
- Save edit backs up `tracker.json`.
- Save edit updates only selected record fields.
- Cancel edit does not change `tracker.json`.
- Edited data appears after refresh.
- Raw text is preserved.
- JSON remains valid.

## Diet Table Changes

- Columns are `Date, Calories, Protein, Carbs, Fat, Food Summary, Notes`.
- Food Summary and Notes use compact previews.
- Horizontal scrolling works.
- Double-click opens a scrollable full-record detail window.
- Current visible headings are Chinese: `日期, 热量, 蛋白质, 碳水, 脂肪, 饮食摘要, 备注`.
- Historical English `Food Summary` and `Notes` stay available in `Food Summary Original` and `Notes Original`.
- New Chinese diet records are not translated to English.

## Training Table Changes

- Columns are `No., Date, Split, Raw Record, Standardized Summary, Notes`.
- Raw Record, Standardized Summary, and Notes use compact previews.
- Current visible headings are Chinese: `编号, 日期, 训练部位, 原始记录, 标准化摘要, 备注`.
- Standardized Summary uses Chinese `movement_dictionary.display_name`.
- Summary format does not use `1th / 2th / 3th`.
- Raw Record keeps the original user text.
- Horizontal scrolling works.
- Double-click opens a scrollable full-record detail window.

## Movement Matrix Changes

1. X axis is dates.
2. Y axis uses `movement_dictionary.json` display names.
3. The same movement across different dates appears in the same row.
4. Cells contain a compact preview of `Day / Ex / load-reps-sets` or cardio details.
5. Horizontal and vertical scrollbars work.
6. Search filters movement rows only and preserves all date columns.
7. Date columns are ascending.
8. Missing movement/date combinations are blank.
9. Double-clicking a nonempty data cell opens the complete movement/date history.
10. Double-click detail still works after filtering with Movement Search.
11. Searching `Flat` finds `诺德士挂片推一`.

## Movement Dictionary Changes

- Every dictionary entry has a unique permanent `movement_id`.
- Every tracker movement and movement history record has a matching `movement_id`.
- UI movement names use Chinese `display_name` values.
- `诺德士平板推` and `挂片推一` both resolve to `CHEST_001`.
- `诺德士平板推` and `挂片推一` both resolve to `CHEST_001`.
- Historical names, aliases, raw detail, weights, reps, and sets remain present.
- Unknown confirmed movements receive a stable `CUSTOM_nnn` dictionary entry.

## Parser Changes

Run:

```text
python tools/smoke_test.py
```

Check body, macros, movement order, aliases, strength sets, and cardio metrics.

## Data Save Changes

- Create a database backup before save.
- `data/tracker.json` remains valid JSON.
- Existing lists and movement histories are preserved.
- Raw text is appended and never removed.
- Tests use temporary data paths.

## UI Layout Changes

- Program opens.
- All table containers use `sticky="nsew"` and expansion weights.
- Long-text tables retain horizontal scrolling.
- Detail windows remain scrollable.
