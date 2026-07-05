# Fitness Ledger Function Index

## Web Desktop Foundation

- `LedgerCommandService.parse`: Calls the maintained desktop parser through an injected UI-free adapter and produces the Review payload.
- `LedgerCommandService.review_payload`: Adds summary, Chinese warnings, duplicate counts, and active mapping options.
- `LedgerCommandService.save`: Uses a cross-process lock, paired checkpoints, validated Review actions, atomic writes, and rollback.
- `LedgerCommandService.movement_definitions`: Returns dictionary terms with tracker history counts.
- `LedgerCommandService.create_movement_definition`: Creates a validated dictionary term and reconciles matching history.
- `LedgerCommandService.update_movement_definition`: Updates names, aliases, metadata, tracker display names, and matching historical records.
- `LedgerCommandService.set_movement_active`: Changes visibility without deleting aliases or history.
- `LedgerCommandService.delete_movement_definition`: Requires exact-name confirmation and deletes structured movement history while preserving raw input.
- `LedgerCommandService.update_record`: Validates and edits the desktop-compatible Body, Diet, or Training field set.
- `LedgerCommandService.update_movement_history`: Locates one history row by permanent IDs and validates order, sets, cardio, notes, and raw movement detail.
- `LedgerWebService.capabilities`: Reports the active shared Review/Save boundary.
- `LedgerWebService.parse_entry`: Stores a server-side pending Review identity for one parsed raw entry.
- `LedgerWebService.save_review`: Merges only allowed Review edits and invokes the shared save service.
- `LedgerWebService.recent`: Builds the latest three-date overview from shared local data.
- `LedgerWebService.collection`: Returns bounded Body, Diet, or Training collections without writing data.
- `LedgerWebService.movement_index`: Returns searchable dictionary terms for the web Movement page.
- `LedgerRequestHandler.do_GET`: Serves static frontend assets and versioned read endpoints.
- `LedgerRequestHandler.do_POST`: Handles shared daily and dictionary commands; duplicate dates return `409` with explicit save modes.
- `web_desktop/launcher.pyw`: Starts the local server and opens the UI in isolated Edge app mode.
- `web_desktop/frontend/app.js`: Controls page navigation, API reads, real-data rendering, search, and detail dialogs.
- `docs/design/STYLE_BIBLE.md`: Durable visual and interaction reference for future Web and simplified Tkinter UI maintenance.

### Web Training And Export Presentation

- `quickPage`: Renders the Daily Entry writing workbench while preserving the shared Parse/Review/Save workflow.
- `compactEntryAside`: Renders the floating Today receipt and layered Recent Saved archive slips from existing local data.
- `bodyPartThemes`: Defines the five Training Records theme identities, copy, colors, imagery, matching keywords, and empty states.
- `matchBodyPart`: Classifies a training record in the browser from Split, Standardized Summary, Notes, and Raw Record without changing source data.
- `bodyPartStats`: Derives session, latest-date, and frequent-movement summaries for one theme.
- `bodyPartThemeControls`: Renders the five primary in-page theme controls and their live record counts.
- `trainingPage`: Renders overview or selected body-part state on the same Training Records route.
- `trainingSidePanel`: Switches between the overview Training Index and selected Body Part Focus Panel.
- `renderTraining`: Preserves search, sorting, detail actions, and session numbering while limiting records to the selected theme.
- `exportPage`: Renders the layered export console and explicit idle, loading, success, and error states.
- `renderExportResult`: Presents visible Copy Markdown, Download Markdown, and Download JSON actions after generation.
- `web_desktop/frontend/styles.css`: Owns the three-layer material system, Daily Entry workbench, Training body-area theme cards, physical control states, reduced-motion fallback, and export-console depth.
- `tools/capture_web_state.mjs`: Captures a specified Web UI state through the local Edge debugging session for visual regression evidence.

Future Web write work must begin with `web_desktop/ARCHITECTURE.md` and extend `ledger_commands.py` rather than writing JSON in the request handler.

## Desktop UI Presentation Layer

