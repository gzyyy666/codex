from __future__ import annotations

from datetime import datetime


SCHEMA_VERSION = "fitness-ledger-read-replica-v2"


def _date(row: dict) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _without_full_raw(row: dict) -> dict:
    return {
        key: value
        for key, value in row.items()
        if str(key).lower().replace("_", " ") not in {"raw", "raw record", "text"}
    }


def _latest_summary(data: dict) -> list[dict]:
    dates = {
        _date(row)
        for key in ("body", "diet", "training")
        for row in data.get(key, [])
        if _date(row)
    }
    if not dates:
        return []
    latest = max(dates)
    select = lambda key: [row for row in data.get(key, []) if _date(row) == latest]
    return [{
        "date": latest,
        "body": select("body")[-1] if select("body") else {},
        "diet": select("diet")[-1] if select("diet") else {},
        "training": select("training"),
    }]


def build_cloud_payload(view_models, data_quality: dict | None = None) -> dict:
    data = view_models.analysis(days=36500, include_raw_preview=False)
    _tracker, dictionary = view_models.snapshot()
    definitions = {
        str(item.get("movement_id", "")): item
        for item in dictionary.get("movements", []) or []
        if item.get("movement_id")
    }
    movements, movement_history, search_index = [], [], []
    for item in data["movements"]:
        definition = definitions.get(str(item.get("movement_id", "")), {})
        movement = {
            "movement_id": item.get("movement_id", ""),
            "display_name": item.get("display_name", ""),
            "english_name": definition.get("english_name", ""),
            "aliases": definition.get("aliases", []) or [],
            "muscle_group": item.get("muscle_group", ""),
            "category": definition.get("category", ""),
            "active": bool(definition.get("active", True)),
            "pinned": bool(definition.get("pinned", False)),
        }
        movements.append(movement)
        search_index.append({
            "type": "movement",
            "id": item["movement_id"],
            "text": " ".join(str(value) for value in (
                movement["display_name"], movement["english_name"],
                " ".join(movement["aliases"]), movement["muscle_group"],
            ) if value),
        })
        for history in item["history"]:
            movement_history.append({"movement_id": item["movement_id"], **_without_full_raw(history)})
    for row in data["body"]:
        search_index.append({
            "type": "daily", "id": row.get("id", ""), "date": row.get("Date", ""),
            "text": f"{row.get('Date','')} {row.get('Training','')} {row.get('Cardio','')} {row.get('Notes','')}",
        })
    for row in data["diet"]:
        search_index.append({
            "type": "diet", "id": row.get("id", ""), "date": row.get("Date", ""),
            "text": f"{row.get('Date','')} {row.get('Food Summary','')} {row.get('Notes','')}",
        })
    for row in data["training"]:
        search_index.append({"type": "training", "id": row.get("id", ""), "date": row.get("Date", ""), "text": f"{row.get('Split','')} {row.get('Standardized Summary','')} {row.get('Notes','')}"})
    safe_data = {
        **data,
        "body": [_without_full_raw(row) for row in data["body"]],
        "diet": [_without_full_raw(row) for row in data["diet"]],
        "training": [_without_full_raw(row) for row in data["training"]],
    }
    payload = {
        "fl_meta": [],
        "fl_latest_summary": _latest_summary(safe_data),
        "fl_daily_records": safe_data["body"], "fl_diet_records": safe_data["diet"],
        "fl_training_sessions": safe_data["training"], "fl_movements": movements,
        "fl_movement_history": movement_history, "fl_raw_entries": data["raw_entries"],
        "fl_search_index": search_index,
        "fl_data_quality_issues": list((data_quality or {}).get("issues", [])),
    }
    generated_at = datetime.now().replace(microsecond=0).isoformat()
    payload["fl_meta"] = [{
        "schema": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": "local-json",
        "sync_state": "local_payload_only",
        "raw_text_policy": "preview-disabled",
        "latest_record_date": payload["fl_latest_summary"][0]["date"] if payload["fl_latest_summary"] else "",
        "collection_counts": {name: len(rows) for name, rows in payload.items() if name != "fl_meta"},
    }]
    return payload
