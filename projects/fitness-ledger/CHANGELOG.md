# Fitness Ledger Changelog

## 2026-07-03 - Shared Platform Services

- Migrated Web Undo to the shared paired tracker/dictionary checkpoint semantics with pre-undo backup and consumed-checkpoint handling.
- Replaced the hard-coded Web Data Check sample with the established desktop rules, acknowledgement filtering, and real repair navigation.
- Added one read-only view-model layer shared by Pre-Workout Reference, Movement Recent 3, Analysis Export, and cloud payload preparation.
- Added Training Pre-Workout Reference without generating plans or advice.
- Added Recent 3 movement performance with maximum load, total reps, volume, and previous-record change.
- Added local Markdown/JSON Analysis Export for 7/14/30-day or custom ranges; full raw text is excluded by default.
- Added a cloud read-replica contract, payload builder, and dry-run validator. No provider, credential, or network write is configured.
- Preserved tracker/dictionary structures, parser behavior, raw input, and local JSON as the sole source of truth.

## 2026-07-03 - Review Movement Priority

- Moved movement recognition and mapping directly below the Web Review heading.
- Reordered the Review index so movement decisions are the first inspection task.
- Added a restrained primary-review surface so new/existing/mapped movement decisions are visible before Body, Diet, and Training details.
- No parser, save behavior, or data structure changed.

## 2026-07-03 - Dictionary Functional Grid

- Reworked the Web Dictionary into a regular five-column functional grid based on the approved reference.
- Concentrated each cell on status, history count, standard/English name, muscle group, and direct actions.
- Kept aliases and extended metadata inside the editor to increase first-screen information density.
- Reused the local movement archive collage as a restrained full-page technical background.
- Added responsive four-, three-, two-, and one-column layouts without changing dictionary behavior or data.

## 2026-07-03 - Web Record Editing And Compact Dictionary

- Added shared Web editing for existing Body, Diet, and Training records using the desktop field boundaries.
- Added Web editing for structured movement-history order, sets, cardio values, notes, and raw movement detail.
- All edits use the shared write lock, paired checkpoints, validation, atomic replacement, and rollback path.
- Reworked Dictionary into a high-density index that keeps aliases and metadata inside the editor, shows more terms per screen, and places Dictionary before Data Check.
- Added compact editorial action controls and a dedicated offline background treatment without external assets.
- Expanded temporary-data integration tests. Raw daily entries and the JSON schema remain unchanged.

## 2026-07-03 - Shared Web Movement Dictionary Administration

- Added shared movement-dictionary commands for create, edit, aliases, metadata, enable/disable, and confirmed deletion.
- Added a complete Web Dictionary page with search, status filtering, history counts, an editorial editor, and destructive-action confirmation.
- Alias edits scan matching CUSTOM rows and previously skipped raw movements for safe historical reconciliation.
- Inactive movements remain recognizable and recordable while staying hidden from desktop/Web Movement Progress.
- Desktop dictionary mutations now use the same locked, paired-checkpoint command service as Web.
- Desktop close no longer rewrites stale in-memory JSON, preventing it from overwriting Web changes made while both surfaces are open.
- Expanded temporary-data integration tests; no formal database or JSON schema changes were made.

## 2026-07-02 - Shared Web Parse/Review/Save

- Added `ledger_commands.py` as the shared UI-free Parse/Review/Save command boundary.
- Connected desktop confirmed saves and Web `/api/parse` + `/api/save` to paired backups, cross-process locking, atomic JSON replacement, and rollback.
- Added the Web `Review Scroll` interface with editable structured fields, movement mapping decisions, duplicate-date modes, Chinese warnings, and a restrained archive background.
- Changed inactive movement behavior: history and alias recognition are preserved and new matching records can still be stored, while desktop/Web Movement Progress and mapping choices hide inactive definitions.
- Expanded temporary-database Web tests and desktop smoke coverage. No database structure changed.

## 2026-07-02

### Visual Bible And Cross-Surface Refinement

