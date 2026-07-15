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
        assert tracker["raw_entries"] == before_raw
        promoted = tracker["movements"]["BACK_005"]
        assert promoted["name"] == "独立下拉动作"
        assert [
            {key: value for key, value in row.items() if key != "movement_id"}
            for row in promoted["history"]
        ] == [
            {key: value for key, value in row.items() if key != "movement_id"}
            for row in before_source_history
        ]
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
    assert "只有确为同一动作时才合并" in app
    assert "/api/movements/custom-promote" in server and "/api/movement-groups" in server
    assert ".overlay .modal>.close" in css and ".drawer>.close" in css and "position:sticky" in css
    assert ".dictionary-form select" in css
    assert "没有可用于成长曲线的组数或有氧数据" in stable
    assert "当时选择了“仅保留原始记录”" in stable
    assert "issueIsCustomIdentity" in app and "state.dictionaryQuery='CUSTOM_'" in app


def test_resolved_and_superseded_skipped_movements_are_not_reported() -> None:
    stable = load_stable_module()
    tracker, dictionary = fixture_values()

    def collect(database: dict) -> list[dict]:
        checker = stable.FitnessTrackerApp.__new__(stable.FitnessTrackerApp)
        checker.database = database
        checker.movement_dictionary = dictionary
        checker.movement_definitions_by_id, checker.movement_definitions_by_alias = stable.movement_definition_index(
            dictionary
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
    test_web_and_copy_contract()
    test_resolved_and_superseded_skipped_movements_are_not_reported()
    print("FITNESS_LEDGER_MOVEMENT_IDENTITY_UX_OK")
