from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from ledger_commands import LedgerCommandError  # noqa: E402
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from web_desktop.backend.server import LedgerWebService, load_stable_module  # noqa: E402

from custom_movement_merge_test import SOURCE_ID, fixture_values, make_service  # noqa: E402


def test_independent_promotion() -> None:
    tracker_value, dictionary_value = fixture_values()
    before_raw = copy.deepcopy(tracker_value["raw_entries"])
    before_source_history = copy.deepcopy(tracker_value["movements"]["legacy-custom-row"]["history"])
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-promote-") as temp:
        service, tracker_file, dictionary_file, backups = make_service(
            Path(temp), tracker_value, dictionary_value
        )
        assert service.movement_groups() == ["Chest", "Back"]
        result = service.promote_custom_movement(
            SOURCE_ID,
            {
                "display_name": "独立下拉动作",
                "english_name": "Independent Pulldown",
                "aliases": ["旧式下拉"],
                "muscle_group": "Back",
                "category": "Strength",
                "equipment": "Cable",
            },
        )
        assert result["target_id"] == "BACK_005"
        assert result["migrated_history_count"] == 2
        tracker = json.loads(tracker_file.read_text(encoding="utf-8"))
        dictionary = json.loads(dictionary_file.read_text(encoding="utf-8"))
        assert SOURCE_ID not in json.dumps(tracker, ensure_ascii=False)
        assert SOURCE_ID not in json.dumps(dictionary, ensure_ascii=False)
        assert [
            {key: item.get(key) for key in ("id", "date", "text", "skipped_movements")}
            for item in tracker["raw_entries"]
        ] == [
            {key: item.get(key) for key in ("id", "date", "text", "skipped_movements")}
            for item in before_raw
        ]
        promoted = tracker["movements"]["BACK_005"]
        assert promoted["name"] == "独立下拉动作"
        for original in before_source_history:
            migrated = next(item for item in promoted["history"] if item["id"] == original["id"])
            expected = {
                **{key: value for key, value in original.items() if key != "cardio"},
                "movement_id": "BACK_005",
            }
            assert {key: migrated.get(key) for key in expected} == expected
            assert "cardio" not in migrated
        assert any(
            item["movement_id"] == "BACK_005"
            and item["display_name"] == "独立下拉动作"
            and item["muscle_group"] == "Back"
            for item in dictionary["movements"]
        )
        assert any(path.name.startswith("undo_tracker_") for path in backups.iterdir())


def test_group_validation_and_new_identity() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-groups-") as temp:
        service, tracker_file, dictionary_file, _backups = make_service(Path(temp))
        before_tracker = tracker_file.read_bytes()
        before_dictionary = dictionary_file.read_bytes()
        try:
            service.promote_custom_movement(SOURCE_ID, {"muscle_group": "MadeUp"})
        except LedgerCommandError as exc:
            assert exc.code == "INVALID_MUSCLE_GROUP"
        else:
            raise AssertionError("A free-text group must not be accepted.")
        assert tracker_file.read_bytes() == before_tracker
        assert dictionary_file.read_bytes() == before_dictionary

        result = service.create_movement_definition(
            {"display_name": "新独立胸部动作", "muscle_group": "Chest"}
        )
        assert result["definition"]["movement_id"] == "CHEST_002"
        assert not result["definition"]["movement_id"].startswith("CUSTOM_")