- `_premium_ensure_visual_assets`: Loads the current generated Hero and FL icon assets.
- `_premium_configure_styles`: Applies shared premium widget, scrollbar, and combobox styling.
- `_premium_page_shell`: Builds the shared cinematic Hero and editorial page header.
- `_premium_build`: Builds the current sidebar, visual navigation, page host, and maximized desktop state.
- `_premium_build_quick_entry`: Builds the complete three-column capture, Hero status, and recent-record composition.
- `_premium_mousewheel`: Routes Windows mouse-wheel input to the scrollable Text, Canvas, or Treeview currently under the pointer.
- `_premium_show_page`: Keeps page switching and selected navigation visually synchronized.
- `_nike_configure_styles`: Applies the current high-contrast desktop widget style without changing application behavior.
- `_nike_show_page`: Raises a page and synchronizes the active sidebar navigation state.
- `_nike_page_shell`: Builds the shared typography-led page header and content canvas.
- `_nike_build`: Builds the shared sidebar, navigation, footer, and page host.
- `_nike_build_quick_entry`: Builds the primary daily capture composition and latest-record overview.
- `_surface`, `_soft_entry`, `_soft_text`, `_pill`, `button`: Shared visual primitives used by all desktop pages and modal windows.

Future desktop visual work must modify the final `_premium_*` presentation layer first. Earlier `_nike_*`, `_themed_*`, and `_editorial_*` definitions remain compatibility implementation and should not be treated as the active visual entry point.

## JSON And Data Safety

| Function | Responsibility | Used by |
| --- | --- | --- |
| `read_json` | Read JSON with a fallback. | Startup and imports |
| `write_json` | Validate a temporary JSON file and atomically replace the target. | All saves |
| `backup_data` | Create a timestamped valid database backup. | Confirmed save and close |
| `backup_file` | Validate and back up one JSON file with a named prefix. | Regular backups and pre-undo safety |
| `create_undo_checkpoint` | Create a paired tracker/dictionary checkpoint before a user save. | Confirmed save and record editor |
| `blank_database` | Create the compatible empty schema. | Initialization |
| `import_history` | Convert the extracted workbook history into the local database. | First startup |
| `ensure_database` | Load or initialize the database and safely apply missing movement IDs. | App startup |
| `load_movement_dictionary` | Load the versioned movement dictionary. | Startup, migration, recognition |
| `movement_definition_index` | Build stable ID and normalized alias lookup indexes. | Startup and dictionary updates |
| `find_movement_definition` | Resolve an ID, display name, English name, or alias to one definition. | Import and migration |
| `migrate_movement_references` | Add stable movement IDs to existing movement objects and history records without deleting old fields. | Startup migration |
| `add_custom_movement_definition` | Register a confirmed unknown movement with a stable `CUSTOM_nnn` ID. | New movement save |

## Parsing Daily Input

| Function | Responsibility | Used by |
| --- | --- | --- |
| `parse_number` | Extract one numeric field. | Body, diet, cardio parsing |
| `parse_date` | Resolve full, short, or current date. | `parse_entry` |
| `extract_load_blocks` | Parse weight, reps, and sets, including progression blocks. | Training parsing and history import |
| `extract_cardio_metrics` | Parse minutes, incline, speed, and heart rate. | Training parsing |
| `extract_labeled_section` | Extract top-level labeled sections without absorbing indented movement notes. | Parser and cleanup helpers |
| `extract_training_section` | Extract the training split and movement body only up to the next top-level Cardio, Diet, or Notes section. | `parse_entry` |
| `extract_bowel_movement` | Parse explicit or clear natural-language bowel movement notes. | `parse_entry` |
| `compact_section_lines` | Compact section text while preserving line boundaries. | Parser display fields |
| `is_cardio_line` | Detect cardio movement lines. | `parse_entry` |
| `strip_movement_metrics` | Remove order and load text from a movement name. | `parse_entry` |
| `FitnessTrackerApp.parse_training_movements` | Parse same-line numbering, number-only headers, and unnumbered movement names followed by set lines without crossing section boundaries. | `parse_entry` |
| `FitnessTrackerApp.parse_entry` | Parse one raw daily note into body, diet, and training sections. | Quick Entry |

## Movement Recognition And History

| Function | Responsibility | Used by |
| --- | --- | --- |
| `normalize_name` | Normalize movement names for alias matching. | Search and movement resolution |
| `title_case_movement` | Format a new movement display name. | New movement creation |
| `FitnessTrackerApp.movement_definition` | Resolve a tracker movement object to its dictionary definition. | Matrix display and search |
| `FitnessTrackerApp.resolve_movement` | Resolve aliases through the dictionary or register a stable custom movement. | Confirmed training save |
| `FitnessTrackerApp.review_new_movements` | Ask for approval before each unknown movement can enter the dictionary and Movement Matrix. | Confirmed training save |
| `FitnessTrackerApp.resolve_reviewed_movement` | Apply Review decisions to use, map, add, or skip a movement. | Confirmed training save |
| `FitnessTrackerApp.tracker_movement_for_definition` | Reuse or create the tracker-side movement object for a chosen dictionary definition. | Review mapping and save |
| `format_number` | Format numeric values without unnecessary decimals. | Matrix formatting |
| `make_cell_preview` | Collapse whitespace and shorten long table values without changing source data. | Body, Diet, Training, Movement Matrix |
| `format_set_summary` | Format strength or cardio details. | Matrix cells |
| `format_matrix_cell` | Format `Day / Ex / training details`. | Movement Matrix |
| `FitnessTrackerApp.get_movement_matrix_dates` | Return all history dates in ascending order. | Matrix refresh |

