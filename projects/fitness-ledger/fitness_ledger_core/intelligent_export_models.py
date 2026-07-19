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
from typing import Any


SCHEMA_VERSION = "fitness-ledger-intelligent-export-v1"
MAX_LIST = 64
MAX_TEXT = 400


class ContractError(ValueError):
    """Raised when a model response violates a Core contract."""


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
    kind: str = "unspecified"
    start: str | None = None
    end: str | None = None
    days: int | None = None
    anchor: str = "latest"

    @classmethod
    def from_dict(cls, value: Any) -> "DateIntent":
        raw = _obj(value, "date_intent")
        _unknown(raw, {"kind", "start", "end", "days", "anchor"}, "date_intent")
        kind = _text(raw.get("kind", "unspecified"), "date_intent.kind", 32)
        if kind not in {"unspecified", "explicit_range", "relative", "all"}:
            raise ContractError("date_intent.kind is invalid")
        days = raw.get("days")
        if days is not None and (isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 36500):
            raise ContractError("date_intent.days is invalid")
        return cls(kind, raw.get("start"), raw.get("end"), days, _text(raw.get("anchor", "latest"), "date_intent.anchor", 32))


@dataclass(frozen=True)
class MovementMention:
    text: str
    confidence: float = 0.0
    body_part: str = ""

    @classmethod
    def from_dict(cls, value: Any) -> "MovementMention":
        raw = _obj(value, "movement_mention")
        _unknown(raw, {"text", "confidence", "body_part"}, "movement_mention")
        return cls(
            _text(raw.get("text", ""), "movement_mention.text", 120, True),
            _number(raw.get("confidence", 0.0), "movement_mention.confidence"),
            _text(raw.get("body_part", ""), "movement_mention.body_part", 80),
        )


@dataclass(frozen=True)
class IntentSpec:
    interpreted_goal: str
    analysis_dimensions: list[str]
    date_intent: DateIntent
    movement_mentions: list[MovementMention]
    catalog_requirements: list[str]
    preferred_detail: str = "summary"
    raw_entry_relevance: str = "none"
    confidence: float = 0.0
    needs_fallback: bool = False
    warnings: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Any) -> "IntentSpec":
        raw = _obj(value, "intent")
        allowed = {"schema_version", "interpreted_goal", "analysis_dimensions", "date_intent", "movement_mentions", "catalog_requirements", "preferred_detail", "raw_entry_relevance", "confidence", "needs_fallback", "warnings"}
        _unknown(raw, allowed, "intent")
        if raw.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ContractError("unsupported intent schema_version")
        dimensions = [_text(item, "analysis_dimensions[]", 64, True) for item in _list(raw.get("analysis_dimensions", []), "analysis_dimensions", 12)]
        requirements = [_text(item, "catalog_requirements[]", 64, True) for item in _list(raw.get("catalog_requirements", []), "catalog_requirements", 12)]
        warnings = [_text(item, "warnings[]", 240) for item in _list(raw.get("warnings", []), "warnings", 12)]
        detail = _text(raw.get("preferred_detail", "summary"), "preferred_detail", 40)
        raw_relevance = _text(raw.get("raw_entry_relevance", "none"), "raw_entry_relevance", 32)
        if raw_relevance not in {"none", "preview", "requested"}:
            raise ContractError("raw_entry_relevance is invalid")
        if not isinstance(raw.get("needs_fallback", False), bool):
            raise ContractError("needs_fallback must be boolean")
        return cls(
            _text(raw.get("interpreted_goal", ""), "interpreted_goal", 400, True),
            dimensions,
            DateIntent.from_dict(raw.get("date_intent", {})),
            [MovementMention.from_dict(item) for item in _list(raw.get("movement_mentions", []), "movement_mentions", 8)],
            requirements,
            detail,
            raw_relevance,
            _number(raw.get("confidence", 0.0), "confidence"),
            bool(raw.get("needs_fallback", False)),
            warnings,
            SCHEMA_VERSION,
        )

    def to_dict(self) -> dict:
        return asdict(self)


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
    needs_fallback: bool = False
    priority: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Any) -> "ExportPlanDraft":
        raw = _obj(value, "plan")
        allowed = {"schema_version", "interpreted_goal", "analysis_dimensions", "date_range", "selected_modules", "selected_fields", "selected_movements", "notes_selection", "candidate_record_ids", "training_detail_level", "movement_detail_level", "include_raw_entries", "include_excluded_history", "excluded_history_usage", "use_progress_history_for_metrics", "inclusion_reasons", "exclusion_reasons", "missing_data_warnings", "planner_confidence", "needs_fallback", "priority"}
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
        for key in ("include_raw_entries", "include_excluded_history", "use_progress_history_for_metrics", "needs_fallback"):
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
            bool(raw.get("needs_fallback", False)),
            strings("priority", 128),
            SCHEMA_VERSION,
        )

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
    needs_fallback: bool
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
        "schema_version": {"type": "string", "const": SCHEMA_VERSION},
        "interpreted_goal": {"type": "string", "minLength": 1, "maxLength": 400},
        "analysis_dimensions": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 64}},
        "date_intent": _schema({"kind": {"type": "string", "enum": ["unspecified", "explicit_range", "relative", "all"]}, "start": {"type": ["string", "null"], "maxLength": 10}, "end": {"type": ["string", "null"], "maxLength": 10}, "days": {"type": ["integer", "null"], "minimum": 1, "maximum": 36500}, "anchor": {"type": "string", "maxLength": 32}}, ["kind"]),
        "movement_mentions": {"type": "array", "maxItems": 8, "items": _schema({"text": {"type": "string", "minLength": 1, "maxLength": 120}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "body_part": {"type": "string", "maxLength": 80}}, ["text", "confidence", "body_part"])},
        "catalog_requirements": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 64}},
        "preferred_detail": {"type": "string", "maxLength": 40},
        "raw_entry_relevance": {"type": "string", "enum": ["none", "preview", "requested"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "needs_fallback": {"type": "boolean"},
        "warnings": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 240}},
    }, ["schema_version", "interpreted_goal", "analysis_dimensions", "date_intent", "movement_mentions", "catalog_requirements", "preferred_detail", "raw_entry_relevance", "confidence", "needs_fallback", "warnings"])


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
    return plan_json_schema()
