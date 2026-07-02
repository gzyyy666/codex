# Fitness Ledger Web Desktop Architecture

## Objective

Provide browser-grade layout, typography, depth, motion, and responsive behavior without replacing the stable Python business logic or duplicating user data.

## Layers

```text
Existing data and business rules
  data/tracker.json
  data/movement_dictionary.json
  stable_app.pyw
            |
            v
Shared read model
  mobile_viewer/data_access.py
            |
            v
Web desktop service
  web_desktop/backend/server.py
            |
            v
Browser-grade UI
  web_desktop/frontend/index.html
  web_desktop/frontend/styles.css
  web_desktop/frontend/app.js
            |
            v
Windows shell
  web_desktop/launcher.pyw -> Microsoft Edge app mode
```

## Safety Boundary

Web reads continue through `LedgerDataAccess`. Daily Parse and confirmed Save now pass through `ledger_commands.py`, which shares the maintained desktop parser, validates Review decisions, creates paired checkpoints, acquires a cross-process lock, writes atomically, and rolls the dictionary back if tracker replacement fails. Request handlers never write JSON directly.

## Command Bridge

The next migration phase should expose commands rather than direct file writes:

1. `POST /api/parse` returns a pending Review payload and active movement mapping options.
2. `POST /api/save` validates the pending identity, merges only allowed edits, and runs the shared save workflow.
3. Duplicate dates require an explicit `overwrite` or `append_training` save mode.
4. `edit_record`, `undo_last_save`, and `acknowledge_data_issue` remain deferred until they can use the same command boundary.

Each command must be covered by the existing regression tests before its matching web control is enabled.

## Desktop Packaging Path

The current shell uses Microsoft Edge app mode because it requires no Electron, Rust, Node runtime, or copied browser engine. The same frontend and API can later be wrapped by Tauri without redesigning pages or changing endpoint contracts.
