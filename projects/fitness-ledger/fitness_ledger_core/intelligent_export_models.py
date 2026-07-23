"""Strict, dependency-free contracts for the intelligent export Core MVP.

The model-facing objects in this module deliberately use dataclasses and
small runtime validators instead of adding a new dependency to Fitness
Ledger.  The JSON schemas are also emitted here so the Ollama adapter can
constrain responses without exposing any project internals.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal


SCHEMA_VERSION = "fitness-ledger-intelligent-export-v1"
INTENT_SCHEMA_VERSION = "fitness-ledger-intelligent-export-intent-v2"
SEMANTIC_HINTS_SCHEMA_VERSION = "fitness-ledger-semantic-hints-v1"
SELECTION_SCHEMA_VERSION = "fitness-ledger-intelligent-export-v1.1"
PLANNER_CONFIDENCE_THRESHOLD = 0.5
BODY_PART_IDS = ("CHEST", "BACK", "SHOULDER", "ARMS", "CORE", "LEGS")
BodyPartId = Literal["CHEST", "BACK", "SHOULDER", "ARMS", "CORE", "LEGS"]
INTENT_DIMENSIONS = (
    "body_state",
    "diet_macros",
    "training_context",
    "movement_progress",
    "daily_notes",
    "diet_notes",
    "training_notes",
    "movement_notes",
    "raw_trace",
)
SEMANTIC_HINT_DIMENSIONS = (
    "body_state",
    "diet_macros",
    "training_context",
    "movement_progress",
)
INTENT_RELATIONSHIP_TYPES = ("trend", "comparison", "impact", "correlation", "summary")
INTENT_EVIDENCE_FOCUS = ("quantitative_metrics", "session_context", "progress_history", "notes_context", "raw_trace")
PLANNING_DECISIONS = {"ready", "fallback_required"}
FALLBACK_REASON_CODES = {
    "NO_VALID_WINDOW",
    "NO_RELEVANT_MODULES",
    "NO_USABLE_CANDIDATES",
    "UNRESOLVED_REQUIRED_MOVEMENT",
    "REQUEST_NOT_UNDERSTOOD",
    "NO_SAFE_PLAN",
}
MAX_LIST = 64
MAX_TEXT = 400


class ContractError(ValueError):
    """Raised when a model response violates a Core contract."""

    def __init__(self, message: str, code: str = "MODEL_SCHEMA_INVALID") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SemanticHint:
    dimension: str
    evidence: str


@dataclass(frozen=True)
class SemanticHints:
    """The only semantic object the local model is allowed to produce."""

    hints: list[SemanticHint]
    schema_version: str = SEMANTIC_HINTS_SCHEMA_VERSION

    @property
    def dimensions(self) -> list[str]:
        return list(dict.fromkeys(item.dimension for item in self.hints))

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "semantic_hints": [{"dimension": item.dimension, "evidence": item.evidence} for item in self.hints],
        }

    @classmethod
    def from_dict(cls, value: Any) -> "SemanticHints":
        raw = _obj(value, "semantic_hints")
        _unknown(raw, {"schema_version", "semantic_hints"}, "semantic_hints")
        if raw.get("schema_version") != SEMANTIC_HINTS_SCHEMA_VERSION:
            raise ContractError("unsupported semantic hints schema_version")
        items = _list(raw.get("semantic_hints"), "semantic_hints", 8)
        parsed: list[SemanticHint] = []
        for index, item in enumerate(items):
            entry = _obj(item, f"semantic_hints[{index}]")
            _unknown(entry, {"dimension", "evidence"}, f"semantic_hints[{index}]")
            dimension = _text(entry.get("dimension"), f"semantic_hints[{index}].dimension", 40, True)
            evidence = _text(entry.get("evidence"), f"semantic_hints[{index}].evidence", 120, True)
            if dimension not in SEMANTIC_HINT_DIMENSIONS:
                raise ContractError("semantic hint dimension is invalid", "MODEL_SEMANTIC_HINT_ENUM")
            parsed.append(SemanticHint(dimension, evidence))
        if len({(item.dimension, item.evidence) for item in parsed}) != len(parsed):
            raise ContractError("semantic hints must not contain duplicates", "MODEL_SEMANTIC_HINT_DUPLICATE")
        return cls(parsed)


def _obj(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be an object")
    return value


def _unknown(value: dict, allowed: set[str], name: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ContractError(f"{name} contains unknown fields: {', '.join(unknown)}")


def _text(value: Any, name: str, limit: int = MAX_TEXT, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ContractError(f"{name} must be a string")
    if required and not value.strip():
        raise ContractError(f"{name} must not be empty")
    if len(value) > limit:
        raise ContractError(f"{name} exceeds {limit} characters")
    return value


def _list(value: Any, name: str, limit: int = MAX_LIST) -> list:
    if not isinstance(value, list):
        raise ContractError(f"{name} must be an array")
    if len(value) > limit:
        raise ContractError(f"{name} exceeds {limit} items")
    return value


def _number(value: Any, name: str, minimum: float = 0, maximum: float = 1) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be numeric")
    number = float(value)
    if not minimum <= number <= maximum:
        raise ContractError(f"{name} is outside [{minimum}, {maximum}]")
    return number


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class DateIntent:
    mode: str = "unspecified"
    relative_range: str | None = None
    comparison_needed: bool = False
    raw_date_mentions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Any) -> "DateIntent":
        raw = _obj(value, "date_intent")
        _unknown(raw, {"mode", "relative_range", "comparison_needed", "raw_date_mentions"}, "date_intent")
        mode = _text(raw.get("mode", "unspecified"), "date_intent.mode", 32)
        if mode not in {"unspecified", "relative", "explicit", "all_available"}:
            raise ContractError("date_intent.mode is invalid")
        relative = raw.get("relative_range")
        if relative is not None:
            relative = _text(relative, "date_intent.relative_range", 32)
            if relative not in {"last_week", "recent", "recent_4_weeks", "recent_8_weeks", "recent_12_weeks", "recent_months", "all_available"}:
                raise ContractError("date_intent.relative_range is invalid")
        comparison = raw.get("comparison_needed", False)
        if not isinstance(comparison, bool):
            raise ContractError("date_intent.comparison_needed must be boolean")
        mentions = [_text(item, "date_intent.raw_date_mentions[]", 80, True) for item in _list(raw.get("raw_date_mentions", []), "date_intent.raw_date_mentions", 8)]
        if mode == "relative" and relative is None:
            raise ContractError("relative date_intent requires relative_range")
        if mode == "explicit" and not mentions:
            raise ContractError("explicit date_intent requires raw_date_mentions")
        if mode == "unspecified" and relative not in {None}:
            raise ContractError("unspecified date_intent cannot set relative_range")
        if mode == "all_available" and relative not in {None, "all_available"}:
            raise ContractError("all_available date_intent has invalid relative_range")
        return cls(mode, relative, comparison, mentions)


@dataclass(frozen=True)
class MovementMention:
    text: str
    confidence: float = 0.0

    @classmethod
    def from_dict(cls, value: Any) -> "MovementMention":
        raw = _obj(value, "movement_mention")
        _unknown(raw, {"text", "confidence"}, "movement_mention")
        return cls(
            _text(raw.get("text", ""), "movement_mention.text", 120, True),
            _number(raw.get("confidence", 0.0), "movement_mention.confidence"),
        )


@dataclass(frozen=True)
class IntentSpec:
    """Canonical semantic scope plus non-authoritative compatibility metadata."""

    dimensions: list[str]
    excluded_dimensions: list[str]
    date_text: list[str]
    movement_mentions: list[str]
    target_body_parts: list[BodyPartId]
    ambiguous: bool
    interpreted_goal: str = ""
    date_intent: DateIntent = field(default_factory=DateIntent)
    relationship_types: list[str] = field(default_factory=list)
    evidence_focus: list[str] = field(default_factory=list)
    catalog_requirements: list[str] = field(default_factory=list)
    preferred_detail: str = "summary"
    raw_entry_relevance: str = "none"
    confidence: float = 0.0
    needs_fallback: bool = False
    warnings: list[str] = field(default_factory=list)
    schema_version: str = INTENT_SCHEMA_VERSION

    @property
    def analysis_dimensions(self) -> list[str]:
        return list(self.dimensions)

    @property
    def target_body_part_ids(self) -> list[str]:
        return list(self.target_body_parts)

    @property
    def explicit_movement_mentions(self) -> list[str]:
        return list(self.movement_mentions)

    @classmethod
    def from_dict(cls, value: Any) -> "IntentSpec":
        raw = _obj(value, "intent")
        canonical = {"dimensions", "excluded_dimensions", "date_text", "movement_mentions", "target_body_parts", "ambiguous"}
        if canonical.issubset(raw):
            _unknown(raw, canonical | {"schema_version"}, "intent")
            if raw.get("schema_version") != INTENT_SCHEMA_VERSION:
                raise ContractError("unsupported intent schema_version")
            dimensions = [_text(item, "dimensions[]", 64, True) for item in _list(raw.get("dimensions"), "dimensions", 12)]
            date_text = [_text(item, "date_text[]", 80, True) for item in _list(raw.get("date_text"), "date_text", 8)]
            movement_mentions = [_text(item, "movement_mentions[]", 120, True) for item in _list(raw.get("movement_mentions"), "movement_mentions", 8)]
            target_body_parts = [_text(item, "target_body_parts[]", 16, True) for item in _list(raw.get("target_body_parts"), "target_body_parts", 6)]
            excluded = [_text(item, "excluded_dimensions[]", 64, True) for item in _list(raw.get("excluded_dimensions"), "excluded_dimensions", len(INTENT_DIMENSIONS))]
            if any(item not in INTENT_DIMENSIONS for item in dimensions + excluded):
                raise ContractError("intent dimensions contain an invalid semantic value")
            if any(item not in BODY_PART_IDS for item in target_body_parts):
                raise ContractError("target_body_parts contains an invalid BodyPartId")
            if len(set(dimensions)) != len(dimensions) or len(set(excluded)) != len(excluded):
                raise ContractError("intent dimensions must not contain duplicates")
            if set(dimensions).intersection(excluded):
                raise ContractError("a dimension cannot be both included and excluded")
            if len(set(target_body_parts)) != len(target_body_parts):
                raise ContractError("target_body_parts must not contain duplicates")
            if not isinstance(raw.get("ambiguous"), bool):
                raise ContractError("ambiguous must be boolean")
            return cls(dimensions, excluded, date_text, movement_mentions, list(target_body_parts), raw["ambiguous"], schema_version=INTENT_SCHEMA_VERSION)

        # Legacy fixture compatibility. This branch is never accepted by the
        # model boundary; it only keeps old deterministic tests readable.
        allowed = {"schema_version", "interpreted_goal", "analysis_dimensions", "date_intent", "relationship_types", "evidence_focus", "excluded_dimensions", "movement_mentions", "target_body_parts", "catalog_requirements", "preferred_detail", "raw_entry_relevance", "confidence", "needs_fallback", "warnings"}
        _unknown(raw, allowed, "legacy intent")
        if raw.get("schema_version") != INTENT_SCHEMA_VERSION:
            raise ContractError("unsupported intent schema_version")
        if "target_body_parts" not in raw:
            raise ContractError("target_body_parts is required")
        target_body_parts = _list(raw.get("target_body_parts"), "target_body_parts", 6)
        if any(not isinstance(item, str) or item not in BODY_PART_IDS for item in target_body_parts):
            raise ContractError("target_body_parts contains an invalid BodyPartId")
        if len(target_body_parts) != len(set(target_body_parts)):
            raise ContractError("target_body_parts must not contain duplicates")
        dimensions = [_text(item, "analysis_dimensions[]", 64, True) for item in _list(raw.get("analysis_dimensions", []), "analysis_dimensions", 12)]
        if any(item not in INTENT_DIMENSIONS for item in dimensions):
            raise ContractError("analysis_dimensions contains an invalid semantic dimension")
        if len(dimensions) != len(set(dimensions)):
            raise ContractError("analysis_dimensions must not contain duplicates")
        relationships = [_text(item, "relationship_types[]", 32, True) for item in _list(raw.get("relationship_types", []), "relationship_types", 5)]
        if any(item not in INTENT_RELATIONSHIP_TYPES for item in relationships):
            raise ContractError("relationship_types contains an invalid relationship type")
        if len(relationships) != len(set(relationships)):
            raise ContractError("relationship_types must not contain duplicates")
        focus = [_text(item, "evidence_focus[]", 40, True) for item in _list(raw.get("evidence_focus", []), "evidence_focus", 5)]
        if any(item not in INTENT_EVIDENCE_FOCUS for item in focus):
            raise ContractError("evidence_focus contains an invalid evidence focus")
        if len(focus) != len(set(focus)):
            raise ContractError("evidence_focus must not contain duplicates")
        excluded = [_text(item, "excluded_dimensions[]", 64, True) for item in _list(raw.get("excluded_dimensions", []), "excluded_dimensions", len(INTENT_DIMENSIONS))]
        if any(item not in INTENT_DIMENSIONS for item in excluded):
            raise ContractError("excluded_dimensions contains an invalid semantic dimension")
        if len(excluded) != len(set(excluded)):
            raise ContractError("excluded_dimensions must not contain duplicates")
        if set(excluded).intersection(dimensions):
            raise ContractError("a dimension cannot be both included and excluded")
        requirements = [_text(item, "catalog_requirements[]", 64, True) for item in _list(raw.get("catalog_requirements", []), "catalog_requirements", 12)]
        warnings = [_text(item, "warnings[]", 240) for item in _list(raw.get("warnings", []), "warnings", 12)]
        detail = _text(raw.get("preferred_detail", "summary"), "preferred_detail", 40)
        raw_relevance = _text(raw.get("raw_entry_relevance", "none"), "raw_entry_relevance", 32)
        if raw_relevance not in {"none", "preview", "requested"}:
            raise ContractError("raw_entry_relevance is invalid")
        if not isinstance(raw.get("needs_fallback", False), bool):
            raise ContractError("needs_fallback must be boolean")
        old_mentions = [MovementMention.from_dict(item).text for item in _list(raw.get("movement_mentions", []), "movement_mentions", 8)]
        return cls(dimensions, excluded, list(DateIntent.from_dict(raw.get("date_intent", {})).raw_date_mentions), old_mentions, list(target_body_parts), bool(raw.get("needs_fallback", False)), _text(raw.get("interpreted_goal", ""), "interpreted_goal", 400, True), DateIntent.from_dict(raw.get("date_intent", {})), relationships, focus, requirements, detail, raw_relevance, _number(raw.get("confidence", 0.0), "confidence"), bool(raw.get("needs_fallback", False)), warnings, INTENT_SCHEMA_VERSION)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "dimensions": list(self.dimensions),
            "excluded_dimensions": list(self.excluded_dimensions),
            "date_text": list(self.date_text),
            "movement_mentions": list(self.movement_mentions),
            "target_body_parts": list(self.target_body_parts),
            "ambiguous": bool(self.ambiguous),
        }


@dataclass(frozen=True)
class CandidateWindow:
    window_id: str
    requested_start: str
    requested_end: str
    resolved_start: str
    resolved_end: str
    anchor: str
    modules: list[str]
    record_count: int
    missing_data_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModuleCard:
    module_id: str
    available: bool
    date_start: str
    date_end: str
    record_count: int
    active_date_count: int
    field_coverage: dict[str, float]
    missing_intervals: list[str]
    factual_summary: str
    available_detail_levels: list[str]
    estimated_cost: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MovementCard:
    movement_id: str
    canonical_name: str
    aliases: list[str]
    body_part: str
    body_part_id: str
    history_count: int
    progress_history_count: int
    excluded_history_count: int
    date_start: str
    date_end: str
    latest_history_date: str
    latest_valid_progress_date: str
    latest_valid_performance: dict
    trend_sample_sufficiency: str
    window_stats: dict = field(default_factory=dict)
    estimated_cost: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class NotesCard:
    note_candidate_id: str
    date: str
    note_type: str
    scope: str
    source_record_id: str
    movement_id: str = ""
    history_id: str = ""
    char_count: int = 0
    short_fragment: str = ""
    dedup_hash: str = ""
    related_candidate_ids: list[str] = field(default_factory=list)
    estimated_cost: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CandidateRecordCard:
    candidate_record_id: str
    module_id: str
    date: str
    record_kind: str
    factual_summary: dict
    flags: list[str] = field(default_factory=list)
    related_movement_ids: list[str] = field(default_factory=list)
    related_note_ids: list[str] = field(default_factory=list)
    estimated_cost: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DataCatalog:
    catalog_id: str
    source_snapshot_id: str
    generated_at: str
    date_range: dict
    latest_record_date: str
    modules: list[ModuleCard]
    movements: list[MovementCard]
    notes: list[NotesCard]
    candidate_records: list[CandidateRecordCard]
    windows: list[CandidateWindow] = field(default_factory=list)

    def to_prompt_dict(self) -> dict:
        """Return only compact facts safe to send to a local model."""
        return {
            "schema_version": SCHEMA_VERSION,
            "catalog_id": self.catalog_id,
            "source_snapshot_id": self.source_snapshot_id,
            "date_range": self.date_range,
            "latest_record_date": self.latest_record_date,
            "modules": [item.to_dict() for item in self.modules],
            "movements": [item.to_dict() for item in self.movements],
            "notes": [item.to_dict() for item in self.notes],
            "candidate_records": [item.to_dict() for item in self.candidate_records],
            "windows": [item.to_dict() for item in self.windows],
        }


@dataclass(frozen=True)
class ExportPlanDraft:
    interpreted_goal: str
    analysis_dimensions: list[str]
    date_range: dict
    selected_modules: list[str]
    selected_fields: dict[str, list[str]]
    selected_movements: list[str]
    notes_selection: list[str]
    candidate_record_ids: list[str]
    training_detail_level: str = "summary"
    movement_detail_level: str = "summary"
    include_raw_entries: bool = False
    include_excluded_history: bool = False
    excluded_history_usage: str = "none"
    use_progress_history_for_metrics: bool = True
    inclusion_reasons: dict[str, str] = field(default_factory=dict)
    exclusion_reasons: dict[str, str] = field(default_factory=dict)
    missing_data_warnings: list[str] = field(default_factory=list)
    planner_confidence: float = 0.0
    planning_decision: str = "ready"
    fallback_reason_codes: list[str] = field(default_factory=list)
    priority: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Any) -> "ExportPlanDraft":
        raw = _obj(value, "plan")
        allowed = {"schema_version", "interpreted_goal", "analysis_dimensions", "date_range", "selected_modules", "selected_fields", "selected_movements", "notes_selection", "candidate_record_ids", "training_detail_level", "movement_detail_level", "include_raw_entries", "include_excluded_history", "excluded_history_usage", "use_progress_history_for_metrics", "inclusion_reasons", "exclusion_reasons", "missing_data_warnings", "planner_confidence", "planning_decision", "fallback_reason_codes", "needs_fallback", "priority"}
        _unknown(raw, allowed, "plan")
        if raw.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ContractError("unsupported plan schema_version")
        def strings(key: str, limit: int = MAX_LIST) -> list[str]:
            return [_text(item, f"{key}[]", 120, True) for item in _list(raw.get(key, []), key, limit)]
        selected_fields = _obj(raw.get("selected_fields", {}), "selected_fields")
        if len(selected_fields) > 12:
            raise ContractError("selected_fields has too many modules")
        normalized_fields = {str(module): strings_from(value, f"selected_fields.{module}") for module, value in selected_fields.items()}
        date_range = _obj(raw.get("date_range", {}), "date_range")
        _unknown(date_range, {"window_id", "requested_start", "requested_end", "resolved_start", "resolved_end", "anchor"}, "date_range")
        for key in ("window_id", "requested_start", "requested_end", "resolved_start", "resolved_end"):
            if key not in date_range or not isinstance(date_range[key], str):
                raise ContractError(f"date_range.{key} is required")
        for key in ("include_raw_entries", "include_excluded_history", "use_progress_history_for_metrics"):
            if not isinstance(raw.get(key, False if key != "use_progress_history_for_metrics" else True), bool):
                raise ContractError(f"{key} must be boolean")
        usage = _text(raw.get("excluded_history_usage", "none"), "excluded_history_usage", 32)
        if usage not in {"none", "context_only"}:
            raise ContractError("excluded_history_usage is invalid")
        detail_values = {"summary", "detailed", "full"}
        training_detail = _text(raw.get("training_detail_level", "summary"), "training_detail_level", 24)
        movement_detail = _text(raw.get("movement_detail_level", "summary"), "movement_detail_level", 24)
        if training_detail not in detail_values or movement_detail not in detail_values:
            raise ContractError("detail level is invalid")
        legacy_fallback = raw.get("needs_fallback", False)
        if not isinstance(legacy_fallback, bool):
            raise ContractError("needs_fallback must be boolean")
        decision = _text(raw.get("planning_decision", "fallback_required" if legacy_fallback else "ready"), "planning_decision", 32)
        if decision not in PLANNING_DECISIONS:
            raise ContractError("planning_decision is invalid")
        reasons = strings("fallback_reason_codes", 8)
        if legacy_fallback and not reasons:
            reasons = ["NO_SAFE_PLAN"]
        if decision == "ready" and reasons:
            raise ContractError("ready selection cannot contain fallback reasons")
        if decision == "fallback_required" and not reasons:
            raise ContractError("fallback_required selection needs a reason")
        if any(code not in FALLBACK_REASON_CODES for code in reasons):
            raise ContractError("fallback_reason_codes contains an unknown code")
        return cls(
            _text(raw.get("interpreted_goal", ""), "interpreted_goal", 400, True),
            strings("analysis_dimensions", 12),
            date_range,
            strings("selected_modules", 12),
            normalized_fields,
            strings("selected_movements", 16),
            strings("notes_selection", 64),
            strings("candidate_record_ids", 128),
            training_detail,
            movement_detail,
            bool(raw.get("include_raw_entries", False)),
            bool(raw.get("include_excluded_history", False)),
            usage,
            bool(raw.get("use_progress_history_for_metrics", True)),
            mapping(raw.get("inclusion_reasons", {}), "inclusion_reasons"),
            mapping(raw.get("exclusion_reasons", {}), "exclusion_reasons"),
            strings("missing_data_warnings", 32),
            _number(raw.get("planner_confidence", 0.0), "planner_confidence"),
            decision, reasons,
            strings("priority", 128),
            SCHEMA_VERSION,
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModelSelectionModule:
    module_id: str
    priority: int = 1
    reason: str = ""

    @classmethod
    def from_dict(cls, value: Any) -> "ModelSelectionModule":
        raw = _obj(value, "selected_modules[]")
        _unknown(raw, {"module_id", "priority", "reason"}, "selected_modules[]")
        priority = raw.get("priority", 1)
        if isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 12:
            raise ContractError("selected_modules[].priority is invalid")
        return cls(_text(raw.get("module_id", ""), "selected_modules[].module_id", 120, True), priority, _text(raw.get("reason", ""), "selected_modules[].reason", 120))


@dataclass(frozen=True)
class ModelSelectionFields:
    module_id: str
    field_ids: list[str]
    reason: str = ""

    @classmethod
    def from_dict(cls, value: Any) -> "ModelSelectionFields":
        raw = _obj(value, "selected_fields[]")
        _unknown(raw, {"module_id", "field_ids", "reason"}, "selected_fields[]")
        return cls(_text(raw.get("module_id", ""), "selected_fields[].module_id", 120, True), strings_from(raw.get("field_ids", []), "selected_fields[].field_ids",), _text(raw.get("reason", ""), "selected_fields[].reason", 120))


@dataclass(frozen=True)
class ModelSelectionMovement:
    movement_id: str
    detail_level: str = "summary"
    priority: int = 1
    reason: str = ""

    @classmethod
    def from_dict(cls, value: Any) -> "ModelSelectionMovement":
        raw = _obj(value, "selected_movements[]")
        _unknown(raw, {"movement_id", "detail_level", "priority", "reason"}, "selected_movements[]")
        detail = _text(raw.get("detail_level", "summary"), "selected_movements[].detail_level", 24)
        if detail not in {"summary", "detailed", "full"}:
            raise ContractError("selected_movements[].detail_level is invalid")
        priority = raw.get("priority", 1)
        if isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 16:
            raise ContractError("selected_movements[].priority is invalid")
        return cls(_text(raw.get("movement_id", ""), "selected_movements[].movement_id", 120, True), detail, priority, _text(raw.get("reason", ""), "selected_movements[].reason", 120))


@dataclass(frozen=True)
class ModelSelectionExclusion:
    candidate_id: str
    reason: str = ""

    @classmethod
    def from_dict(cls, value: Any) -> "ModelSelectionExclusion":
        raw = _obj(value, "exclusion_decisions[]")
        _unknown(raw, {"candidate_id", "reason"}, "exclusion_decisions[]")
        return cls(_text(raw.get("candidate_id", ""), "exclusion_decisions[].candidate_id", 160, True), _text(raw.get("reason", ""), "exclusion_decisions[].reason", 120))


@dataclass(frozen=True)
class ModelPlanningSelection:
    schema_version: str
    selected_window_id: str
    selected_modules: list[ModelSelectionModule]
    selected_fields: list[ModelSelectionFields]
    selected_movements: list[ModelSelectionMovement]
    selected_note_candidate_ids: list[str]
    selected_candidate_record_ids: list[str]
    training_detail_level: str
    movement_detail_level: str
    include_raw_entries: bool
    include_excluded_history: bool
    excluded_history_usage: str
    use_progress_history_for_metrics: bool
    missing_data_warning_codes: list[str]
    exclusion_decisions: list[ModelSelectionExclusion]
    planner_confidence: float
    planning_decision: str
    fallback_reason_codes: list[str]

    @classmethod
    def from_dict(cls, value: Any) -> "ModelPlanningSelection":
        raw = _obj(value, "selection")
        allowed = {"schema_version", "selected_window_id", "selected_modules", "selected_fields", "selected_movements", "selected_note_candidate_ids", "selected_candidate_record_ids", "training_detail_level", "movement_detail_level", "include_raw_entries", "include_excluded_history", "excluded_history_usage", "use_progress_history_for_metrics", "missing_data_warning_codes", "exclusion_decisions", "planner_confidence", "planning_decision", "fallback_reason_codes"}
        _unknown(raw, allowed, "selection")
        if raw.get("schema_version") != SELECTION_SCHEMA_VERSION:
            raise ContractError("unsupported selection schema_version")
        def strings(key: str, limit: int) -> list[str]:
            return [_text(item, f"{key}[]", 160, True) for item in _list(raw.get(key, []), key, limit)]
        for key in ("include_raw_entries", "include_excluded_history", "use_progress_history_for_metrics"):
            if not isinstance(raw.get(key), bool):
                raise ContractError(f"{key} must be boolean")
        usage = _text(raw.get("excluded_history_usage", "none"), "excluded_history_usage", 32)
        if usage not in {"none", "context_only"}:
            raise ContractError("excluded_history_usage is invalid")
        details = {"summary", "detailed", "full"}
        training = _text(raw.get("training_detail_level", "summary"), "training_detail_level", 24)
        movement = _text(raw.get("movement_detail_level", "summary"), "movement_detail_level", 24)
        if training not in details or movement not in details:
            raise ContractError("detail level is invalid")
        selection = cls(
            SELECTION_SCHEMA_VERSION,
            _text(raw.get("selected_window_id", ""), "selected_window_id", 160),
            [ModelSelectionModule.from_dict(item) for item in _list(raw.get("selected_modules"), "selected_modules", 12)],
            [ModelSelectionFields.from_dict(item) for item in _list(raw.get("selected_fields"), "selected_fields", 12)],
            [ModelSelectionMovement.from_dict(item) for item in _list(raw.get("selected_movements"), "selected_movements", 16)],
            strings("selected_note_candidate_ids", 64), strings("selected_candidate_record_ids", 128), training, movement,
            bool(raw["include_raw_entries"]), bool(raw["include_excluded_history"]), usage,
            bool(raw["use_progress_history_for_metrics"]), strings("missing_data_warning_codes", 32),
            [ModelSelectionExclusion.from_dict(item) for item in _list(raw.get("exclusion_decisions"), "exclusion_decisions", 64)],
            _number(raw.get("planner_confidence"), "planner_confidence"),
            _text(raw.get("planning_decision"), "planning_decision", 32), strings("fallback_reason_codes", 8),
        )
        if selection.planning_decision not in PLANNING_DECISIONS:
            raise ContractError("planning_decision is invalid")
        if any(code not in FALLBACK_REASON_CODES for code in selection.fallback_reason_codes):
            raise ContractError("fallback_reason_codes contains an unknown code")
        if set(selection.missing_data_warning_codes) & FALLBACK_REASON_CODES:
            raise ContractError("warning and fallback reason codes cannot be mixed")
        if selection.planning_decision == "ready":
            if selection.fallback_reason_codes:
                raise ContractError("ready selection cannot contain fallback reasons")
            if not selection.selected_window_id:
                raise ContractError("ready selection requires a window")
            if not selection.selected_modules:
                raise ContractError("ready selection requires modules")
        elif not selection.fallback_reason_codes:
            raise ContractError("fallback_required selection needs a reason")
        return selection

    def to_dict(self) -> dict:
        return asdict(self)


def strings_from(value: Any, name: str) -> list[str]:
    return [_text(item, f"{name}[]", 120, True) for item in _list(value, name, 32)]


def mapping(value: Any, name: str) -> dict[str, str]:
    raw = _obj(value, name)
    if len(raw) > 128:
        raise ContractError(f"{name} has too many entries")
    return {str(key): _text(item, f"{name}.{key}", 240, True) for key, item in raw.items()}


@dataclass(frozen=True)
class ValidatedExportPlan:
    plan_id: str
    catalog_id: str
    source_snapshot_id: str
    original_request: str
    interpreted_goal: str
    analysis_dimensions: list[str]
    date_range: dict
    selected_modules: list[str]
    selected_fields: dict[str, list[str]]
    selected_movements: list[str]
    notes_selection: list[str]
    candidate_record_ids: list[str]
    training_detail_level: str
    movement_detail_level: str
    include_raw_entries: bool
    include_excluded_history: bool
    excluded_history_usage: str
    use_progress_history_for_metrics: bool
    inclusion_reasons: dict[str, str]
    exclusion_reasons: dict[str, str]
    missing_data_warnings: list[str]
    estimated_record_count: int
    estimated_output_size: int
    planner_confidence: float
    planning_decision: str
    fallback_reason_codes: list[str]
    model_trace_id: str
    generated_at: str = field(default_factory=_now)
    trimmed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PlanExplanation:
    original_request: str
    interpreted_goal: str
    selected_window: dict
    selected_modules: list[str]
    selected_fields: dict[str, list[str]]
    selected_movements: list[str]
    selected_notes: list[str]
    inclusion_reasons: dict[str, str]
    exclusion_reasons: dict[str, str]
    missing_data: list[str]
    output_size: int
    planner_confidence: float
    repaired: bool = False
    trimmed: bool = False
    fallback: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ManualFallbackResult:
    fallback_required: bool
    fallback_reason: str
    resolved_explicit_constraints: dict
    manual_export_prefill: dict
    warnings: list[str]
    trace_id: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModelCallResult:
    raw_text: str
    adapter: str
    model: str
    duration_ms: int = 0
    response_keys: list[str] = field(default_factory=list)
    message_keys: list[str] = field(default_factory=list)
    finish_reason: str = ""
    eval_count: int = 0
    prompt_eval_count: int = 0
    truncated: bool = False
    output_chars: int = 0
    http_status: int = 0
    response_bytes: int = 0
    load_duration_ns: int = 0
    prompt_eval_duration_ns: int = 0
    eval_duration_ns: int = 0


@dataclass(frozen=True)
class TraceRecord:
    trace_id: str
    request_hash: str
    catalog_hash: str
    plan_hash: str = ""
    adapter: str = ""
    model: str = ""
    prompt_version: str = ""
    schema_version: str = SCHEMA_VERSION
    duration_ms: int = 0
    error_code: str = ""
    repaired: bool = False
    trimmed: bool = False
    fallback: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "additionalProperties": False, "properties": properties, "required": required}


def intent_json_schema() -> dict:
    return _schema({
        "schema_version": {"type": "string", "const": INTENT_SCHEMA_VERSION},
        "dimensions": {"type": "array", "maxItems": len(INTENT_DIMENSIONS), "uniqueItems": True, "items": {"type": "string", "enum": list(INTENT_DIMENSIONS)}},
        "excluded_dimensions": {"type": "array", "maxItems": len(INTENT_DIMENSIONS), "uniqueItems": True, "items": {"type": "string", "enum": list(INTENT_DIMENSIONS)}},
        "date_text": {"type": "array", "maxItems": 8, "items": {"type": "string", "minLength": 1, "maxLength": 80}},
        "movement_mentions": {"type": "array", "maxItems": 8, "items": {"type": "string", "minLength": 1, "maxLength": 120}},
        "target_body_parts": {"type": "array", "maxItems": 6, "uniqueItems": True, "items": {"type": "string", "enum": list(BODY_PART_IDS)}},
        "ambiguous": {"type": "boolean"},
    }, ["schema_version", "dimensions", "excluded_dimensions", "date_text", "movement_mentions", "target_body_parts", "ambiguous"])


def semantic_hints_json_schema() -> dict:
    return _schema({
        "schema_version": {"type": "string", "const": SEMANTIC_HINTS_SCHEMA_VERSION},
        "semantic_hints": {
            "type": "array",
            "maxItems": 8,
            "items": _schema({
                "dimension": {"type": "string", "enum": list(SEMANTIC_HINT_DIMENSIONS)},
                "evidence": {"type": "string", "minLength": 1, "maxLength": 120},
            }, ["dimension", "evidence"]),
        },
    }, ["schema_version", "semantic_hints"])


def plan_json_schema() -> dict:
    text_array = {"type": "array", "maxItems": 128, "items": {"type": "string", "minLength": 1, "maxLength": 120}}
    return _schema({
        "schema_version": {"type": "string", "const": SCHEMA_VERSION},
        "interpreted_goal": {"type": "string", "minLength": 1, "maxLength": 400},
        "analysis_dimensions": text_array,
        "date_range": _schema({"window_id": {"type": "string", "maxLength": 120}, "requested_start": {"type": "string", "maxLength": 10}, "requested_end": {"type": "string", "maxLength": 10}, "resolved_start": {"type": "string", "maxLength": 10}, "resolved_end": {"type": "string", "maxLength": 10}, "anchor": {"type": "string", "maxLength": 32}}, ["window_id", "requested_start", "requested_end", "resolved_start", "resolved_end", "anchor"]),
        "selected_modules": text_array, "selected_fields": {"type": "object", "additionalProperties": {"type": "array", "maxItems": 32, "items": {"type": "string", "maxLength": 120}}}, "selected_movements": text_array, "notes_selection": text_array, "candidate_record_ids": text_array,
        "training_detail_level": {"type": "string", "enum": ["summary", "detailed", "full"]}, "movement_detail_level": {"type": "string", "enum": ["summary", "detailed", "full"]}, "include_raw_entries": {"type": "boolean"}, "include_excluded_history": {"type": "boolean"}, "excluded_history_usage": {"type": "string", "enum": ["none", "context_only"]}, "use_progress_history_for_metrics": {"type": "boolean"}, "inclusion_reasons": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 240}}, "exclusion_reasons": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 240}}, "missing_data_warnings": {"type": "array", "maxItems": 32, "items": {"type": "string", "maxLength": 240}}, "planner_confidence": {"type": "number", "minimum": 0, "maximum": 1}, "needs_fallback": {"type": "boolean"}, "priority": text_array,
    }, ["schema_version", "interpreted_goal", "analysis_dimensions", "date_range", "selected_modules", "selected_fields", "selected_movements", "notes_selection", "candidate_record_ids", "training_detail_level", "movement_detail_level", "include_raw_entries", "include_excluded_history", "excluded_history_usage", "use_progress_history_for_metrics", "inclusion_reasons", "exclusion_reasons", "missing_data_warnings", "planner_confidence", "needs_fallback", "priority"])


def repair_json_schema() -> dict:
    return selection_json_schema()


def selection_json_schema(allowed_window_ids: list[str] | None = None) -> dict:
    # Keep the Ollama schema compact while mirroring runtime nested bounds;
    # this prevents common malformed optional objects from forcing Repair.
    non_empty = {"type": "string", "minLength": 1, "maxLength": 160}
    short_text = {"type": "string", "maxLength": 120}
    module = {"type": "object", "additionalProperties": False, "properties": {"module_id": non_empty, "priority": {"type": "integer", "minimum": 1, "maximum": 12}, "reason": short_text}, "required": ["module_id", "priority", "reason"]}
    fields = {"type": "object", "additionalProperties": False, "properties": {"module_id": non_empty, "field_ids": {"type": "array", "items": {"type": "string", "maxLength": 120}}, "reason": short_text}, "required": ["module_id", "field_ids", "reason"]}
    movement = {"type": "object", "additionalProperties": False, "properties": {"movement_id": non_empty, "detail_level": {"type": "string", "enum": ["summary", "detailed", "full"]}, "priority": {"type": "integer", "minimum": 1, "maximum": 16}, "reason": short_text}, "required": ["movement_id", "detail_level", "priority", "reason"]}
    exclusion = {"type": "object", "additionalProperties": False, "properties": {"candidate_id": non_empty, "reason": short_text}, "required": ["candidate_id", "reason"]}
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "schema_version": {"type": "string", "const": SELECTION_SCHEMA_VERSION},
        "selected_window_id": non_empty,
        "selected_modules": {"type": "array", "maxItems": 12, "items": module},
        "selected_fields": {"type": "array", "maxItems": 12, "items": fields},
        "selected_movements": {"type": "array", "maxItems": 16, "items": movement},
        "selected_note_candidate_ids": {"type": "array", "maxItems": 64, "items": {"type": "string", "maxLength": 160}},
        "selected_candidate_record_ids": {"type": "array", "maxItems": 128, "items": {"type": "string", "maxLength": 160}},
        "training_detail_level": {"type": "string", "enum": ["summary", "detailed", "full"]},
        "movement_detail_level": {"type": "string", "enum": ["summary", "detailed", "full"]},
        "include_raw_entries": {"type": "boolean"}, "include_excluded_history": {"type": "boolean"},
        "excluded_history_usage": {"type": "string", "enum": ["none", "context_only"]},
        "use_progress_history_for_metrics": {"type": "boolean"},
        "missing_data_warning_codes": {"type": "array", "items": {"type": "string"}},
        "exclusion_decisions": {"type": "array", "maxItems": 64, "items": exclusion},
        "planner_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "planning_decision": {"type": "string", "enum": ["ready", "fallback_required"]},
        "fallback_reason_codes": {"type": "array", "maxItems": 8, "items": {"type": "string", "enum": sorted(FALLBACK_REASON_CODES)}},
    }, "required": ["schema_version", "selected_window_id", "selected_modules", "selected_fields", "selected_movements", "selected_note_candidate_ids", "selected_candidate_record_ids", "training_detail_level", "movement_detail_level", "include_raw_entries", "include_excluded_history", "excluded_history_usage", "use_progress_history_for_metrics", "missing_data_warning_codes", "exclusion_decisions", "planner_confidence", "planning_decision", "fallback_reason_codes"]}
    if allowed_window_ids:
        schema["properties"]["selected_window_id"] = {"type": "string", "enum": list(allowed_window_ids)}
    return schema
