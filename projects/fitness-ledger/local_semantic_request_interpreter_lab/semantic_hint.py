"""Narrow, catalog-grounded semantic hints for the Stage B route."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


HINT_ROOT_KEYS = {"candidates", "ambiguities"}
CANDIDATE_KEYS = {"dimension", "canonical_value", "evidence", "confidence"}
AMBIGUITY_KEYS = {"dimension", "reason", "evidence"}
REQUESTED_INFORMATION_PREFIX = "requested_information."
MIN_READY_CONFIDENCE = 0.70


class SemanticHintError(ValueError):
    """A model hint is malformed, ungrounded, or outside its candidate pool."""


@dataclass(frozen=True)
class SemanticHintRequest:
    """The only mutable semantic surface exposed to the model."""

    user_text: str
    fixed_constraints: tuple[dict[str, Any], ...]
    candidate_pool: Mapping[str, tuple[str, ...]]
    evidence_options: Mapping[str, tuple[str, ...]]
    required_dimensions: tuple[str, ...]

    def to_prompt_payload(self) -> dict[str, Any]:
        return {
            "user_text": self.user_text,
            "fixed_constraints": [dict(item) for item in self.fixed_constraints],
            "candidate_pool": {key: list(values) for key, values in self.candidate_pool.items()},
            "evidence_options": {key: list(values) for key, values in self.evidence_options.items()},
            "allowed_dimensions": list(self.candidate_pool),
        }

    def to_json_schema(self) -> dict[str, Any]:
        """Build a request-scoped grammar schema from the already validated pool."""
        candidate_variants = []
        for dimension, values in self.candidate_pool.items():
            candidate_variants.append({
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
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "candidates": {"type": "array", "maxItems": 32, "items": {"oneOf": candidate_variants}},
                "ambiguities": {
                    "type": "array",
                    "maxItems": 16,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "dimension": {"enum": list(self.candidate_pool)},
                            "reason": {"type": "string", "minLength": 1, "maxLength": 160},
                            "evidence": {"enum": sorted({evidence for values in self.evidence_options.values() for evidence in values})},
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


def _strict_dict(value: Any, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SemanticHintError(f"{label} must be an object")
    unknown = set(value) - keys
    if unknown:
        raise SemanticHintError(f"{label} has unknown fields: {sorted(unknown)}")
    return value


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticHintError(f"{label} must be a non-empty string")
    return value


def validate_semantic_hint(value: Mapping[str, Any], request: SemanticHintRequest) -> SemanticHint:
    """Validate only the narrow hint contract, never a RequestDraft."""
    root = _strict_dict(value, "semantic_hint", HINT_ROOT_KEYS)
    if set(root) != HINT_ROOT_KEYS:
        raise SemanticHintError("semantic_hint must contain exactly candidates and ambiguities")
    candidates = root["candidates"]
    ambiguities = root["ambiguities"]
    if not isinstance(candidates, list) or len(candidates) > 32:
        raise SemanticHintError("candidates must be a list with at most 32 items")
    if not isinstance(ambiguities, list) or len(ambiguities) > 16:
        raise SemanticHintError("ambiguities must be a list with at most 16 items")

    allowed_dimensions = set(request.candidate_pool)
    seen: set[tuple[str, str]] = set()
    checked: list[SemanticCandidate] = []
    for index, raw in enumerate(candidates):
        item = _strict_dict(raw, f"candidates[{index}]", CANDIDATE_KEYS)
        if set(item) != CANDIDATE_KEYS:
            raise SemanticHintError(f"candidates[{index}] must contain exactly four fields")
        dimension = _nonempty_string(item["dimension"], f"candidates[{index}].dimension")
        canonical = _nonempty_string(item["canonical_value"], f"candidates[{index}].canonical_value")
        evidence = _nonempty_string(item["evidence"], f"candidates[{index}].evidence")
        confidence = item["confidence"]
        if dimension not in allowed_dimensions:
            raise SemanticHintError(f"unknown or protected dimension: {dimension}")
        if canonical not in request.candidate_pool[dimension]:
            raise SemanticHintError(f"candidate is not in catalog pool: {dimension}={canonical}")
        if evidence not in request.evidence_options.get(dimension, ()) or evidence not in request.user_text:
            raise SemanticHintError(f"candidate evidence is not grounded: {dimension}={evidence}")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise SemanticHintError(f"invalid confidence: {dimension}={canonical}")
        key = (dimension, canonical)
        if key in seen:
            raise SemanticHintError(f"duplicate candidate: {dimension}={canonical}")
        seen.add(key)
        checked.append(SemanticCandidate(dimension, canonical, evidence, float(confidence)))

    checked_ambiguities: list[dict[str, str]] = []
    for index, raw in enumerate(ambiguities):
        item = _strict_dict(raw, f"ambiguities[{index}]", AMBIGUITY_KEYS)
        if set(item) != AMBIGUITY_KEYS:
            raise SemanticHintError(f"ambiguities[{index}] must contain exactly dimension, reason, evidence")
        dimension = _nonempty_string(item["dimension"], f"ambiguities[{index}].dimension")
        reason = _nonempty_string(item["reason"], f"ambiguities[{index}].reason")
        evidence = _nonempty_string(item["evidence"], f"ambiguities[{index}].evidence")
        if dimension not in allowed_dimensions:
            raise SemanticHintError(f"unknown or protected ambiguity dimension: {dimension}")
        if evidence not in request.user_text:
            raise SemanticHintError(f"ambiguity evidence is not grounded: {dimension}")
        checked_ambiguities.append({"dimension": dimension, "reason": reason, "evidence": evidence})
    return SemanticHint(tuple(checked), tuple(checked_ambiguities))


def rank_candidates(hint: SemanticHint, dimension: str) -> tuple[SemanticCandidate, ...]:
    """Return a stable confidence ranking for one permitted dimension."""
    return tuple(sorted((item for item in hint.candidates if item.dimension == dimension), key=lambda item: (-item.confidence, item.canonical_value)))


def assemble_semantic_hint(intent: Any, request: SemanticHintRequest, hint: SemanticHint) -> dict[str, Any]:
    """Merge hint-selected requested fields into immutable deterministic constraints."""
    datasets: list[dict[str, Any]] = []
    if hint.ambiguities and any(not rank_candidates(hint, dimension) for dimension in request.required_dimensions):
        reasons = "; ".join(item["reason"] for item in hint.ambiguities)
        return {
            "schema_version": "fitness-ledger-request-draft-v1",
            "status": "needs_confirmation",
            "purpose": intent.purpose,
            "datasets": [],
            "relations": [],
            "missing_confirmations": [f"请确认 requested information：{reasons}"],
            "warnings": [],
        }
    for fixed in request.fixed_constraints:
        dataset = json.loads(json.dumps(fixed, ensure_ascii=False))
        dimension = f"{REQUESTED_INFORMATION_PREFIX}{dataset['kind']}"
        selected = rank_candidates(hint, dimension)
        if not selected:
            raise SemanticHintError(f"missing candidates for required dimension: {dimension}")
        if any(item.confidence < MIN_READY_CONFIDENCE for item in selected):
            return {
                "schema_version": "fitness-ledger-request-draft-v1",
                "status": "needs_confirmation",
                "purpose": intent.purpose,
                "datasets": [],
                "relations": [],
                "missing_confirmations": [f"请确认 {dimension} 的候选字段"],
                "warnings": [],
            }
        allowed_order = request.candidate_pool[dimension]
        dataset["requested_information"] = [value for value in allowed_order if any(item.canonical_value == value for item in selected)]
        if not dataset["requested_information"]:
            raise SemanticHintError(f"empty selected candidates: {dimension}")
        datasets.append(dataset)
    return {
        "schema_version": "fitness-ledger-request-draft-v1",
        "status": "ready",
        "purpose": intent.purpose,
        "datasets": datasets,
        "relations": [],
        "missing_confirmations": [],
        "warnings": [],
    }


def build_comparative_hint_request(user_text: str, capability_catalog: dict[str, Any]) -> SemanticHintRequest:
    """Build a generic comparative-export hint pool from catalog capabilities."""
    training_values = tuple(value for value in ("date", "session", "movements", "sets") if value in capability_catalog["datasets"]["training"])
    diet_values = tuple(value for value in ("date", "energy", "protein", "carbohydrate", "fat") if value in capability_catalog["datasets"]["diet"])
    return SemanticHintRequest(
        user_text=user_text,
        fixed_constraints=(
            {"draft_id": "training_month", "kind": "training", "scope": {}, "time_intent": {"type": "recent_days", "days": 30}, "requested_information": [], "notes": {"requested": False, "scopes": []}},
            {"draft_id": "diet_month", "kind": "diet", "scope": {}, "time_intent": {"type": "recent_days", "days": 30}, "requested_information": [], "notes": {"requested": False, "scopes": []}},
        ),
        candidate_pool={
            "requested_information.training": training_values,
            "requested_information.diet": diet_values,
        },
        evidence_options={
            "requested_information.training": ("训练",),
            "requested_information.diet": ("饮食",),
        },
        required_dimensions=("requested_information.training", "requested_information.diet"),
    )


def build_semantic_hint_prompt(request: SemanticHintRequest, template: str) -> str:
    return template.replace("{{HINT_REQUEST}}", json.dumps(request.to_prompt_payload(), ensure_ascii=False, separators=(",", ":")))
