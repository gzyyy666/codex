# Fitness Ledger Project Bootstrap

Use this file to restore project context with low token cost.

## Current Files

- Working project: `%USERPROFILE%\Documents\Codex\2026-06-16\vs-code-ai\work\fitness_tracker_app`
- Main program: `stable_app.pyw`
- Core database: `data/tracker.json`
- Movement dictionary: `data/movement_dictionary.json`
- Historical import: `data/history_import.json`
- Desktop launcher: `%USERPROFILE%\Desktop\Fitness Ledger.lnk`
- Web launcher: `%USERPROFILE%\Desktop\Fitness Ledger Web.lnk`
- Web desktop foundation: `web_desktop/`
- Web architecture: `web_desktop/ARCHITECTURE.md`
- Original workbook: `%USERPROFILE%\Desktop\fitness_tracker_clean_en.xlsx`
- Maintenance rules: `FITNESS_LEDGER_MAINTENANCE.md`
- Function map: `FUNCTION_INDEX.md`
- Regression guide: `REGRESSION_CHECKLIST.md`
- Product-function review brief: `FUNCTIONAL_REVIEW_BRIEF.md`
- External design reference: `DESIGN.md` (Nike analysis from VoltAgent/awesome-design-md, MIT licensed)
- Project-specific visual authority: `docs/design/STYLE_BIBLE.md`

## Core Pages

- Quick Entry
- Body
- Diet
- Training
- Movement Progress
- Data Check

## Web Desktop Boundary

- `stable_app.pyw` remains the maintained desktop UI and parser implementation.
- `ledger_commands.py` is the shared UI-free Parse/Review/Save command service used by desktop and Web.
- `web_desktop/backend/server.py` exposes local Parse and confirmed Save commands and reuses `mobile_viewer/data_access.py` for reads.
- `web_desktop/frontend/` is the browser-grade visual layer.
- Web visual rules live in `docs/design/STYLE_BIBLE.md`; current Training uses a three-layer material scene with five body-area controls directly on the Training Records first screen.
- Body-area controls set an in-page `selectedBodyPart` state on `#training`. They filter and theme the existing record page without opening a separate route or writing classification results to JSON.
- Web daily Review/Save and Movement Dictionary administration use the shared command service.
- Web Body/Diet/Training and movement-history editing use the shared command service.
- Web Undo and Data Check writes remain deferred.
- Never bypass the shared cross-process lock, paired checkpoint, atomic-write, and rollback workflow.

## Default Workflow

1. Read `FITNESS_LEDGER_MAINTENANCE.md`.
2. Read `PROJECT_BOOTSTRAP.md`.
3. Read `FUNCTION_INDEX.md`.
4. Before visual design work, read `docs/design/STYLE_BIBLE.md` and then use root `DESIGN.md` as a secondary Nike interaction and composition reference.
5. Preserve the established Fitness Ledger identity when the generic Nike reference conflicts with the project-specific Style Bible.
6. Read only the functions relevant to the request.
7. Do not scan the full `stable_app.pyw` by default.
8. Do not scan the full project by default.
9. Select the minimum tests from `REGRESSION_CHECKLIST.md`.
10. Record durable changes in `CHANGELOG.md`.

## Shared Platform Services (2026-07-03)

- `ledger_commands.py` is the only shared write boundary for desktop and Web. Web Undo must call `LedgerCommandService.undo_last_write`; do not recreate restore logic in JavaScript.
- `fitness_ledger_core/shared_view_models.py` is the read-only projection layer for Pre-Workout Reference, movement insight, Analysis Export, and cloud payloads.
- `fitness_ledger_core/data_quality_view.py` exposes the desktop Data Check rules to Web and preserves `data/data_check_state.json` acknowledgement semantics.
- `cloud_sync/` prepares a disposable read-only replica only. Local JSON remains the sole source of truth; no provider or network uploader is configured.
- Generated `cloud_sync/out/*.json` files contain personal data and must remain untracked.

## Request Routing

