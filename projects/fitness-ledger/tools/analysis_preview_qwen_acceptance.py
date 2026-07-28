"""Reproducible qwen3:4b Preview acceptance on anonymous fixtures.

This command never opens the formal tracker.  It creates the same anonymous
fixture used by the deterministic tests and emits one trace per request.  Use
``--output`` to persist a local JSON artifact for review.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_preview_service import AnalysisPreviewService  # noqa: E402
from fitness_ledger_core.shadow_planner import OllamaShadowTransport  # noqa: E402
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from intelligent_export_core_test import fixture  # noqa: E402


REQUESTS = (
    "分析最近体重变化",
    "分析最近饮食情况",
    "分析最近训练表现",
    "分析最近饮食和训练",
    "删除最近训练记录",
    "追溯最近一周的原始记录",
    "看看最近的情况",
    "看看推胸有没有进步",
)


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-qwen-preview-") as name:
        tracker, dictionary = fixture(Path(name))
        service = AnalysisPreviewService(LedgerViewModels(tracker, dictionary), OllamaShadowTransport())
        # Evaluate once per request so the model latency and raw output in each
        # trace correspond to exactly one service state transition.
        results = []
        for request in REQUESTS:
            response = service.preview(request)
            results.append({
                "case_id": f"preview_{len(results) + 1:02d}",
                "user_input": request,
                "status": response["status"],
                "trace": response["trace"],
                "planner": {
                    "model": response["planner"].get("model", ""),
                    "model_digest": response["planner"].get("model_digest", ""),
                    "latency_ms": response["planner"].get("latency_ms", 0),
                    "capabilities": [item["capability_id"] for item in (response.get("mapping_preview") or {}).get("mapped_capabilities", [])],
                },
            })
        return {"schema_version": "fitness-ledger-qwen-preview-acceptance-v1", "anonymous": True, "cases": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(), ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