## UI Build

| Function | Responsibility | Used by |
| --- | --- | --- |
| `button` | Build consistent app buttons. | All pages |
| `apply_icon` | Apply the app icon. | Main and detail windows |
| `FitnessTrackerApp.page_shell` | Build a standard page header and container. | All pages |
| `FitnessTrackerApp.build_table_with_scrollbars` | Build a resizable table with vertical and horizontal scrolling. | Body, Diet, Training |
| `FitnessTrackerApp.build_body_page` | Build the simplified body table. | Startup |
| `FitnessTrackerApp.build_diet_page` | Build the wide diet table and detail binding. | Startup |
| `FitnessTrackerApp.build_training_page` | Build the wide training table and detail binding. | Startup |
| `FitnessTrackerApp.build_movement_page` | Build the searchable Movement Matrix shell. | Startup |
| `FitnessTrackerApp.build_data_check_page` | Build the read-only rule-check table. | Startup |
| `FitnessTrackerApp.open_detail_window` | Show copyable, read-only content in a scrollable detail window. | All data pages |
| `FitnessTrackerApp.open_record_detail_window` | Convert a record to labeled full text and open the shared detail window. | Body, Diet and Training |
| `FitnessTrackerApp.open_record_editor` | Open read-only detail/editor window with Edit, Save, and Cancel. | Body, Diet, Training |
| `FitnessTrackerApp.open_movement_cell_detail` | Resolve a matrix cell by row ID and column ID and open its history editor. | Movement Matrix |
| `FitnessTrackerApp.open_movement_history_editor` | Open editable structured history fields for one movement/date cell. | Movement Matrix double-click |
| `FitnessTrackerApp.edit_selected_movement_definition` | Open the selected row's dictionary editor. | Movement Matrix controls |
| `FitnessTrackerApp.open_movement_dictionary_manager` | Open the term-only movement dictionary window without training history. | Movement Progress button |
| `FitnessTrackerApp.refresh_dictionary_manager` | Apply search/status filters and refresh dictionary terms. | Dictionary manager |
| `FitnessTrackerApp.manager_edit_selected_aliases` | Add and remove aliases with the standard display name protected. | Dictionary manager |

## Review Before Save

| Function | Responsibility | Used by / Notes |
| --- | --- | --- |
| `FitnessTrackerApp.parse_and_review` | Read Quick Entry raw text, parse it, and open the review popup. | Entry point for `Parse & review` |
| `FitnessTrackerApp.open_review_window` | Render parsed body, diet, training, and movement preview in a scrollable popup with fixed bottom buttons. | Review popup layout; `Confirm & save` calls `commit_pending`; `Cancel` closes without saving |
| `FitnessTrackerApp.collect_review_warnings` | Report missing fields, duplicate dates, suspicious section pollution, missing sets, and new movements. | Review warning panel |
| `FitnessTrackerApp.format_review_summary` | Build the compact final Body/Diet/Training summary. | Review header |
| `FitnessTrackerApp.refresh_review_summary` | Refresh the final summary after Review edits without overwriting manual summaries. | Review form events |
| `FitnessTrackerApp.apply_review_edits` | Validate and copy editable Review fields and movement decisions into the pending record. | Warning refresh and confirmed save |
| `FitnessTrackerApp.confirm_review` | Validate Review edits and honor cancel decisions before saving. | Review confirmation button |
| `FitnessTrackerApp.records_on_date` | Find Body, Diet, and Training records for duplicate-date checks. | Review warnings and save |
| `FitnessTrackerApp.choose_duplicate_action` | Ask whether to overwrite, append a second training session, or cancel. | Duplicate-date save |
| `FitnessTrackerApp.remove_records_for_overwrite` | Replace one date's structured records and histories while marking old raw entries superseded. | Overwrite save mode |
| `FitnessTrackerApp.commit_pending` | Review unknown movements, save approved records, and aggregate movement notes into the training-day Notes field. | Existing confirmed-save flow; backs up then writes `data/tracker.json` |