- Review popup missing buttons: `parse_and_review`, `open_review_window`, `commit_pending`.
- Review editing/warnings: `open_review_window`, `apply_review_edits`, `collect_review_warnings`, `confirm_review`.
- Review final summary: `format_review_summary`, `refresh_review_summary`, `apply_review_edits`.
- Duplicate date handling: `records_on_date`, `choose_duplicate_action`, `remove_records_for_overwrite`, `commit_pending`.
- Undo Last Save: `create_undo_checkpoint`, `undo_last_save`, `write_json`.
- Data Check: `build_data_check_page`, `collect_data_issues`, `refresh_data_check`, `acknowledge_selected_data_issue`, `reset_acknowledged_data_issues`.
- Quick Entry latest status/recent records: `refresh_quick_overview`, `latest_day_status`, `recent_record_dates`, `open_record_from_overview`.
- Data Check Open navigation: `open_selected_data_issue`, `open_record_from_overview`, `open_raw_record_detail`, `open_movement_history_editor`.
- Data Check acknowledge/hide state: `DATA_CHECK_STATE_FILE`, `load_data_check_state`, `data_check_issue_key`, `visible_data_issues`.
- New movement recognition/review: `parse_entry`, `format_review_lines`, `review_new_movements`, `resolve_movement`, `add_custom_movement_definition`, `commit_pending`, `refresh_movements`.
- Training movement notes: `parse_training_movements`, `format_review_lines`, `commit_pending`, `standardized_summary_for_day`, `refresh_training`.
- Input format parsing: `build_quick_entry`, `parse_and_review`, `parse_entry`, `extract_load_blocks`, `extract_cardio_metrics`.
- Table display too long: `make_cell_preview`, `build_table_with_scrollbars`, `refresh_body`, `refresh_diet`, `refresh_training`, `refresh_movements`, `open_detail_window`.
- Movement matrix: `build_movement_page`, `get_movement_matrix_dates`, `format_matrix_cell`, `refresh_movements`, `open_movement_cell_detail`.
- Automatic input recording: `parse_and_review`, `open_review_window`, `commit_pending`, `backup_data`, `write_json`.
- Body table: `build_body_page`, `refresh_body`, `extract_bowel_movement`, `extract_labeled_section`.
- Diet table/detail: `build_diet_page`, `refresh_diet`, `open_selected_diet_detail`, `open_record_detail_window`.
- Training table/detail: `build_training_page`, `refresh_training`, `standardized_summary_for_day`, `display_name_for_movement`, `open_selected_training_detail`, `open_record_detail_window`.
- Movement Dictionary: `load_movement_dictionary`, `movement_definition_index`, `find_movement_definition`, `migrate_movement_references`.
- Movement Matrix: `build_movement_page`, `get_movement_matrix_dates`, `format_matrix_cell`, `refresh_movements`.
- Movement history editing: `open_movement_cell_detail`, `open_movement_history_editor`, `save_movement_history_records`.
- Movement dictionary editing/deletion: `edit_selected_movement_definition`, `save_movement_definition`, `delete_selected_movement_definition`, `delete_movement_definition`.
- Term-only dictionary manager: `open_movement_dictionary_manager`, `refresh_dictionary_manager`, `manager_edit_selected_aliases`, `toggle_movement_definition`.
- Parser: `parse_entry`, `extract_load_blocks`, `extract_cardio_metrics`, `movement_definition`, `resolve_movement`.
- Save safety: `backup_data`, `write_json`, `commit_pending`, `close`.
- Chinese display/Diet migration: `data/movement_dictionary.json`, `data/tracker.json`, `tools/zh_display_migration.py`, `refresh_diet`, `refresh_training`.
- Bowel Movement parsing: `extract_bowel_movement`, `parse_entry`, `commit_pending`, `refresh_body`.
- Body field pollution / recent Cardio repair: `extract_labeled_section`, `refresh_body`, `tools/body_bowel_cardio_migration.py`.
- Existing record editing: `open_record_editor`, `save_record_edit`, `open_selected_body_detail`, `open_selected_diet_detail`, `open_selected_training_detail`.
- Historical Chinese display and movement-note repair: `tools/training_notes_zh_migration.py`.

## Intentionally Deferred

- Charts and large dashboards
- Weekly/monthly reports
- AI diet or training analysis
- Training-plan generation
- Actual cloud upload/provider configuration, accounts, two-way sync, conflict resolution, and wearable integrations

## Display Rules

- New entries can use Chinese by default.
- UI movement names should resolve through `movement_id -> movement_dictionary.display_name`.
- `Raw Record` and `raw_entries[*].text` preserve original user text.
- Body main table displays only Date, Weight, Bowel Movement, Training split, Cardio summary, and Notes.
- Historical `Context` fields are preserved in records/details but not shown in the Body main table.
- Historical English Diet summaries may be shown in Chinese while the original text is preserved in `Food Summary Original` and `Notes Original`.
- If movement definitions need adjustment, update `data/movement_dictionary.json` first.
- Historical missing bowel records are intentionally ignored by Data Check; Review still warns when a new entry omits bowel information.
