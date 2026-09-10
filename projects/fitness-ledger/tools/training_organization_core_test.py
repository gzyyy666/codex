"""Anonymous acceptance tests for Session Theme / Movement Category separation."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.record_relations import migrate_state
from fitness_ledger_core.training_organization import organization_catalog
from fitness_ledger_core.movement_target_scope import body_part_id_for_muscle_group


def run() -> None:
    database = {
        "training_sessions": [
            {
                "id": "session:morning",
                "Date": "2099-09-07",
                "No.": 1,
                "Split": "Shoulder Arms",
                "movement_items": [
                    {"id": "item:1", "movement_id": "m_shoulder", "order": 1},
                    {"id": "item:2", "movement_id": "", "name": "temporary drill", "order": 2},
                    {"id": "item:3", "movement_id": "m_arms", "order": 3},
                ],
            },
            {
                "id": "session:evening",
                "Date": "2099-09-07",
                "No.": 2,
                "Split": "Pull",
                "movement_items": [
                    {"id": "item:4", "movement_id": "m_back", "order": 1},
                    {"id": "item:5", "movement_id": "m_arms", "order": 2},
                ],
            },
        ],
        "daily_records": [{"id": "body:1", "Date": "2099-09-07"}],
        "diet_records": [],
        "movements": {},
        "raw_entries": [],
    }
    dictionary = {
        "version": "1.0",
        "movements": [
            {"movement_id": "m_shoulder", "display_name": "Press", "muscle_group": "Shoulder"},
            {"movement_id": "m_arms", "display_name": "Curl", "muscle_group": "Arms"},
            {"movement_id": "m_back", "display_name": "Row", "muscle_group": "Back"},
        ],
    }
    normalized, normalized_dictionary, report = migrate_state(database, dictionary)
    assert report["training_organization"] is True
    sessions = normalized["training_sessions"]
    assert sessions[0]["session_theme_name"] == "Shoulder Arms"
    assert sessions[1]["session_theme_name"] == "Pull"
    assert sessions[0]["session_theme_id"] != sessions[1]["session_theme_id"]
    assert sessions[0]["session_sequence"] == 1
    assert sessions[1]["session_sequence"] == 2

    first_items = sessions[0]["movement_items"]
    assert [item["order_in_session"] for item in first_items] == [1, 2, 3]
    assert [item["order_in_category"] for item in first_items] == [1, None, 1]
    assert first_items[1]["movement_category_id"] is None
    second_items = sessions[1]["movement_items"]
    assert [item["order_in_session"] for item in second_items] == [1, 2]
    assert [item["order_in_category"] for item in second_items] == [1, 1]

    catalog = organization_catalog(normalized, normalized_dictionary)
    assert {item["display_name"] for item in catalog["session_themes"]} == {"Shoulder Arms", "Pull"}
    assert all(not item["artwork_key"] and item["color_key"] for item in catalog["session_themes"])
    categories = {item["category_id"]: item for item in catalog["movement_categories"]}
    assert set(categories) >= {"chest", "shoulders", "back", "legs", "glutes", "arms", "core", "cardio"}
    assert categories["glutes"]["active"] is False
    assert categories["cardio"]["active"] is False
    assert body_part_id_for_muscle_group("Glutes") == "GLUTES"
    assert body_part_id_for_muscle_group("Cardio") == "CARDIO"

    # A session without a theme remains valid and does not invent a generic
    # catalog entry that the user did not configure.
    database["training_sessions"].append({"id": "session:un themed", "Date": "2099-09-08", "No.": 3, "movement_items": []})
    unthemed, _dictionary, _report = migrate_state(database, dictionary)
    blank = next(item for item in unthemed["training_sessions"] if item["id"] == "session:un themed")
    assert blank["session_theme_id"] == ""
    assert blank["session_theme_name"] == ""

    # A second normalization is a no-op and therefore safe for every read-only
    # projection that calls migrate_state.
    again, _again_dictionary, again_report = migrate_state(copy.deepcopy(normalized), copy.deepcopy(normalized_dictionary))
    assert again == normalized
    assert again_report["changed"] is False


if __name__ == "__main__":
    run()
    print("FITNESS_LEDGER_TRAINING_ORGANIZATION_CORE_OK")
