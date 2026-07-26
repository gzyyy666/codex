"""Vertical-slice service for the registry-driven analysis path."""
from __future__ import annotations
from typing import Any

from .analysis_materialization import EvidenceMaterializer, EvidenceProfileConsistencyValidator, evaluate_materialized_evidence
from .analysis_registry import AnalysisOperation, ConfirmationStateMachine, IntentASTParser, TaskRegistry
from .data_catalog import DataCatalogBuilder
from .intent_compiler import IntentCompiler, IntentCompileError
from .intelligent_export_models import IntentSpec
from .request_gate import ANALYSIS_REQUEST, MOVEMENT_RESOLUTION_REQUIRED, RAW_PERMISSION_REQUIRED, RequestGate, UNSUPPORTED_WRITE_OPERATION

REGISTRY_CONVERGENCE_SERVICE_SCHEMA_VERSION="fitness-ledger-registry-convergence-service-v1"

class RegistryConvergencePreviewService:
    def __init__(self, views: Any):
        self.views=views; self.catalog=DataCatalogBuilder(views).build(); self.gate=RequestGate(views,self.catalog); self.compiler=IntentCompiler(views); self.task_registry=TaskRegistry(); self.materializer=EvidenceMaterializer(); self.profile_validator=EvidenceProfileConsistencyValidator()

    @staticmethod
    def _safe_security(response):
        response["security"]={"executor_called":False,"raw_read":False,"formal_data_written":False,"raw_in_authorized_modules":False}
        return response

    def preview(self, request: str) -> dict[str,Any]:
        ast=IntentASTParser.parse(request); gate=self.gate.evaluate(request); machine=ConfirmationStateMachine(); machine.advance("gate")
        base={"schema_version":REGISTRY_CONVERGENCE_SERVICE_SCHEMA_VERSION,"user_input":str(request or ""),"gate":gate.to_dict(),"intent_ast":ast.to_dict(),"task_selection":None,"task_expansion":None,"slots":{},"state":machine.to_dict(),"materialized_evidence":None,"evidence_evaluation":None,"safety":{},"model_fallback":{"called":False,"task_source":"deterministic_alias","status":"not_run"}}
        if gate.status in {RAW_PERMISSION_REQUIRED,UNSUPPORTED_WRITE_OPERATION}:
            if gate.status==RAW_PERMISSION_REQUIRED: machine.advance("needs_raw_permission")
            else: machine.advance("blocked")
            base["state"]=machine.to_dict(); base["status"]="raw_permission_required" if gate.status==RAW_PERMISSION_REQUIRED else "unsupported_operation"; return self._safe_security(base)
        if gate.status not in {ANALYSIS_REQUEST, MOVEMENT_RESOLUTION_REQUIRED} or gate.facts is None:
            machine.advance("needs_analysis_target"); base["state"]=machine.to_dict(); base["status"]="clarification_required"; return self._safe_security(base)
        task_ids=self.task_registry.resolve(ast); base["task_selection"]={"task_ids":task_ids,"task_source":"deterministic_alias"}
        if not task_ids:
            machine.advance("needs_analysis_target"); base["state"]=machine.to_dict(); base["status"]="clarification_required"; return self._safe_security(base)
        expansion=self.task_registry.expand(task_ids,ast); base["task_expansion"]=expansion.to_dict(); machine.advance("task_resolved")
        confirmations=list(expansion.required_confirmations)
        if gate.status==MOVEMENT_RESOLUTION_REQUIRED or getattr(gate.facts,"movement_ambiguous",False):
            if "movement_identity" not in confirmations: confirmations.append("movement_identity")
        if confirmations:
            event="needs_notes_scope" if "notes_scope" in confirmations else "needs_movement_confirmation" if any(x in confirmations for x in ("movement_identity","movement_or_bodypart_scope")) else "needs_analysis_target"
            machine.advance(event); base["slots"]={"required_confirmations":confirmations,"movement":ast.movement_expression,"notes":ast.notes_expression}; base["state"]=machine.to_dict(); base["status"]="movement_resolution_required" if event=="needs_movement_confirmation" else "confirmation_required"; base["evidence_evaluation"]={"status":"needs_confirmation","answerability":"needs_resolution","missing_information":confirmations}; return self._safe_security(base)
        try:
            intent, candidate_package, draft=self.compiler.compile(request,IntentSpec([],[],[],[],[],False),self.catalog,facts=gate.facts)
        except IntentCompileError as exc:
            machine.advance("needs_movement_confirmation" if exc.code=="UNRESOLVED_REQUIRED_MOVEMENT" else "needs_analysis_target"); base["state"]=machine.to_dict(); base["status"]="movement_resolution_required" if exc.code=="UNRESOLVED_REQUIRED_MOVEMENT" else "clarification_required"; base["slots"]={"error_code":exc.code}; return self._safe_security(base)
        machine.advance("evidence_ready"); evidence=self.materializer.materialize(candidate_package,expansion); profile_errors=self.profile_validator.validate(evidence); evaluation=evaluate_materialized_evidence(expansion,evidence)
        machine.advance("materialized"); machine.advance("insufficient" if evaluation["answerability"]=="insufficient_evidence" else "limited" if evaluation["answerability"]=="ready_with_limits" else "ready")
        base.update({"slots":{"time_expression":ast.time_expression,"movement_expression":ast.movement_expression,"bodypart_expression":ast.bodypart_expression,"condition_groups":ast.condition_groups,"explicit_only":ast.explicit_only,"explicit_include":ast.explicit_include,"explicit_exclude":ast.explicit_exclude},"materialized_evidence":evidence.to_dict(),"evidence_profile_validation":{"errors":profile_errors,"passed":not profile_errors},"evidence_evaluation":evaluation,"state":machine.to_dict(),"status":"ready_with_limits" if evaluation["answerability"]=="ready_with_limits" else "insufficient_evidence" if evaluation["answerability"]=="insufficient_evidence" else "ready","mapping_preview":{"required_capabilities":expansion.required_capabilities,"optional_capabilities":expansion.optional_capabilities,"required_fields":expansion.required_fields,"authorized_modules":evidence.profile.authorized_modules,"metric_ids":expansion.metric_ids}})
        return self._safe_security(base)
