from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]


def validate_payload() -> dict:
    """Validate the generated replica package without making a network request."""
    path = PROJECT_DIR / "cloud_sync" / "out" / "fitness_ledger_cloud_payload.json"
    if not path.exists():
        raise FileNotFoundError("Build the payload first with build_cloud_payload.py.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "fl_meta", "fl_latest_summary", "fl_daily_records", "fl_diet_records",
        "fl_training_sessions", "fl_movements", "fl_movement_history",
        "fl_raw_entries", "fl_search_index", "fl_data_quality_issues",
    }
    missing = sorted(expected.difference(payload))
    invalid = sorted(name for name, rows in payload.items() if not isinstance(rows, list))
    if missing or invalid:
        raise ValueError(f"Invalid cloud payload; missing={missing}, non_list={invalid}")
    report = {
        "status": "validated_local_payload",
        "network_request_made": False,
        "validated_at": datetime.now().replace(microsecond=0).isoformat(),
        "payload": str(path),
        "collections": {name: len(rows) for name, rows in payload.items()},
        "warnings": ["尚未执行 CloudBase 网络上传；请按 manifest 顺序导入后再核对 fl_meta。"],
    }
    report_path = path.with_name("fitness_ledger_cloud_sync_report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the prepared Fitness Ledger cloud payload.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run: raise SystemExit("Only --dry-run is supported until a cloud provider is explicitly selected.")
    try:
        report = validate_payload()
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print("DRY RUN: no network request was made.")
    for name, count in report["collections"].items(): print(f"{name}: {count}")
    print(f"report: {Path(report['payload']).with_name('fitness_ledger_cloud_sync_report.json')}")

if __name__ == "__main__": main()
