"""Deterministic request classification before the local analysis planner.

The gate is intentionally small.  It classifies the request and exposes only
the safe facts already produced by ``IntentCompiler``.  It does not interpret
new entities, grant permissions, call a model, or execute a command.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .data_catalog import DataCatalogBuilder, MovementResolver
from .analysis_registry import AnalysisOperation, IntentASTParser
from .intent_compiler import DeterministicRequestFacts, IntentCompiler
from .intelligent_export_models import MovementMention


REQUEST_GATE_SCHEMA_VERSION = "fitness-ledger-request-gate-v1"

ANALYSIS_REQUEST = "ANALYSIS_REQUEST"
CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
MOVEMENT_RESOLUTION_REQUIRED = "MOVEMENT_RESOLUTION_REQUIRED"
RAW_PERMISSION_REQUIRED = "RAW_PERMISSION_REQUIRED"
UNSUPPORTED_WRITE_OPERATION = "UNSUPPORTED_WRITE_OPERATION"
UNSUPPORTED_REQUEST = "UNSUPPORTED_REQUEST"

# These are policy categories, not a second natural-language parser.  The
# existing command parser remains authoritative for read scopes and dates.
_PLAN_ACTION_TERMS = ("制定计划", "安排训练", "训练计划", "program", "workout plan")
_WRITE_ACTION_TERMS = ("删除", "删掉", "修改", "更新", "写入", "保存", "录入", "新增", "添加", "同步", "上传", "发布", "清空", "delete", "update", "save", "sync")


def safe_model_context(facts: DeterministicRequestFacts) -> dict[str, Any]:
    """Project deterministic facts without raw-text/date keys."""

    context = facts.to_model_context()
    entities = dict(context.get("recognized_entities", {}))
    entities.pop("date_expressions", None)
    command = facts.command
    context["recognized_entities"] = entities
    context["command"] = {
        "request_kind": getattr(command, "request_kind", ""),
        "domains": list(getattr(command, "domains", []) or []),
        "layers": list(getattr(command, "layers", []) or []),
        "status": getattr(command, "status", ""),
        "errors": list(getattr(command, "errors", []) or []),
        "date_kind": getattr(getattr(command, "date", None), "kind", "none"),
    }
    return context


@dataclass(frozen=True)
class RequestGateDecision:
    status: str
    request: str
    reason_codes: list[str]
    facts: DeterministicRequestFacts | None
    movement_candidates: list[dict[str, Any]]
    confirmation_requirements: list[str]
    intent_ast: dict[str, Any] | None = None
    schema_version: str = REQUEST_GATE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        facts = safe_model_context(self.facts) if self.facts else {}
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "request": self.request,
            "reason_codes": list(self.reason_codes),
            "facts": facts,
            "movement_candidates": [dict(item) for item in self.movement_candidates],
            "confirmation_requirements": list(self.confirmation_requirements),
            "intent_ast": dict(self.intent_ast or {}),
        }


class RequestGate:
    """Closed-domain read/analysis gate backed by the existing deterministic Core."""

    def __init__(self, views: Any, catalog: Any | None = None) -> None:
        self.views = views
        self.catalog = catalog or DataCatalogBuilder(views).build()
        self.compiler = IntentCompiler(views)
        self.movement_resolver = MovementResolver(views)

    @staticmethod
    def _plan_action(request: str) -> bool:
        value = str(request or "").casefold()
        return any(term.casefold() in value for term in _PLAN_ACTION_TERMS)

    @staticmethod
    def _status_for_facts(facts: DeterministicRequestFacts) -> tuple[str, list[str], list[str]]:
        command = facts.command
        errors = list(getattr(command, "errors", []) or [])
        if getattr(command, "request_kind", "") == "unsupported_operation":
            return UNSUPPORTED_WRITE_OPERATION, errors or ["UNSUPPORTED_OPERATION"], []
        if facts.raw_requested or "raw_trace" in facts.dimensions:
            return RAW_PERMISSION_REQUIRED, ["RAW_PERMISSION_REQUIRED"], ["raw_permission"]
        if "MOVEMENT_REQUIRES_CLARIFICATION" in errors or facts.movement_ambiguous:
            return MOVEMENT_RESOLUTION_REQUIRED, ["MOVEMENT_REQUIRES_CLARIFICATION"], ["movement_identity"]
        if "DATE_REQUIRES_CLARIFICATION" in errors:
            return CLARIFICATION_REQUIRED, ["DATE_REQUIRES_CLARIFICATION"], ["time_window"]
        if "EMPTY_SCOPE" in errors or "NO_READ_INTENT" in errors or not facts.dimensions:
            return CLARIFICATION_REQUIRED, errors or ["EMPTY_SCOPE"], ["analysis_target"]
        if getattr(command, "status", "") != "resolved":
            return CLARIFICATION_REQUIRED, errors or ["REQUEST_NOT_UNDERSTOOD"], ["analysis_target"]
        return ANALYSIS_REQUEST, [], []

    def _movement_candidates(self, facts: DeterministicRequestFacts) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for mention in facts.query_scope.unresolved_movement_mentions:
            for item in self.movement_resolver.resolve(MovementMention(mention, 1.0), self.catalog.movements)[:5]:
                candidates.append(
                    {
                        "mention": mention,
                        "movement_id": str(item.get("movement_id", "")),
                        "canonical_name": str(item.get("canonical_name", "")),
                        "score": item.get("score", 0),
                    }
                )
        return candidates

    def evaluate(self, request: str) -> RequestGateDecision:
        text = str(request or "").strip()[:2000]
        if not text:
            return RequestGateDecision(CLARIFICATION_REQUIRED, text, ["EMPTY_REQUEST"], None, [], ["analysis_target"])
        ast = IntentASTParser.parse(text)
        if ast.operation == AnalysisOperation.RAW_READ.value:
            return RequestGateDecision(RAW_PERMISSION_REQUIRED, text, ["RAW_PERMISSION_REQUIRED"], None, [], ["raw_permission"], ast.to_dict())
        if ast.operation in {AnalysisOperation.DELETE.value, AnalysisOperation.WRITE.value, AnalysisOperation.SYNC.value}:
            return RequestGateDecision(UNSUPPORTED_WRITE_OPERATION, text, ["UNSUPPORTED_OPERATION"], None, [], [], ast.to_dict())
        if self._plan_action(text) or any(term.casefold() in text.casefold() for term in _WRITE_ACTION_TERMS):
            reason = "UNSUPPORTED_PLANNING_OPERATION" if self._plan_action(text) else "UNSUPPORTED_OPERATION"
            return RequestGateDecision(UNSUPPORTED_WRITE_OPERATION, text, [reason], None, [], [], ast.to_dict())
        try:
            facts = self.compiler.prepare(text, self.catalog)
        except Exception:
            # The gate is fail-closed.  Keep parser failures out of the model
            # boundary and ask the user for a supported read target.
            return RequestGateDecision(UNSUPPORTED_REQUEST, text, ["REQUEST_CLASSIFICATION_FAILED"], None, [], ["analysis_target"], ast.to_dict())

        status, reasons, confirmations = self._status_for_facts(facts)
        if status == ANALYSIS_REQUEST and self._plan_action(text):
            status = UNSUPPORTED_WRITE_OPERATION
            reasons = ["UNSUPPORTED_PLANNING_OPERATION"]
        return RequestGateDecision(
            status,
            text,
            reasons,
            facts,
            self._movement_candidates(facts) if status == MOVEMENT_RESOLUTION_REQUIRED else [],
            confirmations,
            ast.to_dict(),
        )
