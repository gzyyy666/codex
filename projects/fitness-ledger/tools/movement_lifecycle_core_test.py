from __future__ import annotations

import copy
import json
import runpy
import sys
import tempfile
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import ledger_commands as command_module
from fitness_ledger_core.cloud_payload import build_cloud_payload
from fitness_ledger_core.shared_view_models import LedgerViewModels
from ledger_commands import LedgerCommandError, LedgerCommandService
from tools.custom_movement_merge_test import TARGET_ID, fixture_values, make_service, write_json


SOURCE_ID = "BACK_002"


def lifecycle_values() -> tuple[dict, dict]:
    tracker, dictionary = fixture_values()
    dictionary["movements"].append({
        "movement_id": SOURCE_ID,
        "display_name": "坐姿划船",
        "english_name": "Seated Row",
        "aliases": ["器械划船", "Cable Row"],
        "muscle_group": "Back",
        "category": "Strength",
        "equipment": "Cable",
        "active": True,
        "notes": "Independent canonical source.",
    })
    tracker["movements"][SOURCE_ID] = {
        "movement_id": SOURCE_ID,
        "name": "坐姿划船",
        "aliases": ["旧式坐姿划船"],
        "history": [
            {
                "id": "canonical-source-1",
                "movement_id": SOURCE_ID,
                "date": "2026-06-04",
                "training_day": 10,
                "order": 3,
                "sets": [{"weight": 50.0, "reps": 10, "sets": 4}],
                "cardio": {},
                "notes": "肩胛后缩",
                "raw": "50kg x 10 x 4",
                "source": "text entry",
            },
            {
                "id": "canonical-source-2",
                "movement_id": SOURCE_ID,
                "date": "2026-06-06",
                "training_day": 11,
                "order": 1,
                "sets": [{"weight": 55.0, "reps": 8, "sets": 3}],
                "cardio": {"duration_minutes": 3},
                "notes": "保留备注",
                "raw": "55kg x 8 x 3",
                "source": "historical import",
            },
        ],
        "created_at": "2026-05-03T08:00:00",
    }
    return tracker, dictionary


def command_service(root: Path) -> tuple[LedgerCommandService, Path, Path, Path]:
    tracker, dictionary = lifecycle_values()
    return make_service(root, tracker, dictionary)


def assert_error_code(action, code: str) -> LedgerCommandError:
    try:
        action()
    except LedgerCommandError as exc:
        assert exc.code == code, (exc.code, exc.details)
        return exc
    raise AssertionError(f"Expected {code}")


def test_general_merge() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-general-merge-") as temp:
        service, tracker_file, dictionary_file, backups = command_service(Path(temp))
        before_tracker = json.loads(tracker_file.read_text(encoding="utf-8"))
        before_dictionary = json.loads(dictionary_file.read_text(encoding="utf-8"))
        source_history = copy.deepcopy(before_tracker["movements"][SOURCE_ID]["history"])
        target_history = copy.deepcopy(before_tracker["movements"][TARGET_ID]["history"])
        raw_before = copy.deepcopy(before_tracker["raw_entries"])
        target_before = next(item for item in before_dictionary["movements"] if item["movement_id"] == TARGET_ID)
        tracker_bytes_before_preview = tracker_file.read_bytes()
        dictionary_bytes_before_preview = dictionary_file.read_bytes()

        custom_preview = service.preview_merge_custom_movement(SOURCE_ID, TARGET_ID)
        assert custom_preview["can_execute"] is False
        assert "SOURCE_NOT_CUSTOM" in {item["code"] for item in custom_preview["blockers"]}

        preview = service.preview_merge_movement(SOURCE_ID, TARGET_ID)
        assert preview["can_execute"] is True
        assert preview["operation"] == "MOVEMENT_TO_CANONICAL_MOVEMENT_MERGE"
        assert preview["history"]["source_history_count"] == 2
        assert preview["history"]["target_history_after"] == 3
        assert tracker_file.read_bytes() == tracker_bytes_before_preview
        assert dictionary_file.read_bytes() == dictionary_bytes_before_preview
        assert not backups.exists()
        result = service.merge_movement(SOURCE_ID, TARGET_ID, preview["plan_identity"])
        assert result["status"] == "UPDATED"
        assert result["migrated_history_count"] == 2
        assert result["remaining_source_references"] == []

        stored_tracker = json.loads(tracker_file.read_text(encoding="utf-8"))
        stored_dictionary = json.loads(dictionary_file.read_text(encoding="utf-8"))
        assert SOURCE_ID not in stored_tracker["movements"]
        assert not any(item["movement_id"] == SOURCE_ID for item in stored_dictionary["movements"])
        target_after = next(item for item in stored_dictionary["movements"] if item["movement_id"] == TARGET_ID)
        for field in ("movement_id", "display_name", "english_name", "muscle_group", "category", "equipment"):
            assert target_after.get(field) == target_before.get(field)
        assert {"坐姿划船", "Seated Row", "器械划船", "Cable Row", "旧式坐姿划船"}.issubset(
            set(target_after["aliases"])
        )
        target_row = stored_tracker["movements"][TARGET_ID]
        assert [item["id"] for item in target_row["history"]] == [
            *(item["id"] for item in target_history),
            *(item["id"] for item in source_history),
        ]
        for original in source_history:
            migrated = next(item for item in target_row["history"] if item["id"] == original["id"])
            assert migrated == {**original, "movement_id": TARGET_ID}
        assert stored_tracker["raw_entries"] == raw_before

        undo = service.undo_last_write()
        assert undo["undone"] is True
        assert json.loads(tracker_file.read_text(encoding="utf-8")) == before_tracker
        assert json.loads(dictionary_file.read_text(encoding="utf-8")) == before_dictionary
        assert list(backups.glob("undone_tracker_*.json"))


