"""Anonymous fixture tests for the registry-driven Data Module candidate."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.data_module_engine import (
    DataModuleEngine,
    DataModuleError,
    DataModuleDefinitionStore,
    DataModuleMigrationService,
    ModuleDefinition,
    ModuleRegistry,
    RegistryDrivenParser,
    stable_hash,
)
from ledger_commands import LedgerCommandService


ROOT = PROJECT_ROOT
REGISTRY_FILE = ROOT / "tools" / "fixtures" / "data_modules" / "registry.json"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def sample_database() -> dict:
    return {
        "daily_records": [],
        "diet_records": [],
        "training_sessions": [],
        "movements": {},
        "raw_entries": [],
        "data_module_records": [],
    }


def sample_dictionary() -> dict:
    return {"version": "1.0", "movements": []}


class DataModuleCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-data-module-")
        root = Path(self.temp.name)
        self.tracker = root / "tracker.json"
        self.dictionary = root / "movement_dictionary.json"
        self.backups = root / "backups"
        self.definition_store = root / "data_module_definitions.json"
        write_json(self.tracker, sample_database())
        write_json(self.dictionary, sample_dictionary())
        DataModuleDefinitionStore.initialize(self.definition_store, REGISTRY_FILE, backup_dir=root / "definition-backups")
        self.service = LedgerCommandService(
            self.tracker,
            self.dictionary,
            self.backups,
            lambda *_args: {},
            self.definition_store,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_full_numeric_lifecycle_is_registry_driven(self) -> None:
        before_tracker = self.tracker.read_bytes()
        before_dictionary = self.dictionary.read_bytes()
        preview = self.service.data_module_preview("2026-08-12 腰围 82.5 cm；静息心率 62 bpm")
        self.assertEqual(preview["status"], "preview_ready")
        self.assertFalse(preview["write_attempted"])
        self.assertEqual({item["module_id"] for item in preview["candidates"]}, {"waist_cm", "resting_hr"})
        self.assertEqual(before_tracker, self.tracker.read_bytes())
        self.assertEqual(before_dictionary, self.dictionary.read_bytes())

        saved = self.service.data_module_save(preview, confirmed=True)
        self.assertTrue(saved["changed"])
        self.assertEqual(saved["created_count"], 2)
        self.assertEqual(saved["updated_count"], 0)
        self.assertTrue(saved["raw_preserved"])
        database, _dictionary = self.service.load_state()
        self.assertEqual(len(database["data_module_records"]), 2)
        self.assertEqual(len(database["raw_entries"]), 1)
        self.assertEqual(database["raw_entries"][0]["text"], "2026-08-12 腰围 82.5 cm；静息心率 62 bpm")
        self.assertTrue(self.service.undo_status()["available"])

        waist = self.service.data_module_query("waist_cm", latest=True)
        self.assertEqual(waist[0]["display_value"], 82.5)
        self.assertEqual(waist[0]["display_unit"], "cm")
        history = self.service.data_module_history("resting_hr")
        self.assertEqual(history["latest"]["value"], 62)
        self.assertEqual(len(self.service.data_module_export()["records"]), 2)

        catalog = self.service.data_module_analysis_catalog()
        self.assertEqual([item["module_id"] for item in catalog["modules"]], ["waist_cm"])
        with self.assertRaisesRegex(Exception, "hidden"):
            self.service.data_module_analysis_preview(["resting_hr"])
        analysis = self.service.data_module_analysis_preview(["waist_cm"])
        self.assertFalse(analysis["public_protocol_changed"])
        self.assertEqual(analysis["rows"][0]["extension.waist_cm"], 82.5)

        cloud_first = self.service.data_module_cloud_payload()
        cloud_second = self.service.data_module_cloud_payload()
        self.assertEqual(cloud_first, cloud_second)
        self.assertFalse(cloud_first["meta"]["network_request_made"])
        self.assertEqual(cloud_first["meta"]["raw_policy"], "excluded")
        self.assertNotIn("source_raw_hash", cloud_first["records"][0])
        verification = self.service.data_module_cloud_verify(cloud_first)
        self.assertTrue(verification["verified"])
        roundtrip = self.service.data_module_cloud_roundtrip(cloud_first)
        self.assertEqual(roundtrip["payload_hash"], cloud_first["meta"]["payload_hash"])
        leaked = copy.deepcopy(cloud_first)
        leaked["records"][0]["private"] = "must never upload"
        self.assertFalse(self.service.data_module_cloud_verify(leaked)["verified"])
        mini = self.service.data_module_mini_contract()
        self.assertEqual(set(mini["renderers"]), {"single_metric", "metric_history"})
        self.assertEqual(len(mini["modules"]), 2)
        self.assertEqual(len(self.service.data_module_presentation_contract()["modules"]), 2)

        no_change_preview = self.service.data_module_preview("2026-08-12 腰围 82.5 cm")
        no_change = self.service.data_module_save(no_change_preview, confirmed=True)
        self.assertEqual(no_change["status"], "NO_CHANGES")
        self.assertFalse(no_change["write_attempted"])

    def test_second_and_third_module_use_the_same_chain(self) -> None:
        registry = ModuleRegistry.from_file(REGISTRY_FILE)
        third = ModuleDefinition.from_dict(
            {
                "module_id": "body_fat_pct",
                "label": "体脂率",
                "aliases": ["体脂率", "body fat"],
                "category_id": "extension",
                "data_type": "quantity",
                "actual_unit": "%",
                "display_unit": "%",
                "definition_version": 1,
                "status": "active",
                "capabilities": {
                    "recordable": True,
                    "queryable": True,
                    "history_enabled": True,
                    "exportable": True,
                    "analysis_visible": False,
                    "cloud_syncable": False,
                    "mini_program_visible": False,
                },
                "validation_contract": {"minimum": 1, "maximum": 80, "decimal_places": 1},
                "recording_behavior": {"kind": "scalar", "cardinality": "one_per_day"},
                "presentation": {"section": "extension", "slot": "secondary", "order": 30, "renderer": "single_metric"},
            }
        )
        registry.register(third)
        engine = DataModuleEngine(registry, self.tracker, self.dictionary, self.backups, self.service)
        preview = engine.preview("2026-08-13 body fat 18.5 %")
        self.assertEqual(preview["candidates"][0]["module_id"], "body_fat_pct")
        saved = engine.save_preview(preview, confirmed=True)
        self.assertTrue(saved["changed"])
        self.assertEqual(engine.query("body_fat_pct", latest=True)[0]["value"], 18.5)
        self.assertEqual({row["module_id"] for row in engine.normal_export()["records"]}, {"body_fat_pct"})

    def test_unitless_module_and_definition_delete_remove_candidate_records(self) -> None:
        category_preview = self.service.data_module_definition_preview({
            "kind": "category",
            "action": "create",
            "values": {"category_id": "review_delete_category", "label": "Review Delete Category"},
        })
        self.service.data_module_definition_save(category_preview, confirmed=True)
        module_preview = self.service.data_module_definition_preview({
            "kind": "module",
            "action": "create",
            "values": {
                "module_id": "review_unitless_module",
                "label": "Unitless Review Metric",
                "aliases": ["Unitless Review Metric", "unitless metric"],
                "category_id": "review_delete_category",
                "actual_unit": "",
                "display_unit": "",
                "data_type": "number",
                "presentation": {"section": "extension", "slot": "summary"},
            },
        })
        self.service.data_module_definition_save(module_preview, confirmed=True)
        preview = self.service.data_module_preview("2026-08-12 unitless metric 7")
        self.service.data_module_save(preview, confirmed=True)
        delete_module = self.service.data_module_definition_preview({"kind": "module", "action": "delete", "module_id": "review_unitless_module"})
        saved = self.service.data_module_definition_save(delete_module, confirmed=True)
        self.assertEqual(saved["deleted_record_count"], 1)
        database, _dictionary = self.service.load_state()
        self.assertFalse(any(item.get("module_id") == "review_unitless_module" for item in database["data_module_records"]))
        delete_category = self.service.data_module_definition_preview({"kind": "category", "action": "delete", "category_id": "review_delete_category"})
        self.service.data_module_definition_save(delete_category, confirmed=True)
        self.assertNotIn("review_delete_category", {item["category_id"] for item in self.service.data_module_product_catalog()["categories"]})

    def test_registry_collisions_versions_and_unit_gate(self) -> None:
        registry = ModuleRegistry.from_file(REGISTRY_FILE)
        with self.assertRaisesRegex(DataModuleError, "alias"):
            registry.register(ModuleDefinition.from_dict({
                "module_id": "waist_alias_collision",
                "label": "其他",
                "aliases": ["腰围"],
                "category_id": "extension",
                "data_type": "text",
                "actual_unit": "",
                "display_unit": "",
                "definition_version": 1,
                "status": "active",
                "capabilities": {"mini_program_visible": False},
                "validation_contract": {},
                "recording_behavior": {"kind": "scalar", "cardinality": "one_per_day"},
                "presentation": {"section": "extension", "slot": "summary", "order": 99},
            }))
        with self.assertRaisesRegex(DataModuleError, "immutable"):
            registry.preview_update("waist_cm", {"module_id": "renamed_waist"})
        with self.assertRaisesRegex(DataModuleError, "migration"):
            registry.preview_update("waist_cm", {"actual_unit": "m"})
        current, renamed = registry.preview_update("waist_cm", {"label": "腰围记录", "aliases": ["腰围记录", "waist record"], "category_id": "extension", "display_unit": "厘米", "status": "retired", "capabilities": {"recordable": False}})
        self.assertEqual(renamed.definition_version, current.definition_version + 1)
        self.assertEqual(renamed.definition_history[-1]["label"], "腰围")
        registry.update("waist_cm", {"label": "腰围记录", "aliases": ["腰围记录", "waist record"], "category_id": "extension", "display_unit": "厘米", "status": "retired", "capabilities": {"recordable": False}})
        reenabled = registry.update("waist_cm", {"status": "active", "capabilities": {"recordable": True}})
        self.assertEqual(reenabled.status, "active")
        self.assertGreaterEqual(reenabled.definition_version, 3)

    def test_migration_fixture_is_explicit_rollback_safe_and_idempotent(self) -> None:
        registry = ModuleRegistry.from_file(REGISTRY_FILE)
        definition = registry.require("waist_cm")
        database = {
            "data_module_records": [{
                "record_id": "dm:waist_cm:2026-08-12:0",
                "module_id": "waist_cm",
                "date": "2026-08-12",
                "value": 82.5,
                "actual_unit": "cm",
                "definition_version": 1,
                "definition_snapshot": definition.snapshot(),
            }]
        }
        migrations = DataModuleMigrationService(registry)
        blocked = migrations.preview("waist_cm", {"actual_unit": "m"}, database)
        self.assertFalse(blocked["can_execute_on_fixture"])
        plan = migrations.preview(
            "waist_cm",
            {"actual_unit": "m", "display_unit": "m", "value_migration": {"factor": 0.01, "offset": 0}},
            database,
        )
        updated_registry, updated_database = migrations.apply_fixture(plan, registry, database)
        self.assertEqual(updated_database["data_module_records"][0]["value"], 0.825)
        self.assertEqual(updated_database["data_module_records"][0]["actual_unit"], "m")
        self.assertEqual(updated_registry.require("waist_cm").actual_unit, "m")
        restored_registry, restored_database = migrations.rollback_fixture(plan, updated_registry, updated_database)
        self.assertEqual(stable_hash(restored_database["data_module_records"]), stable_hash(database["data_module_records"]))
        self.assertEqual(restored_registry.require("waist_cm").actual_unit, "cm")
        with self.assertRaisesRegex(DataModuleError, "stale"):
            migrations.apply_fixture(plan, updated_registry, updated_database)
        corrupt = copy.deepcopy(database)
        corrupt["data_module_records"][0]["value"] = 9999
        self.assertTrue(any(issue["severity"] == "high" for issue in DataModuleEngine(registry, self.tracker).data_check(corrupt)))

    def test_preview_stale_and_paired_write_rollback(self) -> None:
        preview = self.service.data_module_preview("2026-08-12 腰围 82.5 cm")
        database = json.loads(self.tracker.read_text(encoding="utf-8"))
        database["daily_records"].append({"Date": "2026-08-13", "Weight": 70})
        write_json(self.tracker, database)
        with self.assertRaisesRegex(DataModuleError, "stale"):
            self.service.data_module_engine().save_preview(preview, confirmed=True)

        preview = self.service.data_module_preview("2026-08-12 腰围 82.5 cm")
        before_tracker = self.tracker.read_bytes()
        before_dictionary = self.dictionary.read_bytes()
        import ledger_commands

        with mock.patch.object(ledger_commands, "_write_json_atomic", side_effect=OSError("fixture write failure")):
            with self.assertRaisesRegex(Exception, "write"):
                self.service.data_module_engine().save_preview(preview, confirmed=True)
        self.assertEqual(before_tracker, self.tracker.read_bytes())
        self.assertEqual(before_dictionary, self.dictionary.read_bytes())

    def test_unsupported_future_recording_is_explicitly_deferred(self) -> None:
        registry = ModuleRegistry.from_file(REGISTRY_FILE)
        definition = registry.require("resting_hr")
        future = copy.deepcopy(definition.to_dict())
        future["module_id"] = "sleep_session"
        future["label"] = "睡眠时段"
        future["aliases"] = ["睡眠时段"]
        future["data_type"] = "structured"
        future["actual_unit"] = ""
        future["display_unit"] = ""
        future["recording_behavior"] = {"kind": "session", "cardinality": "many_per_session"}
        future["capabilities"]["mini_program_visible"] = False
        future["presentation"]["renderer"] = "metric_history"
        registry.register(ModuleDefinition.from_dict(future))
        engine = DataModuleEngine(registry, self.tracker)
        with self.assertRaisesRegex(DataModuleError, "failed validation"):
            engine.preview("2026-08-12 睡眠时段 22:00")


if __name__ == "__main__":
    unittest.main()
