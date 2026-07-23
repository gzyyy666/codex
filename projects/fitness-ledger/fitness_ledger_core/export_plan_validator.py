"""Semantic validation for model-created export plans."""

from __future__ import annotations

from datetime import date

from .candidate_cards import CandidatePackage
from .data_catalog import source_snapshot
from .intelligent_export_models import ContractError, ExportPlanDraft, ValidatedExportPlan, stable_hash


ALLOWED_FIELDS = {
    "body": {"Date", "Weight (kg)", "Bowel Movement", "Training", "Cardio", "Notes"},
    "diet": {"Date", "Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)", "Food Summary", "Notes"},
    "training": {"Date", "Split", "Standardized Summary", "Notes"},
    "movement_history": {"date", "movement_id", "sets", "order", "notes", "exclude_from_progress"},
    "raw_entries": {"date", "id", "preview"},
    "movement_progress": {"date", "movement_id", "sets", "order", "notes"},
    "notes": {"date", "scope", "note_candidate_id"},
}


class PlanValidationError(ValueError):
    def __init__(self, message: str, code: str = "PLAN_INVALID") -> None:
        super().__init__(message)
        self.code = code


def validate_source_snapshot(views, expected_snapshot_id: str) -> None:
    actual = source_snapshot(views)["source_snapshot_id"]
    if actual != expected_snapshot_id:
        raise PlanValidationError("source data changed since catalog creation", "SOURCE_CHANGED")


