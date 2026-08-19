"""Regression cases for the historical Daily Entry LLM prompt contract."""

from __future__ import annotations

import re
import runpy
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.data_module_engine import DataModuleEngine, ModuleDefinition, ModuleRegistry


ALLOWED_TOP_LEVEL_LABELS = {
    "date",
    "weight",
    "排便",
    "bowel",
    "calories",
    "protein",
    "carbs",
    "fat",
    "diet",
    "diet notes",
    "training",
    "training notes",
    "cardio",
    "notes",
}
CORE_ORDER = ["date", "weight", "排便", "calories", "protein", "carbs", "fat", "diet", "training", "cardio"]


def parser_fixture():
    namespace = runpy.run_path(ROOT / "stable_app.pyw")
    names = [
        "坐姿腿举",
        "深蹲",
        "坐姿腿弯举",
        "腿屈伸",
        "悬垂举腿",
        "俯身哑铃飞鸟",
        "侧平举",
        "引体向上",
        "诺德士拉背拨片",
    ]
    dictionary = {
        "movements": [
            {"movement_id": f"PROMPT_{index:03d}", "display_name": name, "aliases": [name], "active": True}
            for index, name in enumerate(names, 1)
        ]
    }
    app = namespace["FitnessTrackerApp"].__new__(namespace["FitnessTrackerApp"])
    app.movement_dictionary = dictionary
    app.movement_definitions_by_id, app.movement_definitions_by_alias = namespace["movement_definition_index"](dictionary)
    return app


def top_level_labels(raw: str) -> list[str]:
    labels = []
    current_section = ""
    for line in raw.splitlines():
        if not line or line[0].isspace() or ":" not in line:
            continue
        label = line.split(":", 1)[0].strip().lower()
        if label in ALLOWED_TOP_LEVEL_LABELS:
            labels.append(label)
            current_section = label
            continue
        # Food and Note bodies are intentionally natural text and may contain
        # colons (for example, a timestamp) without becoming new fields.
        assert current_section in {"diet", "diet notes", "training notes", "notes"}, f"unexpected Daily Entry field: {label!r}"
    return labels


def assert_copyable_format(raw: str) -> None:
    assert not raw.startswith("```")
    assert not raw.startswith("以下是")
    labels = top_level_labels(raw)
    core = [label for label in labels if label in CORE_ORDER]
    assert core == sorted(core, key=CORE_ORDER.index), core
    training = raw.split("training:", 1)[1].split("\ncardio:", 1)[0] if "training:" in raw else ""
    action_headers = re.findall(r"^ (\d+)\. ", training, re.MULTILINE)
    assert action_headers == [str(index) for index in range(1, len(action_headers) + 1)]
    for line in training.splitlines():
        if line.strip() and not line.startswith(" ") and not line.startswith("training notes:"):
            raise AssertionError(f"training line is not one-space indented: {line!r}")


def test_prompt_contract_and_dynamic_registry() -> None:
    registry = ModuleRegistry.from_file(ROOT / "tools" / "fixtures" / "data_modules" / "registry.json")
    registry.register(
        ModuleDefinition.from_dict(
            {
                "module_id": "hydration_ml",
                "label": "饮水量",
                "aliases": ["饮水量", "water"],
                "category_id": "extension",
                "data_type": "quantity",
                "actual_unit": "ml",
                "display_unit": "ml",
                "definition_version": 1,
                "status": "active",
                "capabilities": {"recordable": True},
                "validation_contract": {"minimum": 0, "maximum": 10000, "decimal_places": 0},
                "recording_behavior": {"kind": "scalar", "cardinality": "one_per_day"},
                "presentation": {"section": "extension", "slot": "summary", "order": 99},
            }
        )
    )
    engine = DataModuleEngine(registry, Path(tempfile.gettempdir()) / "fitness-ledger-prompt-test-tracker.json")
    template = engine.llm_entry_template()
    assert template["schema"] == "fitness-ledger-llm-entry-template-v5"
    assert template["template_version"] == 5
    assert "饮水量 | module_id=hydration_ml" in template["prompt_template"]
    assert "用户明确写出的动作、组数、饮食条目" in template["prompt_template"]
    assert "禁止生成这些句子" in template["prompt_template"]
    assert "完全没有排便信息时省略排便字段" in template["prompt_template"]
    assert "60-12-1" in template["prompt_template"]
    assert "俯身哑铃飞鸟" in template["prompt_template"]
    assert "【执行原始记录】" in template["prompt_template"]
    assert template["prompt_template"].count("{{daily_text}}") == 1
    assert "__DAILY_TEXT_PLACEHOLDER__" not in template["prompt_template"]
    assert template["canonical_entry_format"]["field_order"] == CORE_ORDER


