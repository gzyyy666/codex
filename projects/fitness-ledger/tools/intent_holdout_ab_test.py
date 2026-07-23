"""Blind holdout and ablation acceptance for Grounded Semantic Intent v3."""

from __future__ import annotations

import json
import argparse
import re
import sys
import tempfile
import time
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fitness_ledger_core.data_catalog import DataCatalogBuilder
from fitness_ledger_core.export_plan_validator import ExportPlanValidator, PlanValidationError
from fitness_ledger_core.intelligent_export import ExportExecutor, PlanExplanation
from fitness_ledger_core.intelligent_export_models import ContractError, SemanticHints
from fitness_ledger_core.intent_compiler import IntentCompileError, IntentCompiler
from fitness_ledger_core.intent_interpreter import IntentInterpreter, parse_json_object
from fitness_ledger_core.local_model_adapter import LocalModelError, OllamaNativeAdapter
from fitness_ledger_core.shared_view_models import LedgerViewModels

from intent_real_acceptance import CASES as REGRESSION_CASES, RecordingAdapter, fixture


HOLDOUT_FILE = Path(__file__).resolve().parent / "fixtures" / "intent_holdout_cases.json"
OUTPUT_DIR = Path(__file__).resolve().parent / "test_outputs" / "grounded_semantic_intent_v3_holdout"
DIMENSION_MODULES = {
    "body_state": "body",
    "diet_macros": "diet",
    "training_context": "training",
    "movement_progress": "movement_progress",
    "daily_notes": "notes",
    "diet_notes": "notes",
    "training_notes": "notes",
    "movement_notes": "notes",
    "raw_trace": "raw_entries",
}
SAFE_ERRORS = {"REQUEST_NOT_UNDERSTOOD", "NO_SAFE_SCOPE", "UNRESOLVED_REQUIRED_MOVEMENT", "NO_VALID_WINDOW"}


def normalized(text: str) -> str:
    return "".join(char.casefold() for char in str(text or "") if char.isalnum())


def load_cases() -> list[dict]:
    cases = json.loads(HOLDOUT_FILE.read_text(encoding="utf-8"))
    assert len(cases) == 60, len(cases)
    assert len({item["case_id"] for item in cases}) == 60
    old = {normalized(request) for _, request, _ in REGRESSION_CASES}
    duplicates = [item["case_id"] for item in cases if normalized(item["request"]) in old]
    assert not duplicates, duplicates
    return cases


def scope_snapshot(result: dict) -> dict:
    plan = result.get("plan", {}) if isinstance(result, dict) else {}
    intent = result.get("intent", {}) if isinstance(result, dict) else {}
    payload = result.get("output", {}).get("payload", {}) if isinstance(result, dict) else {}
    return {
        "dimensions": list(intent.get("dimensions", [])),
        "excluded_dimensions": list(intent.get("excluded_dimensions", [])),
        "date_expression": list(intent.get("date_text", [])),
        "modules": list(plan.get("selected_modules", [])),
        "fields": dict(plan.get("selected_fields", {})),
        "movement_mentions": list(intent.get("movement_mentions", [])),
        "target_body_parts": list(intent.get("target_body_parts", [])),
        "movement_ids": list(plan.get("selected_movements", [])),
        "notes_scopes": sorted({str(item.get("scope", "")) for item in payload.get("notes", []) if item.get("scope")}),
        "raw_allowed": bool(plan.get("include_raw_entries")),
    }


def deterministic_facts(compiler: IntentCompiler, request: str, catalog) -> dict:
    facts = compiler.prepare(request, catalog)
    cards = {item.canonical_name: item for item in catalog.movements}
    movement_candidates = []
    for mention in facts.query_scope.explicit_movement_mentions:
        matches = compiler.movement_resolver.resolve(
            __import__("fitness_ledger_core.intelligent_export_models", fromlist=["MovementMention"]).MovementMention(mention, 1.0),
            list(catalog.movements),
        )
        movement_candidates.append({"mention": mention, "matches": matches})
    return facts, {
        "scope": facts.to_model_context().get("scope", {}),
        "dimensions": list(facts.dimensions),
        "date_expression": list(facts.date_text),
        "notes_scope": list(facts.notes_scopes),
        "body_parts": list(facts.query_scope.target_body_part_ids),
        "movement_mentions": list(facts.query_scope.explicit_movement_mentions),
        "movement_candidates": movement_candidates,
        "movement_ambiguity": bool(facts.movement_ambiguous),
        "raw_explicit": bool(facts.raw_requested),
        "date_kind": facts.command.date.kind if facts.command else "none",
        "command_status": facts.command.status if facts.command else "unknown",
    }


