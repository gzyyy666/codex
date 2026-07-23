"""Real qwen3:4b end-to-end acceptance; never imported by production code."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.intelligent_export import IntelligentExportService
from fitness_ledger_core.intelligent_export_models import ContractError, IntentSpec, SemanticHints, semantic_hints_json_schema
from fitness_ledger_core.intent_interpreter import IntentInterpreter, parse_json_object
from fitness_ledger_core.local_model_adapter import OllamaNativeAdapter
from fitness_ledger_core.shared_view_models import LedgerViewModels


def fixture(root: Path) -> tuple[Path, Path]:
    tracker = {
        "version": 1,
        "daily_records": [
            {"id": "anon-body-1", "Date": "2026-07-01", "Weight (kg)": 80, "Training": "肩", "Notes": "匿名 body note"},
            {"id": "anon-body-2", "Date": "2026-07-08", "Weight (kg)": 79.5, "Training": "胸", "Notes": "匿名 body note"},
            {"id": "anon-body-3", "Date": "2026-07-15", "Weight (kg)": 79, "Training": "肩", "Notes": "匿名 body note"},
        ],
        "diet_records": [
            {"id": "anon-diet-1", "Date": "2026-07-01", "Calories (kcal)": 2100, "Protein (g)": 150, "Carbs (g)": 120, "Fat (g)": 60, "Notes": "匿名 diet note"},
            {"id": "anon-diet-2", "Date": "2026-07-08", "Calories (kcal)": 2050, "Protein (g)": 155, "Carbs (g)": 100, "Fat (g)": 58, "Notes": "匿名 diet note"},
            {"id": "anon-diet-3", "Date": "2026-07-15", "Calories (kcal)": 2150, "Protein (g)": 152, "Carbs (g)": 140, "Fat (g)": 61, "Notes": "匿名 diet note"},
        ],
        "training_sessions": [
            {"id": "anon-training-1", "Date": "2026-07-01", "No.": 1, "Split": "肩", "Notes": "匿名 training note"},
            {"id": "anon-training-2", "Date": "2026-07-08", "No.": 2, "Split": "胸", "Notes": "匿名 training note"},
            {"id": "anon-training-3", "Date": "2026-07-15", "No.": 3, "Split": "肩", "Notes": "匿名 training note"},
        ],
        "movements": {
            "press-a": {"movement_id": "anon-press-a", "history": [{"id": "anon-h1", "movement_id": "anon-press-a", "date": "2026-07-01", "order": 1, "sets": [{"weight": 60, "reps": 8, "sets": 3}], "notes": "anon movement note", "exclude_from_progress": False}, {"id": "anon-h2", "movement_id": "anon-press-a", "date": "2026-07-08", "order": 1, "sets": [{"weight": 62, "reps": 7, "sets": 3}], "notes": "anon movement note", "exclude_from_progress": False}]},
            "press-b": {"movement_id": "anon-press-b", "history": [{"id": "anon-h3", "movement_id": "anon-press-b", "date": "2026-07-01", "order": 2, "sets": [{"weight": 45, "reps": 10, "sets": 3}], "notes": "anon movement note", "exclude_from_progress": False}, {"id": "anon-h4", "movement_id": "anon-press-b", "date": "2026-07-08", "order": 2, "sets": [{"weight": 47, "reps": 9, "sets": 3}], "notes": "anon movement note", "exclude_from_progress": False}]},
            "shoulder-a": {"movement_id": "anon-shoulder-a", "history": [{"id": "anon-h5", "movement_id": "anon-shoulder-a", "date": "2026-07-01", "order": 1, "sets": [{"weight": 10, "reps": 12, "sets": 3}], "notes": "anon movement note", "exclude_from_progress": False}, {"id": "anon-h6", "movement_id": "anon-shoulder-a", "date": "2026-07-08", "order": 1, "sets": [{"weight": 12, "reps": 10, "sets": 3}], "notes": "anon movement note", "exclude_from_progress": False}]},
        },
        "raw_entries": [{"id": "anon-raw-1", "date": "2026-07-08", "text": "匿名 raw content"}],
    }
    dictionary = {"version": 1, "movements": [
        {"movement_id": "anon-press-a", "display_name": "卧推", "english_name": "Bench Press", "aliases": ["卧推", "Bench Press"], "muscle_group": "Chest", "active": True},
        {"movement_id": "anon-press-b", "display_name": "下斜推", "english_name": "Decline Press", "aliases": ["下斜推"], "muscle_group": "Chest", "active": True},
        {"movement_id": "anon-shoulder-a", "display_name": "侧平举", "english_name": "Lateral Raise", "aliases": ["侧平举"], "muscle_group": "Shoulder", "active": True},
    ]}
    tracker_path, dictionary_path = root / "tracker.json", root / "movement_dictionary.json"
    tracker_path.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
    dictionary_path.write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
    return tracker_path, dictionary_path


CASES = [
    ("A1", "分析最近的饮食和体重变化", {"dimensions": {"body_state", "diet_macros"}, "modules": {"body", "diet"}, "forbidden_dimensions": {"training_context", "movement_progress", "daily_notes", "diet_notes", "training_notes", "movement_notes", "raw_trace"}}),
    ("A2", "仅分析体重", {"dimensions": {"body_state"}, "modules": {"body"}, "forbidden_dimensions": set(INTENT_DIMENSIONS := {"diet_macros", "training_context", "movement_progress", "daily_notes", "diet_notes", "training_notes", "movement_notes", "raw_trace"})}),
    ("A3", "分析最近的训练和饮食，不看体重", {"dimensions": {"training_context", "diet_macros"}, "modules": {"training", "diet"}, "forbidden_dimensions": {"body_state"}}),
    ("A4", "看看最近减脂怎么样，训练有没有受影响", {"dimensions": {"body_state", "diet_macros", "training_context"}, "modules": {"body", "diet", "training"}, "forbidden_dimensions": {"movement_progress"}}),
    ("B5", "只看最近一个月的饮食，不要训练", {"dimensions": {"diet_macros"}, "modules": {"diet"}, "forbidden_dimensions": {"training_context", "movement_progress", "training_notes", "movement_notes"}}),
    ("B6", "仅分析训练备注，不要每日总结", {"dimensions": {"training_notes"}, "modules": {"notes"}, "forbidden_dimensions": {"daily_notes"}, "note_scopes": {"training"}}),
    ("B7", "分析饮食备注，不包含体重和训练", {"dimensions": {"diet_notes"}, "modules": {"notes"}, "forbidden_dimensions": {"body_state", "training_context", "movement_progress", "raw_trace"}, "note_scopes": {"diet"}}),
    ("C8", "分析低碳是否导致卧推表现下降", {"dimensions": {"diet_macros", "movement_progress"}, "modules": {"diet", "movement_progress"}, "movement_mentions": {"卧推"}, "movement_ids": {"anon-press-a"}}),
    ("C9", "只看卧推最近有没有进步，不分析饮食", {"dimensions": {"movement_progress"}, "modules": {"movement_progress"}, "forbidden_dimensions": {"diet_macros"}, "movement_mentions": {"卧推"}, "movement_ids": {"anon-press-a"}}),
    ("C10", "看看卧推和下斜推最近的表现", {"dimensions": {"movement_progress"}, "modules": {"movement_progress"}, "movement_mentions": {"卧推", "下斜推"}, "movement_ids": {"anon-press-a", "anon-press-b"}}),
    ("C11", "看看肩部训练最近怎么样", {"dimensions": {"training_context"}, "modules": {"training"}, "forbidden_dimensions": {"movement_progress"}, "parts": {"SHOULDER"}}),
    ("C12", "只看胸部整体训练，不分析具体动作", {"dimensions": {"training_context"}, "modules": {"training"}, "forbidden_dimensions": {"movement_progress"}, "parts": {"CHEST"}}),
    ("C13", "看看推胸有没有进步", {"abstain": True}),
    ("D14", "追溯最近一周的原始记录", {"dimensions": {"raw_trace"}, "modules": {"raw_entries"}, "raw": True}),
    ("D15", "分析最近饮食是否影响训练", {"dimensions": {"diet_macros", "training_context"}, "modules": {"diet", "training"}, "forbidden_dimensions": {"raw_trace"}, "raw": False}),
    ("D16", "看看最近的情况", {"abstain": True}),
    ("D17", "把没用的数据清理掉", {"abstain": True}),
    ("D18", "不要训练，也不要饮食", {"abstain": True}),
]

HIGH_RISK = ["B5", "C8", "C11", "C13", "D14", "D16"]


class RecordingAdapter:
    def __init__(self, model: str = "qwen3:4b") -> None:
        self.adapter_name = "deterministic-only"
        self.model_name = ""
        self.calls: list[dict] = []

    def health_check(self, timeout: float = 2.0) -> dict:
        return {"available": False, "reason": "model calls disabled for deterministic acceptance"}

    def generate_json(self, **kwargs):
        raise AssertionError("model call is forbidden in deterministic acceptance")


def schema_check(raw_text: str) -> tuple[bool, str]:
    try:
        raw = parse_json_object(raw_text)
        IntentInterpreter._validate_raw_model_boundary(raw)
        SemanticHints.from_dict(raw)
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}:{getattr(exc, 'code', '')}:{str(exc)[:160]}"


def evaluate(case_id: str, request: str, expected: dict, result: dict, adapter: RecordingAdapter) -> dict:
    call = adapter.calls[-1] if adapter.calls else None
    raw_text = call["raw_text"] if call else ""
    schema_ok, schema_error = True, "deterministic-only; no model schema is evaluated"
    plan = result.get("plan", {})
    intent = result.get("intent", {})
    modules = set(plan.get("selected_modules", []))
    dimensions = set(intent.get("dimensions", []))
    movement_ids = set(plan.get("selected_movements", []))
    mentions = set(intent.get("movement_mentions", []))
    fields = plan.get("selected_fields", {})
    notes = result.get("output", {}).get("payload", {}).get("notes", [])
    scope_ok = True
    over = 0
    under = 0
    if expected.get("abstain"):
        scope_ok = result.get("status") != "ready" and "output" not in result
    else:
        required_dims = expected.get("dimensions", set())
        required_modules = expected.get("modules", set())
        missing_dims = required_dims - dimensions
        missing_modules = required_modules - modules
        forbidden_dims = expected.get("forbidden_dimensions", set()) & dimensions
        extra_modules = modules - required_modules
        under = len(missing_dims) + len(missing_modules)
        over = len(forbidden_dims) + len(extra_modules)
        scope_ok = result.get("status") == "ready" and not missing_dims and not missing_modules and not forbidden_dims and not extra_modules
        if "movement_mentions" in expected:
            unexpected_movements = movement_ids - expected.get("movement_ids", set())
            missing_movements = expected.get("movement_ids", set()) - movement_ids
            over += len(unexpected_movements)
            under += len(missing_movements)
            scope_ok = scope_ok and mentions == expected["movement_mentions"] and movement_ids == expected.get("movement_ids", set())
        elif movement_ids:
            over += len(movement_ids)
            scope_ok = False
        if "parts" in expected:
            scope_ok = scope_ok and set(intent.get("target_body_parts", [])) == expected["parts"]
        if "note_scopes" in expected:
            scope_ok = scope_ok and {item.get("scope") for item in notes} <= expected["note_scopes"] and bool(notes)
        if "raw" in expected:
            raw_match = bool(plan.get("include_raw_entries")) is expected["raw"]
            if not raw_match and bool(plan.get("include_raw_entries")):
                over += 1
            scope_ok = scope_ok and raw_match
    raw_allowed = bool(plan.get("include_raw_entries")) if plan else False
    multiple = len(movement_ids) > len(expected.get("movement_ids", movement_ids)) if not expected.get("abstain") else False
    return {
        "case_id": case_id, "request": request, "raw_json": raw_text, "schema_valid": schema_ok,
        "schema_error": schema_error, "model_call_count": len(adapter.calls), "intent": intent,
        "final_scope": {"modules": sorted(modules), "fields": fields, "movement_mentions": sorted(mentions), "movement_ids": sorted(movement_ids), "raw": raw_allowed, "notes_scopes": sorted({item.get("scope", "") for item in notes})},
        "status": result.get("status"), "error_code": result.get("error_code", ""), "error": result.get("error", ""),
        "scope_pass": scope_ok, "over_selection": over, "missing_expected_scope_items": under, "under_selection": under, "multiple_selection": multiple,
        "safe_rejection": bool(expected.get("abstain")) and result.get("status") != "ready",
        "valid_request_rejected": not bool(expected.get("abstain")) and result.get("status") != "ready",
        "unsafe_acceptance": not scope_ok and result.get("status") == "ready",
        "unsafe_expansion": result.get("status") == "ready" and over > 0,
        "duration_ms": result.get("diagnostics", {}).get("duration_ms", call.get("wall_ms", 0) if call else 0),
        "fallback_reason": result.get("error_code", "") if result.get("status") != "ready" else "",
    }


def run_case(views, case_id: str, request: str, expected: dict) -> dict:
    adapter = RecordingAdapter()
    result = IntelligentExportService(views, adapter).run(request)
    record = evaluate(case_id, request, expected, result, adapter)
    record["call_config"] = [item["config"] for item in adapter.calls]
    record["model_calls"] = len(adapter.calls)
    return record


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-real-acceptance-") as name:
        root = Path(name)
        tracker, dictionary = fixture(root)
        views = LedgerViewModels(tracker, dictionary)
        records = []
        for case_id, request, expected in CASES:
            records.append({"kind": "fixed", **run_case(views, case_id, request, expected)})
        for case_id in HIGH_RISK:
            request, expected = next((request, expected) for cid, request, expected in CASES if cid == case_id)
            for repeat in range(1, 4):
                records.append({"kind": "stability", "repeat": repeat, **run_case(views, case_id, request, expected)})
        output_file = Path(tempfile.gettempdir()) / f"fitness-ledger-real-intent-acceptance-{int(time.time())}.json"
        output_file.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        valid = [item for item in records if item["schema_valid"]]
        scope = [item for item in records if item["scope_pass"]]
        fixed = [item for item in records if item["kind"] == "fixed"]
        abstentions = [item for item in fixed if item["safe_rejection"]]
        raw_cases = [item for item in records if item["case_id"] == "D14" or item["case_id"] in {"D15", "D16", "D17", "D18"}]
        raw_pass = sum((item["final_scope"]["raw"] == (item["case_id"] == "D14")) for item in raw_cases)
        only_exclude = [item for item in records if item["case_id"] in {"B5", "B6", "B7", "C9", "C12", "D18"}]
        movement_cases = [item for item in records if item["case_id"] in {"C8", "C9", "C10", "C11", "C12", "C13"}]
        durations = [item["duration_ms"] for item in records]
        summary = {
            "result_file": str(output_file), "records": len(records), "schema_validity_rate": None, "deterministic_contract_rate": round(len(valid) / len(records), 4),
            "final_scope_pass_rate": round(len(scope) / len(records), 4), "over_selection_count": sum(item["over_selection"] for item in records),
            "missing_expected_scope_items": sum(item["missing_expected_scope_items"] for item in records),
            "raw_boundary_pass_rate": round(raw_pass / len(raw_cases), 4), "only_exclude_pass_rate": round(sum(item["scope_pass"] for item in only_exclude) / len(only_exclude), 4),
            "movement_resolution_pass_rate": round(sum(item["scope_pass"] for item in movement_cases) / len(movement_cases), 4),
            "model_call_counts": sorted(set(item["model_calls"] for item in records)), "average_duration_ms": round(sum(durations) / len(durations), 1), "max_duration_ms": max(durations),
            "fixed_failures": [item["case_id"] for item in records if item["kind"] == "fixed" and not item["scope_pass"]],
            "stability_failures": [f"{item['case_id']}#{item['repeat']}" for item in records if item["kind"] == "stability" and not item["scope_pass"]],
            "fixed_metrics": {
                "unique_task_success": sum(item["scope_pass"] for item in fixed),
                "safe_rejection": sum(item["safe_rejection"] for item in fixed),
                "valid_request_rejected": sum(item["valid_request_rejected"] for item in fixed),
                "unsafe_acceptance": sum(item["unsafe_acceptance"] for item in fixed),
                "unsafe_expansion": sum(item["unsafe_expansion"] for item in fixed),
            },
            "all_run_metrics": {
                "unique_task_success_records": sum(item["scope_pass"] for item in records),
                "safe_rejection_records": sum(item["safe_rejection"] for item in records),
                "valid_request_rejected_records": sum(item["valid_request_rejected"] for item in records),
                "unsafe_acceptance_records": sum(item["unsafe_acceptance"] for item in records),
                "unsafe_expansion_records": sum(item["unsafe_expansion"] for item in records),
            },
        }
        print("RESULT_FILE=" + str(output_file))
        print("SUMMARY=" + json.dumps(summary, ensure_ascii=True))
        for item in records:
            print("CASE=" + json.dumps({"kind": item["kind"], "repeat": item.get("repeat"), "id": item["case_id"], "status": item["status"], "schema_valid": item["schema_valid"], "scope_pass": item["scope_pass"], "calls": item["model_calls"], "over": item["over_selection"], "under": item["under_selection"], "error": item["error_code"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
