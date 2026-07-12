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
| `trainingDayDetail` | ISO `date` (`YYYY-MM-DD`) | one read-only training-day projection | `session: null`, `movements: []` | `fl_training_sessions`, `fl_movement_history`, `fl_movements` |
| `recordDetail` | ISO `date` | Body, Diet, Training arrays | arrays may be empty | three record collections |
| `quality` | none | up to 50 read-only issues | `[]` | `fl_data_quality_issues` |

No action calls database `add`, `update`, `set`, or `remove`. Pagination is currently bounded by `limit <= 50`; the first MVP uses small lists rather than unbounded reads.

## `trainingDayDetail`

Input:

```json
{"action":"trainingDayDetail","date":"2026-07-06"}
```

The date must be ISO `YYYY-MM-DD`; an invalid value returns the existing failure envelope with `code: "INVALID_DATE"`.

The response data is:

```json
{
  "date": "2026-07-06",
  "session": {
    "id": "...",
    "date": "2026-07-06",
    "split": "肩手臂",
    "summary": "标准化摘要",
    "notes": "训练总备注"
  },
  "movements": [
    {
      "movement_id": "SHOULDER_001",
      "movement_name": "Y举",
      "english_name": "Y Raise",
      "muscle_group": "Shoulder",
      "order": 1,
      "sets": [],
      "notes": ""
    }
  ]
}
```

`session` is built from `fl_training_sessions`: its date field is `Date`, with `Split`, `Standardized Summary`, and `Notes`. Movement rows are read by the same ISO date from `fl_movement_history.date`; `movement_id`, `order`, `sets`, and `notes` are preserved without summary parsing. Names come from `fl_movements.display_name`, with `english_name` and `muscle_group` copied when present. A missing dictionary row falls back to `movement_id` as `movement_name`. Explicit `order` values sort ascending; missing values retain source order after ordered rows. No session returns `session: null`; no history returns `movements: []`.
