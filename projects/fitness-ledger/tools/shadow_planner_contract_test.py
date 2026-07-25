"""Milestone 3 shadow planner contract tests with anonymous fixtures and fakes."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_evaluation import AnonymizedDataProjector, privacy_audit  # noqa: E402
from fitness_ledger_core.analysis_foundation import AnalysisRequirementSpecV1, FoundationError, RequirementMapper  # noqa: E402
from fitness_ledger_core.data_catalog import DataCatalogBuilder  # noqa: E402
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from fitness_ledger_core.shadow_planner import (  # noqa: E402
    REQUIRED_CATEGORIES,
    SHADOW_ENDPOINT,
    SHADOW_MATRIX_SCHEMA_VERSION,
    SHADOW_MODEL,
    FakeShadowTransport,
    DeterministicBaseline,
    ShadowEvaluationMatrix,
    ShadowPlannerRunner,
    ShadowTransportError,
    build_shadow_input,
    shadow_matrix_json_schema,
    shadow_report_json_schema,
    _strict_json,
)
from intelligent_export_core_test import fixture  # noqa: E402


MATRIX = ROOT / "tools" / "fixtures" / "intelligent_export_shadow_matrix.json"


def requirement_payload() -> dict:
    return {
        "schema_version": "fitness-ledger-analysis-requirement-v1",
        "analysis_goal": "评估最近体重变化",
        "questions_to_answer": ["体重趋势如何？"],
        "required_capabilities": [{"capability_id": "body_history", "reason": "用户明确提到体重变化"}],
        "optional_capabilities": [],
        "preferred_time_window": {"kind": "recent", "label": "最近"},
        "derived_metrics": [{"name": "体重变化趋势", "reason": "帮助回答体重趋势问题"}],
        "missing_information": [],
        "clarifications": [],
        "evidence": [{"text": "最近体重变化", "source": "user_goal"}],
        "gpt_prompt_outline": ["先概括数据覆盖", "回答体重趋势并标记不确定性"],
    }


def expect(code: str, callback) -> None:
    try:
        callback()
    except FoundationError as exc:
        assert exc.code == code, (code, exc.code)
    else:
        raise AssertionError(f"expected {code}")


def anonymous_baseline() -> tuple[DeterministicBaseline, dict]:
    root = Path(tempfile.mkdtemp(prefix="fitness-ledger-shadow-fixture-"))
    tracker, dictionary = fixture(root)
    views = LedgerViewModels(tracker, dictionary)
    catalog = DataCatalogBuilder(views).build()
    return DeterministicBaseline(views, catalog), {"views": views, "catalog": catalog, "root": root}


def test_matrix_contract() -> ShadowEvaluationMatrix:
    matrix = ShadowEvaluationMatrix.load(MATRIX)
    assert matrix.schema_version == SHADOW_MATRIX_SCHEMA_VERSION
    assert len(matrix.cases) >= 10
    assert REQUIRED_CATEGORIES <= {case.category for case in matrix.cases}
    assert matrix.matrix_hash == ShadowEvaluationMatrix.from_dict(matrix.to_dict()).matrix_hash
    assert shadow_matrix_json_schema()["properties"]["cases"]["minItems"] == 10
    assert shadow_report_json_schema()["properties"]["model"]["const"] == SHADOW_MODEL
    serialized = json.dumps(matrix.to_dict(), ensure_ascii=False)
    assert "record_id" not in serialized and "private raw" not in serialized
    expect("EVALUATION_DATA_LEAKAGE", lambda: ShadowEvaluationMatrix.from_dict({**matrix.to_dict(), "cases": [matrix.cases[0].to_dict()] * 10}))
    expect("EVALUATION_PRIVACY_VIOLATION", lambda: ShadowEvaluationMatrix.from_dict({**matrix.to_dict(), "matrix_id": "tracker.json"}))
    return matrix


def test_input_and_schema_boundaries() -> None:
    baseline, fixture_data = anonymous_baseline()
    requirement = AnalysisRequirementSpecV1.from_dict(requirement_payload(), user_goal="分析最近体重变化")
    mapping = RequirementMapper().map(requirement)
    context = {"blocks": [item.to_dict() for item in AnonymizedDataProjector().build(fixture_data["catalog"], mapping)]}
    payload = build_shadow_input("分析最近体重变化", RequirementMapper().registry, context)
    assert set(payload) == {"user_goal", "available_capabilities", "analysis_context"}
    assert privacy_audit(payload["analysis_context"])["passed"]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "record_id" not in serialized and "private raw" not in serialized
    assert baseline.evaluate("分析最近体重变化")["outcome"] == "MAPPED"
    expect("EVALUATION_PRIVACY_VIOLATION", lambda: build_shadow_input("目标", RequirementMapper().registry, {"record_id": "must-not-pass"}))
    expect("FORMAL_DATE_FORBIDDEN", lambda: AnalysisRequirementSpecV1.from_dict({**requirement_payload(), "preferred_time_window": {"kind": "explicit_user_phrase", "label": "2026-07-25"}}, user_goal="分析最近体重变化"))
    expect("EVIDENCE_NOT_GROUNDED", lambda: AnalysisRequirementSpecV1.from_dict({**requirement_payload(), "evidence": [{"text": "今天发生了膝盖疼痛", "source": "user_goal"}]}, user_goal="分析最近体重变化"))


def test_runner_failure_injection() -> None:
    baseline, _ = anonymous_baseline()
    case = ShadowEvaluationMatrix.load(MATRIX).cases[0]
    context = {"aggregate": {"coverage": "anonymous"}}

    valid_transport = FakeShadowTransport([requirement_payload()])
    result = ShadowPlannerRunner(valid_transport).run_case(case, baseline.evaluate(case.user_goal), context)
    assert result.final_status == "VALIDATED", result.to_dict()
    assert valid_transport.calls[0]["user_payload"]["user_goal"] == case.user_goal
    assert valid_transport.calls[0]["response_schema"] == AnalysisRequirementSpecV1.json_schema()

    invalid = ShadowPlannerRunner(FakeShadowTransport(["not-json"])).run_case(case, baseline.evaluate(case.user_goal), context)
    assert invalid.final_status == "INVALID" and invalid.error_source == "Prompt / Schema"

    unavailable = ShadowPlannerRunner(FakeShadowTransport(errors=[ShadowTransportError("offline", "MODEL_CONNECTION_ERROR", 2)])).run_case(case, baseline.evaluate(case.user_goal), context)
    assert unavailable.final_status == "MODEL_UNAVAILABLE" and unavailable.retry == 1

    raw_proposal = {**requirement_payload(), "required_capabilities": [{"capability_id": "raw_trace", "reason": "原始记录"}]}
    raw = ShadowPlannerRunner(FakeShadowTransport([raw_proposal])).run_case(case, baseline.evaluate(case.user_goal), context)
    assert raw.final_status == "ABSTAIN" and raw.mapping_result["error_code"] == "RAW_PERMISSION_NOT_GRANTABLE"

    unknown_proposal = {**requirement_payload(), "required_capabilities": [{"capability_id": "not-in-registry", "reason": "越过 Registry 的候选"}]}
    unknown = ShadowPlannerRunner(FakeShadowTransport([unknown_proposal])).run_case(case, baseline.evaluate(case.user_goal), context)
    assert unknown.final_status == "ABSTAIN" and unknown.mapping_result["error_code"] == "UNKNOWN_CAPABILITY"
    assert unknown.error_source == "Registry"

    expect("FORMAL_ID_FORBIDDEN", lambda: _strict_json(json.dumps({"record_id": "formal"}, ensure_ascii=False)))


def test_matrix_report_is_structured() -> None:
    matrix = ShadowEvaluationMatrix.load(MATRIX)
    baseline, _ = anonymous_baseline()
    transport = FakeShadowTransport([requirement_payload() for _ in matrix.cases])
    report = ShadowPlannerRunner(transport).run_matrix(matrix, baseline, {"aggregate": {"coverage": "anonymous"}})
    value = report.to_dict()
    assert report.total_cases == len(matrix.cases)
    assert report.model == SHADOW_MODEL and report.endpoint == SHADOW_ENDPOINT and report.model_digest == "fake-digest"
    assert value["schema_version"] == "fitness-ledger-qwen-shadow-report-v1"
    assert set(report.metrics["status_counts"]) == {"VALIDATED", "ABSTAIN", "INVALID", "MODEL_UNAVAILABLE", "SAFE_FALLBACK"}
    assert "raw_text" not in json.dumps(value, ensure_ascii=False)
    assert "ExportExecutor" not in json.dumps(value, ensure_ascii=False)


def test_static_shadow_boundary() -> None:
    source = (ROOT / "fitness_ledger_core" / "shadow_planner.py").read_text(encoding="utf-8")
    assert "IntelligentExportService(" not in source
    assert "OllamaNativeAdapter(" not in source
    assert "ExportExecutor(" not in source
    assert "_legacy_run" not in source


def main() -> None:
    test_matrix_contract()
    test_input_and_schema_boundaries()
    test_runner_failure_injection()
    test_matrix_report_is_structured()
    test_static_shadow_boundary()
    print("FITNESS_LEDGER_SHADOW_PLANNER_CONTRACT_OK")


if __name__ == "__main__":
    main()
