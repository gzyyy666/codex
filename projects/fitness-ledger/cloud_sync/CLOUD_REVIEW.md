# Cloud Review: Current Truth

## Current State

- Provider: not configured
- CloudBase environment: not configured
- Real cloud database writes: none
- Available artifact: local sanitized payload only
- Sync mode: dry-run validation only
- Source of truth: `data/tracker.json` and `data/movement_dictionary.json`

The generated payload is stored at `cloud_sync/out/fitness_ledger_cloud_payload.json` and is ignored by Git because it contains personal fitness data.

## Replica Collections

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

Inspect the generated JSON and `fitness_ledger_cloud_sync_report.json`. A valid report must state `network_request_made: false` until CloudBase deployment is explicitly configured.

## Maintenance Rule

Never correct the replica manually. Correct local data through the maintained desktop or Web application, rebuild the payload, replace the cloud collections, then verify `fl_meta.generated_at` and collection counts.
