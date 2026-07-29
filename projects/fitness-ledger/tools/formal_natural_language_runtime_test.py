"""Real read-only HTTP acceptance for natural-language Analysis Export.

This script requires an explicit FITNESS_LEDGER_FORMAL_DIR. It never substitutes
an anonymous fixture and keeps downloaded artifacts in memory.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import threading
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.formal_analysis_request_adapter import (  # noqa: E402
    FormalAnalysisRequestAdapter,
)
from fitness_ledger_core.formal_analysis_request_preview_service import (  # noqa: E402
    FormalAnalysisRequestPreviewService,
)
from fitness_ledger_core.formal_readonly_data_source import (  # noqa: E402
    FormalReadOnlyDataSource,
)
from web_desktop.backend.analysis_export_protocol import (  # noqa: E402
    AnalysisExportProtocolService,
)
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


CASES = (
    "导出最近28天体重",
    "导出最近14天饮食",
    "导出最近三次训练和每次训练前三天的饮食",
)
MOVEMENT_RESOLUTION_CASE = "导出最近三次杠铃卧推的组数、次数和负重"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _post(base_url: str, path: str, value: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
    request = Request(
        base_url + path,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _get(base_url: str, path: str) -> tuple[str, bytes]:
    with urlopen(base_url + path, timeout=30) as response:
        return response.headers.get_content_type(), response.read()


def _formal_paths() -> tuple[Path, Path]:
    configured = os.environ.get("FITNESS_LEDGER_FORMAL_DIR", "").strip()
    if not configured:
        raise RuntimeError(
            "FITNESS_LEDGER_FORMAL_DIR is required; no fixture fallback is allowed."
        )
    root = Path(configured).expanduser().resolve()
    data_root = root / "data" if (root / "data").is_dir() else root
    tracker = data_root / "tracker.json"
    dictionary = data_root / "movement_dictionary.json"
    if not tracker.is_file() or not dictionary.is_file():
        raise RuntimeError("Configured formal tracker or movement dictionary is missing.")
    return tracker, dictionary


def main() -> None:
    tracker, dictionary = _formal_paths()
    before = {"tracker": _sha256(tracker), "dictionary": _sha256(dictionary)}
    unconfigured = AnalysisExportProtocolService.from_environment({})
    assert unconfigured.provider.formal_data_available is False
    assert unconfigured.provider.availability_status == "not_configured"
    incomplete = AnalysisExportProtocolService.from_environment(
        {"FITNESS_LEDGER_FORMAL_TRACKER_PATH": str(tracker)}
    )
    assert incomplete.provider.formal_data_available is False
    assert incomplete.provider.availability_status == "incomplete_configuration"
    invalid = AnalysisExportProtocolService.from_environment(
        {
            "FITNESS_LEDGER_FORMAL_TRACKER_PATH": str(tracker) + ".missing",
            "FITNESS_LEDGER_FORMAL_MOVEMENT_DICTIONARY_PATH": str(dictionary),
        }
    )
    assert invalid.provider.formal_data_available is False
    assert invalid.provider.availability_status == "invalid_configuration"
    provider = FormalReadOnlyDataSource(tracker, dictionary)
    assert provider.formal_data_available
    assert provider.source_kind == "formal_local_json_read_only"

    service = LedgerWebService.__new__(LedgerWebService)
    service.formal_analysis_preview = FormalAnalysisRequestPreviewService(
        FormalAnalysisRequestAdapter()
    )
    service.analysis_export_protocol = AnalysisExportProtocolService(provider)
    server = create_server(port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    summaries: list[dict[str, Any]] = []
    try:
        for text in CASES:
            natural = _post(
                base_url,
                "/api/analysis-export/v1/natural-language/preview",
                {"text": text},
            )
            assert natural["status"] == "ready", natural
            assert natural["route"] == "deterministic", natural
            assert natural["provider_called"] is False, natural
            assert natural["request"]["raw"] is False, natural
            assert natural["validation"]["valid"] is True, natural
            assert natural["execution"]["executor_called"] is False, natural
            assert natural["execution"]["formal_data_written"] is False, natural

            preview = _post(
                base_url,
                "/api/analysis-export/v1/preview",
                {"request": natural["request"]},
            )
            assert preview["status"] == "preview_ready", preview
            assert preview["preview"]["formal_data_available"] is True, preview
            assert preview["preview"]["source_kind"] == provider.source_kind, preview
            assert preview["preview"]["record_count"] > 0, preview
            assert preview["execution"] == {
                "executor_called": False,
                "formal_data_written": False,
            }

            exported = _post(
                base_url,
                "/api/analysis-export/v1/export",
                {
                    "request": natural["request"],
                    "confirmation_token": preview["confirmation_token"],
                    "confirmed": True,
                },
            )
            assert exported["status"] == "bundle_ready", exported
            assert exported["formats"] == ["json", "markdown"], exported
            assert exported["safety_flags"] == {
                "raw_included": False,
                "executor_called": False,
                "formal_data_written": False,
            }

            artifact_id = exported["artifact_id"]
            json_type, json_body = _get(
                base_url,
                "/api/analysis-export/v1/artifact/"
                + artifact_id
                + "?"
                + urlencode({"format": "json"}),
            )
            markdown_type, markdown_body = _get(
                base_url,
                "/api/analysis-export/v1/artifact/"
                + artifact_id
                + "?"
                + urlencode({"format": "markdown"}),
            )
            bundle = json.loads(json_body.decode("utf-8"))
            assert json_type == "application/json"
            assert markdown_type == "text/markdown"
            assert markdown_body
            assert bundle["request"]["raw"] is False
            assert bundle["safety_flags"] == exported["safety_flags"]
            assert bundle["provenance"]["source_kind"] == provider.source_kind
            summaries.append(
                {
                    "text": text,
                    "natural_status": natural["status"],
                    "preview_status": preview["status"],
                    "export_status": exported["status"],
                    "record_count": exported["record_count"],
                    "formats": exported["formats"],
                }
            )

        movement_resolution = _post(
            base_url,
            "/api/analysis-export/v1/natural-language/preview",
            {"text": MOVEMENT_RESOLUTION_CASE},
        )
        assert movement_resolution["status"] == "PREVIEW_READY_RESOLUTION_REQUIRED", movement_resolution
        assert movement_resolution["resolution"]["next"] == "movement_resolver_or_user_confirmation"
        assert movement_resolution["execution"]["executor_called"] is False
        summaries.append(
            {
                "text": MOVEMENT_RESOLUTION_CASE,
                "natural_status": movement_resolution["status"],
                "preview_status": "not_started",
                "export_status": "blocked_until_resolution",
            }
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    after = {"tracker": _sha256(tracker), "dictionary": _sha256(dictionary)}
    assert after == before, {"before": before, "after": after}
    print(
        json.dumps(
            {
                "status": "FORMAL_NATURAL_LANGUAGE_RUNTIME_OK",
                "cases": summaries,
                "source_kind": provider.source_kind,
                "formal_hashes_unchanged": True,
                "executor_called": False,
                "formal_data_written": False,
                "raw": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
