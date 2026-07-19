"""Selection contract and deterministic assembler checks on anonymous data."""
from __future__ import annotations
import tempfile, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fitness_ledger_core.candidate_cards import CandidateSummarizer
from fitness_ledger_core.data_catalog import DataCatalogBuilder, MovementResolver
from fitness_ledger_core.export_plan_assembler import ExportPlanAssembler
from fitness_ledger_core.intelligent_export_models import ContractError, IntentSpec, ModelPlanningSelection, selection_json_schema
from fitness_ledger_core.shared_view_models import LedgerViewModels
from intelligent_export_core_test import fixture, intent

def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-selection-") as name:
        tracker, dictionary = fixture(Path(name)); views = LedgerViewModels(tracker, dictionary)
        catalog = DataCatalogBuilder(views).build(); parsed_intent = IntentSpec.from_dict(intent())
        package = CandidateSummarizer(catalog, MovementResolver(views)).build("shoulder progress", parsed_intent, "concise")
        window = package.windows[0].window_id
        raw = {"schema_version": "fitness-ledger-intelligent-export-v1", "selected_window_id": window, "selected_modules": [{"module_id": "body", "priority": 1, "reason": "weight"}], "selected_fields": [], "selected_movements": [], "selected_note_candidate_ids": [], "selected_candidate_record_ids": [], "training_detail_level": "summary", "movement_detail_level": "summary", "include_raw_entries": False, "include_excluded_history": False, "excluded_history_usage": "none", "use_progress_history_for_metrics": True, "missing_data_warning_codes": [], "exclusion_decisions": [], "planner_confidence": 0.8, "needs_fallback": False}
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
    print("FITNESS_LEDGER_INTELLIGENT_EXPORT_SELECTION_OK")

if __name__ == "__main__": main()
