# Fitness Ledger Cloud Sync Preparation

This directory prepares a **read-only cloud replica**. Local JSON remains the sole source of truth.

- `build_cloud_payload.py` creates a sanitized payload in `out/`.
- `sync_to_cloud.py --dry-run` validates and reports what would be sent.
- `out/cloudbase_import/` contains one ignored import file per replica collection plus a manifest.
- No provider, credentials, network writes, two-way sync, or conflict resolution are configured.

Generated payloads may contain personal fitness data and are intentionally ignored by Git.
