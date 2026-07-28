"""Selection contract and deterministic assembler checks on anonymous data."""
from __future__ import annotations
import tempfile, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fitness_ledger_core.candidate_cards import CandidateSummarizer
from fitness_ledger_core.data_catalog import DataCatalogBuilder, MovementResolver
from fitness_ledger_core.export_plan_assembler import ExportPlanAssembler
from fitness_ledger_core.intelligent_export import IntelligentExportService
from fitness_ledger_core.intelligent_export_errors import error_info
from fitness_ledger_core.intelligent_export_models import ContractError, IntentSpec, ModelPlanningSelection, SELECTION_SCHEMA_VERSION, selection_json_schema
from fitness_ledger_core.local_model_adapter import FakeLocalModelAdapter
from fitness_ledger_core.shared_view_models import LedgerViewModels
from intelligent_export_core_test import fixture, intent

def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-selection-") as name:
        tracker, dictionary = fixture(Path(name)); views = LedgerViewModels(tracker, dictionary)
        catalog = DataCatalogBuilder(views).build(); parsed_intent = IntentSpec.from_dict(intent())
        package = CandidateSummarizer(catalog, MovementResolver(views)).build("shoulder progress", parsed_intent, "concise")
        window = package.windows[0].window_id
        raw = {"schema_version": SELECTION_SCHEMA_VERSION, "selected_window_id": window, "selected_modules": [{"module_id": "body", "priority": 1, "reason": "weight"}], "selected_fields": [], "selected_movements": [], "selected_note_candidate_ids": [], "selected_candidate_record_ids": [], "training_detail_level": "summary", "movement_detail_level": "summary", "include_raw_entries": False, "include_excluded_history": False, "excluded_history_usage": "none", "use_progress_history_for_metrics": True, "missing_data_warning_codes": ["DIET_COVERAGE_INCOMPLETE"], "exclusion_decisions": [], "planner_confidence": 0.8, "planning_decision": "ready", "fallback_reason_codes": []}
        selection = ModelPlanningSelection.from_dict(raw)
        draft = ExportPlanAssembler(package).assemble(selection, "shoulder progress", parsed_intent)
        assert draft.date_range["window_id"] == window and draft.selected_fields["body"]
        assert "plan_id" not in selection.to_dict() and "catalog_id" not in selection.to_dict()
        assert "selected_modules" in selection_json_schema()["required"]
        try:
            ModelPlanningSelection.from_dict({**raw, "catalog_id": "forbidden"})
        except ContractError:
            pass
        else:
            raise AssertionError("system field accepted by selection contract")
        try:
            ModelPlanningSelection.from_dict({**raw, "needs_fallback": False})
        except ContractError:
            pass
        else:
            raise AssertionError("legacy needs_fallback accepted by new selection contract")
        for bad in ({**raw, "planning_decision": "ready", "fallback_reason_codes": ["NO_SAFE_PLAN"]}, {**raw, "planning_decision": "fallback_required", "fallback_reason_codes": []}, {**raw, "selected_modules": []}, {**raw, "selected_window_id": ""}, {**raw, "missing_data_warning_codes": ["NO_SAFE_PLAN"]}):
            try:
                ModelPlanningSelection.from_dict(bad)
            except ContractError:
                pass
            else:
                raise AssertionError("invalid planning selection accepted")
        def service_selection(confidence=0.8, decision="ready", reasons=None, warnings=None):
            return {**raw, "planner_confidence": confidence, "planning_decision": decision, "fallback_reason_codes": list(reasons or []), "missing_data_warning_codes": list(warnings or [])}
        # Warnings are non-blocking; a ready, useful plan reaches the assembler and executor.
        ready = IntelligentExportService(views, FakeLocalModelAdapter([service_selection(warnings=["DIET_COVERAGE_INCOMPLETE"])])).run("体重和饮食趋势")
        assert ready["status"] == "ready" and ready["selection"]["planning_decision"] == "ready"
        # Confidence is a deterministic gate, not a warning-to-fallback conversion.
        low = IntelligentExportService(views, FakeLocalModelAdapter([service_selection(confidence=0.49)])).run("体重趋势")
        assert low["status"] == "basic_fallback_used"
        blocked = IntelligentExportService(views, FakeLocalModelAdapter([service_selection(decision="fallback_required", reasons=["NO_USABLE_CANDIDATES"], confidence=0.99)])).run("未知请求")
        assert blocked["status"] == "basic_fallback_used"
        assert "当前候选" in error_info("PLANNER_FALLBACK_REQUIRED")["user"]
        # A contradictory first response is repaired once; the repair cannot add an unknown candidate.
        contradictory = {**service_selection(), "planning_decision": "ready", "fallback_reason_codes": ["NO_SAFE_PLAN"]}
        repaired = IntelligentExportService(views, FakeLocalModelAdapter([contradictory, service_selection()])).run("体重趋势")
        assert repaired["status"] == "ready" and repaired["trace"]["repaired"] is True
        unknown_repair = {**service_selection(), "selected_candidate_record_ids": ["record:not-supplied"]}
        rejected = IntelligentExportService(views, FakeLocalModelAdapter([contradictory, unknown_repair])).run("体重趋势")
        assert rejected["status"] == "basic_fallback_used"
    print("FITNESS_LEDGER_INTELLIGENT_EXPORT_SELECTION_OK")

if __name__ == "__main__": main()
