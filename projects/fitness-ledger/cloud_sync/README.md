# Fitness Ledger Cloud Sync Preparation

This directory prepares and, when explicitly configured, updates a **read-only cloud replica**. Local JSON remains the sole source of truth.

- `build_cloud_payload.py` creates a sanitized payload in `out/`.
- `sync_to_cloud.py --dry-run` validates and reports what would be sent.
- `out/cloudbase_import/` contains one ignored import file per replica collection plus a manifest.
- The ignored `cloud_sync_config.json` can enable the reviewed Tencent CloudBase SDK provider for one-click replacement and verification.
- Credentials are read only from system environment variables; no credential is committed.
- This is one-way replacement sync, not two-way sync or conflict resolution.

Without the ignored local config, the workbench remains in safe manual-import mode.

Generated payloads may contain personal fitness data and are intentionally ignored by Git.
