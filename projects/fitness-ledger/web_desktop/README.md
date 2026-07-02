# Fitness Ledger Web Desktop

## Premium UI preview

The browser shell now implements the approved seven-screen dark product system across Quick Entry, Parse & Review, Body, Diet, Training, Movement Progress, Data Check, record editors, detail layers, duplicate-date handling, and movement approval.

Real local data is loaded through the existing read-only API. Parse, save, edit, undo, approval, and destructive actions are visual interaction previews only; the stable desktop application remains the sole write-capable application.

This is the browser-grade desktop UI foundation. It runs beside the stable Tkinter program and reads the same local database.

## Current Phase

- Real local Body, Diet, Training, Movement, status, recent records, search, and detail data.
- Browser-grade responsive layout, surfaces, shadows, blur, focus, hover, and page transitions.
- Read-only API boundary.
- Existing Tkinter program remains the only write-capable application.

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
- Do not enable Parse, Save, Edit, Undo, or Data Check commands until their bridge uses the existing backup and atomic-save paths.
