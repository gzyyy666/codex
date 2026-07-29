"""Anonymous contract checks for the controlled natural-language export preview."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.formal_analysis_request_adapter import FormalAnalysisRequestAdapter  # noqa: E402
from fitness_ledger_core.formal_analysis_request_preview_service import FormalAnalysisRequestPreviewService  # noqa: E402
from web_desktop.backend.server import LedgerWebService  # noqa: E402


def web_service() -> LedgerWebService:
    service = LedgerWebService.__new__(LedgerWebService)
    service.formal_analysis_preview = FormalAnalysisRequestPreviewService(FormalAnalysisRequestAdapter())
    return service


def test_input_boundaries() -> None:
    service = web_service()
    assert service.analysis_export_natural_language_preview({"text": ""})["status"] == "invalid_request"
    assert service.analysis_export_natural_language_preview({"text": 42})["errors"][0]["code"] == "TEXT_MUST_BE_STRING"
    assert service.analysis_export_natural_language_preview({"text": "x" * 501})["errors"][0]["code"] == "TEXT_TOO_LONG"


def test_deterministic_ready_and_fail_closed() -> None:
    service = web_service()
    ready = service.analysis_export_natural_language_preview({"text": "导出最近28天体重"})
    assert ready["status"] == "ready", ready
    assert ready["provider_called"] is False
    assert ready["request"]["raw"] is False
    assert ready["execution"]["executor_called"] is False

    cross_dataset = service.analysis_export_natural_language_preview({"text": "分析最近一个月训练和饮食"})
    assert cross_dataset["status"] in {"needs_confirmation", "planner_required"}
    assert cross_dataset["provider_called"] is False

    assert service.analysis_export_natural_language_preview({"text": "导出原始记录"})["status"] == "unsupported"
    assert service.analysis_export_natural_language_preview({"text": "删除昨天的训练"})["status"] == "unsupported"


def test_frontend_wires_preview_only_boundary() -> None:
    app = (ROOT / "web_desktop" / "frontend" / "app.js").read_text(encoding="utf-8")
    focused_page = app[app.rfind("function analysisExportProtocolPage()") : app.index("function setAnalysisExportProtocolMode")]
    assert "/api/analysis-export/v1/natural-language/preview" in app
    assert "data-analysis-export-natural-preview" in app
    assert "await useFormalSemanticRequest()" in app
    assert "await previewAnalysisExportProtocol()" in app
    assert "生成数据预览" in focused_page
    assert "确认并导出" in focused_page
    assert "高级入口" in focused_page
    assert "QUICK EXAMPLES" not in focused_page
    assert "data-analysis-export-natural-example" not in focused_page


def main() -> None:
    test_input_boundaries()
    test_deterministic_ready_and_fail_closed()
    test_frontend_wires_preview_only_boundary()
    print("FITNESS_LEDGER_FORMAL_LOCAL_SEMANTIC_HINT_WEB_OK")


if __name__ == "__main__":
    main()