def plan_from_hints(views, request: str, hints: SemanticHints) -> dict:
    started = time.monotonic()
    try:
        catalog = DataCatalogBuilder(views).build()
        compiler = IntentCompiler(views)
        facts, fact_record = deterministic_facts(compiler, request, catalog)
        compiled_intent, package, draft = compiler.compile(request, hints, catalog, "standard", facts)
        validator = ExportPlanValidator()
        trace_id = f"holdout:{int(time.time() * 1000000)}"
        plan = validator.validate(draft, package, request, trace_id, trim=False)
        explanation = PlanExplanation(
            request[:2000], plan.interpreted_goal, plan.date_range, plan.selected_modules,
            plan.selected_fields, plan.selected_movements, plan.notes_selection,
            plan.inclusion_reasons, plan.exclusion_reasons, plan.missing_data_warnings,
            plan.estimated_output_size, 1.0, False, plan.trimmed, False,
        )
        executed = ExportExecutor(views).execute(plan, package, explanation)
        result = {
            "status": "ready", "intent": compiled_intent.to_dict(), "plan": plan.to_dict(),
            "output": {"payload": {"notes": [{"scope": item.get("scope", "")} for item in executed.get("payload", {}).get("notes", [])]}},
        }
        return result, fact_record, int((time.monotonic() - started) * 1000), ""
    except (IntentCompileError, PlanValidationError, ContractError, LocalModelError) as exc:
        return {"status": "safe_fallback", "error_code": getattr(exc, "code", "NO_SAFE_PLAN"), "error": str(exc)[:240]}, locals().get("fact_record", {}), int((time.monotonic() - started) * 1000), type(exc).__name__
    except Exception as exc:
        return {"status": "safe_fallback", "error_code": "NO_SAFE_PLAN", "error": str(exc)[:240]}, locals().get("fact_record", {}), int((time.monotonic() - started) * 1000), type(exc).__name__


def run_deterministic(views, request: str) -> dict:
    result, facts, duration, error_type = plan_from_hints(views, request, SemanticHints([]))
    return {
        "mode": "DETERMINISTIC_ONLY", "status": result.get("status"), "error_code": result.get("error_code", ""),
        "error_type": error_type, "deterministic": facts, "model_raw_hints": None,
        "accepted_hints": [], "rejected_hints": [], "hint_changed_scope": False,
        "final_scope": scope_snapshot(result), "model_call_count": 0, "duration_ms": duration,
    }


def run_full(views, request: str) -> dict:
    started = time.monotonic()
    catalog = DataCatalogBuilder(views).build()
    compiler = IntentCompiler(views)
    facts, fact_record = deterministic_facts(compiler, request, catalog)
    adapter = RecordingAdapter()
    service = __import__("fitness_ledger_core.intelligent_export", fromlist=["IntelligentExportService"]).IntelligentExportService(views, adapter)
    result = service.run(request)
    call = adapter.calls[-1] if adapter.calls else {}
    raw_hints = ""
    parsed_hints = []
    schema_valid = False
    if call.get("raw_text"):
        raw_hints = call["raw_text"]
        try:
            raw_object = parse_json_object(raw_hints)
            IntentInterpreter._validate_raw_model_boundary(raw_object)
            SemanticHints.from_dict(raw_object)
            parsed_hints = raw_object.get("semantic_hints", [])
            schema_valid = True
        except Exception:
            parsed_hints = []
    grounding = getattr(getattr(service, "interpreter", None), "last_grounding_result", None)
    accepted = grounding.hints.to_dict().get("semantic_hints", []) if grounding else []
    rejected = list(grounding.rejected) if grounding else []
    full_scope = scope_snapshot(result)
    det_result, _, _, _ = plan_from_hints(views, request, SemanticHints([]))
    det_scope = scope_snapshot(det_result)
    return {
        "mode": "FULL_V3", "status": result.get("status"), "error_code": result.get("error_code", ""),
        "error_type": "" if result.get("status") == "ready" else result.get("error_code", ""),
        "deterministic": fact_record, "model_raw_hints": raw_hints, "model_parsed_hints": parsed_hints,
        "accepted_hints": accepted, "rejected_hints": rejected,
        "hint_changed_scope": full_scope != det_scope, "final_scope": full_scope,
        "deterministic_only_scope": det_scope, "model_call_count": len(adapter.calls), "schema_valid": schema_valid,
        "duration_ms": result.get("diagnostics", {}).get("duration_ms", int((time.monotonic() - started) * 1000)),
    }