- Added `docs/design/STYLE_BIBLE.md` as the durable source of truth for the existing Web visual language and interaction semantics.
- Expanded Movement Detail width and chart prominence while increasing trajectory information density.
- Fixed Data Check so only the visible Open control launches Chinese issue details, and widened its final table column to prevent clipping.
- Added stable body-area classes and a dedicated high-contrast leg archive treatment using the existing leg-training illustration.
- Updated the Web desktop shortcut to use the same monogram icon as the stable local desktop application.
- Removed forced Tk scaling, made the Quick Entry body responsive, and routed mouse-wheel input to scrollable desktop widgets under the pointer.
- No parser, database structure, or save behavior changed.

### Movement Alias Historical Reconciliation

- Fixed Review's English `Map to existing movement` action so it is applied instead of silently falling back to the current match.
- Saving an action alias now scans active historical raw entries for matching skipped movements and restores their sets and movement notes into the selected formal history.
- Matching CUSTOM rows can be merged into the formal movement while conflicting formal IDs remain protected.
- Added `器械下拉` to `诺德士高拉` and restored its 2026-07-02 sets.
- Added `诺德士拨片拉背` to `诺德士拉背拨片` and restored its 2026-07-02 sets and note.
- Raw daily input and the JSON data structure remain unchanged.

## 2026-07-01

### Browser-grade Desktop Foundation

- Added `web_desktop/` as a parallel browser-grade UI shell without replacing `stable_app.pyw`.
- Added a dependency-free local HTTP API that reuses `mobile_viewer/data_access.py` and reads the existing JSON files.
- Added responsive Quick Entry, Body, Diet, Training, Movement, Data Check, search, recent-record, and detail surfaces.
- Added Edge app-mode launcher and the separate desktop shortcut `Fitness Ledger Web Preview.lnk`.
- Kept all web write endpoints disabled until they can route through the existing review, backup, undo, and atomic-save behavior.
- Added `tools/web_desktop_test.py` for API, UTF-8 JSON, static frontend, and write-boundary verification.
- The stable desktop application and all data structures remain unchanged.

### Premium Lifestyle UI Refactor

- Reworked the complete desktop presentation layer around a cinematic monochrome fitness-journal Hero, warm editorial surfaces, restrained Volt accents, and clearer elevation.
- Preserved the existing sidebar, Quick Entry, status, recent records, Body, Diet, Training, Movement Progress, Data Check, Review, edit, and detail functionality.
- Added stable selected navigation and low-key hover feedback without changing commands or workflows.
- Added a generated FL desktop icon and updated the existing desktop shortcut to use it.
- Added high-DPI layout calibration so the full three-column Quick Entry screen and primary CTA remain visible when maximized.
- No parser, save flow, database structure, tracker content, or movement logic was changed.

## 2026-06-30

### Nike-Inspired Product UI Layer

- Added a final presentation-only UI layer with a high-contrast graphite, white, and Volt visual system.
- Rebuilt the sidebar, active navigation state, page headers, and Quick Entry composition around stronger typography and negative space.
- Removed routine surface borders so Body, Diet, Training, Movement Progress, Data Check, Review, detail, and edit views use tone and spacing for hierarchy.
- Unified primary, secondary, navigation, danger, input, text-area, status, and badge treatments across the desktop tool.
- Corrected the Review window layout so the editable content owns the expandable scroll region.
- No parser, save flow, database structure, tracker data, or movement logic was changed.

### Desktop UI Visual System Upgrade

- Replaced the previous mixed card/table desktop presentation with a unified warm editorial UI layer inside `stable_app.pyw`.
- Reworked Quick Entry, Body, Diet, Training, Movement Progress, Data Check, Review, detail windows, and record editors to share one visual language.
- Body, Diet, and Training now render as flowing stacked surfaces instead of the old visible grid-first layout.
- Movement Progress now presents history as a timeline-style flow while preserving the hidden matrix compatibility layer for existing tools/tests.
- Data Check now renders as issue threads with direct actions while preserving the same underlying rule logic and acknowledged-hide behavior.
- No parser, save flow, database structure, or movement logic was changed.

### Mobile Viewer

