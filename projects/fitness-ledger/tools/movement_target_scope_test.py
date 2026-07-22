"""Anonymous tests for canonical target body-part scope resolution."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.candidate_cards import CandidateSummarizer
from fitness_ledger_core.data_catalog import DataCatalogBuilder, MovementResolver
from fitness_ledger_core.export_planner import ExportPlanner
from fitness_ledger_core.intelligent_export_models import ContractError, IntentSpec, ModelPlanningSelection, SELECTION_SCHEMA_VERSION
from fitness_ledger_core.movement_target_scope import MovementTargetScopeResolver, body_part_id_for_muscle_group
from fitness_ledger_core.shared_view_models import LedgerViewModels

from intelligent_export_core_test import fixture, intent


def main() -> None:
    assert [body_part_id_for_muscle_group(value) for value in ("Chest", "Back", "Shoulder", "Arms", "Core", "Legs")] == ["CHEST", "BACK", "SHOULDER", "ARMS", "CORE", "LEGS"]
    assert body_part_id_for_muscle_group("unknown") is None

    valid = IntentSpec.from_dict(intent())
    assert valid.target_body_parts == ["SHOULDER"]
    invalid = copy.deepcopy(intent())
    invalid["target_body_parts"] = ["chest"]
    try:
        IntentSpec.from_dict(invalid)
    except ContractError:
        pass
    else:
        raise AssertionError("lowercase body-part id was accepted")
    invalid = copy.deepcopy(intent())
    invalid["movement_mentions"] = [{"text": "Lateral Raise", "confidence": 0.9, "body_part": "SHOULDER"}]
    try:
        IntentSpec.from_dict(invalid)
    except ContractError:
        pass
    else:
        raise AssertionError("movement mention body_part was accepted")

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-target-scope-") as name:
        root = Path(name)
        tracker_file, dictionary_file = fixture(root)
        tracker = json.loads(tracker_file.read_text(encoding="utf-8"))
        dictionary = json.loads(dictionary_file.read_text(encoding="utf-8"))
        dictionary["movements"].extend([
            {"movement_id": "CHEST_006", "display_name": "Bench Press", "english_name": "Bench Press", "aliases": ["Bench Press"], "muscle_group": "Chest", "active": True},
            {"movement_id": "BACK_001", "display_name": "Row", "english_name": "Row", "aliases": ["Row"], "muscle_group": "Back", "active": True},
        ])
        tracker["movements"]["bench"] = {"movement_id": "CHEST_006", "history": [{"id": "bench-1", "movement_id": "CHEST_006", "date": "2026-07-15", "training_day": 3, "order": 2, "sets": [{"weight": 50, "reps": 8}], "notes": "", "exclude_from_progress": False}]}
        tracker["movements"]["row"] = {"movement_id": "BACK_001", "history": []}
        tracker_file.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
        dictionary_file.write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
        views = LedgerViewModels(tracker_file, dictionary_file)
        catalog = DataCatalogBuilder(views).build()

        body_part_intent = copy.deepcopy(intent())
        body_part_intent["movement_mentions"] = []
        body_part_intent["target_body_parts"] = ["CHEST"]
        package = CandidateSummarizer(catalog, MovementResolver(views)).build("分析胸部训练", IntentSpec.from_dict(body_part_intent), budget_mode="complete")
        assert "CHEST_006" in package.target_scope.expanded_direct_movement_ids
        assert package.movement_roles["CHEST_006"] == "BODY_PART_TARGET"
        assert "CHEST_006" in package.allowed_ids["movement_ids"]

        explicit = copy.deepcopy(body_part_intent)
        explicit["movement_mentions"] = [{"text": "Bench Press", "confidence": 0.99}]
        explicit_package = CandidateSummarizer(catalog, MovementResolver(views)).build("分析 Bench Press", IntentSpec.from_dict(explicit), budget_mode="complete")
        assert "CHEST_006" in explicit_package.target_scope.direct_movement_ids
        assert explicit_package.movement_roles["CHEST_006"] == "EXPLICIT_TARGET"

        mixed = copy.deepcopy(body_part_intent)
        mixed["target_body_parts"] = ["CHEST"]
        mixed_package = CandidateSummarizer(catalog, MovementResolver(views)).build("分析胸部训练", IntentSpec.from_dict(mixed))
        context_id = next((value for value, role in mixed_package.movement_roles.items() if role == "CONTEXT"), None)
        direct_id = next(value for value, role in mixed_package.movement_roles.items() if role in {"EXPLICIT_TARGET", "BODY_PART_TARGET"})
        assert context_id and direct_id
        selection_raw = {"schema_version": SELECTION_SCHEMA_VERSION, "selected_window_id": mixed_package.windows[0].window_id, "selected_modules": [{"module_id": mixed_package.allowed_modules[0], "reason": "context"}], "selected_fields": [], "selected_movements": [{"movement_id": context_id, "detail_level": "summary", "priority": 1, "reason": "context"}], "selected_note_candidate_ids": [], "selected_candidate_record_ids": [], "training_detail_level": "summary", "movement_detail_level": "summary", "include_raw_entries": False, "include_excluded_history": False, "excluded_history_usage": "none", "use_progress_history_for_metrics": True, "missing_data_warning_codes": [], "exclusion_decisions": [], "planner_confidence": 0.9, "planning_decision": "ready", "fallback_reason_codes": []}
        context_selection = ModelPlanningSelection.from_dict(selection_raw)
        try:
            ExportPlanner._validate_target_coverage(context_selection, mixed_package)
        except ContractError as exc:
            assert exc.code == "TARGET_SCOPE_NOT_COVERED"
        else:
            raise AssertionError("context-only selection bypassed target coverage")
        selection_raw["selected_movements"] = [{"movement_id": direct_id, "detail_level": "summary", "priority": 1, "reason": "direct"}]
        ExportPlanner._validate_target_coverage(ModelPlanningSelection.from_dict(selection_raw), mixed_package)

        no_target = copy.deepcopy(mixed)
        no_target["target_body_parts"] = []
        no_target["movement_mentions"] = []
        no_target_package = CandidateSummarizer(catalog, MovementResolver(views)).build("总结训练", IntentSpec.from_dict(no_target))
        ExportPlanner._validate_target_coverage(context_selection, no_target_package)

        unresolved = copy.deepcopy(body_part_intent)
        unresolved["target_body_parts"] = ["LEGS"]
        unresolved_package = CandidateSummarizer(catalog, MovementResolver(views)).build("分析腿部训练", IntentSpec.from_dict(unresolved))
        assert not unresolved_package.target_scope.expanded_direct_movement_ids
        assert "TARGET_BODY_PART_HAS_NO_DIRECT_MOVEMENT_DATA" in unresolved_package.target_scope.warnings
        assert all(value not in {"CHEST_006", "SHOULDER_001"} for value in unresolved_package.target_scope.direct_target_ids)

        fallback = copy.deepcopy(body_part_intent)
        fallback["target_body_parts"] = []
        fallback["movement_mentions"] = []
        fallback_package = CandidateSummarizer(catalog, MovementResolver(views)).build("总结训练", IntentSpec.from_dict(fallback))
        assert all(role == "GENERAL_FALLBACK" for role in fallback_package.movement_roles.values())

    print("FITNESS_LEDGER_MOVEMENT_TARGET_SCOPE_OK")


if __name__ == "__main__":
    main()
