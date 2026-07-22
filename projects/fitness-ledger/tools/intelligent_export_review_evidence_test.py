"""Anonymous tests for the deterministic Intelligent Export review evidence contract."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fitness_ledger_core.intelligent_export import IntelligentExportService
from fitness_ledger_core.intelligent_export_review_evidence import build_bundle, privacy_audit
from fitness_ledger_core.local_model_adapter import FakeLocalModelAdapter
from fitness_ledger_core.shared_view_models import LedgerViewModels

from intelligent_export_core_test import fixture, intent, plan_for


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-review-evidence-") as name:
        root = Path(name)
        tracker, dictionary = fixture(root)
        views = LedgerViewModels(tracker, dictionary)
        adapter = FakeLocalModelAdapter([intent(), plan_for(views)])
        result = IntelligentExportService(views, adapter).run("比较最近肩部训练、饮食和体重变化", "concise")
        assert result["status"] == "ready"
        assert result["output"]["execution_evidence"]["progress_history_count"] == len(result["output"]["execution_evidence"]["progress_history_ids"])
        bundle = build_bundle([("review", "比较最近肩部训练、饮食和体重变化", result)], [result, result, result])
        assert bundle["review_status"] == "ready", bundle["integrity_audit"]
        assert bundle["privacy_audit"]["passed"]
        assert all(len(item["snippet"]) <= 80 for item in bundle["request_evidence"][0]["candidates"]["notes"])
        assert "progress" not in bundle["request_evidence"][0]["execution"]
        evidence = bundle["request_evidence"][0]
        assert evidence["intent"]["target_body_parts"] == ["SHOULDER"]
        assert evidence["candidates"]["target_scope"]["direct_body_part_ids"] == ["SHOULDER"]
        assert {item["candidate_role"] for item in evidence["candidates"]["movements"]} <= {"EXPLICIT_TARGET", "BODY_PART_TARGET"}
        assert evidence["selection"]["target_coverage_status"] == "covered"
        assert evidence["execution"]["target_progress_history_ids"]
        assert bundle["stability_comparison"]["common_note_ids"]

        missing_execution = copy.deepcopy(result)
        missing_execution["output"].pop("execution_evidence")
        blocked = build_bundle([("review", "比较最近肩部训练、饮食和体重变化", missing_execution)])
        assert blocked["review_status"] == "blocked"
        assert "REVIEW_EXECUTION_IDS_MISSING" in blocked["integrity_audit"]["blocking_integrity_codes"]
        assert "REVIEW_PROGRESS_FIELD_MISMATCH" in blocked["integrity_audit"]["blocking_integrity_codes"]

        bad_intent = copy.deepcopy(result)
        bad_intent["intent"]["interpreted_goal"] = "????????"
        blocked_intent = build_bundle([("review", "比较最近肩部训练、饮食和体重变化", bad_intent)])
        assert "REVIEW_INTENT_INVALID" in blocked_intent["integrity_audit"]["blocking_integrity_codes"]

        bad_selection = copy.deepcopy(result)
        bad_selection["selection"]["selected_movements"][0]["movement_id"] = "UNKNOWN"
        blocked_selection = build_bundle([("review", "比较最近肩部训练、饮食和体重变化", bad_selection)])
        assert "REVIEW_SELECTED_ID_NOT_IN_CANDIDATES" in blocked_selection["integrity_audit"]["blocking_integrity_codes"]

        # Repair evidence must preserve the structural diff without exposing a prompt.
        repair_adapter = FakeLocalModelAdapter([intent(), plan_for(views, invalid=True), plan_for(views)])
        repaired = IntelligentExportService(views, repair_adapter).run("比较最近肩部训练", "concise")
        repair = repaired["diagnostics"].get("repair", {})
        assert repaired["status"] == "ready" and repair.get("repair_used")
        assert repair.get("original_validation_codes")
        assert "raw_text" not in json.dumps(repair, ensure_ascii=False)

        assert privacy_audit({"snippet": "ok"})["passed"]
        assert not privacy_audit({"snippet": "x" * 81})["passed"]
    print("FITNESS_LEDGER_INTELLIGENT_EXPORT_REVIEW_EVIDENCE_OK")


if __name__ == "__main__":
    main()