## Table Refresh

| Function | Responsibility | Used by |
| --- | --- | --- |
| `FitnessTrackerApp.refresh_body` | Display Date, Weight, Bowel Movement, Training split, Cardio summary, and Notes while preserving hidden Context in details. | Startup and save |
| `FitnessTrackerApp.refresh_diet` | Display compact diet previews and map rows to full records. | Startup and save |
| `FitnessTrackerApp.display_name_for_movement` | Resolve UI movement names through `movement_id -> movement_dictionary.display_name`. | Training and Movement UI |
| `FitnessTrackerApp.standardized_summary_for_day` | Rebuild Chinese training summaries from movement history and the movement dictionary. | Training table and detail display |
| `FitnessTrackerApp.refresh_training` | Display compact training previews with Chinese standardized movement names. | Startup and save |
| `FitnessTrackerApp.refresh_movements` | Build the compact matrix with dictionary display names and dictionary-backed search. | Startup, save, search |
| `FitnessTrackerApp.refresh_all` | Refresh all data pages. | Startup and save |
| `FitnessTrackerApp.refresh_quick_overview` | Refresh the latest-day status and recent three-day shortcut cards. | Startup, save, edit, and undo |
| `FitnessTrackerApp.latest_day_status` | Evaluate latest structured fields and High Data Check issues without AI. | Quick Entry status |
| `FitnessTrackerApp.recent_record_dates` | Return the latest distinct saved dates. | Quick Entry recent records |
| `FitnessTrackerApp.open_record_from_overview` | Reuse an existing Body/Diet/Training editor from a shortcut. | Quick Entry and Data Check |
| `FitnessTrackerApp.open_raw_record_detail` | Open preserved raw input read-only. | Quick Entry and Data Check |
| `FitnessTrackerApp.collect_data_issues` | Run non-AI quality checks without modifying records. | Data Check page |
| `FitnessTrackerApp.refresh_data_check` | Populate the Data Check table after filtering acknowledged issues. | Page open, refresh, and acknowledge |
| `FitnessTrackerApp.acknowledge_selected_data_issue` | Mark one selected Data Check issue as confirmed and hide it. | Data Check |
| `FitnessTrackerApp.reset_acknowledged_data_issues` | Restore all previously hidden Data Check issues. | Data Check |
| `FitnessTrackerApp.open_selected_data_issue` | Open a locatable Body, Diet, Training, Movement, Raw, or Dictionary target. | Data Check |

## Save And Lifecycle

| Function | Responsibility | Used by |
| --- | --- | --- |
| `FitnessTrackerApp.commit_pending` | Back up and append confirmed parsed data while preserving raw text. | Confirmation window |
| `FitnessTrackerApp.save_record_edit` | Back up and save edits to the selected Body, Diet, or Training record without deleting other fields. | Record editor |
| `FitnessTrackerApp.save_movement_history_records` | Validate and save set/order/note/raw/cardio edits for matrix history records. | Movement history editor |
| `FitnessTrackerApp.reconcile_unassigned_movements_for_definition` | After an alias edit, merge matching CUSTOM rows and restore matching non-superseded skipped raw movements into the formal movement history while preserving raw text. | Dictionary editor |
| `FitnessTrackerApp.save_movement_definition` | Validate and save dictionary metadata, reconcile matching historical unassigned movements, and synchronize the tracker row name. | Dictionary editor |
| `FitnessTrackerApp.toggle_movement_definition` | Safely enable or disable a definition without deleting history or aliases. | Dictionary manager |
| `FitnessTrackerApp.delete_movement_definition` | Delete one confirmed dictionary entry and its complete structured movement row while preserving raw input. | Movement Matrix delete |
| `FitnessTrackerApp.undo_last_save` | Restore the newest paired save checkpoint and retain it as an `undone` backup. | Quick Entry |
| `FitnessTrackerApp.close` | Back up and safely save before closing. | Window close |
| `main` | Start the desktop application. | Launcher |

## Shared Web Platform Services

