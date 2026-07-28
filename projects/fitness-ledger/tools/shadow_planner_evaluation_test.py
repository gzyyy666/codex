"""Deterministic tests for the anonymous Shadow Planner evaluation loop."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_foundation import CapabilityRegistryV1, FoundationError  # noqa: E402
from fitness_ledger_core.data_catalog import DataCatalogBuilder  # noqa: E402
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from fitness_ledger_core.shadow_planner import (  # noqa: E402
    SHADOW_POLICY_VERSION,
    SHADOW_SYSTEM_PROMPT,
    FakeShadowTransport,
    ShadowEvaluationMatrix,
)
from fitness_ledger_core.shadow_planner_evaluation import (  # noqa: E402
    ANALYSIS_DETAILS_SCHEMA_VERSION,
    ANALYSIS_DETAILS_SYSTEM_PROMPT,
    CAPABILITY_SELECTION_SCHEMA_VERSION,
    CAPABILITY_SELECTION_SYSTEM_PROMPT,
    EVALUATION_REFERENCE_IMPLEMENTATIONS,
    GROUNDING_PROMPT_VERSION,
    LEGACY_M3_HOLDOUT_HASH,
    REGISTRY_V2_MODEL_VIEW_VERSION,
    TWO_STAGE_PROMPT_VERSION,
    TWO_STAGE_REQUEST_SCHEMA_VERSION,
    CapabilityRegistryV2,
    compare_registry_reports,
    compare_report_values,
    compare_reports,
    holdout_hash,
    run_grounding_benchmark,
    select_minimal_fix,
)
from intelligent_export_core_test import fixture  # noqa: E402


MATRIX = ROOT / "tools" / "fixtures" / "intelligent_export_shadow_matrix.json"


def proposal(case, capabilities=None) -> dict:
    requested = case.expected_capabilities if capabilities is None else capabilities
    return {
        "schema_version": "fitness-ledger-analysis-requirement-v1",
        "analysis_goal": "形成安全的匿名分析需求" if case.expected_abstain else f"分析用户提出的{case.category}问题",
        "questions_to_answer": [] if case.expected_abstain else ["当前匿名记录能回答哪些趋势问题？"],
        "required_capabilities": [
            {"capability_id": capability_id, "reason": "该能力与用户明确提出的分析对象一致"}
            for capability_id in requested
        ],
        "optional_capabilities": [],
        "preferred_time_window": {"kind": "recent", "label": "最近"} if not case.expected_abstain else {"kind": "unspecified", "label": ""},
        "derived_metrics": [],
        "missing_information": ["需要明确可分析目标"] if case.expected_abstain else [],
        "clarifications": ["请确认分析对象"] if case.expected_abstain else [],
        "evidence": [],
        "gpt_prompt_outline": ["只分析匿名聚合事实并说明不确定性"],
    }


def selection(case) -> dict:
    return {
        "schema_version": CAPABILITY_SELECTION_SCHEMA_VERSION,
        "abstain": case.expected_abstain,
        "required_capabilities": [
            {"capability_id": capability_id, "reason": "用户明确请求该分析对象"}
            for capability_id in case.expected_capabilities
        ],
        "optional_capabilities": [],
        "missing_information": ["缺少安全分析目标"] if case.expected_abstain else [],
        "clarifications": ["请明确只读分析目标"] if case.expected_abstain else [],
    }


def details(case) -> dict:
    return {
        "schema_version": ANALYSIS_DETAILS_SCHEMA_VERSION,
        "analysis_goal": f"分析{case.category}相关趋势",
        "questions_to_answer": ["匿名记录可以回答哪些趋势？"],
        "preferred_time_window": {"kind": "recent", "label": "最近"},
        "derived_metrics": [],
        "gpt_prompt_outline": ["基于匿名聚合事实回答问题"],
    }


def environment():
    temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-shadow-eval-")
    tracker, dictionary = fixture(Path(temp.name))
    views = LedgerViewModels(tracker, dictionary)
    return temp, views, DataCatalogBuilder(views).build()


def test_gold_and_registry() -> ShadowEvaluationMatrix:
    matrix = ShadowEvaluationMatrix.load(MATRIX)
    assert len(matrix.cases) == 18
    assert len([case for case in matrix.cases if case.split == "holdout"]) == 13
    assert holdout_hash(matrix) == LEGACY_M3_HOLDOUT_HASH
    for case in matrix.cases:
        assert case.explanation and case.boundary_rules
        assert not (set(case.expected_capabilities) & set(case.forbidden_capabilities))
    registry = CapabilityRegistryV2()
    assert set(registry.ids) == set(CapabilityRegistryV1().ids)
    model_view = registry.model_view()
    assert model_view["view_version"] == REGISTRY_V2_MODEL_VIEW_VERSION
    assert registry.model_view_hash == __import__("hashlib").sha256(
        json.dumps(model_view, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert "tracker.json" not in json.dumps(model_view, ensure_ascii=False)
    assert "movement_dictionary" not in json.dumps(model_view, ensure_ascii=False)
    expected_view_fields = {
        "capability_id",
        "human_description",
        "user_expression_examples",
        "analysis_questions",
        "related_capabilities",
        "forbidden_usage",
        "evidence_examples",
        "model_selectable",
        "requires_user_confirmation",
        "grants_raw",
    }
    assert all(set(item) == expected_view_fields for item in model_view["capabilities"])
    for capability in registry.to_dict()["capabilities"]:
        assert capability["human_description"]
        assert capability["user_expression_examples"]
        assert capability["forbidden_usage"]
        assert capability["evidence_examples"]
    assert {item["license"] for item in EVALUATION_REFERENCE_IMPLEMENTATIONS} == {"MIT"}
    return matrix


def test_reproducible_trace(matrix: ShadowEvaluationMatrix):
    temp, views, catalog = environment()
    try:
        responses = [proposal(case) for case in matrix.cases]
        transport = FakeShadowTransport(responses)
        report = run_grounding_benchmark(
            matrix,
            views,
            catalog,
            CapabilityRegistryV1(),
            SHADOW_POLICY_VERSION,
            SHADOW_SYSTEM_PROMPT,
            "v1-test",
            transport,
        )
        assert report.holdout_hash == LEGACY_M3_HOLDOUT_HASH
        assert len(report.traces) == len(matrix.cases)
        assert report.metrics["holdout"]["schema_validity"] == 1.0
        assert report.metrics["holdout"]["capability_match"] == 1.0
        assert report.metrics["holdout"]["boundary_safety"] == 1.0
        assert report.metrics["holdout"]["correct_abstain"] == 1.0
        assert report.failure_counts["EXPECTED_ABSTAIN"] == 4
        for trace in report.traces:
            value = trace.to_dict()
            assert set(
                (
                    "case_id",
                    "user_input",
                    "model_name",
                    "model_digest",
                    "prompt_version",
                    "registry_version",
                    "request_schema_version",
                    "model_raw_output",
                    "parsed_requirement",
                    "gold_requirement",
                    "validation_result",
                    "metrics",
                    "failure_category",
                )
            ) <= set(value)
            assert value["model_raw_output"]
            assert "tracker.json" not in json.dumps(value, ensure_ascii=False)
        comparison = compare_reports(report, report)
        assert comparison["same_holdout"] is True
        assert all(value == 0 for value in comparison["delta"].values())
        value_comparison = compare_report_values(report.to_dict(), report.to_dict())
        assert value_comparison["same_model_digest"] is True
        assert value_comparison["decision"] == "CONTINUE_QWEN3B4"
    finally:
        temp.cleanup()


def test_failure_classification(matrix: ShadowEvaluationMatrix):
    temp, views, catalog = environment()
    try:
        responses = ["not-json", *[proposal(case) for case in matrix.cases[1:]]]
        report = run_grounding_benchmark(
            matrix,
            views,
            catalog,
            CapabilityRegistryV1(),
            SHADOW_POLICY_VERSION,
            SHADOW_SYSTEM_PROMPT,
            "v1-invalid-test",
            FakeShadowTransport(responses),
        )
        first = report.traces[0]
        assert first.failure_category == "SCHEMA_FAILURE"
        assert first.model_raw_output == "not-json"
        assert first.validation_result["error_code"] == "MODEL_SCHEMA_INVALID"
        assert select_minimal_fix(report.to_dict())["strategy"] == "TWO_STAGE_SCHEMA"
    finally:
        temp.cleanup()

    temp, views, catalog = environment()
    try:
        responses = [
            proposal(matrix.cases[0], ["diet_macros"]),
            *[proposal(case) for case in matrix.cases[1:]],
        ]
        report = run_grounding_benchmark(
            matrix,
            views,
            catalog,
            CapabilityRegistryV2(),
            GROUNDING_PROMPT_VERSION,
            SHADOW_SYSTEM_PROMPT,
            "grounded-classification-test",
            FakeShadowTransport(responses),
        )
        assert report.traces[0].failure_category == "PROMPT_GROUNDING_FAILURE"
    finally:
        temp.cleanup()


def test_two_stage_schema_strategy(matrix: ShadowEvaluationMatrix):
    temp, views, catalog = environment()
    try:
        responses = []
        for case in matrix.cases:
            responses.append(selection(case))
            if not case.expected_abstain:
                responses.append(details(case))
        transport = FakeShadowTransport(responses)
        report = run_grounding_benchmark(
            matrix,
            views,
            catalog,
            CapabilityRegistryV1(),
            TWO_STAGE_PROMPT_VERSION,
            CAPABILITY_SELECTION_SYSTEM_PROMPT + "\n" + ANALYSIS_DETAILS_SYSTEM_PROMPT,
            "v2-test",
            transport,
            strategy="two_stage_schema",
            request_schema_version=TWO_STAGE_REQUEST_SCHEMA_VERSION,
        )
        assert report.metrics["holdout"]["schema_validity"] == 1.0
        assert report.metrics["holdout"]["capability_match"] == 1.0
        assert report.metrics["holdout"]["boundary_safety"] == 1.0
        assert report.metrics["holdout"]["correct_abstain"] == 1.0
        assert all(trace.request_schema_version == TWO_STAGE_REQUEST_SCHEMA_VERSION for trace in report.traces)
        assert any(call["system_prompt"] == CAPABILITY_SELECTION_SYSTEM_PROMPT for call in transport.calls)
        assert any(call["system_prompt"] == ANALYSIS_DETAILS_SYSTEM_PROMPT for call in transport.calls)
    finally:
        temp.cleanup()


def test_registry_v2_model_view_injection(matrix: ShadowEvaluationMatrix):
    temp, views, catalog = environment()
    try:
        responses = []
        for case in matrix.cases:
            responses.append(selection(case))
            if not case.expected_abstain:
                responses.append(details(case))
        registry = CapabilityRegistryV2()
        view = registry.model_view()
        view["sha256"] = registry.model_view_hash
        transport = FakeShadowTransport(responses)
        report = run_grounding_benchmark(
            matrix,
            views,
            catalog,
            registry,
            TWO_STAGE_PROMPT_VERSION,
            CAPABILITY_SELECTION_SYSTEM_PROMPT + "\n" + ANALYSIS_DETAILS_SYSTEM_PROMPT,
            "v2-registry-test",
            transport,
            strategy="two_stage_schema",
            request_schema_version=TWO_STAGE_REQUEST_SCHEMA_VERSION,
            capability_view=view,
        )
        assert report.registry_view_version == REGISTRY_V2_MODEL_VIEW_VERSION
        assert report.registry_view_hash == registry.model_view_hash
        assert report.metrics["holdout"]["explicit_abstain"] == 1.0
        selection_calls = [call for call in transport.calls if call["system_prompt"] == CAPABILITY_SELECTION_SYSTEM_PROMPT]
        assert selection_calls and selection_calls[0]["user_payload"]["available_capabilities"] == view["capabilities"]
        assert compare_registry_reports(report.to_dict(), report.to_dict())["state"] == "READY_FOR_WEB_INTERFACE"
    finally:
        temp.cleanup()


def test_holdout_guard(matrix: ShadowEvaluationMatrix):
    changed = matrix.to_dict()
    changed["cases"][0]["user_goal"] = "不同输入"
    try:
        altered = ShadowEvaluationMatrix.from_dict(changed)
        temp, views, catalog = environment()
        try:
            run_grounding_benchmark(
                altered,
                views,
                catalog,
                CapabilityRegistryV1(),
                SHADOW_POLICY_VERSION,
                SHADOW_SYSTEM_PROMPT,
                "changed",
                FakeShadowTransport([]),
            )
        finally:
            temp.cleanup()
    except FoundationError as exc:
        assert exc.code == "GOLD_LABEL_ERROR"
    else:
        raise AssertionError("changed legacy holdout was accepted")


def main() -> None:
    matrix = test_gold_and_registry()
    test_reproducible_trace(matrix)
    test_failure_classification(matrix)
    test_two_stage_schema_strategy(matrix)
    test_registry_v2_model_view_injection(matrix)
    test_holdout_guard(matrix)
    print("FITNESS_LEDGER_SHADOW_PLANNER_EVALUATION_OK")


if __name__ == "__main__":
    main()
