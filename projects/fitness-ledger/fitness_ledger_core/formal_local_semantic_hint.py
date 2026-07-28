"""Narrow, request-scoped SemanticHint contract for formal Request v1.1."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


class SemanticHintError(ValueError):
    """The hint is malformed, ungrounded, or outside the formal candidate pool."""


def parse_json_strict(text: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SemanticHintError(f"DUPLICATE_FIELD:{key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda item: (_ for _ in ()).throw(SemanticHintError(f"INVALID_CONSTANT:{item}")),
        )
    except (TypeError, json.JSONDecodeError) as exc:
        raise SemanticHintError("INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise SemanticHintError("INVALID_JSON_ROOT")
    return value


@dataclass(frozen=True)
class SemanticHintRequest:
    user_text: str
    candidate_pool: Mapping[str, tuple[str, ...]]
    evidence_options: Mapping[str, tuple[str, ...]]
    required_dimensions: tuple[str, ...]

    def to_prompt_payload(self) -> dict[str, Any]:
        return {
            "user_text": self.user_text,
            "candidate_pool": {key: list(values) for key, values in self.candidate_pool.items()},
            "evidence_options": {key: list(values) for key, values in self.evidence_options.items()},
            "allowed_dimensions": list(self.candidate_pool),
            "protected_dimensions": [
                "status",
                "dataset_type",
                "dataset_id",
                "time_range",
                "filters",
                "notes_scope",
                "raw",
                "output",
            ],
        }

    def to_json_schema(self) -> dict[str, Any]:
        variants: list[dict[str, Any]] = []
        for dimension, values in self.candidate_pool.items():
            variants.append({
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "dimension": {"const": dimension},
                    "canonical_value": {"enum": list(values)},
                    "evidence": {"enum": list(self.evidence_options.get(dimension, ()))},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["dimension", "canonical_value", "evidence", "confidence"],
            })
        evidence = sorted({item for values in self.evidence_options.values() for item in values})
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "candidates": {"type": "array", "maxItems": 32, "items": {"oneOf": variants}},
                "ambiguities": {
                    "type": "array",
                    "maxItems": 16,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "dimension": {"enum": list(self.candidate_pool)},
                            "reason": {"type": "string", "minLength": 1, "maxLength": 160},
                            "evidence": {"enum": evidence},
                        },
                        "required": ["dimension", "reason", "evidence"],
                    },
                },
            },
            "required": ["candidates", "ambiguities"],
        }


@dataclass(frozen=True)
class SemanticCandidate:
    dimension: str
    canonical_value: str
    evidence: str
    confidence: float


@dataclass(frozen=True)
class SemanticHint:
    candidates: tuple[SemanticCandidate, ...]
    ambiguities: tuple[dict[str, str], ...]

    def to_summary(self) -> dict[str, Any]:
        return {
            "candidates": [
                {
                    "dimension": item.dimension,
                    "canonical_value": item.canonical_value,
                    "evidence": item.evidence,
                    "confidence": item.confidence,
                }
                for item in self.candidates
            ],
            "ambiguities": [dict(item) for item in self.ambiguities],
        }


def validate_semantic_hint(value: Mapping[str, Any], request: SemanticHintRequest) -> SemanticHint:
    if not isinstance(value, dict) or set(value) != {"candidates", "ambiguities"}:
        raise SemanticHintError("INVALID_HINT_ROOT")
    candidates, ambiguities = value["candidates"], value["ambiguities"]
    if not isinstance(candidates, list) or len(candidates) > 32:
        raise SemanticHintError("INVALID_CANDIDATES")
    if not isinstance(ambiguities, list) or len(ambiguities) > 16:
        raise SemanticHintError("INVALID_AMBIGUITIES")

    checked: list[SemanticCandidate] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(candidates):
        if not isinstance(item, dict) or set(item) != {"dimension", "canonical_value", "evidence", "confidence"}:
            raise SemanticHintError(f"INVALID_CANDIDATE_SHAPE:{index}")
        dimension = item["dimension"]
        canonical = item["canonical_value"]
        evidence = item["evidence"]
        confidence = item["confidence"]
        if dimension not in request.candidate_pool:
            raise SemanticHintError(f"PROTECTED_OR_UNKNOWN_DIMENSION:{dimension}")
        if canonical not in request.candidate_pool[dimension]:
            raise SemanticHintError(f"CANDIDATE_OUTSIDE_POOL:{dimension}:{canonical}")
        if evidence not in request.evidence_options.get(dimension, ()) or evidence not in request.user_text:
            raise SemanticHintError(f"UNGROUNDED_EVIDENCE:{dimension}")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise SemanticHintError(f"INVALID_CONFIDENCE:{dimension}:{canonical}")
        key = (dimension, canonical)
        if key in seen:
            raise SemanticHintError(f"DUPLICATE_CANDIDATE:{dimension}:{canonical}")
        seen.add(key)
        checked.append(SemanticCandidate(dimension, canonical, evidence, float(confidence)))

    checked_ambiguities: list[dict[str, str]] = []
    for index, item in enumerate(ambiguities):
        if not isinstance(item, dict) or set(item) != {"dimension", "reason", "evidence"}:
            raise SemanticHintError(f"INVALID_AMBIGUITY_SHAPE:{index}")
        dimension, reason, evidence = item["dimension"], item["reason"], item["evidence"]
        if dimension not in request.candidate_pool:
            raise SemanticHintError(f"PROTECTED_OR_UNKNOWN_DIMENSION:{dimension}")
        if not isinstance(reason, str) or not reason.strip():
            raise SemanticHintError(f"INVALID_AMBIGUITY_REASON:{index}")
        if evidence not in request.evidence_options.get(dimension, ()) or evidence not in request.user_text:
            raise SemanticHintError(f"UNGROUNDED_AMBIGUITY:{dimension}")
        checked_ambiguities.append({"dimension": dimension, "reason": reason, "evidence": evidence})

    dimensions = {item.dimension for item in checked}
    ambiguous_dimensions = {item["dimension"] for item in checked_ambiguities}
    unresolved = set(request.required_dimensions) - dimensions - ambiguous_dimensions
    if unresolved:
        raise SemanticHintError(f"MISSING_REQUIRED_DIMENSIONS:{sorted(unresolved)}")
    return SemanticHint(tuple(checked), tuple(checked_ambiguities))


def build_prompt(request: SemanticHintRequest, template: str) -> str:
    return template.replace(
        "{{HINT_REQUEST}}",
        json.dumps(request.to_prompt_payload(), ensure_ascii=False, separators=(",", ":")),
    )
