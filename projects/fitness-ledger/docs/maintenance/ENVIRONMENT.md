# Environment And Launch Guide

## Working Copy

Recommended local working path:

`%USERPROFILE%\Documents\Codex\2026-06-16\vs-code-ai\work\fitness_tracker_app`

The path is not a data contract. Code should resolve files relative to the project directory.

## Runtime

- Windows 10/11
- Python 3.12+; the maintained machine currently uses a standalone CPython build
- Tkinter for the desktop application
- Local HTTP service from Python standard library
- Native HTML, CSS, and JavaScript for Web; no React/Vite build step
- Edge app mode for the Web launcher

## Entry Points

- Desktop: `stable_app.pyw`
- Web: `web_desktop/launcher.pyw`
- Web service directly: `python web_desktop/backend/server.py`
- Mobile viewer: `start_mobile_viewer.py`

Desktop shortcuts are local convenience files and are not repository authority.

## Required Validation

```powershell
python -m py_compile stable_app.pyw
python -m py_compile web_desktop/backend/server.py
python tools/regression_test.py
```

Run `python tools/smoke_test.py` after parser, save, duplicate-date, dictionary, or migration changes.

For Web changes also run:

```powershell
node --check web_desktop/frontend/app.js
python tools/web_desktop_test.py
```

## Local-Only Files

- `data/`
- `data/backups/`
- `backups/`
- `cloud_sync/out/`
- browser profiles
- generated QA screenshots
- original spreadsheets

These must not be copied into the public GitHub memory repository.
