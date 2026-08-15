# PWA Share Inbox Phase 3

This document describes the production-safe handoff prepared after the
candidate Review was accepted. The candidate launcher, anonymous fixture,
`share-review.html`, simulator labels, and candidate-only JSON store are not
part of the formal PWA bundle.

## User flow

1. On the phone, share a text to Fitness Ledger or paste it into `share.html`.
2. After the user confirms, the text is saved as one private pending inbox
   item.
3. On the computer, open the same authenticated PWA account and copy the
   item.
4. In the desktop Daily Entry page, use the existing “导入文字” flow.
5. Preview, edit, and confirm. Only that existing local save boundary can
   change the formal tracker or Data Module records.
6. Mark the inbox item processed, or reject it without changing formal data.

The inbox is a transport buffer, not a second ledger. It stores no parsed
record, no Data Module definition, no raw tracker backup, and no Cloud Sync
payload.

## CloudBase collection contract

Collection: `fl_web_share_inbox`

Fields written by the Web client:

- `client_id`: deterministic duplicate key for one title/text pair;
- `title`: at most 120 characters;
- `text`: at most 4,000 characters;
- `source`: `pwa_share`;
- `status`: `pending`, `copied`, `processed`, `rejected`, or `failed`;
- `received_at`, `updated_at`, `expires_at`: millisecond timestamps.

The collection must use private ownership rules before release:

```json
{
  "read": "doc._openid == auth.uid || doc._openid == auth.openid",
  "write": "doc._openid == auth.uid || doc._openid == auth.openid"
}
```

Web queries include `_openid: "{openid}"` so the database rule can validate
the query scope. The browser never sends or chooses an owner id.

## Formal release boundary

The following are intentionally absent from the formal PWA bundle:

- candidate `share-review.html`, `share-review.css`, and `share-review.js`;
- anonymous temporary tracker/registry fixtures;
- candidate Flask share-inbox endpoints;
- manual “模拟手机分享” wording;
- candidate browser launcher and candidate-only status vocabulary.

The WeChat Mini Program source and its `fl_*` read replica are unchanged.

## Cost and operations

This path adds variable usage only: one small database write when a phone item
is submitted, one read when the desktop inbox is opened/refreshed, and one
small write when an item is copied, processed, or rejected. It does not add a
permanently running server or an AI call. The actual bill depends on the
CloudBase environment plan, resource-point rules, retention volume, and use
frequency; check the environment billing page before release.

The 30-day expiry field limits retained text, but automatic deletion is not
enabled in this candidate because it would require a reviewed scheduled job.
Before release choose either manual cleanup or a separately tested scheduled
cleanup function.

## Required release evidence

- CloudBase collection exists with the private rule above;
- Web login on phone and computer resolves to the same account;
- two different accounts cannot read or update each other's items;
- repeated share of the same text is idempotent;
- no share action changes formal tracker data;
- desktop Daily Entry preview/edit/confirm still saves normally;
- physical Android/iOS share-sheet test passes, with paste fallback retained;
- current CloudBase billing plan and expected monthly volume are recorded.

No CloudBase collection, security rule, deployment, or Mini Program publish is
performed by the development branch.
