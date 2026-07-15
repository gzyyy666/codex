# Fitness Ledger Changelog

## 2026-07-15 - CUSTOM movement canonicalization commands

- Added Core-only `preview_merge_custom_movement` and `merge_custom_movement` commands for explicit CUSTOM-to-existing-canonical migration; no Desktop, Web, Mini Program, or backend route was added.
- Preview now reports supported/unknown references, history counts and IDs, duplicate/same-day warnings, alias additions/conflicts, immutable raw audit state, source/target metadata, data fingerprint, blockers, and a stable plan identity without writing files or checkpoints.
- Execute re-reads and revalidates the current pair under the shared write lock, rejects stale previews, preserves every history business field and ID, removes the source only after all supported references migrate, and keeps canonical target metadata unchanged.
- Paired checkpoint, atomic writes, post-write validation, paired rollback, and existing Undo cover the complete migration; failed transactions discard their unused migration checkpoint after successful rollback.
- Added anonymous temporary-fixture coverage for migration invariants, conflict blockers, stale preview, tracker/dictionary/post-validation failures, Undo, Cloud payload target-only projection, existing Data Check, and dry-run SHA/size/mtime preservation.
- Formal data, schema, raw text, Cloud uploader, CloudBase, UI, and real CUSTOM records were not modified.

## 2026-07-15 - Silent archive health check

- Added a read-only Data Check summary endpoint that reuses the maintained desktop checker and caches results in memory by tracker/dictionary fingerprint.
- Kept healthy archives visually silent; review-worthy issues add only a restrained amber count to the existing Data Check navigation entry.
- Distinguished checker failure with a neutral `Health check unavailable` state while leaving the main Web experience usable.
- Added anonymous tests for healthy, warning/error, cache invalidation, unavailable, large-fixture, and file-integrity behavior.
- Data structure, save semantics, Cloud Sync, Analysis Export, CloudBase, and Mini Program impact: none.

## 2026-07-11 - Cloud Sync local-first console

- Rebuilt the Web Cloud Sync presentation around a single natural-language sync conclusion, a single primary action, and a compact local-to-cloud data flow.
- Made the mode explicit: users manually trigger sync; when configured, the click automatically prepares the payload, uploads it, and verifies the CloudBase replica. Local saves do not imply background upload.
- Moved hashes, provider metadata, import tools, report access, and environment checks out of the default visual hierarchy into compact status summaries or the closed Advanced & Recovery section.
- Added Chinese status mapping, staged sync feedback, safe failure messaging, and an explicit local-source / read-only-cloud boundary without changing backend endpoints or sync behavior.
- Updated the Style Bible with the durable Cloud Sync hierarchy and interaction rules.
- Modified files: `web_desktop/frontend/app.js`, `web_desktop/frontend/styles.css`, `docs/design/STYLE_BIBLE.md`, `CHANGELOG.md`.
- Data structure and API impact: none.

## 2026-07-07 - Visible Data Check repair actions and intuitive focus ranks

- Rebuilt the Data Check table as a five-column layout so the repair column remains visible without horizontal scrolling.
- Combined each issue with its suggested action and verified the CUSTOM repair CTA opens Movement Dictionary with `CUSTOM_` prefilled.
- Defined focus rank semantics as `0 = normal`, `1 = highest priority`, then `2`, `3`, and so on.
- Positive focus ranks automatically mark a movement as focused; non-focused movements continue sorting strictly by training frequency before name/date tie-breakers.
- Applied the same focus ordering to Web Movement Index, dictionary ordering, cloud payloads, ledgerRead, and the Mini Program.
- Visual QA screenshots confirmed the action column and direct CUSTOM route in the running Web app.
- Data structure impact: none.

## 2026-07-07 - Sync workbench, repair routing, and structured details

- Reorganized Web Cloud Sync into a Chinese-first manual-import control surface with explicit status, local preparation, cloud-check, and help groups.
- Added real fixed-target actions for opening the CloudBase import directory and setup guide; automatic upload remains intentionally disabled.
- Added direct Data Check repair routes, including a dedicated CUSTOM movement action that opens Movement Dictionary focused on unstandardized entries.
- Replaced Recent Saved daily-record JSON dumps with structured Body, Diet, Training, movement-set, note, and collapsed raw-input sections.
- Removed the incorrectly scoped training-day switch from Web Movement Index; the movement/training-day segmented switch remains only in the Mini Program training reference page.
- Refined Mini Program training-day cards into compact date/split records with current-body-part movement chips, notes, and a clear daily-detail action.
- Tests: Python compile, JavaScript syntax, regression, smoke, Web shared-write, Mini Program, and Cloud payload tests passed.
- Data structure impact: none.

