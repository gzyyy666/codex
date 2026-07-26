"""HTTP-independent tests for the isolated Review UI application."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.shadow_planner import FakeShadowTransport, ShadowModelManifest  # noqa: E402
from analysis_preview_review_ui import ReviewUIApplication  # noqa: E402
from fitness_ledger_core.shadow_planner_evaluation import ANALYSIS_DETAILS_SCHEMA_VERSION, CAPABILITY_SELECTION_SCHEMA_VERSION  # noqa: E402


def selection(capability_ids: list[str]) -> dict:
    return {
        "schema_version": CAPABILITY_SELECTION_SCHEMA_VERSION,
        "abstain": not capability_ids,
        "required_capabilities": [{"capability_id": item, "reason": "匿名 Review fixture"} for item in capability_ids],
        "optional_capabilities": [],
        "missing_information": [] if capability_ids else ["缺少目标"],
        "clarifications": [] if capability_ids else ["请补充目标"],
    }


def details() -> dict:
    return {
        "schema_version": ANALYSIS_DETAILS_SCHEMA_VERSION,
        "analysis_goal": "分析匿名记录趋势",
        "questions_to_answer": ["趋势如何？"],
        "preferred_time_window": {"kind": "recent", "label": "最近"},
        "derived_metrics": [],
        "gpt_prompt_outline": ["只使用匿名聚合事实"],
    }


def main() -> None:
    transport = FakeShadowTransport([selection(["body_history"]), details()])
    application = ReviewUIApplication(transport)
    try:
        result = application.preview({"request": "分析最近体重变化", "budget_mode": "standard"})
        assert result["status"] == "ready", result
        assert result["execution"]["executor_called"] is False
        assert result["gpt_analysis_package_preview"]["raw_included"] is False
        assert result["mapping_preview"]["deterministic_plan_preview"]["selected_modules"] == ["body"]
        assert "candidate_record_ids" not in json.dumps(result, ensure_ascii=False)

        blocked = application.preview({"request": "删除最近饮食记录"})
        assert blocked["status"] == "unsupported_operation"
        assert blocked["planner"]["status"] == "not_run"
        assert len(transport.calls) == 2

        unavailable = ReviewUIApplication(FakeShadowTransport(manifest=ShadowModelManifest("http://127.0.0.1:11434", "qwen3:4b", False, error_code="MODEL_UNAVAILABLE")))
        try:
            assert unavailable.preview({"request": "分析最近体重变化"})["status"] == "model_unavailable"
        finally:
            unavailable.close()
    finally:
        application.close()
    print("FITNESS_LEDGER_ANALYSIS_PREVIEW_REVIEW_UI_OK")


if __name__ == "__main__":
    main()
