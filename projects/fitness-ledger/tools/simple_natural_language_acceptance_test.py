"""Acceptance boundary for simple daily natural-language input.

This test intentionally documents the current narrow parser contract.  It
checks that supported facts are recognized, unsupported shorthand is not
invented, and the original text remains available for Review.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from web_desktop.backend.server import LedgerWebService  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class SimpleNaturalLanguageAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-simple-natural-")
        root = Path(self.temp.name)
        tracker = root / "tracker.json"
        dictionary = root / "movement_dictionary.json"
        write_json(
            tracker,
            {
                "daily_records": [],
                "diet_records": [],
                "training_sessions": [],
                "movements": {},
                "raw_entries": [],
                "data_module_records": [],
            },
        )
        write_json(
            dictionary,
            {
                "version": "1.0",
                "movements": [
                    {"movement_id": "press", "display_name": "卧推", "aliases": ["卧推"]}
                ],
            },
        )
        self.service = LedgerWebService(tracker, dictionary, root / "backups")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def preview(self, raw: str) -> dict:
        payload = self.service.import_preview({"raw": raw, "transport": "acceptance"})
        self.assertFalse(payload["write_attempted"])
        self.assertEqual(payload["review"]["raw"], raw)
        return payload["review"]

    def test_weight_is_recognized_and_unsupported_bowel_shorthand_is_safe(self) -> None:
        review = self.preview("\u4eca\u5929\u4f53\u91cd66.4kg")
        self.assertEqual(review["body"]["weight"], 66.4)
        self.assertEqual(review["body"]["bowel_movement"], "")

        review = self.preview("\u4f53\u91cd66.4\uff0c\u672a\u6392\u4fbf")
        self.assertEqual(review["body"]["weight"], 66.4)
        self.assertEqual(review["body"]["bowel_movement"], "\u65e0")

        review = self.preview("\u4eca\u5929\u672a\u6392\u4fbf")
        self.assertEqual(review["body"]["bowel_movement"], "\u65e0")

    def test_unlabelled_diet_cardio_and_training_do_not_get_invented(self) -> None:
        review = self.preview(
            "\u4eca\u59292150\u5343\u5361\uff0c\u86cb\u767d150\uff0c\u78b3\u6c34230\uff0c\u8102\u80aa60"
        )
        self.assertIsNone(review["diet"]["calories"])
        self.assertIsNone(review["diet"]["protein"])
        self.assertEqual(review["diet"]["carbs"], 230.0)
        self.assertEqual(review["diet"]["fat"], 60.0)
        self.assertEqual(review["training"]["movements"], [])

        review = self.preview("\u6709\u6c27 30\u5206\u949f\u8dd1\u6b65\u673a\u722c\u5761")
        self.assertEqual(review["training"]["movements"], [])
        self.assertEqual(review["body"]["cardio_summary"], "")

        review = self.preview("\u4eca\u5929\u5367\u63a860kg 5 5 4")
        self.assertEqual(review["training"]["movements"], [])


if __name__ == "__main__":
    unittest.main()
