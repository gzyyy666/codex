# Cloud Sync Guide

## Web Workbench

Open `Export` and use the quiet `Cloud Sync` entry. It can:

1. rebuild all ten CloudBase import files;
2. validate collection structure and counts locally;
3. show the exact import directory;
4. compare an imported/exported `fl_meta` row after manual CloudBase import.

The workbench does not perform a network upload. This is deliberate: no CloudBase management credential is stored by the project, and local JSON remains the only writable source of truth.

## Local Review

1. Run `python cloud_sync/build_cloud_payload.py`.
2. Inspect `cloud_sync/out/fitness_ledger_cloud_payload.json` locally and the generated per-collection `.json` files. Their content is JSON Lines for CloudBase import compatibility.
3. Run `python cloud_sync/sync_to_cloud.py --dry-run`.
4. Inspect `cloud_sync/out/fitness_ledger_cloud_sync_report.json`.

The current implementation performs no network requests. A real CloudBase uploader must not be enabled until the user reviews the database environment and payload.

## Future CloudBase Replacement Flow

1. Create the ten collections from `CLOUD_REVIEW.md`.
2. Clear each old disposable replica collection and import the complete UTF-8 JSON Lines file in Insert mode.
3. Replace old replica documents rather than merging unknown state.
4. Write `fl_meta` last so its timestamp means the replacement completed.
5. Verify collection counts in the console against `fl_meta.collection_counts`.

If upload fails, leave the previous cloud replica in place, correct the local cause, rebuild, and retry. Never repair formal data directly in CloudBase.
