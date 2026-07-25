"""Isolated qwen3:4b Shadow Planner evaluation boundary.

This module is intentionally not imported by the Web service or
``IntelligentExportService``.  It sends only anonymous, aggregate context to
the one configured local Ollama endpoint and returns proposal/evaluation
records.  It never executes a command, builds an ExportPlan, or writes data.
"""

from __future__ import annotations

import json
import hashlib
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from .analysis_evaluation import privacy_audit
from .analysis_foundation import (
    AnalysisRequirementSpecV1,
    CapabilityRegistryV1,
    FoundationError,
    RequirementMapper,
)


SHADOW_ENDPOINT = "http://127.0.0.1:11434"
SHADOW_MODEL = "qwen3:4b"
SHADOW_TIMEOUT_SECONDS = 30.0
SHADOW_MAX_ATTEMPTS = 2
SHADOW_POLICY_VERSION = "qwen3-shadow-planner-v1"
SHADOW_MATRIX_SCHEMA_VERSION = "fitness-ledger-qwen-shadow-matrix-v1"
SHADOW_REPORT_SCHEMA_VERSION = "fitness-ledger-qwen-shadow-report-v1"

SHADOW_SYSTEM_PROMPT = """You are a shadow-only Fitness Ledger analysis requirement planner.
Return exactly one JSON object matching the supplied AnalysisRequirementSpec schema.
You propose analysis requirements only. Do not create an ExportPlan, select formal
field IDs, record IDs, Raw access, Notes scope, final dates, output formats, or any
write/delete/sync action. Use only capability IDs in the supplied registry. Evidence
must quote or conservatively paraphrase information that appears in user_goal. Put
inferred capability rationale in capability.reason, never in evidence. A preferred
time window may be recent, last_week, recent_months, all_available, or an explicit
user phrase without a day-level date. If the goal is unsupported, ambiguous, or
missing required information, use clarifications/missing_information and keep the
proposal conservative. This is not a command and must never be executed directly."""

CAPABILITY_TO_DIMENSION = {
    "body_history": "body_state",
    "diet_macros": "diet_macros",
    "training_context": "training_context",
    "movement_progress": "movement_progress",
    "notes_context": "notes_context",
    "raw_trace": "raw_trace",
}
DIMENSION_TO_CAPABILITY = {value: key for key, value in CAPABILITY_TO_DIMENSION.items()}
REQUIRED_CATEGORIES = {
    "body",
    "diet",
    "training",
    "time_window",
    "notes",
    "movement",
    "body_part",
    "raw",
    "ambiguous_date",
    "ambiguous_movement",
    "missing_information",
    "unsupported_operation",
    "multi_module",
}


class ShadowTransportError(RuntimeError):
    def __init__(self, message: str, code: str, attempts: int = 1) -> None:
        super().__init__(message)
        self.code = code
        self.attempts = attempts

    @property
    def retry_count(self) -> int:
        return max(0, self.attempts - 1)


@dataclass(frozen=True)
class ShadowModelManifest:
    endpoint: str
    model: str
    available: bool
    digest: str = ""
    model_names: list[str] | None = None
    error_code: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "model": self.model,
            "available": self.available,
            "digest": self.digest,
            "model_names": list(self.model_names or []),
            "error_code": self.error_code,
            "error": self.error,
        }


@dataclass(frozen=True)
class ShadowCall:
    raw_text: str
    latency_ms: int
    attempts: int
    finish_reason: str = ""
    output_chars: int = 0

    @property
    def retry_count(self) -> int:
        return max(0, self.attempts - 1)


