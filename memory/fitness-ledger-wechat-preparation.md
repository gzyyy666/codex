---
title: Fitness Ledger WeChat preparation state
status: active
updated: 2026-07-05
project: fitness-ledger
tags: [wechat, cloudbase, read-only, cloud-replica]
---

# Fitness Ledger WeChat Preparation State

## Current Truth

- No real CloudBase environment or network uploader is configured.
- Previous cloud work produced a local payload and dry-run only; it did not upload a database.
- Local JSON remains the sole source of truth.
- The prepared cloud contract is `fitness-ledger-read-replica-v2` with ten read-only collections.
- Full raw text is excluded by default.

## Prepared Assets

- `projects/fitness-ledger/cloud_sync/`: payload builder, per-collection import files, contract, review guide, and no-network report.
- `projects/fitness-ledger/mini_program/`: WeChat DevTools project skeleton with seven pages.
- `mini_program/cloudfunctions/ledgerRead`: one OpenID-allowlisted cloud function containing read operations only.
- Setup, API contract, UI states, preview checklist, and automated structural tests are included.

## User Inputs Still Required

1. WeChat Mini Program AppID.
2. CloudBase environment creation and env_id.
3. Import of the ten generated replica collections.
4. Deployment of `ledgerRead`.
5. OpenID allowlist configuration.
6. Simulator and real-device review.

## Recovery Prompt

```text
Continue Fitness Ledger WeChat deployment.
Read projects/fitness-ledger/START_HERE.md, memory/fitness-ledger-wechat-preparation.md,
projects/fitness-ledger/cloud_sync/CLOUD_REVIEW.md, and projects/fitness-ledger/mini_program/README.md.
Do not claim real cloud upload unless fl_meta is visible in the selected CloudBase environment.
Keep the Mini Program read-only and local JSON authoritative.
```