## 2026-07-06 - Movement Index original-art restoration

- Restored the five approved body-area illustrations as direct, unfiltered panel backgrounds.
- Removed grayscale, brightness, multiply, mask, and dark-overlay treatments from Movement Index artwork.
- Enlarged and centrally cropped each illustration so the athlete and exercise occupy at least 70% of the panel.
- Reduced ordinary movement cards to highly translucent light/dark glass layers while keeping the lead card visually dominant.
- Preserved all Movement Index data, sorting, search, dictionary, and trajectory behavior.
- Modified files: `web_desktop/frontend/final-pass.css`, `docs/design/STYLE_BIBLE.md`, `design-qa.md`, `CHANGELOG.md`.
- Data structure impact: none.

## 2026-07-06 - Refined Movement Index material hierarchy

- Rebalanced all five Movement Index panels around dominant black-gray geometric figures, with mustard, coral, blue-green, smoky violet, and gray-blue retained only as local underglow.
- Enlarged and strengthened the approved shoulder, chest, back, legs, and arms figures to occupy roughly 60-75% of each panel instead of appearing as faint edge decoration.
- Increased ordinary movement-card transparency so panel color and body-area artwork remain visible through the foreground surface.
- Preserved a three-level hierarchy: semi-translucent warm-yellow lead card, light glass medium-frequency card, and dark glass low-frequency card.
- Added a controlled veil and no more than two trajectory lines per panel so illustrations remain recognizable without competing with labels or actions.
- Preserved Movement Index structure, sorting, search, dictionary entry, movement data, and detail navigation.
- Modified files: `web_desktop/frontend/final-pass.css`, `docs/design/STYLE_BIBLE.md`, `CHANGELOG.md`.
- Data structure impact: none.
- User verification: visually compare all five body-area panels at 1280px and 1600px widths.

## 2026-07-06 - Unified Web Body-Area Art

- Replaced the Web Training and Movement Progress body-area images with the approved five-image abstract set shared with the Mini Program.
- Kept shoulder amber, chest coral, back teal, legs violet, and arms cyan consistent across Training entry controls, selected Training themes, Movement Index groups, and Movement Detail headers.
- Added a darker editorial treatment for Web imagery so translucent controls and movement cards remain readable.
- No layout, filtering, data, API, or record behavior changed.

## 2026-07-05 - WeChat Sitemap Validation

- Replaced the empty Mini Program sitemap rule list with an explicit private `disallow` rule for all pages.
- Fixed WeChat DevTools real-device error `-80055 Invalid SiteMap` without changing page access or application behavior.

## 2026-07-05 - WeChat Archive Navigation And Theme Art

- Promoted the five-body-area training archive to the Mini Program Home tab and removed the redundant standalone Home and Search tabs.
- Added a compact daily Training Records tab with tolerant date search, newest/oldest ordering, and explicit day-detail actions.
- Added tolerant date search and newest/oldest ordering to the secondary Body and Diet archives.
- Added one read-only `trainingRecords` CloudBase action without changing any collection or formal data structure.
- Added a cohesive five-image abstract training set: shoulder amber, chest coral, back teal, legs violet, and arms cyan.
- Selected body-area pages now use matching background washes and low-opacity representative art while preserving movement-first readability.
- Re-entering the Home tab resets a selected body-area theme to the five-area overview.
- Training Records now uses a restrained printed-paper background and layered nutrition-note-inspired archive slips.
- Removed the superseded first-generation Mini Program theme images.
- JavaScript syntax, Mini Program structure, JSON, and cloud payload tests passed.

## 2026-07-05 - WeChat Gym Reference UX Completion

