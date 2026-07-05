# Fitness Ledger Project Context

Fitness Ledger is a single-user, local-first fitness journal. It records free-form daily notes, preserves raw text, and produces structured Body, Diet, Training, Cardio, Movement, and Data Check views.

## Current Surfaces

- Tkinter desktop application for the complete local workflow.
- Browser-grade local Web application with shared Parse/Review/Save, editing, dictionary management, export, and data-quality actions.
- Read-only mobile viewer for phone access on the local network.

## Current Architecture

- `stable_app.pyw`: maintained parser and desktop presentation.
- `ledger_commands.py`: safe shared command boundary.
- `fitness_ledger_core/`: shared projections and analysis/export helpers.
- `web_desktop/`: local Web service and frontend.
- `mobile_viewer/`: read-only mobile surface.
- local `data/`: sole personal-data authority.

## Core Guarantees

- Raw daily text is preserved.
- Tracker and movement dictionary writes are atomic and checkpointed.
- Movement identity uses permanent IDs and aliases.
- Duplicate dates require an explicit overwrite/append/cancel decision.
- Disabled movements remain recordable but are hidden from active growth views.
- Repository source contains no personal database.

For task routing use `START_HERE.md` and `docs/INDEX.md` rather than this summary.