- Added a separate read-only mobile viewer under `mobile_viewer/`.
- Introduced a dedicated data access layer for `tracker.json` and `movement_dictionary.json`.
- Added Flask HTML pages for Home, Today, Search, Movement Progress, and Record Detail.
- Added JSON endpoints for today summary, training-by-date, search, and movement history.
- Search supports Chinese names, English names, aliases, date text, split keywords, and diet keywords.
- Movement history now falls back to parsing raw legacy text when older records do not have structured `sets`, so pull-up and similar history pages still show usable set summaries.
- Desktop parser, review, save flow, and existing database structure were not changed.

### Data Check Acknowledge And Hide

- Added per-issue `确认并隐藏` behavior on the Data Check page.
- Hidden issues are stored outside `tracker.json` in `data/data_check_state.json`.
- Added `恢复全部已确认` to restore hidden issues.
- Quick Entry latest-day High issue counts now ignore already acknowledged Data Check items.
- Added regression coverage for acknowledge/hide and restore flows.

## 2026-06-29

### Daily Review And Quick Entry Workflow

- Added a compact Review final summary for date, Body, macros, training, movement counts, cardio, and notes.
- Final summary follows valid Review edits while preserving deliberate manual summary changes.
- Added latest-day completeness status to Quick Entry using existing structured fields and Data Check rules.
- Added shortcut cards for the latest three saved dates with Body, Diet, Training, raw input, and Undo actions.
- Added Data Check `Open` targeting for Body, Diet, Training, Movement cells, raw input, and the dictionary manager.
- Data Check remains rule-based and read-only; unlocatable issues stay informational.
- No parser, raw-text, or database-schema changes were made.
- Charts, dashboards, AI analysis, and training-plan features remain intentionally deferred.

### Dedicated Movement Dictionary Manager

- Replaced scattered Movement Progress dictionary controls with one `动作词典管理` entry.
- Added a term-only list with active state, Chinese/English names, muscle group, category, equipment, alias count, and movement ID.
- Added search plus active/inactive filters.
- Added focused alias add/remove management.
- Added safe enable/disable without deleting history or breaking historical alias recognition.
- Disabled definitions no longer appear as Review mapping candidates.
- Rename and delete remain available inside the manager; no training dates, weights, sets, or history are shown there.

### Leg Movement Duplicate Merge

- Consolidated duplicate tracker rows into one `LEG_001 / 腿屈伸` row and one `LEG_002 / 腿弯举` row.
- Removed redundant dictionary entries `CUSTOM_003` and `CUSTOM_004`; their aliases remain on the canonical definitions.
- Corrected 2026-06-25 to 腿屈伸 `100 × 12 × 3` and 腿弯举 `90 × 12 × 3`.
- Preserved the pre-correction movement text in `raw_original` and preserved all daily raw entries.
- Created paired tracker/dictionary backups before migration.

### Pull-up Data Check Exception

- Treats `BACK_001`, `引体向上`, and `Pull-up` as bodyweight work.
- Pull-up history no longer triggers a missing-sets warning merely because no external load was parsed.
- Other movement quality checks are unchanged.

### Movement Dictionary And Matrix Editing

User-facing changes:

- Removed historical missing-bowel warnings from Data Check; new-entry Review warnings remain.
- Added `编辑动作词典` and `删除整个动作` controls to Movement Progress.
- Dictionary editing supports Chinese name, English name, aliases, muscle group, category, equipment, and notes.
- Double-clicking a nonempty matrix cell now opens an editor for movement order, sets, notes, raw detail, and cardio metrics.
- Whole-movement deletion removes the dictionary entry, complete matrix row, and structured history after confirmation.

Data safety:

- Rename, record edit, and delete operations require paired undo checkpoints.
- Old display names are preserved as aliases during rename.
- Whole-movement deletion preserves every raw daily input record and can be restored with Undo Last Save.
- No database migration or automatic deletion was performed.

Tests:

- Verified missing-bowel issues no longer appear in Data Check.
- Verified movement history editing, dictionary rename, complete row deletion, raw preservation, compilation, regression, and temporary-file smoke tests.

