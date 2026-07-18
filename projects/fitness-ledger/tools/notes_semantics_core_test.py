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


def main() -> None:
    app = parser_fixture()
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

    print("FITNESS_LEDGER_NOTES_SEMANTICS_CORE_OK")


if __name__ == "__main__":
    main()
