# Cloud Data Contract

Schema: `fitness-ledger-read-replica-v2`

The authoritative contract is the output of `fitness_ledger_core.cloud_payload.build_cloud_payload`. It contains ten base collections documented in `CLOUD_REVIEW.md`.

When a local Data Module definition store is explicitly configured, the same
payload may add three sanitized extension collections: `fl_data_modules`,
`fl_data_module_records`, and `fl_data_module_contract`. The extension is
additive; with no configured registry the ten-collection payload is retained.
`fl_data_module_contract` is the compact read-only mobile projection shared by
the WeChat client and the phone home-screen PWA. The PWA Web gateway may prefer
the full sanitized module and record collections so its dated archive is not
limited by the compact contract history window. None of these views contains
raw input, private fields, notes, or source hashes, and neither client writes
these collections.

## Guarantees

- The replica is generated from the shared local projection layer.
- Collection values are arrays of JSON objects.
- `fl_meta` contains schema, generation time, source, sync state, latest record date, raw text policy, and collection counts.
- `fl_movements` contains names, aliases, body area, category, and active state.
- `fl_raw_entries.preview` is empty unless a future explicit opt-in changes the policy.
- The replica is disposable and must never become an editable primary database.
- Mini program and cloud functions must not reproduce parser or migration logic.

## Replacement Strategy

The first CloudBase release replaces each replica collection from a complete validated payload, then writes `fl_meta` last. Incremental or two-way synchronization is intentionally unsupported.
