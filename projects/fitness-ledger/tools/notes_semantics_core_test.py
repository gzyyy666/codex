"""Anonymous Notes semantic Core acceptance matrix."""
from __future__ import annotations

import copy
import json
import runpy
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ledger_commands
from ledger_commands import LedgerCommandError, LedgerCommandService
from fitness_ledger_core.analysis_export import build_export
from fitness_ledger_core.notes import normalize_note_text
from fitness_ledger_core.shared_view_models import LedgerViewModels
from web_desktop.backend.server import LedgerWebService


def parser_fixture():
    namespace = runpy.run_path(ROOT / "stable_app.pyw")
    app = namespace["FitnessTrackerApp"].__new__(namespace["FitnessTrackerApp"])
    app.movement_dictionary = {
        "movements": [
            {"movement_id": "SHOULDER_001", "display_name": "俯身哑铃飞鸟", "aliases": ["飞鸟"], "active": True},
            {"movement_id": "SHOULDER_002", "display_name": "侧平举", "aliases": [], "active": True},
        ]
    }
    app.movement_definitions_by_id, app.movement_definitions_by_alias = namespace["movement_definition_index"](app.movement_dictionary)
    return app


CANONICAL = """2026-07-18
notes:
 今日整体状态正常，白天有些困。

diet notes:
 训练前碳水较少，练后正常补充。

diet:
 早餐：燕麦
 calories: 1800

training notes:
 今天左肩稳定性一般，整体控制优先。

training: 肩
 俯身哑铃飞鸟
 10kg x 15 x 2
 notes: 前倾约30度，本次主要刺激中束。
  第二行仍属于这个动作。
 侧平举
 5kg x 12 x 3
 notes: 控制速度。
俯身哑铃飞鸟
 7.5kg x 10 x 2
 notes: 同名动作的第二个实例。
"""


