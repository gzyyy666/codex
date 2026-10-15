# Cloud Sync Guide

## Web Workbench

Open `Export` and use the quiet `Cloud Sync` entry. It can:

1. rebuild the current manifest's CloudBase import files, including configured extension collections;
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

Daily Entry also has a configuration-controlled post-save sync path: the
frontend checks `auto_sync_enabled` and provider readiness before requesting
sync. This describes source capability, not the current local switch or a
permanently running background service. Do not change that switch or add
automatic uploads to unrelated edit paths as part of documentation maintenance.

## Local Review

1. Run `python cloud_sync/build_cloud_payload.py`.
2. Inspect `cloud_sync/out/fitness_ledger_cloud_payload.json` locally and the generated per-collection `.json` files. Their content is JSON Lines for CloudBase import compatibility.
3. Run `python cloud_sync/sync_to_cloud.py --dry-run`.
4. Inspect `cloud_sync/out/fitness_ledger_cloud_sync_report.json`.

The `--dry-run` path performs no network requests. The real uploader is
intentionally opt-in through the ignored local config and should be used only
against the disposable `fl_*` replica collections.

## CloudBase Replacement Flow

1. The explicitly authorized uploader creates the manifest's actual collection payloads from the configured formal local source; ten base collections may be extended by Data Modules.
2. It clears each old disposable replica collection and inserts the complete UTF-8 JSON Lines payload.
3. It replaces old replica documents rather than merging unknown state.
4. It writes `fl_meta` last as the snapshot marker; the marker alone is not proof that every provider operation succeeded.
5. Verify every required collection's actual provider outcome/readback as well as metadata, counts, hashes, version and latest date. A local `SYNCED` result does not establish phone access/freshness.

If upload fails, inspect the verified result before retrying. Never repair formal data directly in CloudBase.