class ShadowTransport(Protocol):
    def read_manifest(self) -> ShadowModelManifest: ...

    def generate(self, *, user_payload: dict[str, Any], response_schema: dict[str, Any], system_prompt: str | None = None) -> ShadowCall: ...


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class OllamaShadowTransport:
    """One-purpose client for the fixed local qwen3:4b shadow endpoint."""

    def __init__(self, endpoint: str = SHADOW_ENDPOINT, model: str = SHADOW_MODEL, timeout: float = SHADOW_TIMEOUT_SECONDS, system_prompt: str = SHADOW_SYSTEM_PROMPT) -> None:
        if endpoint.rstrip("/") != SHADOW_ENDPOINT:
            raise ValueError("Shadow endpoint must be the fixed local Ollama endpoint")
        if model != SHADOW_MODEL:
            raise ValueError("Shadow model must be qwen3:4b")
        if not 0 < float(timeout) <= SHADOW_TIMEOUT_SECONDS:
            raise ValueError("Shadow timeout must be between 0 and 30 seconds")
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = float(timeout)
        self.system_prompt = system_prompt
        self._slot = threading.BoundedSemaphore(1)
        self.last_payload: dict[str, Any] | None = None
        self.last_call: ShadowCall | None = None

    def read_manifest(self) -> ShadowModelManifest:
        request = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=min(5.0, self.timeout)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, socket.timeout, TimeoutError, json.JSONDecodeError) as exc:
            return ShadowModelManifest(self.endpoint, self.model, False, error_code="MODEL_UNAVAILABLE", error=str(exc)[:240])
        models = payload.get("models", []) if isinstance(payload, dict) else []
        if not isinstance(models, list):
            return ShadowModelManifest(self.endpoint, self.model, False, error_code="MODEL_INVALID_MANIFEST", error="models is not an array")
        names = []
        digest = ""
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("model") or "")
            if name:
                names.append(name)
            if name == self.model:
                digest = str(item.get("digest") or "")
        if not digest:
            return ShadowModelManifest(self.endpoint, self.model, False, model_names=sorted(names), error_code="MODEL_UNAVAILABLE", error="qwen3:4b is not present or has no digest")
        return ShadowModelManifest(self.endpoint, self.model, True, digest=digest, model_names=sorted(names))

    def generate(self, *, user_payload: dict[str, Any], response_schema: dict[str, Any], system_prompt: str | None = None) -> ShadowCall:
        if not self._slot.acquire(timeout=min(self.timeout, 5.0)):
            raise ShadowTransportError("shadow transport is busy", "MODEL_BUSY")
        started = time.monotonic()
        self.last_payload = json.loads(json.dumps(user_payload, ensure_ascii=False))
        self.last_call = None
        try:
            request_payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt or self.system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":"))},
                ],
                "stream": False,
                "think": False,
                "format": response_schema,
                "options": {"temperature": 0.0, "num_ctx": 4096, "num_predict": 1200},
                "keep_alive": 0,
            }
            request = urllib.request.Request(
                f"{self.endpoint}/api/chat",
                data=_json_bytes(request_payload),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            last_error: ShadowTransportError | None = None
            for attempt in range(1, SHADOW_MAX_ATTEMPTS + 1):
                try:
                    with urllib.request.urlopen(request, timeout=self.timeout) as response:
                        raw_response = response.read()
                    payload = json.loads(raw_response.decode("utf-8"))
                    message = payload.get("message") if isinstance(payload, dict) else None
                    content = message.get("content") if isinstance(message, dict) else None
                    if not isinstance(content, str) or not content.strip():
                        raise ShadowTransportError("shadow response has no content", "MODEL_EMPTY_RESPONSE", attempt)
                    finish_reason = str(payload.get("done_reason") or payload.get("finish_reason") or "")
                    self.last_call = ShadowCall(content, int((time.monotonic() - started) * 1000), attempt, finish_reason, len(content))
                    return self.last_call
                except ShadowTransportError as exc:
                    last_error = exc
                except urllib.error.HTTPError as exc:
                    last_error = ShadowTransportError(f"Ollama HTTP {exc.code}", "MODEL_CONNECTION_ERROR", attempt)
                except (urllib.error.URLError, OSError, socket.timeout, TimeoutError) as exc:
                    last_error = ShadowTransportError(str(exc)[:240], "MODEL_CONNECTION_ERROR", attempt)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    last_error = ShadowTransportError(str(exc)[:240], "MODEL_INVALID_JSON", attempt)
                if attempt < SHADOW_MAX_ATTEMPTS:
                    continue
            raise last_error or ShadowTransportError("shadow request failed", "MODEL_UNAVAILABLE", SHADOW_MAX_ATTEMPTS)
        finally:
            self._slot.release()


class FakeShadowTransport:
    """Adapter-shaped fake used for schema and failure-injection tests."""

    def __init__(self, responses: list[Any] | None = None, errors: list[Exception] | None = None, manifest: ShadowModelManifest | None = None) -> None:
        self.responses = list(responses or [])
        self.errors = list(errors or [])
        self.calls: list[dict[str, Any]] = []
        self.manifest = manifest or ShadowModelManifest(SHADOW_ENDPOINT, SHADOW_MODEL, True, "fake-digest")
        self.last_payload: dict[str, Any] | None = None
        self.last_call: ShadowCall | None = None

    def read_manifest(self) -> ShadowModelManifest:
        return self.manifest

    def generate(self, *, user_payload: dict[str, Any], response_schema: dict[str, Any], system_prompt: str | None = None) -> ShadowCall:
        self.last_payload = json.loads(json.dumps(user_payload, ensure_ascii=False))
        self.last_call = None
        self.calls.append({"user_payload": user_payload, "response_schema": response_schema, "system_prompt": system_prompt})
        if self.errors:
            error = self.errors.pop(0)
            if isinstance(error, ShadowTransportError):
                raise error
            raise ShadowTransportError(str(error), getattr(error, "code", "MODEL_UNAVAILABLE"), 1)
        if not self.responses:
            raise ShadowTransportError("fake shadow has no response", "MODEL_UNAVAILABLE")
        response = self.responses.pop(0)
        raw = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        self.last_call = ShadowCall(raw, 0, 1, "stop", len(raw))
        return self.last_call


@dataclass(frozen=True)
class ShadowMatrixCase:
    case_id: str
    category: str
    user_goal: str
    labels: list[str]
    expected_capabilities: list[str]
    optional_capabilities: list[str]
    forbidden_capabilities: list[str]
    expected_abstain: bool
    boundary_rules: list[str]
    explanation: str
    expected_error_category: str = ""
    split: str = "holdout"

    @classmethod
    def from_dict(cls, value: Any) -> "ShadowMatrixCase":
        if not isinstance(value, dict):
            raise FoundationError("shadow matrix case must be an object", "EVALUATION_CASE_INVALID")
        allowed = {"case_id", "category", "user_goal", "labels", "expected_capabilities", "optional_capabilities", "forbidden_capabilities", "expected_abstain", "boundary_rules", "explanation", "expected_error_category", "split"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise FoundationError(f"shadow matrix case contains unknown fields: {', '.join(unknown)}", "EVALUATION_CASE_INVALID")
        case_id = str(value.get("case_id") or "").strip()
        category = str(value.get("category") or "").strip()
        user_goal = str(value.get("user_goal") or "").strip()
        labels = [str(item).strip() for item in value.get("labels", [])]
        expected = [str(item).strip() for item in value.get("expected_capabilities", [])]
        optional = [str(item).strip() for item in value.get("optional_capabilities", [])]
        forbidden = [str(item).strip() for item in value.get("forbidden_capabilities", [])]
        boundary_rules = [str(item).strip() for item in value.get("boundary_rules", [])]
        explanation = str(value.get("explanation") or "").strip()
        expected_error_category = str(value.get("expected_error_category") or "").strip()
        split = str(value.get("split") or "holdout").strip()
        if not case_id or not category or not user_goal or category not in REQUIRED_CATEGORIES:
            raise FoundationError("shadow matrix case has invalid identity or category", "EVALUATION_CASE_INVALID")
        if not labels or any(not item for item in labels):
            raise FoundationError("shadow matrix case labels are invalid", "EVALUATION_CASE_INVALID")
        if any(not item for item in expected + optional + forbidden + boundary_rules) or not explanation or split not in {"holdout", "golden"}:
            raise FoundationError("shadow matrix gold fields are invalid", "GOLD_LABEL_ERROR")
        if set(expected) & set(forbidden) or expected and bool(value.get("expected_abstain")):
            raise FoundationError("shadow matrix gold fields conflict", "GOLD_LABEL_ERROR")
        return cls(case_id, category, user_goal, labels, expected, optional, forbidden, bool(value.get("expected_abstain", False)), boundary_rules, explanation, expected_error_category, split)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowEvaluationMatrix:
    matrix_id: str
    version: str
    cases: list[ShadowMatrixCase]
    schema_version: str = SHADOW_MATRIX_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Any) -> "ShadowEvaluationMatrix":
        if not isinstance(value, dict):
            raise FoundationError("shadow matrix must be an object", "EVALUATION_DATASET_INVALID")
        allowed = {"schema_version", "matrix_id", "version", "cases"}
        unknown = sorted(set(value) - allowed)
        if unknown or value.get("schema_version") != SHADOW_MATRIX_SCHEMA_VERSION:
            raise FoundationError("shadow matrix schema is invalid", "EVALUATION_DATASET_INVALID")
        audit = privacy_audit(value)
        if not audit["passed"]:
            raise FoundationError("; ".join(audit["violations"][:8]), "EVALUATION_PRIVACY_VIOLATION")
        matrix_id = str(value.get("matrix_id") or "").strip()
        version = str(value.get("version") or "").strip()
        if not matrix_id or not version:
            raise FoundationError("shadow matrix identity is invalid", "EVALUATION_DATASET_INVALID")
        raw_cases = value.get("cases")
        if not isinstance(raw_cases, list) or len(raw_cases) < 10:
            raise FoundationError("shadow matrix needs at least 10 cases", "EVALUATION_DATASET_INVALID")
        cases = [ShadowMatrixCase.from_dict(item) for item in raw_cases]
        if len({item.case_id for item in cases}) != len(cases):
            raise FoundationError("shadow matrix case IDs must be unique", "EVALUATION_DATA_LEAKAGE")
        normalized = {re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", item.user_goal.casefold()) for item in cases}
        if len(normalized) != len(cases):
            raise FoundationError("shadow matrix user goals must be unique", "EVALUATION_DATA_LEAKAGE")
        categories = {item.category for item in cases}
        missing = sorted(REQUIRED_CATEGORIES - categories)
        if missing:
            raise FoundationError(f"shadow matrix missing categories: {', '.join(missing)}", "EVALUATION_DATASET_INVALID")
        return cls(matrix_id, version, cases)

    @classmethod
    def load(cls, path: str | Path) -> "ShadowEvaluationMatrix":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def matrix_hash(self) -> str:
        payload = {"schema_version": self.schema_version, "matrix_id": self.matrix_id, "version": self.version, "cases": [item.to_dict() for item in self.cases]}
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "matrix_id": self.matrix_id, "version": self.version, "cases": [item.to_dict() for item in self.cases]}


class DeterministicBaseline:
    """Small read-only projection of existing IntentCompiler facts."""

    def __init__(self, views: Any, catalog: Any) -> None:
        from .intent_compiler import IntentCompiler

        self.compiler = IntentCompiler(views)
        self.catalog = catalog

    def evaluate(self, user_goal: str) -> dict[str, Any]:
        facts = self.compiler.prepare(user_goal, self.catalog)
        command = facts.command
        status = getattr(command, "status", "") if command else ""
        if status != "resolved":
            if status == "unsupported_operation":
                code = "UNSUPPORTED_OPERATION"
            elif "DATE_REQUIRES_CLARIFICATION" in (getattr(command, "errors", []) or []):
                code = "INCOMPLETE_DATE_RANGE"
            elif "MOVEMENT_REQUIRES_CLARIFICATION" in (getattr(command, "errors", []) or []):
                code = "UNRESOLVED_REQUIRED_MOVEMENT"
            else:
                code = "REQUEST_NOT_UNDERSTOOD"
            outcome = "ABSTAIN"
        else:
            code = ""
            outcome = "MAPPED" if facts.dimensions else "ABSTAIN"
        capabilities = sorted({DIMENSION_TO_CAPABILITY[item] for item in facts.dimensions if item in DIMENSION_TO_CAPABILITY})
        return {
            "outcome": outcome,
            "error_code": code,
            "capability_ids": capabilities,
            "date_kind": getattr(getattr(command, "date", None), "kind", "none") if command else "none",
            "notes_scopes": sorted(facts.notes_scopes),
            "raw_requested": bool(facts.raw_requested),
            "movement_mentions": list(facts.query_scope.explicit_movement_mentions),
            "scope_operations": [item.to_dict() for item in getattr(command, "scope_operations", [])],
        }


def build_shadow_input(user_goal: str, registry: CapabilityRegistryV1, analysis_context: dict[str, Any] | None = None) -> dict[str, Any]:
    goal = str(user_goal or "").strip()
    if not goal or len(goal) > 2000:
        raise FoundationError("shadow user_goal is invalid", "EVALUATION_CASE_INVALID")
    context = dict(analysis_context or {})
    audit = privacy_audit(context)
    if not audit["passed"]:
        raise FoundationError("; ".join(audit["violations"][:8]), "EVALUATION_PRIVACY_VIOLATION")
    if len(_json_bytes(context)) > 6000:
        raise FoundationError("shadow analysis_context exceeds 6000 bytes", "EVALUATION_DATASET_INVALID")
    payload = {
        "user_goal": goal,
        "available_capabilities": registry.to_dict()["capabilities"],
        "analysis_context": context,
    }
    return payload


def _strict_json(raw_text: str) -> dict[str, Any]:
    try:
        value = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise FoundationError("shadow model output is not strict JSON", "MODEL_SCHEMA_INVALID") from exc
    if not isinstance(value, dict):
        raise FoundationError("shadow model output must be an object", "MODEL_SCHEMA_INVALID")
    audit = privacy_audit(value)
    if not audit["passed"]:
        raise FoundationError("; ".join(audit["violations"][:8]), "FORMAL_ID_FORBIDDEN")
    text = json.dumps(value, ensure_ascii=False)
    if re.search(r"export[_ ]plan|raw[_ ]permission|notes[_ ]scope|正式字段|记录id|动作id|写入|删除|同步", text, re.I):
        raise FoundationError("shadow model output crosses a forbidden boundary", "FORMAL_ID_FORBIDDEN")
    return value


def _classify_error(code: str, stage: str, baseline: dict[str, Any] | None = None) -> str:
    if code in {"UNKNOWN_CAPABILITY", "CAPABILITY_NOT_MODEL_SELECTABLE"}:
        return "Registry"
    if code in {"RAW_PERMISSION_NOT_GRANTABLE", "NOTES_SCOPE_REQUIRES_CONFIRMATION", "MAPPING_INVALID"}:
        return "Mapping"
    if code in {"MODEL_SCHEMA_INVALID", "EVIDENCE_NOT_GROUNDED", "FORMAL_DATE_FORBIDDEN", "FORMAL_ID_FORBIDDEN", "PACKAGE_INVALID"}:
        return "Prompt / Schema"
    if code in {"INCOMPLETE_DATE_RANGE", "UNRESOLVED_REQUIRED_MOVEMENT", "REQUEST_NOT_UNDERSTOOD", "UNSUPPORTED_OPERATION", "NO_SAFE_SCOPE"}:
        return "数据不足"
    if code.startswith("MODEL_") or stage == "comparison":
        return "模型能力不足"
    return "模型能力不足" if stage == "model" else "Prompt / Schema"


@dataclass(frozen=True)
class ShadowCaseRecord:
    case_id: str
    category: str
    user_goal: str
    model_proposal: dict[str, Any] | None
    schema_result: dict[str, Any]
    registry_result: dict[str, Any]
    mapping_result: dict[str, Any]
    correct_abstain: bool | None
    baseline: dict[str, Any]
    baseline_diff: dict[str, Any]
    validator_errors: list[dict[str, str]]
    latency_ms: int
    retry: int
    final_status: str
    error_source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowEvaluationReport:
    report_id: str
    matrix_id: str
    matrix_hash: str
    model: str
    model_digest: str
    endpoint: str
    manifest: dict[str, Any]
    total_cases: int
    metrics: dict[str, Any]
    error_sources: dict[str, int]
    case_records: list[ShadowCaseRecord]
    schema_version: str = SHADOW_REPORT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "matrix_id": self.matrix_id,
            "matrix_hash": self.matrix_hash,
            "model": self.model,
            "model_digest": self.model_digest,
            "endpoint": self.endpoint,
            "manifest": self.manifest,
            "total_cases": self.total_cases,
            "metrics": self.metrics,
            "error_sources": self.error_sources,
            "case_records": [item.to_dict() for item in self.case_records],
        }