def make_service(root: Path, app) -> LedgerCommandService:
    tracker = root / "tracker.json"; dictionary = root / "movement_dictionary.json"
    tracker.write_text(json.dumps({"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []}, ensure_ascii=False), encoding="utf-8")
    dictionary.write_text(json.dumps(app.movement_dictionary, ensure_ascii=False), encoding="utf-8")
    return LedgerCommandService(tracker, dictionary, root / "backups", lambda raw, *_args: app.parse_entry(raw))


def make_web_service(root: Path, app) -> LedgerWebService:
    tracker = root / "tracker.json"; dictionary = root / "movement_dictionary.json"
    tracker.write_text(json.dumps({"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []}, ensure_ascii=False), encoding="utf-8")
    dictionary.write_text(json.dumps(app.movement_dictionary, ensure_ascii=False), encoding="utf-8")
    return LedgerWebService(tracker, dictionary, root / "backups")


def test_formal_field_boundaries(app) -> None:
    diet = app.parse_entry("2026-07-20\ndiet notes:\n训练前碳水较少。\ncalories: 2200\nprotein: 140\ncarbs: 220\nfat: 60")
    assert diet["diet"]["notes"] == "训练前碳水较少。"
    assert diet["diet"]["calories"] == 2200.0
    assert diet["diet"]["protein"] == 140.0
    assert diet["diet"]["carbs"] == 220.0
    assert diet["diet"]["fat"] == 60.0
    assert "calories" not in diet["diet"]["notes"]

    diet_before = app.parse_entry("2026-07-20\ncalories: 2200\ndiet notes:\n训练前碳水较少。\nprotein: 140")
    assert diet_before["diet"]["calories"] == 2200.0
    assert diet_before["diet"]["protein"] == 140.0
    assert diet_before["diet"]["notes"] == "训练前碳水较少。"

    body = app.parse_entry(
        "2026-07-21\nnotes:\n今日状态稳定。\nweight: 80\nbody fat: 20\nwaist: 82\nsleep: 7\nsteps: 9000"
    )
    assert body["body"]["notes"] == "今日状态稳定。"
    assert body["body"]["weight"] == 80.0
    assert body["body"]["body_fat"] == 20.0
    assert body["body"]["waist"] == 82.0
    assert body["body"]["sleep"] == 7.0
    assert body["body"]["steps"] == 9000.0

    training = app.parse_entry(
        "2026-07-22\ntraining notes:\n整体控制优先。\ntraining: 肩\n 俯身哑铃飞鸟\n 10kg x 10 x 2\n notes: 动作控制。\n  calories: 2200 只是正文提及\nweight: 80"
    )
    assert training["training"]["notes"] == "整体控制优先。"
    assert training["training"]["movements"][0]["notes"] == "动作控制。\ncalories: 2200 只是正文提及"
    assert training["body"]["weight"] == 80.0

    training_after = app.parse_entry(
        "2026-07-22\ntraining: 肩\n 俯身哑铃飞鸟\n 10kg x 10 x 2\n notes: 动作控制。\ntraining notes:\n整次训练备注。\ncardio:\n跑步机 20 分钟"
    )
    assert training_after["training"]["notes"] == "整次训练备注。"
    assert training_after["training"]["movements"][0]["notes"] == "动作控制。"

    unindented = app.parse_entry(
        "2026-07-22\n训练部位: 肩\n俯身哑铃飞鸟\n10kg x 10 x 2"
    )
    assert unindented["training"]["split"] == "肩"
    assert unindented["training"]["movements"][0]["movement_id"] == "SHOULDER_001"

    inline = app.parse_entry(
        "2026-07-22\ntraining part: 肩\n俯身哑铃飞鸟 10kg x 10 x 2"
    )
    assert inline["training"]["split"] == "肩"
    assert inline["training"]["movements"][0]["sets"][0]["weight"] == 10.0

    split_on_next_line = app.parse_entry(
        "2026-07-22\ntraining:\n 肩\n 俯身哑铃飞鸟\n 10kg x 10 x 2\n 侧平举\n 5kg x 12 x 3"
    )
    assert split_on_next_line["training"]["split"] == "肩"
    assert [item["name"] for item in split_on_next_line["training"]["movements"]] == ["俯身哑铃飞鸟", "侧平举"]

    aliases = app.parse_entry(
        "2026-07-23\n备注:\n整日别名。\nweight: 80\n饮食备注:\n饮食别名。\ncalories: 2200\n训练备注:\n训练别名。"
    )
    assert aliases["body"]["notes"] == "整日别名。"
    assert aliases["diet"]["notes"] == "饮食别名。"
    assert aliases["training"]["notes"] == "训练别名。"

    crlf = app.parse_entry("2026-07-23\r\ndiet notes:\r\n训练前碳水较少。\r\n\r\ncalories: 2200\r\n")
    assert crlf["diet"]["notes"] == "训练前碳水较少。"
    assert crlf["diet"]["calories"] == 2200.0

    prose = app.parse_entry("2026-07-23\ndiet notes:\n今天 calories 稍高，但没有正式字段。\n")
    assert prose["diet"]["notes"] == "今天 calories 稍高，但没有正式字段。"


def test_web_save_review_boundaries(app) -> None:
    raw = """2026-07-24
weight: 80
notes:
今日整体状态正常。

diet notes:
训练前碳水较少。
calories: 2200
protein: 140
carbs: 220
fat: 60

training notes:
今天左肩稳定性一般。

training: 肩
 俯身哑铃飞鸟
 10kg x 10 x 2
 notes: 本次控制优先。
"""
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-notes-web-boundary-") as name:
        root = Path(name); service = make_web_service(root, app)
        payload = service.parse_entry(raw)
        review = payload["review"]
        assert review["body"]["notes"] == "今日整体状态正常。"
        assert review["body"]["weight"] == 80.0
        assert review["diet"]["notes"] == "训练前碳水较少。"
        assert review["diet"]["calories"] == 2200.0
        assert review["diet"]["protein"] == 140.0
        assert review["diet"]["carbs"] == 220.0
        assert review["diet"]["fat"] == 60.0
        assert review["training"]["notes"] == "今天左肩稳定性一般。"
        assert review["training"]["movements"][0]["notes"] == "本次控制优先。"

        saved = service.save_review({"review_id": payload["review_id"], "review": review})
        assert saved["status"] == "CREATED"
        tracker = json.loads((root / "tracker.json").read_text(encoding="utf-8"))
        assert tracker["daily_records"][0]["Notes"] == "今日整体状态正常。"
        assert tracker["daily_records"][0]["Weight (kg)"] == 80.0
        assert tracker["diet_records"][0]["Notes"] == "训练前碳水较少。"
        assert tracker["diet_records"][0]["Calories (kcal)"] == 2200.0
        assert tracker["diet_records"][0]["Protein (g)"] == 140.0
        assert tracker["training_sessions"][0]["Notes"] == "今天左肩稳定性一般。"
        markdown = build_export(LedgerViewModels(root / "tracker.json", root / "movement_dictionary.json"), {"days": 30})["markdown"]
        assert "diet_notes: 训练前碳水较少。" in markdown
        assert "diet_notes: 训练前碳水较少。\ncalories" not in markdown


def main() -> None:
    app = parser_fixture()
    test_formal_field_boundaries(app)
    test_web_save_review_boundaries(app)
    parsed = app.parse_entry(CANONICAL)
    assert parsed["body"]["notes"] == "今日整体状态正常，白天有些困。"
    assert parsed["diet"]["notes"] == "训练前碳水较少，练后正常补充。"
    assert parsed["training"]["notes"] == "今天左肩稳定性一般，整体控制优先。"
    movements = parsed["training"]["movements"]
    assert [item["notes"] for item in movements] == [
        "前倾约30度，本次主要刺激中束。\n第二行仍属于这个动作。",
        "控制速度。",
        "同名动作的第二个实例。",
    ]
    assert movements[0]["movement_id"] == movements[2]["movement_id"]
    assert all("notes" not in item for item in app.movement_dictionary["movements"])

    # Historical unindented action-note compatibility works only when the next
    # line is an unambiguous movement boundary; a trailing top-level notes block
    # remains Daily Notes.
    legacy = app.parse_entry("2026-07-19\ntraining: 肩\n1. 侧平举\n5kg x 12 x 2\nnotes: 旧格式动作备注。\n2. 飞鸟\n10kg x 10 x 1\nnotes:\n全日备注。")
    assert legacy["training"]["movements"][0]["notes"] == "旧格式动作备注。"
    assert legacy["body"]["notes"] == "全日备注。"
    assert legacy["training"]["movements"][1]["notes"] == ""

    assert normalize_note_text("\r\n  同一条  \r\n") == "同一条"
    assert normalize_note_text("第一行\n\n第二行") == "第一行\n\n第二行"

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-notes-") as name:
        root = Path(name); service = make_service(root, app)
        review = service.parse(CANONICAL)
        assert review["review"]["diet"]["notes"] == parsed["diet"]["notes"]
        saved = service.save(review["review"])
        assert saved["changed"] and saved["notes_updated"]
        tracker, dictionary = service.load_state()
        assert tracker["daily_records"][0]["Notes"] == "今日整体状态正常，白天有些困。"
        assert tracker["diet_records"][0]["Notes"] == "训练前碳水较少，练后正常补充。"
        assert tracker["training_sessions"][0]["Notes"] == "今天左肩稳定性一般，整体控制优先。"
        histories = [row for movement in tracker["movements"].values() for row in movement["history"]]
        assert sorted(row["notes"] for row in histories) == sorted(item["notes"] for item in movements)
        assert dictionary == app.movement_dictionary

        views = LedgerViewModels(root / "tracker.json", root / "movement_dictionary.json")
        analysis = views.analysis(days=30)
        assert analysis["body"][0]["daily_notes"] == tracker["daily_records"][0]["Notes"]
        assert analysis["diet"][0]["diet_notes"] == tracker["diet_records"][0]["Notes"]
        assert analysis["training"][0]["training_notes"] == tracker["training_sessions"][0]["Notes"]
        assert analysis["movements"][0]["history"][0]["movement_notes"]
        markdown = build_export(views, {"days": 30})["markdown"]
        assert "daily_notes:" in markdown and "diet_notes:" in markdown and "training_notes:" in markdown
        assert markdown.count("前倾约30度，本次主要刺激中束。") == 1

        # Same note with only line-ending/edge-space noise is not a business update.
        body_id = tracker["daily_records"][0]["id"]
        checkpoints_before_no_change = sorted((root / "backups").glob("undo_tracker_*.json"))
        no_change = service.update_record("body", body_id, {"Notes": "\r\n 今日整体状态正常，白天有些困。  \r\n"})
        assert no_change["status"] == "NO_CHANGES"
        assert sorted((root / "backups").glob("undo_tracker_*.json")) == checkpoints_before_no_change

        cleared = service.update_record("body", body_id, {"Notes": ""})
        assert cleared["status"] == "UPDATED"
        assert service.load_state()[0]["daily_records"][0]["Notes"] == ""
        assert "Notes" not in service.load_state()[0]["diet_records"][0] or service.load_state()[0]["diet_records"][0]["Notes"]

        before_tracker = (root / "tracker.json").read_bytes()
        backups_before_failure = sorted(path.name for path in (root / "backups").glob("*"))
        original_write = ledger_commands._write_json_atomic
        ledger_commands._write_json_atomic = lambda *_args: (_ for _ in ()).throw(OSError("injected notes failure"))
        try:
            try:
                service.update_record("diet", tracker["diet_records"][0]["id"], {"Notes": "失败写入"})
            except (LedgerCommandError, OSError) as exc:
                if isinstance(exc, LedgerCommandError):
                    assert exc.code == "SAVE_FAILED"
            else:
                raise AssertionError("expected SAVE_FAILED")
        finally:
            ledger_commands._write_json_atomic = original_write
        assert (root / "tracker.json").read_bytes() == before_tracker
        assert sorted(path.name for path in (root / "backups").glob("*")) == backups_before_failure

    print("FITNESS_LEDGER_NOTES_SEMANTICS_CORE_OK")


if __name__ == "__main__":
    main()