def evaluate(case: dict, observation: dict) -> dict:
    expected = case
    scope = observation["final_scope"]
    required = set(expected.get("required_dimensions", []))
    forbidden = set(expected.get("forbidden_dimensions", []))
    dimensions = set(scope.get("dimensions", []))
    missing = sorted(required - dimensions)
    forbidden_found = sorted(forbidden & dimensions)
    modules_expected = {DIMENSION_MODULES[item] for item in required}
    modules = set(scope.get("modules", []))
    missing_modules = sorted(modules_expected - modules)
    extra_modules = sorted(modules - modules_expected) if expected["expected_outcome"] == "execute" else []
    movement_expected = expected.get("expected_movement_mentions")
    movement_match = movement_expected is None or sorted(scope.get("movement_mentions", [])) == sorted(movement_expected)
    if expected.get("movement_ambiguity"):
        movement_match = observation["status"] != "ready"
    notes_match = sorted(scope.get("notes_scopes", [])) == sorted(expected.get("expected_notes_scope", []))
    date_match = sorted(scope.get("date_expression", [])) == sorted(expected.get("expected_date_expression", [])) if "date_expression" in scope else True
    date_kind_match = not expected.get("date_kind") or observation["deterministic"].get("date_kind") == expected["date_kind"]
    reason_match = not expected.get("reason_code") or observation.get("error_code") == expected["reason_code"]
    raw_match = bool(scope.get("raw_allowed")) == bool(expected.get("raw_allowed"))
    correct_clarification = expected["expected_outcome"] == "clarify" and observation["status"] != "ready"
    correct_rejection = expected["expected_outcome"] == "reject" and observation["status"] != "ready"
    if expected["expected_outcome"] == "execute":
        scope_pass = observation["status"] == "ready" and not missing and not forbidden_found and not missing_modules and not extra_modules and movement_match and notes_match and raw_match
    elif expected["expected_outcome"] == "clarify":
        scope_pass = correct_clarification and date_kind_match and reason_match and not scope.get("raw_allowed")
    else:
        scope_pass = correct_rejection and not scope.get("raw_allowed")
    unsafe_expansion = observation["status"] == "ready" and bool(forbidden_found or extra_modules or (not raw_match and scope.get("raw_allowed")))
    valid_rejected = expected["expected_outcome"] == "execute" and observation["status"] != "ready"
    unsafe_acceptance = observation["status"] == "ready" and not scope_pass
    return {
        "scenario_pass": scope_pass, "missing_expected_scope_items": len(missing) + len(missing_modules),
        "forbidden_found": forbidden_found, "extra_modules": extra_modules,
        "correct_clarification": correct_clarification, "correct_rejection": correct_rejection,
        "valid_request_rejected": valid_rejected, "unsafe_acceptance": unsafe_acceptance,
        "unsafe_expansion": unsafe_expansion, "notes_scope_pass": notes_match,
        "date_expression_pass": date_match, "raw_boundary_pass": raw_match,
        "movement_resolution_pass": movement_match,
    }


def run_mode(cases: list[dict], mode: str, views) -> list[dict]:
    rows = []
    for case in cases:
        observation = run_full(views, case["request"]) if mode == "FULL_V3" else run_deterministic(views, case["request"])
        evaluation = evaluate(case, observation)
        rows.append({"case": case, "observation": observation, "evaluation": evaluation})
    return rows


