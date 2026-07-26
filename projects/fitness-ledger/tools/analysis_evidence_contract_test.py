"""Anonymous tests for Evidence Requirement and Claim Validation contracts."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_evidence import (  # noqa: E402
    TASK_REGISTRY,
    EvidenceRequirementCompiler,
    compile_and_evaluate,
    task_registry,
)
from fitness_ledger_core.analysis_foundation import AnalysisRequirementSpecV1, RequirementMapper  # noqa: E402
from fitness_ledger_core.data_catalog import DataCatalogBuilder  # noqa: E402
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from intelligent_export_core_test import fixture  # noqa: E402


def requirement(goal: str, capabilities: list[str], derived: list[str] | None = None) -> AnalysisRequirementSpecV1:
    return AnalysisRequirementSpecV1.from_dict(
        {
            "schema_version": "fitness-ledger-analysis-requirement-v1",
            "analysis_goal": goal,
            "questions_to_answer": [goal],
            "required_capabilities": [{"capability_id": item, "reason": "用户明确提出该只读分析目标"} for item in capabilities],
            "optional_capabilities": [],
            "preferred_time_window": {"kind": "recent", "label": "最近"},
            "derived_metrics": [{"name": item, "reason": "模型提出的未执行指标"} for item in (derived or [])],
            "missing_information": [],
            "clarifications": [],
            "evidence": [],
            "gpt_prompt_outline": [],
        },
        user_goal=goal,
    )


def environment():
    temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-evidence-")
    tracker, dictionary = fixture(Path(temp.name))
    views = LedgerViewModels(tracker, dictionary)
    catalog = DataCatalogBuilder(views).build()
    return temp, views, catalog


def test_task_registry_is_registered_and_non_executable() -> None:
    public = task_registry()
    assert public
    assert set(public) == set(TASK_REGISTRY)
    encoded = json.dumps(public, ensure_ascii=False)
    assert "export_plan" not in encoded
    assert "record_id" not in encoded


def test_body_profile_distinguishes_candidate_from_materialized() -> None:
    temp, views, catalog = environment()
    try:
        goal = "分析最近体重变化"
        facts = __import__("fitness_ledger_core.intent_compiler", fromlist=["IntentCompiler"]).IntentCompiler(views).prepare(goal, catalog)
        _intent, _package, draft = __import__("fitness_ledger_core.intent_compiler", fromlist=["IntentCompiler"]).IntentCompiler(views).compile(goal, None, catalog, facts=facts)
        req = requirement(goal, ["body_history"], ["体重趋势"])
        mapping = RequirementMapper().map(req)
        evaluation = compile_and_evaluate(req, goal, facts, catalog, draft, mapping)
        assert evaluation.status == "ready_with_limits"
        assert evaluation.answerability == "ready_with_limits"
        assert evaluation.evidence_profile.candidate_record_count == 3
        assert evaluation.evidence_profile.materialized_record_count is None
        assert evaluation.evidence_profile.exported_record_count is None
        assert "quality:body.measurement_context" in evaluation.missing_information
        assert evaluation.evidence_requirements.analysis_task_ids == ["weight_trend", "body_record_coverage"]
        assert evaluation.evidence_requirements.ignored_model_derived_metrics == ["体重趋势"]
    finally:
        temp.cleanup()


def test_diet_and_training_sufficiency_fail_closed() -> None:
    temp, views, catalog = environment()
    try:
        compiler = __import__("fitness_ledger_core.intent_compiler", fromlist=["IntentCompiler"]).IntentCompiler(views)
        goal = "分析饮食是否影响训练"
        facts = compiler.prepare(goal, catalog)
        _intent, _package, draft = compiler.compile(goal, None, catalog, facts=facts)
        req = requirement(goal, ["diet_macros", "training_context"], ["饮食-训练相关性指数"])
        evaluation = compile_and_evaluate(req, goal, facts, catalog, draft, RequirementMapper().map(req))
        assert evaluation.status == "insufficient_evidence"
        assert evaluation.answerability == "insufficient_evidence"
        assert any(item.startswith("training.movements.sets.load") for item in evaluation.missing_information)
        assert "计算未注册的饮食-训练相关性指数" in evaluation.forbidden_claims
        assert "diet" in evaluation.evidence_profile.selected_modules
        assert "training" in evaluation.evidence_profile.selected_modules
        assert "raw_entries" in evaluation.evidence_profile.available_modules
        assert "raw_entries" not in evaluation.evidence_profile.authorized_modules
        assert (evaluation.evidence_profile.aligned_day_count or 0) < 4
    finally:
        temp.cleanup()


def test_training_summary_cannot_claim_performance() -> None:
    temp, views, catalog = environment()
    try:
        compiler = __import__("fitness_ledger_core.intent_compiler", fromlist=["IntentCompiler"]).IntentCompiler(views)
        goal = "分析最近训练表现有没有下降"
        facts = compiler.prepare(goal, catalog)
        _intent, _package, draft = compiler.compile(goal, None, catalog, facts=facts)
        req = requirement(goal, ["training_context"])
        evaluation = compile_and_evaluate(req, goal, facts, catalog, draft, RequirementMapper().map(req))
        assert evaluation.status == "insufficient_evidence"
        assert "training_summary_only" in evaluation.evidence_profile.quality_flags
        assert "仅凭训练摘要评价表现" in evaluation.forbidden_claims
        assert "downgrade_to_coverage_report" == evaluation.required_next_action
    finally:
        temp.cleanup()


def main() -> None:
    test_task_registry_is_registered_and_non_executable()
    test_body_profile_distinguishes_candidate_from_materialized()
    test_diet_and_training_sufficiency_fail_closed()
    test_training_summary_cannot_claim_performance()
    print("FITNESS_LEDGER_ANALYSIS_EVIDENCE_CONTRACT_OK")


if __name__ == "__main__":
    main()