def test_general_merge_guards() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-general-stale-") as temp:
        service, tracker_file, _dictionary_file, backups = command_service(Path(temp))
        preview = service.preview_merge_movement(SOURCE_ID, TARGET_ID)
        tracker = json.loads(tracker_file.read_text(encoding="utf-8"))
        tracker["concurrent_change"] = True
        write_json(tracker_file, tracker)
        assert_error_code(
            lambda: service.merge_movement(SOURCE_ID, TARGET_ID, preview["plan_identity"]),
            "PREVIEW_STALE",
        )
        assert not backups.exists()

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-general-conflict-") as temp:
        service, _tracker_file, dictionary_file, _backups = command_service(Path(temp))
        dictionary = json.loads(dictionary_file.read_text(encoding="utf-8"))
        chest = next(item for item in dictionary["movements"] if item["movement_id"] == "CHEST_001")
        chest["aliases"].append("Seated Row")
        write_json(dictionary_file, dictionary)
        preview = service.preview_merge_movement(SOURCE_ID, TARGET_ID)
        assert preview["can_execute"] is False
        assert "ALIAS_OWNERSHIP_CONFLICT" in {item["code"] for item in preview["blockers"]}

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-general-rollback-") as temp:
        service, tracker_file, dictionary_file, backups = command_service(Path(temp))
        tracker_before = tracker_file.read_bytes()
        dictionary_before = dictionary_file.read_bytes()
        preview = service.preview_merge_movement(SOURCE_ID, TARGET_ID)
        original_write = command_module._write_json_atomic

        def fail_tracker(path: Path, value) -> None:
            if Path(path) == tracker_file:
                raise OSError("forced tracker failure")
            original_write(path, value)

        command_module._write_json_atomic = fail_tracker
        try:
            error = assert_error_code(
                lambda: service.merge_movement(SOURCE_ID, TARGET_ID, preview["plan_identity"]),
                "MIGRATION_FAILED",
            )
            assert error.details["rolled_back"] is True
        finally:
            command_module._write_json_atomic = original_write
        assert tracker_file.read_bytes() == tracker_before
        assert dictionary_file.read_bytes() == dictionary_before
        assert not list(backups.glob("undo_*.json"))


