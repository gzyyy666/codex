"""Anonymous tests for the Web Analysis Export Protocol Service."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web_desktop.backend.analysis_export_protocol import (  # noqa: E402
    AnalysisExportProtocolService,
    AnonymousFixtureProvider,
    FormalReadOnlyProvider,
)
from fitness_ledger_core.formal_analysis_request_adapter import FormalAnalysisRequestAdapter  # noqa: E402


FIXTURE_DIR = ROOT / "tools" / "fixtures" / "analysis_export_anonymous"


def load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def service(fixture: dict | None = None) -> AnalysisExportProtocolService:
    return AnalysisExportProtocolService(AnonymousFixtureProvider(fixture or FIXTURE_DIR / "fixture.json"))


def test_validate_contract_and_provider_disabled() -> None:
    valid = load("requests.json")["body_recent_28"]
    result = service().validate({"request": valid})
    assert result["status"] == "valid"
    assert result["schema_version"] == "fitness-ledger-analysis-export-request-v1.1"
    assert result["execution"] == {"executor_called": False, "formal_data_written": False}
    assert result["request_interpreter_provider"] == {
        "provider_id": "local-qwen3", "enabled": False, "status": "not_connected"
    }

    unavailable = AnalysisExportProtocolService(FormalReadOnlyProvider())
    preview = unavailable.preview({"request": valid})
    assert preview["status"] == "formal_data_unavailable"
    assert preview["execution"] == {"executor_called": False, "formal_data_written": False}


def test_invalid_boundaries_are_reported_without_provider_calls() -> None:
    protocol = service()
    invalid = copy.deepcopy(load("requests.json")["body_recent_28"])
    invalid["datasets"][0]["fields"] = ["date", "unknown_field"]
    assert protocol.validate({"request": invalid})["status"] == "invalid"

    too_many = copy.deepcopy(load("requests.json")["body_recent_28"])
    too_many["datasets"] = [copy.deepcopy(too_many["datasets"][0]) for _ in range(9)]
    assert any(item["code"] == "TOO_MANY_DATASETS" for item in protocol.validate({"request": too_many})["errors"])

    raw = copy.deepcopy(load("requests.json")["body_recent_28"])
    raw["raw"] = True
    assert any(item["code"] == "RAW_PERMISSION_REQUIRED" for item in protocol.validate({"request": raw})["errors"])


def test_preview_resolution_progress_exclusion_and_confirmation() -> None:
    fixture = load("fixture.json")
    fixture = copy.deepcopy(fixture)
    next(item for item in fixture["movement_catalog"] if item["movement_id"] == "m_synthetic_fly")["exclude_from_progress"] = True
    movement = load("requests.json")["movement_body_part_selector"]
    movement["datasets"][0]["filters"]["movement_selector"]["value"] = "back"
    protocol = service(fixture)
    context_id = "multi-batch-test-context"
    preview = protocol.preview({"request": movement, "preview_context_id": context_id})
    assert preview["status"] == "preview_ready", preview
    assert preview["preview"]["movement_body_part_resolution"][0]["status"] == "resolved"
    assert preview["preview"]["progress_exclusion_count"] == 0

    excluded_request = copy.deepcopy(load("requests.json")["movement_latest_3_id"])
    excluded_request["datasets"][0]["filters"]["movement_selector"]["value"] = "m_synthetic_fly"
    excluded_preview = protocol.preview({"request": excluded_request, "preview_context_id": context_id})
    assert excluded_preview["status"] == "preview_ready"
    assert excluded_preview["preview"]["progress_exclusion_count"] == 1

    mismatch = protocol.export({"request": movement, "confirmed": True, "confirmation_token": "wrong"})
    assert mismatch["status"] == "confirmation_mismatch"

    token = preview["confirmation_token"]
    changed = copy.deepcopy(movement)
    changed["purpose"] = "changed after preview"
    assert protocol.export({"request": changed, "confirmed": True, "confirmation_token": token, "preview_context_id": context_id})["status"] == "confirmation_mismatch"

    exported = protocol.export({"request": movement, "confirmed": True, "confirmation_token": token, "preview_context_id": context_id})
    assert exported["status"] == "bundle_ready", exported
    assert exported["safety_flags"] == {
        "raw_included": False, "executor_called": False, "formal_data_written": False
    }
    for format_name in ("json", "markdown"):
        artifact = protocol.artifact(exported["artifact_id"], format_name)
        assert artifact is not None
        assert artifact[1]
    assert protocol.export({
        "request": movement,
        "confirmed": True,
        "confirmation_token": token,
        "preview_context_id": context_id,
    })["status"] == "confirmation_mismatch"


def test_new_preview_context_invalidates_old_plan() -> None:
    protocol = service()
    old_request = load("requests.json")["body_recent_28"]
    new_request = load("requests.json")["diet_recent_14"]
    old_preview = protocol.preview({"request": old_request, "preview_context_id": "old-plan"})
    assert protocol.invalidate_preview_context("old-plan") == 1
    new_preview = protocol.preview({"request": new_request, "preview_context_id": "new-plan"})
    assert old_preview["status"] == "preview_ready"
    assert new_preview["status"] == "preview_ready"
    assert protocol.export({
        "request": old_request,
        "confirmed": True,
        "confirmation_token": old_preview["confirmation_token"],
        "preview_context_id": "old-plan",
    })["status"] == "confirmation_mismatch"
    assert protocol.export({
        "request": new_request,
        "confirmed": True,
        "confirmation_token": new_preview["confirmation_token"],
        "preview_context_id": "new-plan",
    })["status"] == "bundle_ready"


def test_ambiguous_movement_requires_resolution() -> None:
    protocol = service()
    ambiguous = load("resolution_requests.json")["movement_name_ambiguous"]
    preview = protocol.preview({"request": ambiguous})
    assert preview["status"] == "movement_resolution_required"
    assert len(preview["errors"][0]["candidates"]) == 2
    assert protocol.resolve({"selector": {"kind": "movement_name", "value": "Synthetic Press Ambiguous"}})["status"] == "movement_resolution_required"


def test_natural_language_request_feeds_direct_bundle_export() -> None:
    cases = json.loads(
        (FIXTURE_DIR / "natural_language_routing_cases.json").read_text(encoding="utf-8")
    )
    case = next(item for item in cases if item["id"] == "ready_body_phrase")
    natural = FormalAnalysisRequestAdapter().preview(case["text"])
    assert natural["status"] == "ready", natural

    protocol = service()
    preview = protocol.preview({"request": natural["request"]})
    assert preview["status"] == "preview_ready", preview
    exported = protocol.export({
        "request": natural["request"],
        "confirmed": True,
        "confirmation_token": preview["confirmation_token"],
    })
    assert exported["status"] == "bundle_ready", exported
    assert protocol.artifact(exported["artifact_id"], "json")[1]


def test_frontend_uses_only_v1_protocol_controls() -> None:
    app = (ROOT / "web_desktop" / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "analysisExportProtocolPage" in app
    assert "/api/analysis-export/v1/validate" in app
    assert "/api/analysis-export/v1/preview" in app
    assert "/api/analysis-export/v1/export" in app
    assert "data-analysis-export-confirm" in app
    assert 'data-analysis-export-mode="json"' in app
    assert 'data-analysis-export-mode="guided"' in app
    assert "analysis-export-scope-digest" in app
    assert "protocol-composer-tools" in app
    assert "exportFormalSemanticDataPackage" in app
    assert "supersedes_preview_context_id" in app
    assert "preview_context_id:preview.preview_context_id" in app
    assert "/api/analysis-export/v1/artifact/" in app
    assert "导出数据包" in app
    assert "QUICK EXAMPLES" not in app
    assert "data-analysis-export-natural-use" not in app
    assert "???" not in app


def main() -> None:
    test_validate_contract_and_provider_disabled()
    test_invalid_boundaries_are_reported_without_provider_calls()
    test_preview_resolution_progress_exclusion_and_confirmation()
    test_new_preview_context_invalidates_old_plan()
    test_ambiguous_movement_requires_resolution()
    test_natural_language_request_feeds_direct_bundle_export()
    test_frontend_uses_only_v1_protocol_controls()
    print("FITNESS_LEDGER_ANALYSIS_EXPORT_PROTOCOL_WEB_OK")


if __name__ == "__main__":
    main()
