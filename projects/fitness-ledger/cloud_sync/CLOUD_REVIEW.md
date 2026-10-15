# Cloud Review: Current Truth

## Configuration and evidence boundary

- A fresh checkout contains no provider credentials or environment binding.
- Source supports dry-run preparation and an explicitly configured one-way
  uploader; absence of configuration in Git does not establish formal runtime
  or provider state.
- For an operational task, inspect current local status and scoped provider
  results. This document does not assert that a provider is presently connected,
  disconnected, uploaded or verified.
- Local formal `data/tracker.json` and `data/movement_dictionary.json` remain
  authoritative. See `CLOUD_SYNC_GUIDE.md` for the scoped workflow.

The generated payload is stored at `cloud_sync/out/fitness_ledger_cloud_payload.json` and is ignored by Git because it contains personal fitness data.

## Replica Collections

The table lists ten base collections. A configured Data Module registry can
add `fl_data_modules`, `fl_data_module_records` and `fl_data_module_contract`;
use the generated manifest and `CLOUD_DATA_CONTRACT.md` for the actual package.

| Collection | Purpose | Mini program | Mutability |
| --- | --- | --- | --- |
| `fl_meta` | Schema, generation time, counts, latest date, sync state | Yes | Read-only replica |
| `fl_latest_summary` | Latest Body, Diet, and Training summary | Yes | Read-only replica |
| `fl_daily_records` | Body records | Yes | Read-only replica |
| `fl_diet_records` | Diet records | Yes | Read-only replica |
| `fl_training_sessions` | Training sessions | Yes | Read-only replica |
| `fl_movements` | Sanitized movement dictionary | Yes | Read-only replica |
| `fl_movement_history` | Structured movement history | Yes | Read-only replica |
| `fl_search_index` | Prepared searchable text | Yes | Read-only replica |
| `fl_raw_entries` | IDs, dates, and disabled previews by default | Detail reference only | Read-only replica |
| `fl_data_quality_issues` | Unacknowledged local Data Check results | Status only | Read-only replica |

## Review Commands

```powershell
python cloud_sync/build_cloud_payload.py
python cloud_sync/sync_to_cloud.py --dry-run
```

Inspect the generated JSON and `fitness_ledger_cloud_sync_report.json` locally.
The `--dry-run` report must state `network_request_made: false`; it does not
prove network upload or phone freshness. Do not upload payloads as review artifacts.

## Maintenance Rule

Never correct the replica manually. Correct local data through the maintained desktop or Web application, rebuild the payload, replace the cloud collections, then verify `fl_meta.generated_at` and collection counts.
