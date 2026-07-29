"""The single local-model semantic boundary for Intelligent Export."""

from __future__ import annotations

import json
import re

from .intelligent_export_models import ContractError, SemanticHints, semantic_hints_json_schema
from .intent_semantic_validator import GroundingValidationResult, GroundingValidator, IntentSemanticValidator
from .local_model_adapter import INTENT_MODEL_CONFIG, LocalModelAdapter


PROMPT_VERSION = "intelligent-export-semantic-hints-v1"
INTENT_SYSTEM_PROMPT = """你只输出 Grounded Semantic Hints，不输出完整 Intent，也不选择真实数据。

每条 hint 只能标注用户原文实际提到或明确暗示的四个基础维度之一：
- body_state：体重、体脂、减脂、身体状态。
- diet_macros：饮食、低碳、碳水、热量、蛋白、脂肪、摄入。
- training_context：训练、锻炼、训练状态，或明确讨论训练受到影响。
- movement_progress：明确动作的进步、表现、增长或下降；没有唯一动作时不要输出。

严格规则：
- evidence 必须逐字复制用户原文中的连续子串，不得改写、翻译或生成日期。
- 普通“饮食”是 diet_macros，不是 Notes。
- 普通“训练”是 training_context，不是 training_notes。
- “肩部训练”“胸部整体训练”是训练和部位事实，不是具体动作。
- “看看最近的情况”没有具体领域证据，返回空 semantic_hints。
- 不为了“影响、关系、变化”自动选择全部维度。
- 不输出日期、动作文本、部位、Notes、Raw、模块、字段、ID、ambiguous、confidence、warning 或关系类型。
- 只能返回符合 Semantic Hints Schema 的一个 JSON 对象，不要 Markdown 或解释。"""

_FORBIDDEN_MODEL_FIELDS = {
    "catalog_requirements", "preferred_detail", "raw_entry_relevance", "selected_modules", "selected_fields",
    "selected_movements", "notes_selection", "candidate_record_ids", "selected_note_candidate_ids",
    "selected_candidate_record_ids", "movement_id", "note_id", "history_id", "record_id",
}
_FORMAL_ID = re.compile(r"(?i)(?:\b[A-Z]+_\d+\b|\b(?:body|diet|training|raw|note|history|record)[-:][A-Za-z0-9_-]*\d[A-Za-z0-9_-]*\b)")


def parse_json_object(raw: str) -> dict:
    text = str(raw or "").replace("\ufeff", "").strip()
    if not text:
        raise ContractError("model response is empty", "MODEL_EMPTY_RESPONSE")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    if start < 0:
        raise ContractError("model output contains no JSON object", "MODEL_INVALID_JSON")
    depth = 0
    in_string = False
    escaped = False
    end = None
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        raise ContractError("model output contains an incomplete JSON object", "MODEL_OUTPUT_TRUNCATED")
    try:
        value = json.loads(text[start:end])
    except json.JSONDecodeError as exc:
        raise ContractError("model output is not valid JSON", "MODEL_INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise ContractError("model output must be a JSON object", "MODEL_INVALID_JSON")
    return value


class IntentInterpreter:
    def __init__(self, adapter: LocalModelAdapter) -> None:
        self.adapter = adapter
        self.last_result = None
        self.last_grounding_result: GroundingValidationResult | None = None

    def interpret(self, request: str, catalog_summary: dict | None = None, today: str | None = None, semantic_context: dict | None = None) -> tuple[SemanticHints, object]:
        payload = {
            "request": str(request or "")[:2000],
            "deterministic_facts": dict(semantic_context or {}),
            "semantic_hints_schema": semantic_hints_json_schema(),
        }
        result = self.adapter.generate_json(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_payload=payload,
            response_schema=semantic_hints_json_schema(),
            config=INTENT_MODEL_CONFIG,
        )
        self.last_result = result
        raw = parse_json_object(result.raw_text)
        self._validate_raw_model_boundary(raw)
        hints = SemanticHints.from_dict(raw)
        grounding = GroundingValidator.validate(hints, request, semantic_context)
        self.last_grounding_result = grounding
        return grounding.hints, result

    def parse_repair(self, request: str, raw: str) -> tuple[SemanticHints, GroundingValidationResult]:
        """Compatibility parser only; the production path never calls repair."""
        parsed = parse_json_object(raw)
        self._validate_raw_model_boundary(parsed)
        hints = SemanticHints.from_dict(parsed)
        grounding = GroundingValidator.validate(hints, request, {})
        self.last_grounding_result = grounding
        return grounding.hints, grounding

    @staticmethod
    def _validate_raw_model_boundary(raw: dict) -> None:
        required = {"schema_version", "semantic_hints"}
        missing = sorted(required - set(raw))
        if missing:
            raise ContractError(f"Semantic hints output is missing required fields: {', '.join(missing)}", "MODEL_SCHEMA_INVALID")
        allowed = required
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ContractError(f"Semantic hints output contains unknown fields: {', '.join(unknown)}", "MODEL_SCHEMA_EXTRA_FIELD")
        forbidden = sorted(_FORBIDDEN_MODEL_FIELDS.intersection(raw))
        if forbidden:
            raise ContractError(f"Semantic hints output contains forbidden selection fields: {', '.join(forbidden)}", "MODEL_INTENT_SELECTION_FIELD")
        encoded = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
        if _FORMAL_ID.search(encoded):
            raise ContractError("Semantic hints output contains a real-data or formal movement ID", "MODEL_INTENT_DATA_ID")
