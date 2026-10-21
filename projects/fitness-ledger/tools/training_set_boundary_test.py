"""Regression tests for load units and prose around training set expressions."""
from __future__ import annotations

import importlib.machinery
import math
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

loader = importlib.machinery.SourceFileLoader("fitness_ledger_stable_app", str(PROJECT / "stable_app.pyw"))
stable = loader.load_module()

DICTIONARY = {"movements": [
    {"movement_id": "DIP", "display_name": "双杠臂屈伸", "aliases": ["双杠臂屈伸"], "active": True},
    {"movement_id": "FLY", "display_name": "哑铃飞鸟", "aliases": ["哑铃飞鸟"], "active": True},
]}


def parser():
    app = stable.FitnessTrackerApp.__new__(stable.FitnessTrackerApp)
    app.movement_dictionary = DICTIONARY
    app.movement_definitions_by_id, app.movement_definitions_by_alias = stable.movement_definition_index(DICTIONARY)
    return app


def main():
    # Metric spellings stay attached to the movement boundary, with pounds
    # normalized into the application's kilogram-based numeric field.
    unit_cases = [
        ("40kg-12-1", 40.0),
        ("40 公斤 x 12 x 1", 40.0),
        ("88lb-12-1", round(88 * 0.45359237, 3)),
        ("88 lbs 12次1组", round(88 * 0.45359237, 3)),
        ("88磅-12-1", round(88 * 0.45359237, 3)),
    ]
    for expression, expected in unit_cases:
        rows = stable.extract_load_blocks(expression)
        assert len(rows) == 1, (expression, rows)
        assert math.isclose(rows[0]["weight"], expected, rel_tol=0, abs_tol=1e-9), (expression, rows)
        assert stable.strip_movement_metrics("双杠臂屈伸 " + expression) == "双杠臂屈伸"
    annotated = stable.extract_load_blocks("40kg-12-1（轻松完成）30kg-10-1")
    assert [(row["weight"], row["reps"], row["sets"]) for row in annotated] == [(40.0, 12, 1), (30.0, 10, 1)]
    assert stable.strip_movement_metrics("双杠臂屈伸 40kg-12-1（轻松完成）") == "双杠臂屈伸"

    # Unit-bearing drops retain one row per formal set and every segment.
    fly = "(27.5lb+22lb+16.5lb)-(10+6+6)-2 (27.5lb+22lb+16.5lb+11lb)-(10+6+6+6)-1"
    fly_rows = stable.extract_load_blocks(fly)
    assert [row["sets"] for row in fly_rows] == [2, 1]
    assert [len(row["segments"]) for row in fly_rows] == [3, 4]
    assert math.isclose(fly_rows[0]["segments"][0]["weight"], round(27.5 * 0.45359237, 3), abs_tol=1e-9)

    # Inline and following-line notes stay with the movement and cannot add
    # phantom sets even when the prose contains set-shaped numbers.
    for numbered in (False, True):
        prefix = "1. " if numbered else ""
        entry = (
            "2099-01-01\ntraining: test\n"
            f" {prefix}哑铃飞鸟 {fly} notes: 共3组正式组；回忆估算，注记中的 99-99-99 不是训练组。\n"
            f" {prefix if not numbered else '2. '}双杠臂屈伸 自重-10-2\n"
            " notes: 愉悦组；备注里有 77-77-77 但不是组记录。"
        )
        training = parser().parse_entry(entry)["training"]
        movements = training["movements"]
        assert [row["movement_id"] for row in movements] == ["FLY", "DIP"]
        assert [sum(item["sets"] for item in row["sets"]) for row in movements] == [3, 2]
        assert movements[0]["notes"] == "共3组正式组；回忆估算，注记中的 99-99-99 不是训练组。"
        assert movements[1]["notes"] == "愉悦组；备注里有 77-77-77 但不是组记录。"
        assert training["raw"].endswith("备注里有 77-77-77 但不是组记录。")

    # Existing bodyweight inline regression remains valid.
    dip = parser().parse_entry("training: test\n双杠臂屈伸 自重-10-2")['training']['movements']
    assert len(dip) == 1 and dip[0]["movement_id"] == "DIP"
    assert dip[0]["sets"] == [{"weight": 0.0, "weight_text": "自重", "reps": 10, "sets": 2}]
    print("FITNESS_LEDGER_TRAINING_SET_BOUNDARY_OK")


if __name__ == "__main__":
    main()
