"""Anonymous Data & Evaluation Pipeline for Intelligent Export Milestone 2.

The pipeline evaluates Foundation Contract candidates without invoking a
model.  Its input is a small, hand-reviewed dataset of user-goal strings and
candidate AnalysisRequirementSpec payloads.  It validates split isolation,
privacy boundaries, deterministic capability mapping, evidence grounding,
time-window boundaries, and Raw/Notes permissions.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .analysis_foundation import (
    AnalysisRequirementSpecV1,
    CapabilityRegistryV1,
    FoundationError,
    GPTAnalysisPackage,
    PackageDataBlock,
    RequirementMapping,
    RequirementMapper,
)


EVALUATION_DATASET_SCHEMA_VERSION = "fitness-ledger-intelligent-export-evaluation-dataset-v1"
EVALUATION_REPORT_SCHEMA_VERSION = "fitness-ledger-intelligent-export-evaluation-report-v1"
EVALUATION_POLICY_VERSION = "foundation-mapping-policy-v1"
SPLITS = ("golden", "holdout")
OUTCOMES = ("mapped", "needs_confirmation", "rejected")

_FORBIDDEN_KEYS = {
    "raw",
    "raw_text",
    "raw_entries",
    "tracker",
    "dictionary",
    "source_snapshot_id",
    "record_id",
    "movement_id",
    "field_id",
    "history_id",
    "export_plan",
}
_FORBIDDEN_TEXT = (
    re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/|tracker\.json|movement_dictionary\.json)", re.I),
    re.compile(r"\b(?:record|movement|field|history)[_-]\d+\b", re.I),
    re.compile(r"\b(?:record|movement|field|history):[A-Za-z0-9_-]+\b", re.I),
    re.compile(r"(?:raw_entries|source_snapshot_id)", re.I),
)


def _error(code: str, message: str) -> FoundationError:
    return FoundationError(message, code)


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _text(value: Any, name: str, limit: int, required: bool = False) -> str:
    if not isinstance(value, str):
        raise _error("EVALUATION_CASE_INVALID", f"{name} must be a string")
    result = value.strip()
    if required and not result:
        raise _error("EVALUATION_CASE_INVALID", f"{name} must not be empty")
    if len(result) > limit:
        raise _error("EVALUATION_CASE_INVALID", f"{name} exceeds {limit} characters")
    return result


def _obj(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error("EVALUATION_DATASET_INVALID", f"{name} must be an object")
    return value


def _items(value: Any, name: str, limit: int) -> list[Any]:
    if not isinstance(value, list):
        raise _error("EVALUATION_DATASET_INVALID", f"{name} must be an array")
    if len(value) > limit:
        raise _error("EVALUATION_DATASET_INVALID", f"{name} exceeds {limit} items")
    return value


def _strings(value: Any, name: str, limit: int, text_limit: int = 120) -> list[str]:
    values = _items(value, name, limit)
    return [_text(item, f"{name}[]", text_limit, True) for item in values]


def _unknown(value: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _error("EVALUATION_CASE_INVALID", f"{name} contains unknown fields: {', '.join(unknown)}")


def _walk_privacy(value: Any, path: str = "root") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text.casefold() in _FORBIDDEN_KEYS:
                violations.append(f"{path}.{key_text}")
            violations.extend(_walk_privacy(item, f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_walk_privacy(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in _FORBIDDEN_TEXT):
            violations.append(path)
    return violations


def privacy_audit(value: Any) -> dict[str, Any]:
    violations = _walk_privacy(value)
    return {"passed": not violations, "violations": violations}


@dataclass(frozen=True)
class EvaluationExpectation:
    outcome: str
    mapped_capabilities: list[str]
    required_capabilities: list[str]
    optional_capabilities: list[str]
    preferred_time_window_kind: str
    require_clarification: bool
    error_code: str = ""
    notes_scope_status: str = "not_selected"

    @classmethod
    def from_dict(cls, value: Any) -> "EvaluationExpectation":
        raw = _obj(value, "expected")
        _unknown(raw, {"outcome", "mapped_capabilities", "required_capabilities", "optional_capabilities", "preferred_time_window_kind", "require_clarification", "error_code", "notes_scope_status"}, "expected")
        outcome = _text(raw.get("outcome"), "expected.outcome", 32, True)
        if outcome not in OUTCOMES:
            raise _error("EVALUATION_CASE_INVALID", "expected.outcome is invalid")
        require_clarification = raw.get("require_clarification")
        if not isinstance(require_clarification, bool):
            raise _error("EVALUATION_CASE_INVALID", "expected.require_clarification must be boolean")
        mapped = _strings(raw.get("mapped_capabilities"), "expected.mapped_capabilities", 16, 80)
        required = _strings(raw.get("required_capabilities"), "expected.required_capabilities", 16, 80)
        optional = _strings(raw.get("optional_capabilities"), "expected.optional_capabilities", 16, 80)
        if len(set(mapped)) != len(mapped) or len(set(required)) != len(required) or len(set(optional)) != len(optional):
            raise _error("EVALUATION_CASE_INVALID", "expected capability lists must not contain duplicates")
        if set(required) & set(optional):
            raise _error("EVALUATION_CASE_INVALID", "expected required and optional capabilities overlap")
        time_kind = _text(raw.get("preferred_time_window_kind"), "expected.preferred_time_window_kind", 32, True)
        error_code = _text(raw.get("error_code", ""), "expected.error_code", 80)
        notes_scope = _text(raw.get("notes_scope_status", "not_selected"), "expected.notes_scope_status", 64, True)
        if outcome == "rejected" and not error_code:
            raise _error("EVALUATION_CASE_INVALID", "rejected cases require expected.error_code")
        if outcome != "rejected" and error_code:
            raise _error("EVALUATION_CASE_INVALID", "non-rejected cases cannot have expected.error_code")
        return cls(outcome, mapped, required, optional, time_kind, require_clarification, error_code, notes_scope)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationCaseV1:
    case_id: str
    split: str
    user_goal: str
    candidate_requirement: dict[str, Any]
    expected: EvaluationExpectation
    labels: list[str]

    @classmethod
    def from_dict(cls, value: Any) -> "EvaluationCaseV1":
        raw = _obj(value, "cases[]")
        _unknown(raw, {"case_id", "split", "user_goal", "candidate_requirement", "expected", "labels"}, "cases[]")
        case_id = _text(raw.get("case_id"), "cases[].case_id", 120, True)
        split = _text(raw.get("split"), "cases[].split", 16, True)
        if split not in SPLITS:
            raise _error("EVALUATION_CASE_INVALID", "cases[].split is invalid")
        candidate = _obj(raw.get("candidate_requirement"), "cases[].candidate_requirement")
        labels = _strings(raw.get("labels", []), "cases[].labels", 16, 64)
        return cls(case_id, split, _text(raw.get("user_goal"), "cases[].user_goal", 2000, True), candidate, EvaluationExpectation.from_dict(raw.get("expected")), labels)

    def to_dict(self) -> dict[str, Any]:
        return {"case_id": self.case_id, "split": self.split, "user_goal": self.user_goal, "candidate_requirement": self.candidate_requirement, "expected": self.expected.to_dict(), "labels": list(self.labels)}


@dataclass(frozen=True)
class EvaluationDatasetV1:
    dataset_id: str
    version: str
    cases: list[EvaluationCaseV1]
    schema_version: str = EVALUATION_DATASET_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Any) -> "EvaluationDatasetV1":
        raw = _obj(value, "evaluation_dataset")
        _unknown(raw, {"schema_version", "dataset_id", "version", "cases"}, "evaluation_dataset")
        if raw.get("schema_version") != EVALUATION_DATASET_SCHEMA_VERSION:
            raise _error("EVALUATION_DATASET_INVALID", "unsupported evaluation dataset schema_version")
        audit = privacy_audit(raw)
        if not audit["passed"]:
            raise _error("EVALUATION_PRIVACY_VIOLATION", "; ".join(audit["violations"][:8]))
        cases = [EvaluationCaseV1.from_dict(item) for item in _items(raw.get("cases"), "cases", 256)]
        if not cases:
            raise _error("EVALUATION_DATASET_INVALID", "evaluation dataset must contain cases")
        case_ids = [item.case_id for item in cases]
        if len(case_ids) != len(set(case_ids)):
            raise _error("EVALUATION_DATASET_INVALID", "case_id values must be unique")
        goals = [_normalize_goal(item.user_goal) for item in cases]
        if len(goals) != len(set(goals)):
            raise _error("EVALUATION_DATA_LEAKAGE", "duplicate user goals are not allowed across evaluation cases")
        if not all(split in {item.split for item in cases} for split in SPLITS):
            raise _error("EVALUATION_DATASET_INVALID", "dataset must contain both golden and holdout cases")
        return cls(_text(raw.get("dataset_id"), "dataset_id", 120, True), _text(raw.get("version"), "version", 40, True), cases)

    @classmethod
    def load(cls, path: str | Path) -> "EvaluationDatasetV1":
        file_path = Path(path)
        try:
            value = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise _error("EVALUATION_DATASET_INVALID", f"cannot load evaluation dataset: {exc}") from exc
        return cls.from_dict(value)

    @property
    def dataset_hash(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "dataset_id": self.dataset_id, "version": self.version, "cases": [item.to_dict() for item in self.cases]}

    def split(self, split: str) -> list[EvaluationCaseV1]:
        if split not in SPLITS:
            raise _error("EVALUATION_DATASET_INVALID", f"unknown evaluation split: {split}")
        return [item for item in self.cases if item.split == split]


class AnonymizedDataProjector:
    """Project a deterministic DataCatalog into capability-level facts.

    The projector intentionally drops candidate, movement, note, and raw IDs.
    It is suitable for building a future GPTAnalysisPackage, but it never
    reads a formal file by itself and never creates an ExportPlan.
    """

    _MODULES = {
        "body_history": "body",
        "diet_macros": "diet",
        "training_context": "training",
        "movement_progress": "movement_history",
    }

    def __init__(self, registry: CapabilityRegistryV1 | None = None) -> None:
        self.registry = registry or CapabilityRegistryV1()

    def build(self, catalog: Any, mapping: RequirementMapping) -> list[PackageDataBlock]:
        modules = {str(item.module_id): item for item in getattr(catalog, "modules", [])}
        movements = list(getattr(catalog, "movements", []) or [])
        notes = list(getattr(catalog, "notes", []) or [])
        blocks: list[PackageDataBlock] = []
        for mapped in mapping.mapped_capabilities:
            definition = self.registry.require(mapped.capability_id)
            if definition.grants_raw:
                raise _error("EVALUATION_PRIVACY_VIOLATION", "Raw capability cannot enter an anonymized data block")
            facts: list[str]
            module_id = self._MODULES.get(mapped.capability_id)
            if module_id:
                module = modules.get(module_id)
                if module is None or not module.available:
                    facts = ["当前没有可用的结构化记录。"]
                else:
                    facts = [
                        f"可用记录数量：{int(module.record_count)}。",
                        f"有效日期数量：{int(module.active_date_count)}。",
                        f"字段覆盖：{', '.join(sorted(module.field_coverage))}。",
                    ]
            elif mapped.capability_id == "notes_context":
                facts = [f"可用 Notes 候选数量：{len(notes)}。", "Notes 作用域尚未由此数据投影选择。"]
            else:
                facts = ["该能力没有可公开的匿名结构化摘要。"]
            blocks.append(PackageDataBlock(mapped.capability_id, definition.source_contracts[0], facts))
        audit = privacy_audit([item.to_dict() for item in blocks])
        if not audit["passed"]:
            raise _error("EVALUATION_PRIVACY_VIOLATION", "; ".join(audit["violations"][:8]))
        return blocks

    def build_package(self, requirement: AnalysisRequirementSpecV1, mapping: RequirementMapping, catalog: Any, user_goal: str, source_snapshot_id: str, confirmed_time_window: dict[str, str] | None = None) -> GPTAnalysisPackage:
        blocks = self.build(catalog, mapping)
        return GPTAnalysisPackage.build(requirement, mapping, user_goal, source_snapshot_id, blocks, confirmed_time_window)


def _normalize_goal(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.casefold())


@dataclass(frozen=True)
class EvaluationCaseResult:
    case_id: str
    split: str
    passed: bool
    observed_outcome: str
    error_code: str
    checks: dict[str, bool]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationReportV1:
    report_id: str
    dataset_id: str
    dataset_hash: str
    policy_version: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    metrics: dict[str, Any]
    by_split: dict[str, dict[str, Any]]
    case_results: list[EvaluationCaseResult]
    schema_version: str = EVALUATION_REPORT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "dataset_id": self.dataset_id,
            "dataset_hash": self.dataset_hash,
            "policy_version": self.policy_version,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "pass_rate": self.pass_rate,
            "metrics": self.metrics,
            "by_split": self.by_split,
            "case_results": [item.to_dict() for item in self.case_results],
        }


class FoundationEvaluationRunner:
    """Run deterministic Foundation checks against anonymous candidates."""

    def __init__(self, mapper: RequirementMapper | None = None) -> None:
        self.mapper = mapper or RequirementMapper()

    def evaluate_case(self, case: EvaluationCaseV1, candidate_requirement: dict[str, Any] | None = None) -> EvaluationCaseResult:
        candidate = case.candidate_requirement if candidate_requirement is None else candidate_requirement
        if candidate is None:
            return self._result(case, False, "rejected", "EVALUATION_CANDIDATE_MISSING", {"error_code_match": case.expected.error_code == "EVALUATION_CANDIDATE_MISSING"}, {"stage": "candidate"})
        try:
            requirement = AnalysisRequirementSpecV1.from_dict(candidate, user_goal=case.user_goal)
        except FoundationError as exc:
            checks = {"outcome_match": case.expected.outcome == "rejected", "error_code_match": case.expected.error_code == exc.code, "safe_rejection": case.expected.outcome == "rejected", "evidence_grounded": exc.code != "EVIDENCE_NOT_GROUNDED"}
            passed = all(checks[name] for name in ("outcome_match", "error_code_match", "safe_rejection"))
            return self._result(case, passed, "rejected", exc.code, checks, {"stage": "requirement", "message": str(exc)[:240]})
        try:
            mapping = self.mapper.map(requirement)
        except FoundationError as exc:
            checks = {"outcome_match": case.expected.outcome == "rejected", "error_code_match": case.expected.error_code == exc.code, "safe_rejection": case.expected.outcome == "rejected", "evidence_grounded": True}
            return self._result(case, all(checks.values()), "rejected", exc.code, checks, {"stage": "mapping", "message": str(exc)[:240]})

        observed = "needs_confirmation" if any(item.requires_user_confirmation for item in mapping.mapped_capabilities) else "mapped"
        required = sorted(item.capability_id for item in requirement.required_capabilities)
        optional = sorted(item.capability_id for item in requirement.optional_capabilities)
        mapped = sorted(item.capability_id for item in mapping.mapped_capabilities)
        checks = {
            "outcome_match": observed == case.expected.outcome,
            "error_code_match": not case.expected.error_code,
            "mapped_capabilities_exact": mapped == sorted(case.expected.mapped_capabilities),
            "required_capabilities_exact": required == sorted(case.expected.required_capabilities),
            "optional_capabilities_exact": optional == sorted(case.expected.optional_capabilities),
            "preferred_time_window_match": requirement.preferred_time_window.kind == case.expected.preferred_time_window_kind,
            "clarification_match": bool(requirement.clarifications) == case.expected.require_clarification,
            "evidence_grounded": True,
            "raw_permission_boundary": mapping.raw_permission_status == "not_granted" and "raw_trace" not in mapped,
            "notes_scope_boundary": mapping.notes_scope_status == case.expected.notes_scope_status,
        }
        details = {"stage": "mapping", "mapped_capabilities": mapped, "notes_scope_status": mapping.notes_scope_status, "date_resolution_status": mapping.date_resolution_status}
        return self._result(case, all(checks.values()), observed, "", checks, details)

    @staticmethod
    def _result(case: EvaluationCaseV1, passed: bool, observed: str, error_code: str, checks: dict[str, bool], details: dict[str, Any]) -> EvaluationCaseResult:
        return EvaluationCaseResult(case.case_id, case.split, passed, observed, error_code, checks, details)

    def run(self, dataset: EvaluationDatasetV1, candidates: Mapping[str, dict[str, Any]] | None = None) -> EvaluationReportV1:
        overrides = dict(candidates or {})
        unknown = sorted(set(overrides) - {item.case_id for item in dataset.cases})
        if unknown:
            raise _error("EVALUATION_CASE_INVALID", f"candidate overrides reference unknown cases: {', '.join(unknown)}")
        results = [self.evaluate_case(case, overrides.get(case.case_id)) for case in dataset.cases]
        passed = sum(item.passed for item in results)
        metrics = self._metrics(dataset.cases, results)
        by_split = {split: self._split_metrics([item for item in results if item.split == split]) for split in SPLITS}
        report_payload = {"dataset_hash": dataset.dataset_hash, "policy_version": EVALUATION_POLICY_VERSION, "results": [item.to_dict() for item in results]}
        return EvaluationReportV1(f"evaluation:{_digest(report_payload)[:20]}", dataset.dataset_id, dataset.dataset_hash, EVALUATION_POLICY_VERSION, len(results), passed, round(passed / len(results), 4), metrics, by_split, results)

    @staticmethod
    def _metrics(cases: list[EvaluationCaseV1], results: list[EvaluationCaseResult]) -> dict[str, Any]:
        check_names = sorted({name for item in results for name in item.checks})
        boundary_pairs = [(case, result) for case, result in zip(cases, results) if {"raw", "notes"} & set(case.labels)]
        boundary_passed = sum(
            result.error_code == "RAW_PERMISSION_NOT_GRANTABLE"
            if "raw" in case.labels
            else result.checks.get("raw_permission_boundary", False) and result.checks.get("notes_scope_boundary", False)
            for case, result in boundary_pairs
        )
        return {
            "outcome_accuracy": round(sum(item.checks.get("outcome_match", False) for item in results) / len(results), 4),
            "mapping_exact_rate": round(sum(item.checks.get("mapped_capabilities_exact", False) for item in results) / len(results), 4),
            "evidence_grounding_rate": round(sum(item.checks.get("evidence_grounded", False) for item in results) / len(results), 4),
            "boundary_pass_rate": round(boundary_passed / len(boundary_pairs), 4) if boundary_pairs else 1.0,
            "check_pass_counts": {name: sum(item.checks.get(name, False) for item in results) for name in check_names},
            "unsafe_acceptance_count": sum(case.expected.outcome == "rejected" and result.observed_outcome != "rejected" for case, result in zip(cases, results)),
        }

    @staticmethod
    def _split_metrics(results: list[EvaluationCaseResult]) -> dict[str, Any]:
        passed = sum(item.passed for item in results)
        return {"total_cases": len(results), "passed_cases": passed, "pass_rate": round(passed / len(results), 4) if results else 0.0}


def evaluation_dataset_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "const": EVALUATION_DATASET_SCHEMA_VERSION},
            "dataset_id": {"type": "string", "minLength": 1, "maxLength": 120},
            "version": {"type": "string", "minLength": 1, "maxLength": 40},
            "cases": {"type": "array", "minItems": 2, "maxItems": 256},
        },
        "required": ["schema_version", "dataset_id", "version", "cases"],
    }


def evaluation_report_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "const": EVALUATION_REPORT_SCHEMA_VERSION},
            "report_id": {"type": "string", "minLength": 1},
            "dataset_id": {"type": "string", "minLength": 1},
            "dataset_hash": {"type": "string", "minLength": 64, "maxLength": 64},
            "policy_version": {"type": "string", "const": EVALUATION_POLICY_VERSION},
            "total_cases": {"type": "integer", "minimum": 1},
            "passed_cases": {"type": "integer", "minimum": 0},
            "pass_rate": {"type": "number", "minimum": 0, "maximum": 1},
            "metrics": {"type": "object"},
            "by_split": {"type": "object"},
            "case_results": {"type": "array", "minItems": 1},
        },
        "required": ["schema_version", "report_id", "dataset_id", "dataset_hash", "policy_version", "total_cases", "passed_cases", "pass_rate", "metrics", "by_split", "case_results"],
    }
