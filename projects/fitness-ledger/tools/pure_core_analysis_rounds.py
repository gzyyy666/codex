"""Fresh analysis-intent acceptance rounds for the model-free export Core."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any


ROUND_ONE = [
    {"id": "AR1-1", "text": "分析过去六周的体重和饮食趋势。", "status": "ready", "domains": ["body", "diet"], "rules": ["TIME_RECENT_CUSTOM"], "analysis": True, "days": 42},
    {"id": "AR1-2", "text": "比较最近4次胸训的整体状态。", "status": "ready", "domains": ["training"], "analysis": True, "sessions": 4, "body_part": "胸"},
    {"id": "AR1-3", "text": "导出最近21天饮食，用于评估减脂执行。", "status": "ready", "domains": ["diet"], "analysis": True, "days": 21},
    {"id": "AR1-4", "text": "看看最近3次背部训练的动作安排。", "status": "candidate_confirmation_required", "domains": ["training", "movement_progress"], "candidate_min": 1, "patched_dataset_min": 2},
    {"id": "AR1-5", "text": "查看七月份身体数据和整体训练情况，不要饮食。", "status": "ready", "domains": ["body", "training"], "rules": ["TIME_EXPLICIT_MONTH"]},
    {"id": "AR1-6", "text": "分析上一次腿训当天的饮食与训练状态。", "status": "ready", "domains": ["diet", "training"], "rules": ["RELATION_TARGET_SESSION_DAY"], "analysis": True, "sessions": 1, "body_part": "腿"},
    {"id": "AR1-7", "text": "导出卧推和引体向上从有记录以来的完整成长数据。", "status": "ready", "domains": ["movement_progress"], "rules": ["SCOPE_ALL_AVAILABLE_SELECTED_DOMAIN"], "dataset_count": 2},
    {"id": "AR1-8", "text": "看看最近肩部主要动作的表现。", "status": "ready", "domains": ["movement_progress"], "rules": ["MOVEMENT_REPRESENTATIVE_TOP3_V1"], "dataset_count": 3},
    {"id": "AR1-9", "text": "导出各个部位代表性动作最近4次的表现。", "status": "ready", "domains": ["movement_progress"], "rules": ["MOVEMENT_MAJOR_PER_BODY_PART_V1"], "sessions": 4, "dataset_min": 4},
    {"id": "AR1-10", "text": "判断最近一段时间体重变化时训练是否稳定。", "status": "ready", "domains": ["body", "training"], "rules": ["TIME_RECENT_CONTEXT_30D"], "analysis": True, "days": 30},
]

ROUND_TWO = [
    {"id": "AR2-1", "text": "只导出最近18天饮食数据，用来判断饮食执行，不要身体和训练。", "status": "ready", "domains": ["diet"], "analysis": True, "days": 18},
    {"id": "AR2-2", "text": "整理最近两个月全部健身数据，不含动作成长。", "status": "ready", "domains": ["body", "diet", "training"], "rules": ["CONCEPT_ALL_FITNESS_V1"], "days": 60},
    {"id": "AR2-3", "text": "查看最近2次胸部训练的动作安排和整体表现。", "status": "candidate_confirmation_required", "domains": ["training", "movement_progress"], "candidate_min": 1, "sessions": 2},
    {"id": "AR2-4", "text": "比较2026-07-05到2026-07-20的身体和训练情况。", "status": "ready", "domains": ["body", "training"], "rules": ["TIME_EXPLICIT_RANGE"], "analysis": True},
    {"id": "AR2-5", "text": "分析最近2次肩部训练前2天到训练当天的饮食。", "status": "ready", "domains": ["diet", "training"], "rules": ["RELATION_PRE_TRAINING_EXPLICIT"], "analysis": True, "sessions": 2, "body_part": "肩"},
    {"id": "AR2-6", "text": "导出最近腿训后1天的饮食与对应训练。", "status": "ready", "domains": ["diet", "training"], "rules": ["RELATION_POST_TRAINING_1D"], "body_part": "腿"},
    {"id": "AR2-7", "text": "查看最近背部训练当天吃了什么。", "status": "ready", "domains": ["diet", "training"], "rules": ["RELATION_TARGET_SESSION_DAY"], "body_part": "背", "diet_complete": True},
    {"id": "AR2-8", "text": "导出卧推、卧推、引体向上近期完整进展。", "status": "ready", "domains": ["movement_progress"], "dataset_count": 2},
    {"id": "AR2-9", "text": "导出数据库原始记录并修改其中的饮食。", "status": "unsupported", "domains": ["diet"]},
    {"id": "AR2-10", "text": "分析最近一个月每个部位主要动作有没有变化。", "status": "ready", "domains": ["movement_progress"], "rules": ["MOVEMENT_MAJOR_PER_BODY_PART_V1"], "analysis": True, "days": 30, "dataset_min": 4},
]

ROUND_THREE = [
    {"id": "AR3-1", "text": "评估最近28天饮食执行，只需要饮食证据。", "status": "ready", "domains": ["diet"], "analysis": True, "days": 28},
    {"id": "AR3-2", "text": "查看最近一个月胸训和腿训的整体表现。", "status": "ready", "domains": ["training"], "days": 30},
    {"id": "AR3-3", "text": "看看肩部训练都安排了什么动作。", "status": "candidate_confirmation_required", "domains": ["training", "movement_progress"], "candidate_min": 1},
    {"id": "AR3-4", "text": "导出七月份完整饮食和训练记录，不要身体数据。", "status": "ready", "domains": ["diet", "training"], "rules": ["TIME_EXPLICIT_MONTH"]},
    {"id": "AR3-5", "text": "比较最近5次卧推和引体向上的完整进展。", "status": "ready", "domains": ["movement_progress"], "analysis": True, "sessions": 5, "dataset_count": 2},
    {"id": "AR3-6", "text": "查看最近3次背训前1天饮食，不包括训练当天。", "status": "ready", "domains": ["diet", "training"], "sessions": 3, "body_part": "背"},
    {"id": "AR3-7", "text": "导出最近45天所有健身数据，但不要动作表现和饮食备注。", "status": "ready", "domains": ["body", "diet", "training"], "days": 45},
    {"id": "AR3-8", "text": "分析各部位代表性动作近期表现是否稳定。", "status": "ready", "domains": ["movement_progress"], "rules": ["MOVEMENT_MAJOR_PER_BODY_PART_V1"], "analysis": True, "dataset_min": 4},
    {"id": "AR3-9", "text": "请把最近饮食记录删除并重新保存。", "status": "unsupported", "domains": ["diet"]},
    {"id": "AR3-10", "text": "分析最近一段时间体重、饮食和训练状态。", "status": "ready", "domains": ["body", "diet", "training"], "rules": ["TIME_RECENT_CONTEXT_30D"], "analysis": True, "days": 30},
]

ROUND_FOUR = [
    {"id": "AR4-1", "text": "把过去30天体重跟饮食一起导出来，想判断执行是否合理。", "status": "ready", "domains": ["body", "diet"], "analysis": True, "days": 30},
    {"id": "AR4-2", "text": "最近五回胸训都做了哪些动作？", "status": "candidate_confirmation_required", "domains": ["training", "movement_progress"], "candidate_min": 1, "sessions": 5},
    {"id": "AR4-3", "text": "导出上次背训之前两天吃的东西。", "status": "ready", "domains": ["diet", "training"], "rules": ["RELATION_PRE_TRAINING_EXPLICIT"], "sessions": 1, "body_part": "背", "diet_complete": True},
    {"id": "AR4-4", "text": "比较7月1日至7月20日的身体和训练情况。", "status": "ready", "domains": ["body", "training"], "analysis": True, "start": "2026-07-01", "end": "2026-07-20"},
    {"id": "AR4-5", "text": "导出近三周完整饮食，不含饮食备注。", "status": "ready", "domains": ["diet"], "days": 21, "no_notes_scope": "diet"},
    {"id": "AR4-6", "text": "导出每个部位最常练的动作最近3次表现。", "status": "ready", "domains": ["movement_progress"], "rules": ["MOVEMENT_MAJOR_PER_BODY_PART_V1"], "sessions": 3, "dataset_min": 4},
    {"id": "AR4-7", "text": "看看最近几场腿部训练后两天的饮食。", "status": "ready", "domains": ["diet", "training"], "rules": ["RELATION_POST_TRAINING_EXPLICIT"], "sessions": 3, "body_part": "腿"},
    {"id": "AR4-8", "text": "导出卧推近期完整进展，不要动作备注。", "status": "ready", "domains": ["movement_progress"], "sessions": 6, "no_notes_scope": "movement"},
    {"id": "AR4-9", "text": "导出身体和训练数据，排除饮食和动作成长。", "status": "ready", "domains": ["body", "training"]},
    {"id": "AR4-10", "text": "整理近两周所有健身数据，不要动作表现。", "status": "ready", "domains": ["body", "diet", "training"], "rules": ["CONCEPT_ALL_FITNESS_V1"], "days": 14},
]

ROUND_FIVE = [
    {"id": "AR5-1", "text": "导出过去四周体重和训练，不看饮食。", "status": "ready", "domains": ["body", "training"], "days": 28},
    {"id": "AR5-2", "text": "最近六回背训动作安排。", "status": "candidate_confirmation_required", "domains": ["training", "movement_progress"], "candidate_min": 1, "sessions": 6},
    {"id": "AR5-3", "text": "查看上次肩训前3日到当天吃了什么。", "status": "ready", "domains": ["diet", "training"], "sessions": 1, "body_part": "肩", "diet_complete": True, "include_day": True},
    {"id": "AR5-4", "text": "导出7月5日到20日的饮食。", "status": "ready", "domains": ["diet"], "start": "2026-07-05", "end": "2026-07-20"},
    {"id": "AR5-5", "text": "导出每个部位最常做的动作最近2次表现。", "status": "ready", "domains": ["movement_progress"], "rules": ["MOVEMENT_MAJOR_PER_BODY_PART_V1"], "sessions": 2, "dataset_min": 4},
    {"id": "AR5-6", "text": "导出卧推所有历史，不含动作笔记。", "status": "ready", "domains": ["movement_progress"], "no_notes_scope": "movement"},
    {"id": "AR5-7", "text": "比较最近三场胸部训练表现。", "status": "ready", "domains": ["training"], "analysis": True, "sessions": 3, "body_part": "胸"},
    {"id": "AR5-8", "text": "分析近两个月身体、饮食和训练状态。", "status": "ready", "domains": ["body", "diet", "training"], "analysis": True, "days": 60},
    {"id": "AR5-9", "text": "查看肩部都有哪些动作。", "status": "candidate_confirmation_required", "domains": ["movement_progress"], "candidate_min": 1},
    {"id": "AR5-10", "text": "把原始输入完整导出。", "status": "unsupported", "domains": []},
]


def post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:8786{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def datasets(response: dict[str, Any]) -> list[dict[str, Any]]:
    return [dataset for request in response.get("requests", []) for dataset in request.get("datasets", [])]


def validate_case(spec: dict[str, Any], natural: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    errors: list[str] = []
    plan = natural.get("semantic_plan", {})
    if natural.get("status") != spec["status"]:
        errors.append(f"status={natural.get('status')} expected={spec['status']}")
    if natural.get("model_calls") != 0:
        errors.append("model_calls must be 0")
    if plan.get("requested_domains") != spec["domains"]:
        errors.append(f"domains={plan.get('requested_domains')} expected={spec['domains']}")
    if not set(spec.get("rules", [])).issubset(set(plan.get("applied_rule_ids", []))):
        errors.append(f"missing rules {sorted(set(spec.get('rules', [])) - set(plan.get('applied_rule_ids', [])))}")
    if spec.get("analysis") is not None and bool(plan.get("analysis_boundary", {}).get("analysis_requested")) != spec["analysis"]:
        errors.append("analysis boundary mismatch")
    if len(natural.get("candidates", [])) < spec.get("candidate_min", 0):
        errors.append("insufficient candidates")

    effective = natural
    if spec["status"] == "candidate_confirmation_required" and natural.get("candidates"):
        selected = [item["movement_id"] for item in natural["candidates"][:3] if item.get("movement_id")]
        effective = post("/api/analysis-export/v1/natural-language/preview", {"text": spec["text"], "selected_movement_ids": selected})
        if effective.get("status") != "ready":
            errors.append(f"candidate patch status={effective.get('status')}")

    items = datasets(effective)
    if "dataset_count" in spec and len(items) != spec["dataset_count"]:
        errors.append(f"dataset_count={len(items)} expected={spec['dataset_count']}")
    if len(items) < spec.get("dataset_min", 0):
        errors.append(f"dataset_count={len(items)} below {spec['dataset_min']}")
    if len(items) < spec.get("patched_dataset_min", 0):
        errors.append(f"patched_dataset_count={len(items)} below {spec['patched_dataset_min']}")
    if "days" in spec and not any(item.get("time_range", {}).get("days") == spec["days"] for item in items):
        errors.append(f"missing recent_days={spec['days']}")
    if "sessions" in spec and not any(item.get("time_range", {}).get("sessions") == spec["sessions"] for item in items):
        errors.append(f"missing sessions={spec['sessions']}")
    if "start" in spec and not any(
        item.get("time_range", {}).get("start") == spec["start"] and item.get("time_range", {}).get("end") == spec["end"]
        for item in items
    ):
        errors.append(f"missing range={spec['start']}..{spec['end']}")
    if "body_part" in spec and not any(item.get("filters", {}).get("body_part") == spec["body_part"] for item in items):
        errors.append(f"missing body_part={spec['body_part']}")
    if spec.get("include_day") is not None and not any(
        item.get("time_range", {}).get("include_target_session_day") is spec["include_day"]
        for item in items
    ):
        errors.append(f"include_target_session_day={spec['include_day']} missing")
    if spec.get("diet_complete") and not any(
        item.get("type") == "diet" and "food_summary" in item.get("fields", []) and item.get("notes_scope") == "diet"
        for item in items
    ):
        errors.append("diet complete profile missing")
    if "no_notes_scope" in spec and any(item.get("notes_scope") == spec["no_notes_scope"] for item in items):
        errors.append(f"notes_scope={spec['no_notes_scope']} was not excluded")
    movement_ids = [
        item.get("filters", {}).get("movement_selector", {}).get("value")
        for item in items
        if item.get("type") == "movement_progress"
    ]
    if len([item for item in movement_ids if item]) != len(set(item for item in movement_ids if item)):
        errors.append("duplicate movement dataset")

    previews: list[dict[str, Any]] = []
    if effective.get("status") == "ready":
        for request in effective.get("requests", []):
            preview = post("/api/analysis-export/v1/preview", {
                "request": request,
                "preview_context_id": effective.get("preview_context_id", ""),
            })
            previews.append(preview)
            if preview.get("status") != "preview_ready":
                errors.append(f"preview status={preview.get('status')}")
            if preview.get("preview", {}).get("raw", {}).get("allowed"):
                errors.append("raw unexpectedly allowed")
    return not errors, errors, {"natural": natural, "effective": effective, "previews": previews}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, choices=(1, 2, 3, 4, 5), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = {1: ROUND_ONE, 2: ROUND_TWO, 3: ROUND_THREE, 4: ROUND_FOUR, 5: ROUND_FIVE}[args.round]
    records = []
    for spec in cases:
        natural = post("/api/analysis-export/v1/natural-language/preview", {"text": spec["text"]})
        passed, errors, evidence = validate_case(spec, natural)
        records.append({"spec": spec, "passed": passed, "errors": errors, **evidence})
    result = {
        "schema_version": "fitness-ledger-pure-core-analysis-round-v1",
        "round": args.round,
        "passed": sum(record["passed"] for record in records),
        "total": len(records),
        "model_calls_total": sum(int(record["natural"].get("model_calls") or 0) for record in records),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("round", "passed", "total", "model_calls_total")}, ensure_ascii=False))
    if result["passed"] != result["total"]:
        for record in records:
            if not record["passed"]:
                print(json.dumps({"id": record["spec"]["id"], "errors": record["errors"]}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