- Compressed the Mini Program Home hero and made body-area selection plus the first two high-frequency movements visible in the primary mobile flow.
- Home now defaults to the most recently trained body area and switches movement content in place.
- Added real Training sorting by frequency, latest date, and movement name.
- Promoted the latest three movement sessions, including reps and volume, above older history.
- Added secondary read-only Body and Diet archive pages, entered from Status rather than the main tab bar.
- Added `bodyRecords` and `dietRecords` read-only cloud actions without changing collections or formal data structures.
- Added backward-compatible search-result cleanup so older cloud responses do not expose concatenated index blobs.
- Kept long notes and meal text collapsed behind explicit actions.
- JavaScript, Mini Program structure, JSON, and cloud payload tests passed.

## 2026-07-05 - WeChat Gym-Side Training Workbench

- Replaced the generic Mini Program dashboard with a body-area-first gym reference flow.
- Added shoulder, chest, back, legs, and arms archive controls using the established Web theme colors.
- Added read-only `bodyAreas` and `bodyArea` cloud-function actions that aggregate movement frequency, latest performance, previous performance, historical best, and recent sessions without changing formal data structures.
- Reworked movement detail into recent signals plus a compact chronological trajectory.
- Reworked Today, search, and record details so long food/training prose is collapsed behind explicit expand or detail actions.
- Cleaned search results so users see movement names, dates, record types, and short previews instead of concatenated search-index text.
- Changed Mini Program navigation to Home, Training, Search, and Status; Today remains accessible as a secondary archive route.
- Preserved OpenID allowlisting, read-only CloudBase access, local JSON authority, and all desktop/Web behavior.
- Validation: JavaScript syntax, Mini Program structure, JSON files, and cloud payload tests passed. WeChat DevTools visual QA remains a manual user step.

## 2026-07-05 - Cloud Review And WeChat Read-Only Preparation

- Audited the previous cloud-sync claim and documented that no provider, environment, or network upload is configured.
- Upgraded the disposable replica to schema v2 with ten collections, latest summary, data-quality issues, complete movement aliases, counts, and explicit local-only sync state.
- Removed full raw record fields from the default replica and retained empty raw references only.
- Added per-collection CloudBase import files, manifest, dry-run report, review guide, and maintenance contract.
- Added a WeChat DevTools project skeleton with seven mobile pages and one OpenID-allowlisted read-only cloud function.
- Added setup, API, UI-state, preview, payload, and Mini Program validation documentation.
- Preserved local JSON as the source of truth and made no desktop, Web, parser, or formal data-structure changes.

## 2026-07-03 - Daily Entry Material Workbench

- Upgraded Daily Entry from a flat form composition to a layered writing workbench.
- Added a thick notebook slab, tactile primary action, floating Today receipt, layered Recent Saved slips, and local readiness glass status.
- Preserved the previously approved Training body-area theme-card controls and in-page theme behavior.
- Added functional material roles, contact/ambient shadows, edge highlights, and reduced-motion behavior to Daily Entry.
- Preserved all existing input, Review, save, Undo, search, sort, theme filtering, record detail, and data behavior.
- Added no frontend dependencies and made no backend or JSON changes.

## 2026-07-03 - Training Records In-Page Body Themes

- Replaced the independent Before You Train route with five body-area controls inside Training Records.
- Added browser-only shoulder, chest, back, legs, and arms classification across Split, summary, notes, and raw record text.
- Added synchronized theme state for the page header, atmosphere, active control, record filter, card accents, focus panel, and empty state.
- Preserved Training search, sorting, session numbering, record editing, and explicit detail actions.
- Added `All Records` and `Back to overview` without changing the URL, backend contracts, or local JSON.
- Added restrained theme transitions and reduced-motion fallback without new frontend dependencies.

## 2026-07-03 - High-Availability Z-Axis Web Pass

- Added the five body-area reference controls directly to Training Records and removed the extra mode-tab step.
- Added body-area scene transitions, representative offline imagery, and staggered movement-card entry to Pre-Workout Reference.
- Added layered material tokens, tactile hover/pressed states, contact shadows, ambient shadows, inner highlights, and reduced-motion support.
- Fixed Analysis Export action labels and added explicit preparing, ready, and error states.
- Upgraded the Home training-reference action into a visible secondary physical control.
- Preserved all existing data, API, editing, Undo, movement, and export behavior.

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

## 2026-07-04 - Web Material Depth Reconciliation

Modified files:

- `web_desktop/frontend/styles.css`
- `docs/design/STYLE_BIBLE.md`
- `design-qa.md`

Changes:

- Refined the existing material tokens instead of introducing a competing style system.
- Added low-opacity local paper grain, two-stage contact/ambient shadows, and WebKit frosted-surface fallbacks.
- Improved Daily Entry ruled-paper alignment, journal-slab grounding, receipt depth, archive-slip edges, and primary-control focus states.
- Improved Training node contact depth, active-theme glow, archive-card grain, toolbar controls, and focus-panel frosting.
- Added restrained material treatment to existing modal and drawer surfaces.
- Preserved all routes, DOM contracts, data structures, API calls, parser behavior, and save behavior.

Data structure impact: None.

User data modified: No.

Tests:

- `node --check web_desktop/frontend/app.js`
- CSS brace validation
- `python tools/regression_test.py`
- Edge render review at 1440 x 1100 for Daily Entry and Training Records

## 2026-07-04 - Training Focused Archive Metamorphosis

Modified files:

- `web_desktop/frontend/app.js`
- `web_desktop/frontend/styles.css`
- `docs/design/STYLE_BIBLE.md`
- `design-qa.md`

Changes:

- Preserved the shoulder illustration and assigned the separate dynamic arm artwork to Arms, matching Movement Progress.
- Added a controlled selected-body-part grid transformation: the active archive becomes the foreground anchor while the remaining controls stay legible and interactive.
- Completed the wide-screen focused composition with a tall cover, horizontal factual receipt, and compact chronological training slips, eliminating dead space after filtering.
- Reused the existing filtered records and Focus Panel as the factual summary instead of inventing unsupported 1RM or monthly metrics.
- Added explicit Training-route reset behavior so returning from another primary page opens the all-records overview.
- Preserved in-page body-area switching without a new route.

Data structure impact: None.

User data modified: No.

Tests:

- JavaScript syntax validation
- CSS brace validation
- `python tools/regression_test.py`
- Edge/CDP interaction render for Arms focused state at 1440 x 1100
- Visual evidence: `web_desktop/frontend/design-qa-training-arms-v2.png`
- Navigation test: Training -> Home -> Training returns `overview`

## 2026-07-04 - Export Material Workbench

Modified files:

- `web_desktop/frontend/styles.css`
- `docs/design/STYLE_BIBLE.md`

Changes:

- Compressed the Export hero and vertical rhythm so the complete build workflow fits in one standard desktop viewport.
- Upgraded the Build Range card to warm paper/frosted material with inset controls and gold focus treatment.
- Upgraded the Export Capsule to a layered graphite slab with edge highlights, grain, warm ambient reflection, and grounded contact shadows.
- Refined the Generate export button as the sole tactile gold CTA while preserving all existing behavior and generated actions.

Data structure impact: None.

User data modified: No.

Tests:

- JavaScript syntax validation
- CSS brace validation
- `python -m py_compile web_desktop/backend/server.py`
- `python tools/regression_test.py`
- Real export generation and Edge render at 1600 x 1000
- Visual evidence: `web_desktop/frontend/design-qa-export-material.png`
- Success-state evidence: `web_desktop/frontend/design-qa-export-success.png`

## 2026-07-04 - Final Archive Interaction Pass

Modified files:

- `web_desktop/frontend/index.html`
- `web_desktop/frontend/app.js`
- `web_desktop/frontend/styles.css`
- `web_desktop/frontend/final-pass.css`
- `docs/design/STYLE_BIBLE.md`

Changes:

- Reduced Body controls to search, recent-days range, and newest/oldest ordering.
- Reduced Diet controls to search and newest/oldest ordering.
- Corrected Training search and body-area archives to match only the daily training theme/split and date, not movement contents.
- Rebalanced selected Training views with alternate body-area controls as a vertical index beside the active cover and denser first-screen information.
- Moved selected Training search, ordering, and overview controls into the former decorative header space so the summary and records begin higher.
- Kept mixed-theme days eligible by their stored split while limiting each focused card's Key Movements and notes to the selected body area.
- Removed Dictionary from global navigation and added a contextual tactile entry to Movement Index.
- Removed the idle Export capsule's decorative corner orbit while preserving state color changes.