### Review Editing, Duplicate Dates, Undo, And Data Check

Changed files:

- `stable_app.pyw`
- `tools/regression_test.py`
- `tools/smoke_test.py`
- `FUNCTION_INDEX.md`
- `PROJECT_BOOTSTRAP.md`
- `REGRESSION_CHECKLIST.md`
- `CHANGELOG.md`

User-facing changes:

- Review is now an editable Body/Diet/Training/Movements form with a warning panel.
- New movements can be added, mapped to an existing movement, skipped, or used to cancel the save.
- Duplicate dates offer overwrite, same-day additional training, or cancel.
- Quick Entry includes `Undo Last Save` backed by paired tracker/dictionary checkpoints.
- Added a read-only Data Check page with rule-based quality warnings.

Data behavior:

- Overwrite keeps all raw text and marks replaced raw entries `superseded`.
- Same-day additional training does not duplicate Body or Diet records.
- Skipped movement names may be recorded on the raw entry for later checking.
- Optional compatible metadata includes `save_mode`, `superseded`, and `skipped_movements`.

Deliberately deferred:

- Charts, dashboards, reports, AI analysis, training plans, cloud sync, accounts, and mobile features.

Tests:

- Review editing and warnings use live UI widgets against an in-memory database.
- Save, overwrite, same-day append, undo, and movement mapping use temporary JSON files.
- Python compilation, regression, and smoke tests passed.

### Training Boundary And Unnumbered Movement Parsing Fix

Changed files:

- `stable_app.pyw`
- `tools/regression_test.py`
- `FUNCTION_INDEX.md`
- `REGRESSION_CHECKLIST.md`
- `CHANGELOG.md`

Parser changes:

- Training text now ends at the next top-level Cardio, Diet, or Notes section.
- A number-only line such as `1.` can provide the order for the following movement name.
- Known or set-backed unnumbered movement names now start separate movement records.
- The `cardio:` section label can no longer fall through as an unknown movement named `有氧`.

Data structure impact:

- None.

Data writes:

- None. Existing `tracker.json` and movement dictionary records were not changed.

Tests:

- Added the reported 2026-06-29 input shape as a parser regression case.
- Python compilation, full regression, and save smoke tests passed.

## 2026-06-27

### Movement Notes, Chinese Records, And New-Movement Approval

Changed files:

- `stable_app.pyw`
- `data/tracker.json`
- `data/movement_dictionary.json`
- `tools/training_notes_zh_migration.py`
- `tools/regression_test.py`
- `tools/smoke_test.py`
- Project maintenance indexes and checklists

Behavior changes:

- Movement-level notes are now aggregated into the training-day Notes field while remaining in movement history.
- Unknown movements are marked in Review and require Yes/No/Cancel approval before Movement Matrix insertion.
- Rejecting a movement preserves the raw training record without registering that movement.

Data maintenance:

- Converted historical structured Body and Training display fields to Chinese.
- Preserved original English values in compatible `Original` fields and preserved every raw record.
- Recovered movement notes for 2026-06-25 through 2026-06-27 where the raw/history data allowed it.
- Normalized known tracker movement names to dictionary Chinese display names while preserving old names as aliases.

Data structure impact:

- No breaking schema change; optional `Original` fields were added only where a translated source value needed preservation.

Tests:

- Python compilation passed.
- Full regression and save smoke tests passed.
- Startup smoke test passed.

## 2026-06-26

### Body Bowel Field, Cardio Repair, And Record Editing

Changed files:

- `stable_app.pyw`
- `data/tracker.json`
- `tools/body_bowel_cardio_migration.py`
- `tools/regression_test.py`
- `PROJECT_BOOTSTRAP.md`
- `PROJECT_INDEX.md`
- `FUNCTION_INDEX.md`
- `REGRESSION_CHECKLIST.md`
- `CHANGELOG.md`

Parser changes:

- Added explicit bowel-movement extraction for labels such as `排便`, `bowel`, and `bowel movement`.
- Added top-level section extraction so indented movement `notes:` are not treated as global Body notes.
- Body records now save Training split, Cardio summary, Bowel Movement, and clean global Notes.

