"""Anonymous A/B test for direct Chinese and English-pivot intent parsing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fitness_ledger_core.intelligent_export_models import IntentSpec
from fitness_ledger_core.intent_interpreter import (
    IntentInterpreter,
    IntentSemanticValidator,
    parse_json_object,
)
from fitness_ledger_core.local_model_adapter import INTENT_MODEL_CONFIG, OllamaNativeAdapter


CATALOG = {
    "date_range": {"start": "2026-01-01", "end": "2026-07-23"},
    "modules": [{"module_id": item} for item in ("body", "diet", "training", "movement_history", "raw_entries")],
    "budget_mode": "standard",
}

TRANSLATE_PROMPT = (
    "Translate the Chinese request into a lossless concise English semantic paraphrase. "
    "Preserve negation scope, relative dates as words, relation words, body-part and "
    "exercise mentions. Add nothing. Do not output IDs, data, modules, fields, records, "
    "notes, or normalized dates. Return one JSON object with semantic_english and "
    "preserved_phrases."
)
TRANSLATE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "semantic_english": {"type": "string"},
        "preserved_phrases": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["semantic_english", "preserved_phrases"],
}

CASES = [
    ("diet_body", "分析一下最近的饮食和体重变化", {"body_state", "diet_macros"}, {"trend", "comparison"}),
    ("low_carb_bench", "分析最近低碳是否导致卧推表现下降", {"diet_macros", "movement_progress", "training_context"}, {"impact"}),
    ("shoulder_trend", "看看最近肩部训练有没有进步", {"training_context", "movement_progress"}, {"trend"}),
    ("fat_loss_training", "看看我最近减脂怎么样，训练有没有受影响", {"body_state", "diet_macros", "training_context"}, {"impact"}),
    ("body_trend", "看看最近体重趋势", {"body_state"}, {"trend"}),
    ("vague", "帮我看看最近怎么样", set(), set()),
    ("explicit_date", "分析2026年7月的饮食和体重", {"body_state", "diet_macros"}, set()),
    ("legacy_alias", "看看上周体重和饮食的变化", {"body_state", "diet_macros"}, {"trend", "comparison"}),
    ("notes_only", "总结最近的训练备注", {"training_notes"}, {"summary"}),
    ("negative_scope", "只想看饮食宏量，不要训练", {"diet_macros"}, set()),
    ("growth_relation", "分析训练水平增长程度与饮食的关系", {"diet_macros", "training_context", "movement_progress"}, {"correlation"}),
    ("last_week", "比较上周和这周的体重变化", {"body_state"}, {"comparison", "trend"}),
]


def raw_intent(raw: dict) -> IntentSpec | None:
    try:
        IntentInterpreter._validate_raw_model_boundary(raw)
        intent = IntentSpec.from_dict(raw)
        return intent if IntentSemanticValidator().validate(intent).is_valid else None
    except Exception:
        return None


def score(intent: IntentSpec | None, dimensions: set[str], relationships: set[str], vague: bool) -> tuple[bool, bool, bool]:
    if intent is None:
        return False, False, False
    return (
        set(intent.analysis_dimensions) == dimensions,
        set(intent.relationship_types) == relationships,
        bool(intent.needs_fallback and not intent.analysis_dimensions and not intent.relationship_types and intent.warnings)
        if vague
        else not intent.needs_fallback,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--no-stability", action="store_true")
    args = parser.parse_args()
    adapter = OllamaNativeAdapter(model="qwen3:4b", keep_alive="10m")
    cases = CASES[:6] if args.quick else CASES
    rows: list[dict] = []
    for case_id, request, dimensions, relationships in cases:
        direct = None
        direct_raw = None
        direct_error = ""
        try:
            direct, result = IntentInterpreter(adapter).interpret(request, CATALOG)
            direct_raw = raw_intent(parse_json_object(result.raw_text))
        except Exception as exc:
            direct_error = type(exc).__name__

        translation = ""
        phrases: list[str] = []
        pivot = None
        pivot_error = ""
        try:
            result = adapter.generate_json(
                system_prompt=TRANSLATE_PROMPT,
                user_payload={"request": request},
                response_schema=TRANSLATE_SCHEMA,
                config=INTENT_MODEL_CONFIG,
            )
            translated = json.loads(result.raw_text)
            translation = str(translated.get("semantic_english", "")).strip()
            phrases = list(translated.get("preserved_phrases", []))
            _, parsed = IntentInterpreter(adapter).interpret(translation, CATALOG)
            pivot = raw_intent(parse_json_object(parsed.raw_text))
        except Exception as exc:
            pivot_error = type(exc).__name__

        rows.append(
            {
                "id": case_id,
                "translation": translation,
                "preserved_phrases": phrases,
                "direct_final": score(direct, dimensions, relationships, case_id == "vague"),
                "direct_raw": score(direct_raw, dimensions, relationships, case_id == "vague"),
                "pivot_raw": score(pivot, dimensions, relationships, case_id == "vague"),
                "direct_dimensions": list(direct.analysis_dimensions) if direct else [],
                "direct_relationships": list(direct.relationship_types) if direct else [],
                "pivot_dimensions": list(pivot.analysis_dimensions) if pivot else [],
                "pivot_relationships": list(pivot.relationship_types) if pivot else [],
                "errors": {"direct": direct_error, "pivot": pivot_error},
            }
        )

    stability: dict[str, bool] = {}
    if not args.no_stability:
        for case_id, request, _, _ in cases:
            outputs = []
            for _ in range(3):
                try:
                    intent, _ = IntentInterpreter(adapter).interpret(request, CATALOG)
                    outputs.append(json.dumps(intent.to_dict(), ensure_ascii=False, sort_keys=True))
                except Exception as exc:
                    outputs.append(f"ERROR:{type(exc).__name__}")
            stability[case_id] = len(set(outputs)) == 1

    for row in rows:
        print(json.dumps(row, ensure_ascii=True, separators=(",", ":")))
    print(
        "SUMMARY "
        + json.dumps(
            {
                "cases": len(rows),
                "direct_final_exact": sum(all(row["direct_final"]) for row in rows),
                "direct_raw_exact": sum(all(row["direct_raw"]) for row in rows),
                "pivot_raw_exact": sum(all(row["pivot_raw"]) for row in rows),
                "stable_cases_3_runs": sum(stability.values()),
                "stability": stability,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
