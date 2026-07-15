from __future__ import annotations

import copy
import hashlib
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


SOURCE_ID = "CUSTOM_023"
TARGET_ID = "BACK_004"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def file_signature(path: Path) -> tuple[str, int, int]:
    payload = path.read_bytes()
    stat = path.stat()
    return hashlib.sha256(payload).hexdigest(), stat.st_size, stat.st_mtime_ns


def fixture_values() -> tuple[dict, dict]:
    duplicate_shape = {
        "date": "2026-06-01",
        "training_day": 8,
        "order": 2,
        "sets": [{"weight": 40.0, "reps": 10, "sets": 3}],
        "cardio": {},
        "raw": "40kg x 10 x 3",
        "notes": "末组严格",
        "source": "text entry",
    }
    tracker = {
        "version": "2.0",
        "daily_records": [],
        "diet_records": [],
        "training_sessions": [
            {"id": "session-8", "No.": 8, "Date": "2026-06-01", "Split": "Back", "Raw Record": "原训练文本"}
        ],
        "movements": {
            TARGET_ID: {
                "movement_id": TARGET_ID,
                "name": "高位下拉",
                "aliases": ["下拉"],
                "history": [{"id": "target-history", "movement_id": TARGET_ID, **duplicate_shape}],
                "created_at": "2026-05-01T08:00:00",
            },
            "legacy-custom-row": {
                "movement_id": SOURCE_ID,
                "name": "旧下拉",
                "aliases": ["Old Pulldown", "旧式下拉"],
                "history": [
                    {"id": "source-history-1", "movement_id": SOURCE_ID, **copy.deepcopy(duplicate_shape)},
                    {
                        "id": "source-history-2",
                        "movement_id": SOURCE_ID,
                        "date": "2026-06-03",
                        "training_day": 9,
                        "order": 1,
                        "sets": [{"weight": 45.0, "reps": 8, "sets": 4, "tempo": "3-1-1"}],
                        "cardio": {"duration_minutes": 5},
                        "raw": "45kg x 8 x 4",
                        "notes": "保留动作备注",
                        "source": "historical import",
                        "legacy_extra": {"quality": "strict"},
                    },
                ],
                "created_at": "2026-05-02T08:00:00",
            },
        },
        "raw_entries": [
            {
                "id": "raw-1",
                "date": "2026-06-03",
                "text": "原始输入：旧下拉 45kg x 8 x 4；不得改写。",
                "skipped_movements": ["旧式下拉"],
            }
        ],
    }
    dictionary = {
        "version": "1.0",
        "movements": [
            {
                "movement_id": TARGET_ID,
                "display_name": "高位下拉",
                "english_name": "Lat Pulldown",
                "aliases": ["下拉"],
                "muscle_group": "Back",
                "category": "Strength",
                "equipment": "Cable",
                "active": True,
            },
            {
                "movement_id": SOURCE_ID,
                "display_name": "旧下拉",
                "english_name": "Old Pulldown",
                "aliases": ["旧式下拉", " 旧 下拉 "],
                "muscle_group": "Back",
                "category": "Strength",
                "equipment": "Cable",
                "active": True,
            },
            {
                "movement_id": "CHEST_001",
                "display_name": "卧推",
                "english_name": "Bench Press",
                "aliases": ["平板卧推"],
                "muscle_group": "Chest",
                "active": True,
            },
        ],
    }
    return tracker, dictionary


def make_service(root: Path, tracker_value: dict | None = None, dictionary_value: dict | None = None):
    tracker = root / "tracker.json"
    dictionary = root / "movement_dictionary.json"
    backups = root / "backups"
    default_tracker, default_dictionary = fixture_values()
    write_json(tracker, tracker_value or default_tracker)
    write_json(dictionary, dictionary_value or default_dictionary)
    return LedgerCommandService(tracker, dictionary, backups, lambda *_args: {}), tracker, dictionary, backups


def expect_block(mutator, expected_code: str, source_id: str = SOURCE_ID, target_id: str = TARGET_ID) -> None:
    tracker_value, dictionary_value = fixture_values()
    mutator(tracker_value, dictionary_value)
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-custom-block-") as temp:
        service, _tracker, _dictionary, _backups = make_service(Path(temp), tracker_value, dictionary_value)
        preview = service.preview_merge_custom_movement(source_id, target_id)
        assert preview["can_execute"] is False
        assert expected_code in {item["code"] for item in preview["blockers"]}, preview["blockers"]


