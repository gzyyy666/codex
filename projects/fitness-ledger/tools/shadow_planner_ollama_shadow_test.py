"""Anonymous qwen3:4b shadow evaluation; never invokes formal export execution."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.data_catalog import DataCatalogBuilder  # noqa: E402
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from fitness_ledger_core.shadow_planner import (  # noqa: E402
    SHADOW_ENDPOINT,
    SHADOW_MODEL,
    DeterministicBaseline,
    OllamaShadowTransport,
    ShadowEvaluationMatrix,
    ShadowPlannerRunner,
)
from intelligent_export_core_test import fixture  # noqa: E402


MATRIX = ROOT / "tools" / "fixtures" / "intelligent_export_shadow_matrix.json"


def main() -> None:
    transport = OllamaShadowTransport()
    manifest = transport.read_manifest()
    print(json.dumps({"endpoint": manifest.endpoint, "model": manifest.model, "available": manifest.available, "digest": manifest.digest, "error_code": manifest.error_code}, ensure_ascii=False, sort_keys=True))
    if not manifest.available:
        print("FITNESS_LEDGER_QWEN_SHADOW_MODEL_UNAVAILABLE")
        return
    assert manifest.endpoint == SHADOW_ENDPOINT
    assert manifest.model == SHADOW_MODEL
    assert manifest.digest

    matrix = ShadowEvaluationMatrix.load(MATRIX)
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-qwen-shadow-") as name:
        tracker, dictionary = fixture(Path(name))
        views = LedgerViewModels(tracker, dictionary)
        catalog = DataCatalogBuilder(views).build()
        baseline = DeterministicBaseline(views, catalog)
        report = ShadowPlannerRunner(transport).run_matrix(
            matrix,
            baseline,
            {"coverage": {"modules": ["body", "diet", "training"], "mode": "anonymous_aggregate"}},
        )

    assert report.model == SHADOW_MODEL and report.model_digest == manifest.digest
    allowed = {"ABSTAIN", "INVALID", "MODEL_UNAVAILABLE", "SAFE_FALLBACK", "VALIDATED"}
    assert {item.final_status for item in report.case_records} <= allowed
    serialized = json.dumps(report.to_dict(), ensure_ascii=False)
    assert "raw_text" not in serialized
    assert "record_id" not in serialized
    print(json.dumps({"report_id": report.report_id, "model_digest": report.model_digest, "total_cases": report.total_cases, "metrics": report.metrics, "error_sources": report.error_sources}, ensure_ascii=False, sort_keys=True))
    print("FITNESS_LEDGER_QWEN_SHADOW_OK")


if __name__ == "__main__":
    main()
