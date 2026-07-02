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

The foundation phase is intentionally read-only. `POST` requests return `501 Not Implemented`. This prevents the web prototype from bypassing backups, review decisions, duplicate-date handling, movement approval, or atomic JSON writes.

## Command Bridge Plan

The next migration phase should expose commands rather than direct file writes:

1. `parse_entry(raw_text)` returns an immutable review payload.
2. `confirm_review(review_payload, decisions)` invokes the existing save workflow.
3. `edit_record(record_type, id, patch)` invokes the existing backup and atomic write path.
4. `undo_last_save()` restores the existing paired checkpoint.
5. `acknowledge_data_issue(issue_key)` reuses the existing Data Check state file.

Each command must be covered by the existing regression tests before its matching web control is enabled.

## Desktop Packaging Path

The current shell uses Microsoft Edge app mode because it requires no Electron, Rust, Node runtime, or copied browser engine. The same frontend and API can later be wrapped by Tauri without redesigning pages or changing endpoint contracts.
