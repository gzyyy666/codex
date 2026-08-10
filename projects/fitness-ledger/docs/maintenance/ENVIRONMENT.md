# Environment And Launch Guide

## Standardized local layout

- Git source worktree: `D:\FitnessLedger\source`
- FL source boundary: `D:\FitnessLedger\source\projects\fitness-ledger`
- Formal runtime application: `D:\FitnessLedger\app`
- Recovery and historical QA archive: `D:\FitnessLedger\archive`
- Temporary review output: `D:\FitnessLedger\work`

The source worktree is the modification and review authority. The formal
application is the only directory allowed to contain live personal JSON and
local provider configuration. Never copy `app\data\` into Git.

## Working Copy

Recommended local working path:

`D:\FitnessLedger\app`

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

The desktop shortcut and the user environment variable
`FITNESS_LEDGER_FORMAL_DIR` must both resolve to `D:\FitnessLedger\app`.
The shortcut remains a local convenience file; the Git source tree is the
repository authority.

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

## Web runtime identity

The Web header exposes a small runtime identity marker backed by `GET /api/build-info`.
In a Git Worktree preview it reads the current Worktree's read-only `HEAD`, branch,
`main`, `origin/main`, dirty state, and service start time. It never fetches or
writes Git state. The formal business directory is not a repository, so its
`web_desktop/runtime_build_info.json` deployment manifest is the only source for
formal identity; the file is intentionally Git-ignored and missing or incomplete
metadata renders `BUILD UNKNOWN` rather than inventing a published build.

The Git baseline/integration workflow may generate that manifest only after a
fresh Git audit and an explicit confirmation that the deployed commit was pushed
to `origin/main`:

```powershell
python tools/generate_runtime_build_info.py `
  --repo C:\path\to\fitness-ledger `
  --output C:\path\to\formal\web_desktop\runtime_build_info.json `
  --push-verified `
  --tag optional-release-tag
```

The tool reads real `HEAD`, `main`, and `origin/main`, writes atomically as UTF-8,
and performs no Push, Merge, Tag, data write, or formal writeback beyond the
explicit `--output` file. `PUBLISHED` is shown only when `push_verified=true`
and the recorded commit equals the recorded `origin_main_sha`; Worktree builds
always remain `PREVIEW`, including dirty previews. After deploying changed Web
code, restart the Web service so `server_started_at` identifies the new process.

## Local-Only Files

- `data/`
- `data/backups/`
- `backups/`
- `cloud_sync/out/`
- browser profiles
- generated QA screenshots
- original spreadsheets

These must not be copied into the public GitHub memory repository.

## Future-task startup contract

1. Open `D:\FitnessLedger\source` as the Codex workspace.
2. Read `projects/fitness-ledger/START_HERE.md`.
3. Run `python projects/fitness-ledger/tools/project_status.py --write --json`
   from the FL project directory.
4. For visual changes, read `docs/design/STYLE_BIBLE.md` and inspect only the
   relevant evidence under `docs/design/evidence/`.
5. Treat `D:\FitnessLedger\app\data\` as protected local state; use fixtures
   or temporary directories for tests.
