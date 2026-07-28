"""Deterministic IntentCompiler unit tests using hand-written Intent fixtures."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fitness_ledger_core.data_catalog import DataCatalogBuilder
from fitness_ledger_core.intelligent_export_models import IntentSpec
from fitness_ledger_core.intent_compiler import IntentCompileError, IntentCompiler, ScopeFence
from fitness_ledger_core.shared_view_models import LedgerViewModels
from intelligent_export_core_test import fixture


def intent(dimensions, *, excluded=None, date_text=None, movements=None, parts=None, ambiguous=False):
    return IntentSpec.from_dict({
        "schema_version": "fitness-ledger-intelligent-export-intent-v2",
        "dimensions": dimensions,
        "excluded_dimensions": excluded or [],
        "date_text": date_text or [],
        "movement_mentions": movements or [],
        "target_body_parts": parts or [],
        "ambiguous": ambiguous,
    })


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-compiler-") as name:
        tracker, dictionary = fixture(Path(name))
        views = LedgerViewModels(tracker, dictionary)
        catalog = DataCatalogBuilder(views).build()
        compiler = IntentCompiler(views)

        _, package, draft = compiler.compile("分析最近的饮食和体重变化", intent(["body_state", "diet_macros"], date_text=["最近"]), catalog)
        assert draft.selected_modules == ["body", "diet"]
        assert draft.selected_fields["body"] == ["Date", "Weight (kg)"]
        assert draft.selected_fields["diet"] == ["Date", "Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)"]
        assert not draft.selected_movements
        assert package.windows

        _, _, draft = compiler.compile("分析最近低碳是否导致侧平举表现下降", intent(["diet_macros", "training_context", "movement_progress"], movements=["侧平举"]), catalog)
        assert draft.selected_modules == ["diet", "movement_progress"]
        assert draft.selected_movements == ["SHOULDER_001"]

        fenced = ScopeFence.apply("只看饮食宏量，不要训练", intent(["diet_macros", "training_context", "movement_progress"]))
        assert fenced.dimensions == ["diet_macros"]
        assert "training_context" in fenced.excluded_dimensions

        try:
            compiler.compile("看看最近动作进步", intent(["movement_progress"]), catalog)
        except IntentCompileError as exc:
            assert exc.code in {"UNRESOLVED_REQUIRED_MOVEMENT", "REQUEST_NOT_UNDERSTOOD"}
        else:
            raise AssertionError("unresolved movement scope was accepted")

        try:
            compiler.compile("查看原始记录", intent(["raw_trace"]), catalog)
        except IntentCompileError:
            raise AssertionError("explicit raw request should compile to a bounded raw plan")
    print("FITNESS_LEDGER_INTENT_COMPILER_OK")


if __name__ == "__main__":
    main()