def expect_execute_failure(stage: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"fitness-ledger-custom-{stage}-") as temp:
        service, tracker, dictionary, backups = make_service(Path(temp))
        before_tracker = tracker.read_bytes()
        before_dictionary = dictionary.read_bytes()
        preview = service.preview_merge_custom_movement(SOURCE_ID, TARGET_ID)
        original_write = command_module._write_json_atomic
        original_post_validation = service._post_write_custom_movement_validation

        def failing_write(path: Path, value) -> None:
            if (stage == "dictionary" and Path(path) == dictionary) or (stage == "tracker" and Path(path) == tracker):
                raise OSError(f"forced {stage} write failure")
            original_write(path, value)

        def failing_validation(_plan: dict):
            raise RuntimeError("forced post-write validation failure")

        try:
            if stage in {"dictionary", "tracker"}:
                command_module._write_json_atomic = failing_write
            else:
                service._post_write_custom_movement_validation = failing_validation
            try:
                service.merge_custom_movement(SOURCE_ID, TARGET_ID, preview["plan_identity"])
                raise AssertionError("forced failure unexpectedly succeeded")
            except LedgerCommandError as exc:
                assert exc.code == "MIGRATION_FAILED"
                assert exc.details["rolled_back"] is True
                assert exc.details["failed_stage"] == (
                    "dictionary_write" if stage == "dictionary" else
                    "tracker_write" if stage == "tracker" else
                    "post_write_validation"
                )
        finally:
            command_module._write_json_atomic = original_write
            service._post_write_custom_movement_validation = original_post_validation
        assert tracker.read_bytes() == before_tracker
        assert dictionary.read_bytes() == before_dictionary
        assert not list(backups.glob("undo_*.json"))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-custom-merge-") as temp:
        service, tracker, dictionary, backups = make_service(Path(temp))
        original_tracker = json.loads(tracker.read_text(encoding="utf-8"))
        original_dictionary = json.loads(dictionary.read_text(encoding="utf-8"))
        before_histories = [
            copy.deepcopy(history)
            for movement in original_tracker["movements"].values()
            for history in movement["history"]
        ]
        before_raw_text = [item["text"] for item in original_tracker["raw_entries"]]
        tracker_signature = file_signature(tracker)
        dictionary_signature = file_signature(dictionary)

        preview = service.preview_merge_custom_movement(SOURCE_ID, TARGET_ID)
        assert preview["can_execute"] is True
        assert preview["source"]["movement_id"] == SOURCE_ID
        assert preview["target"]["movement_id"] == TARGET_ID
        assert preview["history"]["source_history_count"] == 2
        assert preview["history"]["target_history_count"] == 1
        assert preview["history"]["target_history_after"] == 3
        assert preview["duplicates"]["exact_content"]
        assert preview["duplicates"]["same_dates"] == ["2026-06-01"]
        assert preview["duplicates"]["same_training_days"]
        assert preview["duplicates"]["policy"] == "preserve_all_no_automatic_deduplication"
        assert "旧下拉" in preview["aliases"]["to_add"]
        assert "Old Pulldown" in preview["aliases"]["to_add"]
        assert preview["aliases"]["normalized_duplicates"]
        assert preview["raw"]["skipped_source_matches"]
        assert preview["raw"]["text_unchanged"] is True
        assert preview["references"]["unknown_count"] == 0
        assert preview["plan_identity"]
        assert preview["data_fingerprint"]["identity"]
        assert file_signature(tracker) == tracker_signature
        assert file_signature(dictionary) == dictionary_signature
        assert not backups.exists()

        result = service.merge_custom_movement(SOURCE_ID, TARGET_ID, preview["plan_identity"])
        assert result["status"] == "UPDATED" and result["changed"] is True
        assert result["migrated_history_count"] == 2
        assert result["target_history_after"] == 3
        assert result["raw_entries_unchanged"] is True
        assert result["remaining_source_references"] == []
        assert result["undo"]["available"] is True
        migrated_tracker = json.loads(tracker.read_text(encoding="utf-8"))
        migrated_dictionary = json.loads(dictionary.read_text(encoding="utf-8"))
        assert not any(item.get("movement_id") == SOURCE_ID for item in migrated_dictionary["movements"])
        assert not any(item.get("movement_id") == SOURCE_ID for item in migrated_tracker["movements"].values())
        assert "legacy-custom-row" not in migrated_tracker["movements"]
        target_definition = next(item for item in migrated_dictionary["movements"] if item["movement_id"] == TARGET_ID)
        target_movement = next(item for item in migrated_tracker["movements"].values() if item["movement_id"] == TARGET_ID)
        assert target_definition["display_name"] == "高位下拉"
        assert target_definition["english_name"] == "Lat Pulldown"
        assert target_definition["muscle_group"] == "Back"
        assert {"旧下拉", "Old Pulldown", "旧式下拉"}.issubset(set(target_definition["aliases"]))
        assert len({_key for _key in map(command_module._normalize_name, target_definition["aliases"])}) == len(target_definition["aliases"])
        assert len(target_movement["history"]) == len(before_histories)
        migrated_by_id = {item["id"]: item for item in target_movement["history"]}
        for original in before_histories:
            migrated = migrated_by_id[original["id"]]
            expected = {**original, "movement_id": TARGET_ID}
            assert migrated == expected
        assert [item["text"] for item in migrated_tracker["raw_entries"]] == before_raw_text
        assert migrated_tracker["raw_entries"][0]["skipped_movements"] == ["旧式下拉"]

        review = service.review_payload(
            {"id": "review", "date": "2099-01-01", "training": {"movements": [{"name": "Old Pulldown"}]}},
            migrated_tracker,
            migrated_dictionary,
        )
        assert review["review"]["training"]["movements"][0]["movement_id"] == TARGET_ID

        payload = build_cloud_payload(LedgerViewModels(tracker, dictionary))
        payload_ids = {item["movement_id"] for item in payload["fl_movement_history"]}
        assert TARGET_ID in payload_ids and SOURCE_ID not in payload_ids
        assert SOURCE_ID not in {item["movement_id"] for item in payload["fl_movements"]}

        stable = runpy.run_path(PROJECT / "stable_app.pyw")
        checker = stable["FitnessTrackerApp"].__new__(stable["FitnessTrackerApp"])
        checker.database = migrated_tracker
        checker.movement_dictionary = migrated_dictionary
        checker.movement_definitions_by_id, checker.movement_definitions_by_alias = stable["movement_definition_index"](
            migrated_dictionary
        )
        issues = checker.collect_data_issues()
        assert not any(SOURCE_ID in json.dumps(issue, ensure_ascii=False) for issue in issues)
        remaining = service._source_reference_paths(migrated_tracker, migrated_dictionary, SOURCE_ID)
        assert remaining["migratable"] == [] and remaining["unknown"] == []

        undo = service.undo_last_write()
        assert undo["undone"] is True
        assert json.loads(tracker.read_text(encoding="utf-8")) == original_tracker
        assert json.loads(dictionary.read_text(encoding="utf-8")) == original_dictionary
        assert list(backups.glob("undone_tracker_*.json"))
        assert list(backups.glob("undone_dictionary_*.json"))

    expect_block(lambda _t, _d: None, "SOURCE_ID_REQUIRED", source_id="")
    expect_block(lambda _t, _d: None, "TARGET_ID_REQUIRED", target_id="")
    expect_block(lambda _t, _d: None, "SOURCE_EQUALS_TARGET", target_id=SOURCE_ID)
    def remove_source(_tracker, dictionary):
        dictionary["movements"] = [item for item in dictionary["movements"] if item["movement_id"] != SOURCE_ID]

    def remove_target(_tracker, dictionary):
        dictionary["movements"] = [item for item in dictionary["movements"] if item["movement_id"] != TARGET_ID]

    def conflict_alias(_tracker, dictionary):
        next(item for item in dictionary["movements"] if item["movement_id"] == "CHEST_001")["aliases"].append("Old Pulldown")

    def conflict_history_id(tracker, _dictionary):
        tracker["movements"][TARGET_ID]["history"][0]["id"] = "source-history-1"

    def unknown_reference(tracker, _dictionary):
        tracker["training_sessions"][0]["movement_id"] = SOURCE_ID

    def unknown_source_field(tracker, _dictionary):
        tracker["movements"]["legacy-custom-row"]["business_metric"] = 42

    def inactive_target(_tracker, dictionary):
        next(item for item in dictionary["movements"] if item["movement_id"] == TARGET_ID)["active"] = False

    def duplicate_source(_tracker, dictionary):
        source = next(item for item in dictionary["movements"] if item["movement_id"] == SOURCE_ID)
        dictionary["movements"].append(copy.deepcopy(source))

    def add_custom_target(_tracker, dictionary):
        dictionary["movements"].append({
            "movement_id": "CUSTOM_999",
            "display_name": "另一个 CUSTOM",
            "english_name": "Another Custom",
            "aliases": [],
            "muscle_group": "Back",
            "active": True,
        })

    expect_block(remove_source, "SOURCE_NOT_UNIQUE")
    expect_block(duplicate_source, "SOURCE_NOT_UNIQUE")
    expect_block(remove_target, "TARGET_NOT_UNIQUE")
    expect_block(conflict_alias, "ALIAS_OWNERSHIP_CONFLICT")
    expect_block(conflict_history_id, "HISTORY_ID_CONFLICT")
    expect_block(unknown_reference, "UNKNOWN_SOURCE_REFERENCE")
    expect_block(unknown_source_field, "SOURCE_ROW_UNKNOWN_FIELDS")
    expect_block(inactive_target, "TARGET_UNAVAILABLE")
    expect_block(lambda _t, _d: None, "SOURCE_NOT_CUSTOM", source_id="CHEST_001")
    expect_block(add_custom_target, "TARGET_IS_CUSTOM", target_id="CUSTOM_999")

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-custom-stale-") as temp:
        service, tracker, _dictionary, backups = make_service(Path(temp))
        preview = service.preview_merge_custom_movement(SOURCE_ID, TARGET_ID)
        current = json.loads(tracker.read_text(encoding="utf-8"))
        current["concurrent_change"] = True
        write_json(tracker, current)
        try:
            service.merge_custom_movement(SOURCE_ID, TARGET_ID, preview["plan_identity"])
            raise AssertionError("stale preview unexpectedly executed")
        except LedgerCommandError as exc:
            assert exc.code == "PREVIEW_STALE"
        assert not backups.exists()

    for failure_stage in ("dictionary", "tracker", "validation"):
        expect_execute_failure(failure_stage)

    print("FITNESS_LEDGER_CUSTOM_MOVEMENT_MERGE_OK")


if __name__ == "__main__":
    main()