class ExportPlanValidator:
    def validate(self, draft: ExportPlanDraft, package: CandidatePackage, request: str, trace_id: str = "", trim: bool = True) -> ValidatedExportPlan:
        allowed_modules = set(package.allowed_modules) | {"movement_progress", "notes"}
        selected_modules = list(dict.fromkeys(draft.selected_modules))
        if any(item not in allowed_modules for item in selected_modules):
            raise PlanValidationError("plan contains an unknown module ID", "UNKNOWN_MODULE_ID")
        if not selected_modules:
            raise PlanValidationError("plan selects no modules", "NO_MODULES")
        for module in selected_modules:
            if not draft.selected_fields.get(module):
                raise PlanValidationError(f"selected module has no explicit fields: {module}", "EMPTY_SELECTED_FIELDS")
        if {"movement_history", "movement_progress"}.intersection(selected_modules) and not draft.selected_movements:
            raise PlanValidationError("movement export requires explicit selected movements", "EMPTY_SELECTED_MOVEMENTS")
        if draft.include_raw_entries and not any(token in str(request or "").casefold() for token in ("原始记录", "原始输入", "原文追溯", "追溯原始", "raw record", "raw input", "raw trace")):
            raise PlanValidationError("raw entries require an explicit raw-trace request", "RAW_NOT_EXPLICIT")
        if draft.date_range.get("window_id") not in {item.window_id for item in package.windows}:
            raise PlanValidationError("plan contains an unknown window ID", "UNKNOWN_WINDOW_ID")
        window = next(item for item in package.windows if item.window_id == draft.date_range["window_id"])
        if draft.date_range.get("resolved_start") != window.resolved_start or draft.date_range.get("resolved_end") != window.resolved_end:
            raise PlanValidationError("plan resolved dates do not match the catalog window", "DATE_MISMATCH")
        try:
            if date.fromisoformat(window.resolved_start) > date.fromisoformat(window.resolved_end):
                raise PlanValidationError("resolved date range is invalid", "INVALID_DATE_RANGE")
        except ValueError as exc:
            raise PlanValidationError("resolved date range is invalid", "INVALID_DATE_RANGE") from exc
        for module, fields in draft.selected_fields.items():
            if module not in allowed_modules:
                raise PlanValidationError(f"unknown selected_fields module: {module}", "UNKNOWN_MODULE_ID")
            invalid_fields = set(fields) - ALLOWED_FIELDS.get(module, set())
            if invalid_fields:
                raise PlanValidationError(f"unknown fields in {module}: {', '.join(sorted(invalid_fields))}", "UNKNOWN_FIELD_ID")
            if module not in selected_modules and fields:
                raise PlanValidationError(f"fields selected for unselected module: {module}", "FIELD_MODULE_MISMATCH")
        movement_ids = set(package.allowed_ids["movement_ids"])
        if any(item not in movement_ids for item in draft.selected_movements):
            raise PlanValidationError("plan contains an unknown movement ID", "UNKNOWN_MOVEMENT_ID")
        note_ids = set(package.allowed_ids["note_candidate_ids"])
        if any(item not in note_ids for item in draft.notes_selection):
            raise PlanValidationError("plan contains an unknown Note candidate ID", "UNKNOWN_NOTE_ID")
        record_ids = set(package.allowed_ids["candidate_record_ids"])
        if any(item not in record_ids for item in draft.candidate_record_ids):
            raise PlanValidationError("plan contains an unknown candidate record ID", "UNKNOWN_RECORD_ID")
        if draft.include_excluded_history and draft.excluded_history_usage != "context_only":
            raise PlanValidationError("excluded history must be context_only", "INVALID_PROGRESS_SEMANTICS")
        if "movement_progress" in selected_modules and not draft.use_progress_history_for_metrics:
            raise PlanValidationError("movement progress metrics must use progress history", "INVALID_PROGRESS_SEMANTICS")
        selected_records = [item for item in package.candidate_records if item.candidate_record_id in draft.candidate_record_ids]
        excluded_selected = [item for item in selected_records if "excluded_from_progress" in item.flags]
        if excluded_selected and not draft.include_excluded_history:
            raise PlanValidationError("excluded history requires explicit context_only selection", "INVALID_PROGRESS_SEMANTICS")
        if excluded_selected and draft.excluded_history_usage != "context_only":
            raise PlanValidationError("excluded history cannot be progress evidence", "INVALID_PROGRESS_SEMANTICS")
        budget = package.budget
        trimmed = False
        selected_movements = list(draft.selected_movements)
        notes_selection = list(draft.notes_selection)
        candidate_record_ids = list(draft.candidate_record_ids)
        if len(selected_movements) > budget["movements"] or len(notes_selection) > budget["notes"] or len(candidate_record_ids) > budget["records"]:
            overshoot = max(len(selected_movements) / max(1, budget["movements"]), len(notes_selection) / max(1, budget["notes"]), len(candidate_record_ids) / max(1, budget["records"]))
            if not trim or overshoot > 1.25:
                raise PlanValidationError("plan exceeds budget", "PLAN_OVER_BUDGET")
            selected_movements = selected_movements[: budget["movements"]]
            notes_selection = notes_selection[: budget["notes"]]
            candidate_record_ids = candidate_record_ids[: budget["records"]]
            trimmed = True
        if draft.include_raw_entries and budget["raw"] <= 0:
            raise PlanValidationError("raw entries are not permitted by this budget", "PLAN_OVER_BUDGET")
        estimated_count = len(candidate_record_ids) + len(notes_selection)
        estimated_size = min(budget["output_bytes"], 800 + estimated_count * 180 + len(selected_movements) * 450)
        plan_data = {
            "request": request,
            "catalog": package.catalog_id,
            "window": window.window_id,
            "modules": selected_modules,
            "fields": draft.selected_fields,
            "movements": selected_movements,
            "notes": notes_selection,
            "records": candidate_record_ids,
        }
        return ValidatedExportPlan(
            plan_id=f"plan:{stable_hash(plan_data)[:24]}",
            catalog_id=package.catalog_id,
            source_snapshot_id=package.source_snapshot_id,
            original_request=str(request or "")[:2000],
            interpreted_goal=draft.interpreted_goal,
            analysis_dimensions=draft.analysis_dimensions,
            date_range=window.to_dict(),
            selected_modules=selected_modules,
            selected_fields=draft.selected_fields,
            selected_movements=selected_movements,
            notes_selection=notes_selection,
            candidate_record_ids=candidate_record_ids,
            training_detail_level=draft.training_detail_level,
            movement_detail_level=draft.movement_detail_level,
            include_raw_entries=draft.include_raw_entries,
            include_excluded_history=draft.include_excluded_history,
            excluded_history_usage=draft.excluded_history_usage,
            use_progress_history_for_metrics=True if "movement_progress" in selected_modules else draft.use_progress_history_for_metrics,
            inclusion_reasons=draft.inclusion_reasons,
            exclusion_reasons=draft.exclusion_reasons,
            missing_data_warnings=list(dict.fromkeys(window.missing_data_warnings + draft.missing_data_warnings)),
            estimated_record_count=estimated_count,
            estimated_output_size=estimated_size,
            planner_confidence=draft.planner_confidence,
            planning_decision=draft.planning_decision,
            fallback_reason_codes=list(draft.fallback_reason_codes),
            model_trace_id=trace_id,
            trimmed=trimmed,
        )
