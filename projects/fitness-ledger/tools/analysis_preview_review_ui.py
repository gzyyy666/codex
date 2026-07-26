"""Local-only Review UI for the Intelligent Export Preview Service.

Run from ``projects/fitness-ledger``:

    python tools/analysis_preview_review_ui.py --port 8788

The server binds to 127.0.0.1, uses an anonymous temporary fixture, and only
returns Preview data. It has no formal-data path, Executor, Cloud, or Web
application integration.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_preview_service import AnalysisPreviewService  # noqa: E402
from fitness_ledger_core.shadow_planner import OllamaShadowTransport, ShadowTransport  # noqa: E402
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from intelligent_export_core_test import fixture  # noqa: E402


UI_SCHEMA_VERSION = "fitness-ledger-analysis-preview-review-ui-v1"
MAX_REQUEST_BYTES = 100_000


def _package_summary(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    return {
        "schema_version": value.get("schema_version", ""),
        "capability_ids": list(value.get("capability_ids", [])),
        "preferred_time_window": value.get("preferred_time_window", {}),
        "confirmed_time_window": value.get("confirmed_time_window"),
        "data_block_count": len(value.get("data_blocks", [])),
        "raw_included": value.get("raw_included", False),
        "notes_scope": value.get("notes_scope"),
    }


def _safe_mapping(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    result = {key: item for key, item in value.items() if key != "deterministic_plan_preview"}
    plan = value.get("deterministic_plan_preview") or {}
    if plan:
        result["deterministic_plan_preview"] = {
            "interpreted_goal": plan.get("interpreted_goal", ""),
            "analysis_dimensions": list(plan.get("analysis_dimensions", [])),
            "date_range": plan.get("date_range", {}),
            "selected_modules": list(plan.get("selected_modules", [])),
            "selected_fields": dict(plan.get("selected_fields", {})),
            "selected_movements": list(plan.get("selected_movements", [])),
            "notes_selection_count": len(plan.get("notes_selection", [])),
            "missing_data_warnings": list(plan.get("missing_data_warnings", [])),
            "estimated_record_count": plan.get("estimated_record_count", 0),
            "estimated_output_size": plan.get("estimated_output_size", 0),
        }
    return result


def safe_ui_response(response: dict[str, Any]) -> dict[str, Any]:
    """Return UI evidence without candidate record contents or source IDs."""

    trace = response.get("trace", {})
    planner = response.get("planner", {})
    return {
        "schema_version": UI_SCHEMA_VERSION,
        "status": response.get("status", ""),
        "trace_id": response.get("trace_id", ""),
        "gate": response.get("gate", {}),
        "planner": {
            "status": planner.get("status", ""),
            "model": planner.get("model", ""),
            "model_digest": planner.get("model_digest", ""),
            "prompt_version": planner.get("prompt_version", ""),
            "latency_ms": planner.get("latency_ms", 0),
            "retry": planner.get("retry", 0),
            "raw_output": planner.get("raw_output", ""),
            "stage_results": planner.get("stage_results", {}),
        },
        "analysis_requirement_spec": trace.get("parsed_requirement"),
        "validation": response.get("validation", {}),
        "resolution": response.get("resolution", {}),
        "mapping_preview": _safe_mapping(response.get("mapping_preview")),
        "analysis_evaluation": response.get("analysis_evaluation"),
        "gpt_analysis_package_preview": _package_summary(response.get("gpt_analysis_package_preview")),
        "review": response.get("review", {}),
        "execution": response.get("execution", {}),
        "trace": {
            "schema_version": trace.get("schema_version", ""),
            "gate_status": trace.get("gate_status", ""),
            "planner_status": trace.get("planner_status", ""),
            "failure_category": trace.get("failure_category", ""),
        },
    }


class ReviewUIApplication:
    """Application object kept separate for deterministic HTTP tests."""

    def __init__(self, transport: ShadowTransport) -> None:
        self._fixture_dir = tempfile.TemporaryDirectory(prefix="fitness-ledger-review-ui-")
        tracker, dictionary = fixture(Path(self._fixture_dir.name))
        views = LedgerViewModels(tracker, dictionary)
        self.service = AnalysisPreviewService(views, transport)
        self.transport = transport

    def close(self) -> None:
        self._fixture_dir.cleanup()

    def health(self) -> dict[str, Any]:
        manifest = self.transport.read_manifest()
        return {
            "schema_version": UI_SCHEMA_VERSION,
            "ui": "local_review_only",
            "model": manifest.model,
            "model_available": manifest.available,
            "model_digest": manifest.digest,
            "executor_connected": False,
            "formal_data_connected": False,
        }

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = str(payload.get("request") or "").strip()[:2000]
        confirmations = payload.get("confirmations") if isinstance(payload.get("confirmations"), dict) else {}
        budget_mode = str(payload.get("budget_mode") or "standard")
        if budget_mode not in {"concise", "standard", "complete"}:
            budget_mode = "standard"
        return safe_ui_response(self.service.preview(request, confirmations, budget_mode))


def _handler(application: ReviewUIApplication):
    class Handler(BaseHTTPRequestHandler):
        server_version = "FitnessLedgerReviewUI/1.0"

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/health":
                self._json(200, application.health())
                return
            if path in {"/", "/index.html"}:
                body = (Path(__file__).with_name("review_ui").joinpath("index.html")).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/app.js":
                body = (Path(__file__).with_name("review_ui").joinpath("app.js")).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._json(404, {"error": "NOT_FOUND"})

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/preview":
                self._json(404, {"error": "NOT_FOUND"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    raise ValueError("invalid request size")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("request must be an object")
                self._json(200, application.preview(payload))
            except Exception as exc:  # the UI receives a stable error, no traceback
                self._json(400, {"error": "INVALID_REVIEW_REQUEST", "detail": str(exc)[:160]})

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    application = ReviewUIApplication(OllamaShadowTransport())
    server = ThreadingHTTPServer((args.host, args.port), _handler(application))
    print(f"Fitness Ledger Review UI: http://{args.host}:{args.port}")
    print("Anonymous fixture only; no formal data, Executor, Cloud, or Web app connection.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        application.close()


if __name__ == "__main__":
    main()
