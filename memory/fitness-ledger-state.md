---
id: fitness-ledger-state
type: memory
status: active
updated: 2026-07-06
tags: [fitness-ledger, python, desktop, web, rollback]
source: projects/fitness-ledger
---

# Fitness Ledger State

## Summary

Fitness Ledger is a local-first personal fitness journal with a maintained Tkinter desktop application, a browser-grade Web application using shared safe read/write services, and a read-only mobile viewer. The authoritative local data remains JSON and is intentionally excluded from the public memory repository.

## Durable Architecture

- Maintained desktop entry: `stable_app.pyw`.
- Desktop source of truth: local `data/tracker.json` and `data/movement_dictionary.json`.
- Shared write boundary: `ledger_commands.py` provides UI-free Parse/Review/Save and Movement Dictionary administration, cross-process locking, paired checkpoints, atomic writes, and rollback.
- Shared read-only projection boundary: `fitness_ledger_core/shared_view_models.py` powers training reference, movement insight, exports, and cloud payload preparation from the same local snapshots.
- Browser UI: `web_desktop/frontend/`; local command/read service: `web_desktop/backend/server.py`.
- Mobile viewer: `mobile_viewer/`.
- Desktop and Web confirmed daily saves use the same command service and desktop parser.
- Raw daily input is preserved; structured records can be repaired without deleting source text.

## Durable Product Behavior

- Daily free-form input is parsed, reviewed, then explicitly saved.
- Movement aliases resolve through a formal movement dictionary.
- Adding an alias scans active historical skipped movements and restores matching sets and notes into the formal movement history.
- Disabling a movement preserves aliases and history and still permits matching records to be stored, while hiding that movement from desktop/Web Movement Progress and active mapping choices.
- Body, Diet, Training, Movement Progress, and Data Check provide record inspection and correction paths.
- Web daily entry supports editable Review, duplicate-date modes, movement add/map/skip decisions, and paired database/dictionary Undo through the shared command service.
- Web Data Check now uses the desktop rule set, existing acknowledgement state, and direct repair routes instead of sample issues.
- Training places five body-area controls directly on the Training Records first screen. Each control changes the current page in place, filters matching real sessions, and synchronizes the header, atmosphere, cards, and focus panel; there is no separate reference route, generated plan, or advice.
- The accepted Training body-area controls are the compact horizontal rectangular theme cards. A later connected circular-node experiment was rejected and must not be restored unless the user explicitly requests it.
- Movement detail includes Recent 3 performance metrics and changes.
- Analysis Export produces local Markdown/JSON for 7/14/30-day or custom ranges, excluding full raw text by default.
- `cloud_sync/` builds the disposable read-only CloudBase replica; import and deployment are user-controlled. CloudBase is connected as of 2026-07-05, while local JSON remains authoritative.
- The WeChat Mini Program is an operational read-only gym reference surface. Its primary flow is Home body area -> movement signals -> full trajectory, with a separate date-first Training Records tab.
- Web Movement Dictionary supports create, rename, aliases, muscle-group/category/equipment metadata, enable/disable, and confirmed deletion.
- Web Body, Diet, and Training records are editable through the same maintained field sets as desktop; movement-history rows support structured set/order/cardio/note edits by permanent IDs.
- Dictionary uses a professional five-column functional grid; aliases and extended metadata remain available in its editor rather than occupying the main directory.
- Dictionary edits from desktop and Web use the same command service. Desktop shutdown does not rewrite stale in-memory JSON over newer Web changes.
- Duplicate dates never save silently: overwrite replaces that date's structured Body/Diet/Training and movement history while superseding old raw entries; append-training adds only another training session; cancel writes nothing.
- New movement approval requires an explicit training-area selection before dictionary creation in desktop and Web Review.
- Movement dictionary entries may set optional `pinned: true` and `focus_rank`; focused movements sort by rank before frequency and name while preserving all history. Web Dictionary is the write surface; Web Movement Index and the Mini Program are read/display surfaces.
- Web Data Check separates Details from direct Repair routing; repair opens an existing editor and never silently changes data.
- Web Export contains a deliberately quiet Cloud Sync workbench for local ten-collection package generation, validation, and post-import `fl_meta` comparison. It does not perform or claim a network upload.
- Mini Program body-area archives can switch between movement-first and training-day-first views and show cloud freshness from `fl_meta`.
- Body-area Training Day views are aggregated from movement history by date, not only from the session title. A multi-part training day appears under every body part that has a recorded movement, and the Mini Program opens the existing date-detail page.
- Web Export > Cloud Sync remains a manual CloudBase-import workbench. It reports local/cloud freshness, raw-text policy, configuration uncertainty, recent local operations, and per-collection verification. Direct upload and automatic sync are intentionally disabled until provider credentials and a verified upload path exist.
- Cloud Sync is Chinese-first and task-oriented: current mode, local/cloud dates, payload timestamp, environment ID, raw-text policy, ledgerRead/allowlist uncertainty, and automatic-sync status are shown separately from grouped local preparation, cloud checking, and help actions.
- Web formal daily-record details must never use JSON dumps. Recent Saved and date-detail surfaces render structured Body, Diet, Training, movement sets, and notes; raw source is secondary and collapsed.
- Web Movement Index is movement-first only. The movement/training-day segmented view belongs exclusively to the Mini Program training reference page.
- Mini Program training-day view preserves the selected body part and shows date, split, up to four related movement chips, a short note, and the existing date-detail route.
- Data Check repair actions reuse the existing Body/Diet/Training editors, raw-entry detail, Movement trajectory, Movement Dictionary, and Cloud Sync workbench; issue acknowledgement remains separate from repair.
- Data Check CUSTOM movement issues open Movement Dictionary with `CUSTOM_` prefilled so unstandardized entries are immediately visible; navigation never performs automatic data repair.

