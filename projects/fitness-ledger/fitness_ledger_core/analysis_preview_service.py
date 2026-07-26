"""Web-ready, read-only orchestration for local analysis previews.

This module is deliberately a thin state machine, not an agent framework.  It
reuses the existing Shadow Planner contract for the only model step and then
hands all scope, dates, IDs, validation, and data preparation back to the
deterministic Core.  The executor is never called here.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .analysis_foundation import (
    AnalysisRequirementSpecV1,
    CapabilityRegistryV1,
    FoundationError,
    GPTAnalysisPackage,
    PackageDataBlock,
    RequirementMapper,
)
from .candidate_cards import CandidatePackage
from .data_catalog import DataCatalogBuilder
from .export_plan_validator import ExportPlanValidator, PlanValidationError
from .intent_compiler import IntentCompileError, IntentCompiler
from .intelligent_export_models import stable_hash
from .request_gate import (
    ANALYSIS_REQUEST,
    CLARIFICATION_REQUIRED,
    MOVEMENT_RESOLUTION_REQUIRED,
    RAW_PERMISSION_REQUIRED,
    RequestGate,
    RequestGateDecision,
    safe_model_context,
    UNSUPPORTED_REQUEST,
    UNSUPPORTED_WRITE_OPERATION,
)
from .shadow_planner import DIMENSION_TO_CAPABILITY, ShadowMatrixCase, ShadowTransport
from .shadow_planner_evaluation import (
    REQUEST_SCHEMA_VERSION,
    TWO_STAGE_PROMPT_VERSION,
    CapabilityRegistryV2,
    run_two_stage_case,
)


PREVIEW_SERVICE_SCHEMA_VERSION = "fitness-ledger-analysis-preview-service-v1"
PREVIEW_TRACE_SCHEMA_VERSION = "fitness-ledger-analysis-preview-trace-v1"


class PreviewServiceError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def _service_status(gate_status: str) -> str:
    return {
        RAW_PERMISSION_REQUIRED: "raw_permission_required",
        MOVEMENT_RESOLUTION_REQUIRED: "movement_resolution_required",
        UNSUPPORTED_WRITE_OPERATION: "unsupported_operation",
        CLARIFICATION_REQUIRED: "clarification_required",
        UNSUPPORTED_REQUEST: "clarification_required",
    }.get(gate_status, "clarification_required")


def _expected_capabilities(facts: Any) -> set[str]:
    expected: set[str] = set()
    for dimension in facts.dimensions:
        if dimension in DIMENSION_TO_CAPABILITY:
            expected.add(DIMENSION_TO_CAPABILITY[dimension])
        elif dimension.endswith("_notes"):
            expected.add("notes_context")
    return expected


def _catalog_data_blocks(package: CandidatePackage, mapping: Any) -> list[PackageDataBlock]:
    """Create metadata-only package blocks; never copy record or Raw content."""

    blocks: list[PackageDataBlock] = []
    for mapped in mapping.mapped_capabilities:
        source = mapped.source_contracts[0] if mapped.source_contracts else "deterministic_core"
        module_id = source.split(":", 1)[-1] if ":" in source else ""
        card = next((item for item in package.modules if item.module_id == module_id), None)
        if card is None and mapped.capability_id == "notes_context":
            card = next((item for item in package.modules if item.module_id == "notes"), None)
        facts = [
            "只读匿名数据模块可用性与覆盖元数据",
            f"module_available={bool(card and card.available)}",
            f"record_count={int(card.record_count) if card else 0}",
        ]
        blocks.append(PackageDataBlock(mapped.capability_id, source, facts))
    return blocks


class AnalysisIntentPlanner:
    """Adapter that runs the existing two-stage Shadow Planner contract."""

    def __init__(self, transport: ShadowTransport, registry: CapabilityRegistryV1 | None = None) -> None:
        self.transport = transport
        self.registry = registry or CapabilityRegistryV2()

    def plan(self, request: str, facts: Any) -> dict[str, Any]:
        manifest = self.transport.read_manifest()
        if not manifest.available:
            return {"status": "model_unavailable", "manifest": manifest.to_dict(), "requirement": None, "raw_output": ""}

        case = ShadowMatrixCase(
            case_id="preview",
            category="analysis_preview",
            user_goal=request,
            labels=["legal_analysis"],
            expected_capabilities=[],
            optional_capabilities=[],
            forbidden_capabilities=["raw_trace"],
            expected_abstain=False,
            boundary_rules=["planner_only"],
            explanation="Preview-only legal analysis request",
        )
        baseline = {"outcome": "MAPPED", "capability_ids": [], "raw_requested": False}
        expected_ids = _expected_capabilities(facts)
        full_view = self.registry.model_view()["capabilities"] if hasattr(self.registry, "model_view") else None
        # The Gate has already established the legal deterministic dimensions.
        # Passing only that subset prevents optional-capability drift without
        # changing the prompt or repairing the model's response afterwards.
        allowed_view = [item for item in (full_view or []) if item["capability_id"] in expected_ids]
        execution = run_two_stage_case(
            case,
            baseline,
            safe_model_context(facts),
            manifest,
            self.transport,
            self.registry,
            allowed_view,
        )
        record = execution.record
        if record.final_status == "MODEL_UNAVAILABLE":
            return {"status": "model_unavailable", "manifest": manifest.to_dict(), "requirement": None, "raw_output": execution.model_raw_output, "stage_results": execution.stage_results}
        if record.model_proposal is None:
            return {
                "status": "planner_invalid",
                "manifest": manifest.to_dict(),
                "requirement": None,
                "raw_output": execution.model_raw_output,
                "stage_results": execution.stage_results,
                "error_code": (record.validator_errors[0].get("code") if record.validator_errors else "PLANNER_INVALID"),
            }
        try:
            requirement = AnalysisRequirementSpecV1.from_dict(record.model_proposal, user_goal=request)
        except FoundationError as exc:
            return {"status": "planner_invalid", "manifest": manifest.to_dict(), "requirement": None, "raw_output": execution.model_raw_output, "stage_results": execution.stage_results, "error_code": exc.code}
        return {
            "status": "planned",
            "manifest": manifest.to_dict(),
            "requirement": requirement,
            "raw_output": execution.model_raw_output,
            "stage_results": execution.stage_results,
            "latency_ms": record.latency_ms,
            "retry": record.retry,
            "prompt_version": TWO_STAGE_PROMPT_VERSION,
            "request_schema_version": REQUEST_SCHEMA_VERSION,
        }


class AnalysisPreviewService:
    """Run Gate → Planner → mapping → deterministic plan validation → preview."""

    def __init__(self, views: Any, transport: ShadowTransport, registry: CapabilityRegistryV1 | None = None) -> None:
        self.views = views
        self.registry = registry or CapabilityRegistryV2()
        self.catalog = DataCatalogBuilder(views).build()
        self.gate = RequestGate(views, self.catalog)
        self.compiler = IntentCompiler(views)
        self.mapper = RequirementMapper(self.registry)
        self.planner = AnalysisIntentPlanner(transport, self.registry)
        self.validator = ExportPlanValidator()

    @staticmethod
    def _trace_id(request: str, gate: RequestGateDecision) -> str:
        return f"preview:{stable_hash({'request': request, 'gate': gate.status})[:24]}"

    def _base_response(self, request: str, gate: RequestGateDecision, trace_id: str, status: str) -> dict[str, Any]:
        return {
            "schema_version": PREVIEW_SERVICE_SCHEMA_VERSION,
            "status": status,
            "trace_id": trace_id,
            "gate": gate.to_dict(),
            "planner": {"status": "not_run"},
            "validation": {"status": "not_run"},
            "resolution": {"status": "not_run"},
            "mapping_preview": None,
            "gpt_analysis_package_preview": None,
            "review": {"required": True, "editable_fields": ["questions_to_answer", "optional_capabilities", "preferred_time_window"]},
            "execution": {"allowed": False, "mode": "preview_only", "executor_called": False},
            "trace": {
                "schema_version": PREVIEW_TRACE_SCHEMA_VERSION,
                "request": str(request or "")[:2000],
                "gate_status": gate.status,
                "planner_status": "not_run",
                "model_raw_output": "",
                "parsed_requirement": None,
                "validation_result": {"status": "not_run"},
                "failure_category": "REQUEST_GATE" if gate.status != ANALYSIS_REQUEST else "",
            },
        }

    def preview(self, request: str, confirmations: dict[str, Any] | None = None, budget_mode: str = "standard") -> dict[str, Any]:
        confirmations = dict(confirmations or {})
        gate = self.gate.evaluate(request)
        trace_id = self._trace_id(str(request or ""), gate)
        if gate.status != ANALYSIS_REQUEST:
            return self._base_response(request, gate, trace_id, _service_status(gate.status))
        if gate.facts is None:
            return self._base_response(request, gate, trace_id, "clarification_required")

        response = self._base_response(request, gate, trace_id, "planner_invalid")
        planner = self.planner.plan(gate.request, gate.facts)
        response["planner"] = {
            "status": planner.get("status"),
            "model": planner.get("manifest", {}).get("model", ""),
            "model_digest": planner.get("manifest", {}).get("digest", ""),
            "prompt_version": planner.get("prompt_version", ""),
            "request_schema_version": planner.get("request_schema_version", ""),
            "latency_ms": planner.get("latency_ms", 0),
            "retry": planner.get("retry", 0),
            "error_code": planner.get("error_code", ""),
            "raw_output": planner.get("raw_output", ""),
            "stage_results": planner.get("stage_results", {}),
        }
        response["trace"].update(
            {
                "planner_status": planner.get("status", ""),
                "model_name": planner.get("manifest", {}).get("model", ""),
                "model_digest": planner.get("manifest", {}).get("digest", ""),
                "prompt_version": planner.get("prompt_version", ""),
                "model_raw_output": planner.get("raw_output", ""),
            }
        )
        if planner.get("status") == "model_unavailable":
            response["status"] = "model_unavailable"
            response["trace"]["failure_category"] = "MODEL_UNAVAILABLE"
            return response
        if planner.get("status") != "planned" or planner.get("requirement") is None:
            response["trace"]["failure_category"] = "PLANNER_SCHEMA_FAILURE"
            return response

        requirement = planner["requirement"]
        expected = _expected_capabilities(gate.facts)
        try:
            mapping = self.mapper.map(requirement)
        except FoundationError as exc:
            response["status"] = "mapping_unavailable"
            response["validation"] = {"status": "failed", "error_code": exc.code}
            response["trace"].update({"parsed_requirement": requirement.to_dict(), "validation_result": response["validation"], "failure_category": "MAPPING_FAILURE"})
            return response
        mapped_ids = {item.capability_id for item in mapping.mapped_capabilities}
        if mapped_ids != expected:
            response["validation"] = {"status": "failed", "error_code": "CAPABILITY_SCOPE_MISMATCH", "expected": sorted(expected), "actual": sorted(mapped_ids)}
            response["trace"].update({"parsed_requirement": requirement.to_dict(), "validation_result": response["validation"], "failure_category": "PLANNER_SCOPE_FAILURE"})
            return response

        notes_confirmation = confirmations.get("notes_scope")
        if mapping.notes_scope_status == "requires_user_confirmation":
            requested_scopes = set(gate.facts.notes_scopes)
            if notes_confirmation not in requested_scopes:
                response["status"] = "clarification_required"
                response["validation"] = {"status": "passed", "notes_scope_status": mapping.notes_scope_status}
                response["review"]["confirmation_required"] = "notes_scope"
                response["review"]["allowed_notes_scopes"] = sorted(requested_scopes)
                response["mapping_preview"] = mapping.to_dict()
                response["trace"].update({"parsed_requirement": requirement.to_dict(), "validation_result": response["validation"], "failure_category": "HUMAN_CONFIRMATION_REQUIRED"})
                return response
            mapped = [replace(item, status="available", requires_user_confirmation=False) for item in mapping.mapped_capabilities]
            mapping = replace(mapping, mapped_capabilities=mapped, notes_scope_status="confirmed")

        response["mapping_preview"] = mapping.to_dict()
        try:
            _intent, candidate_package, draft = self.compiler.compile(gate.request, None, self.catalog, budget_mode, gate.facts)
            validated_plan = self.validator.validate(draft, candidate_package, gate.request, trace_id=trace_id, trim=False)
        except (IntentCompileError, PlanValidationError) as exc:
            response["status"] = "mapping_unavailable"
            response["validation"] = {"status": "failed", "error_code": getattr(exc, "code", "PLAN_INVALID")}
            response["trace"].update({"parsed_requirement": requirement.to_dict(), "validation_result": response["validation"], "failure_category": "CORE_VALIDATION_FAILURE"})
            return response

        response["validation"] = {"status": "passed", "error_code": "", "scope_locked_by": "deterministic_core"}
        response["resolution"] = {
            "status": "resolved",
            "window": dict(validated_plan.date_range),
            "movement_ids": list(validated_plan.selected_movements),
            "notes_selection_count": len(validated_plan.notes_selection),
        }
        response["mapping_preview"] = {**mapping.to_dict(), "deterministic_plan_preview": validated_plan.to_dict()}
        try:
            package = GPTAnalysisPackage.build(
                requirement,
                mapping,
                gate.request,
                self.catalog.source_snapshot_id,
                _catalog_data_blocks(candidate_package, mapping),
            )
        except FoundationError as exc:
            response["status"] = "mapping_unavailable"
            response["validation"] = {"status": "failed", "error_code": exc.code}
            response["trace"].update({"parsed_requirement": requirement.to_dict(), "validation_result": response["validation"], "failure_category": "PACKAGE_BOUNDARY_FAILURE"})
            return response
        response["gpt_analysis_package_preview"] = package.to_dict()
        response["status"] = "ready"
        response["trace"].update({"parsed_requirement": requirement.to_dict(), "validation_result": response["validation"], "failure_category": ""})
        return response
