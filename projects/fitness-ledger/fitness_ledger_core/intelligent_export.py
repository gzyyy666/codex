"""Read-only intelligent export orchestration and deterministic execution."""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from dataclasses import asdict

from .candidate_cards import BUDGETS, CandidatePackage, CandidateSummarizer
from .data_catalog import DataCatalogBuilder, MovementResolver, source_snapshot
from .export_plan_validator import ExportPlanValidator, PlanValidationError, validate_source_snapshot
from .export_planner import ExportPlanner
from .export_plan_assembler import ExportPlanAssembler
from .intelligent_export_models import (
    ContractError,
    ExportPlanDraft,
    ModelPlanningSelection,
    IntentSpec,
    ManualFallbackResult,
    PlanExplanation,
    TraceRecord,
    ValidatedExportPlan,
    stable_hash,
)
from .intent_interpreter import IntentInterpreter, parse_json_object, INTENT_SYSTEM_PROMPT, PROMPT_VERSION
from .local_model_adapter import (
    INTENT_MODEL_CONFIG,
    REPAIR_MODEL_CONFIG,
    LocalModelAdapter,
    LocalModelError,
)
from .shared_view_models import history_in_progress, movement_in_progress
from .intelligent_export_models import intent_json_schema, selection_json_schema


REPAIR_SYSTEM_PROMPT = """Repair only the Fitness Ledger model selection JSON. Return exactly one selection object matching the supplied schema. Use only allowed IDs and fields; do not output a full plan, dates, catalog IDs, paths, estimates, raw text, or prose. Excluded history is context_only and progress metrics must use valid progress history. Set needs_fallback=true when it cannot be repaired."""
INTENT_REPAIR_SYSTEM_PROMPT = """Repair only the Fitness Ledger intent JSON. Return exactly one object matching the supplied intent schema. Do not output an export plan, catalog contents, raw entries, paths, or prose."""


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
        return {"payload": payload, "json": json.dumps(payload, ensure_ascii=False, indent=2), "markdown": self._markdown(payload, plan, explanation)}

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
            catalog = self.catalog_builder.build()
            diagnostics = {"prompt_version": PROMPT_VERSION, "schema_version": "fitness-ledger-intelligent-export-v1", "candidate_counts": {}, "stages": {}}
            catalog_summary = {"date_range": catalog.date_range, "modules": [{"module_id": item.module_id, "record_count": item.record_count} for item in catalog.modules], "budget_mode": budget_mode}
            repair_used = False
            intent_interpreter = IntentInterpreter(self.adapter)
            try:
                intent, intent_result = intent_interpreter.interpret(request, catalog_summary)
                diagnostics["stages"]["intent"] = self._model_diag(intent_result, {"payload_chars": len(json.dumps(catalog_summary, ensure_ascii=False)), "schema_chars": len(json.dumps(intent_json_schema(), ensure_ascii=False))})
            except Exception as exc:
                try:
                    repair_used = True
                    repair_result = self.adapter.generate_json(system_prompt=INTENT_REPAIR_SYSTEM_PROMPT, user_payload={"invalid_output": "intent unavailable", "validation_error": {"code": getattr(exc, "code", "INTENT_INVALID"), "message": str(exc)[:240]}, "intent_schema": intent_json_schema()}, response_schema=intent_json_schema(), config=REPAIR_MODEL_CONFIG)
                    intent = IntentSpec.from_dict(parse_json_object(repair_result.raw_text)); intent_result = repair_result
                except Exception as repair_error:
                    return self._fallback(request, getattr(repair_error, "code", "MODEL_REPAIR_FAILED"), trace_id, started, catalog)
            if self._expired(started):
                return self._fallback(request, "TASK_TIMEOUT", trace_id, started, catalog)
            try:
                package = CandidateSummarizer(catalog, MovementResolver(self.views)).build(request, intent, budget_mode)
                diagnostics["candidate_counts"] = {"windows": len(package.windows), "modules": len(package.modules), "movements": len(package.movements), "notes": len(package.notes), "records": len(package.candidate_records), "allowed_ids": {key: len(value) for key, value in package.allowed_ids.items()}}
            except Exception as exc:
                return self._fallback(request, getattr(exc, "code", "CATALOG_INVALID"), trace_id, started, catalog, intent)
            planner = ExportPlanner(self.adapter)
            assembler = ExportPlanAssembler(package)
            try:
                selection, planning_result = planner.plan(request, intent, package)
                draft = assembler.assemble(selection, request, intent, trace_id)
                diagnostics["stages"]["planning"] = self._model_diag(planning_result, {"payload_chars": len(json.dumps(planner.last_payload or {}, ensure_ascii=False)), "schema_chars": len(json.dumps(selection_json_schema(), ensure_ascii=False))})
                if selection.needs_fallback:
                    return self._fallback(request, "LOW_CONFIDENCE", trace_id, started, catalog, intent)
            except Exception as exc:
                if repair_used:
                    return self._fallback(request, getattr(exc, "code", "MODEL_SELECTION_INVALID"), trace_id, started, catalog, intent)
                try:
                    repair_used = True
                    repair_result = self.adapter.generate_json(system_prompt=REPAIR_SYSTEM_PROMPT, user_payload={"invalid_selection": "selection parse failed", "validation_error": {"code": getattr(exc, "code", "PLANNING_INVALID"), "message": str(exc)[:240]}, "allowed_window_ids": package.allowed_ids["window_ids"], "allowed_module_ids": package.allowed_modules, "allowed_field_ids_by_module": package.allowed_fields, "allowed_movement_ids": package.allowed_ids["movement_ids"], "allowed_note_candidate_ids": package.allowed_ids["note_candidate_ids"], "allowed_candidate_record_ids": package.allowed_ids["candidate_record_ids"], "selection_schema": selection_json_schema()}, response_schema=selection_json_schema(), config=REPAIR_MODEL_CONFIG)
                    selection = planner.parse_selection(repair_result.raw_text); draft = assembler.assemble(selection, request, intent, trace_id)
                    diagnostics["stages"]["repair"] = self._model_diag(repair_result, {"schema_chars": len(json.dumps(selection_json_schema(), ensure_ascii=False))})
                except Exception as repair_error:
                    return self._fallback(request, getattr(repair_error, "code", "MODEL_REPAIR_FAILED"), trace_id, started, catalog, intent)
            repaired = repair_used
            try:
                plan = self.validator.validate(draft, package, request, trace_id)
            except PlanValidationError as first_error:
                if repair_used or self._expired(started):
                    return self._fallback(request, first_error.code if repair_used else "TASK_TIMEOUT", trace_id, started, catalog, intent)
                repaired = True
                try:
                    repair_result = self.adapter.generate_json(system_prompt=REPAIR_SYSTEM_PROMPT, user_payload={"invalid_selection": selection.to_dict(), "validation_error": {"code": first_error.code, "message": str(first_error)[:240]}, "allowed_window_ids": package.allowed_ids["window_ids"], "allowed_module_ids": package.allowed_modules, "allowed_field_ids_by_module": package.allowed_fields, "allowed_movement_ids": package.allowed_ids["movement_ids"], "allowed_note_candidate_ids": package.allowed_ids["note_candidate_ids"], "allowed_candidate_record_ids": package.allowed_ids["candidate_record_ids"], "selection_schema": selection_json_schema()}, response_schema=selection_json_schema(), config=REPAIR_MODEL_CONFIG)
                    selection = planner.parse_selection(repair_result.raw_text); draft = assembler.assemble(selection, request, intent, trace_id); plan = self.validator.validate(draft, package, request, trace_id, trim=False)
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
            return {"status": "ready", "intent": intent.to_dict(), "catalog": catalog.to_prompt_dict(), "candidate_package": package.to_prompt_dict(), "selection": selection.to_dict(), "plan": plan.to_dict(), "explanation": explanation.to_dict(), "output": output, "trace": trace.to_dict(), "diagnostics": diagnostics}
        finally:
            self._task_slots.release()

    def _fallback(self, request: str, reason: str, trace_id: str, started: float, catalog=None, intent=None) -> dict:
        dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", str(request or ""))
        explicit = {"start": dates[0], "end": dates[-1]} if dates else {}
        modules = [item for item in ("body", "diet", "training", "movement_history") if any(word in str(request).lower() for word in {item, {"body": "体重", "diet": "饮食", "training": "训练", "movement_history": "动作"}.get(item, "")})]
        result = ManualFallbackResult(True, reason, explicit, {"days": 14, **explicit, "modules": modules}, ["模型结果不可用，未自动猜测未明确的范围或动作。"], trace_id)
        return {"status": "fallback", "fallback": result.to_dict(), "trace": {"trace_id": trace_id, "error_code": reason, "duration_ms": int((time.monotonic() - started) * 1000), "fallback": True}}

    def _expired(self, started: float) -> bool:
        return time.monotonic() - started > self.overall_timeout

    @staticmethod
    def _model_diag(result, extra=None) -> dict:
        data = dict(extra or {})
        data.update({"adapter": getattr(result, "adapter", ""), "model": getattr(result, "model", ""), "duration_ms": getattr(result, "duration_ms", 0), "output_chars": getattr(result, "output_chars", len(getattr(result, "raw_text", ""))), "response_keys": getattr(result, "response_keys", []), "message_keys": getattr(result, "message_keys", []), "finish_reason": getattr(result, "finish_reason", ""), "eval_count": getattr(result, "eval_count", 0), "prompt_eval_count": getattr(result, "prompt_eval_count", 0), "http_status": getattr(result, "http_status", 0), "response_bytes": getattr(result, "response_bytes", 0), "load_duration_ns": getattr(result, "load_duration_ns", 0), "prompt_eval_duration_ns": getattr(result, "prompt_eval_duration_ns", 0), "eval_duration_ns": getattr(result, "eval_duration_ns", 0), "truncated": getattr(result, "truncated", False)})
        return data
