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
| `movementCatalog` | none | active movement names, aliases, IDs, and body-part metadata | `[]` | `fl_movements` |
| `movementHistory` | `movementId`, optional `limit` | recent history | `[]` | `fl_movement_history` |
| `trainingDayDetail` | ISO `date` (`YYYY-MM-DD`) | one read-only training-day projection | `session: null`, `movements: []` | `fl_training_sessions`, `fl_movement_history`, `fl_movements` |
| `recordDetail` | ISO `date` | Body, Diet, Training arrays | arrays may be empty | three record collections |
| `dataModules` | none | Sanitized Data Module contract for read-only rendering | valid empty contract | `fl_data_module_contract` or `fl_data_modules`, `fl_data_module_records` |
| `quality` | none | up to 50 read-only issues | `[]` | `fl_data_quality_issues` |

No action calls database `add`, `update`, `set`, or `remove`. Pagination is currently bounded by `limit <= 50`; the first MVP uses small lists rather than unbounded reads.

## `dataModules`

The action returns `fitness-ledger-mini-module-contract-v1`. It contains only
modules explicitly enabled for Mini reading, their latest value, and bounded
history. Body and Diet archive pages place matching records inside the same
date slip as the formal record; the Status page can show modules configured as
the lightweight home widget. No new Mini page is created and no new record is
writable from the Mini Program. If the extension collections have not yet
been deployed, the action returns an empty valid contract so existing pages
continue to work.

## `movementCatalog`

This is a read-only catalog for local UI candidate matching. It returns active
movement definitions even when the movement has no history yet. The catalog
contains `movement_id`, `display_name`, `english_name`, `aliases`,
`muscle_group`, and derived `body_parts`. It does not return training history,
and the Mini Program never writes a candidate back as a formal record.

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