UI changes:

- Body Records now display Date, Weight, Bowel Movement, Training, Cardio, and Notes.
- Context is preserved in stored records but no longer shown as a main table column.
- Double-click Body, Diet, and Training rows now opens a small editable record window with Edit, Save, and Cancel controls.

Data cleanup:

- Backed up `tracker.json` before migration.
- Fixed 2026-06-25 and 2026-06-26 Body Cardio to `跑步机爬坡`.
- Cleaned polluted Body/Diet/Training display fields while preserving `raw_entries[*].text`.

Data structure impact:

- Compatible additive field: `Bowel Movement` may be present in Body records.
- No database restructure.

Tests:

- `python -m py_compile stable_app.pyw`
- `python tools/regression_test.py`
- `python tools/smoke_test.py`

### Training Table Raw Record Display Simplification

Changed files:

- `stable_app.pyw`
- `tools/regression_test.py`
- `CHANGELOG.md`

UI changes:

- Removed `Raw Record` from the Training table surface.
- Added a small `查看原始记录` button on the Training page.
- Kept raw records available through the new button and the existing double-click detail window.
- Adjusted Training table column widths for a cleaner table view.

Data structure impact:

- None.

Tests:

- `python -m py_compile stable_app.pyw`
- `python tools/regression_test.py`
- `python tools/smoke_test.py`

### Chinese Display And Historical Diet Main-View Migration

Changed files:

- `stable_app.pyw`
- `data/movement_dictionary.json`
- `data/tracker.json`
- `tools/zh_display_migration.py`
- `tools/regression_test.py`
- `FUNCTION_INDEX.md`
- `PROJECT_BOOTSTRAP.md`
- `REGRESSION_CHECKLIST.md`
- `CHANGELOG.md`

Data changes:

- Backed up `tracker.json` and `movement_dictionary.json` before migration.
- Kept movement IDs stable.
- Strengthened dictionary Chinese `display_name` values and aliases for known Chinese inputs.
- Converted 10 historical Diet records to Chinese main display.
- Preserved English Diet originals in `Food Summary Original` and `Notes Original`.
- Rebuilt historical Training `Standardized Summary` values from movement history using Chinese movement names.
- Moved generated `New movements: ...` text from Training `Notes` to `System Notes Original` when present.

UI changes:

- Body, Diet, Training, and Movement Matrix headings now use Chinese labels.
- Training table and detail display use `movement_id -> movement_dictionary.display_name`.
- Record detail labels are localized for common Body, Diet, and Training fields.

Parser/save changes:

- Added support for Chinese `体重`, `训练`, `饮食`, and `备注` labels.
- New saved training summaries use `第N个动作：中文动作名`.
- `Raw Record` and raw entry text remain unchanged.

Data structure impact:

- Compatible additive fields only: `Food Summary Original`, `Notes Original`, and `System Notes Original`.

Tests:

- `python -m py_compile stable_app.pyw`
- `python tools/regression_test.py`
- `python tools/smoke_test.py`

### Multi-line Movement Set Parsing And Body Review Narrowing

Changed files:

- `stable_app.pyw`
- `tools/smoke_test.py`
- `FUNCTION_INDEX.md`
- `CHANGELOG.md`

Parser changes:

- Added structured parsing for numbered movement headers such as `1. Movement name`.
- Attached following non-numbered set lines to the current movement.
- Supported `x`, `×`, `*`, and hyphen-style load formats.
- Kept indented `notes:` under the current movement instead of treating it as a global note.
- Tightened movement-number detection so `17.5kg` is not mistaken for movement number `17`.

Review changes:

- Review popup Body section now shows only weight and notes/context.
- Body fat, waist, and sleep are no longer actively displayed in the Review popup.

Data structure impact:

- None.

Data writes:

- None during this maintenance change.

Tests:

- `python -m py_compile stable_app.pyw`
- `python tools/regression_test.py`
- `python tools/smoke_test.py`
- Direct parser checks for multi-line set blocks and `×` multiplication signs.

