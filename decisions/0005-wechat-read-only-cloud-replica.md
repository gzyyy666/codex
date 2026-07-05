# 0005: WeChat Uses An Allowlisted Read-Only Cloud Replica

Date: 2026-07-05

## Decision

The first WeChat Mini Program reads a disposable CloudBase replica through one OpenID-allowlisted cloud function. It does not parse, edit, save, undo, maintain the dictionary, or write to any collection.

## Reason

Fitness Ledger is a single-user local-first archive. Keeping formal writes in the maintained desktop/Web command boundary avoids duplicated parsing, cloud conflicts, and accidental remote replacement of local data.

## Consequences

- Local JSON remains authoritative.
- The complete cloud payload replaces replica collections; `fl_meta` is written last.
- Full raw text is excluded by default.
- CloudBase setup, import, allowlist, and real-device preview remain explicit deployment steps.
