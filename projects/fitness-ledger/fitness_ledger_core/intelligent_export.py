"""Read-only intelligent export orchestration and deterministic execution."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict

from .candidate_cards import BUDGETS, CandidatePackage, CandidateSummarizer
from .data_catalog import DataCatalogBuilder, MovementResolver, _record_id, source_snapshot
from .export_plan_validator import ExportPlanValidator, PlanValidationError, validate_source_snapshot
from .export_planner import ExportPlanner
from .export_plan_assembler import ExportPlanAssembler
from .intelligent_export_models import (
    ContractError,
    BODY_PART_IDS,
    ExportPlanDraft,
    ModelPlanningSelection,
    PLANNER_CONFIDENCE_THRESHOLD,
    PlanExplanation,
    TraceRecord,
    ValidatedExportPlan,
    stable_hash,
)
from .local_model_adapter import (
    REPAIR_MODEL_CONFIG,
    LocalModelAdapter,
    LocalModelError,
)
from .shared_view_models import history_in_progress, movement_in_progress
from .intelligent_export_models import selection_json_schema

PROMPT_VERSION = "intelligent-export-prompts-v1"


REPAIR_SYSTEM_PROMPT = """Repair only the Fitness Ledger model selection JSON. Return exactly one selection object matching the supplied schema. Use only the supplied allowed IDs and fields; do not output a full plan, dates, catalog IDs, paths, estimates, raw text, or prose. Movement candidates have roles: EXPLICIT_TARGET and BODY_PART_TARGET directly cover the stated target; CONTEXT and GENERAL_FALLBACK are supporting evidence only. When a direct target candidate exists and movements are selected, retain at least one direct target. Excluded history is context_only and progress metrics must use valid progress history. Repair only semantic contradictions: a complete safe selection should be planning_decision=ready with no fallback reasons; data incompleteness belongs in missing_data_warning_codes. Use planning_decision=fallback_required only when no safe meaningful plan can be formed, with at least one allowed fallback_reason_code. Do not add candidates that were not supplied."""
def _date(value) -> str:
    return str(value or "")[:10]


class ExportExecutor:
    """Execute only an already validated plan against an in-memory read model."""

    def __init__(self, views) -> None:
        self.views = views

    def execute(self, plan: ValidatedExportPlan, package: CandidatePackage, explanation: PlanExplanation) -> dict:
        validate_source_snapshot(self.views, plan.source_snapshot_id)
        data = self.views.analysis(
            start=plan.date_range["resolved_start"],
            end=plan.date_range["resolved_end"],
            include_raw_preview=plan.include_raw_entries,
        )
        selected = set(plan.selected_modules)
        body = self._fields(data.get("body", []), "body", plan) if "body" in selected else []
        diet = self._fields(data.get("diet", []), "diet", plan) if "diet" in selected else []
        training = self._fields(data.get("training", []), "training", plan) if "training" in selected else []
        movements = self._movement_payload(data.get("movements", []), plan, selected)
        notes = self._notes_payload(data, package, plan)
        raw = data.get("raw_entries", []) if plan.include_raw_entries and "raw_entries" in selected else []
        payload = {
            "schema_version": "fitness-ledger-intelligent-export-payload-v1",
            "range": {"start": plan.date_range["resolved_start"], "end": plan.date_range["resolved_end"]},
            "plan_id": plan.plan_id,
            "summary": {
                "selected_modules": plan.selected_modules,
                "selected_movements": plan.selected_movements,
                "progress_metrics_use_valid_history": plan.use_progress_history_for_metrics,
                "context_only_excluded_history": plan.include_excluded_history,
            },
            "body": body,
            "diet": diet,
            "training": training,
            "movements": movements,
            "notes": notes,
            "raw_entries": raw,
            "plan_explanation": explanation.to_dict(),
        }
        execution_evidence = self._execution_evidence(data, package, plan, payload)
        return {"payload": payload, "json": json.dumps(payload, ensure_ascii=False, indent=2), "markdown": self._markdown(payload, plan, explanation), "execution_evidence": execution_evidence}

    @staticmethod
    def _movement_record_id(movement_id: str, history: dict) -> str:
        return f"movement-history:{movement_id}:{history.get('id') or stable_hash([_date(history.get('date')), history.get('order'), history.get('sets')])[:20]}"

    def _execution_evidence(self, data: dict, package: CandidatePackage, plan: ValidatedExportPlan, payload: dict) -> dict:
        """Expose IDs/counts already used by execution without changing payload semantics."""
        start, end = plan.date_range["resolved_start"], plan.date_range["resolved_end"]
        in_range = lambda value: bool(value) and (not start or start <= str(value)[:10] <= end)
        actual_record_ids: list[str] = []
        module_record_counts: dict[str, int] = {}
        for module in ("body", "diet", "training"):
            if module not in plan.selected_modules:
                continue
            rows = [row for row in data.get(module, []) or [] if in_range(row.get("Date"))]
            module_record_counts[module] = len(rows)
            actual_record_ids.extend(_record_id(module, row) for row in rows)
        if plan.include_raw_entries and "raw_entries" in plan.selected_modules:
            rows = [row for row in data.get("raw_entries", []) or [] if in_range(row.get("date"))]
            module_record_counts["raw_entries"] = len(rows)
            actual_record_ids.extend(_record_id("raw", row) for row in rows)
        progress_ids: list[str] = []
        context_ids: list[str] = []
        movement_record_counts: dict[str, int] = {}
        _tracker, dictionary = self.views.snapshot()
        definitions = {str(item.get("movement_id")): item for item in dictionary.get("movements", []) or []}
        wanted = set(plan.selected_movements)
        for movement in data.get("movements", []) or []:
            movement_id = str(movement.get("movement_id", ""))
            if wanted and movement_id not in wanted:
                continue
            count = 0
            definition = definitions.get(movement_id, {})
            for history in movement.get("history", []) or []:
                if not in_range(history.get("date")):
                    continue
                count += 1
                rid = self._movement_record_id(movement_id, history)
                actual_record_ids.append(rid)
                if movement_in_progress(definition) and history_in_progress(history):
                    progress_ids.append(rid)
                elif plan.include_excluded_history:
                    context_ids.append(rid)
            if count:
                movement_record_counts[movement_id] = count
        note_ids = [str(item.get("note_candidate_id", "")) for item in payload.get("notes", []) if item.get("note_candidate_id")]
        roles = dict(getattr(package, "movement_roles", {}) or {})
        target_ids = {movement_id for movement_id, role in roles.items() if role in {"EXPLICIT_TARGET", "BODY_PART_TARGET"}}
        context_movement_ids = {movement_id for movement_id, role in roles.items() if role == "CONTEXT"}
        target_progress_ids = [rid for rid in progress_ids if len(rid.split(":", 2)) > 1 and rid.split(":", 2)[1] in target_ids]
        context_progress_ids = [rid for rid in progress_ids if len(rid.split(":", 2)) > 1 and rid.split(":", 2)[1] in context_movement_ids]
        target_training_record_ids = [item.candidate_record_id for item in package.candidate_records if item.module_id == "training" and item.candidate_record_id in set(plan.candidate_record_ids) and set(item.related_movement_ids).intersection(target_ids)]
        sections = sorted(key for key in payload if key in {"body", "diet", "training", "movements", "notes", "raw_entries"})
        return {
            "actual_record_ids": sorted(set(actual_record_ids)),
            "actual_note_ids": sorted(set(note_ids)),
            "output_sections": sections,
            "actual_output_size": len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
            "progress_history_count": len(progress_ids),
            "progress_history_ids": sorted(set(progress_ids)),
            "target_movement_ids": sorted(target_ids),
            "context_movement_ids": sorted(context_movement_ids),
            "target_progress_history_ids": sorted(target_progress_ids),
            "context_progress_history_ids": sorted(context_progress_ids),
            "target_training_record_ids": sorted(target_training_record_ids),
            "context_only_count": len(context_ids),
            "context_only_ids": sorted(set(context_ids)),
            "module_record_counts": module_record_counts,
            "movement_record_counts": movement_record_counts,
            "missing_data_codes": list(plan.missing_data_warnings),
            "insufficient_sample_codes": [],
            "execution_warning_codes": [],
        }

    @staticmethod
    def _fields(rows: list[dict], module: str, plan: ValidatedExportPlan) -> list[dict]:
        fields = set(plan.selected_fields.get(module, []))
        if not fields:
            return [dict(row) for row in rows]
        fields.add("Date")
        return [{key: value for key, value in row.items() if key in fields} for row in rows]

    def _movement_payload(self, movements: list[dict], plan: ValidatedExportPlan, selected: set[str]) -> list[dict]:
        wanted = set(plan.selected_movements)
        result = []
        _tracker, dictionary = self.views.snapshot()
        definitions = {str(item.get("movement_id")): item for item in dictionary.get("movements", []) or []}
        for movement in movements:
            if wanted and str(movement.get("movement_id")) not in wanted:
                continue
            definition = definitions.get(str(movement.get("movement_id")), {})
            full = []
            progress = []
            context = []
            for history in movement.get("history", []) or []:
                row = dict(history)
                is_progress = movement_in_progress(definition) and history_in_progress(history)
                row["evidence_class"] = "progress_evidence" if is_progress else "context_only"
                if is_progress:
                    progress.append(row)
                elif plan.include_excluded_history:
                    context.append(row)
                if "movement_history" in selected or "movement_progress" in selected:
                    full.append(row)
            if "movement_progress" in selected:
                full = progress
            elif not plan.include_excluded_history:
                full = progress if "movement_history" in selected else []
            result.append({"movement_id": movement.get("movement_id", ""), "display_name": movement.get("display_name", ""), "muscle_group": movement.get("muscle_group", ""), "history": full, "progress_history": progress, "context_only": context})
        return result

    @staticmethod
    def _notes_payload(data: dict, package: CandidatePackage, plan: ValidatedExportPlan) -> list[dict]:
        selected = set(plan.notes_selection)
        cards = {item.note_candidate_id: item for item in package.notes if item.note_candidate_id in selected}
        result = []
        for note_id, card in cards.items():
            text = ""
            if card.note_type == "daily":
                text = next((str(row.get("Notes", "")) for row in data.get("body", []) if str(row.get("id", "")) == card.source_record_id), "")
            elif card.note_type == "diet":
                text = next((str(row.get("Notes", "")) for row in data.get("diet", []) if str(row.get("id", "")) == card.source_record_id), "")
            elif card.note_type == "training":
                text = next((str(row.get("Notes", "")) for row in data.get("training", []) if str(row.get("id", "")) == card.source_record_id), "")
            elif card.note_type == "movement":
                for movement in data.get("movements", []):
                    for history in movement.get("history", []) or []:
                        if str(history.get("id", "")) == card.history_id:
                            text = str(history.get("notes", ""))
                            break
            result.append({"note_candidate_id": note_id, "date": card.date, "scope": card.scope, "movement_id": card.movement_id, "history_id": card.history_id, "text": text})
        return result

    @staticmethod
    def _markdown(payload: dict, plan: ValidatedExportPlan, explanation: PlanExplanation) -> str:
        lines = ["# Fitness Ledger 智能分析导出", "", f"日期：{payload['range']['start']} 至 {payload['range']['end']}", f"计划：{plan.plan_id}", "", "## 计划说明", "", f"目标：{explanation.interpreted_goal}"]
        if explanation.selected_modules:
            lines.append(f"- 模块：{'、'.join(explanation.selected_modules)}")
        if explanation.selected_movements:
            lines.append(f"- 动作：{'、'.join(explanation.selected_movements)}")
        if explanation.missing_data:
            lines.extend(["- 数据提示：" + "；".join(explanation.missing_data)])
        if payload.get("body"):
            lines.extend(["", "## Body", ""])
            lines.extend(json.dumps(row, ensure_ascii=False) for row in payload["body"])
        if payload.get("diet"):
            lines.extend(["", "## Diet", ""])
            lines.extend(json.dumps(row, ensure_ascii=False) for row in payload["diet"])
        if payload.get("training"):
            lines.extend(["", "## Training", ""])
            lines.extend(json.dumps(row, ensure_ascii=False) for row in payload["training"])
        if payload.get("movements"):
            lines.extend(["", "## Movement", ""])
            for movement in payload["movements"]:
                lines.append(f"### {movement['display_name']} ({movement['movement_id']})")
                for history in movement.get("history", []):
                    marker = "context_only" if history.get("evidence_class") == "context_only" else "progress_evidence"
                    lines.append(f"- {_date(history.get('date'))} [{marker}] {json.dumps(history.get('sets', []), ensure_ascii=False)}")
        if payload.get("notes"):
            lines.extend(["", "## Notes", ""])
            for note in payload["notes"]:
                lines.append(f"- {note['date']} [{note['scope']}] {note['text']}")
        if payload.get("raw_entries"):
            lines.extend(["", "## Raw Preview", ""])
            for row in payload["raw_entries"]:
                lines.append(f"- {row.get('date', '')}: {row.get('preview', '')}")
        return "\n".join(lines).strip() + "\n"


class IntelligentExportService:
    """Single-stage deterministic scope → Planning → execution pipeline."""

    _task_slots = threading.BoundedSemaphore(1)

    def __init__(self, views, adapter: LocalModelAdapter, overall_timeout: float = 120.0) -> None:
        self.views = views
        self.adapter = adapter
        self.overall_timeout = overall_timeout
        self.catalog_builder = DataCatalogBuilder(views)
        self.validator = ExportPlanValidator()
        self.executor = ExportExecutor(views)

    def run(self, request: str, budget_mode: str = "standard") -> dict:
        started = time.monotonic(); trace_id = f"trace:{uuid.uuid4().hex[:16]}"
        if not self._task_slots.acquire(timeout=5.0):
            return {"status": "model_unavailable", "error_code": "MODEL_BUSY", "trace": {"trace_id": trace_id}}
        try:
            catalog = self.catalog_builder.build()
            from .query_scope import QueryScopeResolver
            from .basic_export_fallback import BasicExportFallbackBuilder
            scope = QueryScopeResolver(catalog=catalog).resolve(request)
            diagnostics = {"prompt_version": PROMPT_VERSION, "stages": {}, "model_call_count": 0, "planning_repair_used": False, "candidate_counts": {}}
            if self._expired(started):
                return self._basic_fallback(request, scope, catalog, None, "TASK_TIMEOUT", trace_id, started, diagnostics)
            package = CandidateSummarizer(catalog, MovementResolver(self.views)).build(request, scope, budget_mode)
            diagnostics["candidate_counts"] = {"windows": len(package.windows), "modules": len(package.modules), "movements": len(package.movements), "notes": len(package.notes), "records": len(package.candidate_records)}
            if not package.windows:
                return {"status": "no_usable_data", "error_code": "NO_USABLE_DATA", "query_scope": scope.to_dict(), "catalog": catalog.to_prompt_dict(), "candidate_package": package.to_prompt_dict(), "trace": {"trace_id": trace_id}}
            planner = ExportPlanner(self.adapter); assembler = ExportPlanAssembler(package)
            selection = None; result = None; repaired = False; repair_meta = {}
            try:
                selection, result = planner.plan(request, scope, package); diagnostics["model_call_count"] = 1
                if selection.planning_decision == "fallback_required":
                    raise ContractError("planner requested fallback", "NO_SAFE_PLAN")
                if selection.planner_confidence < PLANNER_CONFIDENCE_THRESHOLD:
                    raise ContractError("planner confidence is below the safe threshold", "NO_SAFE_PLAN")
                diagnostics["stages"]["planning"] = self._model_diag(result)
                draft = assembler.assemble(selection, request, scope, trace_id)
                plan = self.validator.validate(draft, package, request, trace_id)
            except Exception as first_error:
                diagnostics["model_call_count"] = max(diagnostics["model_call_count"], 1)
                try:
                    repaired = True; diagnostics["planning_repair_used"] = True
                    diagnostics["repair"] = {"repair_used": True, "phase": "planning", "original_validation_codes": [getattr(first_error, "code", "PLANNING_INVALID")], "repaired_validation_codes": []}
                    repair_result = self.adapter.generate_json(system_prompt=REPAIR_SYSTEM_PROMPT, user_payload={"original_request": str(request or "")[:2000], "query_scope": scope.to_dict(), "invalid_selection": selection.to_dict() if selection else {}, "validation_error": {"code": getattr(first_error, "code", "PLANNING_INVALID"), "message": str(first_error)[:240]}, "target_scope": package.target_scope.to_dict(), "candidate_roles": package.movement_roles, "allowed_window_ids": package.allowed_ids["window_ids"], "allowed_module_ids": package.allowed_modules, "allowed_field_ids_by_module": package.allowed_fields, "allowed_movement_ids": package.allowed_ids["movement_ids"], "allowed_note_candidate_ids": package.allowed_ids["note_candidate_ids"], "allowed_candidate_record_ids": package.allowed_ids["candidate_record_ids"], "selection_schema": selection_json_schema()}, response_schema=selection_json_schema(), config=REPAIR_MODEL_CONFIG)
                    diagnostics["model_call_count"] = 2; diagnostics["stages"]["repair"] = self._model_diag(repair_result)
                    selection = planner.parse_selection(repair_result.raw_text); planner._validate_target_coverage(selection, package)
                    diagnostics["repair"]["repaired_validation_codes"] = ["REPAIRED_SELECTION"]
                    draft = assembler.assemble(selection, request, scope, trace_id); plan = self.validator.validate(draft, package, request, trace_id, trim=False)
                except Exception as repair_error:
                    return self._basic_fallback(request, scope, catalog, package, getattr(repair_error, "code", getattr(first_error, "code", "PLANNING_FAILED")), trace_id, started, diagnostics)
            explanation = PlanExplanation(request[:2000], plan.interpreted_goal, plan.date_range, plan.selected_modules, plan.selected_fields, plan.selected_movements, plan.notes_selection, plan.inclusion_reasons, plan.exclusion_reasons, plan.missing_data_warnings, plan.estimated_output_size, plan.planner_confidence, repaired, plan.trimmed, False)
            output = self.executor.execute(plan, package, explanation)
            diagnostics["duration_ms"] = int((time.monotonic() - started) * 1000)
            trace = TraceRecord(trace_id, stable_hash(request[:2000]), stable_hash(catalog.to_prompt_dict()), stable_hash(plan.to_dict()), getattr(self.adapter, "adapter_name", "unknown"), getattr(self.adapter, "model_name", "unknown"), PROMPT_VERSION, "", diagnostics["duration_ms"], "", repaired, plan.trimmed, False)
            return {"status": "ready", "query_scope": scope.to_dict(), "catalog": catalog.to_prompt_dict(), "candidate_package": package.to_prompt_dict(), "selection": selection.to_dict(), "plan": plan.to_dict(), "explanation": explanation.to_dict(), "output": output, "trace": trace.to_dict(), "diagnostics": diagnostics}
        except Exception as exc:
            return {"status": "execution_failed", "error_code": getattr(exc, "code", "EXECUTION_FAILED"), "trace": {"trace_id": trace_id, "error": str(exc)[:240]}}
        finally:
            self._task_slots.release()

    def _basic_fallback(self, request, scope, catalog, package, reason, trace_id, started, diagnostics):
        from .basic_export_fallback import BasicExportFallbackBuilder
        try:
            if package is None:
                package = CandidateSummarizer(catalog, MovementResolver(self.views)).build(request, scope, "standard")
            selection = BasicExportFallbackBuilder().build(request, scope, package, reason)
            planner = ExportPlanner(self.adapter); planner._validate_selection(selection, package); planner._validate_target_coverage(selection, package)
            draft = ExportPlanAssembler(package).assemble(selection, request, scope, trace_id)
            plan = self.validator.validate(draft, package, request, trace_id, trim=False)
            explanation = PlanExplanation(request[:2000], plan.interpreted_goal, plan.date_range, plan.selected_modules, plan.selected_fields, plan.selected_movements, plan.notes_selection, plan.inclusion_reasons, plan.exclusion_reasons, plan.missing_data_warnings, plan.estimated_output_size, plan.planner_confidence, bool(diagnostics.get("planning_repair_used")), plan.trimmed, True)
            output = self.executor.execute(plan, package, explanation)
            diagnostics["duration_ms"] = int((time.monotonic() - started) * 1000); diagnostics["fallback_reason"] = reason
            return {"status": "basic_fallback_used", "query_scope": scope.to_dict(), "catalog": catalog.to_prompt_dict(), "candidate_package": package.to_prompt_dict(), "selection": selection.to_dict(), "plan": plan.to_dict(), "explanation": explanation.to_dict(), "output": output, "fallback": {"used": True, "reason": reason, "selected_movement_ids": plan.selected_movements}, "diagnostics": diagnostics, "trace": {"trace_id": trace_id, "fallback": True, "duration_ms": diagnostics["duration_ms"]}}
        except Exception as exc:
            return {"status": "no_usable_data", "error_code": "NO_USABLE_DATA", "query_scope": scope.to_dict(), "trace": {"trace_id": trace_id, "fallback": True, "error": str(exc)[:240]}}

    def _expired(self, started: float) -> bool:
        return time.monotonic() - started > self.overall_timeout

    @staticmethod
    def _model_diag(result, extra=None) -> dict:
        data = dict(extra or {})
        data.update({"adapter": getattr(result, "adapter", ""), "model": getattr(result, "model", ""), "duration_ms": getattr(result, "duration_ms", 0), "output_chars": getattr(result, "output_chars", len(getattr(result, "raw_text", ""))), "response_keys": getattr(result, "response_keys", []), "message_keys": getattr(result, "message_keys", []), "finish_reason": getattr(result, "finish_reason", ""), "eval_count": getattr(result, "eval_count", 0), "prompt_eval_count": getattr(result, "prompt_eval_count", 0), "http_status": getattr(result, "http_status", 0), "response_bytes": getattr(result, "response_bytes", 0), "load_duration_ns": getattr(result, "load_duration_ns", 0), "prompt_eval_duration_ns": getattr(result, "prompt_eval_duration_ns", 0), "eval_duration_ns": getattr(result, "eval_duration_ns", 0), "truncated": getattr(result, "truncated", False)})
        return data
