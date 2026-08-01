from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.restricted_export_integration import compile_natural_language_export


class FakeViews:
    def __init__(self, tracker: dict, dictionary: dict, training_splits: list[str]) -> None:
        self._tracker = tracker
        self._dictionary = dictionary
        self._analysis = {
            "body": [],
            "diet": [],
            "training": [{"Date": "2026-07-31", "Split": value} for value in training_splits],
            "raw_entries": [],
        }
        self._temp = tempfile.TemporaryDirectory()
        root = Path(self._temp.name)
        self.tracker_file = root / "tracker.json"
        self.dictionary_file = root / "movement_dictionary.json"
        self.tracker_file.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
        self.dictionary_file.write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")

    def snapshot(self):
        return json.loads(json.dumps(self._tracker)), json.loads(json.dumps(self._dictionary))

    def analysis(self, **_kwargs):
        return json.loads(json.dumps(self._analysis))

    def close(self) -> None:
        self._temp.cleanup()


def fake_views() -> FakeViews:
    dictionary = {
        "movements": [
            {
                "movement_id": "BACK_009",
                "display_name": "单臂绳索下拉",
                "english_name": "One Arm Pulldown",
                "aliases": ["单臂下拉"],
                "synonyms": ["单臂拉"],
                "name_aliases": ["单臂动作"],
                "alternate_names": ["OAP"],
                "muscle_group": "Back",
                "active": True,
            },
            {
                "movement_id": "SHOULDER_003",
                "display_name": "器械中束飞鸟",
                "aliases": ["飞鸟"],
                "muscle_group": "Shoulder",
                "active": True,
            },
            {
                "movement_id": "CHEST_010",
                "display_name": "哑铃飞鸟",
                "aliases": ["飞鸟"],
                "muscle_group": "Chest",
                "active": True,
            },
        ]
    }
    tracker = {
        "movements": {
            "back": {
                "movement_id": "BACK_009",
                "history": [{"id": "h1", "date": "2026-07-31", "sets": []}],
            },
            "shoulder": {
                "movement_id": "SHOULDER_003",
                "history": [{"id": "h2", "date": "2026-07-31", "sets": []}],
            },
            "chest": {
                "movement_id": "CHEST_010",
                "history": [{"id": "h3", "date": "2026-07-31", "sets": []}],
            },
        }
    }
    return FakeViews(tracker, dictionary, ["背部", "胸部", "肩部"])


class RestrictedExportIntegrationTests(unittest.TestCase):
    def test_formal_alias_fields_and_training_body_part_are_projected(self) -> None:
        views = fake_views()
        self.addCleanup(views.close)
        result = compile_natural_language_export(
            views,
            "导出最近4次单臂动作表现",
        )
        request = result["requests"][0]
        self.assertEqual(result["status"], "ready")
        self.assertEqual(request["output"], {"formats": ["json"]})
        self.assertEqual(
            request["datasets"][0]["filters"]["movement_selector"],
            {"kind": "movement_id", "value": "BACK_009"},
        )

        training = compile_natural_language_export(views, "导出最近30天背部训练")
        self.assertEqual(training["requests"][0]["datasets"][0]["filters"], {"body_part": "背"})

    def test_ambiguous_alias_requires_guided_selection_then_resolves(self) -> None:
        views = fake_views()
        self.addCleanup(views.close)
        pending = compile_natural_language_export(views, "导出最近4次飞鸟动作表现")
        self.assertEqual(pending["status"], "needs_clarification")
        self.assertGreaterEqual(len(pending["candidates"]), 2)
        self.assertEqual(pending["requests"], [])

        resolved = compile_natural_language_export(
            views,
            "导出最近4次飞鸟动作表现",
            ["SHOULDER_003"],
        )
        self.assertEqual(resolved["status"], "ready")
        self.assertEqual(
            resolved["requests"][0]["datasets"][0]["filters"]["movement_selector"]["value"],
            "SHOULDER_003",
        )

    def test_body_part_discovery_is_stage_a_only_until_selected(self) -> None:
        views = fake_views()
        self.addCleanup(views.close)
        pending = compile_natural_language_export(views, "导出最近4次背部动作表现")
        self.assertEqual(pending["status"], "candidate_confirmation_required")
        self.assertEqual(pending["requests"], [])
        selected = compile_natural_language_export(views, "导出最近4次背部动作表现", ["BACK_009"])
        self.assertEqual(selected["status"], "ready")
        self.assertEqual(len(selected["requests"][0]["datasets"]), 1)


if __name__ == "__main__":
    unittest.main()
