"""Anonymous tests for the desktop natural-language import boundary."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ledger_commands import LedgerCommandError
from web_desktop.backend.server import LedgerWebService


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def anonymous_tracker() -> dict:
    # FormalReadOnlyDataSource expects the same field names as the real local
    # tracker, but this fixture contains no personal data.
    return {
        "daily_records": [
            {
                "Date": "2099-12-31",
                "Weight (kg)": 69.9,
                "Bowel Movement": "yes",
                "Training": "rest",
                "Cardio": "walk",
            }
        ],
        "diet_records": [],
        "training_sessions": [],
        "movements": {},
        "raw_entries": [],
        "data_module_records": [],
    }


class NaturalLanguageImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-natural-import-")
        root = Path(self.temp.name)
        self.tracker = root / "tracker.json"
        self.dictionary = root / "movement_dictionary.json"
        write_json(self.tracker, anonymous_tracker())
        write_json(self.dictionary, {"version": "1.0", "movements": []})
        self.service = LedgerWebService(self.tracker, self.dictionary, root / "backups")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_preview_is_read_only_and_confirm_writes_through_existing_boundary(self) -> None:
        before = self.tracker.read_bytes()
        preview = self.service.import_preview(
            {"raw": "2099-12-30 体重 70 kg", "transport": "paste"}
        )

        self.assertEqual(preview["schema"], "fitness-ledger-natural-language-import-preview-v1")
        self.assertEqual(preview["source"]["kind"], "natural_language_import")
        self.assertFalse(preview["write_attempted"])
        self.assertEqual(preview["review"]["date"], "2099-12-30")
        self.assertEqual(preview["review"]["body"]["weight"], 70.0)
        self.assertEqual(before, self.tracker.read_bytes())

        result = self.service.import_confirm(
            {"review_id": preview["review_id"], "review": preview["review"]}
        )

        self.assertEqual(result["source_kind"], "natural_language_import")
        self.assertEqual(result["status"], "CREATED")
        self.assertTrue(result["changed"])
        saved = json.loads(self.tracker.read_text(encoding="utf-8"))
        self.assertEqual(saved["raw_entries"][0]["text"], "2099-12-30 体重 70 kg")
        self.assertEqual(saved["daily_records"][-1]["Weight (kg)"], 70.0)

    def test_confirm_rejects_changed_preserved_raw_input(self) -> None:
        preview = self.service.import_preview({"raw": "2099-12-29 体重 70 kg"})
        changed = copy.deepcopy(preview["review"])
        changed["raw"] = "2099-12-29 体重 71 kg"

        with self.assertRaisesRegex(LedgerCommandError, "identity or preserved raw"):
            self.service.import_confirm(
                {"review_id": preview["review_id"], "review": changed}
            )

        self.assertEqual(len(json.loads(self.tracker.read_text(encoding="utf-8"))["raw_entries"]), 0)

    def test_empty_import_is_rejected_before_parse(self) -> None:
        with self.assertRaisesRegex(LedgerCommandError, "请先粘贴或输入"):
            self.service.import_preview({"raw": "  "})


if __name__ == "__main__":
    unittest.main()
