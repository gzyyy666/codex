"""Deterministic conversion from model selection to the formal draft contract."""

from __future__ import annotations

from .candidate_cards import CandidatePackage
from .export_plan_validator import ALLOWED_FIELDS
from .intelligent_export_models import ContractError, ExportPlanDraft, ModelPlanningSelection


WARNING_TEXT = {
    "REQUEST_OUTSIDE_DATA_RANGE": "Requested range extends beyond available data.",
    "NO_MOVEMENT_MATCH": "No confident movement candidate was available.",
    "LOW_CONFIDENCE": "Planner confidence is low.",
    "BODY_COVERAGE_INCOMPLETE": "Body coverage is incomplete in the selected range.",
    "DIET_COVERAGE_INCOMPLETE": "Diet coverage is incomplete in the selected range.",
    "TRAINING_COVERAGE_INCOMPLETE": "Training coverage is incomplete in the selected range.",
    "RAW_NOT_REQUESTED": "Raw entry preview was not requested.",
}
DEFAULT_FIELDS = {
    "body": ["Date", "Weight (kg)", "Training", "Notes"],
    "diet": ["Date", "Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)", "Notes"],
    "training": ["Date", "Split", "Standardized Summary", "Notes"],
    "movement_history": ["date", "movement_id", "sets", "order", "notes", "exclude_from_progress"],
    "movement_progress": ["date", "movement_id", "sets", "order", "notes"],
    "notes": ["date", "scope", "note_candidate_id"],
    "raw_entries": ["date", "id", "preview"],
}


class ExportPlanAssembler:
    def __init__(self, package: CandidatePackage) -> None:
        self.package = package

    def assemble(self, selection: ModelPlanningSelection, request: str, intent, trace_id: str = "") -> ExportPlanDraft:
        window = next((item for item in self.package.windows if item.window_id == selection.selected_window_id), None)
        if window is None:
            raise ContractError("selected_window_id is not present in the candidate package")
        modules = list(dict.fromkeys(item.module_id for item in sorted(selection.selected_modules, key=lambda x: (x.priority, x.module_id))))
        fields: dict[str, list[str]] = {}
        for item in selection.selected_fields:
            if item.module_id in fields:
                fields[item.module_id] = list(dict.fromkeys(fields[item.module_id] + item.field_ids))
            else:
                fields[item.module_id] = list(dict.fromkeys(item.field_ids))
        for module in modules:
            if module not in fields:
                fields[module] = list(DEFAULT_FIELDS.get(module, sorted(ALLOWED_FIELDS.get(module, set()))))
        movements = [item.movement_id for item in sorted(selection.selected_movements, key=lambda x: (x.priority, x.movement_id))]
        inclusion = {}
        for item in selection.selected_modules:
            inclusion.setdefault(item.module_id, item.reason)
        for item in selection.selected_movements:
            inclusion.setdefault(item.movement_id, item.reason)
        exclusions = {item.candidate_id: item.reason for item in selection.exclusion_decisions}
        warnings = [WARNING_TEXT.get(code, f"Planner warning: {code}") for code in dict.fromkeys(selection.missing_data_warning_codes)]
        if selection.planner_confidence < 0.5 and "LOW_CONFIDENCE" not in selection.missing_data_warning_codes:
            warnings.append(WARNING_TEXT["LOW_CONFIDENCE"])
        progress = True if "movement_progress" in modules else selection.use_progress_history_for_metrics
        return ExportPlanDraft(
            interpreted_goal=intent.interpreted_goal,
            analysis_dimensions=list(intent.analysis_dimensions),
            date_range=window.to_dict(),
            selected_modules=modules,
            selected_fields=fields,
            selected_movements=movements,
            notes_selection=list(selection.selected_note_candidate_ids),
            candidate_record_ids=list(selection.selected_candidate_record_ids),
            training_detail_level=selection.training_detail_level,
            movement_detail_level=selection.movement_detail_level,
            include_raw_entries=selection.include_raw_entries,
            include_excluded_history=selection.include_excluded_history,
            excluded_history_usage=selection.excluded_history_usage,
            use_progress_history_for_metrics=progress,
            inclusion_reasons=inclusion,
            exclusion_reasons=exclusions,
            missing_data_warnings=warnings,
            planner_confidence=selection.planner_confidence,
            needs_fallback=selection.needs_fallback,
            priority=modules + movements,
        )
