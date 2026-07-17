# CloudBase Setup And Review

## What Exists Now

The Git mirror intentionally contains no CloudBase credentials or active environment binding. It contains the local payload builder, import-ready collection files, the read-only cloud function, and the Mini Program skeleton. A formal working directory may be configured; use the live Cloud Sync report and `project_status.py` rather than this source guide to determine whether it is connected.

## Create And Verify The Environment

1. In WeChat DevTools, import `mini_program/`.
2. Replace `touristappid` in local `project.config.json` with your AppID.
3. Open **Cloud Development** and create or select one environment.
4. Copy `miniprogram/config/env.example.js` to the ignored `env.local.js`; set the exact environment ID shown in the console.
5. Create the ten collections listed in `cloud_sync/CLOUD_REVIEW.md`.
6. Verify the selected environment name and ID before importing anything.

## Review And Import

Run `python cloud_sync/build_cloud_payload.py`, then open `cloud_sync/out/cloudbase_import/manifest.json`. In the CloudBase document-database console, clear the previous disposable replica collection and import its matching UTF-8 `.json` file using **Insert** mode. Import `fl_meta` last. Although the extension is `.json` for the file picker, the content uses JSON Lines: one complete JSON object per line.

Collections with zero rows must still follow the current importer contract: use the valid empty-collection representation emitted by the current payload builder/uploader, rather than assuming a missing file is acceptable. Verify the actual `manifest.json` and dry-run report from the current Git baseline before importing; never rely on this guide to infer an older empty-collection behavior.

After import:

1. Open `fl_meta`, check schema, generated time, latest date, and counts.
2. Sort `fl_daily_records` by `Date` descending and inspect the latest row.
3. Filter `fl_movement_history` by one `movement_id` from `fl_movements`.
4. Search `fl_search_index.text` for a known action such as `Y举`.
5. Inspect `fl_raw_entries`; `preview` must be empty under the default policy.
6. Compare every collection count with `fl_meta.collection_counts`.

## Access Control

Deploy `cloudfunctions/ledgerRead`, open the Data Status page, and copy the returned openid. Add it to the cloud function environment variable `FITNESS_LEDGER_ALLOWED_OPENIDS`. Multiple IDs are comma-separated.

After changing the allowlist, redeploy `ledgerRead` from WeChat DevTools: right-click `cloudfunctions/ledgerRead`, choose **Upload and deploy: cloud install dependencies**, wait for success, then reopen Data Status. `whoami` remains accessible without allowlist but returns identity metadata only, never Fitness Ledger records.

Do not place credentials or private keys in Mini Program JavaScript. Do not enable direct client database access; the Mini Program reads through the allowlisted cloud function only.
