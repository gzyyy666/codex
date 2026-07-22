"""Anonymous tests for the Intent semantic boundary and one shared Repair."""

from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.data_catalog import DateRangeResolver
from fitness_ledger_core.intelligent_export import IntelligentExportService
from fitness_ledger_core.intelligent_export_review_evidence import build_bundle
from fitness_ledger_core.intent_semantic_validator import IntentSemanticValidator, repair_diff
from fitness_ledger_core.local_model_adapter import FakeLocalModelAdapter
from fitness_ledger_core.shared_view_models import LedgerViewModels

from intelligent_export_core_test import fixture, intent, plan_for


def main() -> None:
    validator = IntentSemanticValidator()
    base = intent()
    for value in ("分析减脂", "fat loss", "减脂", "卧推"):
        sample = copy.deepcopy(base); sample["interpreted_goal"] = value
        assert validator.validate(sample).is_valid
    for value in ("?", "??", "？？", "。", "  ", "\ufffd", "����"):
        sample = copy.deepcopy(base); sample["interpreted_goal"] = value
        result = validator.validate(sample)
        assert not result.is_valid and result.error_codes
    for value in ("减脂", "卧推"):
        sample = copy.deepcopy(base); sample["interpreted_goal"] = value
        assert validator.validate(sample).is_valid
    sample = copy.deepcopy(base); sample["movement_mentions"] = [{"text": "胸", "confidence": 0.8, "body_part": "胸"}]
    assert validator.validate(sample).is_valid
    sample["movement_mentions"] = [{"text": "??", "confidence": 0.8, "body_part": ""}]
    assert "INTENT_MOVEMENT_MENTION_CORRUPTED" in validator.validate(sample).error_codes
    sample = copy.deepcopy(base); sample["movement_mentions"] = []; sample["date_intent"]["raw_date_mentions"] = []
    assert validator.validate(sample).is_valid
    sample["date_intent"]["raw_date_mentions"] = ["??"]
    assert "INTENT_DATE_MENTION_CORRUPTED" in validator.validate(sample).error_codes
    diff = repair_diff({**base, "interpreted_goal": "????"}, base, ["INTENT_PLACEHOLDER_ONLY"], [])
    assert diff["changed_field_paths"] == ["interpreted_goal"] and "before" in diff["field_snapshots"]["interpreted_goal"]
    assert "????" not in str(diff)

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-intent-semantic-") as name:
        tracker, dictionary = fixture(Path(name)); views = LedgerViewModels(tracker, dictionary)
        corrupt = copy.deepcopy(base); corrupt["interpreted_goal"] = "????"
        good_plan = plan_for(views)
        adapter = FakeLocalModelAdapter([corrupt, base, good_plan])
        with patch.object(DateRangeResolver, "extract_raw_date_mentions", wraps=DateRangeResolver.extract_raw_date_mentions) as resolver:
            result = IntelligentExportService(views, adapter).run("分析最近低碳训练")
        assert result["status"] == "ready", result
        assert len(adapter.calls) == 3
        assert resolver.call_count > 0
        assert result["diagnostics"]["repair"]["intent_semantic_status"] == "valid_after_repair"
        assert result["diagnostics"]["repair"]["intent_repair"]["changed_field_paths"] == ["interpreted_goal"]
        bundle = build_bundle([("semantic-repair", "分析最近低碳训练", result)])
        item = bundle["request_evidence"][0]
        assert item["repair"]["intent_semantic_status"] == "valid_after_repair"

        failed_adapter = FakeLocalModelAdapter([corrupt, corrupt])
        with patch.object(DateRangeResolver, "extract_raw_date_mentions", side_effect=AssertionError("DateResolver called before semantic validation")), patch("fitness_ledger_core.intelligent_export.CandidateSummarizer") as summarizer, patch("fitness_ledger_core.intelligent_export.DataCatalogBuilder.build", side_effect=AssertionError("Data Catalog built before semantic validation")) as catalog_build:
            failed = IntelligentExportService(views, failed_adapter).run("分析最近低碳训练")
        assert failed["status"] == "fallback"
        assert failed["trace"]["error_code"] == "MODEL_INTENT_SEMANTIC_INVALID"
        assert len(failed_adapter.calls) == 2
        summarizer.assert_not_called()
        catalog_build.assert_not_called()
        blocked = build_bundle([("semantic-invalid", "分析最近低碳训练", failed)])
        assert "REVIEW_INTENT_SEMANTIC_INVALID" in blocked["integrity_audit"]["blocking_integrity_codes"]
        assert blocked["privacy_audit"]["passed"]
    print("FITNESS_LEDGER_INTENT_SEMANTIC_VALIDATOR_OK")


if __name__ == "__main__":
    main()
