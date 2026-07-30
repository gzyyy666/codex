"""HTTP acceptance rounds for the model-free intelligent export Core."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


CASES = [
    ("R1", "只导出最近14天体重和最近7天饮食，不要训练。", "ready"),
    ("R2", "导出最近少量饮食数据。", "ready"),
    ("R3", "导出卧推最近3次的完整成长记录。", "ready"),
    ("R4", "导出器械飞鸟最近的表现。", "ready"),
    ("R5", "导出最近少量饮食和一些代表性动作的全部成长记录。", "ready"),
    ("R6", "列出所有肩部动作名称。", "candidate_confirmation_required"),
    ("R7", "导出我上一次肩部训练前2天的饮食，不包含训练当天。", "ready"),
    ("R8", "导出最近7天饮食，并分别导出卧推、引体向上、诺德士高拉、悍马拉背二、单臂绳索下拉、绳索侧平举、哑铃推肩和坐姿腿举的全部成长记录。", "ready"),
    ("R9", "整理最近45天所有健身数据，但不要动作成长记录，也不要饮食备注。", "ready"),
    ("R10", "把数据库原始记录全部导出来。", "unsupported"),
]

ROUND_TWO = [
    ("S2-1", "导出2026-07-01到2026-07-15的身体和饮食数据。", "ready"),
    ("S2-2", "导出最近两周完整训练记录，不要饮食。", "ready"),
    ("S2-3", "列出肩部全部动作名称。", "candidate_confirmation_required"),
    ("S2-4", "导出卧推、卧推最近5次的完整成长记录。", "ready"),
    ("S2-5", "导出最近3次背部训练前1天的饮食，不包含训练当天。", "ready"),
    ("S2-6", "导出引体向上从有记录以来的完整成长记录。", "ready"),
    ("S2-7", "导出最近14天身体数据，不要排便和有氧。", "ready"),
    ("S2-8", "导出最近7天饮食与训练数据。", "ready"),
    ("S2-9", "导出最近六周的体重变化，只保留日期和体重。", "ready"),
    ("S2-10", "请删除最近的饮食记录。", "unsupported"),
]

ROUND_THREE = [
    ("S3-1", "导出最近21天身体数据和最近5天完整饮食记录，不要训练和动作成长数据。", "ready"),
    ("S3-2", "导出最近4次卧推的成长记录。", "ready"),
    ("S3-3", "导出器械飞鸟最近的表现。", "ready"),
    ("S3-4", "导出最近少量饮食和一些代表性动作的全部成长记录。", "ready"),
    ("S3-5", "导出最近2次背部训练前1天的饮食，不包含训练当天。", "ready"),
    ("S3-6", "整理最近45天所有健身数据，但不要动作成长记录，也不要饮食备注。", "ready"),
    ("S3-7", "导出最近7天饮食，并分别导出卧推、引体向上、诺德士高拉、悍马拉背二、单臂绳索下拉、绳索侧平举、哑铃推肩和坐姿腿举的全部成长记录。", "ready"),
    ("S3-8", "列出所有肩部动作名称。", "candidate_confirmation_required"),
    ("S3-9", "把数据库原始记录全部导出来。", "unsupported"),
    ("S3-10", "导出最近四个主要训练动作的最近表现。", "ready"),
]


def post(path: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:8786{path}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def run(output: Path | None = None) -> dict:
    records = []
    for case_id, text, expected in CASES:
        natural = post("/api/analysis-export/v1/natural-language/preview", {"text": text})
        record = {
            "case_id": case_id,
            "input": text,
            "expected_status": expected,
            "status": natural.get("status"),
            "model_calls": natural.get("model_calls"),
            "plan": natural.get("semantic_plan", {}),
            "candidates": natural.get("candidates", []),
            "requests": natural.get("requests", []),
            "previews": [],
            "bundles": [],
            "passed": natural.get("status") == expected and natural.get("model_calls") == 0,
        }
        if expected == "candidate_confirmation_required" and record["candidates"]:
            selected = [item["movement_id"] for item in record["candidates"][:2] if item.get("movement_id")]
            patched = post("/api/analysis-export/v1/natural-language/preview", {"text": text, "selected_movement_ids": selected})
            record["candidate_patch"] = patched
            record["passed"] = record["passed"] and patched.get("status") == "ready" and len(patched.get("requests", [])) == 1
            record["requests"] = patched.get("requests", [])
        for request in record["requests"]:
            preview = post("/api/analysis-export/v1/preview", {"request": request})
            record["previews"].append({
                "status": preview.get("status"),
                "request_fingerprint": fingerprint(preview.get("normalized_request")),
                "dataset_count": preview.get("preview", {}).get("dataset_count"),
                "record_count": preview.get("preview", {}).get("record_count"),
                "warnings": preview.get("preview", {}).get("warnings", []),
                "token": preview.get("confirmation_token", ""),
            })
            record["passed"] = record["passed"] and preview.get("status") == "preview_ready" and not preview.get("preview", {}).get("raw", {}).get("allowed", False)
        records.append(record)

    for confirm_case in (records[1], records[7]):
        if not confirm_case["previews"]:
            continue
        for request, preview in zip(confirm_case["requests"], confirm_case["previews"]):
            result = post("/api/analysis-export/v1/export", {
                "request": request,
                "confirmed": True,
                "confirmation_token": preview["token"],
            })
            confirm_case["bundles"].append({"status": result.get("status"), "bundle_id": result.get("bundle_id", ""), "record_count": result.get("record_count", 0), "safety_flags": result.get("safety_flags", {})})
            confirm_case["passed"] = confirm_case["passed"] and result.get("status") == "bundle_ready" and not result.get("safety_flags", {}).get("raw_included", True) and not result.get("safety_flags", {}).get("formal_data_written", True)

    summary = {
        "schema_version": "fitness-ledger-pure-core-acceptance-v1",
        "model_calls_total": sum(int(item.get("model_calls") or 0) for item in records),
        "passed": sum(bool(item["passed"]) for item in records),
        "total": len(records),
        "records": records,
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--round", type=int, default=1, choices=(1, 2, 3))
    args = parser.parse_args()
    global CASES
    if args.round == 2:
        CASES = ROUND_TWO
    elif args.round == 3:
        CASES = ROUND_THREE
    summary = run(args.output)
    print(json.dumps({key: summary[key] for key in ("passed", "total", "model_calls_total")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
