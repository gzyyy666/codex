# Cloud Sync Guide

## Web Workbench

Open `Export` and use the quiet `Cloud Sync` entry. It can:

1. rebuild all ten CloudBase import files;
2. validate collection structure and counts locally;
3. show the exact import directory;
4. compare an imported/exported `fl_meta` row after manual CloudBase import.

When the ignored local `cloud_sync_config.json` is present and the Tencent Cloud
credentials are available through the configured system environment variables,
the workbench's **执行自动同步** action performs the full network flow:
build the payload from the formal local data directory, replace the read-only
replica collections, write `fl_meta` last, and verify the payload hash and
collection hashes. No credential is stored in Git, and local JSON remains the
only writable source of truth.

On a fresh checkout without that local configuration, the same page safely
falls back to manual import mode. It will generate and validate the payload but
will not write to CloudBase.

## Local Review

1. Run `python cloud_sync/build_cloud_payload.py`.
2. Inspect `cloud_sync/out/fitness_ledger_cloud_payload.json` locally and the generated per-collection `.json` files. Their content is JSON Lines for CloudBase import compatibility.
3. Run `python cloud_sync/sync_to_cloud.py --dry-run`.
4. Inspect `cloud_sync/out/fitness_ledger_cloud_sync_report.json`.

The `--dry-run` path performs no network requests. The real uploader is
intentionally opt-in through the ignored local config and should be used only
against the disposable `fl_*` replica collections.

## CloudBase Replacement Flow

1. The one-click uploader creates the ten collection payloads from the formal local source.
2. It clears each old disposable replica collection and inserts the complete UTF-8 JSON Lines payload.
3. It replaces old replica documents rather than merging unknown state.
4. It writes `fl_meta` last so its timestamp means the replacement completed.
5. It reads `fl_meta` back and verifies counts, hashes, version, and latest date.

If upload fails, inspect the verified result before retrying. Never repair formal data directly in CloudBase.
