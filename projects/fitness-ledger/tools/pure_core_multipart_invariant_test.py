"""Regression checks for multi-body-part dataset and relationship expansion."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.pure_core_export import PureCoreExportCompiler


class FixtureViews:
    def snapshot(self) -> tuple[dict, dict]:
        dictionary_rows = [
            {"movement_id": "chest_press", "display_name": "胸部推举", "muscle_group": "Chest"},
            {"movement_id": "back_pull", "display_name": "背部下拉", "muscle_group": "Back"},
            {"movement_id": "shoulder_press", "display_name": "肩部推举", "muscle_group": "Shoulder"},
            {"movement_id": "arms_curl", "display_name": "手臂弯举", "muscle_group": "Arms"},
            {"movement_id": "legs_press", "display_name": "腿部推举", "muscle_group": "Legs"},
            {"movement_id": "core_crunch", "display_name": "核心卷腹", "muscle_group": "Core"},
        ]
        histories = {
            row["movement_id"]: {
                "history": [{"date": "2026-07-20", "sets": [{"weight_kg": 1, "reps": 1}]}]
            }
            for row in dictionary_rows
        }
        tracker = {
            "daily_records": [{"date": "2026-07-30", "weight_kg": 80}],
            "diet_records": [],
            "training_sessions": [],
            "movements": histories,
        }
        return tracker, {"movements": dictionary_rows}


def datasets(output) -> list[dict]:
    return [dataset for request in output.requests for dataset in request["datasets"]]


def assert_relationship_targets_stay_in_batch(output) -> None:
    for request in output.requests:
        ids = {dataset["dataset_id"] for dataset in request["datasets"]}
        for dataset in request["datasets"]:
            target = dataset.get("time_range", {}).get("target_dataset_id")
            if target:
                assert target in ids, (target, ids)


def run() -> None:
    compiler = PureCoreExportCompiler(FixtureViews())

    two_parts = compiler.compile("分别导出胸部和腿部最近2次训练前1天到训练当天的饮食及训练记录。")
    assert two_parts.status == "ready"
    assert len(datasets(two_parts)) == 4
    assert len(two_parts.plan["relationship_specs"]) == 2
    assert {item["filters"].get("body_part") for item in datasets(two_parts) if item["type"] == "training"} == {"胸", "腿"}
    assert "MULTI_BODY_PART_DATASET_EXPANSION_V1" in two_parts.plan["applied_rule_ids"]

    training_only = compiler.compile("分别导出胸部、背部和肩部最近3次训练记录。")
    assert training_only.status == "ready"
    assert len(datasets(training_only)) == 3
    assert [item["filters"]["body_part"] for item in datasets(training_only)] == ["胸", "背", "肩"]

    name_catalog = compiler.compile("列出胸部和背部所有动作名称。")
    assert name_catalog.status == "candidate_confirmation_required"
    assert {item["body_part"] for item in name_catalog.candidates} == {"Chest", "Back"}

    six_parts = compiler.compile("分别导出胸部、背部、肩部、手臂、腿部和核心最近2次训练前2天的饮食及训练记录。")
    assert six_parts.status == "ready"
    assert len(datasets(six_parts)) == 12
    assert [len(request["datasets"]) for request in six_parts.requests] == [8, 4]
    assert len(six_parts.plan["relationship_specs"]) == 6
    assert_relationship_targets_stay_in_batch(six_parts)

    excludes_day = compiler.compile("导出胸部和腿部最近2次训练前2天的饮食，不包含训练当天。")
    assert all(
        item["time_range"]["include_target_session_day"] is False
        for item in datasets(excludes_day)
        if item["type"] == "diet"
    )

    target_day = compiler.compile("导出胸部和腿部上一次训练当天的饮食及训练记录。")
    assert target_day.status == "ready"
    assert len(datasets(target_day)) == 4
    assert all(
        item["time_range"]["mode"] == "target_session_day"
        for item in datasets(target_day)
        if item["type"] == "diet"
    )

    order = compiler.compile("导出腿部、胸部和背部最近训练记录。")
    assert [item["filters"]["body_part"] for item in datasets(order)] == ["腿", "胸", "背"]

    aliases = compiler.compile("导出胸部和胸最近训练记录。")
    assert len(datasets(aliases)) == 1

    single_part = compiler.compile("导出肩部最近2次训练前1天的饮食。")
    assert single_part.status == "ready"
    assert len(datasets(single_part)) == 2
    assert len(single_part.plan["relationship_specs"]) == 1

    unaffected = compiler.compile("导出最近7天身体和饮食数据。")
    assert unaffected.status == "ready"
    assert [item["type"] for item in datasets(unaffected)] == ["body", "diet"]

    complete_recent = compiler.compile("导出胸部推举最近5次的完整成长记录。")
    assert complete_recent.status == "ready"
    assert datasets(complete_recent)[0]["time_range"] == {"mode": "latest_matching_sessions", "sessions": 5}
    assert datasets(complete_recent)[0]["fields"] == [
        "date", "movement_id", "movement_name", "body_part", "variant", "order", "sets"
    ]

    scoped_and_all = compiler.compile("导出最近7天饮食，以及背部下拉从有记录以来的全部成长记录。")
    scoped_items = datasets(scoped_and_all)
    assert next(item for item in scoped_items if item["type"] == "diet")["time_range"] == {"mode": "recent_days", "days": 7}
    assert next(item for item in scoped_items if item["type"] == "movement_progress")["time_range"]["mode"] == "explicit_range"

    explicit_sessions_win = compiler.compile("导出胸部推举最近4次的全部成长记录。")
    assert datasets(explicit_sessions_win)[0]["time_range"] == {"mode": "latest_matching_sessions", "sessions": 4}

    print("PURE_CORE_MULTIPART_INVARIANTS_OK: 13")


if __name__ == "__main__":
    run()
