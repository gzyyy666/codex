"""Anonymous tests for the deterministic Gate and read-only preview service."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_preview_service import AnalysisPreviewService  # noqa: E402
from fitness_ledger_core.data_catalog import DataCatalogBuilder  # noqa: E402
from fitness_ledger_core.request_gate import (  # noqa: E402
    ANALYSIS_REQUEST,
    CLARIFICATION_REQUIRED,
    MOVEMENT_RESOLUTION_REQUIRED,
    RAW_PERMISSION_REQUIRED,
    UNSUPPORTED_WRITE_OPERATION,
    RequestGate,
)
from fitness_ledger_core.shadow_planner import FakeShadowTransport, ShadowModelManifest  # noqa: E402
from fitness_ledger_core.shadow_planner_evaluation import (  # noqa: E402
    ANALYSIS_DETAILS_SCHEMA_VERSION,
    CAPABILITY_SELECTION_SCHEMA_VERSION,
)
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from intelligent_export_core_test import fixture  # noqa: E402


def selection(capabilities: list[str]) -> dict:
    return {
        "schema_version": CAPABILITY_SELECTION_SCHEMA_VERSION,
        "abstain": not capabilities,
        "required_capabilities": [{"capability_id": item, "reason": "用户明确提出该只读分析对象"} for item in capabilities],
        "optional_capabilities": [],
        "missing_information": [] if capabilities else ["缺少明确分析目标"],
        "clarifications": [] if capabilities else ["请明确需要分析的只读目标"],
    }


def details() -> dict:
    return {
        "schema_version": ANALYSIS_DETAILS_SCHEMA_VERSION,
        "analysis_goal": "分析用户明确提出的匿名记录趋势",
        "questions_to_answer": ["记录趋势如何？"],
        "preferred_time_window": {"kind": "recent", "label": "最近"},
        "derived_metrics": [],
        "gpt_prompt_outline": ["基于确定性 Core 提供的匿名聚合事实回答，并说明不确定性"],
    }


def environment():
    temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-preview-")
    tracker, dictionary = fixture(Path(temp.name))
    views = LedgerViewModels(tracker, dictionary)
    return temp, views, tracker, dictionary


def test_request_gate() -> None:
    temp, views, _tracker, _dictionary = environment()
    try:
        gate = RequestGate(views, DataCatalogBuilder(views).build())
        assert gate.evaluate("分析最近体重变化").status == ANALYSIS_REQUEST
        assert gate.evaluate("分析最近饮食和训练").status == ANALYSIS_REQUEST
        assert gate.evaluate("删除最近训练记录").status == UNSUPPORTED_WRITE_OPERATION
        assert gate.evaluate("写入一条新的训练记录").status == UNSUPPORTED_WRITE_OPERATION
        assert gate.evaluate("帮我制定未来三个月训练计划").status == UNSUPPORTED_WRITE_OPERATION
        assert gate.evaluate("追溯最近一周的原始记录").status == RAW_PERMISSION_REQUIRED
        assert gate.evaluate("看看最近的情况").status == CLARIFICATION_REQUIRED
        assert gate.evaluate("看看一整个月的体重走势").status == CLARIFICATION_REQUIRED
        assert gate.evaluate("看看推胸有没有进步").status == MOVEMENT_RESOLUTION_REQUIRED
    finally:
        temp.cleanup()


def test_legal_preview_reuses_core_without_execution() -> None:
    temp, views, tracker, dictionary = environment()
    try:
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (tracker, dictionary)]
        transport = FakeShadowTransport([selection(["body_history"]), details(), selection(["diet_macros", "training_context"]), details()])
        service = AnalysisPreviewService(views, transport)
        body = service.preview("分析最近体重变化")
        assert body["status"] == "ready", body
        assert body["execution"] == {"allowed": False, "mode": "preview_only", "executor_called": False}
        assert body["mapping_preview"]["mapped_capabilities"][0]["capability_id"] == "body_history"
        assert body["gpt_analysis_package_preview"]["raw_included"] is False
        assert body["gpt_analysis_package_preview"]["notes_scope"] is None
        assert "private raw" not in json.dumps(body, ensure_ascii=False)

        combined = service.preview("分析最近饮食和训练")
        assert combined["status"] == "ready", combined
        assert {item["capability_id"] for item in combined["mapping_preview"]["mapped_capabilities"]} == {"diet_macros", "training_context"}
        assert len(transport.calls) == 4
        after = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (tracker, dictionary)]
        assert before == after
    finally:
        temp.cleanup()


def test_blocked_requests_do_not_call_model() -> None:
    temp, views, _tracker, _dictionary = environment()
    try:
        transport = FakeShadowTransport([])
        service = AnalysisPreviewService(views, transport)
        for request, status in (
            ("删除最近训练记录", "unsupported_operation"),
            ("写入一条新的训练记录", "unsupported_operation"),
            ("追溯最近一周的原始记录", "raw_permission_required"),
            ("看看推胸有没有进步", "movement_resolution_required"),
            ("看看最近的情况", "clarification_required"),
        ):
            assert service.preview(request)["status"] == status
        assert transport.calls == []
    finally:
        temp.cleanup()


def test_model_unavailable_and_planner_scope_failure() -> None:
    temp, views, _tracker, _dictionary = environment()
    try:
        unavailable = FakeShadowTransport(manifest=ShadowModelManifest("http://127.0.0.1:11434", "qwen3:4b", False, error_code="MODEL_UNAVAILABLE"))
        assert AnalysisPreviewService(views, unavailable).preview("分析最近体重变化")["status"] == "model_unavailable"

        abstain = FakeShadowTransport([selection([])])
        failed = AnalysisPreviewService(views, abstain).preview("分析最近体重变化")
        assert failed["status"] == "planner_invalid"
        assert failed["validation"]["error_code"] == "CAPABILITY_SCOPE_MISMATCH"
    finally:
        temp.cleanup()


def main() -> None:
    test_request_gate()
    test_legal_preview_reuses_core_without_execution()
    test_blocked_requests_do_not_call_model()
    test_model_unavailable_and_planner_scope_failure()
    print("FITNESS_LEDGER_ANALYSIS_PREVIEW_SERVICE_OK")


if __name__ == "__main__":
    main()
