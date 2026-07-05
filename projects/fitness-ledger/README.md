# Fitness Ledger

Local Windows desktop tracker for body data, diet, training sessions, and movement progress.

The project also includes a browser UI, a sanitized cloud-replica preparation layer, and a WeChat read-only viewer skeleton. CloudBase is not connected until an AppID, env_id, collections, and OpenID allowlist are configured explicitly.

## Current entry workflow

1. Paste one natural-language daily record into `Quick Entry`.
2. Click `Parse & review`.
3. Check the extracted body data, macros, training split, movements, loads, repetitions, and sets.
4. Click `Confirm & save`.

The original text is always preserved in `data/tracker.json`.

## Current views

- `Body`: Date, Weight, Context, Training, Cardio, and Notes.
- `Diet`: wide macro and food table; double-click a row for full details.
- `Training`: wide raw and standardized record table; double-click for full details.
- `Movement Progress`: movements on rows, dates on columns, and training details in cells.

## Data safety

- Main database: `data/tracker.json`
- Automatic backups: `data/backups/`
- Imported historical source: `data/history_import.json`
- The original desktop Excel workbook is not modified by the app.
