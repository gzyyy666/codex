from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import ledger_commands as command_module
from fitness_ledger_core.analysis_export import build_export
from fitness_ledger_core.cloud_payload import build_cloud_payload
from fitness_ledger_core.shared_view_models import LedgerViewModels
from ledger_commands import LedgerCommandError, LedgerCommandService


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def make_service(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    tracker = root / "tracker.json"
    dictionary = root / "movement_dictionary.json"
    backups = root / "backups"
    write_json(
        tracker,
        {
            "daily_records": [],
            "diet_records": [],
            "training_sessions": [],
            "movements": {},
            "raw_entries": [],
        },
    )
    write_json(
        dictionary,
        {
            "version": "1.0",
            "movements": [
                {
                    "movement_id": "CHEST_001",
                    "display_name": "Bench Press",
                    "aliases": ["Bench Press"],
                    "muscle_group": "Chest",
                    "active": True,
                }
            ],
        },
    )
    return LedgerCommandService(tracker, dictionary, backups, lambda *_args: {}), tracker, dictionary, backups


def movement(name: str, order: int, history_note: str, excluded: bool = False) -> dict:
    return {
        "name": name,
        "display_name": name,
        "movement_id": "CHEST_001",
        "order": order,
        "sets": [{"weight": 60.0 + order, "reps": 8, "sets": 3}],
        "cardio": {},
        "raw": f"{60 + order}kg x 8 x 3 / {order}",
        "notes": history_note,
        "_review_action": "use",
        "exclude_from_progress": excluded,
    }


def parsed_entry(entry_date: str = "2026-07-18", movements: list[dict] | None = None) -> dict:
    return {
        "id": f"entry-{entry_date}",
        "date": entry_date,
        "raw": "training: Bench Press\n...",
        "body": {"weight": None, "bowel_movement": "", "training_summary": "", "cardio_summary": "", "notes": ""},
        "diet": {"calories": None, "protein": None, "carbs": None, "fat": None, "food_summary": "", "notes": ""},
        "training": {
            "split": "Chest",
            "raw": "training: Bench Press",
            "standardized_summary": "Bench Press",
            "notes": "Training note",
            "movements": movements or [movement("Bench Press", 1, "included")],
        },
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-instance-progress-") as temp:
        root = Path(temp)
        service, tracker_file, dictionary_file, backups = make_service(root)
        first = movement("Bench Press", 1, "working set")
        second = movement("Bench Press", 2, "volume only", excluded=True)
        created = service.save(parsed_entry(movements=[first, second]))
        assert created["status"] == "CREATED" and created["saved_movements"] == 2
        assert created["progress_excluded_count"] == 1

        stored = json.loads(tracker_file.read_text(encoding="utf-8"))
        histories = stored["movements"]["CHEST_001"]["history"]
        assert len(histories) == 2
        assert [row["exclude_from_progress"] for row in histories] == [False, True]
        assert [row["order"] for row in histories] == [1, 2]
        ids = [row["id"] for row in histories]

        views = LedgerViewModels(tracker_file, dictionary_file)
        history_payload = views.movement_history_by_id("CHEST_001", limit=20)
        assert len(history_payload["history"]) == 2
        assert len(history_payload["progress_history"]) == 1
        assert history_payload["movement"]["history_count"] == 2
        assert history_payload["movement"]["progress_history_count"] == 1
        assert history_payload["progress_history"][0]["id"] == ids[0]
        index = next(row for row in views.movement_progress_index() if row["movement_id"] == "CHEST_001")
        assert index["history_count"] == 1

        archive = views.training_archive()
        refs = archive[0]["movement_refs"]
        assert {ref["history_id"] for ref in refs} == set(ids)
        assert sorted(ref["exclude_from_progress"] for ref in refs) == [False, True]
        analysis = build_export(views, {"start": "2026-07-18", "end": "2026-07-18"})
        exported = analysis["payload"]["movements"][0]["history"]
        assert {row["id"] for row in exported} == set(ids)
        assert "exclude_from_progress: true" in analysis["markdown"]
        cloud_history = build_cloud_payload(views)["fl_movement_history"]
        assert {row["id"] for row in cloud_history} == set(ids)
        assert sum(bool(row.get("exclude_from_progress")) for row in cloud_history) == 1

        unchanged = service.update_movement_history("CHEST_001", ids[1], {"exclude_from_progress": True})
        assert unchanged["status"] == "NO_CHANGES"
        backup_count = len(list(backups.glob("undo_tracker_*.json")))
        assert len(list(backups.glob("undo_tracker_*.json"))) == backup_count
        before_edit = tracker_file.read_bytes()
        updated = service.update_movement_history("CHEST_001", ids[0], {"exclude_from_progress": True})
        assert updated["status"] == "UPDATED" and updated["history"]["exclude_from_progress"] is True
        assert updated["history"]["sets"] == histories[0]["sets"]
        assert len(views.movement_history_by_id("CHEST_001", limit=20)["progress_history"]) == 0
        undo = service.undo_last_write()
        assert undo["undone"] is True
        assert tracker_file.read_bytes() == before_edit

        before_failure = tracker_file.read_bytes()
        existing_undo = {path.name for path in backups.glob("undo_tracker_*.json")}
        original_write = command_module._write_json_atomic

        def fail_tracker(path: Path, value) -> None:
            if Path(path) == tracker_file:
                raise OSError("forced tracker failure")
            original_write(path, value)

        command_module._write_json_atomic = fail_tracker
        try:
            try:
                service.update_movement_history("CHEST_001", ids[0], {"exclude_from_progress": True})
            except LedgerCommandError as exc:
                assert exc.code == "SAVE_FAILED"
                assert exc.details["rolled_back"] is True
            else:
                raise AssertionError("expected failed history update")
        finally:
            command_module._write_json_atomic = original_write
        assert tracker_file.read_bytes() == before_failure
        assert {path.name for path in backups.glob("undo_tracker_*.json")} == existing_undo

        service.save(parsed_entry("2026-07-19", [movement("Unknown", 1, "kept raw") | {"movement_id": "", "_review_action": "skip"}]))
        after_skip = json.loads(tracker_file.read_text(encoding="utf-8"))
        assert len(after_skip["movements"]["CHEST_001"]["history"]) == 2
        assert after_skip["raw_entries"][-1]["skipped_movements"] == ["Unknown"]

        review_service, _review_tracker, _review_dictionary, _review_backups = make_service(root / "review")
        review_movement = movement("Bench Press", 1, "review")
        review_movement.pop("exclude_from_progress")
        review_service.parser = lambda *_args: parsed_entry("2026-07-20", [review_movement])
        review = review_service.parse("training: Bench Press")
        assert review["review"]["training"]["movements"][0]["exclude_from_progress"] is False

    print("FITNESS_LEDGER_MOVEMENT_INSTANCE_PROGRESS_CORE_OK")


if __name__ == "__main__":
    main()