def test_historical_daily_entry_outputs_parse_without_scope_loss() -> None:
    app = parser_fixture()
    cases = [
        (
            "complete_leg_default_cardio",
            """date: 2026-08-16
weight: 70 kg
排便: 是

calories: 2250
protein: 137
carbs: 220
fat: 84

diet:
米饭300g（熟重）
鸡胸肉200g

training: 腿

 1. 坐姿腿举
 60-12-1
 70-12-2

 2. 深蹲
 20-6-1
 40-6-2
 notes: 幅度浅但是相对稳定，后续可以尝试加入训练安排

 3. 坐姿腿弯举
 90-15-1
 100-12-2

training notes: 训练完成后腿部一直处于无力发软的状态，应该是我目前为止强度最大的腿训，整个训练时间约50分钟；有氧为默认安排

cardio:
30分钟 跑步机爬坡""",
            {
                "split": "腿",
                "bowel": "是",
                "training_notes": "训练完成后腿部一直处于无力发软的状态，应该是我目前为止强度最大的腿训，整个训练时间约50分钟；有氧为默认安排",
                "action_note": "幅度浅但是相对稳定，后续可以尝试加入训练安排",
                "action_index": 1,
                "cardio": "30分钟 跑步机爬坡",
                "movement_count": 3,
            },
        ),
        (
            "shoulder_machine_cardio_and_food_parameters",
            """date: 2026-08-17
weight: 69.8 kg
排便: 是

calories: 1980
protein: 142
carbs: 185
fat: 63

diet:
燕麦50g
牛奶80g

金芒果20.0高蛋白酸奶昔

diet notes:
营养值按当前对话已确认的食品参数估算。

training: 肩

 1. 俯身哑铃飞鸟
 10-15-2
 notes: 前倾约30度，本次主要刺激中束。

 2. 侧平举
 5-12-3
 notes: 控制速度，最后两组接近力竭。

training notes: 今天左肩稳定性一般，整体控制优先。

cardio:
楼梯机61分钟，Level 6，约60步/分钟，机器显示约600 kcal""",
            {
                "split": "肩",
                "bowel": "是",
                "training_notes": "今天左肩稳定性一般，整体控制优先。",
                "action_note": "前倾约30度，本次主要刺激中束。",
                "cardio": "楼梯机61分钟，Level 6，约60步/分钟，机器显示约600 kcal",
                "movement_count": 2,
            },
        ),
        (
            "back_without_bowel_or_inferred_state",
            """date: 2026-08-18
weight: 69.5 kg

calories: 1760
protein: 128
carbs: 160
fat: 58

diet:
鸡蛋2个
米饭250g（熟重）

training: 背

 1. 引体向上
 自重-12-1
 自重-10-2
 notes: 最后一组没有完全力竭。

 2. 诺德士拉背拨片
 45-12-2
 notes: 训练中断，右侧发力感异常。

training notes: 训练中断，疼痛和异常按原记录保留。

cardio:
30分钟 跑步机爬坡""",
            {
                "split": "背",
                "training_notes": "训练中断，疼痛和异常按原记录保留。",
                "action_note": "最后一组没有完全力竭。",
                "cardio": "30分钟 跑步机爬坡",
                "movement_count": 2,
            },
        ),
        (
            "midnight_date_and_explicit_no_cardio",
            """date: 2026-08-19
weight: 69.4 kg
排便: 否

calories: 1510
protein: 96
carbs: 170
fat: 48

diet:
金芒果20.0高蛋白酸奶昔
吐司100g

diet notes:
沿用当前对话已经确认的酸奶昔和吐司参数；记录发生在8月19日00:30。

training: 背

 1. 引体向上
 自重-8-2

training notes: 8月19日00:30后仍属于本日记录。

cardio:
无""",
            {
                "date": "2026-08-19",
                "split": "背",
                "bowel": "否",
                "training_notes": "8月19日00:30后仍属于本日记录。",
                "cardio": "无",
                "movement_count": 1,
            },
        ),
    ]

    for name, raw, expected in cases:
        assert_copyable_format(raw)
        parsed = app.parse_entry(raw)
        assert parsed["date"] == expected.get("date", raw.split("date:", 1)[1].splitlines()[0].strip()), name
        assert parsed["training"]["split"] == expected["split"], name
        assert len(parsed["training"]["movements"]) == expected["movement_count"], name
        assert parsed["training"]["notes"] == expected["training_notes"], name
        assert parsed["body"]["cardio_summary"] == expected["cardio"], name
        if "bowel" in expected:
            assert parsed["body"]["bowel_movement"] == expected["bowel"], name
        else:
            assert parsed["body"]["bowel_movement"] == "", name
        if "action_note" in expected:
            assert parsed["training"]["movements"][expected.get("action_index", 0)]["notes"] == expected["action_note"], name
        if name == "shoulder_machine_cardio_and_food_parameters":
            assert parsed["training"]["movements"][0]["name"] == "俯身哑铃飞鸟"
        assert parsed["diet"]["food_summary"] and "kcal" not in parsed["diet"]["food_summary"], name

    no_inferred_state = app.parse_entry(cases[2][1])
    assert no_inferred_state["body"]["notes"] == ""
    assert "完成度良好" not in cases[2][1]
    assert "今日状态正常" not in cases[2][1]

    legacy = app.parse_entry(
        """date: 2026-08-20
training: 肩
1. 俯身哑铃飞鸟
10-10-2
notes: 旧格式动作备注。
2. 侧平举
5-12-2
notes:
全日备注。"""
    )
    assert legacy["training"]["movements"][0]["notes"] == "旧格式动作备注。"
    assert legacy["body"]["notes"] == "全日备注。"


if __name__ == "__main__":
    test_prompt_contract_and_dynamic_registry()
    test_historical_daily_entry_outputs_parse_without_scope_loss()
    print("LLM entry prompt regression: PASS (dynamic registry + 4 historical cases)")
