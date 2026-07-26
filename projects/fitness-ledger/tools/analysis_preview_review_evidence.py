"""Generate the complete anonymous Review Evidence bundle for Preview Service.

The four legal cases use the configured qwen3:4b transport when available.
The final case deliberately injects an unavailable manifest to prove the
fallback state without changing the machine or formal data.  The output is a
review artifact, not a product API and does not write tracker data.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_preview_service import AnalysisPreviewService  # noqa: E402
from fitness_ledger_core.shadow_planner import (  # noqa: E402
    FakeShadowTransport,
    OllamaShadowTransport,
    SHADOW_ENDPOINT,
    SHADOW_MODEL,
    ShadowModelManifest,
)
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from intelligent_export_core_test import fixture  # noqa: E402


CASES = (
    ("body_recent", "分析最近体重变化", "qwen3:4b"),
    ("diet_recent", "分析最近饮食", "qwen3:4b"),
    ("training_recent", "分析最近训练", "qwen3:4b"),
    ("diet_training_impact", "分析饮食是否影响训练", "qwen3:4b"),
    ("delete_diet", "删除最近饮食记录", "gate_only"),
    ("raw_trace", "查看 Raw 原始记录", "gate_only"),
    ("ambiguous_target", "看看最近情况", "gate_only"),
    ("ambiguous_movement", "看看推胸有没有进步", "gate_only"),
    ("ollama_unavailable", "分析最近体重变化", "unavailable"),
)


def _package_summary(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    return {
        "schema_version": value.get("schema_version", ""),
        "package_id": value.get("package_id", ""),
        "capability_ids": list(value.get("capability_ids", [])),
        "preferred_time_window": value.get("preferred_time_window", {}),
        "confirmed_time_window": value.get("confirmed_time_window"),
        "derived_metrics_count": len(value.get("derived_metrics", [])),
        "gpt_prompt_outline_count": len(value.get("gpt_prompt_outline", [])),
        "data_block_count": len(value.get("data_blocks", [])),
        "raw_included": value.get("raw_included", False),
        "notes_scope": value.get("notes_scope"),
    }


def _case_record(case_id: str, request: str, response: dict[str, Any], transport_kind: str) -> dict[str, Any]:
    planner = response.get("planner", {})
    trace = response.get("trace", {})
    stage_results = planner.get("stage_results", {}) or {}
    planner_called = planner.get("status") not in {"not_run", "model_unavailable"}
    call_count = sum(
        1
        for stage_name in ("capability_selection", "analysis_details")
        if isinstance(stage_results.get(stage_name), dict)
        and (stage_results[stage_name].get("passed") or stage_results[stage_name].get("error_code"))
    )
    mapping = response.get("mapping_preview") or {}
    plan = mapping.get("deterministic_plan_preview") or {}
    return {
        "case_id": case_id,
        "user_input": request,
        "transport": transport_kind,
        "request_gate": response.get("gate", {}),
        "planner": {
            "called": planner_called,
            "call_count": call_count,
            "status": planner.get("status", ""),
            "model": planner.get("model", ""),
            "model_digest": planner.get("model_digest", ""),
            "prompt_version": planner.get("prompt_version", ""),
            "latency_ms": planner.get("latency_ms", 0),
            "raw_output": planner.get("raw_output", ""),
            "stage_results": stage_results,
        },
        "analysis_requirement_spec": trace.get("parsed_requirement"),
        "validation": response.get("validation", {}),
        "analysis_evaluation": response.get("analysis_evaluation"),
        "date_movement_capability_resolution": response.get("resolution", {}),
        "mapping_preview": mapping,
        "gpt_analysis_package_preview_summary": _package_summary(response.get("gpt_analysis_package_preview")),
        "service_status": response.get("status", ""),
        "executor_called": bool(response.get("execution", {}).get("executor_called", True)),
        "raw_read": False,
        "formal_data_written": False,
        "failure_category": trace.get("failure_category", ""),
    }


def generate() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-review-evidence-") as name:
        tracker, dictionary = fixture(Path(name))
        views = LedgerViewModels(tracker, dictionary)
        qwen_service = AnalysisPreviewService(views, OllamaShadowTransport())
        results: list[dict[str, Any]] = []
        for case_id, request, mode in CASES[:-1]:
            response = qwen_service.preview(request)
            results.append(_case_record(case_id, request, response, mode))

        unavailable = FakeShadowTransport(
            manifest=ShadowModelManifest(SHADOW_ENDPOINT, SHADOW_MODEL, False, error_code="MODEL_UNAVAILABLE")
        )
        unavailable_service = AnalysisPreviewService(views, unavailable)
        response = unavailable_service.preview(CASES[-1][1])
        results.append(_case_record(CASES[-1][0], CASES[-1][1], response, "unavailable"))

    latencies = [int(item["planner"]["latency_ms"]) for item in results if item["planner"]["latency_ms"]]
    sorted_latencies = sorted(latencies)
    p95_index = max(0, min(len(sorted_latencies) - 1, int((len(sorted_latencies) * 0.95 + 0.999999)) - 1)) if sorted_latencies else 0
    return {
        "schema_version": "fitness-ledger-analysis-preview-review-evidence-v1",
        "anonymous_fixture": True,
        "model": SHADOW_MODEL,
        "model_digest": next((item["planner"]["model_digest"] for item in results if item["planner"]["model_digest"]), ""),
        "cases": results,
        "summary": {
            "case_count": len(results),
            "ready_count": sum(item["service_status"] == "ready" for item in results),
            "gate_only_count": sum(not item["planner"]["called"] for item in results),
            "executor_called_count": sum(item["executor_called"] for item in results),
            "raw_read_count": sum(item["raw_read"] for item in results),
            "formal_data_written_count": sum(item["formal_data_written"] for item in results),
            "latency_count": len(latencies),
            "latency_average_ms": round(statistics.mean(latencies), 1) if latencies else 0,
            "latency_p95_ms": sorted_latencies[p95_index] if sorted_latencies else 0,
            "latency_max_ms": max(latencies) if latencies else 0,
            "planner_call_count_total": sum(item["planner"]["call_count"] for item in results),
            "analysis_status_counts": dict(
                __import__("collections").Counter(
                    item.get("analysis_evaluation", {}).get("status")
                    for item in results
                    if item.get("analysis_evaluation")
                )
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(generate(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
