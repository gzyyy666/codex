"""Deterministic, model-free export selection used after planning failure."""

from __future__ import annotations

from .intelligent_export_models import ModelPlanningSelection, SELECTION_SCHEMA_VERSION


class BasicExportFallbackBuilder:
    def build(self, request, scope, package, reason: str = "PLANNING_FAILED") -> ModelPlanningSelection:
        if not package.windows:
            raise ValueError("NO_USABLE_DATA")
        direct = set(package.target_scope.direct_movement_ids)
        body = set(package.target_scope.expanded_direct_movement_ids)
        ordered = [item.movement_id for item in package.movements]
        if direct:
            movement_ids = [item for item in ordered if item in direct]
        elif body:
            movement_ids = [item for item in ordered if item in body]
        else:
            movement_ids = [item for item in ordered if package.movement_roles.get(item) == "GENERAL_FALLBACK"]
        movement_ids = movement_ids[: min(3, package.budget.get("movements", 3))]
        record_ids = [item.candidate_record_id for item in package.candidate_records][: min(8, package.budget.get("records", 8))]
        note_ids = [item.note_candidate_id for item in package.notes][: min(6, package.budget.get("notes", 6))]
        modules = [item.module_id for item in package.modules if item.module_id in {"body", "diet", "training", "movement_history"}]
        if not modules:
            modules = ["training", "movement_history"]
        fields = [{"module_id": module, "field_ids": sorted(package.allowed_fields.get(module, [])), "reason": "basic deterministic evidence"} for module in modules]
        allowed_reasons = {"NO_VALID_WINDOW", "NO_RELEVANT_MODULES", "NO_USABLE_CANDIDATES", "UNRESOLVED_REQUIRED_MOVEMENT", "REQUEST_NOT_UNDERSTOOD", "NO_SAFE_PLAN"}
        fallback_reason = reason if reason in allowed_reasons else "NO_SAFE_PLAN"
        return ModelPlanningSelection.from_dict({
            "schema_version": SELECTION_SCHEMA_VERSION,
            "selected_window_id": package.windows[0].window_id,
            "selected_modules": [{"module_id": module, "priority": index + 1, "reason": "basic deterministic evidence"} for index, module in enumerate(modules)],
            "selected_fields": fields,
            "selected_movements": [{"movement_id": movement_id, "detail_level": "summary", "priority": index + 1, "reason": "direct target" if movement_id in direct or movement_id in body else "representative fallback"} for index, movement_id in enumerate(movement_ids)],
            "selected_note_candidate_ids": note_ids,
            "selected_candidate_record_ids": record_ids,
            "training_detail_level": "summary",
            "movement_detail_level": "summary",
            "include_raw_entries": False,
            "include_excluded_history": False,
            "excluded_history_usage": "none",
            "use_progress_history_for_metrics": True,
            "missing_data_warning_codes": list(package.target_scope.warnings),
            "exclusion_decisions": [],
            "planner_confidence": 0.55,
            "planning_decision": "ready",
            "fallback_reason_codes": [],
        })
