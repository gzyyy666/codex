"""Model planning: obtain a small, ID-only selection contract."""

from __future__ import annotations

from .candidate_cards import CandidatePackage
from .intelligent_export_models import SCHEMA_VERSION, ExportPlanDraft, ModelPlanningSelection, ModelSelectionExclusion, ModelSelectionFields, ModelSelectionModule, ModelSelectionMovement, selection_json_schema
from .intent_interpreter import PROMPT_VERSION, parse_json_object
from .local_model_adapter import PLANNING_MODEL_CONFIG, LocalModelAdapter


PLANNING_SYSTEM_PROMPT = """You are a strict Fitness Ledger export selector. Return only one JSON object with every required key. Set schema_version exactly to fitness-ledger-intelligent-export-v1. Choose only IDs and fields listed in the payload. Select at most 3 modules, 3 movements, 6 notes, and 8 records. Reasons are short (under 10 words). Do not output a plan, dates, catalog IDs, paths, estimates, raw text, or prose. Empty arrays are valid; still output every key with false/none defaults. Use progress history for metrics; excluded history is context_only only. Set needs_fallback=true if unsupported."""


class ExportPlanner:
    def __init__(self, adapter: LocalModelAdapter) -> None:
        self.adapter = adapter
        self.last_result = None
        self.last_payload = None

    def plan(self, request: str, intent, package: CandidatePackage) -> tuple[ModelPlanningSelection, object]:
        schema = selection_json_schema()
        payload = {
            "original_request": str(request or "")[:2000],
            "intent": {
                "interpreted_goal": intent.interpreted_goal,
                "analysis_dimensions": intent.analysis_dimensions,
                "date_intent": intent.date_intent.__dict__,
                "preferred_detail": intent.preferred_detail,
                "raw_entry_relevance": intent.raw_entry_relevance,
            },
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
        return parsed, result

    @staticmethod
    def parse_selection(raw_text: str) -> ModelPlanningSelection:
        parsed = parse_json_object(raw_text)
        # Compatibility for the pre-MVP fake adapter contract. Ollama is
        # constrained to selection_json_schema; this path is only for old
        # callers/tests and immediately converts to the new selection.
        if "date_range" in parsed:
            old = ExportPlanDraft.from_dict(parsed)
            parsed = {
                "schema_version": old.schema_version,
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
                "planner_confidence": old.planner_confidence, "needs_fallback": old.needs_fallback,
            }
        return ModelPlanningSelection.from_dict(parsed)
