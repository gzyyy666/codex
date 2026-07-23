"""End-to-end deterministic scope tests; the model response is hand-written."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fitness_ledger_core.intelligent_export import IntelligentExportService
from fitness_ledger_core.local_model_adapter import FakeLocalModelAdapter
from fitness_ledger_core.shared_view_models import LedgerViewModels
from intelligent_export_core_test import fixture


def intent(dimensions, *, evidence=None):
    return {
        "schema_version": "fitness-ledger-semantic-hints-v1",
        "semantic_hints": [{"dimension": dimension, "evidence": (evidence or {}).get(dimension, dimension)} for dimension in dimensions],
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-e2e-") as name:
        tracker, dictionary = fixture(Path(name))
        views = LedgerViewModels(tracker, dictionary)

        adapter = FakeLocalModelAdapter([intent(["body_state", "diet_macros"], evidence={"body_state": "体重", "diet_macros": "饮食"})])
        result = IntelligentExportService(views, adapter).run("分析最近饮食和体重，不要训练")
        assert result["status"] == "ready", result
        assert result["diagnostics"]["model_call_count"] == 0
        assert result["diagnostics"]["planner_called"] is False
        assert result["diagnostics"]["repair_called"] is False
        assert set(result["plan"]["selected_modules"]) == {"body", "diet"}
        assert result["output"]["payload"]["training"] == []
        assert result["output"]["payload"]["movements"] == []
        assert result["output"]["payload"]["raw_entries"] == []
        assert adapter.calls == []

        adapter = FakeLocalModelAdapter([intent(["movement_progress"], evidence={"movement_progress": "侧平举进步"})])
        result = IntelligentExportService(views, adapter).run("看看最近侧平举进步")
        assert result["status"] == "ready", result
        assert adapter.calls == []
        assert result["plan"]["selected_movements"] == ["SHOULDER_001"]
        assert result["output"]["payload"]["diet"] == []
        assert result["output"]["payload"]["body"] == []

        adapter = FakeLocalModelAdapter([intent([])])
        result = IntelligentExportService(views, adapter).run("帮我看看最近怎么样")
        assert result["status"] == "safe_fallback"
        assert adapter.calls == []
        assert "output" not in result
    print("FITNESS_LEDGER_INTENT_E2E_SCOPE_OK")


if __name__ == "__main__":
    main()