def test_progress_exclusion() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-progress-exclusion-") as temp:
        service, tracker_file, dictionary_file, backups = command_service(Path(temp))
        tracker_before = json.loads(tracker_file.read_text(encoding="utf-8"))
        raw_before = copy.deepcopy(tracker_before["raw_entries"])
        definitions = {item["movement_id"]: item for item in service.movement_definitions()}
        assert definitions[TARGET_ID]["exclude_from_progress"] is False
        assert TARGET_ID in {item["movement_id"] for item in service.movement_progress_definitions()}
        no_change = service.set_movement_exclude_from_progress(TARGET_ID, False)
        assert no_change["status"] == "NO_CHANGES" and no_change["changed"] is False
        assert not backups.exists()

        excluded = service.set_movement_exclude_from_progress(TARGET_ID, True)
        assert excluded["status"] == "UPDATED" and excluded["exclude_from_progress"] is True
        stored_tracker = json.loads(tracker_file.read_text(encoding="utf-8"))
        stored_dictionary = json.loads(dictionary_file.read_text(encoding="utf-8"))
        assert stored_tracker == tracker_before
        target = next(item for item in stored_dictionary["movements"] if item["movement_id"] == TARGET_ID)
        assert target["exclude_from_progress"] is True
        assert TARGET_ID not in {item["movement_id"] for item in service.movement_progress_definitions()}

        views = LedgerViewModels(tracker_file, dictionary_file)
        assert TARGET_ID not in {item["movement_id"] for item in views.movement_progress_index()}
        search = views.movement_history("高位下拉", limit=20)
        assert search["movement"]["movement_id"] == TARGET_ID and search["history"]
        archive = views.training_archive(limit=50)
        session = next(item for item in archive if item["id"] == "session-8")
        assert TARGET_ID in {item["movement_id"] for item in session["movement_refs"]}
        analysis = views.analysis(start="2026-06-01", end="2026-06-30")
        assert TARGET_ID in {item["movement_id"] for item in analysis["movements"]}
        payload = build_cloud_payload(views)
        assert TARGET_ID in {item["movement_id"] for item in payload["fl_movements"]}
        assert TARGET_ID in {item["movement_id"] for item in payload["fl_movement_history"]}
        assert json.loads(tracker_file.read_text(encoding="utf-8"))["raw_entries"] == raw_before

        stable = runpy.run_path(PROJECT / "stable_app.pyw")
        checker = stable["FitnessTrackerApp"].__new__(stable["FitnessTrackerApp"])
        checker.database = stored_tracker
        checker.movement_dictionary = stored_dictionary
        checker.movement_definitions_by_id, checker.movement_definitions_by_alias = stable["movement_definition_index"](
            stored_dictionary
        )
        issues = checker.collect_data_issues()
        assert not any(
            TARGET_ID in json.dumps(issue, ensure_ascii=False)
            and any(term in issue["issue"] for term in ("孤立", "缺失", "成长"))
            for issue in issues
        )

        service.undo_last_write()
        restored = json.loads(dictionary_file.read_text(encoding="utf-8"))
        restored_target = next(item for item in restored["movements"] if item["movement_id"] == TARGET_ID)
        assert bool(restored_target.get("exclude_from_progress", False)) is False
        assert TARGET_ID in {item["movement_id"] for item in service.movement_progress_definitions()}

        service.set_movement_exclude_from_progress(TARGET_ID, True)
        restored_result = service.set_movement_exclude_from_progress(TARGET_ID, False)
        assert restored_result["status"] == "UPDATED"
        assert TARGET_ID in {item["movement_id"] for item in service.movement_progress_definitions()}

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-progress-rollback-") as temp:
        service, tracker_file, dictionary_file, backups = command_service(Path(temp))
        tracker_before = tracker_file.read_bytes()
        dictionary_before = dictionary_file.read_bytes()
        original_write = command_module._write_json_atomic

        def fail_dictionary(path: Path, value) -> None:
            if Path(path) == dictionary_file:
                raise OSError("forced dictionary failure")
            original_write(path, value)

        command_module._write_json_atomic = fail_dictionary
        try:
            error = assert_error_code(
                lambda: service.set_movement_exclude_from_progress(TARGET_ID, True),
                "PROGRESS_VISIBILITY_UPDATE_FAILED",
            )
            assert error.details["rolled_back"] is True
        finally:
            command_module._write_json_atomic = original_write
        assert tracker_file.read_bytes() == tracker_before
        assert dictionary_file.read_bytes() == dictionary_before
        assert not list(backups.glob("undo_*.json"))


def main() -> None:
    test_general_merge()
    test_general_merge_guards()
    test_progress_exclusion()
    print("FITNESS_LEDGER_MOVEMENT_LIFECYCLE_CORE_OK")


if __name__ == "__main__":
    main()
