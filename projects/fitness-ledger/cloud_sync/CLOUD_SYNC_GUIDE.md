# Cloud Sync Guide

1. Run `python cloud_sync/build_cloud_payload.py`.
2. Inspect `cloud_sync/out/fitness_ledger_cloud_payload.json` locally.
3. Run `python cloud_sync/sync_to_cloud.py --dry-run`.
4. Only after choosing a provider should a separate authenticated uploader be added.

Current implementation performs no network requests and writes only to `cloud_sync/out/`.