class ShadowPlannerRunner:
    """Run proposals and validation only; never invoke Core execution."""

    def __init__(self, transport: ShadowTransport, registry: CapabilityRegistryV1 | None = None, mapper: RequirementMapper | None = None) -> None:
        self.transport = transport
        self.registry = registry or CapabilityRegistryV1()
        self.mapper = mapper or RequirementMapper(self.registry)

    def run_case(self, case: ShadowMatrixCase, baseline: dict[str, Any], analysis_context: dict[str, Any] | None = None, manifest: ShadowModelManifest | None = None) -> ShadowCaseRecord:
        manifest = manifest or self.transport.read_manifest()
        if not manifest.available:
            return ShadowCaseRecord(case.case_id, case.category, case.user_goal, None, {"passed": False, "error_code": "MODEL_UNAVAILABLE"}, {"passed": False, "error_code": "MODEL_UNAVAILABLE"}, {"passed": False, "error_code": "MODEL_UNAVAILABLE"}, baseline["outcome"] == "ABSTAIN", baseline, {"status": "MODEL_UNAVAILABLE"}, [{"source": "模型能力不足", "code": "MODEL_UNAVAILABLE"}], 0, 0, "MODEL_UNAVAILABLE", "模型能力不足")
        try:
            payload = build_shadow_input(case.user_goal, self.registry, analysis_context)
        except FoundationError as exc:
            source = _classify_error(exc.code, "input")
            return ShadowCaseRecord(case.case_id, case.category, case.user_goal, None, {"passed": False, "error_code": exc.code}, {"passed": False, "error_code": "NOT_RUN"}, {"passed": False, "error_code": "NOT_RUN"}, baseline["outcome"] == "ABSTAIN", baseline, {"status": "SAFE_FALLBACK"}, [{"source": source, "code": exc.code}], 0, 0, "SAFE_FALLBACK", source)
        try:
            call = self.transport.generate(user_payload=payload, response_schema=AnalysisRequirementSpecV1.json_schema())
        except ShadowTransportError as exc:
            final_status = "INVALID" if exc.code == "MODEL_INVALID_JSON" else ("SAFE_FALLBACK" if exc.code == "MODEL_BUSY" else "MODEL_UNAVAILABLE")
            source = _classify_error(exc.code, "model")
            return ShadowCaseRecord(case.case_id, case.category, case.user_goal, None, {"passed": False, "error_code": exc.code}, {"passed": False, "error_code": exc.code}, {"passed": False, "error_code": exc.code}, baseline["outcome"] == "ABSTAIN", baseline, {"status": final_status}, [{"source": source, "code": exc.code}], 0, exc.retry_count, final_status, source)
        try:
            raw = _strict_json(call.raw_text)
        except FoundationError as exc:
            return ShadowCaseRecord(case.case_id, case.category, case.user_goal, None, {"passed": False, "error_code": exc.code}, {"passed": False, "error_code": "NOT_RUN"}, {"passed": False, "error_code": "NOT_RUN"}, baseline["outcome"] == "ABSTAIN", baseline, {"status": "INVALID"}, [{"source": _classify_error(exc.code, "schema"), "code": exc.code}], call.latency_ms, call.retry_count, "INVALID", _classify_error(exc.code, "schema"))
        try:
            requirement = AnalysisRequirementSpecV1.from_dict(raw, user_goal=case.user_goal)
        except FoundationError as exc:
            return ShadowCaseRecord(case.case_id, case.category, case.user_goal, None, {"passed": False, "error_code": exc.code}, {"passed": False, "error_code": "NOT_RUN"}, {"passed": False, "error_code": "NOT_RUN"}, baseline["outcome"] == "ABSTAIN", baseline, {"status": "INVALID"}, [{"source": _classify_error(exc.code, "schema"), "code": exc.code}], call.latency_ms, call.retry_count, "INVALID", _classify_error(exc.code, "schema"))
        try:
            mapping = self.mapper.map(requirement)
        except FoundationError as exc:
            correct_abstain = baseline["outcome"] == "ABSTAIN"
            return ShadowCaseRecord(case.case_id, case.category, case.user_goal, requirement.to_dict(), {"passed": True, "error_code": ""}, {"passed": False, "error_code": exc.code}, {"passed": False, "error_code": exc.code}, correct_abstain, baseline, {"status": "ABSTAIN", "mapped_capabilities": []}, [{"source": _classify_error(exc.code, "mapping"), "code": exc.code}], call.latency_ms, call.retry_count, "ABSTAIN", _classify_error(exc.code, "mapping"))
        mapped_ids = sorted(item.capability_id for item in mapping.mapped_capabilities)
        baseline_ids = sorted(baseline.get("capability_ids", []))
        diff = {
            "added_capabilities": sorted(set(mapped_ids) - set(baseline_ids)),
            "removed_capabilities": sorted(set(baseline_ids) - set(mapped_ids)),
            "baseline_outcome": baseline["outcome"],
            "model_outcome": "MAPPED",
            "raw_requested_mismatch": bool(baseline.get("raw_requested")) and "raw_trace" not in mapped_ids,
            "notes_scope_status": mapping.notes_scope_status,
        }
        mismatch = bool(diff["added_capabilities"] or diff["removed_capabilities"])
        validator_errors = [{"source": "模型能力不足", "code": "MODEL_CAPABILITY_MISMATCH"}] if mismatch else []
        correct_abstain = False if baseline["outcome"] == "ABSTAIN" else None
        return ShadowCaseRecord(case.case_id, case.category, case.user_goal, requirement.to_dict(), {"passed": True, "error_code": "", "output_keys": sorted(raw)}, {"passed": True, "error_code": "", "capabilities": mapped_ids}, {"passed": True, "error_code": "", "capabilities": mapped_ids, "notes_scope_status": mapping.notes_scope_status, "raw_permission_status": mapping.raw_permission_status}, correct_abstain, baseline, diff, validator_errors, call.latency_ms, call.retry_count, "VALIDATED", "模型能力不足" if mismatch else "")

    def run_matrix(self, matrix: ShadowEvaluationMatrix, baseline: DeterministicBaseline, analysis_context: dict[str, Any] | None = None) -> ShadowEvaluationReport:
        manifest = self.transport.read_manifest()
        records = [self.run_case(case, baseline.evaluate(case.user_goal), analysis_context, manifest) for case in matrix.cases]
        statuses = {status: sum(item.final_status == status for item in records) for status in ("VALIDATED", "ABSTAIN", "INVALID", "MODEL_UNAVAILABLE", "SAFE_FALLBACK")}
        valid = [item for item in records if item.schema_result.get("passed")]
        mapped = [item for item in records if item.mapping_result.get("passed")]
        baseline_abstain = [item for item in records if item.baseline.get("outcome") == "ABSTAIN"]
        baseline_mapped = [item for item in records if item.baseline.get("outcome") == "MAPPED"]
        correct_abstain = sum(item.final_status in {"ABSTAIN", "INVALID", "MODEL_UNAVAILABLE", "SAFE_FALLBACK"} for item in baseline_abstain)
        capability_match = sum(not item.baseline_diff.get("added_capabilities") and not item.baseline_diff.get("removed_capabilities") for item in baseline_mapped if item.mapping_result.get("passed"))
        latencies = sorted(item.latency_ms for item in records if item.latency_ms >= 0)
        errors: dict[str, int] = {source: 0 for source in ("Registry", "Mapping", "Prompt / Schema", "数据不足", "模型能力不足")}
        for item in records:
            if item.error_source:
                errors[item.error_source] = errors.get(item.error_source, 0) + 1
            for error in item.validator_errors:
                source = error.get("source", "模型能力不足")
                errors[source] = errors.get(source, 0) + 1
        metrics = {
            "schema_valid_count": len(valid),
            "schema_valid_rate": round(len(valid) / len(records), 4) if records else 0.0,
            "mapping_valid_count": len(mapped),
            "mapping_valid_rate": round(len(mapped) / len(records), 4) if records else 0.0,
            "correct_abstain_count": correct_abstain,
            "correct_abstain_denominator": len(baseline_abstain),
            "correct_abstain_rate": round(correct_abstain / len(baseline_abstain), 4) if baseline_abstain else 1.0,
            "capability_match_count": capability_match,
            "capability_match_denominator": len(baseline_mapped),
            "capability_match_rate": round(capability_match / len(baseline_mapped), 4) if baseline_mapped else 1.0,
            "boundary_violation_count": sum(1 for item in records for error in item.validator_errors if error.get("code") in {"FORMAL_ID_FORBIDDEN", "RAW_PERMISSION_NOT_GRANTABLE", "NOTES_SCOPE_REQUIRES_CONFIRMATION"}),
            "retry_total": sum(item.retry for item in records),
            "latency_average_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
            "latency_p50_ms": latencies[(len(latencies) - 1) // 2] if latencies else 0,
            "latency_p95_ms": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95) - 1)] if latencies else 0,
            "status_counts": statuses,
        }
        payload = {"matrix_hash": matrix.matrix_hash, "model": manifest.model, "digest": manifest.digest, "records": [item.to_dict() for item in records], "metrics": metrics}
        report_id = f"shadow:{hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()[:20]}"
        return ShadowEvaluationReport(report_id, matrix.matrix_id, matrix.matrix_hash, manifest.model, manifest.digest, manifest.endpoint, manifest.to_dict(), len(records), metrics, errors, records)


