from __future__ import annotations

from datetime import datetime


def build_cloud_payload(view_models) -> dict:
    data = view_models.analysis(days=36500, include_raw_preview=False)
    movements, movement_history, search_index = [], [], []
    for item in data["movements"]:
        movements.append({key: item.get(key) for key in ("movement_id", "display_name", "muscle_group")})
        search_index.append({"type": "movement", "id": item["movement_id"], "text": f"{item['display_name']} {item['muscle_group']}"})
        for history in item["history"]:
            movement_history.append({"movement_id": item["movement_id"], **history})
    for row in data["training"]:
        search_index.append({"type": "training", "id": row.get("id", ""), "date": row.get("Date", ""), "text": f"{row.get('Split','')} {row.get('Standardized Summary','')} {row.get('Notes','')}"})
    return {
        "fl_meta": [{"schema": "fitness-ledger-read-replica-v1", "generated_at": datetime.now().replace(microsecond=0).isoformat(), "source": "local-json"}],
        "fl_daily_records": data["body"], "fl_diet_records": data["diet"],
        "fl_training_sessions": data["training"], "fl_movements": movements,
        "fl_movement_history": movement_history, "fl_raw_entries": data["raw_entries"],
        "fl_search_index": search_index,
    }
