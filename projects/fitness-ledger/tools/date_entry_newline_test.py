"""Anonymous regression for aliases inside an explicitly labelled value."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fitness_ledger_core.data_module_engine import RegistryDrivenParser, ModuleRegistry
from natural_language_import_test import anonymous_tracker, write_json


class EntryAliasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-entry-alias-")
        self.addCleanup(self.temp.cleanup)
        self.tracker = Path(self.temp.name) / "tracker.json"
        self.dictionary = self.tracker.parent / "movement_dictionary.json"
        write_json(self.tracker, anonymous_tracker())
        write_json(self.dictionary, {"version": "1.0", "movements": []})
        self.registry = self.tracker.parent / "data_module_definitions.json"
        fixture = json.loads((Path(__file__).parent / "fixtures/data_modules/registry.json").read_text(encoding="utf-8"))
        module = dict(fixture["modules"][0])
        module.update(module_id="cardio_note", label="有氧", aliases=["有氧", "cardio"], data_type="text", actual_unit="", display_unit="", validation_contract={"max_length": 2000})
        module["capabilities"] = {**module["capabilities"], "statistics_visible": False}
        fixture["modules"] = [module]
        write_json(self.registry, fixture)
        from web_desktop.backend.server import LedgerWebService
        self.service = LedgerWebService(self.tracker, self.dictionary, self.tracker.parent / "backups", data_module_registry_file=self.registry)
        self.parser = RegistryDrivenParser(ModuleRegistry.from_dict(fixture))

    def test_preview_preserves_alias_in_value_and_raw(self):
        for ending in ("\n", "\r\n"):
            for value in ("无额外有氧", "有氧完成", "无额外有氧，有氧休息"):
                raw = ending.join(["date:", "2099-12-30", "weight: 70", "cardio: " + value])
                before = (self.tracker.read_bytes(), self.dictionary.read_bytes(), self.registry.read_bytes())
                preview = self.service.import_preview({"raw": raw})
                self.assertEqual(preview["review"]["date"], "2099-12-30")
                self.assertEqual(preview["review"]["raw"], raw)
                candidates = preview["data_modules"]["candidates"]
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0]["value"], value)
                self.assertEqual(before, (self.tracker.read_bytes(), self.dictionary.read_bytes(), self.registry.read_bytes()))

    def test_explicit_repeated_fields_remain_separate(self):
        for separator in (" ", "\n", "\r\n"):
            items = self.parser.parse("2099-12-30\ncardio: walk" + separator + "有氧: cycle")
            self.assertEqual([item.value for item in items], ["walk", "cycle"])

    def test_empty_explicit_field_still_rejected(self):
        from ledger_commands import LedgerCommandError
        with self.assertRaises(LedgerCommandError):
            self.service.import_preview({"raw": "2099-12-30\ncardio:"})


if __name__ == "__main__":
    unittest.main()