def shadow_matrix_json_schema() -> dict[str, Any]:
    """Schema for the anonymous, hand-authored shadow evaluation matrix."""

    case = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "case_id": {"type": "string", "minLength": 1, "maxLength": 80},
            "category": {"type": "string", "enum": sorted(REQUIRED_CATEGORIES)},
            "user_goal": {"type": "string", "minLength": 1, "maxLength": 2000},
            "labels": {"type": "array", "minItems": 1, "maxItems": 16, "items": {"type": "string", "minLength": 1, "maxLength": 80}},
            "expected_capabilities": {"type": "array", "items": {"type": "string", "minLength": 1}},
            "optional_capabilities": {"type": "array", "items": {"type": "string", "minLength": 1}},
            "forbidden_capabilities": {"type": "array", "items": {"type": "string", "minLength": 1}},
            "expected_abstain": {"type": "boolean"},
            "boundary_rules": {"type": "array", "items": {"type": "string", "minLength": 1}},
            "explanation": {"type": "string", "minLength": 1},
            "expected_error_category": {"type": "string"},
            "split": {"type": "string", "enum": ["golden", "holdout"]},
        },
        "required": ["case_id", "category", "user_goal", "labels", "expected_capabilities", "optional_capabilities", "forbidden_capabilities", "expected_abstain", "boundary_rules", "explanation"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "const": SHADOW_MATRIX_SCHEMA_VERSION},
            "matrix_id": {"type": "string", "minLength": 1, "maxLength": 120},
            "version": {"type": "string", "minLength": 1, "maxLength": 40},
            "cases": {"type": "array", "minItems": 10, "maxItems": 256, "items": case},
        },
        "required": ["schema_version", "matrix_id", "version", "cases"],
    }


def shadow_report_json_schema() -> dict[str, Any]:
    """Top-level report schema; case contents remain structured and raw-free."""

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "const": SHADOW_REPORT_SCHEMA_VERSION},
            "report_id": {"type": "string", "minLength": 1},
            "matrix_id": {"type": "string", "minLength": 1},
            "matrix_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "model": {"type": "string", "const": SHADOW_MODEL},
            "model_digest": {"type": "string"},
            "endpoint": {"type": "string", "const": SHADOW_ENDPOINT},
            "manifest": {"type": "object"},
            "total_cases": {"type": "integer", "minimum": 10},
            "metrics": {"type": "object"},
            "error_sources": {"type": "object"},
            "case_records": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["schema_version", "report_id", "matrix_id", "matrix_hash", "model", "model_digest", "endpoint", "manifest", "total_cases", "metrics", "error_sources", "case_records"],
    }
