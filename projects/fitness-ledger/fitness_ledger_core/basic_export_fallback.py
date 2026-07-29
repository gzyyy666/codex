"""Deterministic, model-free export selection used after planning failure."""

from __future__ import annotations

from .intelligent_export_models import ModelPlanningSelection, SELECTION_SCHEMA_VERSION


class BasicExportFallbackBuilder:
    def build(self, request, scope, package, reason: str = "PLANNING_FAILED") -> ModelPlanningSelection:
        if not package.windows:
            raise ValueError("NO_USABLE_DATA")
        text = str(request or "").lower()
        diet_terms = ("饮食", "低碳", "碳水", "热量", "蛋白质", "脂肪", "宏量", "营养", "吃什么", "食物")
        body_terms = ("体重", "减脂", "体脂", "体重变化", "身体状态")
        training_terms = ("训练", "训练表现", "训练日", "训练状态", "恢复", "力量")
        direct = set(package.target_scope.direct_movement_ids)
        body = set(package.target_scope.expanded_direct_movement_ids)
        has_movement_scope = bool(direct or body or getattr(scope, "explicit_movement_ids", []) or getattr(scope, "target_body_part_ids", []))
        requested_modules = set()
        if any(term in text for term in body_terms):
            requested_modules.add("body")
        if any(term in text for term in diet_terms):
            requested_modules.add("diet")
        if any(term in text for term in training_terms):
            requested_modules.add("training")
        if has_movement_scope:
            requested_modules.add("movement_history")
        if not requested_modules:
            requested_modules.update({"body", "diet"})
        ordered = [item.movement_id for item in package.movements]
        if direct:
            movement_ids = [item for item in ordered if item in direct]
        elif body:
            movement_ids = [item for item in ordered if item in body]
        elif has_movement_scope:
            movement_ids = [item for item in ordered if package.movement_roles.get(item) == "GENERAL_FALLBACK"]
        else:
            movement_ids = []
        movement_ids = movement_ids[: min(3, package.budget.get("movements", 3))]
        modules = [item.module_id for item in package.modules if item.module_id in requested_modules]
        if not modules:
            modules = ["body"]
        movement_set = set(movement_ids)
        record_ids = [
            item.candidate_record_id
            for item in package.candidate_records
            if item.module_id in set(modules)
            and not (item.module_id == "movement_history" and "excluded_from_progress" in item.flags)
            and (item.module_id != "movement_history" or set(item.related_movement_ids).intersection(movement_set))
        ][: min(8, package.budget.get("records", 8))]
        note_scopes = {"body": {"daily"}, "diet": {"diet"}, "training": {"training"}, "movement_history": {"movement"}}
        note_ids = [
            item.note_candidate_id
            for item in package.notes
            if item.scope in set().union(*(note_scopes.get(module, set()) for module in modules))
            and (item.scope != "movement" or not movement_set or item.movement_id in movement_set)
        ][: min(6, package.budget.get("notes", 6))]
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