def test_custom_to_canonical_rename_alias_history_progress_chain() -> None:
    tracker_value, dictionary_value = fixture_values()
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-identity-chain-") as temp:
        service, tracker_file, dictionary_file, _backups = make_service(
            Path(temp), tracker_value, dictionary_value
        )
        promoted = service.promote_custom_movement(
            SOURCE_ID,
            {
                "display_name": "独立下拉动作",
                "english_name": "Independent Pulldown",
                "aliases": ["旧式下拉"],
                "muscle_group": "Back",
            },
        )
        target_id = promoted["target_id"]
        current_dictionary = json.loads(dictionary_file.read_text(encoding="utf-8"))
        target = next(item for item in current_dictionary["movements"] if item["movement_id"] == target_id)
        renamed = service.update_movement_definition(
            target_id,
            {
                "display_name": "独立下拉新名称",
                "english_name": "Independent Pulldown",
                "aliases": ["新下拉别名", "旧式下拉"],
                "muscle_group": "Back",
                "category": target.get("category", "Strength"),
                "equipment": target.get("equipment", "Cable"),
            },
            expected_revision=target.get("revision", 1),
        )
        assert renamed["definition"]["movement_id"] == target_id

        views = LedgerViewModels(tracker_file, dictionary_file)
        by_id = views.movement_history_by_id(target_id, limit=8)
        by_alias = views.movement_history("新下拉别名", limit=8)
        progress = views.movement_progress_index()
        assert by_id["movement"]["display_name"] == "独立下拉新名称"
        assert len(by_id["history"]) == 2
        assert len(by_id["progress_history"]) == 2
        assert by_alias["movement"]["movement_id"] == target_id
        assert any(item["movement_id"] == target_id for item in progress)
        assert SOURCE_ID not in json.dumps(
            json.loads(tracker_file.read_text(encoding="utf-8")), ensure_ascii=False
        )
        assert SOURCE_ID not in json.dumps(
            json.loads(dictionary_file.read_text(encoding="utf-8")), ensure_ascii=False
        )


def test_web_and_copy_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-promote-web-") as temp:
        command_service, tracker_file, dictionary_file, backups = make_service(Path(temp))
        service = LedgerWebService(tracker_file, dictionary_file, backups)
        service.commands = command_service
        assert service.movement_groups() == ["Chest", "Back"]
        result = service.promote_custom_movement(
            {"source_id": SOURCE_ID, "definition": {"display_name": "独立下拉动作", "muscle_group": "Back"}}
        )
        assert result["target_id"] == "BACK_005"

    app = (PROJECT / "web_desktop" / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT / "web_desktop" / "frontend" / "styles.css").read_text(encoding="utf-8")
    server = (PROJECT / "web_desktop" / "backend" / "server.py").read_text(encoding="utf-8")
    stable = (PROJECT / "stable_app.pyw").read_text(encoding="utf-8")
    assert 'select name="muscle_group" required' in app
    assert "movementGroupOptions" in app and "/api/movement-groups" in app
    assert "/api/movements/custom-promote" in app and "保存并转为独立正式动作" in app
    assert "这里只会显示已有的非 CUSTOM 正式动作" in app
    assert "/api/movements/custom-promote" in server and "/api/movement-groups" in server
    assert ".overlay .modal>.close" in css and ".drawer>.close" in css and "position:sticky" in css
    assert ".dictionary-form select" in css
    assert "Movement Timeline" in stable
    assert "No structured movement summary." in stable
    assert "issueIsCustomIdentity" in app and "state.dictionaryQuery='CUSTOM_'" in app


def test_resolved_and_superseded_skipped_movements_are_not_reported() -> None:
    stable = load_stable_module()
    tracker, dictionary = fixture_values()

    def collect(database: dict) -> list[dict]:
        checker = stable.FitnessTrackerApp.__new__(stable.FitnessTrackerApp)
        database, dictionary_value, _report = stable.migrate_state(database, dictionary)
        checker.database = database
        checker.movement_dictionary = dictionary_value
        checker.movement_definitions_by_id, checker.movement_definitions_by_alias = stable.movement_definition_index(
            dictionary_value
        )
        return checker.collect_data_issues()

    assert not any("仅保留原始记录" in item["issue"] for item in collect(tracker))
    tracker["raw_entries"][0]["skipped_movements"] = ["完全未知动作"]
    assert any("完全未知动作" in item["issue"] for item in collect(tracker))
    tracker["raw_entries"][0]["superseded"] = True
    assert not any("完全未知动作" in item["issue"] for item in collect(tracker))


if __name__ == "__main__":
    test_independent_promotion()
    test_group_validation_and_new_identity()
    test_custom_to_canonical_rename_alias_history_progress_chain()
    test_web_and_copy_contract()
    test_resolved_and_superseded_skipped_movements_are_not_reported()
    print("FITNESS_LEDGER_MOVEMENT_IDENTITY_UX_OK")
