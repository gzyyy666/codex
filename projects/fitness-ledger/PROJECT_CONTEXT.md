# Fitness Ledger Project Context

> This file contains durable product context, not a live Git or deployment baseline. At task startup use `python tools/project_status.py --write --json`, then follow `AGENTS.md` and `START_HERE.md`. Historical notes below must not override the live status or current source.

## Current App

- Main program: `stable_app.pyw`
- Desktop shortcut: `<USER_DESKTOP>\Fitness Ledger.lnk`
- Main database: `data/tracker.json`
- Automatic backups: `data/backups/`
- Historical workbook extraction: `data/history_import.json`
- Original workbook remains external and is not modified.

## Current Features

- Natural-language daily input with a review-before-save step.
- Body data extraction: date, weight, body fat, waist, sleep, steps, and measurement context.
- Diet extraction: food summary, calories, protein, carbohydrates, and fat.
- Training extraction: split, movement order, weight, repetitions, sets, and cardio parameters.
- Historical movement-name matching through English and Chinese aliases.
- New movement creation when no existing movement matches.
- Simplified Body page focused on weight, context, training, cardio, and notes.
- Wide Diet and Training tables with horizontal scrolling and double-click details.
- Movement Matrix with movements as rows and ascending dates as columns.
- Movement search filters rows without changing matrix date columns.
- Original raw text retention for audit and later correction.

## Mini Program baseline

- The WeChat Mini Program is a read-only gym reference client backed by the
  CloudBase replica; local formal JSON remains authoritative.
- The accepted freeform Training Note is local-only and stored under
  `fitness-ledger:freeform-notepad:v2:current-training`; it is not a formal
  record and is not uploaded to CloudBase.
- Training Reference has an inline editor and a scroll-revealed collapsible
  Dock. Both persist while typing. On tab/page changes, the page must refresh
  from Storage rather than write a stale page mirror over a newer Dock edit.
- Accepted front-end build marker for the current candidate-history build:
  `v2026.08.02-action-candidates-12`.
- Training Reference can recognize movement names, English names, and aliases in
  the freeform note and show a read-only, neutral floating history panel. It uses
  `movementCatalog` for matching and `movement`/`movementHistory` for previews;
  it does not turn note text into a formal record.
- The panel is independent of the note card, keeps a fixed viewport, shows the
  latest record first, and lets the user scroll older records or collapse it to a
  narrow edge tab without interrupting typing.
- Preserve this boundary in future work; automatic action extraction, account
  sync, and Mini Program writes require a separately approved design.

## How a new task should find its place

In plain terms: read the bootstrap for the rules, the index for the file map,
the function index for data ownership, then read only the files named by the
task. Choose the smallest relevant checklist, make the change only inside the
allowed boundary, run its checks, and write a short changelog entry. The formal
business directory is for DevTools acceptance; the separate Git directory is
the durable project record and receives only the selected accepted files.

## Data Safety

- Never clear or replace `data/tracker.json` without a backup.
- Saving a confirmed daily record creates a timestamped backup first.
- Parser tests must use temporary data paths.
- Preserve the original raw text even when parser rules improve.

## Historical First-Version Notes

- The first confirmation page was read-only. The current Desktop/Web Parse & Review flow allows approved field corrections before the shared save boundary while preserving raw input.
- Movement matching uses aliases and exact normalized names, not semantic AI matching.
- The legacy Movement Matrix note is superseded by the current Movement Progress and movement-history detail flows; use current source/tests for route behavior.
- The app does not yet write changes back into the Excel workbook.
- Nutrient values are recorded from user-provided calculated totals; the app does not calculate meals automatically.