### Review Popup Button Layout Fix And Maintenance Index Update

Changed files:

- `stable_app.pyw`
- `FITNESS_LEDGER_MAINTENANCE.md`
- `PROJECT_BOOTSTRAP.md`
- `FUNCTION_INDEX.md`
- `REGRESSION_CHECKLIST.md`
- `CHANGELOG.md`

UI changes:

- Fixed `Review parsed entry` so `Confirm & save` and `Cancel` stay in a bottom button area.
- Made the parsed preview area vertically scrollable, so long content cannot push the buttons out of view.

Maintenance changes:

- Added review-popup routing to the project bootstrap.
- Added future-task routing for new movement recognition, new movement review, input auto-recording, table display, and Movement Matrix work.
- Added review-popup and parser/new-movement minimum regression checklists.

Data structure impact:

- None.

Parser impact:

- None.

Data writes:

- None during this maintenance change.

Tests:

- `python -m py_compile stable_app.pyw`
- `python tools/regression_test.py`
- `python tools/smoke_test.py`

## 2026-06-25

### Movement Dictionary v1.0 Migration

Changed files:

- `stable_app.pyw`
- `data/movement_dictionary.json`
- `data/tracker.json`
- Project indexes and regression tests

Migration:

- Added permanent `movement_id` values to 28 existing movement objects and all 46 history records.
- Preserved all existing movement keys, names, aliases, raw history, weights, reps, and sets.
- Added 29 dictionary definitions, including one compatibility entry for `Rear-delt Y Raise (Aux)`.

Runtime changes:

- Parser recognition, confirmed saves, Movement Matrix display, and Movement Search now use the movement dictionary.
- Matrix movement names are dictionary `display_name` values.
- Search includes `display_name`, `english_name`, and aliases.

Data structure impact:

- Compatible additive change: `movement_id` was added to movement objects and history records.

### Compact Table Previews And Full Detail Windows

Changed files:

- `stable_app.pyw`
- `FUNCTION_INDEX.md`
- `REGRESSION_CHECKLIST.md`
- `CHANGELOG.md`
- `tools/regression_test.py`

UI changes:

- Added compact previews for long Body, Diet, Training, and Movement Matrix values.
- Added full-record double-click details to Body.
- Added per-cell double-click details to Movement Matrix.
- Reduced oversized long-text columns while preserving horizontal scrolling.

Data structure impact:

- None.

Data writes:

- None during this maintenance change.

### Foundation Correction And Maintenance System

Changed files:

- `stable_app.pyw`
- `FITNESS_LEDGER_MAINTENANCE.md`
- `PROJECT_BOOTSTRAP.md`
- `PROJECT_INDEX.md`
- `FUNCTION_INDEX.md`
- `REGRESSION_CHECKLIST.md`
- `CHANGELOG.md`
- `tools/regression_test.py`

UI changes:

- Simplified Body to Date, Weight, Context, Training, Cardio, and Notes.
- Added horizontal scrolling to Body, Diet, and Training.
- Reordered and widened Diet and Training long-text columns.
- Added double-click Diet and Training detail windows.
- Replaced movement summary with a movement-by-date matrix.

Data structure impact:

- None.

Data deletion:

- None. Invalid body records are skipped only during display.

Tests:

- Python compilation.
- UI structure and database-hash preservation.
- Strength and cardio matrix formatting.
- Full targeted regression test.

Remaining limitations:

- The Quick Entry confirmation window is still read-only.
- Movement Matrix cells do not yet have a double-click detail view.
- The app does not write changes back to the original Excel workbook.

## 2026-07-02 - Review Mapping Action Fix

Modified files:

- `stable_app.pyw`
- `tools/smoke_test.py`

Changes:

- Added the active English Review action labels to `apply_review_edits` action-code mapping.
- Fixed `Map to existing movement` silently falling back to `use` instead of applying the selected target movement ID.
- Added an end-to-end smoke test that selects the English mapping action through the Review widgets and verifies target movement history and alias updates.

Data structure impact: None.

User data modified: No. Tests use temporary tracker and dictionary files.
