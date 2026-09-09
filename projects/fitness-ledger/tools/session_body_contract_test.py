"""Focused contract checks for the released Session Theme and Body modules."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web_desktop.backend.server import LedgerWebService  # noqa: E402


def module(module_id: str, label: str, aliases: list[str], order: int) -> dict:
    return {
        "module_id": module_id,
        "label": label,
        "aliases": aliases,
        "category_id": "body",
        "data_type": "text",
        "actual_unit": "",
        "display_unit": "",
        "definition_version": 1,
        "status": "active",
        "capabilities": {
            "recordable": True,
            "queryable": True,
            "history_enabled": True,
            "exportable": True,
            "analysis_visible": True,
            "statistics_visible": False,
            "cloud_syncable": True,
            "mini_program_visible": True,
        },
        "validation_contract": {"max_length": 2000},
        "recording_behavior": {"kind": "scalar", "cardinality": "one_per_day"},
        "presentation": {"section": "body", "slot": "top", "order": order, "visible_by_default": True, "renderer": "single_metric"},
        "legacy_source": {
            "collection": "daily_records",
            "date_field": "Date",
            "value_field": "Bowel Movement" if module_id.endswith("bowel_movement") else "Cardio",
            "review_field": "body.bowel_movement" if module_id.endswith("bowel_movement") else "body.cardio_summary",
        },
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-session-body-") as temp:
        root = Path(temp)
        tracker = root / "tracker.json"
        dictionary = root / "movement_dictionary.json"
        registry = root / "data_module_definitions.json"
        write_json(tracker, {
            "daily_records": [{"id": "body:old", "Date": "2026-09-01", "Weight (kg)": 70, "Bowel Movement": "正常", "Cardio": "步行", "Notes": "保留"}],
            "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": [], "data_module_records": [],
        })
        write_json(dictionary, {"version": "1.0", "movements": []})
        write_json(registry, {"schema": "fitness-ledger-data-module-definition-store-v1", "categories": [{"category_id": "body", "label": "Body", "order": 10, "status": "active", "system": True, "presentation": {"template": "core"}}], "modules": [module("body_bowel_movement", "排便", ["排便", "bowel"], 30), module("body_cardio", "有氧", ["有氧", "cardio"], 40)]})
        service = LedgerWebService(tracker, dictionary, root / "backups", data_module_registry_file=registry)

        old_bowel = service.commands.data_module_query("body_bowel_movement")[0]
        assert old_bowel["value"] == "正常" and old_bowel["legacy_projection"] is True
        payload = service.parse_entry("2026-09-02\n体重: 70\n排便: 正常\n有氧: 跑步 30 分钟")
        ids = {item["module_id"] for item in payload["review"]["data_modules"]["candidates"]}
        assert ids == {"body_bowel_movement", "body_cardio"}
        result = service.save_review({"review_id": payload["review_id"], "review": payload["review"]})
        assert result["ok"] is True
        saved = json.loads(tracker.read_text(encoding="utf-8"))
        new_day = next(row for row in saved["daily_records"] if row["Date"] == "2026-09-02")
        assert new_day["Bowel Movement"] == "正常" and new_day["Cardio"] == "跑步 30 分钟"
        assert {row["module_id"] for row in saved["data_module_records"]} == {"body_bowel_movement", "body_cardio"}

        created = service.commands.update_session_theme({"display_name": "Pull", "pinned": True})
        assert created["theme"]["pinned"] is True and created["theme"]["focus_rank"] == 1
        second = service.commands.update_session_theme({"display_name": "Full Body", "pinned": True})
        assert second["theme"]["focus_rank"] == 1
        catalog = service.commands.training_organization()["session_themes"]
        assert next(item for item in catalog if item["display_name"] == "Pull")["focus_rank"] == 2
        disabled = service.commands.set_session_theme_active(second["theme"]["theme_id"], False)
        assert disabled["theme"]["active"] is False


if __name__ == "__main__":
    run()
    print("FITNESS_LEDGER_SESSION_BODY_CONTRACT_OK")