| Function | Responsibility | Used by |
| --- | --- | --- |
| `LedgerCommandService.undo_status` | Find the newest valid paired tracker/dictionary checkpoint without changing data. | Web Daily Entry |
| `LedgerCommandService.undo_last_write` | Restore the paired checkpoint, create pre-undo backups, and consume the checkpoint. | Web Undo |
| `data_quality_view.collect_issues` | Run the established desktop Data Check rules headlessly and filter acknowledged issues. | Web Data Check |
| `data_quality_view.acknowledge_issue` | Atomically persist a confirmed issue key. | Web Data Check |
| `LedgerViewModels.movement_history` | Return normalized history, metrics, changes, and Recent 3 performance. | Movement detail, export |
| `LedgerViewModels.workout_reference` | Build a read-only reference from the user's matching recent sessions. | Training Pre-Workout |
| `LedgerViewModels.analysis` | Build one date-range projection for export and cloud payloads. | Analysis Export, cloud payload |
| `analysis_export.build_export` | Render Markdown and JSON from the shared analysis view. | Web Export |
| `cloud_payload.build_cloud_payload` | Build the disposable read-only replica collections without full raw text. | Cloud dry-run |

## Cloud Replica And WeChat Viewer

- `cloud_sync/build_cloud_payload.py`: Builds schema v2, ten collection files, and a CloudBase import manifest from shared local view models.
- `cloud_sync/sync_to_cloud.py --dry-run`: Validates the payload and writes an explicit no-network sync report.
- `mini_program/miniprogram/services/ledger.js`: Central Mini Program cloud-function client with unconfigured and network error states.
- `mini_program/cloudfunctions/ledgerRead/index.js`: OpenID-allowlisted, read-only query boundary for status, latest, recent, reference, search, movement history, and record detail.
- `tools/cloud_payload_test.py`: Verifies collection contract, counts, raw-text exclusion, and no-network status.
- `tools/mini_program_test.py`: Verifies project skeleton completeness and absence of cloud write calls.

## Web API Additions

- `GET /api/undo-status`, `POST /api/undo`
- `GET /api/data-check`, `POST /api/data-check/acknowledge`
- `GET /api/workout-reference`
- `GET /api/movement-insight`
- `POST /api/analysis-export`

## Future Change Routing

| Future task | Primary functions to inspect first |
| --- | --- |
| New movement auto-recognition | `parse_entry`, `parse_training_movements`, `resolve_movement`, `find_movement_definition`, `add_custom_movement_definition`, `commit_pending`, `refresh_movements` |
| New movement review/approval | `format_review_lines`, `review_new_movements`, `commit_pending`, `resolve_movement`, `add_custom_movement_definition` |
| Review editing and warnings | `open_review_window`, `apply_review_edits`, `collect_review_warnings`, `confirm_review` |
| Review final summary | `format_review_summary`, `refresh_review_summary`, `apply_review_edits` |
| Duplicate date handling | `records_on_date`, `choose_duplicate_action`, `remove_records_for_overwrite`, `commit_pending` |
| Undo save | `create_undo_checkpoint`, `undo_last_save`, `write_json` |
| Data quality checks | `build_data_check_page`, `collect_data_issues`, `refresh_data_check` |
| Daily-use home overview | `build_quick_entry`, `recent_record_dates`, `latest_day_status`, `refresh_quick_overview`, `open_record_from_overview` |
| Data Check navigation | `collect_data_issues`, `refresh_data_check`, `open_selected_data_issue` |
| Input auto-recording | `parse_and_review`, `open_review_window`, `commit_pending`, `backup_data`, `write_json` |
| Review popup save buttons | `open_review_window`, `commit_pending` |
| Movement Matrix cell detail | `refresh_movements`, `format_matrix_cell`, `open_movement_cell_detail`, `open_detail_window` |
| Movement Matrix record editing | `refresh_movements`, `open_movement_cell_detail`, `open_movement_history_editor`, `save_movement_history_records` |
| Movement dictionary editing/deletion | `selected_movement_and_definition`, `edit_selected_movement_definition`, `save_movement_definition`, `reconcile_unassigned_movements_for_definition`, `delete_selected_movement_definition`, `delete_movement_definition` |
| Dedicated dictionary manager | `open_movement_dictionary_manager`, `refresh_dictionary_manager`, `manager_selected_definition`, `manager_edit_selected_aliases`, `toggle_movement_definition` |
| Chinese display and historical Diet conversion | `movement_dictionary.json`, `display_name_for_movement`, `standardized_summary_for_day`, `refresh_diet`, `refresh_training`, `open_record_detail_window`, `tools/zh_display_migration.py` |
| Bowel movement / Body field issues | `extract_bowel_movement`, `extract_labeled_section`, `parse_entry`, `commit_pending`, `refresh_body`, `tools/body_bowel_cardio_migration.py` |
| Existing record editing | `open_record_editor`, `save_record_edit`, `open_selected_body_detail`, `open_selected_diet_detail`, `open_selected_training_detail` |
