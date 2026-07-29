"""Grounded Semantic Hints adapter contract tests; no real model or tracker."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.intelligent_export_models import ContractError, SemanticHints, semantic_hints_json_schema
from fitness_ledger_core.intent_interpreter import IntentInterpreter, parse_json_object
from fitness_ledger_core.local_model_adapter import FakeLocalModelAdapter


def response(hints=None):
    return {
        "schema_version": "fitness-ledger-semantic-hints-v1",
        "semantic_hints": [{"dimension": dimension, "evidence": evidence} for dimension, evidence in (hints or [])],
    }


def main() -> None:
    schema = semantic_hints_json_schema()
    assert set(schema["required"]) == {"schema_version", "semantic_hints"}
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]["semantic_hints"]["items"]["required"]) == {"dimension", "evidence"}

    parsed, _ = IntentInterpreter(FakeLocalModelAdapter([response([("diet_macros", "饮食")])])).interpret("看看饮食", semantic_context={})
    assert parsed.dimensions == ["diet_macros"]

    markdown_payload = json.dumps(response([("body_state", "体重")]), ensure_ascii=False)
    parsed, _ = IntentInterpreter(FakeLocalModelAdapter([f"```json\n{markdown_payload}\n```"])).interpret("看看体重", semantic_context={})
    assert parsed.dimensions == ["body_state"]

    bad_cases = [
        ({**response([("body_state", "体重")]), "extra": True}, "MODEL_SCHEMA_EXTRA_FIELD"),
        (response([("unknown_dimension", "饮食")]), "MODEL_SEMANTIC_HINT_ENUM"),
        (response([("diet_macros", "CHEST_006")]), "MODEL_INTENT_DATA_ID"),
        ("{\"schema_version\": \"fitness-ledger-semantic-hints-v1\"", "MODEL_OUTPUT_TRUNCATED"),
    ]
    for raw, expected in bad_cases:
        try:
            IntentInterpreter(FakeLocalModelAdapter([raw])).interpret("测试饮食", semantic_context={})
        except ContractError as exc:
            assert exc.code == expected, (expected, exc.code)
        else:
            raise AssertionError(f"contract violation accepted: {expected}")

    hints = SemanticHints.from_dict(response([("body_state", "体重")]))
    assert hints.to_dict()["semantic_hints"][0]["evidence"] == "体重"
    assert parse_json_object(json.dumps(response([]), ensure_ascii=False))["semantic_hints"] == []
    print("FITNESS_LEDGER_INTENT_ADAPTER_CONTRACT_OK")


if __name__ == "__main__":
    main()
