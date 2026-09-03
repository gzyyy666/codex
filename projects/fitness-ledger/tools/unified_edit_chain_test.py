from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import ledger_commands as command_module
from fitness_ledger_core.cloud_payload import build_cloud_payload
from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore
from fitness_ledger_core.record_relations import validate_relations
from fitness_ledger_core.shared_view_models import LedgerViewModels
from ledger_commands import LedgerCommandError, LedgerCommandService
from mobile_viewer.data_access import LedgerDataAccess


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def parser(raw: str, _database: dict, _dictionary: dict) -> dict:
    return {
        "id": "raw-edit-preview",
        "date": "2026-01-02",
        "raw": raw,
        "body": {"weight": 70},
        "diet": {"calories": 1800, "protein": 120, "carbs": 160, "fat": 50},
        "training": {
            "split": "Push",
            "raw": raw,
            "movements": [{"name": "Bench", "movement_id": "M1", "order": 1, "sets": [{"weight": 55, "reps": 8, "sets": 3}], "notes": "changed instance note"}],
        },
    }


class UnifiedEditChainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-unified-edit-")
        root = Path(self.temp.name)
        self.tracker = root / "tracker.json"
        self.dictionary = root / "movement_dictionary.json"
        self.backups = root / "backups"
        self.registry = root / "data_module_definitions.json"
        write_json(self.tracker, {
            "daily_records": [{"id": "body-1", "Date": "2026-01-02", "Weight (kg)": 69, "Notes": ""}],
            "diet_records": [{"id": "diet-1", "Date": "2026-01-02", "Calories (kcal)": 1700, "Protein (g)": 110, "Carbs (g)": 150, "Fat (g)": 45}],
            "training_sessions": [{"id": "session-1", "No.": 1, "Date": "2026-01-02", "Split": "Push", "Raw Record": "old raw", "Standardized Summary": "old summary", "Notes": "session note"}],
            "movements": {"M1": {"movement_id": "M1", "name": "Bench", "history": [{"id": "history-1", "movement_id": "M1", "date": "2026-01-02", "training_day": 1, "order": 1, "sets": [{"weight": 40, "reps": 8, "sets": 3}], "notes": "old instance note"}]}},
            "raw_entries": [{"id": "raw-1", "date": "2026-01-02", "text": "old raw"}],
            "data_module_records": [],
        })
        write_json(self.dictionary, {"movements": [{"movement_id": "M1", "display_name": "Bench", "english_name": "Bench Press", "aliases": ["bench"], "muscle_group": "Chest", "category": "Strength", "notes": "old long note"}]})
        DataModuleDefinitionStore.initialize(self.registry, PROJECT / "tools" / "fixtures" / "data_modules" / "registry.json", backup_dir=root / "registry-backups")
        self.service = LedgerCommandService(self.tracker, self.dictionary, self.backups, parser, self.registry)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_migration_and_all_read_models_share_ids(self) -> None:
        preview = self.service.migration_preview()
        self.assertEqual(preview["target_schema"], "fitness-ledger-relations-v1")
        migrated = self.service.migrate_legacy_state(confirmed=True)
        self.assertTrue(migrated["changed"])
        database, dictionary = self.service.load_state()
        self.assertFalse(validate_relations(database, dictionary))
        history = database["movements"]["M1"]["history"][0]
        self.assertEqual(history["training_session_id"], "session-1")
        self.assertEqual(history["record_day_id"], "day:2026-01-02")
        self.assertTrue(Path(migrated["checkpoint"]).name.startswith("undo_tracker_"))

    def test_base_edit_propagates_to_detail_export_and_cloud(self) -> None:
        self.service.migrate_legacy_state(confirmed=True)
        self.service.update_record("body", "body-1", {"Weight (kg)": 70}, expected_revision=1)
        self.service.update_record("diet", "diet-1", {"Protein (g)": 125, "Carbs (g)": 155}, expected_revision=1)
        self.service.update_record("training", "session-1", {"Split": "Pull", "Notes": "updated session note"}, expected_revision=1)
        try:
            self.service.update_record("body", "body-1", {"Weight (kg)": 71}, expected_revision=1)
        except LedgerCommandError as exc:
            self.assertEqual(exc.code, "REVISION_CONFLICT")
        else:
            self.fail("stale revision was accepted")
        detail = LedgerDataAccess(self.tracker, self.dictionary).get_record_detail("2026-01-02")
        cloud = build_cloud_payload(LedgerViewModels(self.tracker, self.dictionary))
        self.assertEqual(detail["body"]["Weight (kg)"], 70)
        self.assertEqual(detail["diet"]["Protein (g)"], 125)
        self.assertEqual(detail["training"][0]["split"], "Pull")
        self.assertEqual(cloud["fl_daily_records"][0]["Weight (kg)"], 70)
        self.assertEqual(cloud["fl_diet_records"][0]["Protein (g)"], 125)
        self.assertEqual(cloud["fl_training_sessions"][0]["Split"], "Pull")
        self.assertEqual(LedgerViewModels(self.tracker, self.dictionary).training_archive()[0]["Split"], "Pull")
        self.assertIn("data_modules", detail)

    def test_movement_definition_and_instance_notes_are_separate(self) -> None:
        self.service.migrate_legacy_state(confirmed=True)
        self.service.update_movement_definition("M1", {"notes": "new long note"}, expected_revision=1)
        self.service.update_movement_history("M1", "history-1", {"sets_text": "55 x 8 x 3", "notes": "new instance note"}, expected_revision=1)
        database, dictionary = self.service.load_state()
        self.assertEqual(dictionary["movements"][0]["notes"], "new long note")
        self.assertEqual(database["movements"]["M1"]["history"][0]["notes"], "new instance note")
        cloud = build_cloud_payload(LedgerViewModels(self.tracker, self.dictionary))
        self.assertEqual(cloud["fl_movements"][0]["notes"], "new long note")
        self.assertEqual(cloud["fl_movement_history"][0]["notes"], "new instance note")

    def test_day_move_preserves_the_explicit_aggregate_relationship(self) -> None:
        self.service.migrate_legacy_state(confirmed=True)
        self.service.update_record("body", "body-1", {"Date": "2026-01-03"}, expected_revision=1, move_scope="day")
        database, _dictionary = self.service.load_state()
        self.assertEqual(database["daily_records"][0]["record_day_id"], "day:2026-01-03")
        self.assertEqual(database["diet_records"][0]["record_day_id"], "day:2026-01-03")
        self.assertEqual(database["training_sessions"][0]["record_day_id"], "day:2026-01-03")
        self.assertEqual(database["movements"]["M1"]["history"][0]["date"], "2026-01-03")
        self.assertFalse(validate_relations(database, _dictionary))

    def test_raw_edit_requires_diff_confirmation_and_updates_graph(self) -> None:
        self.service.migrate_legacy_state(confirmed=True)
        preview = self.service.preview_training_raw_edit("session-1", "new raw", expected_revision=1)
        self.assertTrue(preview["requires_confirmation"])
        self.assertTrue(preview["diff"]["updated"])
        with self.assertRaises(LedgerCommandError) as error:
            self.service.apply_training_raw_edit(preview, confirmed=False)
        self.assertEqual(error.exception.code, "RAW_EDIT_CONFIRMATION_REQUIRED")
        result = self.service.apply_training_raw_edit(preview, confirmed=True)
        self.assertEqual(result["status"], "UPDATED")
        database, _dictionary = self.service.load_state()
        session = database["training_sessions"][0]
        self.assertEqual(session["Raw Record"], "new raw")
        self.assertGreater(session["revision"], 1)
        self.assertFalse(validate_relations(database, _dictionary))

    def test_module_save_and_mid_write_failure_are_safe(self) -> None:
        preview = self.service.data_module_preview("2026-01-02 腰围 82.5 cm")
        saved = self.service.data_module_save(preview, confirmed=True)
        self.assertTrue(saved["changed"])
        record_id = saved["changed_record_ids"][0]
        record = next(item for item in self.service.load_state()[0]["data_module_records"] if item["record_id"] == record_id)
        self.service.update_data_module_record(record_id, {"value": 83}, expected_revision=record["revision"])
        record_after = next(item for item in self.service.load_state()[0]["data_module_records"] if item["record_id"] == record_id)
        self.assertEqual(record_after["value"], 83)
        before_tracker, before_dictionary = self.tracker.read_bytes(), self.dictionary.read_bytes()
        original_writer = command_module._write_json_atomic
        calls = {"count": 0}

        def fail_second(path, value):
            calls["count"] += 1
            if calls["count"] == 2:
                raise OSError("injected write failure")
            return original_writer(path, value)

        command_module._write_json_atomic = fail_second
        try:
            with self.assertRaises(LedgerCommandError) as error:
                self.service.update_record("body", "body-1", {"Weight (kg)": 71}, expected_revision=1)
            self.assertEqual(error.exception.code, "SAVE_FAILED")
        finally:
            command_module._write_json_atomic = original_writer
        self.assertEqual(self.tracker.read_bytes(), before_tracker)
        self.assertEqual(self.dictionary.read_bytes(), before_dictionary)


if __name__ == "__main__":
    unittest.main()
