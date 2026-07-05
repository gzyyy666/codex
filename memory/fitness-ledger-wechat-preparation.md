---
title: Fitness Ledger WeChat read-only deployment state
status: active
updated: 2026-07-05
project: fitness-ledger
tags: [wechat, cloudbase, read-only, cloud-replica]
---

# Fitness Ledger WeChat Deployment State

## Current Truth

- The WeChat AppID, CloudBase environment, replica collections, `ledgerRead` deployment, and OpenID allowlist have been configured by the user.
- The read chain is operational in WeChat DevTools as of 2026-07-05.
- Local JSON remains the sole source of truth.
- The prepared cloud contract is `fitness-ledger-read-replica-v2` with ten read-only collections.
- Full raw text is excluded by default.
- `fl_data_quality_issues` may remain an empty collection; no zero-byte import file is required.

## Prepared Assets

- `projects/fitness-ledger/cloud_sync/`: payload builder, per-collection import files, contract, review guide, and no-network report.
- `projects/fitness-ledger/mini_program/`: maintained gym-side read-only Mini Program with eight registered pages.
- `mini_program/cloudfunctions/ledgerRead`: one OpenID-allowlisted cloud function containing read operations only.
- Setup, API contract, UI states, preview checklist, and automated structural tests are included.

## Mobile Product Flow

- Home is the complete five-body-area training archive instead of a weight/calorie dashboard.
- Training Records is a primary bottom-tab destination with tolerant date search and newest/oldest ordering.
- Selecting shoulder, chest, back, legs, or arms loads movement frequency, latest performance, previous performance, historical best, and full trajectory links.
- Long daily food/training prose is collapsed until explicitly expanded.
- The redundant standalone Search tab was removed; movement discovery remains body-area-first.
- Home keeps all five body controls visible and supports frequency, recent-date, and movement-name ordering.
- Movement Detail promotes the latest three sessions before older history.
- Body and Diet are secondary read-only archives entered from Status and support date search plus newest/oldest ordering.
- Selected body-area pages use the approved five-image abstract theme set with matching amber/coral/teal/violet/cyan page washes.

## Deployment Steps After Code Changes

1. Redeploy `ledgerRead` when its `index.js` changes.
2. Compile the Mini Program in WeChat DevTools.
3. Verify Home body-area counts, open one movement trajectory, and confirm the matching theme illustration.
4. Verify Training Records, Body, and Diet date filtering plus order switching.
5. Perform real-device review before uploading for audit.

## Recovery Prompt

```text
Continue Fitness Ledger WeChat read-only client maintenance.
Read projects/fitness-ledger/START_HERE.md, memory/fitness-ledger-wechat-preparation.md,
projects/fitness-ledger/cloud_sync/CLOUD_REVIEW.md, and projects/fitness-ledger/mini_program/README.md.
CloudBase is connected, but keep the Mini Program read-only and local JSON authoritative.
Never commit env.local.js, OpenIDs, generated cloud payloads, or personal records.
```
