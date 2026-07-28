"""Fail-closed ExportPlanValidator and Executor safety tests."""

from __future__ import annotations

import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fitness_ledger_core.data_catalog import DataCatalogBuilder
from fitness_ledger_core.export_plan_validator import ExportPlanValidator, PlanValidationError
from fitness_ledger_core.intelligent_export import ExportExecutor
from fitness_ledger_core.intelligent_export_models import ContractError, ExportPlanDraft, PlanExplanation
from fitness_ledger_core.intent_compiler import IntentCompiler
from fitness_ledger_core.shared_view_models import LedgerViewModels
from intelligent_export_core_test import fixture
from intent_compiler_test import intent


def rejects(validator, draft, package, request, code):
    try:
        validator.validate(draft, package, request, trim=False)
    except PlanValidationError as exc:
        assert exc.code == code, (code, exc.code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-safety-") as name:
        tracker, dictionary = fixture(Path(name))
        views = LedgerViewModels(tracker, dictionary)
        catalog = DataCatalogBuilder(views).build()
        compiler = IntentCompiler(views)
        _, package, draft = compiler.compile("看看最近体重趋势", intent(["body_state"]), catalog)
        validator = ExportPlanValidator()

        try:
            ExportPlanDraft.from_dict({**draft.to_dict(), "unexpected": True})
        except ContractError:
            pass
        else:
            raise AssertionError("plan extra field was accepted")

        rejects(validator, replace(draft, selected_fields={"body": []}), package, "体重趋势", "EMPTY_SELECTED_FIELDS")
        rejects(validator, replace(draft, selected_modules=["movement_progress"], selected_fields={"movement_progress": ["date"]}, selected_movements=[]), package, "动作进步", "EMPTY_SELECTED_MOVEMENTS")
        rejects(validator, replace(draft, selected_fields={"body": ["unknown"]}), package, "体重趋势", "UNKNOWN_FIELD_ID")
        rejects(validator, replace(draft, selected_modules=["unknown"], selected_fields={"unknown": ["Date"]}), package, "体重趋势", "UNKNOWN_MODULE_ID")
        rejects(validator, replace(draft, selected_movements=["movement:not-supplied"]), package, "体重趋势", "UNKNOWN_MOVEMENT_ID")
        rejects(validator, replace(draft, candidate_record_ids=["record:not-supplied"]), package, "体重趋势", "UNKNOWN_RECORD_ID")
        _, raw_package, raw_draft = compiler.compile("查看原始记录", intent(["raw_trace"], date_text=["最近"]), catalog)
        rejects(validator, replace(raw_draft, include_raw_entries=True), raw_package, "体重趋势", "RAW_NOT_EXPLICIT")

        plan = validator.validate(draft, package, "看看最近体重趋势", trim=False)
        broken = replace(plan, selected_fields={"body": []})
        explanation = PlanExplanation("体重趋势", "体重趋势", plan.date_range, plan.selected_modules, plan.selected_fields, plan.selected_movements, plan.notes_selection, {}, {}, [], 0, 1.0, False, False, False)
        try:
            ExportExecutor(views).execute(broken, package, explanation)
        except PlanValidationError as exc:
            assert exc.code == "EMPTY_SELECTED_FIELDS"
        else:
            raise AssertionError("executor expanded empty fields into full rows")
    print("FITNESS_LEDGER_INTENT_EXECUTOR_SAFETY_OK")


if __name__ == "__main__":
    main()
