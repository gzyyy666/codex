"""Milestone 1 contracts for the local Intelligent Export analysis route.

This module is deliberately a boundary, not an execution pipeline.  It
describes what a future model may request, maps those requests to the
existing deterministic Core capabilities, and records review state.  It does
not call a model, create an ExportPlan, choose a Notes scope, grant Raw
access, or write data.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from typing import Any


FOUNDATION_SCHEMA_VERSION = "fitness-ledger-intelligent-export-foundation-v1"
REGISTRY_SCHEMA_VERSION = "fitness-ledger-capability-registry-v1"
REQUIREMENT_SCHEMA_VERSION = "fitness-ledger-analysis-requirement-v1"
MAPPING_SCHEMA_VERSION = "fitness-ledger-requirement-mapping-v1"
GPT_PACKAGE_SCHEMA_VERSION = "fitness-ledger-gpt-analysis-package-v1"
TRACE_SCHEMA_VERSION = "fitness-ledger-analysis-trace-v1"
CORRECTION_SCHEMA_VERSION = "fitness-ledger-human-correction-v1"


ERRORS = {
    "SCHEMA_INVALID": ("contract", "合约格式无效。", False),
    "EVIDENCE_NOT_GROUNDED": ("contract", "模型证据无法在用户目标中核验。", False),
    "FORMAL_DATE_FORBIDDEN": ("contract", "模型不得生成正式起止日期。", False),
    "FORMAL_ID_FORBIDDEN": ("permission", "模型不得决定正式字段或记录 ID。", False),
    "UNKNOWN_CAPABILITY": ("mapping", "请求引用了当前 Registry 不存在的能力。", False),
    "CAPABILITY_NOT_MODEL_SELECTABLE": ("permission", "该能力不能由模型授予。", False),
    "RAW_PERMISSION_NOT_GRANTABLE": ("permission", "Raw 权限必须来自用户明确请求与确定性 Core。", False),
    "NOTES_SCOPE_REQUIRES_CONFIRMATION": ("permission", "Notes 作用域必须由确定性 Core 或用户确认。", False),
    "MAPPING_INVALID": ("mapping", "需求映射无法形成安全的能力候选。", False),
    "PACKAGE_INVALID": ("contract", "GPT 分析包不符合 Foundation Contract。", False),
    "TRACE_INVALID_TRANSITION": ("state", "分析候选状态变化不被允许。", False),
    "HUMAN_DECISION_INVALID": ("state", "人工修正决定无效。", False),
    "EVALUATION_DATASET_INVALID": ("evaluation", "匿名评估数据集不符合合约。", False),
    "EVALUATION_DATA_LEAKAGE": ("evaluation", "评估数据集存在 Golden/Holdout 泄漏。", False),
    "EVALUATION_PRIVACY_VIOLATION": ("evaluation", "评估数据集包含被禁止的隐私或正式数据标识。", False),
    "EVALUATION_CASE_INVALID": ("evaluation", "评估案例不符合合约。", False),
    "EVALUATION_CANDIDATE_MISSING": ("evaluation", "评估案例缺少候选需求。", False),
}


class FoundationError(ValueError):
    """One error type for every Milestone 1 contract boundary."""

    def __init__(self, message: str, code: str = "SCHEMA_INVALID") -> None:
        super().__init__(message)
        self.code = code


def foundation_error_info(code: str) -> dict[str, Any]:
    category, user_message, retryable = ERRORS.get(code, ERRORS["SCHEMA_INVALID"])
    return {"code": code, "category": category, "user": user_message, "retryable": retryable}


def _error(code: str, message: str) -> FoundationError:
    return FoundationError(message, code)


def _obj(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error("SCHEMA_INVALID", f"{name} must be an object")
    return value


def _unknown(value: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _error("SCHEMA_INVALID", f"{name} contains unknown fields: {', '.join(unknown)}")


def _text(value: Any, name: str, limit: int = 400, required: bool = False) -> str:
    if not isinstance(value, str):
        raise _error("SCHEMA_INVALID", f"{name} must be a string")
    if required and not value.strip():
        raise _error("SCHEMA_INVALID", f"{name} must not be empty")
    if len(value) > limit:
        raise _error("SCHEMA_INVALID", f"{name} exceeds {limit} characters")
    return value.strip()


def _items(value: Any, name: str, limit: int = 32) -> list[Any]:
    if not isinstance(value, list):
        raise _error("SCHEMA_INVALID", f"{name} must be an array")
    if len(value) > limit:
        raise _error("SCHEMA_INVALID", f"{name} exceeds {limit} items")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise _error("SCHEMA_INVALID", f"{name} must be boolean")
    return value


def _number(value: Any, name: str, minimum: float = 0, maximum: float = 1) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error("SCHEMA_INVALID", f"{name} must be numeric")
    result = float(value)
    if not minimum <= result <= maximum:
        raise _error("SCHEMA_INVALID", f"{name} is outside [{minimum}, {maximum}]")
    return result


def _strings(value: Any, name: str, limit: int = 32, text_limit: int = 400) -> list[str]:
    return [_text(item, f"{name}[]", text_limit, True) for item in _items(value, name, limit)]


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.casefold())


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", value.casefold())


def _contains_formal_date(value: str) -> bool:
    return bool(
        re.search(r"(?<!\d)\d{4}[-/]\d{1,2}[-/]\d{1,2}(?!\d)", value)
        or re.search(r"\d{4}年\s*\d{1,2}月\s*\d{1,2}[日号]", value)
    )


def _grounded(evidence: str, user_goal: str) -> bool:
    """Conservative lexical grounding for model-provided evidence.

    It accepts an exact fragment or a short paraphrase with substantial token
    overlap.  This is intentionally not a semantic truth oracle: it only
    prevents the model from presenting unrelated facts as user evidence.
    """

    source, candidate = _normalized(user_goal), _normalized(evidence)
    if not source or not candidate:
        return False
    if candidate in source:
        return True
    source_tokens, evidence_tokens = set(_tokens(user_goal)), set(_tokens(evidence))
    if not evidence_tokens:
        return False
    overlap = len(source_tokens & evidence_tokens) / len(evidence_tokens)
    if overlap < 0.6 or len(source_tokens & evidence_tokens) < 2:
        return False
    numbers = set(re.findall(r"\d+(?:\.\d+)?", evidence))
    return numbers.issubset(set(re.findall(r"\d+(?:\.\d+)?", user_goal)))


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    label: str
    description: str
    source_contracts: tuple[str, ...]
    semantic_dimensions: tuple[str, ...]
    model_selectable: bool = True
    requires_user_confirmation: bool = False
    grants_raw: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "label": self.label,
            "description": self.description,
            "source_contracts": list(self.source_contracts),
            "semantic_dimensions": list(self.semantic_dimensions),
            "model_selectable": self.model_selectable,
            "requires_user_confirmation": self.requires_user_confirmation,
            "grants_raw": self.grants_raw,
        }


CAPABILITY_DEFINITIONS = (
    CapabilityDefinition(
        "body_history",
        "Body history",
        "Analyze recorded body-state history and its available coverage.",
        ("DataCatalogBuilder.module:body", "AnalysisExportCommandParser.domain:body", "IntentCompiler.dimension:body_state"),
        ("body_state",),
    ),
    CapabilityDefinition(
        "diet_macros",
        "Diet macros",
        "Analyze recorded calories, protein, carbohydrates, and fat history.",
        ("DataCatalogBuilder.module:diet", "AnalysisExportCommandParser.domain:diet", "IntentCompiler.dimension:diet_macros"),
        ("diet_macros",),
    ),
    CapabilityDefinition(
        "training_context",
        "Training context",
        "Analyze training-day and session context without inventing movements.",
        ("DataCatalogBuilder.module:training", "AnalysisExportCommandParser.domain:training", "IntentCompiler.dimension:training_context"),
        ("training_context",),
    ),
    CapabilityDefinition(
        "movement_progress",
        "Movement progress",
        "Analyze an already-resolved movement or body-part progress history.",
        ("DataCatalogBuilder.module:movement_history", "MovementResolver", "IntentCompiler.dimension:movement_progress", "AnalysisExportCommandParser.movement_scope"),
        ("movement_progress",),
    ),
    CapabilityDefinition(
        "notes_context",
        "Notes context",
        "Use Notes only after deterministic scope resolution or explicit user confirmation.",
        ("DataCatalogBuilder.notes", "fitness_ledger_core.notes", "AnalysisExportCommandParser.notes_scope"),
        ("daily_notes", "diet_notes", "training_notes", "movement_notes"),
        requires_user_confirmation=True,
    ),
    CapabilityDefinition(
        "raw_trace",
        "Raw trace",
        "Expose preserved raw input only after an explicit user request.",
        ("DataCatalogBuilder.module:raw_entries", "AnalysisExportCommandParser.raw_permission", "ExportPlanValidator.raw_boundary", "ExportExecutor"),
        ("raw_trace",),
        model_selectable=False,
        grants_raw=True,
    ),
)


class CapabilityRegistryV1:
    """The only capability vocabulary available to Requirement Mapping."""

    schema_version = REGISTRY_SCHEMA_VERSION

    def __init__(self, definitions: tuple[CapabilityDefinition, ...] = CAPABILITY_DEFINITIONS) -> None:
        self._definitions = tuple(definitions)
        ids = [item.capability_id for item in self._definitions]
        if len(ids) != len(set(ids)):
            raise _error("SCHEMA_INVALID", "Capability Registry contains duplicate capability IDs")

    @property
    def capabilities(self) -> tuple[CapabilityDefinition, ...]:
        return self._definitions

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(item.capability_id for item in self._definitions)

    def get(self, capability_id: str) -> CapabilityDefinition | None:
        return next((item for item in self._definitions if item.capability_id == capability_id), None)

    def require(self, capability_id: str) -> CapabilityDefinition:
        result = self.get(capability_id)
        if result is None:
            raise _error("UNKNOWN_CAPABILITY", f"unknown capability: {capability_id}")
        return result

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "capabilities": [item.to_dict() for item in self._definitions]}

    @staticmethod
    def json_schema() -> dict[str, Any]:
        capability = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "capability_id": {"type": "string", "minLength": 1, "maxLength": 80},
                "label": {"type": "string", "minLength": 1, "maxLength": 120},
                "description": {"type": "string", "minLength": 1, "maxLength": 300},
                "source_contracts": {"type": "array", "minItems": 1, "items": {"type": "string", "maxLength": 160}},
                "semantic_dimensions": {"type": "array", "minItems": 1, "items": {"type": "string", "maxLength": 80}},
                "model_selectable": {"type": "boolean"},
                "requires_user_confirmation": {"type": "boolean"},
                "grants_raw": {"type": "boolean"},
            },
            "required": ["capability_id", "label", "description", "source_contracts", "semantic_dimensions", "model_selectable", "requires_user_confirmation", "grants_raw"],
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "schema_version": {"type": "string", "const": REGISTRY_SCHEMA_VERSION},
                "capabilities": {"type": "array", "minItems": 1, "items": capability},
            },
            "required": ["schema_version", "capabilities"],
        }


@dataclass(frozen=True)
class CapabilityRequest:
    capability_id: str
    reason: str

    @classmethod
    def from_dict(cls, value: Any, name: str = "capability") -> "CapabilityRequest":
        raw = _obj(value, name)
        _unknown(raw, {"capability_id", "reason"}, name)
        return cls(_text(raw.get("capability_id"), f"{name}.capability_id", 80, True), _text(raw.get("reason"), f"{name}.reason", 240, True))

    def to_dict(self) -> dict[str, str]:
        return {"capability_id": self.capability_id, "reason": self.reason}


@dataclass(frozen=True)
class PreferredTimeWindow:
    kind: str = "unspecified"
    label: str = ""

    ALLOWED = {"unspecified", "recent", "last_week", "recent_months", "all_available", "explicit_user_phrase"}

    @classmethod
    def from_dict(cls, value: Any) -> "PreferredTimeWindow":
        raw = _obj(value, "preferred_time_window")
        _unknown(raw, {"kind", "label"}, "preferred_time_window")
        kind = _text(raw.get("kind", "unspecified"), "preferred_time_window.kind", 32)
        label = _text(raw.get("label", ""), "preferred_time_window.label", 120)
        if kind not in cls.ALLOWED:
            raise _error("SCHEMA_INVALID", "preferred_time_window.kind is invalid")
        if kind == "unspecified" and label:
            raise _error("SCHEMA_INVALID", "unspecified preferred_time_window cannot have a label")
        if kind != "unspecified" and not label:
            raise _error("SCHEMA_INVALID", "preferred_time_window.label is required")
        if _contains_formal_date(label):
            raise _error("FORMAL_DATE_FORBIDDEN", "preferred_time_window cannot contain a formal date")
        return cls(kind, label)

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "label": self.label}


@dataclass(frozen=True)
class DerivedMetric:
    name: str
    reason: str

    @classmethod
    def from_dict(cls, value: Any, name: str = "derived_metrics[]") -> "DerivedMetric":
        raw = _obj(value, name)
        _unknown(raw, {"name", "reason"}, name)
        return cls(_text(raw.get("name"), f"{name}.name", 100, True), _text(raw.get("reason"), f"{name}.reason", 240, True))

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceItem:
    text: str
    source: str = "user_goal"

    @classmethod
    def from_dict(cls, value: Any, user_goal: str, name: str = "evidence[]") -> "EvidenceItem":
        raw = _obj(value, name)
        _unknown(raw, {"text", "source"}, name)
        text = _text(raw.get("text"), f"{name}.text", 240, True)
        source = _text(raw.get("source", "user_goal"), f"{name}.source", 32, True)
        if source != "user_goal" or not _grounded(text, user_goal):
            raise _error("EVIDENCE_NOT_GROUNDED", f"{name} must quote or conservatively paraphrase user_goal")
        return cls(text, source)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisRequirementSpecV1:
    """The complete model-facing requirement object, before deterministic mapping."""

    analysis_goal: str
    questions_to_answer: list[str]
    required_capabilities: list[CapabilityRequest]
    optional_capabilities: list[CapabilityRequest]
    preferred_time_window: PreferredTimeWindow
    derived_metrics: list[DerivedMetric]
    missing_information: list[str]
    clarifications: list[str]
    evidence: list[EvidenceItem]
    gpt_prompt_outline: list[str]
    schema_version: str = REQUIREMENT_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Any, user_goal: str = "") -> "AnalysisRequirementSpecV1":
        raw = _obj(value, "analysis_requirement")
        allowed = {"schema_version", "analysis_goal", "questions_to_answer", "required_capabilities", "optional_capabilities", "preferred_time_window", "derived_metrics", "missing_information", "clarifications", "evidence", "gpt_prompt_outline"}
        _unknown(raw, allowed, "analysis_requirement")
        if raw.get("schema_version") != REQUIREMENT_SCHEMA_VERSION:
            raise _error("SCHEMA_INVALID", "unsupported AnalysisRequirementSpec schema_version")
        required = [CapabilityRequest.from_dict(item, "required_capabilities[]") for item in _items(raw.get("required_capabilities"), "required_capabilities", 16)]
        optional = [CapabilityRequest.from_dict(item, "optional_capabilities[]") for item in _items(raw.get("optional_capabilities"), "optional_capabilities", 16)]
        required_ids = [item.capability_id for item in required]
        optional_ids = [item.capability_id for item in optional]
        if len(required_ids) != len(set(required_ids)) or len(optional_ids) != len(set(optional_ids)):
            raise _error("SCHEMA_INVALID", "capability requests must not contain duplicates")
        if set(required_ids) & set(optional_ids):
            raise _error("SCHEMA_INVALID", "a capability cannot be both required and optional")
        evidence = [EvidenceItem.from_dict(item, user_goal) for item in _items(raw.get("evidence"), "evidence", 16)]
        return cls(
            _text(raw.get("analysis_goal"), "analysis_goal", 400, True),
            _strings(raw.get("questions_to_answer"), "questions_to_answer", 16, 300),
            required,
            optional,
            PreferredTimeWindow.from_dict(raw.get("preferred_time_window")),
            [DerivedMetric.from_dict(item) for item in _items(raw.get("derived_metrics"), "derived_metrics", 16)],
            _strings(raw.get("missing_information"), "missing_information", 16, 240),
            _strings(raw.get("clarifications"), "clarifications", 16, 240),
            evidence,
            _strings(raw.get("gpt_prompt_outline"), "gpt_prompt_outline", 16, 300),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_goal": self.analysis_goal,
            "questions_to_answer": list(self.questions_to_answer),
            "required_capabilities": [item.to_dict() for item in self.required_capabilities],
            "optional_capabilities": [item.to_dict() for item in self.optional_capabilities],
            "preferred_time_window": self.preferred_time_window.to_dict(),
            "derived_metrics": [item.to_dict() for item in self.derived_metrics],
            "missing_information": list(self.missing_information),
            "clarifications": list(self.clarifications),
            "evidence": [item.to_dict() for item in self.evidence],
            "gpt_prompt_outline": list(self.gpt_prompt_outline),
        }

    @staticmethod
    def json_schema() -> dict[str, Any]:
        capability = {"type": "object", "additionalProperties": False, "properties": {"capability_id": {"type": "string", "minLength": 1, "maxLength": 80}, "reason": {"type": "string", "minLength": 1, "maxLength": 240}}, "required": ["capability_id", "reason"]}
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "schema_version": {"type": "string", "const": REQUIREMENT_SCHEMA_VERSION},
                "analysis_goal": {"type": "string", "minLength": 1, "maxLength": 400},
                "questions_to_answer": {"type": "array", "maxItems": 16, "items": {"type": "string", "maxLength": 300}},
                "required_capabilities": {"type": "array", "maxItems": 16, "items": capability},
                "optional_capabilities": {"type": "array", "maxItems": 16, "items": capability},
                "preferred_time_window": {"type": "object", "additionalProperties": False, "properties": {"kind": {"type": "string", "enum": sorted(PreferredTimeWindow.ALLOWED)}, "label": {"type": "string", "maxLength": 120}}, "required": ["kind", "label"]},
                "derived_metrics": {"type": "array", "maxItems": 16, "items": {"type": "object", "additionalProperties": False, "properties": {"name": {"type": "string", "maxLength": 100}, "reason": {"type": "string", "maxLength": 240}}, "required": ["name", "reason"]}},
                "missing_information": {"type": "array", "maxItems": 16, "items": {"type": "string", "maxLength": 240}},
                "clarifications": {"type": "array", "maxItems": 16, "items": {"type": "string", "maxLength": 240}},
                "evidence": {"type": "array", "maxItems": 16, "items": {"type": "object", "additionalProperties": False, "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 240}, "source": {"const": "user_goal"}}, "required": ["text", "source"]}},
                "gpt_prompt_outline": {"type": "array", "maxItems": 16, "items": {"type": "string", "maxLength": 300}},
            },
            "required": ["schema_version", "analysis_goal", "questions_to_answer", "required_capabilities", "optional_capabilities", "preferred_time_window", "derived_metrics", "missing_information", "clarifications", "evidence", "gpt_prompt_outline"],
        }


@dataclass(frozen=True)
class MappedCapability:
    capability_id: str
    requirement_kind: str
    reason: str
    source_contracts: list[str]
    status: str = "available"
    requires_user_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RequirementMapping:
    mapped_capabilities: list[MappedCapability]
    unresolved_capabilities: list[str]
    date_resolution_status: str = "deferred_to_date_range_resolver_and_user_confirmation"
    notes_scope_status: str = "not_selected"
    raw_permission_status: str = "not_granted"
    schema_version: str = MAPPING_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mapped_capabilities": [item.to_dict() for item in self.mapped_capabilities],
            "unresolved_capabilities": list(self.unresolved_capabilities),
            "date_resolution_status": self.date_resolution_status,
            "notes_scope_status": self.notes_scope_status,
            "raw_permission_status": self.raw_permission_status,
        }


class RequirementMapper:
    """Map only to Registry capabilities; never to fields, records, or plans."""

    def __init__(self, registry: CapabilityRegistryV1 | None = None) -> None:
        self.registry = registry or CapabilityRegistryV1()

    def map(self, requirement: AnalysisRequirementSpecV1) -> RequirementMapping:
        mapped: list[MappedCapability] = []
        for kind, requests in (("required", requirement.required_capabilities), ("optional", requirement.optional_capabilities)):
            for request in requests:
                definition = self.registry.get(request.capability_id)
                if definition is None:
                    raise _error("UNKNOWN_CAPABILITY", f"unknown capability: {request.capability_id}")
                if not definition.model_selectable:
                    code = "RAW_PERMISSION_NOT_GRANTABLE" if definition.grants_raw else "CAPABILITY_NOT_MODEL_SELECTABLE"
                    raise _error(code, f"model cannot grant capability: {request.capability_id}")
                mapped.append(MappedCapability(
                    definition.capability_id,
                    kind,
                    request.reason,
                    list(definition.source_contracts),
                    "requires_confirmation" if definition.requires_user_confirmation else "available",
                    definition.requires_user_confirmation,
                ))
        return RequirementMapping(
            mapped,
            [],
            notes_scope_status="requires_user_confirmation" if any(item.capability_id == "notes_context" for item in mapped) else "not_selected",
        )

    def resolve_confirmed_date_candidates(self, requirement: AnalysisRequirementSpecV1, user_goal: str, catalog: Any, confirmed: bool = False, today: date | None = None) -> list[dict[str, str]]:
        """Use the existing DateRangeResolver only after user confirmation.

        The returned windows are deterministic candidates, not an ExportPlan.
        A high-level model preference alone therefore cannot create dates.
        """

        if not confirmed:
            return []
        from .data_catalog import DateRangeResolver
        from .intelligent_export_models import DateIntent, IntentSpec

        preferred = requirement.preferred_time_window
        if preferred.kind == "explicit_user_phrase":
            date_intent = DateIntent("explicit", None, False, [preferred.label])
        elif preferred.kind == "all_available":
            date_intent = DateIntent("all_available", "all_available", False, [])
        elif preferred.kind == "unspecified":
            date_intent = DateIntent()
        else:
            relative = {"recent": "recent", "last_week": "last_week", "recent_months": "recent_months"}[preferred.kind]
            date_intent = DateIntent("relative", relative, False, [])
        intent = IntentSpec([], [], [], [], [], False, date_intent=date_intent)
        windows = DateRangeResolver().resolve(intent, catalog, user_goal, today=today)
        return [{"window_id": item.window_id, "requested_start": item.requested_start, "requested_end": item.requested_end, "resolved_start": item.resolved_start, "resolved_end": item.resolved_end} for item in windows]


@dataclass(frozen=True)
class PackageDataBlock:
    capability_id: str
    source_contract: str
    facts: list[str]

    @classmethod
    def from_dict(cls, value: Any) -> "PackageDataBlock":
        raw = _obj(value, "data_blocks[]")
        _unknown(raw, {"capability_id", "source_contract", "facts"}, "data_blocks[]")
        return cls(_text(raw.get("capability_id"), "data_blocks[].capability_id", 80, True), _text(raw.get("source_contract"), "data_blocks[].source_contract", 160, True), _strings(raw.get("facts"), "data_blocks[].facts", 64, 400))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GPTAnalysisPackage:
    """Deterministic, read-only input package for a future GPT analysis call."""

    package_id: str
    source_snapshot_id: str
    user_goal: str
    analysis_goal: str
    questions_to_answer: list[str]
    capability_ids: list[str]
    preferred_time_window: PreferredTimeWindow
    confirmed_time_window: dict[str, str] | None
    derived_metrics: list[DerivedMetric]
    missing_information: list[str]
    clarifications: list[str]
    evidence: list[EvidenceItem]
    gpt_prompt_outline: list[str]
    data_blocks: list[PackageDataBlock]
    raw_included: bool = False
    notes_scope: str | None = None
    schema_version: str = GPT_PACKAGE_SCHEMA_VERSION

    @classmethod
    def build(cls, requirement: AnalysisRequirementSpecV1, mapping: RequirementMapping, user_goal: str, source_snapshot_id: str, data_blocks: list[PackageDataBlock] | None = None, confirmed_time_window: dict[str, str] | None = None) -> "GPTAnalysisPackage":
        if any(item.status == "requires_confirmation" for item in mapping.mapped_capabilities) and mapping.notes_scope_status != "confirmed":
            raise _error("NOTES_SCOPE_REQUIRES_CONFIRMATION", "Notes scope must be confirmed before packaging")
        if mapping.raw_permission_status != "not_granted":
            raise _error("RAW_PERMISSION_NOT_GRANTABLE", "Foundation package cannot grant Raw permission")
        if confirmed_time_window is not None:
            raw_window = _obj(confirmed_time_window, "confirmed_time_window")
            _unknown(raw_window, {"window_id", "requested_start", "requested_end", "resolved_start", "resolved_end"}, "confirmed_time_window")
            for key in ("window_id", "requested_start", "requested_end", "resolved_start", "resolved_end"):
                _text(raw_window.get(key), f"confirmed_time_window.{key}", 160, True)
        capabilities = [item.capability_id for item in mapping.mapped_capabilities]
        blocks = list(data_blocks or [])
        if any(item.capability_id not in capabilities for item in blocks):
            raise _error("PACKAGE_INVALID", "data block is not mapped to a capability")
        payload = {"user_goal": user_goal, "requirement": requirement.to_dict(), "mapping": mapping.to_dict(), "source_snapshot_id": source_snapshot_id, "confirmed_time_window": confirmed_time_window}
        return cls(_hash(payload), _text(source_snapshot_id, "source_snapshot_id", 160, True), _text(user_goal, "user_goal", 2000, True), requirement.analysis_goal, list(requirement.questions_to_answer), capabilities, requirement.preferred_time_window, confirmed_time_window, list(requirement.derived_metrics), list(requirement.missing_information), list(requirement.clarifications), list(requirement.evidence), list(requirement.gpt_prompt_outline), blocks)

    @classmethod
    def from_dict(cls, value: Any) -> "GPTAnalysisPackage":
        raw = _obj(value, "gpt_analysis_package")
        allowed = {"schema_version", "package_id", "source_snapshot_id", "user_goal", "analysis_goal", "questions_to_answer", "capability_ids", "preferred_time_window", "confirmed_time_window", "derived_metrics", "missing_information", "clarifications", "evidence", "gpt_prompt_outline", "data_blocks", "raw_included", "notes_scope"}
        _unknown(raw, allowed, "gpt_analysis_package")
        if raw.get("schema_version") != GPT_PACKAGE_SCHEMA_VERSION:
            raise _error("PACKAGE_INVALID", "unsupported GPTAnalysisPackage schema_version")
        if raw.get("raw_included") is not False:
            raise _error("RAW_PERMISSION_NOT_GRANTABLE", "Foundation package must not include Raw")
        if raw.get("notes_scope") is not None:
            raise _error("NOTES_SCOPE_REQUIRES_CONFIRMATION", "Foundation package must not choose Notes scope")
        user_goal = _text(raw.get("user_goal"), "user_goal", 2000, True)
        evidence = [EvidenceItem.from_dict(item, user_goal) for item in _items(raw.get("evidence"), "evidence", 16)]
        return cls(_text(raw.get("package_id"), "package_id", 160, True), _text(raw.get("source_snapshot_id"), "source_snapshot_id", 160, True), user_goal, _text(raw.get("analysis_goal"), "analysis_goal", 400, True), _strings(raw.get("questions_to_answer"), "questions_to_answer", 16, 300), _strings(raw.get("capability_ids"), "capability_ids", 16, 80), PreferredTimeWindow.from_dict(raw.get("preferred_time_window")), raw.get("confirmed_time_window"), [DerivedMetric.from_dict(item) for item in _items(raw.get("derived_metrics"), "derived_metrics", 16)], _strings(raw.get("missing_information"), "missing_information", 16, 240), _strings(raw.get("clarifications"), "clarifications", 16, 240), evidence, _strings(raw.get("gpt_prompt_outline"), "gpt_prompt_outline", 16, 300), [PackageDataBlock.from_dict(item) for item in _items(raw.get("data_blocks"), "data_blocks", 16)])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "source_snapshot_id": self.source_snapshot_id,
            "user_goal": self.user_goal,
            "analysis_goal": self.analysis_goal,
            "questions_to_answer": list(self.questions_to_answer),
            "capability_ids": list(self.capability_ids),
            "preferred_time_window": self.preferred_time_window.to_dict(),
            "confirmed_time_window": self.confirmed_time_window,
            "derived_metrics": [item.to_dict() for item in self.derived_metrics],
            "missing_information": list(self.missing_information),
            "clarifications": list(self.clarifications),
            "evidence": [item.to_dict() for item in self.evidence],
            "gpt_prompt_outline": list(self.gpt_prompt_outline),
            "data_blocks": [item.to_dict() for item in self.data_blocks],
            "raw_included": self.raw_included,
            "notes_scope": self.notes_scope,
        }


TRACE_STATUSES = ("PROPOSED", "VALIDATED", "PENDING_REVIEW", "APPROVED", "EDITED", "REJECTED")
TRACE_TRANSITIONS = {
    "PROPOSED": {"VALIDATED", "PENDING_REVIEW", "REJECTED"},
    "VALIDATED": {"PENDING_REVIEW", "APPROVED", "EDITED", "REJECTED"},
    "PENDING_REVIEW": {"APPROVED", "EDITED", "REJECTED"},
    "APPROVED": {"EDITED"},
    "EDITED": {"PENDING_REVIEW", "APPROVED", "REJECTED"},
    "REJECTED": set(),
}


@dataclass(frozen=True)
class TraceEvent:
    event_id: str
    status: str
    candidate_id: str
    validator_result: dict[str, Any]
    human_decision: dict[str, Any] | None = None
    schema_version: str = TRACE_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Any) -> "TraceEvent":
        raw = _obj(value, "events[]")
        _unknown(raw, {"schema_version", "event_id", "status", "candidate_id", "validator_result", "human_decision"}, "events[]")
        if raw.get("schema_version") != TRACE_SCHEMA_VERSION:
            raise _error("SCHEMA_INVALID", "unsupported trace event schema_version")
        status = _text(raw.get("status"), "events[].status", 24, True)
        if status not in TRACE_STATUSES:
            raise _error("SCHEMA_INVALID", "trace event status is invalid")
        validator_result = _obj(raw.get("validator_result", {}), "events[].validator_result")
        decision = raw.get("human_decision")
        if decision is not None:
            decision = _obj(decision, "events[].human_decision")
        return cls(_text(raw.get("event_id"), "events[].event_id", 160, True), status, _text(raw.get("candidate_id"), "events[].candidate_id", 160, True), validator_result, decision)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HumanCorrection:
    correction_id: str
    candidate_id: str
    decision: str
    reason: str
    edited_fields: dict[str, Any] = field(default_factory=dict)
    schema_version: str = CORRECTION_SCHEMA_VERSION

    ALLOWED_EDIT_FIELDS = {"analysis_goal", "questions_to_answer", "required_capabilities", "optional_capabilities", "preferred_time_window", "derived_metrics", "missing_information", "clarifications", "evidence", "gpt_prompt_outline"}

    @classmethod
    def from_dict(cls, value: Any) -> "HumanCorrection":
        raw = _obj(value, "human_correction")
        _unknown(raw, {"schema_version", "correction_id", "candidate_id", "decision", "reason", "edited_fields"}, "human_correction")
        if raw.get("schema_version") != CORRECTION_SCHEMA_VERSION:
            raise _error("HUMAN_DECISION_INVALID", "unsupported human correction schema_version")
        decision = _text(raw.get("decision"), "human_correction.decision", 16, True)
        if decision not in {"APPROVED", "EDITED", "REJECTED"}:
            raise _error("HUMAN_DECISION_INVALID", "human decision must be APPROVED, EDITED, or REJECTED")
        edited = _obj(raw.get("edited_fields", {}), "human_correction.edited_fields")
        forbidden = set(edited) - cls.ALLOWED_EDIT_FIELDS
        if forbidden:
            raise _error("FORMAL_ID_FORBIDDEN", f"human correction contains forbidden fields: {', '.join(sorted(forbidden))}")
        if decision == "EDITED" and not edited:
            raise _error("HUMAN_DECISION_INVALID", "EDITED requires edited_fields")
        if decision != "EDITED" and edited:
            raise _error("HUMAN_DECISION_INVALID", "only EDITED may contain edited_fields")
        return cls(_text(raw.get("correction_id"), "correction_id", 160, True), _text(raw.get("candidate_id"), "candidate_id", 160, True), decision, _text(raw.get("reason"), "human_correction.reason", 400, True), edited)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "correction_id": self.correction_id, "candidate_id": self.candidate_id, "decision": self.decision, "reason": self.reason, "edited_fields": self.edited_fields}

    def apply_to(self, requirement: AnalysisRequirementSpecV1, user_goal: str) -> AnalysisRequirementSpecV1 | None:
        if self.decision == "REJECTED":
            return None
        if self.decision == "APPROVED":
            return requirement
        payload = requirement.to_dict()
        payload.update(self.edited_fields)
        return AnalysisRequirementSpecV1.from_dict(payload, user_goal=user_goal)


@dataclass(frozen=True)
class AnalysisTrace:
    trace_id: str
    candidate_id: str
    status: str
    events: list[TraceEvent]
    schema_version: str = TRACE_SCHEMA_VERSION

    @classmethod
    def proposed(cls, candidate_id: str, trace_id: str | None = None) -> "AnalysisTrace":
        candidate = _text(candidate_id, "candidate_id", 160, True)
        trace = trace_id or f"trace:{_hash(candidate)[:20]}"
        event = TraceEvent(f"event:{_hash((trace, 'PROPOSED'))[:20]}", "PROPOSED", candidate, {})
        return cls(trace, candidate, "PROPOSED", [event])

    @classmethod
    def from_dict(cls, value: Any) -> "AnalysisTrace":
        raw = _obj(value, "analysis_trace")
        _unknown(raw, {"schema_version", "trace_id", "candidate_id", "status", "events"}, "analysis_trace")
        if raw.get("schema_version") != TRACE_SCHEMA_VERSION:
            raise _error("SCHEMA_INVALID", "unsupported analysis trace schema_version")
        events = [TraceEvent.from_dict(item) for item in _items(raw.get("events"), "events", 64)]
        if not events or events[0].status != "PROPOSED":
            raise _error("TRACE_INVALID_TRANSITION", "trace must start at PROPOSED")
        candidate_id = _text(raw.get("candidate_id"), "candidate_id", 160, True)
        if any(item.candidate_id != candidate_id for item in events):
            raise _error("TRACE_INVALID_TRANSITION", "trace events have inconsistent candidate_id")
        current = "PROPOSED"
        for item in events[1:]:
            if item.status not in TRACE_TRANSITIONS.get(current, set()):
                raise _error("TRACE_INVALID_TRANSITION", f"invalid trace history: {current} -> {item.status}")
            if item.status in {"VALIDATED", "APPROVED", "EDITED", "REJECTED"} and not item.validator_result:
                raise _error("TRACE_INVALID_TRANSITION", f"{item.status} requires validator_result")
            if item.status in {"APPROVED", "EDITED", "REJECTED"} and item.human_decision is None:
                raise _error("TRACE_INVALID_TRANSITION", f"{item.status} requires human_decision")
            current = item.status
        status = _text(raw.get("status"), "status", 24, True)
        if status != current:
            raise _error("TRACE_INVALID_TRANSITION", "trace status does not match its final event")
        return cls(_text(raw.get("trace_id"), "trace_id", 160, True), candidate_id, status, events)

    def transition(self, status: str, validator_result: dict[str, Any] | None = None, human_decision: dict[str, Any] | None = None) -> "AnalysisTrace":
        if status not in TRACE_STATUSES or status not in TRACE_TRANSITIONS.get(self.status, set()):
            raise _error("TRACE_INVALID_TRANSITION", f"cannot transition {self.status} -> {status}")
        validator = dict(validator_result or {})
        if status in {"VALIDATED", "APPROVED", "EDITED", "REJECTED"} and not validator:
            raise _error("TRACE_INVALID_TRANSITION", f"{status} requires validator_result")
        if status in {"APPROVED", "EDITED", "REJECTED"} and human_decision is None:
            raise _error("TRACE_INVALID_TRANSITION", f"{status} requires human_decision")
        event = TraceEvent(f"event:{_hash((self.trace_id, len(self.events), status, validator, human_decision))[:20]}", status, self.candidate_id, validator, human_decision)
        return replace(self, status=status, events=[*self.events, event])

    def apply_human_correction(self, correction: HumanCorrection, validator_result: dict[str, Any]) -> "AnalysisTrace":
        if correction.candidate_id != self.candidate_id:
            raise _error("HUMAN_DECISION_INVALID", "correction candidate_id does not match trace")
        return self.transition(correction.decision, validator_result, correction.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "trace_id": self.trace_id, "candidate_id": self.candidate_id, "status": self.status, "events": [item.to_dict() for item in self.events]}


def foundation_contract_schema() -> dict[str, Any]:
    return {
        "schema_version": FOUNDATION_SCHEMA_VERSION,
        "registry": CapabilityRegistryV1().to_dict(),
        "analysis_requirement": AnalysisRequirementSpecV1.json_schema(),
        "trace_statuses": list(TRACE_STATUSES),
        "human_decisions": ["APPROVED", "EDITED", "REJECTED"],
        "model_forbidden": ["formal_field_id", "formal_record_id", "raw_permission", "notes_scope", "export_plan", "output_format", "write", "delete", "sync"],
    }
