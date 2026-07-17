# Cloud Data Contract

Schema: `fitness-ledger-read-replica-v2`

The authoritative contract is the output of `fitness_ledger_core.cloud_payload.build_cloud_payload`. It contains eleven collections documented in `CLOUD_REVIEW.md`.

## Guarantees

- The replica is generated from the shared local projection layer.
- Collection values are arrays of JSON objects.
- `fl_meta` contains schema, generation time, source, sync state, latest record date, raw text policy, and collection counts.
- `fl_movements` contains names, aliases, body area, category, and active state.
- `fl_custom_metrics` contains generic metric_id, label, unit, number format, status, date/value rows, and placement locations. It is optional; an empty collection is valid for legacy trackers.
- `fl_raw_entries.preview` is empty unless a future explicit opt-in changes the policy.
- The replica is disposable and must never become an editable primary database.
- Mini program and cloud functions must not reproduce parser or migration logic.

## Replacement Strategy

The first CloudBase release replaces each replica collection from a complete validated payload, then writes `fl_meta` last. Incremental or two-way synchronization is intentionally unsupported.
