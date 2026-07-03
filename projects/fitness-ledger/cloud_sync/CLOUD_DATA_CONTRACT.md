# Cloud Data Contract

Schema: `fitness-ledger-read-replica-v1`

Collections: `fl_meta`, `fl_daily_records`, `fl_diet_records`, `fl_training_sessions`, `fl_movements`, `fl_movement_history`, `fl_raw_entries`, and `fl_search_index`.

`fl_raw_entries` contains identifiers and dates only by default, not full raw text. The payload is derivative and disposable; it must never be treated as an editable primary database.