Data structure impact: None.

User data modified: No.

Tests:

- JavaScript syntax validation
- CSS brace validation
- `python -m py_compile web_desktop/backend/server.py`
- `python tools/regression_test.py`
- Edge render review at 1600 x 1000 for Body, Diet, Training Shoulder, Movement Index, and Export

## 2026-07-04 - Web Interaction Closure

Modified files:

- `web_desktop/frontend/app.js`
- `web_desktop/frontend/final-pass.css`
- `docs/design/STYLE_BIBLE.md`

Changes:

- Added a restrained hover, focus, and pressed treatment to Body `Open record` actions without making the full slip clickable.
- Added an explicit Movement Dictionary return control to Movement Index.
- Rebound Training search and ordering directly to the current page and persisted their state across overview/body-area rerenders.
- Confirmed Training search and ordering work in both the archive overview and selected body-area pages.

Data structure impact: None.

User data modified: No.

Tests:

- JavaScript syntax validation
- CSS brace validation
- `python tools/regression_test.py`
- Browser interaction test at 1600 x 1000 covering Training overview search/order, Shoulder search/order, Dictionary back navigation, and Body action hover/focus styling

## 2026-07-05 - Training Control Click Fix

Modified files:

- `web_desktop/frontend/app.js`

Changes:

- Restricted the Training theme click handler to actual `button[data-training-theme]` controls.
- Prevented clicks on search and ordering controls from matching the themed page container and rerendering the whole page.
- Disabled browser autocomplete on Training search to avoid saved-value overlays during local archive search.

Root cause:

- The Training page root also carries `data-training-theme`. The previous broad `closest('[data-training-theme]')` handler treated any click inside the page as a theme-selection click.

Tests:

- Real mouse click retained the same Training page DOM node.
- Sequential keyboard input retained focus and the entered value.
- Overview search for `肩` returned 9 records.
- Oldest-first ordering returned the earliest matching record.
- The same click, search, and ordering checks passed in the Shoulder archive.

## 2026-07-06 - Review Classification, Repair Routing, Cloud Workbench, Mini Freshness

Modified areas:

- Shared review/save commands and desktop/Web review UI
- Web Data Check and Cloud Sync workbench
- Cloud payload contract and validation report
- Mini Program training reference and freshness display

Changes:

- New movements now require a training-area selection before they can be added to the dictionary.
- Movement definitions support an optional `pinned` flag; pinned movements sort before frequency-based results.
- Data Check rows expose separate Detail and Repair actions while preserving user-confirmed edits.
- Export includes a quiet Cloud Sync entry for building the ten-collection import package and comparing post-import `fl_meta`.
- Mini Program body-part pages can switch between movement history and related training days.
- Mini Program Training and Reference pages show cloud generation time and latest record date, warning after 48 hours.

Data structure impact: optional `movement_dictionary.movements[*].pinned` boolean only; missing values remain false.

Cloud policy: local JSON remains authoritative; no automatic network upload or two-way sync was introduced.

Tests: Python compile, JavaScript syntax checks, regression, smoke, payload build, dry-run validation, service-level fl_meta verification.

## 2026-07-07 - Cloud Maintenance Workbench, Focus Rank, And Training-Day Views

Modified areas:

- Web Cloud Sync status, verification, logs, and safety messaging
- Web Data Check repair routing
- Movement dictionary focus ordering and cloud contract
- Web Movement Index movement/training-day views
- Mini Program body-area movement/training-day views

Changes:

- Cloud Sync now reports manual mode, local/cloud freshness, environment detection, raw-text policy, recent local operations, and per-collection verification results.
- Direct CloudBase upload remains explicitly disabled because provider credentials are not configured.
- Data Check reuses existing editors and exposes issue-specific destinations instead of inventing a second repair system.
- Movement definitions support optional `focus_rank`; pinned items sort by rank before frequency and name.
- Web Movement Index can switch between movement cards and training days aggregated from movement history.
- Mini Program training days use movement-history membership, support multi-part days, show related movement counts, and open the existing daily record page.

Data structure impact: optional `movement_dictionary.movements[*].focus_rank` integer only; missing values remain `0`.

Tests: Python compile, JavaScript syntax checks, regression, smoke, cloud payload, and Mini Program workbench tests.
