"""Model planning: obtain a small, ID-only selection contract."""

from __future__ import annotations

import json
from .candidate_cards import CandidatePackage
from .intelligent_export_models import ContractError, SCHEMA_VERSION, SELECTION_SCHEMA_VERSION, ExportPlanDraft, ModelPlanningSelection, ModelSelectionExclusion, ModelSelectionFields, ModelSelectionModule, ModelSelectionMovement, selection_json_schema
from .local_model_adapter import PLANNING_MODEL_CONFIG, LocalModelAdapter

PROMPT_VERSION = "intelligent-export-prompts-v1"


def parse_json_object(raw_text: str) -> dict:
    value = json.loads(str(raw_text or "").strip())
    if not isinstance(value, dict):
        raise ContractError("model response must be a JSON object")
    return value


PLANNING_SYSTEM_PROMPT = """You are a strict Fitness Ledger export selector. Return only one JSON object matching the supplied selection schema. The application already resolved dates, target body parts, and explicitly named movements deterministically. Use only candidate IDs and fields supplied. EXPLICIT_TARGET and BODY_PART_TARGET directly cover the requested scope; CONTEXT supports it; GENERAL_FALLBACK is representative evidence only. When direct targets exist, retain at least one direct target and do not replace all targets with context. Select only the modules, fields, movements, notes and records needed for a useful export. Use progress history for metrics; excluded history is context_only. Do not output intent fields, dates, catalog IDs, paths, raw text, or prose. Set planning_decision=ready whenever a safe useful selection can be made; otherwise fallback_required with an allowed reason."""


class ExportPlanner:
    def __init__(self, adapter: LocalModelAdapter) -> None:
        self.adapter = adapter
        self.last_result = None
        self.last_payload = None

    def plan(self, request: str, scope, package: CandidatePackage) -> tuple[ModelPlanningSelection, object]:
        schema = selection_json_schema()
        payload = {
            "original_request": str(request or "")[:2000],
            "query_scope": scope.to_dict() if hasattr(scope, "to_dict") else {},
            "candidate_summary": {
                "windows": package.to_planning_prompt_dict()["windows"],
                "modules": package.to_planning_prompt_dict()["modules"],
                "movements": package.to_planning_prompt_dict()["movements"],
                "notes": [{"note_candidate_id": item.note_candidate_id, "date": item.date, "note_type": item.note_type, "movement_id": item.movement_id} for item in package.notes],
                "records": [{"candidate_record_id": item.candidate_record_id, "module_id": item.module_id, "date": item.date, "record_kind": item.record_kind, "flags": item.flags, "related_movement_ids": item.related_movement_ids} for item in package.candidate_records],
            },
            "allowed_window_ids": package.allowed_ids["window_ids"],
            "allowed_module_ids": package.allowed_modules,
            "allowed_field_ids_by_module": package.allowed_fields,
            "allowed_movement_ids": package.allowed_ids["movement_ids"],
            "allowed_note_candidate_ids": package.allowed_ids["note_candidate_ids"],
            "allowed_candidate_record_ids": package.allowed_ids["candidate_record_ids"],
            "budget": package.budget,
            "selection_schema_version": SCHEMA_VERSION,
            "prompt_version": PROMPT_VERSION,
        }
        self.last_payload = payload
        result = self.adapter.generate_json(system_prompt=PLANNING_SYSTEM_PROMPT, user_payload=payload, response_schema=schema, config=PLANNING_MODEL_CONFIG)
        self.last_result = result
        parsed = self.parse_selection(result.raw_text)
        self._validate_selection(parsed, package)
        self._validate_target_coverage(parsed, package)
        return parsed, result

    @staticmethod
    def _validate_selection(selection: ModelPlanningSelection, package: CandidatePackage) -> None:
        if selection.planning_decision == "fallback_required":
            return
        allowed = package.allowed_ids
        if selection.selected_window_id not in allowed["window_ids"]:
            raise ContractError("selected_window_id is not present in the candidate package")
        allowed_modules = set(package.allowed_modules) | {"movement_progress", "notes"}
        if any(item.module_id not in allowed_modules for item in selection.selected_modules):
            raise ContractError("selected_modules contains an unknown module ID")
        for item in selection.selected_fields:
            if item.module_id not in package.allowed_fields:
                raise ContractError("selected_fields contains an unknown module ID")
            if any(field != "Date" and field not in package.allowed_fields[item.module_id] for field in item.field_ids):
                raise ContractError("selected_fields contains an unknown field ID")
        if any(item.movement_id not in allowed["movement_ids"] for item in selection.selected_movements):
            raise ContractError("selected_movements contains an unknown movement ID")
        if any(item not in allowed["note_candidate_ids"] for item in selection.selected_note_candidate_ids):
            raise ContractError("selected_note_candidate_ids contains an unknown ID")
        if any(item not in allowed["candidate_record_ids"] for item in selection.selected_candidate_record_ids):
            raise ContractError("selected_candidate_record_ids contains an unknown ID")
        budget = package.budget
        if len(selection.selected_movements) > budget["movements"] or len(selection.selected_note_candidate_ids) > budget["notes"] or len(selection.selected_candidate_record_ids) > budget["records"]:
            raise ContractError("selection exceeds budget")

    @staticmethod
    def _validate_target_coverage(selection: ModelPlanningSelection, package: CandidatePackage) -> None:
        target_ids = set(package.target_scope.direct_target_ids) & set(package.allowed_ids.get("movement_ids", []))
        if not target_ids or not selection.selected_movements:
            return
        selected_ids = {item.movement_id for item in selection.selected_movements}
        if not selected_ids.intersection(target_ids):
            raise ContractError("selection does not cover a direct target movement", "TARGET_SCOPE_NOT_COVERED")

    @staticmethod
    def parse_selection(raw_text: str) -> ModelPlanningSelection:
        parsed = parse_json_object(raw_text)
        # Compatibility for the pre-MVP fake adapter contract. Ollama is
        # constrained to selection_json_schema; this path is only for old
        # callers/tests and immediately converts to the new selection.
        if "date_range" in parsed:
            old = ExportPlanDraft.from_dict(parsed)
            parsed = {
                "schema_version": SELECTION_SCHEMA_VERSION,
                "selected_window_id": old.date_range["window_id"],
                "selected_modules": [{"module_id": m, "priority": i + 1, "reason": old.inclusion_reasons.get(m, "")} for i, m in enumerate(old.selected_modules)],
                "selected_fields": [{"module_id": m, "field_ids": f, "reason": ""} for m, f in old.selected_fields.items()],
                "selected_movements": [{"movement_id": m, "detail_level": old.movement_detail_level, "priority": i + 1, "reason": old.inclusion_reasons.get(m, "")} for i, m in enumerate(old.selected_movements)],
                "selected_note_candidate_ids": old.notes_selection,
                "selected_candidate_record_ids": old.candidate_record_ids,
                "training_detail_level": old.training_detail_level,
                "movement_detail_level": old.movement_detail_level,
                "include_raw_entries": old.include_raw_entries,
                "include_excluded_history": old.include_excluded_history,
                "excluded_history_usage": old.excluded_history_usage,
                "use_progress_history_for_metrics": old.use_progress_history_for_metrics,
                "missing_data_warning_codes": [], "exclusion_decisions": [],
                "planner_confidence": old.planner_confidence,
                "planning_decision": "fallback_required" if old.planning_decision == "fallback_required" else "ready",
                "fallback_reason_codes": list(old.fallback_reason_codes),
            }
        return ModelPlanningSelection.from_dict(parsed)
