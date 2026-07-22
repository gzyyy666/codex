"""Read-only intelligent export orchestration and deterministic execution."""

from __future__ import annotations

import json
import re
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
    IntentSpec,
    ManualFallbackResult,
    PlanExplanation,
    TraceRecord,
    ValidatedExportPlan,
    stable_hash,
)
from .intent_interpreter import IntentInterpreter, IntentSemanticError, parse_json_object, INTENT_SYSTEM_PROMPT, PROMPT_VERSION
from .intent_semantic_validator import repair_diff
from .local_model_adapter import (
    INTENT_MODEL_CONFIG,
    REPAIR_MODEL_CONFIG,
    LocalModelAdapter,
    LocalModelError,
)
from .shared_view_models import history_in_progress, movement_in_progress
from .intelligent_export_models import intent_json_schema, selection_json_schema


REPAIR_SYSTEM_PROMPT = """Repair only the Fitness Ledger model selection JSON. Return exactly one selection object matching the supplied schema. Use only the supplied allowed IDs and fields; do not output a full plan, dates, catalog IDs, paths, estimates, raw text, or prose. Movement candidates have roles: EXPLICIT_TARGET and BODY_PART_TARGET directly cover the stated target; CONTEXT and GENERAL_FALLBACK are supporting evidence only. When a direct target candidate exists and movements are selected, retain at least one direct target. Excluded history is context_only and progress metrics must use valid progress history. Repair only semantic contradictions: a complete safe selection should be planning_decision=ready with no fallback reasons; data incompleteness belongs in missing_data_warning_codes. Use planning_decision=fallback_required only when no safe meaningful plan can be formed, with at least one allowed fallback_reason_code. Do not add candidates that were not supplied."""
INTENT_REPAIR_SYSTEM_PROMPT = """Repair only the Fitness Ledger intent JSON. Return one corrected Intent JSON object matching the supplied schema, with no Markdown or prose. Preserve every valid field and only repair fields identified by the validation errors. Required text fields must contain meaningful natural-language text, not placeholders such as ?, ??, ？？, N/A, unknown, or replacement characters. Represent explicitly requested body regions in target_body_parts using only CHEST, BACK, SHOULDER, ARMS, CORE, or LEGS. Represent only explicitly named exercises in movement_mentions. Do not convert a body-part scope into a specific movement, invent movements or body parts, or retain movement_mentions.body_part. Use the original user request as the sole semantic source. Do not invent dates, modules, measurements, or facts. Do not generate normalized or ISO dates; preserve explicit date phrases in raw_date_mentions and use only allowed date intent modes. Do not add fields outside the schema. Do not output an export plan, catalog contents, raw entries, paths, or full prompts."""


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
    """Serial Intent → Planning → optional Repair orchestration."""

    _task_slots = threading.BoundedSemaphore(1)

    def __init__(self, views, adapter: LocalModelAdapter, overall_timeout: float = 120.0) -> None:
        self.views = views
        self.adapter = adapter
        self.overall_timeout = overall_timeout
        self.catalog_builder = DataCatalogBuilder(views)
        self.validator = ExportPlanValidator()
        self.executor = ExportExecutor(views)

    def run(self, request: str, budget_mode: str = "standard") -> dict:
        started = time.monotonic()
        trace_id = f"trace:{uuid.uuid4().hex[:16]}"
        if not self._task_slots.acquire(timeout=5.0):
            return self._fallback(request, "MODEL_BUSY", trace_id, started)
        try:
            catalog = None
            diagnostics = {"prompt_version": PROMPT_VERSION, "schema_version": "fitness-ledger-intelligent-export-v1", "candidate_counts": {}, "stages": {}}
            catalog_summary = self._intent_catalog_summary(budget_mode)
            repair_used = False
            repair_meta = {"repair_used": False, "intent_repair_used": False, "original_validation_codes": [], "repaired_validation_codes": [], "changed_field_names": [], "added_selected_ids": [], "removed_selected_ids": [], "decision_changed": False, "confidence_before": None, "confidence_after": None, "intent_schema_status": "valid", "intent_semantic_status": "valid", "intent_semantic_error_codes": [], "intent_initial_semantic_error_codes": [], "intent_semantic_diagnostics": {}, "intent_repair": {}}
            intent_interpreter = IntentInterpreter(self.adapter)
            try:
                intent, intent_result = intent_interpreter.interpret(request, catalog_summary)
                diagnostics["stages"]["intent"] = self._model_diag(intent_result, {"payload_chars": len(json.dumps(catalog_summary, ensure_ascii=False)), "schema_chars": len(json.dumps(intent_json_schema(), ensure_ascii=False))})
            except Exception as exc:
                try:
                    repair_used = True
                    semantic_before = getattr(exc, "result", None)
                    invalid_intent = getattr(exc, "intent", None)
                    semantic_codes = list(getattr(semantic_before, "error_codes", []) or [])
                    invalid_paths = list(getattr(semantic_before, "invalid_field_paths", []) or [])
                    safe_diagnostics = dict(getattr(semantic_before, "diagnostics", {}) or {})
                    original_codes = semantic_codes or [getattr(exc, "code", "INTENT_INVALID")]
                    repair_meta.update({"repair_used": True, "intent_repair_used": True, "phase": "intent", "original_validation_codes": original_codes, "intent_schema_status": "invalid" if not semantic_before else "valid", "intent_semantic_status": "invalid" if semantic_before else "valid", "intent_semantic_error_codes": semantic_codes, "intent_initial_semantic_error_codes": semantic_codes, "intent_semantic_diagnostics": safe_diagnostics})
                    repair_payload = {"request": str(request or "")[:2000], "invalid_intent": invalid_intent.to_dict() if invalid_intent else {}, "validation_error": {"codes": original_codes, "field_paths": invalid_paths, "diagnostics": safe_diagnostics}, "allowed_target_body_parts": list(BODY_PART_IDS), "intent_schema": intent_json_schema()}
                    repair_result = self.adapter.generate_json(system_prompt=INTENT_REPAIR_SYSTEM_PROMPT, user_payload=repair_payload, response_schema=intent_json_schema(), config=REPAIR_MODEL_CONFIG)
                    repaired_raw = parse_json_object(repair_result.raw_text)
                    repaired_intent, repaired_semantic = intent_interpreter.parse_repair(request, repair_result.raw_text)
                    intent = repaired_intent; intent_result = repair_result
                    repair_meta["intent_schema_status"] = "valid_after_repair"
                    repair_meta["intent_semantic_status"] = "valid_after_repair"
                    repair_meta["intent_semantic_error_codes"] = []
                    repair_meta["repaired_validation_codes"] = []
                    repair_meta["intent_repair"] = repair_diff(invalid_intent.to_dict() if invalid_intent else {}, repaired_raw, semantic_codes, repaired_semantic.error_codes)
                    repair_meta["changed_field_names"] = repair_meta["intent_repair"].get("changed_field_paths", [])
                    diagnostics["stages"]["intent"] = self._model_diag(intent_result, {"payload_chars": len(json.dumps(catalog_summary, ensure_ascii=False)), "schema_chars": len(json.dumps(intent_json_schema(), ensure_ascii=False))})
                except Exception as repair_error:
                    final_semantic = getattr(repair_error, "result", None)
                    final_intent = getattr(repair_error, "intent", None) or invalid_intent
                    if final_semantic:
                        repair_meta["intent_semantic_status"] = "invalid"
                        repair_meta["intent_semantic_error_codes"] = list(final_semantic.error_codes)
                        repair_meta["intent_semantic_diagnostics"] = dict(final_semantic.diagnostics)
                        repair_meta["intent_repair"] = repair_diff(invalid_intent.to_dict() if invalid_intent else {}, final_intent.to_dict() if final_intent else {}, semantic_codes, final_semantic.error_codes)
                        repair_meta["changed_field_names"] = repair_meta["intent_repair"].get("changed_field_paths", [])
                        diagnostics["intent_semantic"] = {"initial_status": "invalid", "final_status": "invalid", "error_codes": list(final_semantic.error_codes), "invalid_field_paths": list(final_semantic.invalid_field_paths), "diagnostics": dict(final_semantic.diagnostics)}
                        diagnostics["repair"] = repair_meta
                        return self._fallback(request, "MODEL_INTENT_SEMANTIC_INVALID", trace_id, started, catalog, final_intent, diagnostics)
                    diagnostics["repair"] = repair_meta
                    return self._fallback(request, getattr(repair_error, "code", "MODEL_REPAIR_FAILED"), trace_id, started, catalog, invalid_intent, diagnostics)
            diagnostics.setdefault("intent_semantic", {"initial_status": "invalid" if repair_meta.get("intent_initial_semantic_error_codes") else "valid", "final_status": repair_meta.get("intent_semantic_status", "valid"), "error_codes": repair_meta.get("intent_semantic_error_codes", []), "invalid_field_paths": repair_meta.get("intent_repair", {}).get("changed_field_paths", []), "diagnostics": repair_meta.get("intent_semantic_diagnostics", {})})
            catalog = self.catalog_builder.build()
            if self._expired(started):
                return self._fallback(request, "TASK_TIMEOUT", trace_id, started, catalog)
            try:
                package = CandidateSummarizer(catalog, MovementResolver(self.views)).build(request, intent, budget_mode)
                diagnostics["candidate_counts"] = {"windows": len(package.windows), "modules": len(package.modules), "movements": len(package.movements), "notes": len(package.notes), "records": len(package.candidate_records), "allowed_ids": {key: len(value) for key, value in package.allowed_ids.items()}}
                if not package.windows:
                    return self._fallback(request, "NO_VALID_WINDOW", trace_id, started, catalog, intent)
            except Exception as exc:
                return self._fallback(request, getattr(exc, "code", "CATALOG_INVALID"), trace_id, started, catalog, intent)
            planner = ExportPlanner(self.adapter)
            assembler = ExportPlanAssembler(package)
            try:
                selection, planning_result = planner.plan(request, intent, package)
                if selection.planning_decision == "fallback_required":
                    return self._fallback(request, "PLANNER_FALLBACK_REQUIRED", trace_id, started, catalog, intent)
                if selection.planner_confidence < PLANNER_CONFIDENCE_THRESHOLD:
                    return self._fallback(request, "LOW_CONFIDENCE", trace_id, started, catalog, intent)
                draft = assembler.assemble(selection, request, intent, trace_id)
                diagnostics["stages"]["planning"] = self._model_diag(planning_result, {"payload_chars": len(json.dumps(planner.last_payload or {}, ensure_ascii=False)), "schema_chars": len(json.dumps(selection_json_schema(), ensure_ascii=False))})
            except Exception as exc:
                if repair_used:
                    return self._fallback(request, getattr(exc, "code", "MODEL_SELECTION_INVALID"), trace_id, started, catalog, intent, diagnostics)
                try:
                    repair_used = True
                    repair_meta.update({"repair_used": True, "phase": "selection", "original_validation_codes": [getattr(exc, "code", "PLANNING_INVALID")]})
                    before_selection = getattr(planner, "last_selection", None)
                    repair_result = self.adapter.generate_json(system_prompt=REPAIR_SYSTEM_PROMPT, user_payload={"invalid_selection": getattr(planner.last_result, "raw_text", "")[:12000], "validation_error": {"code": getattr(exc, "code", "PLANNING_INVALID"), "message": str(exc)[:240]}, "target_scope": package.target_scope.to_dict(), "candidate_roles": package.movement_roles, "allowed_window_ids": package.allowed_ids["window_ids"], "allowed_module_ids": package.allowed_modules, "allowed_field_ids_by_module": package.allowed_fields, "allowed_movement_ids": package.allowed_ids["movement_ids"], "allowed_note_candidate_ids": package.allowed_ids["note_candidate_ids"], "allowed_candidate_record_ids": package.allowed_ids["candidate_record_ids"], "selection_schema": selection_json_schema()}, response_schema=selection_json_schema(), config=REPAIR_MODEL_CONFIG)
                    selection = planner.parse_selection(repair_result.raw_text); planner._validate_target_coverage(selection, package)
                    self._record_repair_meta(repair_meta, before_selection.to_dict() if before_selection else {}, selection.to_dict())
                    if selection.planning_decision == "fallback_required":
                        return self._fallback(request, "PLANNER_FALLBACK_REQUIRED", trace_id, started, catalog, intent)
                    if selection.planner_confidence < PLANNER_CONFIDENCE_THRESHOLD:
                        return self._fallback(request, "LOW_CONFIDENCE", trace_id, started, catalog, intent)
                    draft = assembler.assemble(selection, request, intent, trace_id)
                    diagnostics["stages"]["repair"] = self._model_diag(repair_result, {"schema_chars": len(json.dumps(selection_json_schema(), ensure_ascii=False))})
                except Exception as repair_error:
                    return self._fallback(request, getattr(repair_error, "code", "MODEL_REPAIR_FAILED"), trace_id, started, catalog, intent, diagnostics)
            repaired = repair_used
            try:
                plan = self.validator.validate(draft, package, request, trace_id)
            except PlanValidationError as first_error:
                if repair_used or self._expired(started):
                    return self._fallback(request, first_error.code if repair_used else "TASK_TIMEOUT", trace_id, started, catalog, intent)
                repaired = True
                try:
                    repair_meta.update({"repair_used": True, "phase": "validation", "original_validation_codes": [first_error.code]})
                    before_selection = selection.to_dict()
                    repair_result = self.adapter.generate_json(system_prompt=REPAIR_SYSTEM_PROMPT, user_payload={"invalid_selection": selection.to_dict(), "validation_error": {"code": first_error.code, "message": str(first_error)[:240]}, "target_scope": package.target_scope.to_dict(), "candidate_roles": package.movement_roles, "allowed_window_ids": package.allowed_ids["window_ids"], "allowed_module_ids": package.allowed_modules, "allowed_field_ids_by_module": package.allowed_fields, "allowed_movement_ids": package.allowed_ids["movement_ids"], "allowed_note_candidate_ids": package.allowed_ids["note_candidate_ids"], "allowed_candidate_record_ids": package.allowed_ids["candidate_record_ids"], "selection_schema": selection_json_schema()}, response_schema=selection_json_schema(), config=REPAIR_MODEL_CONFIG)
                    selection = planner.parse_selection(repair_result.raw_text); planner._validate_target_coverage(selection, package)
                    self._record_repair_meta(repair_meta, before_selection, selection.to_dict())
                    if selection.planning_decision == "fallback_required":
                        return self._fallback(request, "PLANNER_FALLBACK_REQUIRED", trace_id, started, catalog, intent)
                    if selection.planner_confidence < PLANNER_CONFIDENCE_THRESHOLD:
                        return self._fallback(request, "LOW_CONFIDENCE", trace_id, started, catalog, intent)
                    draft = assembler.assemble(selection, request, intent, trace_id); plan = self.validator.validate(draft, package, request, trace_id, trim=False)
                    diagnostics["stages"]["repair"] = self._model_diag(repair_result, {"schema_chars": len(json.dumps(selection_json_schema(), ensure_ascii=False))})
                except Exception as repair_error:
                    return self._fallback(request, getattr(repair_error, "code", "MODEL_REPAIR_FAILED"), trace_id, started, catalog, intent)
            if self._expired(started):
                return self._fallback(request, "TASK_TIMEOUT", trace_id, started, catalog, intent)
            explanation = PlanExplanation(request[:2000], plan.interpreted_goal, plan.date_range, plan.selected_modules, plan.selected_fields, plan.selected_movements, plan.notes_selection, plan.inclusion_reasons, plan.exclusion_reasons, plan.missing_data_warnings, plan.estimated_output_size, plan.planner_confidence, repaired, plan.trimmed, False)
            try:
                output = self.executor.execute(plan, package, explanation)
            except PlanValidationError as exc:
                return self._fallback(request, exc.code, trace_id, started, catalog, intent)
            trace = TraceRecord(trace_id, stable_hash(request[:2000]), stable_hash(catalog.to_prompt_dict()), stable_hash(plan.to_dict()), getattr(self.adapter, "adapter_name", "unknown"), getattr(self.adapter, "model_name", "unknown"), PROMPT_VERSION, "", int((time.monotonic() - started) * 1000), "", repaired, plan.trimmed, False)
            diagnostics["duration_ms"] = int((time.monotonic() - started) * 1000)
            diagnostics["repair"] = repair_meta
            return {"status": "ready", "intent": intent.to_dict(), "catalog": catalog.to_prompt_dict(), "candidate_package": package.to_prompt_dict(), "selection": selection.to_dict(), "plan": plan.to_dict(), "explanation": explanation.to_dict(), "output": output, "trace": trace.to_dict(), "diagnostics": diagnostics}
        finally:
            self._task_slots.release()

    def _fallback(self, request: str, reason: str, trace_id: str, started: float, catalog=None, intent=None, diagnostics=None) -> dict:
        dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", str(request or ""))
        explicit = {"start": dates[0], "end": dates[-1]} if dates else {}
        modules = [item for item in ("body", "diet", "training", "movement_history") if any(word in str(request).lower() for word in {item, {"body": "体重", "diet": "饮食", "training": "训练", "movement_history": "动作"}.get(item, "")})]
        result = ManualFallbackResult(True, reason, explicit, {"days": 14, **explicit, "modules": modules}, ["模型结果不可用，未自动猜测未明确的范围或动作。"], trace_id)
        output = {"status": "fallback", "fallback": result.to_dict(), "trace": {"trace_id": trace_id, "error_code": reason, "duration_ms": int((time.monotonic() - started) * 1000), "fallback": True}}
        if intent is not None:
            output["intent"] = intent.to_dict() if hasattr(intent, "to_dict") else intent
        if diagnostics:
            output["diagnostics"] = diagnostics
        return output

    def _expired(self, started: float) -> bool:
        return time.monotonic() - started > self.overall_timeout

    def _intent_catalog_summary(self, budget_mode: str) -> dict:
        """Build only the safe date/module summary needed by Intent prompting."""
        data = self.views.analysis(days=36500, include_raw_preview=False)
        tracker, _dictionary = self.views.snapshot()
        dates = []
        for module in ("body", "diet", "training"):
            dates.extend(str(row.get("Date", ""))[:10] for row in data.get(module, []) or [] if row.get("Date"))
        movement_count = 0
        for movement in (tracker.get("movements", {}) or {}).values():
            histories = movement.get("history", []) if isinstance(movement, dict) else []
            movement_count += len(histories or [])
            dates.extend(str(row.get("date", ""))[:10] for row in histories or [] if row.get("date"))
        dates = sorted(value for value in dates if value)
        return {
            "date_range": {"start": dates[0] if dates else "", "end": dates[-1] if dates else ""},
            "modules": [
                {"module_id": "body", "record_count": len(data.get("body", []) or [])},
                {"module_id": "diet", "record_count": len(data.get("diet", []) or [])},
                {"module_id": "training", "record_count": len(data.get("training", []) or [])},
                {"module_id": "movement_history", "record_count": movement_count},
                {"module_id": "raw_entries", "record_count": len(data.get("raw_entries", []) or [])},
            ],
            "budget_mode": budget_mode,
        }

    @staticmethod
    def _record_repair_meta(meta: dict, before: dict, after: dict) -> None:
        before = before or {}; after = after or {}
        meta["repaired_validation_codes"] = ["REPAIRED_SELECTION"]
        meta["confidence_before"] = before.get("planner_confidence")
        meta["confidence_after"] = after.get("planner_confidence")
        meta["decision_changed"] = before.get("planning_decision") != after.get("planning_decision") if before else False
        changed = []
        for key in ("selected_window_id", "selected_modules", "selected_fields", "selected_movements", "selected_note_candidate_ids", "selected_candidate_record_ids", "training_detail_level", "movement_detail_level", "include_excluded_history", "excluded_history_usage", "use_progress_history_for_metrics", "missing_data_warning_codes", "planning_decision", "fallback_reason_codes", "planner_confidence"):
            if before.get(key) != after.get(key):
                changed.append(key)
        meta["changed_field_names"] = changed
        before_ids = set()
        after_ids = set()
        for key in ("selected_note_candidate_ids", "selected_candidate_record_ids"):
            before_ids.update(str(value) for value in before.get(key, []) or [])
            after_ids.update(str(value) for value in after.get(key, []) or [])
        meta["added_selected_ids"] = sorted(after_ids - before_ids)
        meta["removed_selected_ids"] = sorted(before_ids - after_ids)

    @staticmethod
    def _model_diag(result, extra=None) -> dict:
        data = dict(extra or {})
        data.update({"adapter": getattr(result, "adapter", ""), "model": getattr(result, "model", ""), "duration_ms": getattr(result, "duration_ms", 0), "output_chars": getattr(result, "output_chars", len(getattr(result, "raw_text", ""))), "response_keys": getattr(result, "response_keys", []), "message_keys": getattr(result, "message_keys", []), "finish_reason": getattr(result, "finish_reason", ""), "eval_count": getattr(result, "eval_count", 0), "prompt_eval_count": getattr(result, "prompt_eval_count", 0), "http_status": getattr(result, "http_status", 0), "response_bytes": getattr(result, "response_bytes", 0), "load_duration_ns": getattr(result, "load_duration_ns", 0), "prompt_eval_duration_ns": getattr(result, "prompt_eval_duration_ns", 0), "eval_duration_ns": getattr(result, "eval_duration_ns", 0), "truncated": getattr(result, "truncated", False)})
        return data