def metrics(rows: list[dict], mode: str) -> dict:
    total = len(rows)
    scope_cases = [item for item in rows if item["observation"]["deterministic"].get("scope", {}).get("only") or item["observation"]["deterministic"].get("scope", {}).get("include") or item["observation"]["deterministic"].get("scope", {}).get("exclude")]
    raw_cases = [item for item in rows if item["case"]["category"] == "raw"]
    movement_cases = [item for item in rows if item["case"].get("expected_movement_mentions") or item["case"].get("movement_ambiguity")]
    notes_cases = [item for item in rows if item["case"]["category"] in {"diet_notes", "training_notes"}]
    date_cases = [item for item in rows if item["case"]["category"] == "date"]
    durations = sorted(item["observation"]["duration_ms"] for item in rows)
    p50 = durations[(len(durations) - 1) // 2]
    p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95) - 1)]
    return {
        "mode": mode, "scenario_pass_rate": round(sum(item["evaluation"]["scenario_pass"] for item in rows) / total, 4),
        "scenario_pass_count": sum(item["evaluation"]["scenario_pass"] for item in rows),
        "successful_execution": sum(item["case"]["expected_outcome"] == "execute" and item["observation"]["status"] == "ready" and item["evaluation"]["scenario_pass"] for item in rows),
        "correct_clarification": sum(item["evaluation"]["correct_clarification"] for item in rows),
        "correct_rejection": sum(item["evaluation"]["correct_rejection"] for item in rows),
        "valid_request_rejected": sum(item["evaluation"]["valid_request_rejected"] for item in rows),
        "unsafe_acceptance": sum(item["evaluation"]["unsafe_acceptance"] for item in rows),
        "unsafe_expansion": sum(item["evaluation"]["unsafe_expansion"] for item in rows),
        "missing_expected_scope_items": sum(item["evaluation"]["missing_expected_scope_items"] for item in rows),
        "only_exclude_pass_rate": round(sum(item["evaluation"]["scenario_pass"] for item in scope_cases) / len(scope_cases), 4) if scope_cases else 1.0,
        "only_exclude_denominator": len(scope_cases),
        "raw_boundary_pass_rate": round(sum(item["evaluation"]["raw_boundary_pass"] for item in raw_cases) / len(raw_cases), 4) if raw_cases else 1.0,
        "raw_boundary_denominator": len(raw_cases),
        "movement_resolution_pass_rate": round(sum(item["evaluation"]["movement_resolution_pass"] for item in movement_cases) / len(movement_cases), 4) if movement_cases else 1.0,
        "movement_resolution_denominator": len(movement_cases),
        "notes_scope_accuracy": round(sum(item["evaluation"]["notes_scope_pass"] for item in notes_cases) / len(notes_cases), 4) if notes_cases else 1.0,
        "notes_scope_denominator": len(notes_cases),
        "date_expression_accuracy": round(sum(item["evaluation"]["date_expression_pass"] for item in date_cases) / len(date_cases), 4) if date_cases else 1.0,
        "date_expression_denominator": len(date_cases),
        "schema_validity_rate": None if mode == "DETERMINISTIC_ONLY" else round(sum(item["observation"].get("schema_valid", False) for item in rows) / total, 4),
        "model_call_counts": sorted({item["observation"]["model_call_count"] for item in rows}),
        "average_ms": round(sum(durations) / total, 1), "p50_ms": p50, "p95_ms": p95, "max_ms": durations[-1],
    }


def classify(full: list[dict], deterministic: list[dict]) -> dict:
    categories = {"HELPFUL": [], "NEUTRAL": [], "HARMFUL": [], "INSUFFICIENT": []}
    for left, right in zip(full, deterministic):
        full_pass, det_pass = left["evaluation"]["scenario_pass"], right["evaluation"]["scenario_pass"]
        if not det_pass and full_pass:
            key = "HELPFUL"
        elif det_pass and not full_pass:
            key = "HARMFUL"
        elif not det_pass and not full_pass:
            key = "INSUFFICIENT"
        else:
            key = "NEUTRAL"
        categories[key].append(left["case"]["case_id"])
    return {key: {"count": len(value), "case_ids": value} for key, value in categories.items()}


