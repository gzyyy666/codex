# Fitness Ledger Web Desktop

## Premium UI preview

The browser shell now implements the approved seven-screen dark product system across Quick Entry, Parse & Review, Body, Diet, Training, Movement Progress, Data Check, record editors, detail layers, duplicate-date handling, and movement approval.

Real local data is loaded through the existing read model. Parse/Review/Save, record editing, Undo, movement approval, Data Check acknowledgement, and other enabled actions cross the shared `ledger_commands.py` boundary; the frontend never writes JSON directly.

This is the browser-grade desktop UI foundation. It runs beside the stable Tkinter program and reads the same local database.

## Current Phase

- Real local Body, Diet, Training, Movement, status, recent records, search, and detail data.
- Browser-grade responsive layout, surfaces, shadows, blur, focus, hover, and page transitions.
- Shared read model plus command-backed local write boundary.
- The Tkinter program and Web service are both clients of the shared command service; local JSON remains protected by its lock, checkpoints, atomic writes, and rollback rules.

## Run

```text
python web_desktop/launcher.pyw
```

For service diagnostics:

```text
python -m web_desktop.backend.server
```

Then open `http://127.0.0.1:8766`.

## Do Not Do

- Do not write directly to `data/tracker.json` from JavaScript.
- Do not reimplement parser rules in the frontend.
- Do not add a Web write path that bypasses the existing command service, paired checkpoints, atomic-save, rollback, or Review identity checks.
