"""Anonymous Core MVP acceptance tests for intelligent export."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.candidate_cards import BUDGETS, CandidateSummarizer
from fitness_ledger_core.data_catalog import DataCatalogBuilder, MovementResolver, resolve_windows
from fitness_ledger_core.export_plan_validator import ExportPlanValidator, PlanValidationError, validate_source_snapshot
from fitness_ledger_core.intelligent_export import IntelligentExportService
from fitness_ledger_core.intelligent_export_models import ContractError, ExportPlanDraft, IntentSpec, stable_hash
from fitness_ledger_core.local_model_adapter import FakeLocalModelAdapter, LocalModelError
from fitness_ledger_core.shared_view_models import LedgerViewModels


def fixture(root: Path) -> tuple[Path, Path]:
    tracker = {
        "version": 1,
        "daily_records": [
            {"id": "body-1", "Date": "2026-07-01", "Weight (kg)": 80, "Training": "肩", "Notes": "睡眠一般，左肩稳定性一般。"},
            {"id": "body-2", "Date": "2026-07-08", "Weight (kg)": 79.5, "Training": "肩", "Notes": "体重记录稳定。"},
            {"id": "body-3", "Date": "2026-07-15", "Weight (kg)": 79, "Training": "肩", "Notes": "整体状态正常。"},
        ],
        "diet_records": [
            {"id": "diet-1", "Date": "2026-07-01", "Calories (kcal)": 2100, "Protein (g)": 150, "Carbs (g)": 180, "Fat (g)": 60, "Notes": "训练前碳水较少。"},
            {"id": "diet-2", "Date": "2026-07-08", "Calories (kcal)": 2050, "Protein (g)": 155, "Carbs (g)": 160, "Fat (g)": 58, "Notes": "训练日饮食可执行。"},
        ],
        "training_sessions": [
            {"id": "training-1", "Date": "2026-07-01", "No.": 1, "Split": "肩", "Notes": "训练控制优先。"},
            {"id": "training-2", "Date": "2026-07-08", "No.": 2, "Split": "肩", "Notes": "整体输出稳定。"},
            {"id": "training-3", "Date": "2026-07-15", "No.": 3, "Split": "肩", "Notes": "测试被排除实例。"},
        ],
        "movements": {
            "shoulder": {"movement_id": "SHOULDER_001", "history": [
                {"id": "h-1", "movement_id": "SHOULDER_001", "date": "2026-07-01", "training_day": 1, "order": 1, "sets": [{"weight": 10, "reps": 12, "sets": 3}], "notes": "控制速度。", "exclude_from_progress": False, "raw": "private raw 1"},
                {"id": "h-2", "movement_id": "SHOULDER_001", "date": "2026-07-08", "training_day": 2, "order": 1, "sets": [{"weight": 12, "reps": 10, "sets": 3}], "notes": "肩部感觉良好。", "exclude_from_progress": False, "raw": "private raw 2"},
                {"id": "h-3", "movement_id": "SHOULDER_001", "date": "2026-07-15", "training_day": 3, "order": 1, "sets": [{"weight": 14, "reps": 8, "sets": 3}], "notes": "仅保留原始训练记录。", "exclude_from_progress": True, "raw": "private raw 3"},
            ]},
        },
        "raw_entries": [{"id": "raw-1", "date": "2026-07-01", "text": "完整私人原始输入不应进入模型。"}],
    }
    dictionary = {"version": 1, "movements": [{"movement_id": "SHOULDER_001", "display_name": "侧平举", "english_name": "Lateral Raise", "aliases": ["侧平举", "肩部侧平举"], "muscle_group": "Shoulder", "active": True}]}
    tracker_file, dictionary_file = root / "tracker.json", root / "movement_dictionary.json"
    tracker_file.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
    dictionary_file.write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
    return tracker_file, dictionary_file


def intent() -> dict:
    return {"schema_version": "fitness-ledger-intelligent-export-v1", "interpreted_goal": "比较肩部训练表现与饮食支持", "analysis_dimensions": ["movement_progress", "diet_macros", "training_notes"], "date_intent": {"kind": "relative", "days": 28, "anchor": "latest"}, "movement_mentions": [{"text": "侧平举", "confidence": 0.98, "body_part": "肩"}], "catalog_requirements": ["body", "diet", "training", "movement_history"], "preferred_detail": "detailed", "raw_entry_relevance": "none", "confidence": 0.95, "needs_fallback": False, "warnings": []}


def plan_for(views, include_excluded=True, selected_modules=None, invalid=False) -> dict:
    catalog = DataCatalogBuilder(views).build()
    parsed_intent = IntentSpec.from_dict(intent())
    package = CandidateSummarizer(catalog, MovementResolver(views)).build("比较肩部训练表现", parsed_intent)
    window = package.windows[0]
    records = [item.candidate_record_id for item in package.candidate_records]
    selected_modules = selected_modules or ["body", "diet", "training", "movement_history", "movement_progress", "notes"]
    date_range = {key: window.to_dict()[key] for key in ("window_id", "requested_start", "requested_end", "resolved_start", "resolved_end", "anchor")}
    return {"schema_version": "fitness-ledger-intelligent-export-v1", "interpreted_goal": "比较肩部训练表现与饮食支持", "analysis_dimensions": ["movement_progress"], "date_range": date_range, "selected_modules": ["unknown"] if invalid else selected_modules, "selected_fields": {module: ["Date"] for module in selected_modules if module in {"body", "diet", "training"}}, "selected_movements": ["SHOULDER_001"], "notes_selection": [item.note_candidate_id for item in package.notes[:3]], "candidate_record_ids": records, "training_detail_level": "detailed", "movement_detail_level": "detailed", "include_raw_entries": False, "include_excluded_history": include_excluded, "excluded_history_usage": "context_only" if include_excluded else "none", "use_progress_history_for_metrics": True, "inclusion_reasons": {"SHOULDER_001": "用户明确提到肩部动作"}, "exclusion_reasons": {}, "missing_data_warnings": [], "planner_confidence": 0.92, "needs_fallback": False, "priority": []}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-intelligent-export-") as name:
        root = Path(name)
        tracker_file, dictionary_file = fixture(root)
        views = LedgerViewModels(tracker_file, dictionary_file)
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (tracker_file, dictionary_file)]
        catalog = DataCatalogBuilder(views).build()
        assert catalog.movements[0].progress_history_count == 2
        assert catalog.movements[0].excluded_history_count == 1
        assert {item.note_type for item in catalog.notes} == {"daily", "diet", "training", "movement"}
        assert all(len(item.short_fragment) <= 120 for item in catalog.notes)
        assert all("完整私人" not in json.dumps(item.to_dict(), ensure_ascii=False) for item in catalog.candidate_records)

        good_plan = plan_for(views)
        adapter = FakeLocalModelAdapter([intent(), good_plan])
        result = IntelligentExportService(views, adapter).run("比较最近肩部训练、饮食和体重变化")
        assert result["status"] == "ready", result
        assert result["plan"]["source_snapshot_id"] == catalog.source_snapshot_id
        assert any(item["evidence_class"] == "context_only" for item in result["output"]["payload"]["movements"][0]["context_only"])
        assert all("完整私人" not in json.dumps(call["user_payload"], ensure_ascii=False) for call in adapter.calls)
        assert all("private raw" not in json.dumps(call["user_payload"], ensure_ascii=False) for call in adapter.calls)
        assert "完整私人" not in result["output"]["json"]
        assert len(adapter.calls) == 2

        # Planning validation and one successful Repair.
        repair_adapter = FakeLocalModelAdapter([intent(), plan_for(views, invalid=True), good_plan])
        repaired = IntelligentExportService(views, repair_adapter).run("比较肩部训练")
        assert repaired["status"] == "ready" and repaired["trace"]["repaired"] is True
        assert len(repair_adapter.calls) == 3

        # Repair failure becomes a safe fallback.
        failing = FakeLocalModelAdapter([intent(), plan_for(views, invalid=True), plan_for(views, invalid=True)])
        fallback = IntelligentExportService(views, failing).run("比较肩部训练")
        assert fallback["status"] == "fallback"

        # Model unavailable never touches files.
        unavailable = FakeLocalModelAdapter(errors=[LocalModelError("down", "MODEL_UNAVAILABLE")])
        assert IntelligentExportService(views, unavailable).run("模糊减脂复盘")["status"] == "fallback"

        # Unknown IDs, progress semantics, and snapshot changes are hard blockers.
        validator = ExportPlanValidator()
        package = CandidateSummarizer(catalog, MovementResolver(views)).build("比较肩部训练", IntentSpec.from_dict(intent()))
        bad = ExportPlanDraft.from_dict(plan_for(views, include_excluded=False, invalid=False))
        bad = ExportPlanDraft.from_dict({**bad.to_dict(), "candidate_record_ids": [item.candidate_record_id for item in package.candidate_records], "include_excluded_history": False, "excluded_history_usage": "none"})
        try:
            validator.validate(bad, package, "test")
        except PlanValidationError as exc:
            assert exc.code == "INVALID_PROGRESS_SEMANTICS"
        else:
            raise AssertionError("excluded history was accepted as progress data")
        original = tracker_file.read_bytes()
        tracker_file.write_bytes(original + b"\n")
        try:
            try:
                validate_source_snapshot(views, catalog.source_snapshot_id)
            except PlanValidationError as exc:
                assert exc.code == "SOURCE_CHANGED"
            else:
                raise AssertionError("source snapshot change was not detected")
        finally:
            tracker_file.write_bytes(original)
        assert before == [hashlib.sha256(path.read_bytes()).hexdigest() for path in (tracker_file, dictionary_file)]
    print("FITNESS_LEDGER_INTELLIGENT_EXPORT_CORE_OK")


if __name__ == "__main__":
    main()