def invariant_tests(views) -> list[dict]:
    def run(request: str) -> dict:
        return run_deterministic(views, request)

    def dims(request: str) -> set[str]:
        return set(run(request)["final_scope"]["dimensions"])

    checks = []
    base = run("分析最近的饮食和训练")
    changed = run("分析最近的饮食和训练，不要训练")
    checks.append(("exclude training removes training", "training_context" not in set(changed["final_scope"]["dimensions"])))
    checks.append(("only diet stays within diet", dims("只看饮食") <= {"diet_macros"}))
    checks.append(("diet to diet notes changes scope", dims("分析最近的饮食") == {"diet_macros"} and dims("分析最近的饮食备注") == {"diet_notes"}))
    checks.append(("training to training notes changes scope", dims("分析最近的训练") == {"training_context"} and dims("分析最近的训练备注") == {"training_notes"}))
    checks.append(("generic recent request rejects", run("最近怎么样")["status"] != "ready"))
    checks.append(("ambiguous push chest clarifies", run("看看推胸有没有进步")["status"] != "ready"))
    shoulder = run("看看肩部训练最近怎么样")
    checks.append(("body part has no movement", shoulder["status"] == "ready" and not shoulder["final_scope"]["movement_ids"]))
    no_move = run("只看卧推表现，不分析具体动作")
    checks.append(("explicit movement exclusion requires clarification", no_move["status"] != "ready"))
    raw = run("追溯最近一周的原始记录")
    non_raw = run("看看最近一周的记录")
    checks.append(("explicit raw enables raw", raw["final_scope"]["raw_allowed"]))
    checks.append(("removing raw word removes raw", not non_raw["final_scope"]["raw_allowed"]))
    checks.append(("empty only/exclude is safe", run("只看训练，不要训练")["status"] != "ready"))
    checks.append(("empty hints do not expand", base["final_scope"] == run("分析最近的饮食和训练")["final_scope"]))
    return [{"name": name, "pass": bool(passed)} for name, passed in checks]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("deterministic-only",), default="deterministic-only")
    parser.parse_args()
    cases = load_cases()
    duplicate_pairs = []
    for index, left in enumerate(cases):
        for right in cases[index + 1:]:
            ratio = SequenceMatcher(None, normalized(left["request"]), normalized(right["request"])).ratio()
            if ratio >= 0.82:
                duplicate_pairs.append({"left": left["case_id"], "right": right["case_id"], "ratio": round(ratio, 3)})
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-holdout-") as name:
        tracker, dictionary = fixture(Path(name))
        views_full = LedgerViewModels(tracker, dictionary)
        views_det = LedgerViewModels(tracker, dictionary)
        full = []
        deterministic = run_mode(cases, "DETERMINISTIC_ONLY", views_det)
        comparison = {"MODEL_CALLS_DISABLED": {"count": len(cases), "case_ids": [item["case"]["case_id"] for item in deterministic]}}
        output = {
            "schema_version": "fitness-ledger-grounded-semantic-intent-v3-holdout-v1",
            "fixture": "anonymous-local-fixture",
            "case_count": len(cases), "duplicate_pairs": duplicate_pairs,
            "full_metrics": None,
            "deterministic_metrics": metrics(deterministic, "DETERMINISTIC_ONLY"),
            "hint_contribution": comparison,
            "accepted_hint_count": 0,
            "rejected_hint_count": 0,
            "scope_changed_hint_count": 0,
            "invariants": invariant_tests(LedgerViewModels(tracker, dictionary)),
            "full": full, "deterministic_only": deterministic,
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = OUTPUT_DIR / "holdout_ab_results.json"
        output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print("RESULT_FILE=" + str(output_file))
        print("DUPLICATE_PAIRS=" + json.dumps(duplicate_pairs, ensure_ascii=False))
        print("FULL_METRICS=null")
        print("DETERMINISTIC_METRICS=" + json.dumps(output["deterministic_metrics"], ensure_ascii=False))
        print("HINT_CONTRIBUTION=" + json.dumps(comparison, ensure_ascii=False))
        print("HINT_COUNTS=" + json.dumps({"accepted": output["accepted_hint_count"], "rejected": output["rejected_hint_count"], "scope_changed": output["scope_changed_hint_count"]}, ensure_ascii=False))
        print("INVARIANTS=" + json.dumps(output["invariants"], ensure_ascii=False))


if __name__ == "__main__":
    main()
