from __future__ import annotations

import json
import unittest
from pathlib import Path

from local_semantic_request_interpreter_lab.core import DraftError, compile_request_draft, interpret_request, parse_json_strict, validate_request_draft, validate_request_grounding


ROOT = Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "data" / "capability_catalog.json").read_text(encoding="utf-8"))


def good_draft() -> dict:
    return {
        "schema_version": "fitness-ledger-request-draft-v1",
        "status": "ready",
        "purpose": "比较最近三次胸训的训练容量，并结合此前饮食交给 GPT 分析。",
        "datasets": [
            {"draft_id": "target_training", "kind": "training", "scope": {"body_part": "chest"}, "time_intent": {"type": "latest_matching_sessions", "count": 3}, "requested_information": ["session", "movements", "sets"], "notes": {"requested": False, "scopes": []}},
            {"draft_id": "preceding_diet", "kind": "diet", "scope": {}, "time_intent": {"type": "before_each_target_event", "target_draft_id": "target_training", "days_before": 3, "include_target_day": False}, "requested_information": ["energy", "carbohydrate"], "notes": {"requested": False, "scopes": []}},
        ],
        "relations": [{"type": "preceding_event_window", "source_draft_id": "target_training", "dependent_draft_id": "preceding_diet"}],
        "missing_confirmations": [],
        "warnings": [],
    }


class LabTests(unittest.TestCase):
    def test_valid_draft_and_compile_is_read_only(self):
        draft = validate_request_draft(good_draft(), CATALOG)
        compiled = compile_request_draft(draft, CATALOG)
        self.assertFalse(compiled["execution"]["allowed"])
        self.assertFalse(compiled["execution"]["executor_called"])
        self.assertFalse(compiled["execution"]["write_allowed"])
        self.assertFalse(compiled["execution"]["raw"])

    def test_unknown_field_fails_closed(self):
        draft = good_draft()
        draft["datasets"][0]["unknown"] = True
        with self.assertRaises(DraftError):
            validate_request_draft(draft, CATALOG)

    def test_raw_and_duplicate_json_fail_closed(self):
        draft = good_draft()
        draft["raw"] = True
        with self.assertRaises(DraftError):
            validate_request_draft(draft, CATALOG)
        with self.assertRaises(DraftError):
            parse_json_strict('{"a": 1, "a": 2}')

    def test_model_unavailable_fails_closed(self):
        result = interpret_request("导出最近饮食", CATALOG)
        self.assertEqual(result["status"], "model_unavailable")
        self.assertIsNone(result["draft"])

    def test_before_window_requires_relation(self):
        draft = good_draft()
        draft["relations"] = []
        with self.assertRaises(DraftError):
            validate_request_draft(draft, CATALOG)

    def test_grounding_rejects_expanded_scope(self):
        draft = good_draft()
        draft["datasets"][0]["scope"]["movement"] = "bench_press"
        draft["datasets"][0]["scope"]["split"] = "push"
        draft["datasets"][0]["time_intent"] = {"type": "recent_days", "days": 90}
        with self.assertRaises(DraftError):
            validate_request_grounding(draft, "最近三次胸训和每次训练前三天的饮食，给 GPT 分析训练容量变化。")


if __name__ == "__main__":
    unittest.main()
