"""Regression tests for generic text Data Modules and Daily Entry composition."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore  # noqa: E402
from ledger_commands import LedgerCommandError, LedgerCommandService  # noqa: E402
from web_desktop.backend.server import LedgerWebService  # noqa: E402


REGISTRY_FILE = PROJECT_ROOT / "tools" / "fixtures" / "data_modules" / "registry.json"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def database() -> dict:
    return {"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": [], "data_module_records": []}


class GenericDataModuleContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-generic-module-")
        root = Path(self.temp.name)
        self.tracker = root / "tracker.json"
        self.dictionary = root / "movement_dictionary.json"
        self.definitions = root / "data_module_definitions.json"
        write_json(self.tracker, database())
        write_json(self.dictionary, {"version": "1.0", "movements": []})
        payload = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        payload["modules"].extend([
            {
                "module_id": "mood_state",
                "label": "精神状态",
                "aliases": ["精神状态", "mood"],
                "category_id": "body",
                "data_type": "text",
                "actual_unit": "",
                "display_unit": "",
                "definition_version": 1,
                "status": "active",
                "capabilities": {"recordable": True, "queryable": True, "history_enabled": True, "exportable": True, "analysis_visible": True, "statistics_visible": False, "cloud_syncable": True, "mini_program_visible": True},
                "recording_behavior": {"kind": "scalar", "cardinality": "one_per_day"},
                "presentation": {"section": "body", "slot": "top", "order": 90, "visible_by_default": True, "renderer": "single_metric"},
            },
            {
                "module_id": "recovery_note",
                "label": "恢复备注",
                "aliases": ["恢复备注"],
                "category_id": "extension",
                "data_type": "text",
                "actual_unit": "",
                "display_unit": "",
                "definition_version": 1,
                "status": "active",
                "capabilities": {"recordable": True, "queryable": True, "history_enabled": True, "exportable": True, "analysis_visible": True, "statistics_visible": False, "cloud_syncable": True, "mini_program_visible": True},
                "recording_behavior": {"kind": "scalar", "cardinality": "one_per_day"},
                "presentation": {"section": "extension", "slot": "secondary", "order": 10, "visible_by_default": True, "renderer": "single_metric"},
            },
        ])
        write_json(self.definitions, payload)
        self.service = LedgerCommandService(self.tracker, self.dictionary, root / "backups", lambda *_args: {}, self.definitions)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_text_parser_preserves_complete_multiline_content(self) -> None:
        raw = "2026-09-04 精神状态: 积极度和情绪高但是大脑性能中下，English punctuation!\n第二行：保留 100%"
        preview = self.service.data_module_preview(raw)
        self.assertEqual(preview["candidates"][0]["value"], "积极度和情绪高但是大脑性能中下，English punctuation!\n第二行：保留 100%")
        self.assertEqual(preview["candidates"][0]["module_id"], "mood_state")

    def test_unknown_explicit_text_field_is_a_generic_candidate(self) -> None:
        discovered = self.service.data_module_discover("今日状态: 积极度和情绪高但是大脑性能中下")
        self.assertEqual(discovered["kind"], "new_candidate")
        self.assertEqual(discovered["candidate"]["data_type"], "text")
        self.assertEqual(discovered["candidate"]["value"], "积极度和情绪高但是大脑性能中下")
        self.assertEqual(discovered["candidate"]["suggested_category_id"], "body")

    def test_text_contract_is_exportable_cloud_mini_but_not_numeric_statistics(self) -> None:
        raw = "2026-09-04 精神状态: 积极度和情绪高但是大脑性能中下"
        preview = self.service.data_module_preview(raw)
        saved = self.service.data_module_save(preview, confirmed=True)
        self.assertTrue(saved["changed"])
        self.assertEqual(self.service.data_module_export()["records"][0]["value"], "积极度和情绪高但是大脑性能中下")
        self.assertEqual(self.service.data_module_cloud_payload()["records"][0]["value"], "积极度和情绪高但是大脑性能中下")
        mini = self.service.data_module_mini_contract()
        mood_card = next(item for item in mini["modules"] if item["module_id"] == "mood_state")
        self.assertEqual(mood_card["latest"]["value"], "积极度和情绪高但是大脑性能中下")
        with self.assertRaisesRegex(LedgerCommandError, "Statistics"):
            self.service.data_module_statistics("mood_state")

    def test_daily_entry_review_and_save_share_the_module_preview(self) -> None:
        raw = "2026-09-04 精神状态: 积极度和情绪高但是大脑性能中下"
        write_json(self.tracker, {**database(), "daily_records": [{"Date": "2026-09-04", "Weight (kg)": 70}]})
        web = LedgerWebService(self.tracker, self.dictionary, Path(self.temp.name) / "web-backups", data_module_registry_file=self.definitions)
        standard = web.import_preview({"raw": "2026-09-04 体重: 70", "transport": "daily_entry_board"})
        self.assertIn("mood_state", {item["module"]["module_id"] for item in standard["review"]["data_module_slots"]})
        payload = web.import_preview({"raw": raw, "transport": "daily_entry_board"})
        self.assertEqual(payload["review"]["data_modules"]["candidates"][0]["module"]["category_id"], "body")
        result = web.save_review({"review_id": payload["review_id"], "review": copy.deepcopy(payload["review"]), "save_mode": "overwrite"})
        self.assertTrue(result["data_module_result"]["changed"])
        stored = json.loads(self.tracker.read_text(encoding="utf-8"))
        self.assertEqual(stored["data_module_records"][0]["value"], "积极度和情绪高但是大脑性能中下")

    def test_daily_entry_mixes_core_fields_and_modules_in_one_save(self) -> None:
        raw = "2026-09-05 体重 70\n精神状态: 积极度和情绪高但是大脑性能中下"
        write_json(self.tracker, {**database(), "daily_records": [{"Date": "2026-09-04", "Weight (kg)": 71}]})
        web = LedgerWebService(self.tracker, self.dictionary, Path(self.temp.name) / "web-backups", data_module_registry_file=self.definitions)
        payload = web.import_preview({"raw": raw, "transport": "daily_entry_board"})
        self.assertEqual(payload["review"]["body"]["weight"], 70)
        self.assertEqual(payload["review"]["data_modules"]["candidates"][0]["module_id"], "mood_state")
        result = web.save_review({"review_id": payload["review_id"], "review": copy.deepcopy(payload["review"]), "save_mode": "normal"})
        self.assertTrue(result["body_updated"])
        stored = json.loads(self.tracker.read_text(encoding="utf-8"))
        self.assertIn(70, [row.get("Weight (kg)") for row in stored["daily_records"]])
        self.assertEqual(stored["data_module_records"][0]["date"], "2026-09-05")


if __name__ == "__main__":
    unittest.main()
