"""Run the bounded real-model acceptance sequence and write a privacy-safe review package."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.intelligent_export import IntelligentExportService
from fitness_ledger_core.intelligent_export_review_evidence import build_bundle, write_review_index
from fitness_ledger_core.local_model_adapter import OllamaNativeAdapter
from fitness_ledger_core.shared_view_models import LedgerViewModels


REQUESTS = [
    ("01-fat-loss", "看看我最近减脂怎么样，训练有没有受影响"),
    ("02-low-carb-training", "分析最近低碳是否导致胸部训练表现下降"),
    ("03-bench-progress", "导出关于卧推最近一段时间最有价值的数据"),
    ("04-shoulder-progress", "看看这几个月肩部训练是否有进步"),
]
STABILITY_REQUEST = REQUESTS[1][1]


def summarize(result: dict) -> dict:
    intent = result.get("intent", {}) or {}
    package = result.get("candidate_package", {}) or {}
    selection = result.get("selection", {}) or {}
    plan = result.get("plan", {}) or {}
    output = result.get("output", {}) or {}
    notes = package.get("notes", []) or []
    selected_note_ids = set(selection.get("selected_note_candidate_ids", []) or [])
    scopes = Counter(str(item.get("scope", "")) for item in notes if item.get("note_candidate_id") in selected_note_ids)
    windows = [
        {
            "window_id": item.get("window_id", ""),
            "requested_start": item.get("requested_start", ""),
            "requested_end": item.get("requested_end", ""),
            "resolved_start": item.get("resolved_start", ""),
            "resolved_end": item.get("resolved_end", ""),
            "anchor": item.get("anchor", ""),
            "missing_data_warnings": item.get("missing_data_warnings", []),
        }
        for item in package.get("windows", []) or []
    ]
    return {
        "status": result.get("status", ""),
        "fallback_reason": (result.get("fallback") or {}).get("fallback_reason", ""),
        "intent": {
            "interpreted_goal": intent.get("interpreted_goal", ""),
            "analysis_dimensions": intent.get("analysis_dimensions", []),
            "date_intent": intent.get("date_intent", {}),
            "movement_mentions": intent.get("movement_mentions", []),
            "confidence": intent.get("confidence", 0),
            "warnings": intent.get("warnings", []),
        },
        "candidate_windows": windows,
        "candidate_overview": {
            "modules": package.get("modules", []),
            "movements": package.get("movements", []),
            "notes_count": len(notes),
            "record_count": len(package.get("candidate_records", []) or []),
            "budget": package.get("budget", {}),
        },
        "selection": {
            "planning_decision": selection.get("planning_decision", ""),
            "fallback_reason_codes": selection.get("fallback_reason_codes", []),
            "selected_window_id": selection.get("selected_window_id", ""),
            "selected_modules": selection.get("selected_modules", []),
            "selected_fields": selection.get("selected_fields", []),
            "selected_movements": selection.get("selected_movements", []),
            "notes_count": len(selection.get("selected_note_candidate_ids", []) or []),
            "note_scopes": dict(scopes),
            "records_count": len(selection.get("selected_candidate_record_ids", []) or []),
            "training_detail_level": selection.get("training_detail_level", ""),
            "movement_detail_level": selection.get("movement_detail_level", ""),
            "include_raw_entries": selection.get("include_raw_entries", False),
            "include_excluded_history": selection.get("include_excluded_history", False),
            "excluded_history_usage": selection.get("excluded_history_usage", ""),
            "use_progress_history_for_metrics": selection.get("use_progress_history_for_metrics", False),
            "missing_data_warning_codes": selection.get("missing_data_warning_codes", []),
            "planner_confidence": selection.get("planner_confidence", 0),
        },
        "execution": {
            "estimated_record_count": plan.get("estimated_record_count", 0),
            "estimated_output_size": plan.get("estimated_output_size", 0),
            "sections": sorted(key for key in output.get("payload", {}) if key in {"body", "diet", "training", "movements", "notes", "raw_entries"}),
            "actual_record_count": sum(len(output.get("payload", {}).get(key, []) or []) for key in ("body", "diet", "training", "movements", "notes", "raw_entries")),
            "notes_count": len(output.get("payload", {}).get("notes", []) or []),
            "progress_evidence_count": sum(len(item.get("progress", []) or []) for item in output.get("payload", {}).get("movements", []) or []),
            "context_only_count": sum(len(item.get("context_only", []) or []) for item in output.get("payload", {}).get("movements", []) or []),
            "missing_data": plan.get("missing_data_warnings", []),
        },
        "trace": {
            "repaired": (result.get("trace") or {}).get("repaired", False),
            "trimmed": (result.get("trace") or {}).get("trimmed", False),
            "duration_ms": (result.get("trace") or {}).get("duration_ms", 0),
            "error_code": (result.get("trace") or {}).get("error_code", ""),
            "source_snapshot_id": plan.get("source_snapshot_id", ""),
        },
        "diagnostics": result.get("diagnostics", {}).get("stages", {}),
    }


def write_request_markdown(path: Path, request: str, item: dict) -> None:
    intent = item["intent"]; date_intent = intent["date_intent"]; selection = item["selection"]; execution = item["execution"]
    lines = ["# Fitness Ledger Intelligent Export Review", "", "## 1. 用户请求", "", request, "", "## 2. 模型理解", "", f"- interpreted goal: {intent['interpreted_goal']}", f"- analysis dimensions: {', '.join(intent['analysis_dimensions'])}", f"- DateIntent: `{json.dumps(date_intent, ensure_ascii=False)}`", f"- movement mentions: {json.dumps(intent['movement_mentions'], ensure_ascii=False)}", f"- confidence: {intent['confidence']}", f"- warnings: {json.dumps(intent['warnings'], ensure_ascii=False)}", "", "## 3. 日期选择", ""]
    for window in item["candidate_windows"]:
        lines.append(f"- candidate: `{window['window_id']}` → {window['requested_start']}..{window['requested_end']}，交集 {window['resolved_start']}..{window['resolved_end']}；warnings={window['missing_data_warnings']}")
    lines.extend([f"- selected window: `{selection['selected_window_id']}`", "", "## 4. 候选数据概况", "", f"- modules: {json.dumps(item['candidate_overview']['modules'], ensure_ascii=False)}", f"- movement candidates: {json.dumps(item['candidate_overview']['movements'], ensure_ascii=False)}", f"- Notes candidates: {item['candidate_overview']['notes_count']}", f"- record candidates: {item['candidate_overview']['record_count']}", f"- budget: {json.dumps(item['candidate_overview']['budget'], ensure_ascii=False)}", "", "## 5. 最终选择", "", f"- modules: {json.dumps(selection['selected_modules'], ensure_ascii=False)}", f"- fields: {json.dumps(selection['selected_fields'], ensure_ascii=False)}", f"- movements: {json.dumps(selection['selected_movements'], ensure_ascii=False)}", f"- Notes: {selection['notes_count']}，scopes={selection['note_scopes']}", f"- records: {selection['records_count']}", f"- detail: training={selection['training_detail_level']}, movement={selection['movement_detail_level']}", f"- raw: {selection['include_raw_entries']}; excluded history: {selection['include_excluded_history']} ({selection['excluded_history_usage']}); progress metrics={selection['use_progress_history_for_metrics']}", f"- warnings: {selection['missing_data_warning_codes']}", f"- confidence: {selection['planner_confidence']}", "", "## 6. 执行结果", "", f"- estimated records: {execution['estimated_record_count']}; actual safe-count: {execution['actual_record_count']}", f"- estimated output size: {execution['estimated_output_size']}", f"- sections: {execution['sections']}", f"- progress evidence: {execution['progress_evidence_count']}; context-only: {execution['context_only_count']}", f"- Notes count: {execution['notes_count']}", f"- missing data: {execution['missing_data']}", "", "## 7. 安全预览", "", "本包只保留结构、数量、ID 选择和有限诊断，不包含完整 Notes、Raw、tracker、dictionary 或正式路径。", "", "## 8. 人工 Review 问题", "", "1. 时间范围选得是否合理？", "2. 模块是否选多或选少？", "3. 动作是否选对？", "4. Notes 是否有明显噪声或遗漏？", "5. 明细级别是否合适？", "6. 导出内容是否足以回答原问题？", "7. 哪些内容应该增加？", "8. 哪些内容应该删除？", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--formal-dir", default=os.environ.get("FITNESS_LEDGER_FORMAL_DIR", "")); ap.add_argument("--output", default="")
    args = ap.parse_args(); root = Path(args.formal_dir); output = Path(args.output) if args.output else Path(os.environ.get("TEMP", ".")) / ("fitness-ledger-intelligent-export-review-" + datetime.now().strftime("%Y%m%d-%H%M%S")); output.mkdir(parents=True, exist_ok=True)
    tracker = root / "data" / "tracker.json"; dictionary = root / "data" / "movement_dictionary.json"
    adapter = OllamaNativeAdapter(); health = adapter.health_check(); (output / "requests").mkdir(exist_ok=True); (output / "machine").mkdir(exist_ok=True); (output / "stability").mkdir(exist_ok=True)
    if not health.get("available"):
        blocked = {"review_schema_version": "fitness-ledger-review-evidence-v1.0", "review_status": "blocked", "health": health, "integrity_audit": {"passed": False, "blocking_integrity_codes": ["MODEL_UNAVAILABLE"]}, "privacy_audit": {"passed": True, "violations": []}, "request_evidence": [], "stability_evidence": []}
        (output / "summary.json").write_text(json.dumps(blocked, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "integrity-audit.json").write_text(json.dumps(blocked["integrity_audit"], ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "privacy-audit.json").write_text(json.dumps(blocked["privacy_audit"], ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "README.md").write_text("# Intelligent Export Review Evidence\n\n当前模型不可用，Package blocked。未生成任何模型结果。\n", encoding="utf-8")
        print(str(output)); return
    views = LedgerViewModels(tracker, dictionary); results = []
    for label, request in REQUESTS:
        started = time.monotonic(); result = IntelligentExportService(views, adapter, overall_timeout=120).run(request, "concise"); results.append((label, request, result));
    stability = []
    for index in range(1, 4):
        started = time.monotonic(); stability.append(IntelligentExportService(views, adapter, overall_timeout=120).run(STABILITY_REQUEST, "concise"));
    bundle = build_bundle(results, stability)
    bundle["generated_at"] = datetime.now(timezone.utc).isoformat()
    bundle["model_health"] = {key: value for key, value in health.items() if key not in {"raw_response", "prompt", "payload"}}
    (output / "summary.json").write_text(json.dumps({"review_schema_version": bundle["review_schema_version"], "generated_at": bundle["generated_at"], "review_status": bundle["review_status"], "source_snapshot_id": bundle.get("source_snapshot_id", ""), "catalog_id": bundle.get("catalog_id", ""), "requests": [{"request_id": item["request_id"], "status": item["status"], "window": item["selection"].get("selected_window_id", ""), "modules": item["selection"].get("selected_module_ids", []), "movements": item["selection"].get("selected_movement_ids", []), "notes": len(item["selection"].get("selected_note_candidate_ids", [])), "records": len(item["selection"].get("selected_candidate_record_ids", [])), "progress_history": item["execution"].get("progress_history_count", 0), "context_only": item["execution"].get("context_only_count", 0), "confidence": item["selection"].get("planner_confidence", 0), "repair": item["repair"].get("repair_used", False)} for item in bundle["request_evidence"]], "stability": bundle["stability_comparison"], "integrity_audit": bundle["integrity_audit"], "privacy_audit": bundle["privacy_audit"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "integrity-audit.json").write_text(json.dumps(bundle["integrity_audit"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "privacy-audit.json").write_text(json.dumps(bundle["privacy_audit"], ensure_ascii=False, indent=2), encoding="utf-8")
    for item in bundle["request_evidence"]:
        label = item["request_id"]
        (output / "machine" / f"{label}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "requests" / f"{label}.md").write_text("# Review Evidence\n\n" + json.dumps({"request_id": label, "original_request": item["original_request"], "intent": item["intent"], "selection": item["selection"], "execution": {key: item["execution"].get(key) for key in ("output_sections", "actual_output_size", "progress_history_count", "context_only_count", "actual_note_ids", "actual_record_ids")}, "integrity_errors": bundle["integrity_audit"]["request_errors"].get(label, [])}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for index, item in enumerate(bundle["stability_evidence"], 1):
        (output / "stability" / f"low-carb-run-{index}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "stability" / "comparison.json").write_text(json.dumps(bundle["stability_comparison"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "README.md").write_text("# Fitness Ledger Intelligent Export Review Evidence\n\n本包来自运行时结构化 Intent、Candidate、Selection、Plan 与 Execution evidence 投影。它不包含完整 Notes、Raw、tracker、dictionary、正式路径、完整 Prompt 或完整模型响应。请先阅读 `human-review/review-index.md` 与 `integrity-audit.json`。\n", encoding="utf-8")
    write_review_index(bundle, output)
    print(str(output))


if __name__ == "__main__":
    main()
