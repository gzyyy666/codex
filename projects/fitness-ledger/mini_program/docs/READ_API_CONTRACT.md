# Read API Contract

All calls use the `ledgerRead` cloud function and return either:

```json
{"ok": true, "data": {}}
```

or:

```json
{"ok": false, "code": "QUERY_FAILED", "message": "中文提示"}
```

Except for `whoami`, every action requires the caller openid in `FITNESS_LEDGER_ALLOWED_OPENIDS`.

| Action | Input | Data | Empty result | Collections |
| --- | --- | --- | --- | --- |
| `whoami` / `getOpenId` | none | `{openid, appid, env}` | Values may be empty only in invalid runtime | none |
| `status` | none | latest sync metadata | `null` | `fl_meta` |
| `latest` | none | latest daily summary | `null` | `fl_latest_summary` |
| `recent` | `limit`, `skip` | recent Body records | `[]` | `fl_daily_records` |
| `trainingReference` | optional `split` | latest eight matching sessions | `[]` | `fl_training_sessions` |
| `search` | `query` | up to 30 prepared index rows | `[]` | `fl_search_index` |
| `movement` | `movementId` | movement dictionary row | `null` | `fl_movements` |
| `movementHistory` | `movementId`, optional `limit` | recent history | `[]` | `fl_movement_history` |
| `recordDetail` | ISO `date` | Body, Diet, Training arrays | arrays may be empty | three record collections |
| `quality` | none | up to 50 read-only issues | `[]` | `fl_data_quality_issues` |

No action calls database `add`, `update`, `set`, or `remove`. Pagination is currently bounded by `limit <= 50`; the first MVP uses small lists rather than unbounded reads.
