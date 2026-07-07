# Fitness Ledger Documentation Index

Use this index instead of scanning the project.

## Product And Architecture

| Need | Read |
| --- | --- |
| Product purpose and supported workflows | `../PRODUCT.md`, `../FUNCTIONAL_REVIEW_BRIEF.md` |
| Current architecture and service boundaries | `../PROJECT_BOOTSTRAP.md`, `../web_desktop/ARCHITECTURE.md` |
| File and folder map | `../PROJECT_INDEX.md` |
| Function routing | `../FUNCTION_INDEX.md` |
| Safety rules | `../FITNESS_LEDGER_MAINTENANCE.md` |
| Minimum validation | `../REGRESSION_CHECKLIST.md` |

## Design

| Need | Read |
| --- | --- |
| Authoritative visual and interaction language | `design/STYLE_BIBLE.md` |
| Assets, references, tokens, and evidence | `design/DESIGN_RESOURCES.md` |
| Final approved screenshots | `design/evidence/` |
| Secondary external design reference | `../DESIGN.md` |

## Maintenance And Recovery

| Need | Read |
| --- | --- |
| Python, launchers, local paths, and dependencies | `maintenance/ENVIRONMENT.md` |
| Git source rollback and local data rollback | `maintenance/ROLLBACK.md` |
| Reusable engineering and design lessons | `maintenance/WORKFLOW_LESSONS.md` |
| Chronological changes | `../CHANGELOG.md` |
| Cloud replica truth, collections, and review | `../cloud_sync/CLOUD_REVIEW.md` |
| WeChat setup, API, UI states, and preview | `../mini_program/README.md`, `../mini_program/docs/` |

## 2026-07 Maintenance Entry

- Cloud Sync and verification: `../web_desktop/backend/server.py`, `../web_desktop/frontend/app.js`
- Focused movement ordering: `../ledger_commands.py`, `../fitness_ledger_core/cloud_payload.py`
- Body-part Training Day views: `../web_desktop/frontend/app.js`, `../mini_program/cloudfunctions/ledgerRead/index.js`, `../mini_program/miniprogram/pages/reference/`
- Acceptance steps: `../REGRESSION_CHECKLIST.md`

## Source Boundaries

- `stable_app.pyw`: desktop UI and maintained parser.
- `ledger_commands.py`: shared, UI-free write and rollback boundary.
- `fitness_ledger_core/`: shared projections, export, data quality, and cloud payload preparation.
- `web_desktop/`: browser UI and local HTTP service.
- `mobile_viewer/`: read-only phone viewer.
- `mini_program/`: WeChat read-only viewer preparation and allowlisted cloud query boundary.
- `tools/`: tests and deliberate migrations, not runtime state.

## What Is Deliberately Absent

- Personal tracker data and movement dictionary contents
- Automatic database backups
- Browser profiles and caches
- Old project snapshots
- Intermediate QA screenshots
- Raw chat transcripts