## Visual Direction

- Current Web direction: editorial fitness journal, warm paper surfaces, graphite ink, restrained yellow highlight, cinematic fitness imagery, tactile archive slips, and high information density without spreadsheet styling.
- The current high-availability layer adds foreground/midground/background depth, contact plus ambient shadows, inner highlights, restrained physical hover/press behavior, and reduced-motion support without changing the data architecture.
- Daily Entry uses the approved material-workbench treatment: a raised notebook writing slab, layered saved-record slips, a floating Today receipt, and restrained local-first glass status. This material pass does not alter parser, review, or save behavior.
- The reusable visual specification lives at `projects/fitness-ledger/docs/design/STYLE_BIBLE.md`.
- The complete low-token project entry is `projects/fitness-ledger/START_HERE.md`; topic routing is in `projects/fitness-ledger/docs/INDEX.md`.
- Final visual evidence and reproduction guidance live under `projects/fitness-ledger/docs/design/`.
- The accepted Web baseline includes functional Body/Diet search and ordering, Training split/date search and ordering in overview and body-area views, contextual Movement Dictionary access and return, and explicit-only record/detail actions.
- The accepted Mini Program visual translation uses one dark archive stage, five restrained body-area theme controls, tactile paper slips, compact comparison signals, and explicit expansion for long prose.
- Mini Program Home is the complete body-area archive and supports frequency/recent/name movement sorting. Training Records provides tolerant date search and newest/oldest ordering; Body and Diet remain secondary Status routes with equivalent date controls.
- The approved Mini Program theme art is stored under `projects/fitness-ledger/mini_program/miniprogram/images/themes-v2/`; reusable full-resolution versions are under `projects/fitness-ledger/web_desktop/frontend/assets/body-themes-v2/`.
- The same five-image set is now the only body-area visual authority for Web Training and Movement Progress: shoulder amber, chest coral, back teal, legs violet, and arms cyan. Web presentation darkens the artwork beneath translucent controls and applies the same asset to index and detail states.

## Recovery

- Source rollback: use Git commits and tag `fitness-ledger-web-final-2026-07-05` in `projects/fitness-ledger/`.
- Personal data rollback: use timestamped files in the local application's `data/backups/` directory.
- Copied full-project source backups and obsolete local source snapshots are no longer authoritative and were removed after the Git checkpoint was verified.
- Never replace current personal data with repository files because the public repository intentionally contains no personal JSON data.

## Review

- Next review: 2026-08-05
- Archive when the project is retired or replaced.
